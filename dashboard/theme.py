"""
IAprendo Dashboard — Material Design Theme
Componentes visuais reutilizaveis e CSS global.
Importar em cada pagina: from theme import apply_theme, metric_card, ...
"""

import os
import streamlit as st
from typing import Optional


def _sync_secrets_to_env():
    """Copia st.secrets para os.environ (Streamlit Cloud compatibility).
    No Streamlit Cloud, as variaveis ficam em st.secrets em vez de .env.
    Esta funcao faz a ponte para que config/settings.py funcione."""
    try:
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass  # Nao tem secrets (rodando local com .env)


# ============================================================================
# PALETA DE CORES — Material Design
# ============================================================================

COLORS = {
    "primary": "#1976D2",       # Blue 700
    "primary_light": "#BBDEFB", # Blue 100
    "primary_dark": "#0D47A1",  # Blue 900
    "secondary": "#00897B",     # Teal 600
    "secondary_light": "#B2DFDB",
    "accent": "#FF6D00",        # Orange A700
    "success": "#2E7D32",       # Green 800
    "success_light": "#C8E6C9",
    "warning": "#F57F17",       # Yellow 900
    "warning_light": "#FFF9C4",
    "error": "#C62828",         # Red 800
    "error_light": "#FFCDD2",
    "info": "#1565C0",          # Blue 800
    "info_light": "#E3F2FD",
    "surface": "#FFFFFF",
    "background": "#FAFAFA",
    "on_surface": "#212121",
    "on_surface_secondary": "#757575",
    "divider": "#E0E0E0",
    "shadow": "rgba(0,0,0,0.08)",
}

# Status → cor
STATUS_COLORS = {
    "raw": "#9E9E9E",
    "filtered": "#42A5F5",
    "qualified": "#1976D2",
    "enriched": "#00897B",
    "contacted": "#FF6D00",
    "sent": "#7B1FA2",
    "opened": "#F57F17",
    "replied": "#2E7D32",
    "meeting": "#00695C",
    "closed": "#1B5E20",
    "pending": "#F57F17",
    "approved": "#2E7D32",
    "rejected": "#C62828",
    "draft": "#9E9E9E",
    "active": "#2E7D32",
    "paused": "#F57F17",
    "completed": "#1976D2",
}


# ============================================================================
# CSS GLOBAL — Material Design
# ============================================================================

