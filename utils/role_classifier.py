"""
role_classifier - Classifica texto livre de cargo em tipo estruturado de decisor.

Usado pelo ContactFinder para classificar contatos encontrados via APIs
e pelo dashboard para exibir o Mapa de Poder por escola.

Funcao pura, sem dependencias externas, testavel isoladamente.
"""
import re
from typing import Tuple


# Ordem de prioridade para abordagem comercial:
# 1 = Diretor (decisor final)
# 2 = Vice-Diretor (influenciador)
# 3 = Coordenador Pedagogico (champion tecnico)
# 4 = Secretaria (gatekeeper)
# 5 = Administrativo (suporte)
# 99 = Outro/desconhecido

# Patterns de regex: (compiled_regex, decision_maker_type, outreach_priority)
# Ordem importa: vice_diretor ANTES de diretor (para nao capturar vice como diretor)
_ROLE_PATTERNS: list[Tuple[re.Pattern, str, int]] = [
    # Assessor(a) — testar ANTES de diretor (para "Assessora de Direcao")
    (re.compile(r"assessor", re.IGNORECASE), "administrativo", 5),

    # Vice-Diretor(a) — testar ANTES de diretor
    (re.compile(r"vice.?dir", re.IGNORECASE), "vice_diretor", 2),
    (re.compile(r"sub.?dir", re.IGNORECASE), "vice_diretor", 2),
    (re.compile(r"deputy", re.IGNORECASE), "vice_diretor", 2),

    # Diretor(a) — depois de vice para evitar falso positivo
    (re.compile(r"diretor", re.IGNORECASE), "diretor", 1),
    (re.compile(r"diretora", re.IGNORECASE), "diretor", 1),
    (re.compile(r"principal", re.IGNORECASE), "diretor", 1),
    (re.compile(r"head.?of.?school", re.IGNORECASE), "diretor", 1),
    (re.compile(r"dire[cç][aã]o", re.IGNORECASE), "diretor", 1),

    # Coordenador(a) Pedagogico(a) / de Ensino / SOE / Orientacao
    (re.compile(r"coord.*pedag", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"coord.*ensino", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"pedagogic", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"orient.*educa", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"\bSOE\b", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"supervis.*pedag", re.IGNORECASE), "coordenador_pedagogico", 3),
    (re.compile(r"supervis.*ensino", re.IGNORECASE), "coordenador_pedagogico", 3),

    # Secretaria / Tesouraria
    (re.compile(r"secret[aá]ri", re.IGNORECASE), "secretaria", 4),
    (re.compile(r"secretary", re.IGNORECASE), "secretaria", 4),
    (re.compile(r"tesour", re.IGNORECASE), "secretaria", 4),

    # Administrativo
    (re.compile(r"administra", re.IGNORECASE), "administrativo", 5),
    (re.compile(r"gerente", re.IGNORECASE), "administrativo", 5),
    (re.compile(r"gestor", re.IGNORECASE), "administrativo", 5),
    (re.compile(r"manager", re.IGNORECASE), "administrativo", 5),
]

# Labels amigaveis para exibicao no dashboard
ROLE_LABELS: dict[str, str] = {
    "diretor": "Diretor(a)",
    "vice_diretor": "Vice-Diretor(a)",
    "coordenador_pedagogico": "Coord. Pedagogico(a)",
    "secretaria": "Secretaria",
    "administrativo": "Administrativo",
    "outro": "Outro",
}

# Papeis-chave para o Mapa de Poder (exibidos sempre, mesmo sem contato)
POWER_MAP_ROLES: list[str] = [
    "diretor",
    "vice_diretor",
    "coordenador_pedagogico",
]

# Todos os tipos validos (para dropdown no dashboard)
ALL_ROLE_TYPES: list[str] = [
    "diretor",
    "vice_diretor",
    "coordenador_pedagogico",
    "secretaria",
    "administrativo",
    "outro",
]


def classify_role(role_text: str) -> Tuple[str, int]:
    """Classifica texto livre de cargo em tipo estruturado.

    Args:
        role_text: Texto do cargo (ex: 'Diretora', 'Coord. Pedagogico',
                   'Vice-Diretor Geral', 'Responsavel').

    Returns:
        Tupla (decision_maker_type, outreach_priority).
        Ex: ('diretor', 1), ('coordenador_pedagogico', 3), ('outro', 99).
    """
    if not role_text or not isinstance(role_text, str):
        return ("outro", 99)

    text = role_text.strip()
    if not text:
        return ("outro", 99)

    for pattern, dm_type, priority in _ROLE_PATTERNS:
        if pattern.search(text):
            return (dm_type, priority)

    return ("outro", 99)


def classify_email_prefix(email: str) -> Tuple[str, int]:
    """Classifica contato pelo prefixo do email generico.

    Util para emails como direcao@escola.com.br, coordenacao@escola.com.br.

    Args:
        email: Endereco de email.

    Returns:
        Tupla (decision_maker_type, outreach_priority).
    """
    if not email or "@" not in email:
        return ("outro", 99)

    prefix = email.split("@")[0].lower().strip()

    prefix_map = {
        "direcao": ("diretor", 1),
        "diretor": ("diretor", 1),
        "diretora": ("diretor", 1),
        "coordenacao": ("coordenador_pedagogico", 3),
        "coordenador": ("coordenador_pedagogico", 3),
        "coordenadora": ("coordenador_pedagogico", 3),
        "pedagogico": ("coordenador_pedagogico", 3),
        "secretaria": ("secretaria", 4),
        "contato": ("outro", 99),
        "escola": ("outro", 99),
        "info": ("outro", 99),
    }

    return prefix_map.get(prefix, ("outro", 99))


def get_role_label(decision_maker_type: str) -> str:
    """Retorna label amigavel para exibicao no dashboard.

    Args:
        decision_maker_type: Tipo estruturado (ex: 'diretor').

    Returns:
        Label em portugues (ex: 'Diretor(a)').
    """
    return ROLE_LABELS.get(decision_maker_type, "Outro")
