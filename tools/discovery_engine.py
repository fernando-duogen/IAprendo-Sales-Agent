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
    # Web search + LLM parser (DuckDuckGo primary, Perplexity fallback)
    # =========================================================================

    def _search_web(self, query: str, max_results: int = 15) -> str:
        """Busca na web via DuckDuckGo HTML (gratuito, sem API key, sem browser).
        Retorna texto concatenado dos snippets dos resultados.
        Funciona em qualquer ambiente (local, Streamlit Cloud, servidor)."""
        import requests
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            try:
                from bs4 import BeautifulSoup
            except Exception:
                logger.error("BeautifulSoup nao disponivel para web search")
                return ""

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
            encoded_q = requests.utils.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_q}"
            resp = requests.get(url, headers=headers, timeout=20)

            if resp.status_code != 200:
                logger.warning(f"DuckDuckGo retornou {resp.status_code}")
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = []
            for result in soup.select(".result"):
                title_el = result.select_one(".result__title, .result__a")
                snippet_el = result.select_one(".result__snippet")
                title = title_el.get_text(strip=True) if title_el else ""
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                if title or snippet:
                    snippets.append(f"{title}\n{snippet}")
                if len(snippets) >= max_results:
                    break

            text = "\n\n".join(snippets)
            logger.info(f"DuckDuckGo: {len(snippets)} resultados para '{query[:50]}'")
            return text
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return ""

    def _ask_perplexity(self, prompt: str, timeout: int = 60) -> str:
        """Chama Perplexity Browser e retorna resposta em texto livre.
        Fallback — so usado se DuckDuckGo + GPT nao funcionarem."""
        try:
            from tools.perplexity_browser import perplexity_browser
            if not perplexity_browser.is_available():
                logger.warning("Perplexity Browser nao disponivel")
                return ""
            return perplexity_browser._query_perplexity_text(prompt, timeout_seconds=timeout)
        except Exception as e:
            logger.error(f"Perplexity error: {e}")
            return ""

    def _discover_via_llm(
        self,
        cidade: str,
        tipo: str,
        keyword: str,
        limit: int,
        web_context: str,
    ) -> List[Dict[str, Any]]:
        """Pede ao GPT para listar escolas com base no contexto de web search
        + seu proprio conhecimento. Pipeline: DuckDuckGo snippets → GPT."""
        import os
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OPENAI_API_KEY nao disponivel para discovery LLM")
            return []

        keyword_line = f" com diferencial: {keyword}" if keyword else ""
        tipo_txt = {"privada": "privadas", "publica": "publicas", "qualquer": ""}.get(tipo, "")

        system_msg = (
            "Voce e um especialista em escolas do Brasil. "
            "Com base nos resultados de busca web E no seu proprio conhecimento, "
            "liste escolas reais que existem na cidade indicada. "
            "Retorne APENAS um JSON array valido, sem texto antes ou depois. "
            "Se nao tiver certeza sobre um dado, coloque null."
        )
        user_msg = (
            f"Liste ate {limit} escolas {tipo_txt} em {cidade} que ofereçam "
            f"ensino Fundamental anos finais e/ou Ensino Medio{keyword_line}.\n\n"
            f"RESULTADOS DE BUSCA WEB (contexto):\n---\n{web_context[:6000]}\n---\n\n"
            f"Para cada escola, retorne JSON com: "
            f'"nome" (string), "endereco" (string ou null), "bairro" (string ou null), '
            f'"site" (URL ou null), "telefone" (string ou null), '
            f'"diferenciais" (array de strings), "tipo" ("privada" ou "publica").\n\n'
            f"Retorne APENAS o JSON array:"
        )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=3000,
                temperature=0.2,
            )
            result_text = resp.choices[0].message.content or ""
            logger.info("Discovery LLM: resposta recebida", extra={"len": len(result_text)})
            return self._extract_json_array(result_text)
        except Exception as e:
            logger.error(f"Discovery LLM error: {e}")
            return []

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
    # 1. Enriquecer escolas existentes com dados da web
    # =========================================================================

    def enriquecer_escolas_web(
        self,
        cidade: str,
        tipo: str = "privada",
        keyword: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Busca informacoes na web sobre escolas que JA EXISTEM no banco e
        enriquece com sinais (rankings, premios, diferenciais) + dados faltantes
        (site, telefone). NAO cria registros novos.

        Args:
            cidade: cidade alvo
            tipo: "privada", "publica" ou "qualquer"
            keyword: diferencial opcional ("bilingue", "integral")
            limit: max escolas a enriquecer

        Returns:
            dict com enriquecidas, sinais_adicionados, dados_atualizados, erros
        """
        limit = max(1, min(int(limit or 10), 30))
        tipo = (tipo or "privada").lower().strip()
        keyword = (keyword or "").strip()

        logger.info("Enriquecer escolas web: iniciando", extra={
            "cidade": cidade, "tipo": tipo, "keyword": keyword, "limit": limit,
        })

        # Busca na web: DuckDuckGo + GPT
        keyword_line = f" {keyword}" if keyword else ""
        tipo_txt = {"privada": "privadas", "publica": "publicas", "qualquer": ""}.get(tipo, "privadas")

        queries = [
            f"escolas {tipo_txt}{keyword_line} {cidade} ensino fundamental medio",
            f"colegios {tipo_txt}{keyword_line} {cidade} rankings premios",
        ]
        if keyword:
            queries.append(f"escolas {keyword} {cidade}")

        all_snippets = []
        for q in queries:
            snippets = self._search_web(q, max_results=10)
            if snippets:
                all_snippets.append(snippets)

        web_context = "\n\n---\n\n".join(all_snippets)

        if not web_context or len(web_context.strip()) < 30:
            return {
                "cidade": cidade, "tipo": tipo,
                "enriquecidas": [], "sinais_adicionados": 0,
                "dados_atualizados": [], "erros": ["Web search nao retornou dados"],
            }

        # GPT: extrai informacoes estruturadas
        schools = self._discover_via_llm(cidade, tipo, keyword, limit, web_context)

        if not schools:
            return {
                "cidade": cidade, "tipo": tipo,
                "enriquecidas": [], "sinais_adicionados": 0,
                "dados_atualizados": [], "erros": ["GPT nao retornou dados estruturados"],
            }

        enriquecidas: List[Dict[str, Any]] = []
        dados_atualizados: List[Dict[str, Any]] = []
        total_sinais = 0
        erros: List[str] = []

        from integrations.memory import memory

        for school in schools[:limit]:
            if not isinstance(school, dict):
                continue
            name = str(school.get("nome") or "").strip()
            if not name or len(name) < 3:
                continue

            try:
                # Buscar escola existente no banco por nome+cidade
                existing = self._dedup_by_name_city(name, cidade)
                if not existing:
                    continue  # Nao esta no banco — ignora (nao cria registro novo)

                company_id = existing["id"]
                company_name = existing.get("name", name)

                # 1. Atualizar dados faltantes (site, telefone)
                update_fields = {}
                site = (school.get("site") or "").strip()
                telefone = (school.get("telefone") or "").strip()

                if site and not existing.get("website"):
                    update_fields["website"] = site
                if telefone and not existing.get("phone"):
                    update_fields["phone"] = telefone

                if update_fields:
                    try:
                        db.client.table("companies").update(update_fields).eq(
                            "id", company_id
                        ).execute()
                        dados_atualizados.append({
                            "escola": company_name,
                            "campos": list(update_fields.keys()),
                        })
                    except Exception as e:
                        logger.debug(f"Erro ao atualizar dados: {e}")

                # 2. Salvar diferenciais como insights
                differentiators = school.get("diferenciais") or []
                if isinstance(differentiators, str):
                    differentiators = [differentiators]
                if differentiators:
                    try:
                        memory.remember(
                            content=f"Diferenciais: {', '.join(differentiators)}",
                            scope="company",
                            scope_id=company_id,
                            category="insight",
                            importance=6,
                            source="ialex",
                        )
                        total_sinais += 1
                    except Exception:
                        pass

                # 3. Buscar sinais (rankings/premios) para esta escola
                try:
                    sig_result = self.enrich_signals(company_id)
                    total_sinais += sig_result.get("sinais_adicionados", 0)
                except Exception:
                    pass

                enriquecidas.append({
                    "id": company_id,
                    "escola": company_name,
                    "dados_novos": list(update_fields.keys()) if update_fields else [],
                    "diferenciais": differentiators,
                })

            except Exception as e:
                erros.append(f"{name}: {str(e)[:100]}")

        result = {
            "cidade": cidade,
            "tipo": tipo,
            "keyword": keyword,
            "total_web": len(schools),
            "enriquecidas": enriquecidas,
            "sinais_adicionados": total_sinais,
            "dados_atualizados": dados_atualizados,
            "erros": erros,
        }
        logger.info("Enriquecimento web concluido", extra={
            "enriquecidas": len(enriquecidas),
            "sinais": total_sinais,
            "dados_atualizados": len(dados_atualizados),
        })
        return result

    # Manter compatibilidade — alias
    def discover_schools(self, *args, **kwargs):
        return self.enriquecer_escolas_web(*args, **kwargs)

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

        logger.info("Enrich signals", extra={"company_id": company_id, "school_name": name})

        # Schema usado nas 2 tentativas de extracao (DuckDuckGo + Perplexity)
        schema = (
            'Array JSON. Cada item: {"tipo": "ranking|premio|noticia|expansao|reconhecimento", '
            '"titulo": "string descrevendo o sinal", '
            '"ano": numero_ou_null, '
            '"fonte_url": "URL_ou_null"}. '
            'Se o texto nao contem sinais relevantes, retorne [].'
        )

        # === Tentativa 1: DuckDuckGo snippets + GPT ===
        # 5 queries diversificadas pra maximizar cobertura sem custo (DDG gratis).
        queries = [
            f'"{name}" {city} premio ranking educacao',
            f'"{name}" {city} noticias destaque',
            # Imprensa local RS — onde maioria dos premios/noticias de escolas saem
            f'"{name}" {city} site:gauchazh.clicrbs.com.br OR site:g1.globo.com',
            # ENEM eh forte sinal de qualidade no RS (escola que destaca em ENEM aparece)
            f'"{name}" {city} ENEM resultado destaque',
            # Estado (nao so cidade) — captura redes/franquias maiores
            f'"{name}" {state} reconhecimento educacao',
        ]
        all_snippets = []
        for q in queries:
            s = self._search_web(q, max_results=8)
            if s:
                all_snippets.append(s)
        ddg_context = "\n\n".join(all_snippets)

        signals = []
        fonte_usada = None
        if ddg_context and len(ddg_context.strip()) >= 20:
            signals = self._text_to_json_via_llm(ddg_context, schema) or []
            fonte_usada = "duckduckgo"
            logger.info("enrich_signals DuckDuckGo extraiu N sinais",
                        extra={"company_id": company_id, "count": len(signals)})

        # === Tentativa 2: Perplexity (fallback se DuckDuckGo falhou OU nao
        # extraiu sinais). Isso garante que leads sem informacao publica
        # recebam um esforco adicional via busca generativa. ===
        if not signals:
            try:
                from tools.perplexity_browser import perplexity_browser
                if perplexity_browser.is_available():
                    logger.info("enrich_signals fallback pra Perplexity",
                                extra={"company_id": company_id, "school": name})
                    prompt = (
                        f"Pesquise sobre a escola '{name}' em {city}/{state}. "
                        f"Quero saber: rankings educacionais, premios recebidos, noticias "
                        f"importantes, expansoes ou reconhecimentos (2023-2026). "
                        f"Liste ate 5 sinais concretos com ano e fonte se possivel."
                    )
                    plex_context = self._ask_perplexity(prompt, timeout=90)
                    if plex_context and len(plex_context.strip()) >= 20:
                        signals = self._text_to_json_via_llm(plex_context, schema) or []
                        fonte_usada = "perplexity"
                        logger.info("enrich_signals Perplexity extraiu N sinais",
                                    extra={"company_id": company_id, "count": len(signals)})
                else:
                    logger.warning("Perplexity nao disponivel — fallback pulado")
            except Exception as e:
                logger.warning(f"enrich_signals Perplexity falhou: {e}")

        if not signals:
            # Mensagem honesta — diz o que REALMENTE aconteceu
            if fonte_usada == "duckduckgo":
                erro_msg = "DuckDuckGo retornou contexto mas nenhum sinal estruturado (ranking/premio/noticia) foi extraido"
            elif fonte_usada == "perplexity":
                erro_msg = "Perplexity respondeu mas nenhum sinal estruturado foi extraido"
            elif ddg_context:
                erro_msg = "Contexto web insuficiente + Perplexity indisponivel"
            else:
                erro_msg = "Nenhuma fonte retornou dados (DuckDuckGo sem resultados, Perplexity indisponivel)"
            return {
                "company_id": company_id,
                "escola": name,
                "sinais_encontrados": 0,
                "sinais_adicionados": 0,
                "fonte_usada": fonte_usada,
                "preview": [],
                "erros": [erro_msg],
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
                    source="ialex",
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
            "fonte_usada": fonte_usada,
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
