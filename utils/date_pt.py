"""
date_pt - Formatacao de datas em portugues brasileiro.

Wrapper sobre datetime.strftime que traduz os tokens dependentes de locale
(%A, %a, %B, %b) para pt_BR, deixando os demais (%d, %m, %Y, %H, %M, etc.)
para o strftime padrao processar.

Motivacao: Python strftime usa o locale do sistema. No Windows em ingles,
`%A` vira "Tuesday" e `%a` vira "Tue". Em vez de depender de locale.setlocale
(que exige pt_BR instalado no SO e tem efeito global), substituimos apenas os
tokens de nome de dia/mes antes de chamar strftime.

Usage:
    from utils.date_pt import format_pt

    format_pt(datetime.now(), "%a, %d/%m")        # -> "Ter, 21/04"
    format_pt(datetime.now(), "%A, %d de %B")     # -> "Terca, 21 de abril"
    format_pt(datetime.now(), "%d/%m/%Y %H:%M")   # -> "21/04/2026 14:30" (sem locale)
"""
from datetime import datetime
from typing import Union

# Nomes de dias (0 = segunda, seguindo datetime.weekday())
DIAS_SEMANA_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
DIAS_SEMANA_FULL = [
    "Segunda",
    "Terca",
    "Quarta",
    "Quinta",
    "Sexta",
    "Sabado",
    "Domingo",
]

# Nomes de meses (1 = janeiro, seguindo datetime.month)
MESES_ABREV = [
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
]
MESES_FULL = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def format_pt(dt: Union[datetime, None], fmt: str) -> str:
    """Formata um datetime em portugues brasileiro.

    Substitui os tokens dependentes de locale (%A, %a, %B, %b) pelos nomes
    equivalentes em pt_BR antes de delegar ao strftime padrao.

    Args:
        dt: objeto datetime. Se None, retorna string vazia.
        fmt: string de formato (mesmos codigos que strftime).

    Returns:
        Data formatada com nomes de dia/mes em portugues.
    """
    if dt is None:
        return ""

    weekday = dt.weekday()  # 0=Seg, 6=Dom
    month_idx = dt.month - 1  # 0-based para indexar MESES_*

    # Ordem importa: %A antes de %a, %B antes de %b (prefix match no replace)
    fmt_pt = (
        fmt.replace("%A", DIAS_SEMANA_FULL[weekday])
        .replace("%a", DIAS_SEMANA_ABREV[weekday])
        .replace("%B", MESES_FULL[month_idx])
        .replace("%b", MESES_ABREV[month_idx])
    )
    return dt.strftime(fmt_pt)


def dia_semana_pt(dt: datetime, abbreviated: bool = False) -> str:
    """Atalho: retorna apenas o nome do dia da semana em pt_BR."""
    source = DIAS_SEMANA_ABREV if abbreviated else DIAS_SEMANA_FULL
    return source[dt.weekday()]


def mes_pt(dt: datetime, abbreviated: bool = False) -> str:
    """Atalho: retorna apenas o nome do mes em pt_BR."""
    source = MESES_ABREV if abbreviated else MESES_FULL
    return source[dt.month - 1]
