"""IAprendo Sales Agent v2 — entrypoint com navegacao do redesign.

st.navigation monta a sidebar do mockup (grupos Vender/Acompanhar/Sistema,
titulos e icones novos) SEM renomear os arquivos das paginas — o conteudo de
cada fase substitui o interior aos poucos (F3+). Auth roda AQUI, uma unica vez,
para todas as paginas.

Rodar: streamlit run dashboard/main.py
"""
import os
import sys
from pathlib import Path

import streamlit as st

# === Streamlit Cloud: copiar secrets para os.environ ANTES de tudo ===
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ[_k] = _v
except Exception:
    pass

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="IAprendo Sales",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================================
# AUTH CENTRAL (uma vez, para todas as paginas)
# =========================================================================
import yaml
from dashboard._auth import ensure_auth, AUTH_PATH as _AUTH_PATH

_auth = ensure_auth(render_form=True)
authenticator = _auth["authenticator"]
_auth_config = _auth["config"]
_current_user = _auth["user"]

# Compartilhar com as paginas (app.py/Hoje usa) + flag pro _auth_gate nao
# duplicar o CookieManager no mesmo run (st.navigation roda main+pagina juntos)
st.session_state["_v2_current_user"] = _current_user
st.session_state["_v2_auth_done"] = True

with st.sidebar:
    st.markdown(
        f'<div style="padding:10px 8px;border-bottom:1px solid #EEF2F7;margin-bottom:4px">'
        f'<div style="font-size:10.5px;color:#94A3B8;text-transform:uppercase;letter-spacing:0.6px">Logado como</div>'
        f'<div style="font-weight:600;color:#1A202C;font-size:13.5px">{_current_user.get("name", "?")}</div>'
        f'<div style="font-size:11.5px;color:#94A3B8">{_current_user.get("role", "")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    authenticator.logout("Sair", location="sidebar")
    with st.expander("Trocar senha", icon=":material/lock_reset:"):
        try:
            if authenticator.reset_password(
                st.session_state.get("username"), location="main"
            ):
                with _AUTH_PATH.open("w", encoding="utf-8") as _f:
                    yaml.safe_dump(_auth_config, _f, allow_unicode=True, sort_keys=False)
                st.success("Senha atualizada. Use no proximo login.")
        except Exception as _e:
            st.error(f"Erro ao trocar senha: {_e}")

# =========================================================================
# NAVEGACAO v2 (sidebar do mockup) — titulos/icones aqui; arquivos intactos
# =========================================================================
_PG = "dashboard/pages"

pages = {
    "": [
        st.Page("app.py", title="Hoje", icon="🏠", url_path="hoje", default=True),
        st.Page(f"pages/0_💬_Chat_IAlex.py", title="IAlex", icon="🤖", url_path="ialex"),
    ],
    "Vender": [
        st.Page(f"pages/5_📊_Pipeline.py", title="Prospectar", icon="🔍", url_path="prospectar"),
        st.Page(f"pages/2_🏫_Escolas.py", title="Escolas", icon="🏫", url_path="escolas"),
        st.Page(f"pages/6_✉️_Comunicacao.py", title="Mensagens", icon="✉️", url_path="mensagens"),
        st.Page(f"pages/4_💼_Negocios.py", title="Negocios", icon="💼", url_path="negocios"),
    ],
    "Acompanhar": [
        st.Page(f"pages/8_📈_Analytics.py", title="Resultados", icon="📊", url_path="resultados"),
    ],
    "Sistema": [
        st.Page(f"pages/9_⚙️_Configuracoes.py", title="Ajustes", icon="⚙️", url_path="ajustes"),
        st.Page(f"pages/10_📖_Manual.py", title="Ajuda", icon="❓", url_path="ajuda"),
    ],
    "Base (em migracao)": [
        # Importar foi ABSORVIDO por Prospectar > Buscar no Brasil (rodada 1)
        st.Page(f"pages/3_👥_Contatos.py", title="Contatos", icon="👥", url_path="contatos"),
        st.Page(f"pages/4_🗺️_Mapa.py", title="Mapa", icon="🗺️", url_path="mapa"),
        st.Page(f"pages/7_🎯_Inteligencia.py", title="Inteligencia", icon="🎯", url_path="inteligencia"),
    ],
}

pg = st.navigation(pages, position="sidebar", expanded=True)
pg.run()
