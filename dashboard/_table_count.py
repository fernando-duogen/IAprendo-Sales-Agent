"""
_table_count - Sinalizacao consistente acima de tabelas no dashboard.

Mostra ao usuario quantos registros estao em tela, quantos foram filtrados do
total, quais filtros estao ativos e quantos selecionou.

Uso (acima de cada st.dataframe / st.data_editor):

    from dashboard._table_count import render_count

    # Caso simples (so total)
    render_count(total=len(escolas))

    # Com filtro aplicado
    render_count(
        total=88,
        filtered=23,
        filter_summary="status=qualified, score>=60",
        selected=5,
    )

    # Helper de filter_summary a partir de um dict
    render_count(
        total=88,
        filtered=23,
        filter_summary=summarize_filters({"status": "qualified", "score": ">=60"}),
    )
"""
from typing import Any, Dict, Optional

import streamlit as st


def render_count(
    total: int,
    filtered: Optional[int] = None,
    selected: Optional[int] = None,
    filter_summary: str = "",
    label_singular: str = "registro",
    label_plural: str = "registros",
) -> None:
    """Renderiza uma faixa st.caption padronizada acima de uma tabela.

    Args:
        total: Total de registros existentes (sem filtros).
        filtered: Quantos sobraram apos filtros. None se sem filtros aplicados.
        selected: Quantos o usuario selecionou (multiselect, checkbox, etc.).
        filter_summary: Texto curto descrevendo os filtros ativos.
        label_singular/plural: Termo para o tipo de registro (ex: "escola"/"escolas").
    """
    label = label_plural if total != 1 else label_singular
    parts = []

    if filtered is not None and filtered != total:
        parts.append(f"Mostrando **{filtered:,}** de **{total:,}** {label}")
    else:
        parts.append(f"Total: **{total:,}** {label}")

    if filter_summary:
        parts.append(f"filtros: {filter_summary}")

    if selected is not None and selected > 0:
        parts.append(f"**{selected:,}** selecionada(s)")

    st.caption(" &middot; ".join(parts), unsafe_allow_html=True)


def summarize_filters(filters: Dict[str, Any]) -> str:
    """Converte um dict {nome: valor} em string curta para exibir.

    Ignora valores vazios/None/listas vazias.

    Examples:
        >>> summarize_filters({"status": "qualified", "score_min": 60, "city": ""})
        'status=qualified, score_min=60'
        >>> summarize_filters({"types": ["privada", "publica"]})
        'types=privada,publica'
    """
    parts = []
    for k, v in filters.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, (list, tuple, set)):
            if not v:
                continue
            parts.append(f"{k}={','.join(str(x) for x in v)}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)
