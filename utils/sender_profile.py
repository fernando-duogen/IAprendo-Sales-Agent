"""
sender_profile - Identidade do remetente ativo (multi-user).

Resolve qual perfil de remetente esta ativo no contexto atual:
- Dashboard: usuario logado via streamlit-authenticator (st.session_state)
- IAlex: usuario detectado pelo numero do WhatsApp (set_active_sender por thread)
- Fallback: settings.YOUR_NAME / YOUR_EMAIL / YOUR_PHONE (default Fernando)

Cada perfil contem:
- username: id curto (ex: 'fernando', 'lizianne')
- name: nome completo para assinatura
- email: email do remetente (Brevo deve ter validado)
- phone: telefone para assinatura
- role: cargo

Usage:
    from utils.sender_profile import get_active_sender, set_active_sender_for_thread

    # Obter perfil ativo (auto-detecta dashboard ou IAlex ou fallback)
    sender = get_active_sender()
    print(sender['name'], sender['email'])

    # IAlex: setar perfil baseado no numero do WhatsApp
    set_active_sender_for_thread('lizianne')

    # Limpar (fim do request)
    clear_active_sender_for_thread()
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from utils.logger import logger

# ---------------------------------------------------------------------------
# Cache de perfis (carregado do YAML)
# ---------------------------------------------------------------------------
_PROFILES: Optional[Dict[str, Dict[str, Any]]] = None
_PROFILES_MTIME: Optional[float] = None  # mtime do users.yaml quando cacheado
_USERS_YAML_PATH = Path(__file__).parent.parent / "config" / "users.yaml"

# Thread-local para o IAlex setar o sender ativo durante o processamento
# de uma mensagem (cada request roda em sua propria thread no Flask).
_THREAD_LOCAL = threading.local()


def _profiles_from_usernames(usernames: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Constroi o mapa username->perfil a partir do dict 'usernames' — mesma
    estrutura no users.yaml e em st.secrets['auth']['credentials']['usernames']."""
    profiles: Dict[str, Dict[str, Any]] = {}
    for username, info in (usernames or {}).items():
        if not isinstance(info, dict):
            try:
                info = dict(info)  # st.secrets AttrDict -> dict
            except Exception:
                continue
        profiles[username] = {
            "username": username,
            "name": info.get("name", ""),
            # email_sender_name eh usado APENAS pelo brevo_sender (Nome | DUOGEN).
            # Fallback pra `name` se ausente — backward-compatible.
            "email_sender_name": info.get("email_sender_name", info.get("name", "")),
            "email": info.get("email", ""),
            "phone": info.get("phone", ""),
            "role": info.get("role", ""),
            "is_admin": bool(info.get("is_admin", False)),
            # Quem ASSINA os e-mails deste usuario. Vazio = ele mesmo.
            # Ver get_email_identity() — separa "quem opera" de "quem assina".
            "email_identity_from": (info.get("email_identity_from") or "").strip(),
            "whatsapp_numbers": [
                "".join(c for c in str(n) if c.isdigit())
                for n in (info.get("whatsapp_numbers") or [])
            ],
        }
    return profiles


def _usernames_from_secrets() -> Dict[str, Any]:
    """Le os usernames de st.secrets['auth'] (Streamlit Cloud, onde nao ha
    users.yaml). So funciona no contexto do dashboard (Streamlit rodando);
    no IAlex/local o arquivo existe e este caminho nem e chamado."""
    try:
        import streamlit as st  # disponivel so no runtime do dashboard
        auth = st.secrets.get("auth") if hasattr(st.secrets, "get") else st.secrets["auth"]
        if not auth:
            return {}
        creds = auth.get("credentials", {}) or {}
        usernames = creds.get("usernames", {}) or {}
        return {u: dict(info) for u, info in usernames.items()}
    except Exception:
        return {}


