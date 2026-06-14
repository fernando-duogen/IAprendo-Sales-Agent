"""
IAprendo Dashboard — Material Design Theme
Componentes visuais reutilizaveis e CSS global.
Importar em cada pagina: from theme import apply_theme, metric_card, ...
"""

import base64
import os
from pathlib import Path
from typing import Optional

import streamlit as st


def _load_logo_data_uri() -> str:
    """Le a marca (data/brand/logo_iaprendo.png, branca/transparente) e devolve
    como data-URI base64 — pra estampar na faixa azul do sidebar sem depender de
    URL externa. Vazio se o arquivo nao existir (fallback pra texto)."""
    try:
        p = Path(__file__).parent.parent / "data" / "brand" / "logo_iaprendo.png"
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


_LOGO_DATA_URI = _load_logo_data_uri()


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
/* v2 (st.navigation): NAO esconder o 1o item — e a pagina "Hoje".
   Cabecalhos de grupo do nav (Vender/Acompanhar/Sistema) no padrao do mockup */
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] header,
section[data-testid="stSidebar"] [data-testid="stNavSectionHeader"] {
    font-size: 10.5px !important;
    font-weight: 600 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    padding: 12px 12px 4px 12px !important;
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
    box-shadow: 0 1px 3px rgba(16,24,40,0.06);
    transition: box-shadow 0.2s ease;
    border-left: 4px solid #1976D2;
    min-height: 90px;
    position: relative;
    overflow: hidden;
}
.metric-card:hover {
    box-shadow: 0 4px 14px rgba(16,24,40,0.10);
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
    box-shadow: 0 1px 3px rgba(16,24,40,0.06);
    margin-bottom: 12px;
    transition: all 0.2s ease;
    border: 1px solid #EEF2F7;
}
.data-card:hover {
    box-shadow: 0 6px 16px rgba(16,24,40,0.10);
    border-color: #E3E8EF;
}

/* ===== ACTION TILES (Painel home) ===== */
/* Marker div (vazio) dentro de stMarkdown dentro de stElementContainer — usado
   com :has() pra selecionar o PROXIMO stElementContainer (que contem o botao). */
