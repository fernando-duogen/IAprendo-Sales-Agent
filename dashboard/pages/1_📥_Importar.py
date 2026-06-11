"""Pagina Importar Escolas — CASCA de compatibilidade (redesign v2).

O conteudo foi extraido para dashboard/helpers/importar_mec.py e agora vive na
tab "Buscar no Brasil" do Prospectar (mockup prospectar.html). Esta pagina
mantem a URL antiga funcionando fora do menu ate o cutover.
"""
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import apply_theme_no_config, breadcrumb, alert_banner

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

breadcrumb(["IAprendo", "Importar Escolas"])
st.markdown("# Importar Escolas")
alert_banner(
    "Esta funcao agora vive em <strong>🔍 Prospectar → Buscar no Brasil</strong>. "
    "O conteudo abaixo continua funcionando igual.",
    "info",
)

from dashboard.helpers.importar_mec import render_buscar_brasil
render_buscar_brasil(embedded=False)