def _load_profiles() -> Dict[str, Dict[str, Any]]:
    """Carrega config/users.yaml e retorna mapa username -> perfil.

    Cache em memoria com invalidacao por MTIME: se o users.yaml foi editado
    (ex: adicionar/editar usuario) desde o ultimo load, recarrega automatico —
    sem precisar reiniciar o app. Em caso de falha retorna mapa vazio + warning.
    """
    global _PROFILES, _PROFILES_MTIME

    # Mtime atual do arquivo (None se nao existe)
    try:
        _cur_mtime = _USERS_YAML_PATH.stat().st_mtime if _USERS_YAML_PATH.exists() else None
    except Exception:
        _cur_mtime = None

    # Cache valido SE ja carregado E o arquivo nao mudou desde entao
    if _PROFILES is not None and _cur_mtime == _PROFILES_MTIME:
        return _PROFILES

    try:
        if not _USERS_YAML_PATH.exists():
            # Streamlit Cloud: nao ha users.yaml (gitignored). A auth vem de
            # st.secrets["auth"] — carregar os perfis da MESMA fonte, senao
            # get_active_sender_username() cai em None na nuvem e quebra anexos,
            # assinatura e is_admin por usuario.
            secret_users = _usernames_from_secrets()
            if secret_users:
                _PROFILES = _profiles_from_usernames(secret_users)
                _PROFILES_MTIME = _cur_mtime
                logger.info(f"Sender profiles de st.secrets[auth]: {list(_PROFILES.keys())}")
                return _PROFILES
            logger.warning(
                "config/users.yaml ausente e sem st.secrets[auth] — fallback YOUR_*",
                extra={"path": str(_USERS_YAML_PATH)},
            )
            _PROFILES = {}
            _PROFILES_MTIME = _cur_mtime
            return _PROFILES

        with _USERS_YAML_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        usernames = data.get("credentials", {}).get("usernames", {})
        _PROFILES = _profiles_from_usernames(usernames)
        _PROFILES_MTIME = _cur_mtime
        logger.info(f"Sender profiles carregados: {list(_PROFILES.keys())}")
        return _PROFILES
    except Exception as e:
        logger.error(f"Erro ao carregar users.yaml: {e}")
        _PROFILES = {}
        return _PROFILES


def reload_profiles() -> None:
    """Forca reload do users.yaml (apos edicao manual)."""
    global _PROFILES, _PROFILES_MTIME
    _PROFILES = None
    _PROFILES_MTIME = None
    _load_profiles()


# ---------------------------------------------------------------------------
# Default fallback (Fernando, .env)
# ---------------------------------------------------------------------------
def _fallback_profile() -> Dict[str, Any]:
    """Retorna o perfil default do .env (compat com sistema antigo)."""
    _name = os.getenv("YOUR_NAME", "Fernando")
    return {
        "username": "default",
        "name": _name,
        # email_sender_name: usa BREVO_SENDER_NAME se setado, senao name.
        "email_sender_name": os.getenv("BREVO_SENDER_NAME") or _name,
        "email": os.getenv("YOUR_EMAIL", ""),
        "phone": os.getenv("YOUR_PHONE", ""),
        "role": "",
        "is_admin": False,  # default fallback nao tem privilegio
        "whatsapp_numbers": [],
        "email_identity_from": "",
    }


# ---------------------------------------------------------------------------
# Resolucao do sender ativo
# ---------------------------------------------------------------------------
def get_active_sender() -> Dict[str, Any]:
    """Retorna o perfil de remetente ativo no contexto atual.

    Ordem de resolucao:
    1. Thread-local (IAlex setou explicitamente para este request)
    2. st.session_state.username (dashboard logado via streamlit-authenticator)
    3. Fallback para settings.YOUR_NAME / YOUR_EMAIL (Fernando)
    """
    profiles = _load_profiles()

    # 1) Thread-local (IAlex)
    thread_username = getattr(_THREAD_LOCAL, "username", None)
    if thread_username and thread_username in profiles:
        return profiles[thread_username]

    # 2) Streamlit session state (dashboard)
    try:
        import streamlit as st  # import local — evita problema fora de UI

        session_username = st.session_state.get("username")
        if session_username and session_username in profiles:
            return profiles[session_username]
    except Exception:
        pass  # nao estamos em contexto Streamlit

    # 3) Fallback .env
    return _fallback_profile()


