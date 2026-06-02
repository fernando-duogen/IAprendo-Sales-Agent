"""template_selector - Seleção automática de template de email por "alvo".

Escolhe o melhor template dentre os ativos com base em 2 dimensoes:
  1. AUDIENCE (publico): pessoa nominal vs endereco generico (secretaria@)
  2. DATA_PROFILE (dados disponiveis): matriculas (Censo), ENEM, ambos, nenhum

Cada template em message_templates pode declarar:
  - audience_type: 'nominal' | 'generico' | NULL (qualquer)
  - data_profile:  'ambos' | 'matriculas' | 'enem' | 'nenhum' | NULL (qualquer)

NULL = wildcard (serve pra qualquer alvo) → retrocompatibilidade total:
templates antigos sem esses campos continuam selecionaveis.

Regra de ouro: NUNCA escolher um template que EXIJA um dado que a escola
nao tem (senao o email referencia ENEM/matriculas inexistentes). E nunca
mandar template 'nominal' (saudacao pessoal) pra endereco generico.

Usage:
    from utils.template_selector import selecionar_template
    tpl = selecionar_template(company, contact, templates_ativos)
    if tpl:
        template_id = tpl["id"]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.logger import logger

# Local-parts de email que indicam caixa GENERICA (nao pessoa fisica)
_GENERIC_LOCALPARTS = {
    "secretaria", "secretariat", "contato", "contact", "info", "atendimento",
    "falecom", "fale", "administracao", "administrativo", "adm", "escola",
    "diretoria", "sec", "coordenacao", "pedagogico", "comercial", "matriculas",
    "recepcao", "faleconosco", "sac", "ouvidoria",
}

# Cache de presenca de ENEM por inep (evita N queries no batch)
_enem_cache: Dict[str, bool] = {}


def detectar_audience(contact: Optional[Dict[str, Any]]) -> str:
    """Classifica o contato como 'nominal' (pessoa real) ou 'generico' (caixa institucional).

    Regras (qualquer uma -> generico):
      - sem contato
      - source in (placeholder, email_pattern) — nao e pessoa real
      - full_name vazio
      - local-part do email em conjunto generico (secretaria@, contato@, etc)
      - decision_maker_type == 'administrativo' sem nome proprio claro
    """
    if not contact:
        return "generico"

    source = (contact.get("source") or "").strip().lower()
    if source in ("placeholder", "email_pattern"):
        return "generico"

    full_name = (contact.get("full_name") or "").strip()
    if not full_name:
        return "generico"

    # Nome generico explicito (ex: "Secretaria", "Diretor(a)")
    _name_lower = full_name.lower()
    if _name_lower in ("secretaria", "diretor(a)", "diretoria", "coordenacao", "equipe"):
        return "generico"

    email = (contact.get("email") or "").strip().lower()
    if email and "@" in email:
        localpart = email.split("@", 1)[0]
        # Remove sufixos numericos/pontuacao pra comparar (secretaria2 -> secretaria)
        localpart_clean = "".join(c for c in localpart if c.isalpha())
        if localpart_clean in _GENERIC_LOCALPARTS:
            return "generico"

    return "nominal"


def detectar_dados(company: Dict[str, Any]) -> Dict[str, bool]:
    """Detecta quais dados ricos a escola possui.

    Returns:
        {"matriculas": bool, "enem": bool}
    """
    # Matriculas: Censo 2025
    tem_matriculas = bool(
        (company.get("total_matriculas") or 0) > 0
        or (company.get("matriculas_fund_af") or 0) > 0
        or (company.get("matriculas_medio") or 0) > 0
    )

    # ENEM: tabela school_enem_yearly por inep_code (cacheado)
    tem_enem = _tem_enem(company.get("inep_code"))

    return {"matriculas": tem_matriculas, "enem": tem_enem}


def _tem_enem(inep_code: Optional[str]) -> bool:
    """Verifica se a escola tem dados ENEM (school_enem_yearly). Cacheado por inep."""
    if not inep_code:
        return False
    key = str(inep_code).strip()
    if key in _enem_cache:
        return _enem_cache[key]
    try:
        from database.supabase_client import db
        r = (
            db.client.table("school_enem_yearly")
            .select("enem_media_geral")
            .eq("inep_code", key)
            .not_.is_("enem_media_geral", "null")
            .limit(1)
            .execute()
        )
        has = bool(r.data)
    except Exception as e:
        logger.debug(f"_tem_enem falhou pra {key}: {e}")
        has = False
    _enem_cache[key] = has
    return has


def _data_requirement_met(data_profile: Optional[str], tem_matriculas: bool, tem_enem: bool) -> bool:
    """True se a escola tem TODOS os dados que o template exige."""
    if not data_profile or data_profile == "nenhum":
        return True  # template nao exige nada
    if data_profile == "ambos":
        return tem_matriculas and tem_enem
    if data_profile == "matriculas":
        return tem_matriculas
    if data_profile == "enem":
        return tem_enem
    return True  # valor desconhecido -> trata como wildcard (nao bloqueia)


def _data_richness(data_profile: Optional[str]) -> int:
    """Rank de riqueza do template (prefere o mais rico que a escola suporta)."""
    return {"ambos": 3, "matriculas": 2, "enem": 2, "nenhum": 0}.get(data_profile or "", 0)


def selecionar_template(
    company: Dict[str, Any],
    contact: Optional[Dict[str, Any]],
    templates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Seleciona o melhor template ativo pro alvo (company + contact).

    Args:
        company: dict da escola (com inep_code, total_matriculas, etc)
        contact: dict do contato selecionado (pode ser None/placeholder)
        templates: lista de templates ATIVOS (dicts de message_templates)

    Returns:
        O template escolhido, ou None se nenhum elegivel (caller usa fallback).
    """
    if not templates:
        return None

    audience = detectar_audience(contact)
    dados = detectar_dados(company)
    tem_mat, tem_enem = dados["matriculas"], dados["enem"]

    candidatos = []
    for tpl in templates:
        if not tpl.get("is_active", True):
            continue
        t_aud = (tpl.get("audience_type") or "").strip().lower() or None
        t_data = (tpl.get("data_profile") or "").strip().lower() or None

        # 1. Excluir se exige dado que a escola nao tem
        if not _data_requirement_met(t_data, tem_mat, tem_enem):
            continue
        # 2. Excluir se audience conflita (nominal<->generico). NULL nunca conflita.
        if t_aud and t_aud != audience:
            continue

        # 3. Score
        score = _data_richness(t_data)              # riqueza de dados (0-3)
        score += 2 if t_aud == audience else (1 if t_aud is None else 0)  # match de audience
        if tpl.get("is_default"):
            score += 0.5                            # desempate suave
        candidatos.append((score, tpl))

    if not candidatos:
        logger.info(
            "selecionar_template: nenhum elegivel",
            extra={"audience": audience, "tem_matriculas": tem_mat, "tem_enem": tem_enem,
                   "escola": company.get("name")},
        )
        return None

    candidatos.sort(key=lambda x: x[0], reverse=True)
    escolhido = candidatos[0][1]
    logger.info(
        "selecionar_template: escolhido",
        extra={"template": escolhido.get("name"), "audience": audience,
               "tem_matriculas": tem_mat, "tem_enem": tem_enem,
               "escola": company.get("name")},
    )
    return escolhido


