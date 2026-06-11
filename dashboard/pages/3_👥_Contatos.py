"""Pagina 3 - Contatos (CASCA v2).

O conteudo foi absorvido pela pagina Escolas (secao 👥 Pessoas) na rodada 5
do redesign. Este arquivo permanece apenas para historico/F7 — fora do menu.
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
    "Esta funcao agora vive em 🏫 Escolas → 👥 Pessoas.", "info"
)

from dashboard.helpers.contatos_view import render_contatos

render_contatos()
