"""_auth - Autenticacao compartilhada (streamlit-authenticator) com re-login
automatico pelo cookie ("manter logado").

PROBLEMA que isto resolve: o re-login pelo cookie so rodava no app.py. As paginas
so olhavam st.session_state -> em F5/reabrir navegador (session_state zera), o
cookie nao era relido e o app pedia senha de novo.

SOLUCAO (padrao documentado do streamlit-authenticator p/ multipage): chamar
`authenticator.login(location="unrendered")` em TODA entrada (home e paginas).
Isso le o cookie e repopula a sessao SEM renderizar formulario (re-login silencioso).

Uso:
    # home (app.py): renderiza o form quando precisar
    from dashboard._auth import ensure_auth
    auth = ensure_auth(render_form=True)
    authenticator, _auth_config, _current_user = auth["authenticator"], auth["config"], auth["user"]

    # paginas: so re-loga pelo cookie e bloqueia se nao autenticado
    from dashboard._auth_gate import require_auth
    require_auth()
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import yaml
import streamlit_authenticator as stauth

AUTH_PATH = Path(__file__).parent.parent / "config" / "users.yaml"


def _to_mutable_dict(obj: Any) -> Any:
    """Deep-copy de st.secrets (Mapping imutavel) para dict nativo mutavel.

    streamlit_authenticator muta credentials['usernames'], o que falha em
    Secrets read-only. Retorna estrutura 100% nativa preservando os valores.
    """
    if hasattr(obj, "items") and not isinstance(obj, dict):
        return {k: _to_mutable_dict(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: _to_mutable_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_mutable_dict(x) for x in obj]
    return obj


def load_auth_config() -> Optional[Dict[str, Any]]:
    """Carrega a config de auth: users.yaml (local) ou st.secrets['auth'] (Cloud)."""
    try:
        if AUTH_PATH.exists():
            with AUTH_PATH.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        if "auth" in st.secrets:
            return _to_mutable_dict(st.secrets["auth"])
    except Exception as e:
        st.error(f"Falha ao carregar config de autenticacao: {e}")
        st.stop()
    return None


def build_authenticator(config: Dict[str, Any]) -> stauth.Authenticate:
    """Cria o Authenticate a partir da config (1 por run; barato)."""
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )


def ensure_auth(render_form: bool = False) -> Dict[str, Any]:
    """Garante autenticacao, re-logando pelo COOKIE primeiro (manter logado).

    Fluxo:
      1. login(location="unrendered") -> le o cookie e repopula a sessao sem UI.
      2. Se autenticado -> retorna {authenticator, config, username, user}.
      3. Se nao: render_form=True (home) renderiza o form; render_form=False
         (paginas) mostra aviso + link e para.

    Tolerante a falha do cookie (try/except) — nunca trava o acesso, so cai no login.
    """
    config = load_auth_config()
    if not config:
        st.error(
            "Config de autenticacao nao encontrada. Crie `config/users.yaml` "
            "(use `config/users.yaml.example`) ou configure `st.secrets['auth']`."
        )
        st.stop()

    authenticator = build_authenticator(config)

    # 1) Re-login SILENCIOSO pelo cookie (o coracao do "manter logado").
    try:
        authenticator.login(location="unrendered")
    except Exception:
        pass  # cookie ausente/invalido -> segue pro fluxo normal de login

    status = st.session_state.get("authentication_status")

    # 2) Home: renderizar o formulario de login quando ainda nao autenticado.
    if status is not True and render_form:
        try:
            authenticator.login(location="main")
        except Exception as e:
            st.error(f"Erro no login: {e}")
            st.stop()
        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("Usuario ou senha incorretos")
            st.stop()
        if status is None:
            st.warning("Faca login para acessar o IAprendo")
            st.info(
                "**Primeira vez?** Senhas iniciais foram entregues pelo administrador. "
                "Recomendamos trocar pela sidebar apos o login."
            )
            st.stop()

    # 3) Paginas (sem form): bloquear se nao autenticado.
    if status is not True:
        st.warning("Voce precisa fazer login para acessar esta pagina.")
        try:
            st.page_link("app.py", label="Ir para o login", icon=":material/login:")
        except Exception:
            st.markdown("[Ir para o login](/)")
        st.stop()

    # Autenticado
    username = st.session_state.get("username", "")
    user = config.get("credentials", {}).get("usernames", {}).get(username, {})
    return {
        "authenticator": authenticator,
        "config": config,
        "username": username,
        "user": user,
    }