def matriz_cobertura(templates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Retorna a matriz 2x4 (audience x data) indicando quais combos tem template ativo.

    Usado pelo dashboard pra mostrar grid de cobertura.

    Returns:
        Lista de dicts: {audience, data_profile, label, coberto: bool, templates: [nomes]}
    """
    combos = [
        ("nominal", "ambos", "⭐ Nominal · Matrículas+ENEM"),
        ("nominal", "matriculas", "Nominal · Matrículas"),
        ("nominal", "enem", "Nominal · ENEM"),
        ("nominal", "nenhum", "Nominal · Sem dados"),
        ("generico", "ambos", "Genérico · Matrículas+ENEM"),
        ("generico", "matriculas", "Genérico · Matrículas"),
        ("generico", "enem", "Genérico · ENEM"),
        ("generico", "nenhum", "Genérico · Sem dados"),
    ]
    ativos = [t for t in templates if t.get("is_active", True)]
    resultado = []
    for aud, data, label in combos:
        # Coberto se existe template ativo com EXATAMENTE esse audience+data,
        # OU um wildcard que cobre (audience NULL/match + data NULL/match)
        matched = [
            t.get("name", "?")
            for t in ativos
            if ((t.get("audience_type") or "").lower() in (aud, ""))
            and ((t.get("data_profile") or "").lower() in (data, ""))
        ]
        resultado.append({
            "audience": aud,
            "data_profile": data,
            "label": label,
            "coberto": bool(matched),
            "templates": matched,
        })
    return resultado
