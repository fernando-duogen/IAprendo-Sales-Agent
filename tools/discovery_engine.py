"""
Discovery Engine - Descoberta inteligente de escolas além do MEC (Item 8).

Duas capacidades:
1. discover_schools(cidade, tipo, keyword) → encontra escolas que NAO estao no MEC
   via Perplexity (busca generativa). Escolas novas entram em status='discovered'
   (staging) para Fernando revisar antes de promover ao pipeline normal.

2. enrich_signals(company_id) → busca rankings, premios, noticias e expansoes
   sobre uma escola especifica e salva em conversation_memory como insights.
   Alimenta qualifier, writer e RAG automaticamente (infra do Item 1).

REGRAS:
- INEP sintetico para escolas externas: 'EXT-{md5(normalized_name + city)[:8]}'
  (respeita constraint UNIQUE NOT NULL, identifica origem no proprio ID)
- Deduplicacao secundaria por nome normalizado + cidade (evita duplicar
  escolas que ja existem no MEC sem INEP original)
- Discovery e read-only externamente (so le Perplexity, escreve no proprio
  banco). Seguro em qualquer nivel de autonomia.

Usage:
    from tools.discovery_engine import discovery_engine

    # Descobrir novas escolas
    result = discovery_engine.discover_schools(
        cidade="Canoas", tipo="privada", keyword="bilingue", limit=5
    )

    # Enriquecer escola existente com sinais contextuais
    signals = discovery_engine.enrich_signals(company_id="uuid-...")
"""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from utils.logger import logger


# Stopwords de nomes de escolas (removidas na normalizacao para dedup)
_NAME_STOPWORDS = {
    "colegio", "escola", "instituto", "centro", "educacional", "educativo",
    "ensino", "ceu", "ciep", "cem", "cmei", "emeief", "eeem", "eeb",
    "fundamental", "medio", "infantil", "tecnico", "curso", "academia",
    "de", "da", "do", "das", "dos", "e", "em",
}

# Similaridade minima (0-1) para considerar dois nomes como mesma escola
_DEDUP_THRESHOLD = 0.88


