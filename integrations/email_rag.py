"""
Email RAG - Retrieval-Augmented Generation para emails de prospecao.

Busca emails passados que tiveram sucesso (receberam resposta, foram abertos,
tiveram links clicados) e usa como exemplos contextuais ao gerar novos emails.

A ideia: em vez do GPT gerar emails do zero, ele aprende com o que ja funcionou
no passado. Cada email novo fica melhor que o anterior.

Criterios de "sucesso" (em ordem de prioridade):
1. replied_at not null (alguem respondeu) — MAIOR PRIORIDADE
2. clicked_at not null (clicou no link)
3. opened_at not null (abriu o email)

Similaridade (opcional): se fornecido company_id, prioriza exemplos de escolas
similares (mesmo porte, mesma cidade, mesmo tipo).

Cache em memoria: emails bem-sucedidos mudam raramente, cacheamos por 10 min
para evitar queries repetidas.

Usage:
    from integrations.email_rag import email_rag

    # Buscar top 3 emails bem-sucedidos
    examples = email_rag.get_successful_examples(limit=3)

    # Buscar exemplos similares a uma escola
    examples = email_rag.get_successful_examples(
        limit=3,
        company_context={"school_size": "Mais de 1000", "admin_category": "Privada"}
    )

    # Formatar como texto para injetar no prompt
    text = email_rag.format_for_prompt(examples)
"""
import time
from typing import List, Dict, Any, Optional

from database.supabase_client import db
from utils.logger import logger


