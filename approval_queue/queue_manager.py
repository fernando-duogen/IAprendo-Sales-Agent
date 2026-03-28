"""QueueManager - Gerencia a fila de aprovacao humana."""
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

    def approve(self, queue_id: str, edited_subject: str = None, edited_body: str = None) -> bool:
        """Aprova mensagem. Pode editar antes de aprovar."""
        return db.approve_message(queue_id, edited_subject, edited_body)

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