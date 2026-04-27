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
_USERS_YAML_PATH = Path(__file__).parent.parent / "config" / "users.yaml"

# Thread-local para o IAlex setar o sender ativo durante o processamento
# de uma mensagem (cada request roda em sua propria thread no Flask).
_THREAD_LOCAL = threading.local()


def _load_profiles() -> Dict[str, Dict[str, Any]]:
    """Carrega config/users.yaml e retorna mapa username -> perfil.

    Cache em memoria — recarregado apenas se o arquivo for tocado entre
    chamadas (mtime). Em caso de falha (arquivo ausente ou invalido)
    retorna mapa vazio e loga warning.
    """
    global _PROFILES
    if _PROFILES is not None:
        return _PROFILES

    try:
        if not _USERS_YAML_PATH.exists():
            logger.warning(
                "config/users.yaml nao encontrado — fallback para settings.YOUR_*",
                extra={"path": str(_USERS_YAML_PATH)},
            )
            _PROFILES = {}
            return _PROFILES

        with _USERS_YAML_PATH.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        usernames = data.get("credentials", {}).get("usernames", {})
        profiles: Dict[str, Dict[str, Any]] = {}
        for username, info in usernames.items():
            profiles[username] = {
                "username": username,
                "name": info.get("name", ""),
                "email": info.get("email", ""),
                "phone": info.get("phone", ""),
                "role": info.get("role", ""),
                "is_admin": bool(info.get("is_admin", False)),
                "whatsapp_numbers": [
                    "".join(c for c in str(n) if c.isdigit())
                    for n in (info.get("whatsapp_numbers") or [])
                ],
            }
        _PROFILES = profiles
        logger.info(f"Sender profiles carregados: {list(profiles.keys())}")
        return _PROFILES
    except Exception as e:
        logger.error(f"Erro ao carregar users.yaml: {e}")
        _PROFILES = {}
        return _PROFILES


def reload_profiles() -> None:
    """Forca reload do users.yaml (apos edicao manual)."""
    global _PROFILES
    _PROFILES = None
    _load_profiles()


# ---------------------------------------------------------------------------
# Default fallback (Fernando, .env)
# ---------------------------------------------------------------------------
def _fallback_profile() -> Dict[str, Any]:
    """Retorna o perfil default do .env (compat com sistema antigo)."""
    return {
        "username": "default",
        "name": os.getenv("YOUR_NAME", "Fernando"),
        "email": os.getenv("YOUR_EMAIL", ""),
        "phone": os.getenv("YOUR_PHONE", ""),
        "role": "",
        "is_admin": False,  # default fallback nao tem privilegio
        "whatsapp_numbers": [],
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