class EmailRAG:
    """Retrieval de emails bem-sucedidos para RAG."""

    CACHE_TTL_SECONDS = 600  # 10 minutos

    def __init__(self) -> None:
        self._cache: Optional[List[Dict[str, Any]]] = None
        self._cache_ts: float = 0

    def _fetch_all_successful(self) -> List[Dict[str, Any]]:
        """Busca TODOS os emails bem-sucedidos do banco (cache interno)."""
        now = time.time()
        if self._cache is not None and (now - self._cache_ts) < self.CACHE_TTL_SECONDS:
            return self._cache

        try:
            # Buscar emails enviados com qualquer sinal de sucesso
            # Ordem de prioridade: reply > click > open
            all_success = []

            # 1) Responded emails (maior prioridade)
            try:
                replied = db.client.table("approval_queue").select(
                    "id,subject,body,company_id,contact_id,sent_at,replied_at,opened_at,clicked_at"
                ).eq("status", "sent").not_.is_("replied_at", "null").order(
                    "replied_at", desc=True
                ).limit(50).execute().data or []
                for e in replied:
                    e["_rag_tier"] = 1  # reply
                    all_success.append(e)
            except Exception:
                pass

            # 2) Clicked emails (ainda nao respondeu, mas clicou)
            try:
                clicked = db.client.table("approval_queue").select(
                    "id,subject,body,company_id,contact_id,sent_at,replied_at,opened_at,clicked_at"
                ).eq("status", "sent").is_("replied_at", "null").not_.is_("clicked_at", "null").order(
                    "clicked_at", desc=True
                ).limit(30).execute().data or []
                for e in clicked:
                    e["_rag_tier"] = 2  # click
                    all_success.append(e)
            except Exception:
                pass

            # 3) Opened emails (fallback minimo)
            try:
                opened = db.client.table("approval_queue").select(
                    "id,subject,body,company_id,contact_id,sent_at,replied_at,opened_at,clicked_at"
                ).eq("status", "sent").is_("replied_at", "null").is_("clicked_at", "null").not_.is_("opened_at", "null").order(
                    "opened_at", desc=True
                ).limit(30).execute().data or []
                for e in opened:
                    e["_rag_tier"] = 3  # open
                    all_success.append(e)
            except Exception:
                pass

            # Enriquecer com dados da escola e do contato
            company_ids = list({e["company_id"] for e in all_success if e.get("company_id")})
            contact_ids = list({e["contact_id"] for e in all_success if e.get("contact_id")})

            companies_map: Dict[str, Dict] = {}
            if company_ids:
                try:
                    comps = db.client.table("companies").select(
                        "id,name,city,state,school_size,admin_category,qualification_score"
                    ).in_("id", company_ids).execute().data or []
                    companies_map = {c["id"]: c for c in comps}
                except Exception:
                    pass

            contacts_map: Dict[str, Dict] = {}
            if contact_ids:
                try:
                    cts = db.client.table("contacts").select(
                        "id,full_name,role,decision_maker_type"
                    ).in_("id", contact_ids).execute().data or []
                    contacts_map = {c["id"]: c for c in cts}
                except Exception:
                    pass

            for e in all_success:
                e["_company"] = companies_map.get(e.get("company_id"), {})
                e["_contact"] = contacts_map.get(e.get("contact_id"), {})

            # Cache
            self._cache = all_success
            self._cache_ts = now
            logger.info(f"Email RAG: {len(all_success)} emails bem-sucedidos carregados no cache")
            return all_success

        except Exception as e:
            logger.error(f"Erro ao buscar emails bem-sucedidos: {e}")
            return self._cache or []

    def _score_similarity(
        self, email: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Calcula score de similaridade entre um email e o contexto alvo.
        Quanto maior, mais similar (mais relevante).
        """
        score = 0.0
        comp = email.get("_company", {}) or {}

        # Mesmo porte: muito relevante
        if context.get("school_size") and comp.get("school_size"):
            if context["school_size"] == comp["school_size"]:
                score += 3.0

        # Mesmo tipo (publica/privada): relevante
        if context.get("admin_category") and comp.get("admin_category"):
            if context["admin_category"] == comp["admin_category"]:
                score += 2.0

        # Mesma cidade: bonus
        if context.get("city") and comp.get("city"):
            if context["city"].lower() == comp["city"].lower():
                score += 1.5

        # Mesmo estado: bonus menor
        if context.get("state") and comp.get("state"):
            if context["state"] == comp["state"]:
                score += 0.5

        # Mesmo tipo de decisor: relevante
        if context.get("decision_maker_type") and email.get("_contact"):
            if email["_contact"].get("decision_maker_type") == context["decision_maker_type"]:
                score += 1.5

        return score

    def get_successful_examples(
        self,
        limit: int = 3,
        company_context: Optional[Dict[str, Any]] = None,
        exclude_company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna os N emails mais relevantes que tiveram sucesso.

        Args:
            limit: Max exemplos a retornar
            company_context: Dict com dados da escola alvo (school_size,
                             admin_category, city, state, decision_maker_type)
                             para ranquear por similaridade.
            exclude_company_id: Nao incluir emails dessa escola (evita
                                gerar o mesmo email que ja foi enviado).
        """
        all_success = self._fetch_all_successful()
        if not all_success:
            return []

        # Filtrar escola excluida
        candidates = [
            e for e in all_success
            if e.get("company_id") != exclude_company_id
        ]

        # Scoring:
        # - Tier 1 (reply) = 10 pontos base
        # - Tier 2 (click) = 5 pontos base
        # - Tier 3 (open) = 2 pontos base
        # + similaridade (0-8 pontos extras)
        tier_base = {1: 10.0, 2: 5.0, 3: 2.0}

        for e in candidates:
            base = tier_base.get(e.get("_rag_tier", 3), 1.0)
            sim = self._score_similarity(e, company_context or {})
            e["_rag_score"] = base + sim

        candidates.sort(key=lambda x: x.get("_rag_score", 0), reverse=True)
        return candidates[:limit]

    def format_for_prompt(self, examples: List[Dict[str, Any]]) -> str:
        """Formata exemplos como texto para injetar em prompt do LLM."""
        if not examples:
            return ""

        parts = ["=== EXEMPLOS DE EMAILS QUE FUNCIONARAM ==="]
        parts.append(
            "Estes sao emails reais enviados por voce que geraram engajamento "
            "(respostas, cliques ou aberturas). Use-os como referencia de tom, "
            "estilo e estrutura ao gerar o novo email:\n"
        )

        tier_label = {
            1: "RESPONDIDO pelo destinatario",
            2: "com link CLICADO",
            3: "ABERTO mas sem reply",
        }

        for i, e in enumerate(examples, 1):
            comp = e.get("_company", {}) or {}
            contact = e.get("_contact", {}) or {}
            tier = e.get("_rag_tier", 3)
            tier_txt = tier_label.get(tier, "enviado")

            subject = e.get("subject", "")
            body = e.get("body", "") or ""
            # Limitar corpo a 1500 chars para nao estourar contexto
            if len(body) > 1500:
                body = body[:1500] + "\n[... truncado ...]"

            parts.append(f"\n--- EXEMPLO {i} ({tier_txt}) ---")
            parts.append(f"Escola: {comp.get('name', '?')} ({comp.get('city', '')}/{comp.get('state', '')})")
            parts.append(f"Porte: {comp.get('school_size', '?')} | Tipo: {comp.get('admin_category', '?')}")
            if contact.get("full_name"):
                parts.append(f"Destinatario: {contact.get('full_name')} ({contact.get('role', '')})")
            parts.append(f"Assunto: {subject}")
            parts.append(f"Corpo:\n{body}")

        parts.append("\n=== FIM DOS EXEMPLOS ===")
        parts.append(
            "INSTRUCOES: Analise o tom, estrutura e argumentos dos emails acima. "
            "Adapte para a nova escola mantendo o que funcionou, mas PERSONALIZE "
            "com os dados especificos da escola alvo. NUNCA copie texto literal — "
            "inspire-se no estilo.\n"
        )
        return "\n".join(parts)

    def invalidate_cache(self) -> None:
        """Forca recarregamento do cache na proxima chamada."""
        self._cache = None
        self._cache_ts = 0

    def stats(self) -> Dict[str, Any]:
        """Retorna estatisticas dos emails bem-sucedidos no cache."""
        all_success = self._fetch_all_successful()
        by_tier = {1: 0, 2: 0, 3: 0}
        for e in all_success:
            by_tier[e.get("_rag_tier", 3)] += 1
        return {
            "total": len(all_success),
            "respondidos": by_tier[1],
            "clicados": by_tier[2],
            "abertos": by_tier[3],
            "cache_age_seconds": int(time.time() - self._cache_ts) if self._cache else None,
        }


email_rag = EmailRAG()
