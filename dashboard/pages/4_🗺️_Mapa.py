"""Pagina 4 - Mapa (CASCA v2).

O mapa foi absorvido pela pagina Escolas (secao 🏫 Lista → alternador
"Ver como Tabela/Mapa", em dashboard/helpers/mapa_view.py) na rodada 5 do
redesign. Fora do menu desde entao; arquivo mantido para historico/URL antiga.

Ago/2026 — auditoria: esta pagina era a UNICA das 4 orfas que nao tinha virado
casca. Continuava com ~1000 linhas do codigo antigo, incluindo o botao de
Perplexity via subprocess + `venv\\Scripts\\python.exe` (caminho Windows, quebra
na VM Linux) e o gate de `playwright` — que foi removido do requirements quando
o Perplexity-browser foi aposentado. Ou seja: codigo morto e QUEBRADO,
inalcancavel pelo menu. Padronizado como as demais cascas (Importar/Contatos/
Inteligencia). O conteudo original esta no historico do git.
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
    "O mapa agora vive em 🏫 <strong>Escolas</strong> → secao <strong>Lista</strong>, "
    "no alternador <em>Ver como Tabela / Mapa</em> (com os mesmos filtros da lista). "
    "A geocodificacao em lote esta la tambem.",
    "info",
)

if st.button("Ir para Escolas", type="primary"):
    st.switch_page("pages/2_🏫_Escolas.py")
