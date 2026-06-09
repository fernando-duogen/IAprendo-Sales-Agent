"""
_auth_gate - Gate de autenticacao para paginas individuais do Streamlit.

O login real acontece em `dashboard/app.py` (Home). Este modulo e importado
no topo de cada pagina em `dashboard/pages/` para impedir acesso direto via
URL sem autenticacao.

Usage (no topo de cada pagina, antes de qualquer outro import):
    from dashboard._auth_gate import require_auth
    require_auth()
"""
def require_auth():
    """Garante autenticacao na pagina, RE-LOGANDO pelo cookie primeiro.

    Delega pro `ensure_auth` (dashboard/_auth.py), que chama
    `authenticator.login(location="unrendered")` -> le o cookie e repopula a
    sessao SEM formulario. Assim, F5 numa pagina ou reabrir o navegador mantem
    o login (antes so olhava session_state, que zera nesses casos -> pedia senha).
    Se nao houver cookie/sessao valida, mostra aviso + link e para a pagina.
    """
    from dashboard._auth import ensure_auth
    ensure_auth(render_form=False)
