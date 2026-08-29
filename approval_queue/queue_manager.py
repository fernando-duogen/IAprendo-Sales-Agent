"""QueueManager - Gerencia a fila de aprovacao humana."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from database.supabase_client import db
from utils.logger import logger


class QueueManager:
    def get_pending(self, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            return db.get_pending_approvals(limit=limit)
        except Exception as e:
            logger.error("Erro ao buscar pendentes", extra={"error": str(e)})
            return []

    def approve(
        self,
        queue_id: str,
        edited_subject: str = None,
        edited_body: str = None,
        scheduled_send_at: str = None,
        send_as_username: str = None,
        attachment_urls: list = None,
        error_out: list = None,
    ) -> bool:
        """Aprova mensagem. Pode editar, agendar envio e/ou definir remetente/anexos.

        error_out: lista opcional que recebe o MOTIVO da falha (a tela mostrava
        so "Falha ao aprovar." sem dizer nada).
        """
        return db.approve_message(
            queue_id, edited_subject, edited_body, scheduled_send_at,
            send_as_username=send_as_username,
            attachment_urls=attachment_urls,
            error_out=error_out,
        )

    def reject(self, queue_id: str, reason: str = "") -> bool:
        """Rejeita mensagem com motivo opcional."""
        return db.reject_message(queue_id, reason)

    def get_stats(self) -> Dict[str, int]:
        try:
            result = db.client.table("approval_queue").select("status").execute()
            counts: Dict[str, int] = {}
            for row in result.data:
                s = row.get("status", "unknown")
                counts[s] = counts.get(s, 0) + 1
            return counts
        except Exception as e:
            logger.error("Erro ao buscar stats", extra={"error": str(e)})
            return {}

    def get_approved_not_sent(self, older_than_hours: int = 0) -> List[Dict[str, Any]]:
        """Retorna emails aprovados que ainda nao foram enviados.

        Args:
            older_than_hours: filtra aprovados ha mais de X horas.
                0 = todos os aprovados nao enviados.

        Returns:
            Lista de dicts com dados do email + escola + contato.
        """
        try:
            q = db.client.table("approval_queue").select(
                "id, company_id, contact_id, subject, status, created_at, approved_at, scheduled_send_at, "
                "companies(name, city, state), contacts(full_name, email)"
            ).eq("status", "approved")

            if older_than_hours > 0:
                cutoff = (datetime.now(timezone.utc) - timedelta(hours=older_than_hours)).isoformat()
                q = q.lt("approved_at", cutoff)

            r = q.order("approved_at", desc=False).limit(50).execute()
            return r.data or []
        except Exception as e:
            logger.debug(f"get_approved_not_sent failed: {e}")
            return []

    def get_pending_older_than(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Retorna emails pendentes de aprovacao ha mais de X horas."""
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
            r = db.client.table("approval_queue").select(
                "id, company_id, subject, status, created_at, "
                "companies(name, city, state)"
            ).eq("status", "pending").lt("created_at", cutoff).order("created_at").limit(50).execute()
            return r.data or []
        except Exception as e:
            logger.debug(f"get_pending_older_than failed: {e}")
            return []

    def get_by_id(self, queue_id: str) -> Optional[Dict[str, Any]]:
        try:
            q = db.client.table("approval_queue").select(
                "*, companies(name,city,state,qualification_score,qualification_reasoning),"
                "contacts(full_name,email,role)"
            ).eq("id", queue_id).single().execute()
            return q.data
        except Exception as e:
            logger.error("Erro ao buscar item", extra={"queue_id": queue_id, "error": str(e)})
            return None


queue_manager = QueueManager()