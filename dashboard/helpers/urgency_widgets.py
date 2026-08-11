"""
Urgency Widgets (F2) - Componentes Streamlit reutilizaveis para urgency.

Fornece:
- urgency_badge(tier) — HTML badge colorido
- urgency_sparkline(history) — SVG inline sparkline
- hot_leads_widget(leads) — Widget de leads quentes para Home
- TIER_CONFIG — configuracao de cores/emojis/labels por tier
"""
import streamlit as st
from typing import Dict, Any, List


# ============================================================================
# TIER CONFIG
# ============================================================================

TIER_CONFIG: Dict[str, Dict[str, str]] = {
    "CRITICAL": {"emoji": "\U0001f534", "color": "#E53935", "bg": "#FFEBEE", "label": "Critico"},
    "HOT":      {"emoji": "\U0001f7e0", "color": "#FB8C00", "bg": "#FFF3E0", "label": "Quente"},
    "WARM":     {"emoji": "\U0001f7e1", "color": "#F9A825", "bg": "#FFFDE7", "label": "Morno"},
    # COLD em CINZA (nao verde): verde lia-se como "esta tudo bem" para um lead
    # frio. Alinhado com dashboard/labels.py, que ja usava ⚪ #90A4AE.
    "COLD":     {"emoji": "⚪", "color": "#90A4AE", "bg": "#ECEFF1", "label": "Frio"},
}


# ============================================================================
# BADGE
# ============================================================================

def urgency_badge(tier: str) -> str:
    """Retorna HTML badge colorido para o tier de urgencia.

    Args:
        tier: CRITICAL, HOT, WARM ou COLD.

    Returns:
        String HTML com badge estilizado.
    """
    cfg = TIER_CONFIG.get(tier, TIER_CONFIG["COLD"])
    return (
        f'<span style="'
        f'background-color:{cfg["bg"]};'
        f'color:{cfg["color"]};'
        f'padding:2px 8px;'
        f'border-radius:12px;'
        f'font-size:0.8em;'
        f'font-weight:600;'
        f'">{cfg["emoji"]} {cfg["label"]}</span>'
    )


def urgency_badge_text(tier: str) -> str:
    """Retorna texto simples para o tier (para uso em dataframes).

    Args:
        tier: CRITICAL, HOT, WARM ou COLD.

    Returns:
        String com emoji + label.
    """
    cfg = TIER_CONFIG.get(tier, TIER_CONFIG["COLD"])
    return f'{cfg["emoji"]} {cfg["label"]}'


# ============================================================================
# SPARKLINE
# ============================================================================

def urgency_sparkline(history: List[int], width: int = 80, height: int = 20) -> str:
    """Gera SVG inline sparkline a partir de historico de scores.

    Args:
        history: Lista de scores (mais antigo primeiro).
        width: Largura SVG em pixels.
        height: Altura SVG em pixels.

    Returns:
        String SVG inline.
    """
    if not history or len(history) < 2:
        return ""

    min_val = max(0, min(history) - 5)
    max_val = min(100, max(history) + 5)
    val_range = max(max_val - min_val, 1)

    n = len(history)
    step = width / max(n - 1, 1)

    points = []
    for i, val in enumerate(history):
        x = round(i * step, 1)
        y = round(height - ((val - min_val) / val_range) * height, 1)
        points.append(f"{x},{y}")

    polyline = " ".join(points)
    last_val = history[-1]

    # Cor baseada no ultimo score
    if last_val >= 80:
        color = "#E53935"
    elif last_val >= 60:
        color = "#FB8C00"
    elif last_val >= 40:
        color = "#F9A825"
    else:
        color = "#43A047"

    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
        f'<polyline points="{polyline}" '
        f'fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        f'<circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" '
        f'r="2" fill="{color}"/>'
        f'</svg>'
    )


# ============================================================================
# HOT LEADS WIDGET
# ============================================================================

def hot_leads_widget() -> None:
    """Renderiza widget de leads quentes na Home do dashboard.

    Busca leads CRITICAL e HOT e exibe cards resumidos.
    Deve ser chamado dentro de um st.container().
    """
    try:
        from tools.urgency_scorer import urgency_scorer

        critical = urgency_scorer.get_by_tier("CRITICAL", limit=5)
        hot = urgency_scorer.get_by_tier("HOT", limit=5)

        all_leads = critical + hot
        if not all_leads:
            st.info("Nenhum lead com urgencia CRITICAL ou HOT no momento.")
            return

        for lead in all_leads[:6]:
            tier = lead.get("urgency_tier", "COLD")
            cfg = TIER_CONFIG.get(tier, TIER_CONFIG["COLD"])
            score = lead.get("urgency_score", 0)
            name = lead.get("name", "?")
            city = lead.get("city", "")

            st.markdown(
                f'<div style="'
                f'border-left:4px solid {cfg["color"]};'
                f'padding:8px 12px;'
                f'margin-bottom:6px;'
                f'background:{cfg["bg"]};'
                f'border-radius:4px;'
                f'">'
                f'<strong>{cfg["emoji"]} {name}</strong>'
                f'<span style="float:right;font-weight:600;color:{cfg["color"]}">{score}</span>'
                f'<br><small style="color:#666">{city} &middot; {cfg["label"]}</small>'
                f'</div>',
                unsafe_allow_html=True,
            )

    except Exception as e:
        st.warning(f"Erro ao carregar leads quentes: {e}")
