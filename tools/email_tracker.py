"""
EmailTracker - Tracking de abertura/clique/resposta de emails via Brevo.

Funcionalidades:
- Gera tracking IDs unicos para cada email enviado
- Consulta eventos via Brevo API (opened, clicked, delivered, bounced)
- Atualiza approval_queue com timestamps de eventos
- Registra interacoes correspondentes
- Fornece estatisticas agregadas para dashboard

Usage:
    from tools.email_tracker import email_tracker

    # Gerar tracking ID
    tracking_id = email_tracker.generate_tracking_id()

    # Sincronizar eventos do Brevo
    summary = email_tracker.sync_tracking_events()

    # Estatisticas dos ultimos 30 dias
    stats = email_tracker.get_tracking_stats(days=30)

    # Timeline de uma empresa
    timeline = email_tracker.get_email_timeline(company_id="abc-123")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


class EmailTracker:
    """Rastreia eventos de email (open, click, bounce, reply) via Brevo API."""

    BASE_URL = "https://api.brevo.com/v3"

    def __init__(self) -> None:
        """Inicializa tracker com API key do Brevo."""
        self.api_key: str = (
            getattr(settings, "BREVO_API_KEY", "") or os.getenv("BREVO_API_KEY", "")
        )
        self._enabled: bool = bool(self.api_key)
        if not self._enabled:
            logger.warning("BREVO_API_KEY nao configurada - tracking desabilitado")

    # ========================================================================
    # TRACKING ID
    # ========================================================================

    def generate_tracking_id(self) -> str:
        """
        Gera tracking ID unico para um email.

        Returns:
            UUID string no formato padrao (ex: '550e8400-e29b-41d4-a716-446655440000').
        """
        tracking_id = str(uuid.uuid4())
        logger.debug("Tracking ID gerado", extra={"tracking_id": tracking_id})
        return tracking_id

    # ========================================================================
    # ESTATISTICAS AGREGADAS
    # ========================================================================

    def get_tracking_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        Retorna estatisticas agregadas de tracking dos ultimos N dias.

        Consulta approval_queue para contar emails enviados, abertos,
        clicados, respondidos e com bounce.

        Args:
            days: Numero de dias para consultar (default: 30).

        Returns:
            Dict com totais e taxas:
                - total_sent, total_opened, total_clicked, total_replied, total_bounced
                - open_rate, click_rate, reply_rate (percentuais 0-100)
                - by_day: lista de dicts com {date, sent, opened, clicked, replied}
        """
        try:
            since = (datetime.utcnow() - timedelta(days=days)).isoformat()

            # Buscar todos os itens enviados (status approved ou sent) no periodo
            result = db.client.table("approval_queue") \
                .select("id, status, sent_at, opened_at, clicked_at, replied_at, bounced_at") \
                .in_("status", ["approved", "sent"]) \
                .gte("sent_at", since) \
                .execute()

            rows = result.data or []

            total_sent = len(rows)
            total_opened = sum(1 for r in rows if r.get("opened_at"))
            total_clicked = sum(1 for r in rows if r.get("clicked_at"))
            total_replied = sum(1 for r in rows if r.get("replied_at"))
            total_bounced = sum(1 for r in rows if r.get("bounced_at"))

            open_rate = round((total_opened / total_sent * 100), 1) if total_sent > 0 else 0.0
            click_rate = round((total_clicked / total_sent * 100), 1) if total_sent > 0 else 0.0
            reply_rate = round((total_replied / total_sent * 100), 1) if total_sent > 0 else 0.0

            # Agrupar por dia
            by_day: Dict[str, Dict[str, int]] = {}
            for r in rows:
                sent_at = r.get("sent_at", "")
                if not sent_at:
                    continue
                day = sent_at[:10]  # YYYY-MM-DD
                if day not in by_day:
                    by_day[day] = {"date": day, "sent": 0, "opened": 0, "clicked": 0, "replied": 0}
                by_day[day]["sent"] += 1
                if r.get("opened_at"):
                    by_day[day]["opened"] += 1
                if r.get("clicked_at"):
                    by_day[day]["clicked"] += 1
                if r.get("replied_at"):
                    by_day[day]["replied"] += 1

            by_day_list = sorted(by_day.values(), key=lambda x: x["date"])

            stats = {
                "total_sent": total_sent,
                "total_opened": total_opened,
                "total_clicked": total_clicked,
                "total_replied": total_replied,
                "total_bounced": total_bounced,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "reply_rate": reply_rate,
                "days": days,
                "by_day": by_day_list,
            }

            logger.info(
                "Tracking stats calculadas",
                extra={
                    "days": days,
                    "total_sent": total_sent,
                    "open_rate": open_rate,
                    "click_rate": click_rate,
                },
            )

            return stats

        except Exception as e:
            logger.error("Erro ao calcular tracking stats", extra={"error": str(e)})
            return {
                "total_sent": 0,
                "total_opened": 0,
                "total_clicked": 0,
                "total_replied": 0,
                "total_bounced": 0,
                "open_rate": 0.0,
                "click_rate": 0.0,
                "reply_rate": 0.0,
                "days": days,
                "by_day": [],
                "error": str(e),
            }

    # ========================================================================
    # BREVO EVENT POLLING
    # ========================================================================

    def check_brevo_events(self, limit: int = 100) -> Dict[str, Any]:
        """
        Consulta eventos de email na API do Brevo e atualiza o banco.

        Busca eventos dos tipos: delivered, opened, clicked, hardBounce,
        softBounce. Para cada evento encontrado que tenha tag 'queue:UUID',
        atualiza o campo correspondente na approval_queue e insere
        uma interaction.

        Args:
            limit: Numero maximo de eventos por tipo (default: 100).

        Returns:
            Dict com contadores por tipo de evento processado.
        """
        if not self._enabled:
            logger.warning("Brevo tracking desabilitado - API key nao configurada")
            return {"enabled": False, "error": "BREVO_API_KEY nao configurada"}

        event_types = ["delivered", "opened", "clicked", "hardBounce", "softBounce"]
        summary: Dict[str, int] = {et: 0 for et in event_types}
        total_processed = 0

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        for event_type in event_types:
            try:
                resp = requests.get(
                    f"{self.BASE_URL}/smtp/statistics/events",
                    headers=headers,
                    params={"limit": limit, "event": event_type},
                    timeout=30,
                )

                if resp.status_code != 200:
                    logger.warning(
                        "Brevo events API erro",
                        extra={"event_type": event_type, "status": resp.status_code},
                    )
                    continue

                data = resp.json()
                events = data.get("events", [])

                for event in events:
                    processed = self._process_event(event, event_type)
                    if processed:
                        summary[event_type] += 1
                        total_processed += 1

            except Exception as e:
                logger.error(
                    "Erro ao buscar eventos Brevo",
                    extra={"event_type": event_type, "error": str(e)},
                )

        logger.info(
            "Brevo events sincronizados",
            extra={"total_processed": total_processed, "summary": summary},
        )

        return {"enabled": True, "total_processed": total_processed, "by_type": summary}

    def _process_event(self, event: Dict[str, Any], event_type: str) -> bool:
        """
        Processa um evento individual do Brevo.

        Extrai queue_id da tag 'queue:UUID', atualiza approval_queue
        e insere interaction correspondente.

        Args:
            event: Evento retornado pela API Brevo.
            event_type: Tipo do evento (opened, clicked, etc).

        Returns:
            True se o evento foi processado com sucesso.
        """
        try:
            # Extrair queue_id das tags
            tags = event.get("tags", []) or event.get("tag", "")
            queue_id = None

            if isinstance(tags, list):
                for tag in tags:
                    if isinstance(tag, str) and tag.startswith("queue:"):
                        queue_id = tag.replace("queue:", "")
                        break
            elif isinstance(tags, str) and tags.startswith("queue:"):
                queue_id = tags.replace("queue:", "")

            if not queue_id:
                return False

            # Determinar campo e tipo de interacao
            field_map = {
                "delivered": ("delivered_at", "email_delivered"),
                "opened": ("opened_at", "email_opened"),
                "clicked": ("clicked_at", "email_clicked"),
                "hardBounce": ("bounced_at", "email_bounced"),
                "softBounce": ("bounced_at", "email_soft_bounced"),
            }

            if event_type not in field_map:
                return False

            field_name, interaction_type = field_map[event_type]
            event_date = event.get("date", datetime.utcnow().isoformat())

            # Buscar item na fila para obter company_id
            queue_result = db.client.table("approval_queue") \
                .select("id, company_id, contact_id, " + field_name) \
                .eq("id", queue_id) \
                .execute()

            if not queue_result.data:
                return False

            queue_item = queue_result.data[0]

            # Nao sobrescrever se ja tem data (manter primeiro evento)
            if queue_item.get(field_name):
                return False

            # Atualizar approval_queue
            db.client.table("approval_queue") \
                .update({field_name: event_date}) \
                .eq("id", queue_id) \
                .execute()

            # Inserir interaction
            interaction_data = {
                "company_id": queue_item["company_id"],
                "type": interaction_type,
                "channel": "email",
                "metadata": {
                    "queue_id": queue_id,
                    "event_date": event_date,
                    "email": event.get("email", ""),
                },
            }
            if queue_item.get("contact_id"):
                interaction_data["contact_id"] = queue_item["contact_id"]

            db.insert_interaction(interaction_data)

            logger.debug(
                "Evento Brevo processado",
                extra={
                    "queue_id": queue_id,
                    "event_type": event_type,
                    "event_date": event_date,
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Erro ao processar evento Brevo",
                extra={"event_type": event_type, "error": str(e)},
            )
            return False

    # ========================================================================
    # TIMELINE POR EMPRESA
    # ========================================================================

    def get_email_timeline(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Retorna timeline completa de emails para uma empresa.

        Combina dados da approval_queue (mensagens enviadas) com
        interactions (eventos de tracking) ordenados por data.

        Args:
            company_id: UUID da empresa.

        Returns:
            Lista de dicts com {type, date, details} ordenada por data.
        """
        timeline: List[Dict[str, Any]] = []

        try:
            # Buscar mensagens enviadas
            queue_result = db.client.table("approval_queue") \
                .select("id, subject, status, sent_at, opened_at, clicked_at, "
                        "replied_at, bounced_at, tracking_id, brevo_message_id") \
                .eq("company_id", company_id) \
                .in_("status", ["approved", "sent"]) \
                .order("sent_at", desc=True) \
                .execute()

            for item in (queue_result.data or []):
                sent_at = item.get("sent_at")
                if sent_at:
                    timeline.append({
                        "type": "email_sent",
                        "date": sent_at,
                        "details": {
                            "queue_id": item["id"],
                            "subject": item.get("subject", ""),
                            "tracking_id": item.get("tracking_id"),
                            "brevo_message_id": item.get("brevo_message_id"),
                        },
                    })

                # Adicionar eventos de tracking como entradas separadas
                for field, event_type in [
                    ("opened_at", "email_opened"),
                    ("clicked_at", "email_clicked"),
                    ("replied_at", "email_replied"),
                    ("bounced_at", "email_bounced"),
                ]:
                    if item.get(field):
                        timeline.append({
                            "type": event_type,
                            "date": item[field],
                            "details": {
                                "queue_id": item["id"],
                                "subject": item.get("subject", ""),
                            },
                        })

            # Buscar interactions adicionais (podem ter dados extras)
            interactions_result = db.client.table("interactions") \
                .select("type, channel, created_at, metadata, subject") \
                .eq("company_id", company_id) \
                .eq("channel", "email") \
                .order("created_at", desc=True) \
                .execute()

            for interaction in (interactions_result.data or []):
                timeline.append({
                    "type": interaction.get("type", "interaction"),
                    "date": interaction.get("created_at", ""),
                    "details": {
                        "subject": interaction.get("subject", ""),
                        "metadata": interaction.get("metadata"),
                    },
                })

            # Ordenar por data (mais recente primeiro)
            timeline.sort(key=lambda x: x.get("date", ""), reverse=True)

            # Deduplicar entradas muito proximas do mesmo tipo
            seen = set()
            deduplicated = []
            for entry in timeline:
                key = (entry["type"], entry.get("date", "")[:16])  # Agrupa por minuto
                if key not in seen:
                    seen.add(key)
                    deduplicated.append(entry)

            logger.debug(
                "Email timeline gerada",
                extra={"company_id": company_id, "events": len(deduplicated)},
            )

            return deduplicated

        except Exception as e:
            logger.error(
                "Erro ao gerar email timeline",
                extra={"company_id": company_id, "error": str(e)},
            )
            return []

    # ========================================================================
    # SYNC PRINCIPAL
    # ========================================================================

    def sync_tracking_events(self) -> Dict[str, Any]:
        """
        Funcao principal de sincronizacao de tracking.

        Chama check_brevo_events para buscar e processar todos os
        eventos pendentes do Brevo.

        Returns:
            Dict com resumo da sincronizacao (total processado, por tipo).
        """
        logger.info("Iniciando sincronizacao de tracking events")

        try:
            result = self.check_brevo_events()

            logger.info(
                "Sincronizacao de tracking concluida",
                extra={
                    "total_processed": result.get("total_processed", 0),
                    "by_type": result.get("by_type", {}),
                },
            )

            return result

        except Exception as e:
            logger.error("Erro na sincronizacao de tracking", extra={"error": str(e)})
            return {"enabled": False, "error": str(e), "total_processed": 0}


# Singleton
email_tracker = EmailTracker()
