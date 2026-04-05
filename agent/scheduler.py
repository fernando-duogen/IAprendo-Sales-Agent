"""
IAlex Scheduler - Envia mensagens proativas para o Fernando via WhatsApp.
- Briefing matinal (8h)
- Alertas instantaneos (quando alguem responde)
- Resumo semanal (sexta 17h)
"""
import sys
import os
import time
import threading
import schedule
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


class IALexScheduler:
    """Agenda e envia mensagens proativas."""

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        """Inicia o scheduler em background thread."""
        if self._running:
            return

        # Agendar tarefas
        schedule.every().day.at("08:00").do(self._morning_briefing)
        schedule.every().day.at("12:00").do(self._midday_check)
        schedule.every().day.at("17:00").do(self._end_of_day)
        schedule.every().friday.at("17:30").do(self._weekly_report)
        schedule.every(15).minutes.do(self._check_replies)
        schedule.every(15).minutes.do(self._hubspot_pull)
        # Detector de sinais de compra (intent alerts) — a cada 30 min
        schedule.every(30).minutes.do(self._check_buying_signals)
        # Retreino semanal do modelo preditivo (domingo 03:00)
        schedule.every().sunday.at("03:00").do(self._retrain_predictive_model)

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("IAlex scheduler iniciado")

    def stop(self):
        """Para o scheduler."""
        self._running = False
        schedule.clear()
        logger.info("IAlex scheduler parado")

    def _run_loop(self):
        """Loop principal do scheduler."""
        while self._running:
            try:
                schedule.run_pending()
            except Exception as e:
                logger.error(f"Erro no scheduler: {e}")
            time.sleep(30)

    def _send_to_owner(self, text: str):
        """Envia mensagem para o Fernando."""
        try:
            from agent.whatsapp_bridge import WhatsAppBridge
            bridge = WhatsAppBridge()
            owner = os.getenv("IALEX_OWNER_NUMBER", "")
            if owner:
                bridge.send_message(owner, text)
                logger.info("Mensagem proativa enviada", extra={"len": len(text)})
            else:
                logger.warning("IALEX_OWNER_NUMBER nao configurado")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem proativa: {e}")

    def _morning_briefing(self):
        """Envia briefing matinal as 8h."""
        try:
            from agent.brain import Brain
            brain = Brain()
            briefing = brain.get_morning_briefing()
            if briefing:
                self._send_to_owner(f"☀️ *Bom dia, Fernando!*\n\n{briefing}")
        except Exception as e:
            logger.error(f"Erro no briefing matinal: {e}")

    def _midday_check(self):
        """Check rapido ao meio-dia."""
        try:
            from database.supabase_client import db
            from approval_queue import queue_manager

            stats = queue_manager.get_stats()
            pending = stats.get("pending", 0)

            if pending > 0:
                self._send_to_owner(
                    f"🔔 Lembrete: voce tem *{pending} email(s)* aguardando aprovacao.\n"
                    f"Quer que eu aprove todos? Responda 'aprova tudo'."
                )
        except Exception as e:
            logger.error(f"Erro no check meio-dia: {e}")

    def _end_of_day(self):
        """Resumo do dia as 17h."""
        try:
            from database.supabase_client import db

            today = datetime.now().strftime("%Y-%m-%d")
            sent_today = db.client.table("approval_queue").select(
                "id", count="exact"
            ).eq("status", "sent").gte("sent_at", f"{today}T00:00:00").execute()

            count = sent_today.count or 0
            if count > 0:
                self._send_to_owner(
                    f"📊 *Resumo do dia:*\n"
                    f"📤 {count} email(s) enviado(s) hoje.\n"
                    f"Bom trabalho! 💪"
                )
        except Exception as e:
            logger.error(f"Erro no resumo do dia: {e}")

    def _weekly_report(self):
        """Resumo semanal na sexta as 17:30."""
        try:
            from agent.brain import Brain
            brain = Brain()
            report = brain.get_weekly_report()
            if report:
                self._send_to_owner(f"📋 *Resumo Semanal*\n\n{report}")
        except Exception as e:
            logger.error(f"Erro no relatorio semanal: {e}")

    def _check_replies(self):
        """Verifica a cada 15 min se houve novas respostas."""
        try:
            from database.supabase_client import db

            # Buscar emails com replied_at nos ultimos 15 minutos
            fifteen_min_ago = (datetime.now() - timedelta(minutes=16)).isoformat()
            recent_replies = db.client.table("approval_queue").select(
                "id,subject,replied_at,companies(name),contacts(full_name)"
            ).eq("status", "sent").gte("replied_at", fifteen_min_ago).execute().data or []

            for reply in recent_replies:
                comp = reply.get("companies") or {}
                ct = reply.get("contacts") or {}
                self._send_to_owner(
                    f"🎉 *RESPOSTA RECEBIDA!*\n\n"
                    f"🏫 {comp.get('name', '?')}\n"
                    f"👤 {ct.get('full_name', '?')}\n"
                    f"📧 Re: {reply.get('subject', '')[:40]}\n\n"
                    f"Verifique seu email! Quer que eu sugira proximos passos?"
                )
        except Exception as e:
            # Nao logar se for erro normal (tabela sem coluna, etc)
            if "column" not in str(e).lower():
                logger.error(f"Erro ao verificar replies: {e}")

    def _hubspot_pull(self):
        """Puxa mudancas do HubSpot a cada 15 min (sincronizacao reversa)."""
        try:
            from integrations.hubspot_pull import hubspot_pull
            result = hubspot_pull.pull_changes()
            total = result.get("companies", 0) + result.get("contacts", 0) + result.get("deals", 0)
            if total > 0:
                logger.info(f"HubSpot pull: {total} registros atualizados", extra=result)
        except ImportError:
            pass  # HubSpot nao configurado
        except Exception as e:
            logger.error(f"Erro no HubSpot pull agendado: {e}")

    def _check_buying_signals(self):
        """Detecta sinais de compra (intent alerts) e notifica Fernando na hora.
        Roda a cada 30 minutos. Usa o modulo intent_detector com dedup via memoria.
        """
        try:
            from tools.intent_detector import intent_detector
            new_alerts = intent_detector.get_new_alerts(days=7, min_score=50)
            if not new_alerts:
                return
            logger.info(f"Intent detector: {len(new_alerts)} novo(s) alerta(s) de compra")
            for signal in new_alerts:
                message = intent_detector.format_for_whatsapp(signal)
                self._send_to_owner(message)
                intent_detector.mark_alerted(signal)
        except Exception as e:
            logger.error(f"Erro no check buying signals: {e}")

    def _retrain_predictive_model(self):
        """Retreina o modelo preditivo semanalmente (domingo 03:00)."""
        try:
            from tools.predictive_scorer import predictive_scorer
            result = predictive_scorer.train()
            if result.get("trained"):
                logger.info(
                    f"Modelo preditivo retreinado: {result['samples']} amostras, "
                    f"{result['positives']} positivos, accuracy {result['accuracy']}"
                )
                # Notificar Fernando se houve melhoria significativa
                self._send_to_owner(
                    f"🤖 *Modelo preditivo retreinado*\n\n"
                    f"📊 {result['samples']} escolas analisadas\n"
                    f"🎯 {result['positives']} positivos (respostas/reunioes)\n"
                    f"✅ Accuracy: {result['accuracy']}\n\n"
                    f"O IAlex esta mais inteligente! Pergunte 'top oportunidades' para ver o novo ranking."
                )
            else:
                logger.info(f"Retreino nao realizado: {result.get('reason')}")
        except Exception as e:
            logger.error(f"Erro no retreino do modelo preditivo: {e}")

    # === Metodos para executar manualmente ===

    def send_briefing_now(self):
        """Envia briefing agora (para testes)."""
        self._morning_briefing()

    def send_weekly_now(self):
        """Envia relatorio semanal agora (para testes)."""
        self._weekly_report()


# Singleton
ialex_scheduler = IALexScheduler()


if __name__ == "__main__":
    print("IAlex Scheduler - Modo teste")
    print("Enviando briefing matinal...")
    ialex_scheduler.send_briefing_now()
