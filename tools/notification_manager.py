"""
Notification Manager - Sistema simples de notificacoes.

Armazena notificacoes em arquivo JSON para exibir no dashboard Streamlit.
Nao requer banco de dados - usa arquivo local em logs/notifications.json.

Usage:
    from tools.notification_manager import notification_manager

    # Adicionar notificacao
    notification_manager.add_notification(
        title="Novo lead qualificado",
        message="Escola ABC recebeu score 92",
        type="success",
        link="/leads?id=abc-123"
    )

    # Listar notificacoes
    notifications = notification_manager.get_notifications(limit=10)

    # Contar nao lidas
    count = notification_manager.get_unread_count()

    # Marcar como lida
    notification_manager.mark_read("notification-uuid")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import uuid
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import logger


# ============================================================================
# CONSTANTS
# ============================================================================

PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTIFICATIONS_FILE: str = os.path.join(PROJECT_ROOT, "logs", "notifications.json")
MAX_STORED: int = 500  # maximo de notificacoes armazenadas

VALID_TYPES: set = {"info", "success", "warning", "error"}


# ============================================================================
# NOTIFICATION MANAGER
# ============================================================================

class NotificationManager:
    """
    Gerencia notificacoes em arquivo JSON local.

    Thread-safe via lock para acesso concorrente (Streamlit + workers).
    """

    def __init__(self, filepath: Optional[str] = None) -> None:
        """
        Inicializa o manager.

        Args:
            filepath: Caminho para o arquivo JSON. Default: logs/notifications.json
        """
        self._filepath: str = filepath or NOTIFICATIONS_FILE
        self._lock: threading.Lock = threading.Lock()
        self._ensure_file()

    # ========================================================================
    # PUBLIC METHODS
    # ========================================================================

    def add_notification(
        self,
        title: str,
        message: str,
        type: str = "info",
        link: Optional[str] = None,
    ) -> str:
        """
        Adiciona uma notificacao.

        Args:
            title: Titulo curto da notificacao.
            message: Mensagem descritiva.
            type: Tipo - info, success, warning, error.
            link: Link opcional (rota do dashboard ou URL).

        Returns:
            ID da notificacao criada.
        """
        if type not in VALID_TYPES:
            type = "info"

        notification_id: str = str(uuid.uuid4())

        notification: Dict[str, Any] = {
            "id": notification_id,
            "title": title,
            "message": message,
            "type": type,
            "link": link,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "read": False,
        }

        with self._lock:
            notifications = self._load()
            notifications.insert(0, notification)

            # Limitar tamanho
            if len(notifications) > MAX_STORED:
                notifications = notifications[:MAX_STORED]

            self._save(notifications)

        logger.info(
            f"Notificacao criada: {title}",
            extra={"notification_id": notification_id, "type": type},
        )
        return notification_id

    def get_notifications(
        self,
        limit: int = 20,
        unread_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Retorna notificacoes ordenadas por data (mais recentes primeiro).

        Args:
            limit: Maximo de notificacoes retornadas.
            unread_only: Se True, retorna apenas nao lidas.

        Returns:
            Lista de dicts de notificacao.
        """
        with self._lock:
            notifications = self._load()

        if unread_only:
            notifications = [n for n in notifications if not n.get("read")]

        return notifications[:limit]

    def mark_read(self, notification_id: str) -> bool:
        """
        Marca uma notificacao como lida.

        Args:
            notification_id: ID da notificacao.

        Returns:
            True se encontrou e marcou, False se nao encontrou.
        """
        with self._lock:
            notifications = self._load()
            found: bool = False

            for n in notifications:
                if n.get("id") == notification_id:
                    n["read"] = True
                    found = True
                    break

            if found:
                self._save(notifications)

        return found

    def mark_all_read(self) -> int:
        """
        Marca todas as notificacoes como lidas.

        Returns:
            Quantidade de notificacoes marcadas.
        """
        count: int = 0

        with self._lock:
            notifications = self._load()

            for n in notifications:
                if not n.get("read"):
                    n["read"] = True
                    count += 1

            if count > 0:
                self._save(notifications)

        return count

    def get_unread_count(self) -> int:
        """
        Conta notificacoes nao lidas.

        Returns:
            Numero de notificacoes com read=False.
        """
        with self._lock:
            notifications = self._load()

        return sum(1 for n in notifications if not n.get("read"))

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _ensure_file(self) -> None:
        """Cria arquivo JSON se nao existir."""
        try:
            directory = os.path.dirname(self._filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            if not os.path.exists(self._filepath):
                with open(self._filepath, "w", encoding="utf-8") as f:
                    json.dump([], f)
        except Exception as e:
            logger.error(f"Erro ao criar arquivo de notificacoes: {e}")

    def _load(self) -> List[Dict[str, Any]]:
        """Carrega notificacoes do arquivo JSON."""
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        except Exception as e:
            logger.error(f"Erro ao ler notificacoes: {e}")
        return []

    def _save(self, notifications: List[Dict[str, Any]]) -> None:
        """Salva notificacoes no arquivo JSON."""
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(notifications, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar notificacoes: {e}")


# ============================================================================
# SINGLETON
# ============================================================================

notification_manager = NotificationManager()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Notification Manager - Teste ===\n")

    # Criar notificacoes de teste
    nid1 = notification_manager.add_notification(
        title="Lead qualificado",
        message="Escola Modelo recebeu score 92",
        type="success",
    )
    nid2 = notification_manager.add_notification(
        title="Email bounced",
        message="Email para Colegio ABC retornou",
        type="error",
        link="/leads?id=test",
    )
    nid3 = notification_manager.add_notification(
        title="Pipeline concluido",
        message="40 leads processados hoje",
        type="info",
    )

    print(f"Nao lidas: {notification_manager.get_unread_count()}")

    # Marcar uma como lida
    notification_manager.mark_read(nid1)
    print(f"Apos marcar 1: {notification_manager.get_unread_count()}")

    # Listar
    for n in notification_manager.get_notifications(limit=5):
        status = "lida" if n["read"] else "NOVA"
        print(f"  [{status}] [{n['type']}] {n['title']}: {n['message']}")
