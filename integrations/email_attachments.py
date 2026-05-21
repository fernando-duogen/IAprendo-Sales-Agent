"""
Email Attachments - Anexos sticky por usuario para emails outbound.

Cada usuario tem uma lista de PDFs cadastrados. Os que estao ativos
(enabled=True) sao automaticamente anexados nos emails que ele enviar.
Override por mensagem eh feito via approval_queue.metadata.attachment_urls.

Persistencia: mesma estrategia da assinatura (espelho de email_signature.py):
- Marker no `content` de conversation_memory para nao violar CHECK do scope:
    [EMAIL_ATTACHMENTS:<username>]{json}
- scope='global', scope_id=NULL
- Lista JSON: [{id, name, url, size_bytes, uploaded_at, enabled}]

Arquivos PDF ficam no Supabase Storage (db.upload_attachment).

API:
    from integrations.email_attachments import email_attachments

    # Adicionar (apos upload pro storage)
    att_id = email_attachments.add_attachment(
        name="Apresentacao.pdf", url="https://...", size_bytes=1234567,
    )

    # Listar (do usuario ativo)
    items = email_attachments.list_attachments()

    # Toggle / Remover
    email_attachments.toggle_attachment(att_id, enabled=False)
    email_attachments.remove_attachment(att_id, also_delete_file=True)

    # Pra envio (so os ativos)
    actives = email_attachments.get_active_attachments(username="fernando")
    # -> [{"name": ..., "url": ...}, ...] pronto para Brevo
"""
from __future__ import annotations

import json
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from utils.logger import logger


MARKER_PREFIX = "[EMAIL_ATTACHMENTS:"


def _resolve_active_username() -> Optional[str]:
    """Resolve sender ativo (dashboard logado ou IAlex thread). None = fallback."""
    try:
        from utils.sender_profile import get_active_sender_username
        return get_active_sender_username()
    except Exception:
        return None


class EmailAttachments:
    """Gerenciador de anexos sticky por usuario."""

    TABLE = "conversation_memory"

    @staticmethod
    def _marker(username: str) -> str:
        return f"{MARKER_PREFIX}{username}]"

    def _find_row(self, username: str) -> Optional[Dict[str, Any]]:
        try:
            r = (
                db.client.table(self.TABLE)
                .select("*")
                .eq("scope", "global")
                .ilike("content", f"{self._marker(username)}%")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return (r.data or [None])[0]
        except Exception:
            return None

    def _parse_list(self, row: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not row:
            return []
        try:
            content = row.get("content", "")
            if "]" not in content:
                return []
            payload = content.split("]", 1)[1].strip()
            data = json.loads(payload)
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

    def _save_list(self, username: str, items: List[Dict[str, Any]]) -> bool:
        marker = self._marker(username)
        payload = marker + json.dumps(items, ensure_ascii=False)
        try:
            # Remove versao anterior do mesmo marker
            (
                db.client.table(self.TABLE)
                .delete()
                .eq("scope", "global")
                .ilike("content", f"{marker}%")
                .execute()
            )
            # Insere nova
            db.client.table(self.TABLE).insert({
                "scope": "global",
                "scope_id": None,
                "category": "fact",
                "content": payload[:8000],  # limite generoso (vai caber muitos items)
                "importance": 7,
                "source": "ialex",
            }).execute()
            logger.info(
                "Email attachments salvo",
                extra={"username": username, "count": len(items)},
            )
            return True
        except Exception as e:
            logger.error(
                "Erro ao salvar email attachments",
                extra={
                    "username": username,
                    "items_count": len(items),
                    "error_type": type(e).__name__,
                    "error_msg": str(e)[:300],
                },
                exc_info=True,
            )
            return False

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def list_attachments(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lista todos os anexos cadastrados pelo usuario (ativos + inativos)."""
        u = username or _resolve_active_username()
        if not u:
            return []
        return self._parse_list(self._find_row(u))

    def get_active_attachments(
        self, username: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Lista so os anexos ATIVOS, no formato pronto pra Brevo: [{name, url}]."""
        items = self.list_attachments(username=username)
        return [
            {"name": it.get("name", "anexo.pdf"), "url": it.get("url", "")}
            for it in items
            if it.get("enabled", True) and it.get("url")
        ]

    def add_attachment(
        self,
        name: str,
        url: str,
        size_bytes: int = 0,
        storage_path: str = "",
        username: Optional[str] = None,
        enabled: bool = True,
    ) -> Optional[str]:
        """Adiciona anexo a lista do usuario. Retorna o id do anexo (ou None)."""
        u = username or _resolve_active_username()
        if not u:
            return None
        items = self.list_attachments(username=u)
        new_id = str(_uuid.uuid4())
        items.append({
            "id": new_id,
            "name": name,
            "url": url,
            "size_bytes": int(size_bytes),
            "storage_path": storage_path,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "enabled": bool(enabled),
        })
        if self._save_list(u, items):
            return new_id
        return None

    def remove_attachment(
        self,
        attachment_id: str,
        username: Optional[str] = None,
        also_delete_file: bool = True,
    ) -> bool:
        """Remove anexo da lista. Se also_delete_file, tenta apagar do Storage."""
        u = username or _resolve_active_username()
        if not u:
            return False
        items = self.list_attachments(username=u)
        kept = [it for it in items if it.get("id") != attachment_id]
        if len(kept) == len(items):
            return False  # nao achou
        removed = next((it for it in items if it.get("id") == attachment_id), None)
        ok = self._save_list(u, kept)
        if ok and also_delete_file and removed:
            sp = removed.get("storage_path") or ""
            if sp:
                try:
                    db.remove_attachment(sp)
                except Exception:
                    pass
        return ok

    def toggle_attachment(
        self,
        attachment_id: str,
        enabled: bool,
        username: Optional[str] = None,
    ) -> bool:
        """Liga/desliga um anexo (sem deletar)."""
        u = username or _resolve_active_username()
        if not u:
            return False
        items = self.list_attachments(username=u)
        changed = False
        for it in items:
            if it.get("id") == attachment_id:
                it["enabled"] = bool(enabled)
                changed = True
                break
        if not changed:
            return False
        return self._save_list(u, items)


email_attachments = EmailAttachments()
