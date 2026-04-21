"""
Intent Detector - Detecta sinais de compra em escolas e gera alertas.

Monitora emails enviados e identifica escolas que estao "quentes":
- Multiplos opens em curto periodo (curiosidade forte)
- Clicks em links (sinal muito forte)
- Replies recebidos (sinal maximo)
- Keywords nas respostas: "interesse", "orcamento", "reuniao", etc.

Para cada sinal detectado, cria um alerta proativo que e enviado ao Fernando
via WhatsApp. Usa a tabela conversation_memory (item 1) para evitar alertar
2x sobre o mesmo sinal.

Niveis de intent (0-100):
- 100: reply com keywords de alta intencao ("orcamento", "reuniao", "contrato")
- 90:  reply qualquer
- 80:  2+ clicks diferentes
- 70:  1 click
- 60:  5+ opens em 48h (muito curioso)
- 50:  3+ opens em 48h (curioso)
- 40:  reabertura apos 7 dias (recall)
- 0:   sem sinais relevantes

Usage:
    from tools.intent_detector import intent_detector

    # Detectar sinais em todo o banco
    signals = intent_detector.detect_all_signals()

    # Detectar sinais nao alertados ainda (para scheduler)
    new_alerts = intent_detector.get_new_alerts()

    # Marcar sinais como alertados
    intent_detector.mark_alerted(signals)
"""
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from database.supabase_client import db
from utils.logger import logger


# Keywords de alta intencao em respostas (case insensitive)
HIGH_INTENT_KEYWORDS = {
    # Compromisso
    "reuniao": 15,
    "reunião": 15,
    "demo": 15,
    "demonstracao": 15,
    "demonstração": 15,
    "apresentacao": 12,
    "apresentação": 12,
    "conversar": 10,
    "conversa": 10,
    "marcar": 12,
    "agendar": 14,
    "call": 12,
    # Valor/orcamento
    "orcamento": 18,
    "orçamento": 18,
    "proposta": 18,
    "preco": 15,
    "preço": 15,
    "valor": 12,
    "investimento": 15,
    "custo": 12,
    "pagamento": 15,
    "contrato": 20,
    # Interesse
    "interesse": 15,
    "interessada": 15,
    "interessado": 15,
    "quero": 12,
    "queremos": 14,
    "gostaria": 10,
    "gostariamos": 12,
    "gostariamos": 12,
    # Prazo
    "quando": 8,
    "prazo": 10,
    "disponibilidade": 10,
    "disponivel": 8,
    "horario": 8,
    "hora": 6,
}