MATERIAL_CSS = """
<style>
/* ===== IMPORTS ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons+Outlined');

/* ===== GLOBAL RESET ===== */
.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #FAFAFA !important;
}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E0E0E0;
}
section[data-testid="stSidebar"] .stRadio label,
section[data-testid="stSidebar"] a {
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    padding: 6px 12px !important;
    border-radius: 8px !important;
    transition: background 0.15s ease !important;
}
section[data-testid="stSidebar"] a:hover {
    background-color: #E3F2FD !important;
}
section[data-testid="stSidebar"] a[aria-selected="true"] {
    background-color: #BBDEFB !important;
    font-weight: 600 !important;
    color: #1565C0 !important;
}
/* Inverter ordem: conteudo customizado (Painel + branding) antes da navegacao automatica */
section[data-testid="stSidebar"] > div:first-child {
    display: flex;
    flex-direction: column;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    order: 2;
    padding-top: 0 !important;
    margin-top: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    order: 1;
    padding-top: 8px !important;
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
}
/* Esconder link "app" auto-gerado (substituido por "Painel" via page_link) */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li:first-child {
    display: none !important;
}
/* Estilo do link Painel customizado */
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:first-of-type {
    font-weight: 600 !important;
    margin-bottom: 0 !important;
}
/* Reduzir gap do primeiro item da navegacao auto-gerada (depois que Painel some) */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] ul {
    padding-top: 4px !important;
    margin-top: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] li {
    margin: 0 !important;
}

/* ===== HEADERS ===== */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    color: #212121 !important;
    font-weight: 600 !important;
}
h1 { font-size: 28px !important; letter-spacing: -0.5px; }
h2 { font-size: 22px !important; }
h3 { font-size: 18px !important; }

/* ===== METRIC CARDS ===== */
.metric-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px 14px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    transition: box-shadow 0.2s ease;
    border-left: 4px solid #1976D2;
    min-height: 90px;
    position: relative;
    overflow: hidden;
}
.metric-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}
.metric-card .metric-value {
    font-size: 32px;
    font-weight: 700;
    color: #212121;
    line-height: 1.2;
}
.metric-card .metric-label {
    font-size: 11px;
    font-weight: 600;
    color: #757575;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.metric-card .metric-delta {
    font-size: 12px;
    font-weight: 500;
    margin-top: 4px;
}

/* ===== DATA CARDS ===== */
.data-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    margin-bottom: 12px;
    transition: all 0.2s ease;
    border: 1px solid #F5F5F5;
}
.data-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border-color: #E0E0E0;
}

/* ===== STATUS BADGES ===== */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ===== BUTTONS ===== */
.stButton > button {
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}
.stButton > button[kind="primary"] {
    background-color: #1976D2 !important;
    color: white !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1565C0 !important;
    box-shadow: 0 2px 8px rgba(25,118,210,0.3) !important;
}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0px;
    border-bottom: 2px solid #E0E0E0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500;
    font-size: 14px;
    padding: 12px 24px;
    color: #757575;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: #1976D2;
    border-bottom: 2px solid #1976D2;
}

/* ===== DATAFRAME / DATA EDITOR ===== */
.stDataFrame, [data-testid="stDataEditor"] {
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ===== INPUTS — Fundo branco para visibilidade ===== */
.stTextInput > div > div,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stNumberInput > div > div,
.stTextArea > div > div {
    border-radius: 8px !important;
    border: 1.5px solid #BDBDBD !important;
    background-color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div:focus-within,
.stSelectbox > div > div:focus-within,
.stMultiSelect > div > div:focus-within,
.stTextArea > div > div:focus-within {
    border-color: #1976D2 !important;
    box-shadow: 0 0 0 2px rgba(25,118,210,0.2) !important;
}
.stTextInput input, .stTextArea textarea {
    background-color: #FFFFFF !important;
}
.stSlider > div {
    padding-top: 4px;
}
/* Labels de input mais visiveis */
.stTextInput label, .stSelectbox label, .stMultiSelect label,
.stNumberInput label, .stTextArea label, .stSlider label,
.stCheckbox label, .stRadio label {
    font-weight: 500 !important;
    color: #424242 !important;
    font-size: 13px !important;
}

/* ===== EXPANDERS ===== */
.streamlit-expanderHeader {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    background-color: #FAFAFA;
    border-radius: 8px;
}

/* ===== SECTION HEADER ===== */
.section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 24px 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid #E0E0E0;
}
.section-header .material-icons-outlined {
    font-size: 22px;
    color: #1976D2;
}
.section-header h3 {
    margin: 0 !important;
    padding: 0 !important;
}

/* ===== FILTER BAR ===== */
.filter-bar {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 20px;
    border: 1px solid #F0F0F0;
}

/* ===== KANBAN CARD ===== */
.kanban-card {
    background: #FFFFFF;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border-left: 4px solid #1976D2;
    transition: all 0.2s ease;
    cursor: default;
}
.kanban-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    transform: translateY(-1px);
}
.kanban-card .card-title {
    font-weight: 600;
    font-size: 14px;
    color: #212121;
    margin-bottom: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.kanban-card .card-subtitle {
    font-size: 12px;
    color: #757575;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.kanban-card .card-score {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    color: white;
}

/* ===== TIMELINE ===== */
.timeline-item {
    position: relative;
    padding-left: 28px;
    padding-bottom: 20px;
    border-left: 2px solid #E0E0E0;
    margin-left: 10px;
}
.timeline-item:last-child {
    border-left: 2px solid transparent;
}
.timeline-item::before {
    content: '';
    position: absolute;
    left: -6px;
    top: 4px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #1976D2;
    border: 2px solid #FFFFFF;
    box-shadow: 0 0 0 2px #1976D2;
}
.timeline-item .tl-date {
    font-size: 11px;
    color: #9E9E9E;
    font-weight: 500;
}
.timeline-item .tl-title {
    font-size: 14px;
    font-weight: 500;
    color: #212121;
}
.timeline-item .tl-detail {
    font-size: 13px;
    color: #757575;
}

/* ===== STEPPER ===== */
.stepper {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 0;
}
.step {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    position: relative;
}
.step-circle {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    color: white;
    margin-bottom: 8px;
    z-index: 1;
}
.step-label {
    font-size: 12px;
    font-weight: 500;
    color: #757575;
    text-align: center;
}
.step-count {
    font-size: 18px;
    font-weight: 700;
    color: #212121;
}
.step-line {
    position: absolute;
    top: 20px;
    left: 50%;
    width: 100%;
    height: 3px;
    background: #E0E0E0;
    z-index: 0;
}

/* ===== BREADCRUMB ===== */
.breadcrumb {
    font-size: 13px;
    color: #9E9E9E;
    margin-bottom: 16px;
}
.breadcrumb a {
    color: #1976D2;
    text-decoration: none;
}

/* ===== ALERT BANNER ===== */
.alert-banner {
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    font-weight: 500;
}
.alert-success { background: #C8E6C9; color: #1B5E20; }
.alert-warning { background: #FFF9C4; color: #F57F17; }
.alert-error { background: #FFCDD2; color: #B71C1C; }
.alert-info { background: #E3F2FD; color: #0D47A1; }

/* ===== AVATAR ===== */
.avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 16px;
    color: white;
}

/* ===== MISC ===== */
.divider {
    border: none;
    border-top: 1px solid #E0E0E0;
    margin: 20px 0;
}
.text-muted { color: #9E9E9E; }
.text-small { font-size: 12px; }
.mt-1 { margin-top: 8px; }
.mt-2 { margin-top: 16px; }
.mt-3 { margin-top: 24px; }
.mb-1 { margin-bottom: 8px; }
.mb-2 { margin-bottom: 16px; }

/* ===== MOBILE RESPONSIVE ===== */
@media (max-width: 768px) {
    h1 { font-size: 22px !important; }
    h2 { font-size: 18px !important; }
    h3 { font-size: 15px !important; }

    .metric-card { padding: 14px 16px; }
    .metric-card .metric-value { font-size: 24px; }
    .metric-card .metric-label { font-size: 11px; }

    .data-card { padding: 12px 14px; }

    .kanban-card { padding: 10px 12px; }
    .kanban-card .card-title { font-size: 13px; }

    .stepper { flex-wrap: wrap; gap: 8px; }
    .step { min-width: 60px; flex: 0 0 auto; }
    .step-circle { width: 32px; height: 32px; font-size: 13px; }
    .step-label { font-size: 10px; }
    .step-count { font-size: 14px; }
    .step-line { display: none; }

    .filter-bar { padding: 12px; }

    .section-header { margin: 16px 0 10px 0; }

    /* Stack columns on mobile */
    [data-testid="column"] {
        min-width: 100% !important;
    }
}

@media (max-width: 480px) {
    .stApp > header { display: none; }
    .metric-card .metric-value { font-size: 20px; }
    .stepper { padding: 10px 0; }
}
</style>
"""


