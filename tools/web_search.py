# -*- coding: utf-8 -*-
"""Busca web SERVER-SIDE via OpenAI (Responses API + ferramenta `web_search`).

Substitui o `tools/perplexity_browser.py` (automacao de Chrome + assinatura Pro),
que foi aposentado em Ago/2026 porque:
  - exigia Windows + Chrome VISIVEL (headless=False) -> IMPOSSIVEL na VM Oracle;
  - custava a mensalidade do Perplexity Pro (~US$20/mes) p/ 4 usos em 4 meses;
  - levava 45-75s por consulta.

Aqui: ~4s por consulta, ~US$0.004 (R$ 0,02) por escola, MESMA chave OpenAI que o
resto do projeto ja usa, e roda em qualquer lugar (e API, nao navegador).

Contrato COMPATIVEL com o modulo antigo (drop-in):
    is_available() -> bool
    search_text(prompt, timeout_seconds) -> str          (era _query_perplexity_text)
    search_school_contacts(name, city, state) -> List[Dict]
    search_school_address(name, city, state) -> Optional[str]

Tudo defensivo: NUNCA levanta excecao — degrada pra "" / [] / None.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from utils.logger import logger

# gpt-4.1-mini: mesmo modelo do IAlex. NAO usar *-search-preview (deprecado
# pela OpenAI, shutdown anunciado p/ 2026).
_DEFAULT_MODEL = "gpt-4.1-mini"
# Precos gpt-4.1-mini (US$/token) — usados so p/ registrar custo em api_usage.
_PRICE_IN = 0.40 / 1_000_000
_PRICE_OUT = 1.60 / 1_000_000


def _model() -> str:
    m = os.getenv("WEBSEARCH_MODEL", "").strip()
    # Blinda contra o modelo antigo deprecado ficar no .env de alguem
    if not m or "search-preview" in m:
        return _DEFAULT_MODEL
    return m


def is_available() -> bool:
    """True se da pra fazer busca web (chave OpenAI presente e SDK instalado)."""
    try:
        if not os.getenv("OPENAI_API_KEY", "").strip():
            return False
        import openai  # noqa: F401
        return True
    except Exception:
        return False


def _log_usage(endpoint: str, usage: Any) -> None:
    """Registra a chamada em api_usage (best-effort, nunca quebra o fluxo)."""
    try:
        tin = getattr(usage, "input_tokens", 0) or 0
        tout = getattr(usage, "output_tokens", 0) or 0
        cost = tin * _PRICE_IN + tout * _PRICE_OUT
        from database.supabase_client import db
        db.insert_api_usage({
            "api_name": "openai",          # constraint valid_api_name
            "endpoint": endpoint,
            "credits_used": 1,
            "cost_usd": round(cost, 6),
        })
    except Exception:
        pass


def _call(prompt: str, endpoint: str, timeout_seconds: int = 60) -> str:
    """Chamada crua a Responses API com a ferramenta web_search."""
    if not is_available():
        logger.warning("web_search indisponivel (sem OPENAI_API_KEY)")
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=timeout_seconds)
        resp = client.responses.create(
            model=_model(),
            tools=[{"type": "web_search"}],
            input=prompt,
        )
        _log_usage(endpoint, getattr(resp, "usage", None))
        return resp.output_text or ""
    except Exception as e:
        logger.warning(f"web_search falhou ({endpoint}): {str(e)[:200]}")
        return ""


def search_text(prompt: str, timeout_seconds: int = 60) -> str:
    """Busca livre na web. Mesmo contrato do antigo _query_perplexity_text."""
    return _call(prompt, endpoint="web-search", timeout_seconds=timeout_seconds)


# ---------------------------------------------------------------------------
# JSON helpers — pedimos JSON direto ao modelo (mais robusto que regex sobre
# texto livre, que era o que o parser de 400 linhas do Perplexity fazia).
# ---------------------------------------------------------------------------
def _extract_json_array(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []
    raw = text.strip()
    # Remove cercas markdown ```json ... ```
    fence = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    if not raw.startswith("["):
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            return []
        raw = raw[start:end + 1]
    try:
        data = json.loads(raw)
        return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []
    except Exception:
        return []


_EMAIL_RE = re.compile(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+")
# O modelo as vezes escreve a AUSENCIA de dado como TEXTO ("null", "N/A",
# "nao encontrado") em vez de JSON null. Sem isso, campos vazios passariam
# como se fossem valor real.
_VAZIOS = {
    "", "null", "none", "n/a", "na", "-", "--", "nao encontrado",
    "não encontrado", "nao informado", "não informado", "desconhecido",
    "not found", "unknown",
}


def _limpo(valor: Any) -> str:
    """Normaliza um campo do JSON: trata 'null'/'N/A'/etc como vazio."""
    s = str(valor or "").strip().strip("*").strip()
    return "" if s.lower() in _VAZIOS else s


def search_school_contacts(
    name: str, city: str, state: str, timeout_seconds: int = 60
) -> List[Dict[str, Any]]:
    """Busca contatos/decisores de uma escola na web.

    Retorna lista no formato do cascade do ContactFinder (full_name, role,
    email, phone, source, confidence_score). Lista vazia se nao achar nada.

    NOTA HONESTA: nomes de diretores raramente estao publicados na web. O ganho
    real aqui costuma ser email/telefone INSTITUCIONAL (secretaria@, contato@),
    que ja e util pra primeira abordagem. Apollo/Hunter/Snov e a raspagem do
    site continuam sendo as fontes fortes p/ pessoas nominais.
    """
    prompt = (
        f"Pesquise na web os contatos da escola '{name}' em {city}/{state}, Brasil.\n"
        f"Procure: diretor(a), vice-diretor(a), coordenador(a) pedagogico(a), "
        f"secretaria, e os emails/telefones institucionais do site oficial.\n\n"
        f"Responda APENAS com um array JSON valido (sem texto ao redor, sem "
        f"markdown), no formato:\n"
        f'[{{"full_name": "Nome completo ou null", "role": "Cargo", '
        f'"email": "email ou null", "phone": "telefone ou null", '
        f'"confianca": 0-100}}]\n\n'
        f"REGRAS:\n"
        f"- So inclua dados que voce REALMENTE encontrou em fontes; NAO invente "
        f"nomes nem emails.\n"
        f"- Email institucional sem pessoa: use full_name=null e role='Secretaria' "
        f"(ou o setor correspondente).\n"
        f"- confianca: 80+ se veio do site oficial, 50-70 se de terceiros.\n"
        f"- Se nao encontrar nada, responda []."
    )
    txt = _call(prompt, endpoint="web-search-contacts", timeout_seconds=timeout_seconds)
    items = _extract_json_array(txt)

    out: List[Dict[str, Any]] = []
    for it in items[:10]:
        email = _limpo(it.get("email"))
        # Descarta emails ofuscados/invalidos (ex.: "[email protected]", que
        # alguns sites usam como anti-scraping)
        if email and not _EMAIL_RE.fullmatch(email):
            email = ""
        full_name = _limpo(it.get("full_name"))
        role = _limpo(it.get("role"))
        phone = _limpo(it.get("phone"))
        # Util = tem contato OU ao menos um NOME de pessoa identificado
        # (o nome sozinho ja permite deduzir email pelo padrao do dominio).
        if not email and not phone and not full_name:
            continue
        try:
            conf = int(it.get("confianca") or 0)
        except (TypeError, ValueError):
            conf = 0
        out.append({
            "full_name": full_name or "Responsavel",
            "role": role or "Responsavel",
            "email": email or None,
            "phone": phone or None,
            "source": "web_search",
            "confidence_score": max(0, min(conf, 100)) or 50,
        })

    logger.info("web_search contatos", extra={
        "school": name, "city": city, "encontrados": len(out),
    })
    return out


def search_school_address(
    name: str, city: str, state: str, timeout_seconds: int = 45
) -> Optional[str]:
    """Busca o endereco completo de uma escola (fallback de geocodificacao)."""
    prompt = (
        f"Qual o endereco completo da escola '{name}' em {city}/{state}, Brasil? "
        f"Responda APENAS com o endereco em TEXTO PURO, numa unica linha, no "
        f"formato: Rua/Av, numero, bairro, cidade, estado, CEP. "
        f"NAO use markdown, NAO use links, NAO escreva mais nada. "
        f"Se nao encontrar com seguranca, responda exatamente: NAO ENCONTRADO"
    )
    txt = _call(prompt, endpoint="web-search-address", timeout_seconds=timeout_seconds)
    if not txt:
        return None
    if "NAO ENCONTRADO" in txt.upper() or "NÃO ENCONTRADO" in txt.upper():
        return None

    def _parece_endereco(s: str) -> bool:
        return len(s) >= 15 and any(c.isdigit() for c in s) and "," in s

    # 1) Texto normal (removendo markdown de link: [texto](url) -> texto)
    limpo = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", txt)
    for line in limpo.split("\n"):
        line = line.strip().strip("*#").strip()
        if _parece_endereco(line):
            return line

    # 2) Recuperacao: a ferramenta as vezes devolve so um cartao com link do
    #    Google Maps, e o endereco fica CODIFICADO na URL (maps/search/<addr>).
    m = re.search(r"maps/search/([^?)\s]+)", txt)
    if m:
        try:
            from urllib.parse import unquote_plus
            cand = unquote_plus(m.group(1)).strip()
            if _parece_endereco(cand):
                return cand
        except Exception:
            pass
    return None
