"""Resolver de nome de rede educacional com 2 camadas:

1. Override manual (tabela rede_overrides, populada via UI)
2. Derivacao heuristica (_derivar_nome_rede em brain.py)

Usar resolver_nome_rede() em qualquer lugar que precise exibir o nome
da rede — e o ponto unico de entrada.
"""
from typing import Any, Dict, List, Optional

from utils.logger import logger


def _get_override_cached(cnpj: str) -> Optional[str]:
    """Busca override no banco. Falha silenciosa se tabela nao existe."""
    if not cnpj:
        return None
    try:
        from database.supabase_client import db
        r = db.client.table("rede_overrides").select("nome_oficial").eq(
            "cnpj_mantenedora", cnpj
        ).limit(1).execute()
        if r.data and len(r.data) > 0:
            return r.data[0].get("nome_oficial")
    except Exception as e:
        # Tabela pode nao existir (migration 014 nao aplicada)
        err_str = str(e)
        if "rede_overrides" in err_str or "42P01" in err_str:
            logger.debug("rede_overrides table nao existe (migration 014 pendente)")
        else:
            logger.debug(f"rede override lookup erro: {err_str[:100]}")
    return None


def resolver_nome_rede(cnpj: str, escolas: List[Dict[str, Any]]) -> str:
    """Resolve o nome de uma rede a partir do CNPJ + escolas.

    Ordem de precedencia:
    1. Override manual em rede_overrides (se existe)
    2. Derivacao heuristica de _derivar_nome_rede (brain.py)

    Args:
        cnpj: cnpj_mantenedora da rede.
        escolas: lista de dicts de escolas da rede (usada no fallback).

    Returns:
        Nome da rede pra exibir no dashboard.
    """
    # Camada 1: Override
    override = _get_override_cached(cnpj)
    if override:
        return override

    # Camada 2: Heuristica
    try:
        from agent.brain import _derivar_nome_rede
        return _derivar_nome_rede(escolas) or f"Rede {cnpj[:8] if cnpj else '?'}"
    except Exception as e:
        logger.warning(f"_derivar_nome_rede falhou: {e}")
        return f"Rede {cnpj[:8] if cnpj else '?'}"


def set_rede_override(cnpj: str, nome_oficial: str) -> bool:
    """Salva ou atualiza override manual de nome de rede.

    Returns:
        True em caso de sucesso, False em erro (ex: tabela nao existe).
    """
    if not cnpj or not nome_oficial or len(nome_oficial.strip()) < 2:
        return False
    try:
        from database.supabase_client import db
        from datetime import datetime, timezone
        payload = {
            "cnpj_mantenedora": cnpj,
            "nome_oficial": nome_oficial.strip(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Upsert
        db.client.table("rede_overrides").upsert(payload, on_conflict="cnpj_mantenedora").execute()
        logger.info("Rede override salvo", extra={"cnpj": cnpj, "nome": nome_oficial})
        return True
    except Exception as e:
        logger.error(f"set_rede_override falhou: {e}")
        return False


def has_rede_overrides_table() -> bool:
    """Verifica se a tabela rede_overrides existe (migration 014 aplicada).
    Retorna False se nao existir — chamadores mostram banner apropriado.
    """
    try:
        from database.supabase_client import db
        db.client.table("rede_overrides").select("cnpj_mantenedora").limit(1).execute()
        return True
    except Exception as e:
        err_str = str(e)
        if "rede_overrides" in err_str or "42P01" in err_str:
            return False
        # Outro erro — assume que existe mas deu outro problema
        return True