# ---------------------------------------------------------------------------
# Identidade de SAIDA do e-mail (quem assina) — separada de quem OPERA
# ---------------------------------------------------------------------------
# Um usuario pode operar com identidade propria (leads, metas, created_by dele)
# e ainda assim assinar os e-mails como outra pessoa. E o caso do agente
# "vendedor1", que prospecta em nome proprio mas manda e-mail como o Fernando.
#
# Isso NAO e copia de dados: a assinatura e os anexos continuam morando num
# registro so (o do dono da identidade), entao editar a assinatura do Fernando
# muda a de quem herda dele no mesmo instante.
#
# IMPORTANTE: a heranca vale SO para saida de e-mail. get_active_sender_username()
# — que alimenta owner_username/created_by — continua devolvendo quem opera.
def _resolve_identity_username(start: str, profiles: Dict[str, Any]) -> str:
    """Segue a cadeia `email_identity_from` a partir de `start`.

    Defensivo por design: ciclo (a->b->a) ou alvo inexistente fazem o usuario
    assinar como ele mesmo. Identidade errada e pior que heranca perdida.
    """
    seen = set()
    cur = start
    while True:
        if cur not in profiles or cur in seen:
            return start
        seen.add(cur)
        nxt = (profiles[cur].get("email_identity_from") or "").strip()
        if not nxt or nxt == cur or nxt not in profiles:
            return cur
        cur = nxt


def get_email_identity(username: Optional[str] = None) -> Dict[str, Any]:
    """Perfil a usar como REMETENTE (De:, nome/e-mail/telefone no corpo,
    assinatura e anexos).

    Sem argumento, parte do sender ativo. Se o perfil tiver
    `email_identity_from`, devolve o perfil apontado; senao, ele mesmo.
    """
    profiles = _load_profiles()
    if username is None:
        base = get_active_sender()
        start = base.get("username") or ""
    else:
        base = profiles.get(username) or _fallback_profile()
        start = username
    if start not in profiles:
        # fallback .env ou usuario desconhecido: assina como ele mesmo
        return base
    return profiles[_resolve_identity_username(start, profiles)]


def get_email_identity_username(username: Optional[str] = None) -> Optional[str]:
    """Username que indexa assinatura e anexos do e-mail.

    None quando nao ha identidade cadastrada (fallback .env) — mesma semantica
    de get_active_sender_username(), pra preservar o comportamento atual de
    cair na assinatura global legada.
    """
    ident = get_email_identity(username)
    u = ident.get("username")
    return None if (not u or u == "default") else u


def get_profile_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Retorna perfil por username explicitamente."""
    profiles = _load_profiles()
    return profiles.get(username)


def get_profile_by_whatsapp_number(number: str) -> Optional[Dict[str, Any]]:
    """Resolve perfil a partir de um numero de WhatsApp (com ou sem nono digito).

    Compara os ultimos 8 digitos para tolerar variacoes do payload do WhatsApp.
    """
    digits = "".join(c for c in str(number) if c.isdigit())
    if len(digits) < 8:
        return None
    tail = digits[-8:]

    profiles = _load_profiles()
    for username, profile in profiles.items():
        for wa in profile.get("whatsapp_numbers", []):
            if len(wa) >= 8 and wa[-8:] == tail:
                return profile
    return None


def list_profiles() -> List[Dict[str, Any]]:
    """Lista todos os perfis cadastrados (sem expor hash de senha)."""
    return list(_load_profiles().values())


# ---------------------------------------------------------------------------
# Setter para IAlex (thread-local)
# ---------------------------------------------------------------------------
def set_active_sender_for_thread(username: Optional[str]) -> None:
    """IAlex: define o perfil ativo para esta thread (request).

    Chamado pelo webhook_server ao identificar que mensagem veio do
    numero do Fernando ou da Lizianne. Isolada por thread — nao vaza
    entre requests concorrentes.

    Args:
        username: chave do perfil (ex: 'fernando', 'lizianne'). None
            para limpar.
    """
    if username is None:
        clear_active_sender_for_thread()
        return
    _THREAD_LOCAL.username = username


def clear_active_sender_for_thread() -> None:
    """Limpa o sender ativo da thread (chamado ao final do request)."""
    if hasattr(_THREAD_LOCAL, "username"):
        delattr(_THREAD_LOCAL, "username")


def get_active_sender_username() -> Optional[str]:
    """Retorna o username ativo (None se fallback)."""
    profile = get_active_sender()
    if profile.get("username") == "default":
        return None
    return profile.get("username")


def is_admin(username: Optional[str] = None) -> bool:
    """Retorna True se o usuario for super admin (campo is_admin: true no yaml).

    Args:
        username: chave do perfil. Se None, usa o sender ativo.

    Returns:
        True se admin, False senao (inclui usuarios nao cadastrados).
    """
    if username is None:
        profile = get_active_sender()
    else:
        profile = get_profile_by_username(username) or {}
    return bool(profile.get("is_admin", False))
