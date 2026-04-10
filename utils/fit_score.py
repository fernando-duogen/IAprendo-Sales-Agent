"""
Score Fit IAprendo — avaliacao deterministica do encaixe de uma escola
com o produto IAprendo, baseada nos dados do Censo 2025.

Diferenca do qualification_score (que vem do qualifier IA, 0-100):
- Fit score e DETERMINISTICO (mesma escola sempre da o mesmo numero)
- Calculado em tempo real a partir dos campos do banco
- Foca no "encaixe com o produto" (quao bem IAprendo serve esta escola)
- qualification_score foca em "quao qualificado como lead" (IA decide)

Use juntos:
- Score alto + Fit alto = prioridade maxima
- Score alto + Fit baixo = escola qualificada mas produto nao encaixa bem
- Score baixo + Fit alto = escola que pode ter sido subqualificada
- Score baixo + Fit baixo = despriorizar

Formula:
    base = alvo / 20   (ex: 500 alunos alvo = 25 pontos base)
    fit  = base * tech_mult * coord_mult * categoria_mult

Onde:
    tech_mult:
        Alto   = 1.8
        Medio  = 1.2
        Baixo  = 0.6
        outros = 0.9

    coord_mult:
        tem coordenador (>=1) = 1.3
        sem coordenador       = 1.0

    categoria_mult:
        Privada Particular    = 1.2
        Privada Comunitaria   = 1.15
        Privada Confessional  = 1.15
        Privada Filantropica  = 1.1
        Publica (qualquer)    = 1.0
        Sem dado              = 0.9

Resultado sempre cappeado entre 0 e 100.
"""
from typing import Dict, Any


TECH_MULT = {
    "Alto": 1.8,
    "Medio": 1.2,
    "Médio": 1.2,
    "Baixo": 0.6,
}

CATEGORIA_MULT = {
    "Particular": 1.2,
    "Comunitaria": 1.15,
    "Comunitária": 1.15,
    "Confessional": 1.15,
    "Filantropica": 1.1,
    "Filantrópica": 1.1,
}


def calcular_fit_score(company: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula o Fit Score IAprendo para uma escola.

    Args:
        company: Dict com campos do banco (precisa ter pelo menos
                 matriculas_fund_af, matriculas_medio, nivel_tecnologico,
                 qt_coordenadores, categoria_privada).

    Returns:
        Dict com:
            score: int 0-100
            level: str "alto" | "medio" | "baixo" | "sem_dados"
            motivo: str explicacao curta
            componentes: dict com os multiplicadores usados (debug)
    """
    # Alunos alvo
    fund_af = company.get("matriculas_fund_af") or 0
    medio = company.get("matriculas_medio") or 0
    alvo = int(fund_af) + int(medio)

    # Se fonte_dados = catalogo_inep, nao temos os dados — retorna 'sem_dados'
    fonte = company.get("fonte_dados") or ""
    if fonte == "catalogo_inep" or alvo == 0:
        return {
            "score": None,
            "level": "sem_dados",
            "motivo": "Sem dados do Censo 2025 para calcular fit (escola do Catalogo INEP ou sem matriculas)",
            "componentes": {},
        }

    # Base: cada 20 alunos alvo = 1 ponto (500 alunos = 25 pontos)
    base = alvo / 20.0

    # Multiplicador de nivel tecnologico
    nivel_tech = company.get("nivel_tecnologico") or "Sem dado"
    tech_mult = TECH_MULT.get(nivel_tech, 0.9)

    # Multiplicador de coordenador pedagogico
    qt_coord = company.get("qt_coordenadores") or 0
    coord_mult = 1.3 if int(qt_coord) > 0 else 1.0

    # Multiplicador de categoria privada
    categoria = company.get("categoria_privada") or ""
    # Match ignorando acentos / parcial
    categoria_mult = 1.0
    for key, mult in CATEGORIA_MULT.items():
        if key.lower() in categoria.lower():
            categoria_mult = mult
            break
    if not categoria and company.get("admin_dependency", "").lower() == "privada":
        categoria_mult = 1.1  # Privada sem categoria especifica

    # Calcular
    score = base * tech_mult * coord_mult * categoria_mult
    score = min(100, max(0, int(round(score))))

    # Classificar
    if score >= 70:
        level = "alto"
    elif score >= 40:
        level = "medio"
    else:
        level = "baixo"

    # Motivo (explicacao curta)
    razoes = []
    razoes.append(f"{alvo} alunos alvo")
    if nivel_tech != "Sem dado":
        razoes.append(f"tech {nivel_tech}")
    if int(qt_coord) > 0:
        razoes.append(f"com coordenador")
    if categoria:
        razoes.append(categoria.lower())
    motivo = ", ".join(razoes)

    return {
        "score": score,
        "level": level,
        "motivo": motivo,
        "componentes": {
            "alvo": alvo,
            "base": round(base, 1),
            "tech_mult": tech_mult,
            "coord_mult": coord_mult,
            "categoria_mult": categoria_mult,
        },
    }


def fit_emoji(level: str) -> str:
    """Retorna emoji correspondente ao level do fit."""
    return {
        "alto": "🟢",
        "medio": "🟡",
        "baixo": "🔴",
        "sem_dados": "⚪",
    }.get(level, "⚪")


def fit_cor_hex(level: str) -> str:
    """Retorna cor HEX do level (uso em badges/charts)."""
    return {
        "alto": "#2e7d32",
        "medio": "#f57c00",
        "baixo": "#c62828",
        "sem_dados": "#9e9e9e",
    }.get(level, "#9e9e9e")