class DiscoveryEngine:
    """Motor de descoberta e enriquecimento de escolas via Perplexity."""

    # =========================================================================
    # Helpers
    # =========================================================================

    def _normalize_name(self, s: Optional[str]) -> str:
        """Normaliza nome de escola para dedup: remove acentos, lowercase, strip
        stopwords comuns e pontuacao."""
        if not s:
            return ""
        # Remove acentos
        nfkd = unicodedata.normalize("NFKD", str(s))
        ascii_str = nfkd.encode("ASCII", "ignore").decode("ASCII").lower()
        # Remove pontuacao basica
        ascii_str = re.sub(r"[^\w\s]", " ", ascii_str)
        # Tokenizar e remover stopwords
        tokens = [t for t in ascii_str.split() if t and t not in _NAME_STOPWORDS]
        return " ".join(tokens).strip()

    def _normalize_city(self, city: Optional[str]) -> str:
        if not city:
            return ""
        nfkd = unicodedata.normalize("NFKD", str(city))
        return nfkd.encode("ASCII", "ignore").decode("ASCII").lower().strip()

    def _synthetic_inep(self, name: str, city: str) -> str:
        """Gera INEP sintetico deterministico para escolas fora do MEC.
        Formato: 'EXT-{md5[:8]}' — 12 chars (cabe em VARCHAR(20)).
        """
        key = f"{self._normalize_name(name)}|{self._normalize_city(city)}"
        h = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
        return f"EXT-{h}"

    def _dedup_by_name_city(
        self, name: str, city: str
    ) -> Optional[Dict[str, Any]]:
        """Busca escola existente por similaridade de nome + cidade. Retorna
        dict com id e dados se encontrou match >= _DEDUP_THRESHOLD, senao None.
        """
        norm_name = self._normalize_name(name)
        if not norm_name:
            return None
        norm_city = self._normalize_city(city)

        try:
            # Buscar candidatas na mesma cidade (sem filtro por acento — usa
            # ilike e filtra em Python). Limit generoso pra cobrir variacoes.
            q = db.client.table("companies").select(
                "id,name,city,state,status,inep_code"
            )
            if norm_city:
                # Busca por cidade usando ILIKE com primeiros 5 caracteres
                # (evita problema de acento parcial)
                prefix = norm_city[:5] if len(norm_city) >= 5 else norm_city
                q = q.ilike("city", f"%{prefix}%")
            candidates = q.limit(200).execute().data or []

            best_id = None
            best_score = 0.0
            for c in candidates:
                c_norm = self._normalize_name(c.get("name"))
                if not c_norm:
                    continue
                # Cidade tem que bater (normalizada)
                if norm_city and self._normalize_city(c.get("city")) != norm_city:
                    # permite substring (ex: "Porto Alegre" vs "POA")
                    if norm_city not in self._normalize_city(c.get("city") or ""):
                        continue
                score = SequenceMatcher(None, norm_name, c_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_id = c["id"]
                    best_match = c
            if best_id and best_score >= _DEDUP_THRESHOLD:
                logger.info(
                    "Dedup: match encontrado",
                    extra={
                        "name": name, "city": city,
                        "match_id": best_id, "score": round(best_score, 2),
                    },
                )
                return best_match  # type: ignore
            return None
        except Exception as e:
            logger.debug(f"dedup error: {e}")
            return None

    # =========================================================================
    # Perplexity wrapper + LLM parser (2-step: busca → parse)
    # =========================================================================

    def _ask_perplexity(self, prompt: str, timeout: int = 60) -> str:
        """Chama Perplexity Browser e retorna resposta em texto livre.
        Se nao disponivel, retorna string vazia."""
        try:
            from tools.perplexity_browser import perplexity_browser
            if not perplexity_browser.is_available():
                logger.warning("Perplexity Browser nao disponivel (Playwright ausente?)")
                return ""
            return perplexity_browser._query_perplexity_text(prompt, timeout_seconds=timeout)
        except Exception as e:
            logger.error(f"Perplexity error: {e}")
            return ""

    def _text_to_json_via_llm(
        self, text: str, schema_instruction: str, max_tokens: int = 2048
    ) -> List[Dict[str, Any]]:
        """Converte texto livre em JSON array estruturado usando GPT/Claude.
        Pipeline robusto: Perplexity busca info (texto) → LLM parseia em JSON.

        Args:
            text: texto livre retornado pelo Perplexity
            schema_instruction: descricao do schema JSON esperado
            max_tokens: limite de tokens da resposta
        Returns:
            Lista de dicts parseada ou []
        """
        if not text or len(text.strip()) < 20:
            return []

        # Limitar texto pra nao estourar contexto (primeiros 4000 chars)
        text_trimmed = text[:4000]

        system_msg = (
            "Voce e um parser de dados. Recebe texto livre com informacoes "
            "sobre escolas e extrai EXCLUSIVAMENTE um JSON array valido. "
            "Responda APENAS com o JSON array (sem texto, sem explicacao, "
            "sem markdown). Se nao encontrar dados, retorne []."
        )
        user_msg = (
            f"Extraia os dados de escolas do texto abaixo.\n\n"
            f"SCHEMA ESPERADO:\n{schema_instruction}\n\n"
            f"TEXTO FONTE:\n---\n{text_trimmed}\n---\n\n"
            f"Retorne APENAS o JSON array:"
        )

        try:
            import os
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
                result_text = resp.choices[0].message.content or ""
                logger.info("LLM parser: resposta recebida", extra={"len": len(result_text)})
                return self._extract_json_array(result_text)

            # Fallback: Anthropic
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
            if anthropic_key:
                from anthropic import Anthropic
                client = Anthropic(api_key=anthropic_key)
                resp = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=max_tokens,
                    system=system_msg,
                    messages=[{"role": "user", "content": user_msg}],
                )
                result_text = resp.content[0].text if resp.content else ""
                return self._extract_json_array(result_text)

            logger.warning("Nenhuma API key (OpenAI/Anthropic) disponivel para LLM parser")
            return []

        except Exception as e:
            logger.error(f"LLM parser error: {e}")
            return []

    def _extract_json_array(self, text: str) -> List[Dict[str, Any]]:
        """Extrai primeiro array JSON valido do texto. Retorna lista ou []."""
        if not text:
            return []
        # Limpar markdown code blocks
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        # Tenta o texto inteiro
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "escolas" in data:
                return data["escolas"] or []
        except Exception:
            pass
        # Regex: pegar maior [...] no texto
        match = re.search(r"\[[\s\S]*\]", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return data
            except Exception:
                pass
        return []

    # =========================================================================
    # 1. Discover Schools
    # =========================================================================

    def discover_schools(
        self,
        cidade: str,
        tipo: str = "privada",
        keyword: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Descobre escolas em uma cidade via Perplexity. Aplica dedup por
        nome+cidade antes de inserir. Escolas novas viram status='discovered'.

        Args:
            cidade: cidade alvo (ex: "Canoas")
            tipo: "privada", "publica" ou "qualquer"
            keyword: diferencial opcional ("bilingue", "integral", "Waldorf")
            limit: max escolas a retornar

        Returns:
            dict com novas, existentes_atualizadas, erros, resumo
        """
        limit = max(1, min(int(limit or 10), 30))
        tipo = (tipo or "privada").lower().strip()
        keyword = (keyword or "").strip()

        logger.info("Discovery: iniciando", extra={
            "cidade": cidade, "tipo": tipo, "keyword": keyword, "limit": limit,
        })

        # Monta prompt para Perplexity (pede TEXTO legivel, nao JSON —
        # Perplexity nao retorna JSON puro de forma confiavel)
        keyword_line = f" Priorize escolas com caracteristica: {keyword}." if keyword else ""
        tipo_txt = {
            "privada": "privadas",
            "publica": "publicas",
            "qualquer": "privadas ou publicas",
        }.get(tipo, "privadas")

        prompt = (
            f"Liste ate {limit} escolas {tipo_txt} em {cidade} que ofereçam "
            f"ensino Fundamental anos finais e/ou Ensino Medio.{keyword_line} "
            f"Para cada escola, inclua: nome completo, endereco (rua e bairro), "
            f"site oficial, telefone e diferenciais (bilingue, integral, etc). "
            f"Organize em lista numerada."
        )

        logger.info("Discovery: consultando Perplexity", extra={"prompt_len": len(prompt)})
        response_text = self._ask_perplexity(prompt, timeout=90)

        if not response_text or len(response_text.strip()) < 30:
            logger.warning("Discovery: Perplexity retornou resposta vazia/curta")
            return {
                "cidade": cidade, "tipo": tipo, "keyword": keyword,
                "novas": [], "existentes_atualizadas": [],
                "erros": ["Perplexity nao retornou dados suficientes"],
                "total_encontradas": 0,
            }

        # 2-step: usar LLM (GPT) para parsear texto livre em JSON estruturado
        logger.info("Discovery: parseando texto via LLM", extra={"text_len": len(response_text)})
        schema = (
            'Array JSON. Cada item: {"nome": "string", "endereco": "string ou null", '
            '"bairro": "string ou null", "site": "URL ou null", '
            '"telefone": "string ou null", '
            '"diferenciais": ["bilingue","integral",...], '
            '"tipo": "privada" ou "publica"}'
        )
        schools = self._text_to_json_via_llm(response_text, schema)

        if not schools:
            logger.warning("Discovery: nenhuma escola extraida da resposta", extra={
                "response_preview": response_text[:300] if response_text else "(vazio)",
            })
            return {
                "cidade": cidade,
                "tipo": tipo,
                "keyword": keyword,
                "novas": [],
                "existentes_atualizadas": [],
                "erros": ["Perplexity nao retornou JSON valido"],
                "total_encontradas": 0,
            }

        novas: List[Dict[str, Any]] = []
        existentes: List[Dict[str, Any]] = []
        erros: List[str] = []

        for school in schools[:limit]:
            if not isinstance(school, dict):
                continue
            name = str(school.get("nome") or "").strip()
            if not name or len(name) < 3:
                continue

            school_city = cidade  # assume cidade da busca
            school_state = self._infer_state_for_city(cidade)

            try:
                # Dedup
                existing = self._dedup_by_name_city(name, school_city)
                if existing:
                    # Ja existe — apenas registra que teve sinal de discovery
                    try:
                        from integrations.memory import memory
                        memory.remember(
                            content=(
                                f"Discovery confirmou escola existente via Perplexity "
                                f"(busca: {cidade}/{tipo}/{keyword or 'geral'})"
                            ),
                            scope="company",
                            scope_id=existing["id"],
                            category="fact",
                            importance=4,
                            source="discovery_engine",
                        )
                    except Exception:
                        pass
                    existentes.append({
                        "id": existing["id"],
                        "nome": existing.get("name"),
                        "status_atual": existing.get("status"),
                    })
                    continue

                # Nova escola
                inep = self._synthetic_inep(name, school_city)
                address = school.get("endereco") or ""
                bairro = school.get("bairro") or ""
                full_address = (
                    f"{address}, {bairro}" if address and bairro else (address or bairro or "")
                )
                differentiators = school.get("diferenciais") or []
                if isinstance(differentiators, str):
                    differentiators = [differentiators]

                company_data = {
                    "inep_code": inep,
                    "name": name[:500],
                    "city": school_city,
                    "state": school_state,
                    "address": (full_address or None),
                    "phone": school.get("telefone"),
                    "website": school.get("site"),
                    "admin_category": (
                        "Privada" if str(school.get("tipo") or tipo).lower().startswith("priv")
                        else "Publica"
                    ),
                    "education_levels": "Fundamental, Medio",
                    "status": "discovered",
                    "source": "web_discovery",
                    "notes": json.dumps({
                        "discovery_query": {
                            "cidade": cidade, "tipo": tipo, "keyword": keyword,
                        },
                        "diferenciais": differentiators,
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "origem": "perplexity",
                    }, ensure_ascii=False),
                }

                new_id = db.insert_company(company_data)
                if new_id:
                    # Grava diferenciais como memory (insights)
                    if differentiators:
                        try:
                            from integrations.memory import memory
                            memory.remember(
                                content=f"Diferenciais: {', '.join(differentiators)}",
                                scope="company",
                                scope_id=new_id,
                                category="insight",
                                importance=6,
                                source="discovery_engine",
                            )
                        except Exception:
                            pass
                    novas.append({
                        "id": new_id,
                        "nome": name,
                        "cidade": school_city,
                        "inep_sintetico": inep,
                        "site": school.get("site"),
                        "telefone": school.get("telefone"),
                        "diferenciais": differentiators,
                    })
            except Exception as e:
                logger.error(f"Erro ao processar escola discovery: {e}")
                erros.append(f"{name}: {str(e)[:100]}")

        result = {
            "cidade": cidade,
            "tipo": tipo,
            "keyword": keyword,
            "total_encontradas": len(schools),
            "novas": novas,
            "existentes_atualizadas": existentes,
            "erros": erros,
        }
        logger.info("Discovery concluido", extra={
            "novas": len(novas),
            "existentes": len(existentes),
            "erros": len(erros),
        })
        return result

    def _infer_state_for_city(self, city: str) -> str:
        """Heuristica simples: cidades conhecidas → UF. Senao retorna ''."""
        city_norm = self._normalize_city(city)
        # Mapeamento basico — suficiente para ICP inicial
        city_uf = {
            "porto alegre": "RS", "canoas": "RS", "gravatai": "RS",
            "novo hamburgo": "RS", "sao leopoldo": "RS", "viamao": "RS",
            "caxias do sul": "RS", "pelotas": "RS", "santa maria": "RS",
            "sao paulo": "SP", "rio de janeiro": "RJ", "belo horizonte": "MG",
            "curitiba": "PR", "florianopolis": "SC", "brasilia": "DF",
        }
        return city_uf.get(city_norm, "")

    # =========================================================================
    # 2. Enrich Signals (rankings, premios, noticias)
    # =========================================================================

    def enrich_signals(self, company_id: str) -> Dict[str, Any]:
        """Busca sinais contextuais (rankings, premios, noticias) sobre uma
        escola via Perplexity e salva em conversation_memory como insights.

        Returns:
            dict com sinais_adicionados, preview, erros
        """
        try:
            company = db.get_company_detail(company_id)
        except Exception as e:
            return {"erro": f"Escola nao encontrada: {e}"}
        if not company:
            return {"erro": "Escola nao encontrada"}

        name = company.get("name") or ""
        city = company.get("city") or ""
        state = company.get("state") or ""

        logger.info("Enrich signals", extra={"company_id": company_id, "name": name})

        prompt = (
            f"Pesquise sobre a escola '{name}' em {city}/{state}. "
            f"Quero saber: rankings educacionais em que aparece, premios recebidos, "
            f"noticias importantes, expansoes ou reconhecimentos dos ultimos 3 anos "
            f"(2023-2026). Para cada item, informe o tipo (ranking, premio, noticia, "
            f"expansao, reconhecimento), titulo e ano. "
            f"Se nao encontrar nada relevante, diga que nao ha informacoes."
        )

        response_text = self._ask_perplexity(prompt, timeout=60)

        if not response_text or len(response_text.strip()) < 30:
            return {
                "company_id": company_id, "escola": name,
                "sinais_adicionados": 0, "preview": [],
                "erros": ["Perplexity nao retornou dados suficientes"],
            }

        # Parsear texto livre via LLM
        schema = (
            'Array JSON. Cada item: {"tipo": "ranking|premio|noticia|expansao|reconhecimento", '
            '"titulo": "string descrevendo o sinal", '
            '"ano": numero_ou_null, '
            '"fonte_url": "URL_ou_null"}. '
            'Se o texto nao contem sinais relevantes, retorne [].'
        )
        signals = self._text_to_json_via_llm(response_text, schema)

        if not signals:
            return {
                "company_id": company_id,
                "escola": name,
                "sinais_adicionados": 0,
                "preview": [],
                "erros": ["Perplexity nao retornou sinais ou resposta invalida"],
            }

        added = 0
        preview: List[str] = []
        erros: List[str] = []

        try:
            from integrations.memory import memory
        except Exception as e:
            return {"erro": f"Memory indisponivel: {e}"}

        emoji_map = {
            "ranking": "📊", "premio": "🏆", "noticia": "📰",
            "expansao": "📈", "reconhecimento": "⭐",
        }

        for sig in signals:
            if not isinstance(sig, dict):
                continue
            tipo = str(sig.get("tipo") or "noticia").lower().strip()
            titulo = str(sig.get("titulo") or "").strip()
            ano = sig.get("ano")
            fonte = sig.get("fonte_url") or ""
            if not titulo or len(titulo) < 5:
                continue

            emoji = emoji_map.get(tipo, "📌")
            content = f"{emoji} {tipo.title()}: {titulo}"
            if ano:
                content += f" ({ano})"
            if fonte:
                content += f" — fonte: {fonte}"
            content = content[:500]  # limite de memoria

            try:
                mem_id = memory.remember(
                    content=content,
                    scope="company",
                    scope_id=company_id,
                    category="insight",
                    importance=7 if tipo in ("premio", "ranking") else 6,
                    source="discovery_engine",
                )
                if mem_id:
                    added += 1
                    preview.append(content[:150])
            except Exception as e:
                erros.append(f"{titulo}: {str(e)[:80]}")

        logger.info("Enrich signals concluido", extra={
            "company_id": company_id, "added": added, "found": len(signals),
        })

        return {
            "company_id": company_id,
            "escola": name,
            "cidade": city,
            "sinais_encontrados": len(signals),
            "sinais_adicionados": added,
            "preview": preview,
            "erros": erros,
        }

    # =========================================================================
    # 3. Utilidades de staging
    # =========================================================================

    def list_discovered(
        self, limit: int = 50, cidade: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lista escolas em status='discovered' (staging)."""
        try:
            q = db.client.table("companies").select(
                "id,name,city,state,phone,website,admin_category,"
                "education_levels,source,notes,created_at,status"
            ).eq("status", "discovered").order("created_at", desc=True)
            if cidade:
                q = q.ilike("city", f"%{cidade}%")
            return q.limit(limit).execute().data or []
        except Exception as e:
            logger.error(f"list_discovered error: {e}")
            return []

    def promote_to_raw(self, company_id: str) -> bool:
        """Promove escola de status='discovered' para 'raw' (entra no pipeline)."""
        try:
            db.client.table("companies").update({"status": "raw"}).eq(
                "id", company_id
            ).eq("status", "discovered").execute()
            logger.info("Escola promovida discovered→raw", extra={"id": company_id})
            return True
        except Exception as e:
            logger.error(f"promote_to_raw error: {e}")
            return False

    def reject(self, company_id: str, reason: str = "") -> bool:
        """Marca escola descoberta como rejeitada (soft delete)."""
        try:
            update = {"status": "rejected"}
            if reason:
                update["notes"] = json.dumps({
                    "rejected_reason": reason,
                    "rejected_at": datetime.now(timezone.utc).isoformat(),
                }, ensure_ascii=False)
            db.client.table("companies").update(update).eq(
                "id", company_id
            ).execute()
            logger.info("Escola rejeitada", extra={"id": company_id, "reason": reason})
            return True
        except Exception as e:
            logger.error(f"reject error: {e}")
            return False


# Singleton
discovery_engine = DiscoveryEngine()
