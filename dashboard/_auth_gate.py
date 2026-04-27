"""
_auth_gate - Gate de autenticacao para paginas individuais do Streamlit.

O login real acontece em `dashboard/app.py` (Home). Este modulo e importado
no topo de cada pagina em `dashboard/pages/` para impedir acesso direto via
URL sem autenticacao.

Usage (no topo de cada pagina, antes de qualquer outro import):
    from dashboard._auth_gate import require_auth
    require_auth()
"""
import streamlit as st


def require_auth():
    """Bloqueia execucao se o usuario nao estiver autenticado.

    Verifica `st.session_state.authentication_status` que e populado pelo
    streamlit-authenticator no app.py (Home). Se False ou None, mostra aviso
    e link para a Home, e para a execucao da pagina.
    """
    if st.session_state.get("authentication_status") is True:
        return  # autenticado, segue normal

    # Bloqueio
    st.warning("Voce precisa fazer login para acessar esta pagina.")
    try:
        st.page_link("app.py", label="Ir para o login", icon=":material/login:")
    except Exception:
        st.markdown("[Ir para o login](/)")
    st.stop()
