"""Pagina 7 - Inteligencia (CASCA v2).

Radar/Explorador foram absorvidos pela pagina Escolas (secao 🔬 Inteligencia);
o Ranking P1/P2/P3 vive em Prospectar → Recomendadas. Fora do menu desde a
rodada 5; arquivo mantido para historico/F7.
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import apply_theme_no_config, alert_banner

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

alert_banner(
    "Esta funcao agora vive em 🏫 Escolas → 🔬 Inteligencia "
    "(ranking de leads: 🔍 Prospectar → ⭐ Recomendadas).", "info"
)

from dashboard.helpers.inteligencia_view import render_inteligencia

render_inteligencia()
