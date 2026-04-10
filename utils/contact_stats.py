"""
Helpers para estatisticas de cobertura de contatos.

Funcoes puras (nao dependem de DB direto) para calcular taxas de
cobertura a partir de listas ja carregadas de escolas e contatos.
Usado pela pagina Contatos no dashboard.
"""
from typing import Any, Dict, List
from collections import defaultdict


# Emails "placeholder" ou genericos que nao contam como email valido
PLACEHOLDER_PATTERNS = [
    "placeholder", "example.com", "noreply", "no-reply",
    "naoresponder", "nao-responder", "donotreply", "do-not-reply",
    "test@", "teste@",
]


def _is_real_email(email: Any) -> bool:
    """Retorna True se o email parece real (nao placeholder)."""
    if not email:
        return False
    s = str(email).strip().lower()
    if not s or "@" not in s:
        return False
    for p in PLACEHOLDER_PATTERNS:
        if p in s:
            return False
    return True


def _is_real_phone(phone: Any) -> bool:
    """Retorna True se o telefone tem digitos suficientes (>= 8)."""
    if not phone:
        return False
    digits = "".join(c for c in str(phone) if c.isdigit())
    return len(digits) >= 8


def compute_contact_coverage(
    companies: List[Dict[str, Any]],
    contacts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calcula estatisticas de cobertura de contatos.

    Args:
        companies: lista de escolas (dicts com pelo menos 'id').
        contacts: lista de contatos (dicts com company_id, email,
                  phone, phone_whatsapp, decision_maker_type, source).

    Returns:
        Dict com contadores, percentuais, mapas e listas de ids.
    """
    n_total = len(companies)
    if n_total == 0:
        return {
            "total_escolas": 0,
            "com_email": 0, "pct_com_email": 0.0,
            "com_whatsapp": 0, "pct_com_whatsapp": 0.0,
            "com_diretor": 0, "pct_com_diretor": 0.0,
            "com_diretor_email": 0, "pct_com_diretor_email": 0.0,
            "com_coord": 0, "pct_com_coord": 0.0,
            "total_contatos": 0,
            "por_fonte": {},
            "escolas_sem_contato_ids": [],
            "escolas_sem_email_ids": [],
            "escolas_sem_whatsapp_ids": [],
        }

    # Agrupar contatos por company_id
    contatos_por_escola: Dict[str, List[Dict]] = defaultdict(list)
    por_fonte: Dict[str, int] = defaultdict(int)
    for c in contacts:
        cid = c.get("company_id")
        if cid:
            contatos_por_escola[cid].append(c)
        fonte = c.get("source") or "desconhecida"
        por_fonte[fonte] += 1

    # Contadores
    com_email = 0
    com_whatsapp = 0
    com_diretor = 0
    com_diretor_email = 0
    com_coord = 0

    escolas_sem_contato_ids: List[str] = []
    escolas_sem_email_ids: List[str] = []
    escolas_sem_whatsapp_ids: List[str] = []

    for comp in companies:
        cid = comp.get("id")
        cts = contatos_por_escola.get(cid, [])

        if not cts:
            escolas_sem_contato_ids.append(cid)
            escolas_sem_email_ids.append(cid)
            escolas_sem_whatsapp_ids.append(cid)
            continue

        # Tem pelo menos 1 email real?
        has_email = any(_is_real_email(c.get("email")) for c in cts)
        if has_email:
            com_email += 1
        else:
            escolas_sem_email_ids.append(cid)

        # Tem pelo menos 1 WhatsApp (phone_whatsapp ou phone)?
        has_wpp = any(
            _is_real_phone(c.get("phone_whatsapp")) or _is_real_phone(c.get("phone"))
            for c in cts
        )
        if has_wpp:
            com_whatsapp += 1
        else:
            escolas_sem_whatsapp_ids.append(cid)

        # Tem contato do tipo diretor?
        dirs = [c for c in cts if c.get("decision_maker_type") == "diretor"]
        if dirs:
            com_diretor += 1
            if any(_is_real_email(d.get("email")) for d in dirs):
                com_diretor_email += 1

        # Tem contato do tipo coordenador pedagogico?
        if any(c.get("decision_maker_type") == "coordenador_pedagogico" for c in cts):
            com_coord += 1

    def pct(n: int) -> float:
        return round((100.0 * n / n_total), 1) if n_total else 0.0

    return {
        "total_escolas": n_total,
        "total_contatos": len(contacts),
        "com_email": com_email,
        "pct_com_email": pct(com_email),
        "com_whatsapp": com_whatsapp,
        "pct_com_whatsapp": pct(com_whatsapp),
        "com_diretor": com_diretor,
        "pct_com_diretor": pct(com_diretor),
        "com_diretor_email": com_diretor_email,
        "pct_com_diretor_email": pct(com_diretor_email),
        "com_coord": com_coord,
        "pct_com_coord": pct(com_coord),
        "por_fonte": dict(por_fonte),
        "escolas_sem_contato_ids": escolas_sem_contato_ids,
        "escolas_sem_email_ids": escolas_sem_email_ids,
        "escolas_sem_whatsapp_ids": escolas_sem_whatsapp_ids,
    }


def rank_sem_contato_por_fit(
    companies: List[Dict[str, Any]],
    sem_ids: List[str],
    fit_calculator,
    limite: int = 10,
) -> List[Dict[str, Any]]:
    """Ranqueia escolas sem contato (ou sem email/wpp) pelo Fit IAprendo.

    Args:
        companies: lista completa de escolas do banco.
        sem_ids: ids das escolas que nao tem o que queremos (contato/email/wpp).
        fit_calculator: funcao (company_dict) -> dict com 'score' e 'level'.
        limite: top N a retornar.

    Returns:
        Lista de dicts: {id, name, city, state, alvo, fit, fit_level}
    """
    sem_set = set(sem_ids)
    alvos: List[Dict[str, Any]] = []
    for c in companies:
        if c.get("id") not in sem_set:
            continue
        fit = fit_calculator(c)
        fit_score = fit.get("score") or 0
        fit_level = fit.get("level") or "sem_dados"
        alvo_alunos = int((c.get("matriculas_fund_af") or 0) + (c.get("matriculas_medio") or 0))
        alvos.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "city": c.get("city"),
            "state": c.get("state"),
            "alvo": alvo_alunos,
            "fit": fit_score,
            "fit_level": fit_level,
            "qualification_score": c.get("qualification_score") or 0,
        })

    # Ordenar por fit desc, desempate por alvo
    alvos.sort(key=lambda x: (x["fit"], x["alvo"]), reverse=True)
    return alvos[:limite]