# ============================================================================
# FUNCOES UTILITARIAS — Componentes reutilizaveis
# ============================================================================

def _add_sidebar_home():
    """Adiciona branding IAprendo + link Painel no topo do sidebar em todas as paginas."""
    with st.sidebar:
        st.markdown(
            '<p style="text-align:center;padding:10px 0 6px 0;margin:0;border-bottom:1px solid #E0E0E0">'
            '<strong style="font-size:18px;color:#1976D2">🎓 IAprendo</strong><br/>'
            '<span style="font-size:11px;color:#9E9E9E">Agente de Vendas</span></p>',
            unsafe_allow_html=True,
        )
        st.page_link("app.py", label="🏠 Painel")


def apply_theme():
    """Aplica tema Material Design. Chamar no inicio de cada pagina."""
    _sync_secrets_to_env()
    st.set_page_config(
        page_title="IAprendo Sales",
        page_icon="🎓",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(MATERIAL_CSS, unsafe_allow_html=True)
    _add_sidebar_home()


def apply_theme_no_config():
    """Aplica CSS sem set_page_config (para paginas que nao sao a principal)."""
    _sync_secrets_to_env()
    st.markdown(MATERIAL_CSS, unsafe_allow_html=True)
    _add_sidebar_home()


def metric_card(label: str, value, color: str = COLORS["primary"], delta: str = "", icon: str = ""):
    """Renderiza card de metrica Material Design."""
    delta_html = f'<span style="font-size:12px;font-weight:500;color:{COLORS["success"]};display:block">{delta}</span>' if delta else ""
    icon_html = f'<span class="material-icons-outlined" style="font-size:26px;color:{color};position:absolute;right:10px;top:14px;opacity:0.25">{icon}</span>' if icon else ""
    st.markdown(
        f'<p class="metric-card" style="border-left-color:{color}">'
        f'{icon_html}'
        f'<span class="metric-label">{label}</span><br/>'
        f'<span class="metric-value">{value}</span><br/>'
        f'{delta_html}'
        f'</p>',
        unsafe_allow_html=True,
    )


def status_badge(status: str, text: Optional[str] = None):
    """Renderiza badge de status colorido."""
    label = text or status.replace("_", " ").title()
    color = STATUS_COLORS.get(status, "#9E9E9E")
    bg = color + "20"  # 12% opacity
    return f'<span class="badge" style="background:{bg};color:{color}">{label}</span>'


def section_header(title: str, icon: str = ""):
    """Renderiza header de secao com icone Material."""
    if icon:
        st.markdown(
            f'<p style="display:flex;align-items:center;gap:8px;margin:20px 0 12px 0;'
            f'padding-bottom:8px;border-bottom:2px solid #E0E0E0">'
            f'<span class="material-icons-outlined" style="font-size:20px;color:#1976D2">{icon}</span>'
            f'<strong style="font-size:18px;color:#212121">{title}</strong></p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"### {title}")


def alert_banner(message: str, type: str = "info"):
    """Renderiza banner de alerta colorido. type: success, warning, error, info."""
    colors = {
        "success": ("#C8E6C9", "#1B5E20"),
        "warning": ("#FFF9C4", "#F57F17"),
        "error": ("#FFCDD2", "#B71C1C"),
        "info": ("#E3F2FD", "#0D47A1"),
    }
    bg, fg = colors.get(type, colors["info"])
    icons = {"success": "check_circle", "warning": "warning", "error": "error", "info": "info"}
    icon = icons.get(type, "info")
    st.markdown(
        f'<p style="padding:12px 20px;border-radius:8px;margin-bottom:12px;'
        f'background:{bg};color:{fg};font-size:14px;font-weight:500;'
        f'display:flex;align-items:center;gap:10px">'
        f'<span class="material-icons-outlined">{icon}</span>'
        f'{message}</p>',
        unsafe_allow_html=True,
    )


def kanban_card(name: str, subtitle: str = "", score: int = 0, color: str = COLORS["primary"]):
    """Renderiza card de kanban estilo Material."""
    score_color = COLORS["success"] if score >= 70 else COLORS["warning"] if score >= 40 else COLORS["on_surface_secondary"]
    score_html = (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'font-size:11px;font-weight:700;color:white;background:{score_color}">{score}</span>'
        if score else ""
    )
    return (
        f'<p style="background:#FFFFFF;border-radius:10px;padding:12px 14px;margin-bottom:8px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.08);border-left:4px solid {color}">'
        f'<strong style="font-size:13px;color:#212121;display:block;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{name}</strong>'
        f'<span style="font-size:11px;color:#757575;display:block;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{subtitle}</span>'
        f'{score_html}</p>'
    )


def timeline_item(date: str, title: str, detail: str = "", color: str = COLORS["primary"]):
    """Renderiza item de timeline vertical."""
    return (
        f'<p style="position:relative;padding-left:24px;padding-bottom:16px;'
        f'border-left:2px solid #E0E0E0;margin-left:8px;margin-bottom:0">'
        f'<span style="position:absolute;left:-5px;top:4px;width:8px;height:8px;'
        f'border-radius:50%;background:{color}"></span>'
        f'<span style="font-size:11px;color:#9E9E9E;font-weight:500">{date}</span><br/>'
        f'<span style="font-size:14px;font-weight:500;color:#212121">{title}</span><br/>'
        f'<span style="font-size:13px;color:#757575">{detail}</span></p>'
    )


def avatar(name: str, color: str = COLORS["primary"]):
    """Renderiza avatar circular com iniciais."""
    initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "?"
    return f'<span class="avatar" style="background:{color}">{initials}</span>'


def score_color(score: int) -> str:
    """Retorna cor baseada no score."""
    if score >= 80:
        return COLORS["success"]
    elif score >= 60:
        return "#43A047"
    elif score >= 40:
        return COLORS["warning"]
    elif score >= 20:
        return COLORS["accent"]
    else:
        return COLORS["on_surface_secondary"]


def pipeline_stepper(stages: list):
    """Renderiza stepper horizontal como cards compactos com barra de cor.
    stages: [{"label": "Novas", "count": 51, "color": "#9E9E9E"}, ...]
    """
    cols = st.columns(len(stages))
    for i, (col, stage) in enumerate(zip(cols, stages)):
        with col:
            st.markdown(
                f'<p style="text-align:center;background:#FFFFFF;border-radius:10px;'
                f'padding:12px 6px 10px 6px;margin:0;'
                f'box-shadow:0 1px 3px rgba(0,0,0,0.07);'
                f'border-top:3px solid {stage["color"]}">'
                f'<span style="font-size:11px;font-weight:600;color:{stage["color"]};'
                f'text-transform:uppercase;letter-spacing:0.3px">{stage["label"]}</span><br/>'
                f'<span style="font-size:22px;font-weight:700;color:#212121">{stage["count"]}</span>'
                f'</p>',
                unsafe_allow_html=True,
            )


def filter_container():
    """Inicia container de filtros estilizado."""
    return st.container()


def breadcrumb(items: list):
    """Renderiza breadcrumb. items: ["Home", "Escolas", "Detalhe"]"""
    parts = " &rsaquo; ".join(items)
    st.markdown(f'<div class="breadcrumb">{parts}</div>', unsafe_allow_html=True)
