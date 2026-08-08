"""Persistencia das conversas do Chat IAlex (operador v1, F4).

Uma linha por thread em `chat_threads` (migration APLICAR-022): upsert atomico
do snapshot {history, blocks} a cada turno. Degrada com elegancia — se a
tabela nao existir (migration nao aplicada), tudo retorna None/False e o chat
segue funcionando so em memoria da sessao.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database.supabase_client import db
from utils.logger import logger


def new_thread_id() -> str:
    return str(uuid.uuid4())


def load_latest_thread(username: str) -> Optional[Tuple[str, List[Dict], Dict[str, Any]]]:
    """Carrega a conversa mais recente do usuario.

    Returns:
        (thread_id, history, blocks) ou None se nao houver/na falha.
    """
    try:
        r = (
            db.client.table("chat_threads")
            .select("thread_id,history,blocks")
            .eq("username", username)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = r.data or []
        if not rows:
            return None
        row = rows[0]
        history = row.get("history") or []
        blocks = row.get("blocks") or {}
        if not isinstance(history, list) or not isinstance(blocks, dict):
            return None
        return str(row["thread_id"]), history, blocks
    except Exception as e:
        logger.debug(f"chat_store.load_latest_thread: {e}")
        return None


def save_thread(
    username: str,
    thread_id: str,
    history: List[Dict],
    blocks: Dict[str, Any],
) -> bool:
    """Upsert do snapshot da conversa (nunca levanta)."""
    try:
        # Titulo = primeira mensagem do usuario (ajuda num futuro seletor)
        title = ""
        for msg in history:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                title = msg["content"][:80]
                break
        db.client.table("chat_threads").upsert(
            {
                "username": username,
                "thread_id": thread_id,
                "title": title,
                "history": history,
                "blocks": blocks,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="username,thread_id",
        ).execute()
        return True
    except Exception as e:
        logger.debug(f"chat_store.save_thread: {e}")
        return False
