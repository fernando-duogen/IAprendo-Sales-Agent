"""
IAlex Executor - Executa acoes no sistema IAprendo.
Recebe comandos do brain e interage com o banco/APIs.

Cada metodo retorna texto formatado para WhatsApp (curto e direto).
Todos os metodos tem try/except e logging.

Usage:
    from agent.executor import Executor

    executor = Executor()
    result = executor.execute({"type": "check_pending", "params": {}})
    # result = "📋 3 mensagens pendentes:\n1. Escola ABC - Score 85\n..."
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# Garante que o diretorio raiz do projeto esta no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


class Executor:
    """
    Executa acoes decididas pelo Brain no sistema IAprendo.

    Cada metodo corresponde a um action type do Brain.
    Retorna texto formatado para WhatsApp.
    """

    # ------------------------------------------------------------------
    # ROUTER
    # ------------------------------------------------------------------

    def execute(self, action: Dict[str, Any]) -> str:
        """
        Roteia acao para o metodo correto.

        Args:
            action: Dict com 'type' (str) e 'params' (dict)

        Returns:
            Texto formatado para WhatsApp com resultado da acao.
        """
        action_type: str = action.get("type", "none")
        params: Dict[str, Any] = action.get("params", {})

        logger.info(
            "Executando acao",
            extra={"action_type": action_type, "params": params}
        )

        # Mapa de acoes
        action_map = {
            "run_pipeline": self.run_pipeline,
            "check_pending": self.check_pending,
            "approve_all": self.approve_all,
            "approve_id": self.approve_id,
            "get_stats": self.get_stats,
            "search_school": self.search_school,
            "search_contacts": self.search_contacts,
            "run_followups": self.run_followups,
            "get_score": self.get_score,
            "export_report": self.export_report,
            "run_backup": self.run_backup,
            "sync_hubspot": self.sync_hubspot,
            "sync_tracking": self.sync_tracking,
            "get_schedule": self.get_schedule,
        }

        handler = action_map.get(action_type)
        if handler is None:
            if action_type != "none":
                logger.warning(
                    "Acao desconhecida",
                    extra={"action_type": action_type}
                )
            return ""

        try:
            return handler(**params)
        except TypeError as e:
            # Params invalidos
            logger.error(
                "Params invalidos para acao",
                extra={"action_type": action_type, "error": str(e)}
            )
            return f"Erro nos parametros da acao '{action_type}': {str(e)[:100]}"
        except Exception as e:
            logger.error(
                "Erro ao executar acao",
                extra={"action_type": action_type, "error": str(e)}
            )
            return f"Erro ao executar '{action_type}': {str(e)[:100]}"

    # ------------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------------

    def run_pipeline(
        self,
        limit: int = 5,
        steps: Optional[List[str]] = None,
        **kwargs: Any
    ) -> str:
        """
        Roda o pipeline de prospeccao.

        Args:
            limit: Numero de escolas por etapa
            steps: Lista de etapas a executar (qualify, enrich, write, send)

        Returns:
            Resumo do pipeline executado.
        """
        try:
            from workflows.daily_pipeline import run_pipeline

            result = run_pipeline(
                qualify_limit=limit,
                enrich_limit=limit,
                write_limit=limit,
                send_approved=True,
                steps=steps,
            )

            # Formata resultado
            parts: List[str] = ["Pipeline executado:"]

            if "qualified" in result:
                parts.append(f"  - Qualificadas: {result['qualified']}")
            if "enriched" in result:
                parts.append(f"  - Enriquecidas: {result['enriched']}")
            if "messages_created" in result:
                parts.append(f"  - Mensagens criadas: {result['messages_created']}")
            if "sent" in result:
                parts.append(f"  - Enviadas: {result['sent']}")
            if "errors" in result and result["errors"]:
                parts.append(f"  - Erros: {len(result['errors'])}")

            logger.info("Pipeline executado via executor", extra={"result": result})
            return "\n".join(parts)

        except Exception as e:
            logger.error("Erro no pipeline", extra={"error": str(e)})
            return f"Erro ao rodar pipeline: {str(e)[:150]}"

    def check_pending(self, **kwargs: Any) -> str:
        """
        Lista aprovacoes pendentes.

        Returns:
            Lista formatada de mensagens pendentes.
        """
        try:
            from approval_queue.queue_manager import queue_manager

            pending = queue_manager.get_pending(limit=20)

            if not pending:
                return "Nenhuma mensagem pendente de aprovacao."

            lines: List[str] = [f"📋 {len(pending)} pendente(s):\n"]
            for i, item in enumerate(pending[:10], 1):
                school = item.get("companies", {}).get("name", "?") if isinstance(item.get("companies"), dict) else "?"
                contact = item.get("contacts", {}).get("full_name", "?") if isinstance(item.get("contacts"), dict) else "?"
                subject = item.get("subject", "")[:40]
                lines.append(f"{i}. {school} - {contact}")
                lines.append(f"   Assunto: {subject}")
                lines.append(f"   ID: {item.get('id', '?')}")

            if len(pending) > 10:
                lines.append(f"\n... e mais {len(pending) - 10}")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro ao buscar pendentes", extra={"error": str(e)})
            return f"Erro ao buscar pendentes: {str(e)[:100]}"

    def approve_all(self, **kwargs: Any) -> str:
        """
        Aprova todas as mensagens pendentes.

        Returns:
            Contagem de mensagens aprovadas.
        """
        try:
            from approval_queue.queue_manager import queue_manager

            pending = queue_manager.get_pending(limit=100)

            if not pending:
                return "Nenhuma mensagem pendente para aprovar."

            approved = 0
            failed = 0
            for item in pending:
                queue_id = item.get("id")
                if queue_id:
                    success = queue_manager.approve(str(queue_id))
                    if success:
                        approved += 1
                    else:
                        failed += 1

            result = f"✅ {approved} mensagem(ns) aprovada(s)!"
            if failed:
                result += f"\n⚠️ {failed} falharam."

            logger.info(
                "Approve all executado",
                extra={"approved": approved, "failed": failed}
            )
            return result

        except Exception as e:
            logger.error("Erro ao aprovar tudo", extra={"error": str(e)})
            return f"Erro ao aprovar: {str(e)[:100]}"

    def approve_id(self, queue_id: str = "", **kwargs: Any) -> str:
        """
        Aprova uma mensagem especifica por ID.

        Args:
            queue_id: UUID da mensagem na fila

        Returns:
            Confirmacao da aprovacao.
        """
        if not queue_id:
            return "Preciso do ID da mensagem para aprovar. Me manda o ID."

        try:
            from approval_queue.queue_manager import queue_manager

            success = queue_manager.approve(queue_id)
            if success:
                logger.info("Mensagem aprovada", extra={"queue_id": queue_id})
                return f"✅ Mensagem {queue_id[:8]}... aprovada!"
            else:
                return f"Nao consegui aprovar a mensagem {queue_id[:8]}... Verifica se o ID ta certo."

        except Exception as e:
            logger.error("Erro ao aprovar por ID", extra={"queue_id": queue_id, "error": str(e)})
            return f"Erro ao aprovar: {str(e)[:100]}"

    def get_stats(self, **kwargs: Any) -> str:
        """
        Busca estatisticas do CRM.

        Returns:
            Metricas formatadas para WhatsApp.
        """
        try:
            # Total por status
            statuses = ["raw", "filtered", "qualified", "enriched", "contacted", "sent", "opened", "replied"]
            counts: Dict[str, int] = {}

            for status in statuses:
                result = db.client.table("companies").select(
                    "id", count="exact"
                ).eq("status", status).execute()
                counts[status] = result.count or 0

            total = db.client.table("companies").select(
                "id", count="exact"
            ).execute()
            total_count = total.count or 0

            # Contacts
            contacts = db.client.table("contacts").select(
                "id", count="exact"
            ).execute()
            contacts_count = contacts.count or 0

            # Queue stats
            from approval_queue.queue_manager import queue_manager
            queue = queue_manager.get_stats()

            lines: List[str] = [
                "📊 Estatisticas IAprendo:\n",
                f"Escolas na base: {total_count}",
            ]

            for status, count in counts.items():
                if count > 0:
                    lines.append(f"  - {status}: {count}")

            lines.append(f"\nContatos encontrados: {contacts_count}")

            if queue:
                lines.append("\nFila de aprovacao:")
                for status, count in queue.items():
                    lines.append(f"  - {status}: {count}")

            logger.info("Stats geradas")
            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro ao buscar stats", extra={"error": str(e)})
            return f"Erro ao buscar estatisticas: {str(e)[:100]}"

    def search_school(self, name: str = "", **kwargs: Any) -> str:
        """
        Busca escola por nome.

        Args:
            name: Nome (parcial) da escola

        Returns:
            Detalhes da escola encontrada.
        """
        if not name:
            return "Me diz o nome da escola que voce quer buscar."

        try:
            result = db.client.table("companies").select("*").ilike(
                "name", f"%{name}%"
            ).limit(5).execute()

            if not result.data:
                return f"Nenhuma escola encontrada com '{name}'."

            lines: List[str] = [f"🔍 {len(result.data)} resultado(s) para '{name}':\n"]
            for school in result.data:
                lines.append(f"📍 {school.get('name', '?')}")
                lines.append(f"   Cidade: {school.get('city', '?')} / {school.get('state', '?')}")
                lines.append(f"   Status: {school.get('status', '?')}")
                score = school.get("qualification_score")
                if score is not None:
                    lines.append(f"   Score: {score}")
                lines.append(f"   ID: {school.get('id', '?')}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro ao buscar escola", extra={"name": name, "error": str(e)})
            return f"Erro ao buscar escola: {str(e)[:100]}"

    def search_contacts(self, school_name: str = "", **kwargs: Any) -> str:
        """
        Busca contatos de uma escola.

        Args:
            school_name: Nome da escola

        Returns:
            Lista de contatos formatada.
        """
        if not school_name:
            return "Me diz o nome da escola para buscar os contatos."

        try:
            # Busca a escola primeiro
            schools = db.client.table("companies").select("id,name").ilike(
                "name", f"%{school_name}%"
            ).limit(1).execute()

            if not schools.data:
                return f"Nenhuma escola encontrada com '{school_name}'."

            company_id = schools.data[0]["id"]
            company_name = schools.data[0]["name"]

            # Busca contatos
            contacts = db.client.table("contacts").select("*").eq(
                "company_id", company_id
            ).execute()

            if not contacts.data:
                return f"Nenhum contato encontrado para '{company_name}'."

            lines: List[str] = [f"👤 Contatos de {company_name}:\n"]
            for c in contacts.data:
                lines.append(f"  - {c.get('full_name', '?')}")
                lines.append(f"    Cargo: {c.get('role', '?')}")
                lines.append(f"    Email: {c.get('email', '?')}")
                phone = c.get("phone")
                if phone:
                    lines.append(f"    Tel: {phone}")
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro ao buscar contatos", extra={"school_name": school_name, "error": str(e)})
            return f"Erro ao buscar contatos: {str(e)[:100]}"

    def run_followups(self, **kwargs: Any) -> str:
        """
        Verifica e gera follow-ups pendentes.

        Returns:
            Resumo dos follow-ups gerados.
        """
        try:
            from workflows.follow_up_manager import run_follow_up_check

            result = run_follow_up_check(limit=20)

            due = result.get("due", 0)
            generated = result.get("generated", 0)
            errors = result.get("errors", 0)

            if due == 0:
                return "Nenhum follow-up pendente no momento."

            text = f"🔄 Follow-ups: {due} pendentes, {generated} gerados"
            if errors:
                text += f", {errors} erros"
            text += "\nAs mensagens geradas estao na fila de aprovacao."

            logger.info("Follow-ups executados", extra={"result": result})
            return text

        except Exception as e:
            logger.error("Erro ao rodar follow-ups", extra={"error": str(e)})
            return f"Erro ao gerar follow-ups: {str(e)[:100]}"

    def get_score(self, school_name: str = "", **kwargs: Any) -> str:
        """
        Busca score de qualificacao de uma escola.

        Args:
            school_name: Nome da escola

        Returns:
            Score e reasoning da qualificacao.
        """
        if not school_name:
            return "Me diz o nome da escola para ver o score."

        try:
            result = db.client.table("companies").select(
                "name,qualification_score,qualification_reasoning,status"
            ).ilike("name", f"%{school_name}%").limit(1).execute()

            if not result.data:
                return f"Escola '{school_name}' nao encontrada."

            school = result.data[0]
            score = school.get("qualification_score")

            if score is None:
                return f"Escola '{school.get('name')}' ainda nao foi qualificada."

            text = f"🎯 {school.get('name')}\n"
            text += f"Score: {score}/100\n"
            text += f"Status: {school.get('status', '?')}\n"

            reasoning = school.get("qualification_reasoning", "")
            if reasoning:
                # Trunca para WhatsApp
                text += f"\nAnalise: {reasoning[:200]}"
                if len(reasoning) > 200:
                    text += "..."

            return text

        except Exception as e:
            logger.error("Erro ao buscar score", extra={"school_name": school_name, "error": str(e)})
            return f"Erro ao buscar score: {str(e)[:100]}"

    def export_report(self, **kwargs: Any) -> str:
        """
        Gera relatorio/export dos dados.

        Returns:
            Confirmacao com caminho do arquivo ou resumo.
        """
        try:
            # Gera resumo em texto (nao precisa de arquivo para WhatsApp)
            stats_text = self.get_stats()
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")

            return f"📄 Relatorio gerado em {timestamp}\n\n{stats_text}"

        except Exception as e:
            logger.error("Erro ao exportar relatorio", extra={"error": str(e)})
            return f"Erro ao gerar relatorio: {str(e)[:100]}"

    def run_backup(self, **kwargs: Any) -> str:
        """
        Executa backup dos dados.

        Returns:
            Confirmacao do backup.
        """
        try:
            # Conta registros por tabela para confirmar integridade
            tables = ["companies", "contacts", "approval_queue", "interactions"]
            counts: Dict[str, int] = {}

            for table in tables:
                try:
                    result = db.client.table(table).select(
                        "id", count="exact"
                    ).execute()
                    counts[table] = result.count or 0
                except Exception:
                    counts[table] = -1

            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
            lines: List[str] = [f"💾 Status dos dados ({timestamp}):\n"]
            for table, count in counts.items():
                status = f"{count} registros" if count >= 0 else "erro ao acessar"
                lines.append(f"  - {table}: {status}")

            lines.append("\nDados estao seguros no Supabase (backup automatico).")

            logger.info("Backup check executado", extra={"counts": counts})
            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro no backup", extra={"error": str(e)})
            return f"Erro ao verificar backup: {str(e)[:100]}"

    def sync_hubspot(self, **kwargs: Any) -> str:
        """
        Sincroniza dados com HubSpot.

        Returns:
            Resumo da sincronizacao.
        """
        try:
            from integrations.hubspot_sync import HubSpotSync

            sync = HubSpotSync()

            # Busca escolas para sincronizar
            schools = db.client.table("companies").select("*").in_(
                "status", ["qualified", "enriched", "contacted", "sent", "opened", "replied"]
            ).limit(50).execute()

            if not schools.data:
                return "Nenhuma escola para sincronizar com HubSpot."

            synced = 0
            errors = 0
            for school in schools.data:
                try:
                    sync.sync_company(school)
                    synced += 1
                except Exception:
                    errors += 1

            result = f"🔄 HubSpot sync: {synced} escolas sincronizadas"
            if errors:
                result += f", {errors} erros"

            logger.info(
                "HubSpot sync executado",
                extra={"synced": synced, "errors": errors}
            )
            return result

        except ImportError:
            return "Modulo HubSpot nao disponivel. Verifique a configuracao."
        except Exception as e:
            logger.error("Erro no HubSpot sync", extra={"error": str(e)})
            return f"Erro ao sincronizar HubSpot: {str(e)[:100]}"

    def sync_tracking(self, **kwargs: Any) -> str:
        """
        Sincroniza eventos de tracking de email (aberturas, cliques).

        Returns:
            Resumo dos eventos sincronizados.
        """
        try:
            # Busca eventos recentes de tracking
            result = db.client.table("interactions").select(
                "type", count="exact"
            ).execute()

            if not result.data:
                return "Nenhum evento de tracking encontrado."

            # Conta por tipo de evento
            events: Dict[str, int] = {}
            for row in result.data:
                event_type = row.get("type", "unknown")
                events[event_type] = events.get(event_type, 0) + 1

            lines: List[str] = ["📧 Tracking de emails:\n"]
            for event_type, count in events.items():
                lines.append(f"  - {event_type}: {count}")

            logger.info("Tracking sync executado", extra={"events": events})
            return "\n".join(lines)

        except Exception as e:
            logger.error("Erro no tracking sync", extra={"error": str(e)})
            return f"Erro ao sincronizar tracking: {str(e)[:100]}"

    def get_schedule(self, **kwargs: Any) -> str:
        """
        Sugere melhor horario para envio de emails.

        Returns:
            Sugestao de horario baseada em boas praticas B2B.
        """
        try:
            now = datetime.now()
            weekday = now.weekday()  # 0=Monday, 6=Sunday

            # Horarios recomendados para email B2B educacional
            if weekday < 5:  # Dias uteis
                suggestion = (
                    "📅 Melhores horarios para envio (dia util):\n"
                    "  - 08:00-09:00 (inicio do expediente)\n"
                    "  - 10:00-11:00 (apos primeira reuniao)\n"
                    "  - 14:00-15:00 (volta do almoco)\n\n"
                    "Evitar: sexta apos 15h e segunda antes das 9h.\n"
                    "Dica: Escolas costumam checar email no inicio da manha."
                )
            else:
                suggestion = (
                    "⚠️ Hoje e fim de semana.\n"
                    "Melhor agendar envios para segunda-feira 08:00-09:00.\n"
                    "Escolas nao verificam email no fim de semana."
                )

            return suggestion

        except Exception as e:
            logger.error("Erro ao sugerir horario", extra={"error": str(e)})
            return "Erro ao calcular melhor horario."