div[data-testid="stElementContainer"]:has(.action-tile),
div[data-testid="stElementContainer"]:has(.action-tile-hot) {
    margin-bottom: 0 !important;
    height: 0 !important;
    overflow: visible !important;
    padding: 0 !important;
}
.action-tile, .action-tile-hot {
    display: none !important;  /* o marker em si nao renderiza */
}
/* Container do botao (stButton) — garante full width */
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"],
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] {
    width: 100% !important;
}
/* O stElementContainer logo DEPOIS do marker vira o tile completo */
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button,
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button {
    min-height: 88px !important;
    height: 88px !important;
    width: 100% !important;
    padding: 14px 16px !important;
    text-align: left !important;
    border: 1px solid #E0E0E0 !important;
    border-left: 4px solid #1976D2 !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    transition: all 0.15s ease !important;
    white-space: normal !important;
    line-height: 1.3 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
}
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button > div,
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button > div {
    align-items: flex-start !important;
    text-align: left !important;
    width: 100% !important;
    justify-content: flex-start !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 4px !important;
}
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button:hover,
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button:hover {
    box-shadow: 0 4px 14px rgba(0,0,0,0.10) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button {
    background: linear-gradient(to right, #FFF8E1 0%, #FFFFFF 55%) !important;
    border-left-width: 5px !important;
}
/* Icone Material dentro do button (:material/nome: gera span com data-testid=stIconMaterial) */
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"],
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] {
    font-size: 28px !important;
    vertical-align: middle !important;
    margin-right: 6px !important;
    flex-shrink: 0 !important;
}
/* Cores por tile (border-left + icone) — 6 variantes baseadas em COLORS */
div[data-testid="stElementContainer"]:has(.tc-primary) + div[data-testid="stElementContainer"] button { border-left-color: #1976D2 !important; }
div[data-testid="stElementContainer"]:has(.tc-primary) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #1976D2 !important; }
div[data-testid="stElementContainer"]:has(.tc-secondary) + div[data-testid="stElementContainer"] button { border-left-color: #00897B !important; }
div[data-testid="stElementContainer"]:has(.tc-secondary) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #00897B !important; }
div[data-testid="stElementContainer"]:has(.tc-warning) + div[data-testid="stElementContainer"] button { border-left-color: #F57F17 !important; }
div[data-testid="stElementContainer"]:has(.tc-warning) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #F57F17 !important; }
div[data-testid="stElementContainer"]:has(.tc-success) + div[data-testid="stElementContainer"] button { border-left-color: #2E7D32 !important; }
div[data-testid="stElementContainer"]:has(.tc-success) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #2E7D32 !important; }
div[data-testid="stElementContainer"]:has(.tc-accent) + div[data-testid="stElementContainer"] button { border-left-color: #FF6D00 !important; }
div[data-testid="stElementContainer"]:has(.tc-accent) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #FF6D00 !important; }
div[data-testid="stElementContainer"]:has(.tc-info) + div[data-testid="stElementContainer"] button { border-left-color: #1565C0 !important; }
div[data-testid="stElementContainer"]:has(.tc-info) + div[data-testid="stElementContainer"] button span[role="img"][aria-label*="icon"] { color: #1565C0 !important; }
/* Titulo (primeira linha, strong) */
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button p strong,
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button p strong {
    font-size: 14.5px !important;
    color: #212121 !important;
    font-weight: 600 !important;
}
/* Subtitulo (segunda linha do markdown) */
div[data-testid="stElementContainer"]:has(.action-tile) + div[data-testid="stElementContainer"] button p,
div[data-testid="stElementContainer"]:has(.action-tile-hot) + div[data-testid="stElementContainer"] button p {
    margin: 0 !important;
    font-size: 12px !important;
    color: #616161 !important;
    font-weight: 400 !important;
    line-height: 1.4 !important;
    width: 100% !important;
}

/* ===== KANBAN CARDS CLICAVEIS (usado no Pipeline Comercial) ===== */
div[data-testid="stElementContainer"]:has(.kanban-click) {
    margin-bottom: -38px !important;
    height: 0 !important;
    overflow: visible !important;
}
.kanban-click { display: none !important; }

/* Quando kanban cards estao dentro de um expander "Ver mais N", o
   stExpanderDetails tem padding: 10px 16px por padrao, eating 32px
   horizontais. Em colunas estreitas (88px) isso deixa os cards com
   ~54px — distorcendo o layout. Reduz o padding pra recuperar a
   largura e alinhar com os top 6 cards visiveis acima. */
[data-testid="stExpander"]:has(.kanban-click) [data-testid="stExpanderDetails"] {
    padding: 8px 2px !important;
}
[data-testid="stExpander"]:has(.kanban-click) summary {
    padding: 8px 10px !important;
}

div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] {
    width: 100% !important;
}
div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] button {
    min-height: 64px !important;
    height: auto !important;
    width: 100% !important;
    padding: 10px 12px !important;
    text-align: left !important;
    border: 1px solid #E0E0E0 !important;
    border-left: 4px solid #1976D2 !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    white-space: normal !important;
    line-height: 1.3 !important;
    display: flex !important;
    align-items: flex-start !important;
    justify-content: flex-start !important;
    margin-bottom: 6px !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] button > div {
    align-items: flex-start !important;
    text-align: left !important;
    width: 100% !important;
    justify-content: flex-start !important;
}
div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] button:hover {
    box-shadow: 0 3px 8px rgba(0,0,0,0.10) !important;
    transform: translateY(-1px) !important;
    border-color: #BBDEFB !important;
}
div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] button p strong {
    font-size: 12.5px !important;
    color: #212121 !important;
    font-weight: 600 !important;
    display: block !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}
div[data-testid="stElementContainer"]:has(.kanban-click) + div[data-testid="stElementContainer"] button p {
    font-size: 11px !important;
    color: #757575 !important;
    margin: 0 !important;
    line-height: 1.35 !important;
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
    """Branding IAprendo no topo do sidebar (faixa azul + logo da marca)."""
    with st.sidebar:
        if _LOGO_DATA_URI:
            brand = (
                '<div style="background:linear-gradient(135deg,#1976D2 0%,#1565C0 100%);'
                'border-radius:14px;padding:16px 14px 13px;margin:2px 0 10px;'
                'box-shadow:0 1px 3px rgba(16,24,40,.10);text-align:center">'
                f'<img src="{_LOGO_DATA_URI}" alt="IAprendo" '
                'style="height:30px;display:block;margin:0 auto 5px"/>'
                '<div style="font-size:10.5px;color:#BBDEFB;letter-spacing:.6px;'
                'text-transform:uppercase">Agente de Vendas</div></div>'
            )
        else:
            brand = (
                '<p style="text-align:center;padding:10px 0 6px 0;margin:0;'
                'border-bottom:1px solid #E0E0E0">'
                '<strong style="font-size:18px;color:#1976D2">🎓 IAprendo</strong><br/>'
                '<span style="font-size:11px;color:#9E9E9E">Agente de Vendas</span></p>'
            )
        st.markdown(brand, unsafe_allow_html=True)
        # v2: "Hoje" ja e o 1o item do st.navigation — sem page_link duplicado.
        # Carimbo de build — confirma num relance se o Cloud esta na versao nova.
        try:
            from dashboard._build import BUILD
            st.caption(f"build · {BUILD}")
        except Exception:
            pass


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


def metric_card_clickable(label: str, value, color: str = COLORS["primary"],
                          delta: str = "", icon: str = "", key: str = "") -> bool:
    """Metric card que funciona como botao clicavel (st.button com visual de card).
    Retorna True quando clicado. Uso: if metric_card_clickable(...): st.switch_page(...)
    """
    icon_emoji = {"school": "🏫", "pending_actions": "⏳", "send": "📤",
                  "mark_email_read": "📧", "reply": "💬", "autorenew": "🔄",
                  "event": "📅", "payments": "💰"}.get(icon, "📊")
    delta_str = f" ({delta})" if delta else ""
    btn_label = f"{icon_emoji} {label}: {value}{delta_str}"
    return st.button(btn_label, key=key, use_container_width=True, type="secondary")


def action_tile(
    icon: str,
    title: str,
    subtitle: str = "",
    color: str = COLORS["primary"],
    key: str = "",
    highlight: bool = False,
) -> bool:
    """Tile clicavel grande pra home/hub (1 elemento unico, sem botao separado).

    Renderiza um st.button com label em markdown (:material/icon: + **title**
    + subtitle) estilizado via CSS injetado em inject_theme() como card com
    icone grande, borda colorida a esquerda, hover, etc.

    Args:
        icon: nome do icone Material (ex: "rocket_launch", "task_alt")
        title: titulo em negrito (primeira linha)
        subtitle: linha secundaria dinamica (ex: "5 pendentes")
        color: cor do icone e borda esquerda (usar COLORS[...])
        key: chave unica do botao
        highlight: se True, destaca com fundo levemente amarelado (acao urgente)

    Returns:
        True quando clicado. Uso tipico:
            if action_tile("rocket_launch", "Pipeline", "Rodar", key="t1"):
                st.switch_page("pages/5_📊_Pipeline.py")
    """
    wrapper_class = "action-tile-hot" if highlight else "action-tile"
    # Mapeia hex color -> classe semantica pra CSS (:has seletor)
    color_map = {
        COLORS["primary"]: "tc-primary",
        COLORS["secondary"]: "tc-secondary",
        COLORS["warning"]: "tc-warning",
        COLORS["success"]: "tc-success",
        COLORS["accent"]: "tc-accent",
        COLORS["info"]: "tc-info",
    }
    color_class = color_map.get(color, "tc-primary")
    st.markdown(
        f'<div class="{wrapper_class} {color_class}"></div>',
        unsafe_allow_html=True,
    )
    # Label em markdown multi-linha: primeira linha com icone+titulo,
    # segunda linha com subtitulo (separado por 2 espacos + \n = <br>)
    if subtitle:
        label = f":material/{icon}: **{title}**  \n{subtitle}"
    else:
        label = f":material/{icon}: **{title}**"
    return st.button(label, key=key, use_container_width=True)


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


def kanban_card(
    name: str,
    subtitle: str = "",
    score: int = 0,
    color: str = COLORS["primary"],
    alvo: int = 0,
    nivel_tech: str = "",
):
    """Renderiza card de kanban estilo Material.

    Args:
        name: Nome da escola.
        subtitle: Linha de legenda (cidade, data, etc.).
        score: Score de qualificacao (0-100).
        color: Cor da borda esquerda.
        alvo: Total de alunos alvo (Fund AF + Medio). Se > 0, renderiza badge.
        nivel_tech: Nivel tecnologico (Alto/Medio/Baixo). Se preenchido, renderiza chip colorido.
    """
    score_c = COLORS["success"] if score >= 70 else COLORS["warning"] if score >= 40 else COLORS["on_surface_secondary"]
    score_html = (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'font-size:11px;font-weight:700;color:white;background:{score_c};margin-right:4px">{score}</span>'
        if score else ""
    )

    # Badge de alvo (alunos Fund AF + Medio)
    alvo_html = ""
    if alvo and alvo > 0:
        alvo_html = (
            f'<span style="display:inline-block;padding:2px 7px;border-radius:10px;'
            f'font-size:10px;font-weight:600;color:#1565c0;background:#e3f2fd;margin-right:4px" '
            f'title="Alunos alvo: Fund AF + Medio">&#128101; {alvo}</span>'
        )

    # Chip de nivel tecnologico
    tech_html = ""
    if nivel_tech and nivel_tech != "-":
        tech_color_map = {
            "Alto": "#2e7d32",
            "Medio": "#f57c00",
            "Médio": "#f57c00",
            "Baixo": "#c62828",
        }
        tech_bg_map = {
            "Alto": "#e8f5e9",
            "Medio": "#fff3e0",
            "Médio": "#fff3e0",
            "Baixo": "#ffebee",
        }
        tc = tech_color_map.get(nivel_tech, "#616161")
        tb = tech_bg_map.get(nivel_tech, "#f5f5f5")
        tech_html = (
            f'<span style="display:inline-block;padding:2px 7px;border-radius:10px;'
            f'font-size:10px;font-weight:600;color:{tc};background:{tb}" '
            f'title="Nivel tecnologico">{nivel_tech}</span>'
        )

    return (
        f'<p style="background:#FFFFFF;border-radius:10px;padding:12px 14px;margin-bottom:8px;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.08);border-left:4px solid {color}">'
        f'<strong style="font-size:13px;color:#212121;display:block;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap">{name}</strong>'
        f'<span style="font-size:11px;color:#757575;display:block;overflow:hidden;'
        f'text-overflow:ellipsis;white-space:nowrap;margin-bottom:4px">{subtitle}</span>'
        f'{score_html}{alvo_html}{tech_html}</p>'
    )


def kanban_card_clickable(
    name: str,
    score: int = 0,
    alvo: int = 0,
    nivel_tech: str = "",
    color: str = COLORS["primary"],
    key: str = "",
    subtitle: str = "",
) -> bool:
    """Card clicavel pro kanban comercial. Retorna True quando clicado.

    Usa marker div (`.kanban-click`) + CSS :has() pra estilizar o
    stButton adjacente como um card visual. Pattern espelhado do
    action_tile no Painel home.

    Args:
        name: Nome da escola (truncado em 30 chars no label).
        score: Score IA (0-100).
        alvo: Matriculas Fund AF + Medio.
        nivel_tech: Nivel tecnologico (Alto/Medio/Baixo).
        color: Cor do stage (usada no header da coluna, nao no card em si).
        key: Chave unica do botao.
        subtitle: Linha extra (ex: valor R$/mes pra stage proposta/cliente).

    Returns:
        True quando clicado.
    """
    st.markdown(
        '<div class="kanban-click"></div>',
        unsafe_allow_html=True,
    )
    meta_parts = []
    if score:
        meta_parts.append(f"Score {score}")
    if alvo:
        meta_parts.append(f"{alvo} alunos")
    if nivel_tech and nivel_tech != "-":
        meta_parts.append(nivel_tech)
    if subtitle:
        meta_parts.append(subtitle)
    meta = " \u00b7 ".join(meta_parts) if meta_parts else "\u00a0"
    # Strip nome antes do ** pra evitar space-before-closing-delim (markdown
    # nao renderiza "**text **" como bold — exige que nao haja espaco antes).
    name_clean = (name or "?")[:30].rstrip()
    label = f"**{name_clean}**  \n{meta}"
    return st.button(label, key=key, use_container_width=True)


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


# ============================================================================
# COMPONENTES v2 (redesign "Dia de Venda" — F1)
# Vocabulario vem SEMPRE de dashboard/labels.py (fonte unica).
# ============================================================================

def stage_pill(status, commercial_stage=None) -> str:
    """Pill PREENCHIDA da etapa da escola (blueprint §6). Retorna HTML."""
    from dashboard.labels import school_stage
    label, cor = school_stage(status, commercial_stage)
    txt_color = "#3E2723" if label == "Respondeu" else "#fff"
    return (f'<span style="display:inline-block;border-radius:99px;padding:3px 11px;'
            f'font-size:12px;font-weight:600;color:{txt_color};background:{cor};'
            f'white-space:nowrap">{label}</span>')


def priority_badge(tier_or_score, breakdown: str = "") -> str:
    """Badge de Prioridade (🔴🟠🟡⚪) — a UNICA prioridade em listas (§5).
    breakdown vai no title (hover) como explicacao."""
    from dashboard.labels import PRIORITY_TIERS, priority_of
    tier = tier_or_score if isinstance(tier_or_score, str) else priority_of(tier_or_score)
    t = PRIORITY_TIERS.get((tier or "COLD").upper(), PRIORITY_TIERS["COLD"])
    title = breakdown or "Engajamento + Potencial + Avaliacao da IA"
    return (f'<span title="{title}" style="font-size:12.5px;font-weight:700;'
            f'color:{t["color"]};white-space:nowrap;cursor:help">'
            f'{t["emoji"]} {t["label"]}</span>')


def message_chip(status, scheduled_hint=None) -> str:
    """Chip CONTORNADO de status de mensagem (familia visual distinta da pill)."""
    from dashboard.labels import MESSAGE_STATUS, message_status_label
    m = MESSAGE_STATUS.get((status or "pending").lower(), MESSAGE_STATUS["pending"])
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'border-radius:99px;padding:3px 11px;font-size:12px;font-weight:600;'
            f'border:1.5px solid {m["color"]};color:{m["color"]};background:#fff;'
            f'white-space:nowrap">{message_status_label(status, scheduled_hint)}</span>')


# Cores por tipo de atividade (icone em circulo — visual do mockup hoje.html)
_ACTIVITY_COLORS = {
    "responder": "#C62828", "follow_up": "#E65100", "ligar": "#1976D2",
    "preparar_reuniao": "#FB8C00", "registrar_resultado": "#8E24AA",
    "aprovar_mensagens": "#2E7D32", "tarefa": "#607D8B",
}

ACTIVITY_CSS = """
<style>
.v2-act{display:flex;align-items:center;gap:12px;background:#fff;
  border:1px solid #E3E8EF;border-radius:12px;padding:11px 16px;
  margin-bottom:8px;transition:box-shadow .15s ease, transform .12s ease}
.v2-act:hover{box-shadow:0 4px 14px rgba(16,24,40,.10);transform:translateY(-1px)}
.v2-act.overdue{background:#FFF5F5;border-left:4px solid #C62828}
.v2-act-ico{width:38px;height:38px;border-radius:10px;display:flex;
  align-items:center;justify-content:center;font-size:17px;flex-shrink:0}
.v2-act-body{flex:1;min-width:0}
.v2-act-title{font-weight:600;font-size:14px;color:#1A202C;line-height:1.3}
.v2-act-sub{font-size:12px;color:#94A3B8;margin-top:2px;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.v2-act-when{font-size:11.5px;color:#64748B;white-space:nowrap;font-weight:600;
  flex-shrink:0;text-align:right}
.v2-act-when.late{color:#C62828}
.v2-side{background:#fff;border:1px solid #E3E8EF;border-radius:12px;
  padding:13px 16px;margin-bottom:10px;transition:box-shadow .15s ease}
.v2-side:hover{box-shadow:0 3px 10px rgba(16,24,40,.08)}
</style>
"""


def activity_row(activity: dict, overdue: bool = False,
                 when_txt: str = "") -> str:
    """Card de atividade da agenda (Home v2 — visual do mockup hoje.html):
    icone em circulo colorido por tipo + titulo + subtitulo + prazo a direita.
    Botoes (✓/⏰/→) ficam por conta da pagina via st.button ao lado.
    Requer ACTIVITY_CSS injetado 1x na pagina."""
    from dashboard.labels import ACTIVITY_SOURCE_BADGE, ACTIVITY_TYPES
    a_type = (activity.get("type") or "tarefa").lower()
    cor = _ACTIVITY_COLORS.get(a_type, "#607D8B")
    emoji = ACTIVITY_TYPES.get(a_type, {}).get("emoji", "✍️")
    pr = ('<span style="color:#C62828;font-weight:700" title="Prioridade maxima">'
          '🔴</span> ' if activity.get("priority") == 1 else "")
    src = ACTIVITY_SOURCE_BADGE.get(activity.get("source", "manual"), "")
    details = (activity.get("details") or "").replace("\n", " ")[:80]
    sub = " · ".join(x for x in (details, src) if x)
    when_html = (f'<div class="v2-act-when{" late" if overdue else ""}">'
                 f'{when_txt}</div>') if when_txt else ""
    return (
        f'<div class="v2-act{" overdue" if overdue else ""}">'
        f'<div class="v2-act-ico" style="background:{cor}1F;color:{cor}">{emoji}</div>'
        f'<div class="v2-act-body">'
        f'<div class="v2-act-title">{pr}{activity.get("title", "")}</div>'
        + (f'<div class="v2-act-sub">{sub}</div>' if sub else "")
        + f'</div>{when_html}</div>'
    )


def goal_progress(label: str, realized: float, target: float, color: str = None) -> str:
    """Barra de progresso de meta (verde >=80% do ritmo, amarela 50-79, vermelha <50)."""
    pct = min(100.0, (100.0 * realized / target) if target else 0.0)
    if color is None:
        color = "#2E7D32" if pct >= 80 else ("#F9A825" if pct >= 50 else "#C62828")
    val = f"{realized:g}/{target:g}"
    return (
        f'<div style="margin-bottom:10px">'
        f'<div style="display:flex;justify-content:space-between;font-size:12.5px;'
        f'margin-bottom:3px"><span>{label}</span><strong>{val} ({pct:.0f}%)</strong></div>'
        f'<div style="background:#EEF2F7;border-radius:99px;height:8px">'
        f'<div style="background:{color};border-radius:99px;height:8px;width:{pct:.0f}%">'
        f'</div></div></div>'
    )


def empty_state(emoji: str, titulo: str, texto: str, cta_label: str = "", cta_page: str = ""):
    """Estado vazio que ENSINA (blueprint: novato opera sozinho). Renderiza."""
    st.markdown(
        f'<div style="text-align:center;padding:36px 20px;background:#F8FAFF;'
        f'border:1px dashed #CBD5E1;border-radius:14px;margin:10px 0">'
        f'<div style="font-size:34px;margin-bottom:8px">{emoji}</div>'
        f'<div style="font-size:16px;font-weight:700;margin-bottom:6px">{titulo}</div>'
        f'<div style="font-size:13px;color:#64748B">{texto}</div></div>',
        unsafe_allow_html=True,
    )
    if cta_label and cta_page:
        if st.button(cta_label, type="primary"):
            st.switch_page(cta_page)