class IntentDetector:
    """Detecta sinais de compra e gera alertas."""

    MEMORY_CATEGORY = "intent_alert"  # marker no campo content da memoria

    def _fetch_sent_emails_with_tracking(self, days: int = 30) -> List[Dict[str, Any]]:
        """Busca emails enviados nos ultimos N dias com dados de tracking."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            result = db.client.table("approval_queue").select(
                "id,company_id,contact_id,subject,body,sent_at,opened_at,clicked_at,replied_at,follow_up_number"
            ).eq("status", "sent").gte("sent_at", cutoff).execute().data or []
            return result
        except Exception as e:
            logger.error(f"Erro ao buscar emails com tracking: {e}")
            return []

    def _fetch_reply_content(self, queue_id: str) -> str:
        """Busca conteudo da resposta do destinatario na tabela interactions."""
        try:
            r = db.client.table("interactions").select(
                "message_snippet,metadata"
            ).eq("approval_queue_id", queue_id).eq("type", "email_replied").limit(1).execute()
            if r.data:
                snippet = r.data[0].get("message_snippet") or ""
                # Tentar extrair mais do metadata (se JSON tem body completo)
                meta = r.data[0].get("metadata") or {}
                if isinstance(meta, dict):
                    body = meta.get("body") or meta.get("content") or ""
                    if body:
                        return str(body)[:2000]
                return str(snippet)[:1000]
            return ""
        except Exception:
            return ""

    def _analyze_reply_keywords(self, text: str) -> Dict[str, Any]:
        """Analisa resposta do destinatario e retorna score + keywords encontradas.
        Tenta primeiro via LLM (analise semantica), fallback para keywords fixas.
        """
        if not text:
            return {"score": 0, "keywords": []}

        # Tentar analise semantica com LLM (mais precisa)
        llm_result = self._analyze_reply_with_llm(text)
        if llm_result and llm_result.get("score", 0) > 0:
            return llm_result

        # Fallback: keywords fixas
        text_lower = text.lower()
        found = []
        score = 0
        for kw, weight in HIGH_INTENT_KEYWORDS.items():
            if kw in text_lower:
                found.append(kw)
                score += weight
        return {"score": min(score, 100), "keywords": list(set(found))}

    def _analyze_reply_with_llm(self, text: str) -> Optional[Dict[str, Any]]:
        """Analisa resposta usando Claude Haiku para classificacao semantica.

        Detecta intencao real alem de keywords — entende contexto, objecoes,
        perguntas genuinas vs respostas automaticas.

        Returns:
            Dict com score (0-100), keywords (list), classificacao (str), proxima_acao (str)
            ou None se LLM nao disponivel/falhar.
        """
        if not text or len(text.strip()) < 5:
            return None
        try:
            import os
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
            if not client.api_key:
                return None

            prompt = (
                "Analise esta resposta de um diretor/coordenador de escola a uma proposta comercial "
                "da IAprendo (plataforma educacional de IA).\n\n"
                f"Resposta: \"{text[:500]}\"\n\n"
                "Classifique em JSON:\n"
                "{\n"
                '  "classificacao": "interesse_alto" | "interesse_medio" | "pergunta" | "objecao" | "rejeicao" | "automatica",\n'
                '  "score": 0-100 (0=rejeicao, 50=neutro, 100=quer comprar),\n'
                '  "keywords": ["palavras-chave detectadas"],\n'
                '  "proxima_acao": "sugestao de proxima acao em 1 frase"\n'
                "}\n\n"
                "Regras:\n"
                "- interesse_alto (80-100): pede orcamento, demo, reuniao, quer saber preco\n"
                "- interesse_medio (50-79): faz perguntas sobre o produto, pede mais info\n"
                "- pergunta (40-60): pergunta generica, pode ser curiosidade\n"
                "- objecao (20-40): diz que ja tem solucao, nao e prioridade, sem orcamento\n"
                "- rejeicao (0-20): nao tem interesse, pede para parar, cancelar\n"
                "- automatica (0): resposta automatica de ferias, ausencia, etc.\n"
                "Responda APENAS o JSON."
            )

            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
            )

            import json
            raw = resp.choices[0].message.content.strip()
            # Limpar markdown se houver
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)

            score = int(result.get("score", 0))
            keywords = result.get("keywords", [])
            classificacao = result.get("classificacao", "")
            proxima_acao = result.get("proxima_acao", "")

            logger.info(
                f"Intent LLM: {classificacao} (score={score})",
                extra={"keywords": keywords, "proxima_acao": proxima_acao},
            )

            return {
                "score": score,
                "keywords": keywords,
                "classificacao": classificacao,
                "proxima_acao": proxima_acao,
            }
        except Exception as e:
            logger.debug(f"Intent LLM fallback para keywords: {e}")
            return None

    def _compute_signal(self, email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analisa um email e retorna sinal de intent (se houver).
        Retorna None se nao ha sinal relevante (score < 40).
        """
        sent_at = email.get("sent_at")
        opened_at = email.get("opened_at")
        clicked_at = email.get("clicked_at")
        replied_at = email.get("replied_at")

        signal = {
            "queue_id": email["id"],
            "company_id": email.get("company_id"),
            "contact_id": email.get("contact_id"),
            "subject": email.get("subject", ""),
            "sent_at": sent_at,
            "score": 0,
            "level": "none",
            "reasons": [],
            "keywords": [],
        }

        # === REPLY (sinal maximo) ===
        if replied_at:
            signal["score"] = 90
            signal["reasons"].append("respondeu o email")
            # Analisar keywords na resposta
            reply_text = self._fetch_reply_content(email["id"])
            if reply_text:
                analysis = self._analyze_reply_keywords(reply_text)
                if analysis["keywords"]:
                    signal["score"] = min(100, 90 + analysis["score"] // 3)
                    signal["keywords"] = analysis["keywords"]
                    signal["reasons"].append(f"mencionou: {', '.join(analysis['keywords'][:3])}")
            signal["level"] = "critico" if signal["score"] >= 95 else "alto"
            signal["reply_preview"] = reply_text[:300] if reply_text else ""
            return signal

        # === CLICK (sinal forte) ===
        if clicked_at:
            signal["score"] = 75
            signal["reasons"].append("clicou em link do email")
            signal["level"] = "alto"
            return signal

        # === MULTIPLE OPENS (sinal medio) ===
        # Heuristica: se sent_at e opened_at diferem em > 24h, indica
        # que abriu mais de uma vez (Brevo atualiza opened_at no ultimo open)
        if opened_at and sent_at:
            try:
                sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
                open_dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                hours_diff = (open_dt - sent_dt).total_seconds() / 3600

                # Reabriu depois de 24h
                if hours_diff > 24:
                    signal["score"] = 50
                    signal["reasons"].append(f"reabriu apos {int(hours_diff)}h")
                    signal["level"] = "medio"
                    return signal
                # Reabriu depois de 7 dias (recall forte)
                if hours_diff > 168:
                    signal["score"] = 60
                    signal["reasons"].append("reabriu apos 1 semana (interesse latente)")
                    signal["level"] = "medio"
                    return signal
            except Exception:
                pass

        return None

    def detect_all_signals(self, days: int = 30) -> List[Dict[str, Any]]:
        """Detecta TODOS os sinais de intent nos ultimos N dias."""
        emails = self._fetch_sent_emails_with_tracking(days=days)
        signals = []
        for e in emails:
            sig = self._compute_signal(e)
            if sig:
                signals.append(sig)
        # Ordenar por score descendente
        signals.sort(key=lambda s: s["score"], reverse=True)
        return signals

    # ============================================================
    # CLASSIFICACAO LLM PUBLICA (F7 - Inbox de Respostas)
    # ============================================================
    def classify_replies(self, days: int = 30, use_llm: bool = True,
                         min_score: int = 50) -> List[Dict[str, Any]]:
        """Retorna replies recentes com classificacao LLM (cache 1h em memoria).

        Usado pelo Inbox de Respostas no dashboard.

        Args:
            days: janela temporal.
            use_llm: usa GPT-4.1-mini (semantico); se False, so keywords.
            min_score: filtro minimo (so replies com score >= esse).

        Returns:
            Lista de dicts com: queue_id, company_id, company_name, contact_name,
            subject, reply_text (preview 300 chars), replied_at, classificacao,
            acao_sugerida, score, keywords, reasons.
        """
        signals = self.detect_all_signals(days=days)
        results = []

        for s in signals:
            # So replies (tem replied_at)
            if not s.get("reply_preview"):
                continue
            if s.get("score", 0) < min_score:
                continue

            queue_id = s.get("queue_id")
            reply_text = s.get("reply_preview", "")

            # Cache de classificacao (evita re-chamar LLM)
            cached = self._get_cached_classification(queue_id) if queue_id else None
            if cached:
                classification = cached
            else:
                # Classificar
                if use_llm and reply_text:
                    classification = self._analyze_reply_with_llm(reply_text) or {}
                else:
                    classification = self._analyze_reply_keywords(reply_text)

                # Salvar cache 1h
                if queue_id and classification:
                    self._cache_classification(queue_id, classification)

            # Enrich com info de escola/contato
            enriched = self.enrich_signal_with_context(s) if hasattr(self, "enrich_signal_with_context") else s

            results.append({
                "queue_id": queue_id,
                "company_id": s.get("company_id"),
                "company_name": enriched.get("company_name", "?"),
                "city": enriched.get("city", ""),
                "contact_name": enriched.get("contact_name", ""),
                "subject": s.get("subject", "")[:80],
                "reply_text": reply_text[:300],
                "replied_at": s.get("sent_at", ""),  # timestamp do email (replied_at fica implicito)
                "score": s.get("score", 0),
                "level": s.get("level", ""),
                "keywords": classification.get("keywords", []),
                "classificacao": classification.get("classificacao", "sem_classificacao"),
                "acao_sugerida": classification.get("proxima_acao", ""),
                "reasons": s.get("reasons", []),
            })

        return results

    def _get_cached_classification(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """Retorna classificacao cacheada (TTL 1h) ou None."""
        try:
            from integrations.memory import memory
            if not memory.is_available():
                return None
            marker = f"[INTENT_CLS:{queue_id}]"
            existing = memory.search(marker, limit=3)
            for mem in existing:
                content = mem.get("content", "")
                if marker not in content:
                    continue
                # Parse JSON payload after marker
                try:
                    import json as _json
                    payload_str = content.split(marker, 1)[1].strip()
                    payload = _json.loads(payload_str)
                    # Verificar TTL 1h
                    ts = payload.get("_cached_at", 0)
                    import time as _t
                    if _t.time() - ts < 3600:
                        return payload
                except Exception:
                    continue
            return None
        except Exception:
            return None

    def _cache_classification(self, queue_id: str, classification: Dict[str, Any]) -> None:
        """Cacheia classificacao por 1h em conversation_memory."""
        try:
            from integrations.memory import memory
            if not memory.is_available():
                return
            import json as _json, time as _t
            payload = {**classification, "_cached_at": _t.time()}
            marker = f"[INTENT_CLS:{queue_id}]"
            content = f"{marker} {_json.dumps(payload, ensure_ascii=False)}"
            memory.remember(
                content=content,
                scope="global",
                category="insight",
                importance=1,  # baixa prioridade, eh so cache
            )
        except Exception:
            pass

    # ============================================================
    # DEDUPLICACAO VIA MEMORY
    # ============================================================
    def _already_alerted(self, queue_id: str, score: int) -> bool:
        """Verifica se ja alertamos sobre esse sinal (via memoria)."""
        try:
            from integrations.memory import memory
            if not memory.is_available():
                return False
            # Marker formato: "[INTENT_ALERT:queue_id:score]"
            marker = f"[INTENT_ALERT:{queue_id}"
            existing = memory.search(marker, limit=5)
            for mem in existing:
                content = mem.get("content", "")
                if marker in content:
                    # Ja alertamos — nao realertar a menos que score subiu significativamente
                    try:
                        # Extrair score antigo
                        parts = content.split(":")
                        old_score = int(parts[2].rstrip("]"))
                        if score - old_score < 20:
                            return True  # nao subiu o suficiente
                    except Exception:
                        return True
            return False
        except Exception:
            return False

    def mark_alerted(self, signal: Dict[str, Any]) -> None:
        """Registra na memoria que ja alertamos sobre esse sinal."""
        try:
            from integrations.memory import memory
            if not memory.is_available():
                return
            queue_id = signal.get("queue_id", "")
            score = signal.get("score", 0)
            reasons = ", ".join(signal.get("reasons", []))
            marker = f"[INTENT_ALERT:{queue_id}:{score}] {reasons}"
            memory.remember(
                content=marker,
                scope="company",
                scope_id=signal.get("company_id"),
                category="insight",
                importance=min(10, max(5, score // 10)),
                source="auto",
            )
        except Exception as e:
            logger.debug(f"Erro ao marcar alerta: {e}")

    def get_new_alerts(self, days: int = 7, min_score: int = 50) -> List[Dict[str, Any]]:
        """Retorna sinais novos (nao alertados ainda) dos ultimos N dias.
        Para uso pelo scheduler automatico.
        """
        signals = self.detect_all_signals(days=days)
        new = []
        for sig in signals:
            if sig["score"] < min_score:
                continue
            if self._already_alerted(sig["queue_id"], sig["score"]):
                continue
            new.append(sig)
        return new

    # ============================================================
    # ENRIQUECIMENTO
    # ============================================================
    def enrich_signal_with_context(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona nome da escola, contato e detalhes para formatacao."""
        try:
            cid = signal.get("company_id")
            if cid:
                comp = db.client.table("companies").select(
                    "name,city,state,phone,qualification_score,admin_category,school_size"
                ).eq("id", cid).limit(1).execute().data
                if comp:
                    signal["_company"] = comp[0]

            ct_id = signal.get("contact_id")
            if ct_id:
                ct = db.client.table("contacts").select(
                    "full_name,role,email,phone"
                ).eq("id", ct_id).limit(1).execute().data
                if ct:
                    signal["_contact"] = ct[0]
        except Exception as e:
            logger.debug(f"Erro ao enriquecer sinal: {e}")
        return signal

    def format_for_whatsapp(self, signal: Dict[str, Any]) -> str:
        """Formata sinal como mensagem de alerta WhatsApp."""
        signal = self.enrich_signal_with_context(signal)
        comp = signal.get("_company", {}) or {}
        contact = signal.get("_contact", {}) or {}

        # Emoji por nivel
        level_emoji = {
            "critico": "🔥🔥🔥",
            "alto": "🔥🔥",
            "medio": "🔥",
        }
        emoji = level_emoji.get(signal.get("level", "medio"), "🔥")

        score = signal.get("score", 0)
        reasons = signal.get("reasons", [])

        lines = [f"{emoji} *SINAL DE COMPRA DETECTADO* (score {score}/100)"]
        lines.append("")
        lines.append(f"🏫 *{comp.get('name', '?')}*")
        if comp.get("city"):
            lines.append(f"📍 {comp['city']}/{comp.get('state', '')}")
        if contact.get("full_name"):
            lines.append(f"👤 {contact['full_name']} ({contact.get('role', '')})")
        lines.append("")
        lines.append("📊 *Por que alertei:*")
        for r in reasons:
            lines.append(f"   • {r}")

        if signal.get("keywords"):
            lines.append("")
            lines.append(f"🎯 *Keywords detectadas:* {', '.join(signal['keywords'][:5])}")

        reply_preview = signal.get("reply_preview", "")
        if reply_preview:
            lines.append("")
            lines.append(f"💬 *Preview da resposta:*")
            lines.append(f"_{reply_preview[:200]}_")

        lines.append("")
        lines.append("⚡ *Acao recomendada:*")
        if score >= 95:
            lines.append("   LIGUE AGORA. Esse lead esta no ponto de fechamento.")
        elif score >= 80:
            lines.append("   Responda hoje com proposta ou convite para reuniao.")
        elif score >= 60:
            lines.append("   Follow-up personalizado nas proximas 24h.")
        else:
            lines.append("   Adicione ao topo da lista de contato.")

        return "\n".join(lines)


intent_detector = IntentDetector()
