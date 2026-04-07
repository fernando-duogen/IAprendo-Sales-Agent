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

    # Tag usada nos jobs do pipeline automatico (facilita reload dinamico)
    PIPELINE_TAG = "automated_pipeline"
    FOLLOWUP_TAG = "automated_followup"

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
        # Envio de mensagens agendadas — a cada 5 min
        schedule.every(5).minutes.do(self._send_scheduled_messages)
        # Detector de sinais de compra (intent alerts) — a cada 30 min
        schedule.every(30).minutes.do(self._check_buying_signals)
        # Retreino semanal do modelo preditivo (domingo 03:00)
        schedule.every().sunday.at("03:00").do(self._retrain_predictive_model)

        # Pipeline automatico dinamico (carregado da config do banco)
        self._register_automated_pipeline()

        # Follow-ups comportamentais automaticos (Item 6)
        self._register_automated_followup()

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
        """Envia mensagem para o Fernando via WhatsApp."""
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

    def _run_background_with_feedback(
        self,
        task_name: str,
        task_fn,
        timeout_minutes: int = 10,
    ):
        """Executa uma funcao em background thread com GARANTIA de feedback.
        Se a task terminar (sucesso ou erro), envia resultado via WhatsApp.
        Se exceder timeout, envia aviso de timeout.

        REGRA: toda task background DEVE ter feedback. Fernando nunca fica sem resposta.

        Args:
            task_name: nome amigavel (ex: "Follow-ups", "Pipeline")
            task_fn: callable que recebe None e retorna None (usa _send_to_owner internamente)
            timeout_minutes: timeout em minutos (default 10)
        """
        import time as _time

        def _wrapped():
            started = _time.time()
            feedback_sent = False
            try:
                task_fn()
                feedback_sent = True  # task_fn deve ter chamado _send_to_owner
            except Exception as e:
                logger.error(f"Task background '{task_name}' falhou: {e}", exc_info=True)
                if not feedback_sent:
                    try:
                        self._send_to_owner(
                            f"❌ *{task_name} — ERRO*\n\n"
                            f"A tarefa falhou apos {int((_time.time() - started) / 60)} min.\n"
                            f"Erro: `{str(e)[:300]}`\n\n"
                            f"_Verifique os logs no dashboard._"
                        )
                    except Exception:
                        pass

        def _with_timeout():
            import time as _t
            task_thread = threading.Thread(target=_wrapped, daemon=True)
            task_thread.start()
            task_thread.join(timeout=timeout_minutes * 60)
            if task_thread.is_alive():
                logger.error(f"Task background '{task_name}' excedeu timeout de {timeout_minutes} min")
                try:
                    self._send_to_owner(
                        f"⏰ *{task_name} — TIMEOUT*\n\n"
                        f"A tarefa nao terminou em {timeout_minutes} minutos.\n"
                        f"Pode estar travada. Verifique os logs."
                    )
                except Exception:
                    pass

        threading.Thread(target=_with_timeout, daemon=True).start()

    def _send_scheduled_messages(self):
        """Verifica e envia mensagens agendadas cujo horario ja passou.
        Roda a cada 5 minutos. Se scheduled_send_at <= NOW() ou NULL, envia.
        Notifica Fernando sobre envios E bloqueios (sem email).
        """
        try:
            from workflows.send_approved import send_approved_messages
            result = send_approved_messages(limit=20)
            n_sent = result.get("sent", 0)
            n_skipped = result.get("skipped", 0)

            if n_sent > 0:
                logger.info(f"Envio agendado: {n_sent} mensagem(ns) enviada(s)")
                self._send_to_owner(
                    f"📤 *Envio concluido*\n\n"
                    f"✅ {n_sent} mensagem(ns) enviada(s) agora."
                )

            if n_skipped > 0:
                blocked_details = [d for d in result.get("details", []) if d.get("status") == "blocked"]
                logger.warning(f"Envio: {n_skipped} mensagem(ns) bloqueada(s) por falta de email")
                self._send_to_owner(
                    f"⚠️ *{n_skipped} mensagem(ns) BLOQUEADA(S)*\n\n"
                    f"Motivo: contato sem email cadastrado.\n"
                    f"Adicione o email do contato no dashboard e reprocesse.\n"
                    f"_As mensagens foram movidas para status 'blocked'._"
                )
        except Exception as e:
            logger.error(f"Erro no envio agendado: {e}")

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

    # ============================================================
    # PIPELINE AUTOMATICO (Item 5)
    # ============================================================

    def _register_automated_pipeline(self):
        """Registra o job do pipeline automatico com base na config salva.
        Le a config via integrations.pipeline_config e agenda 1 job por dia
        habilitado no horario configurado. Silencioso se desabilitado.
        Gate de autonomia: nao registra se autonomy_level='manual'.
        """
        try:
            from integrations.pipeline_config import pipeline_config
            cfg = pipeline_config.get_config()
            if cfg.get("autonomy_level") == "manual":
                logger.info("Pipeline automatico BLOQUEADO (modo manual)")
                return
            if not cfg.get("enabled"):
                logger.info("Pipeline automatico desabilitado (nenhum job registrado)")
                return
            time_str = cfg.get("schedule_time", "08:00")
            days = cfg.get("days", [])
            day_map = {
                "mon": schedule.every().monday,
                "tue": schedule.every().tuesday,
                "wed": schedule.every().wednesday,
                "thu": schedule.every().thursday,
                "fri": schedule.every().friday,
                "sat": schedule.every().saturday,
                "sun": schedule.every().sunday,
            }
            registered = []
            for d in days:
                j = day_map.get(d)
                if not j:
                    continue
                j.at(time_str).do(self._run_automated_pipeline).tag(self.PIPELINE_TAG)
                registered.append(d)
            logger.info(
                "Pipeline automatico registrado",
                extra={"time": time_str, "days": registered, "steps": cfg.get("steps")},
            )
        except Exception as e:
            logger.error(f"Erro ao registrar pipeline automatico: {e}")

    def reload_pipeline_schedule(self):
        """Limpa jobs antigos do pipeline automatico e re-registra com config atual.
        Chamado pela UI quando Fernando salva nova configuracao.
        """
        try:
            schedule.clear(self.PIPELINE_TAG)
            logger.info("Jobs antigos do pipeline automatico removidos")
        except Exception as e:
            logger.debug(f"reload_pipeline_schedule clear: {e}")
        self._register_automated_pipeline()

    def _run_automated_pipeline(self, triggered_by: str = "schedule"):
        """Executa o pipeline automatico conforme config e envia resumo WhatsApp.
        Usa _run_background_with_feedback para garantir que Fernando sempre recebe retorno.
        """
        def _task():
            self.__run_pipeline_inner(triggered_by)

        self._run_background_with_feedback(
            task_name="Pipeline automatico",
            task_fn=_task,
            timeout_minutes=15,
        )

    def __run_pipeline_inner(self, triggered_by: str):
        """Logica interna do pipeline (chamada pelo wrapper com feedback)."""
        started = datetime.now()
        from integrations.pipeline_config import pipeline_config
        from workflows.daily_pipeline import run_pipeline

        cfg = pipeline_config.get_config()

        # Se foi disparado por schedule, validar dia atual
        if triggered_by == "schedule":
            today = pipeline_config.weekday_short_from_date(started)
            if today not in cfg.get("days", []):
                self._send_to_owner(
                    f"🤖 *Pipeline automatico*: hoje ({today}) nao esta nos dias configurados. Nada a fazer."
                )
                return

        # Gate de autonomia em runtime (defense in depth)
        autonomy = cfg.get("autonomy_level", "semi_auto")
        effective_send = cfg.get("send_approved", False) and autonomy == "full_auto"
        effective_steps = list(cfg.get("steps") or [])
        if autonomy != "full_auto" and "send" in effective_steps:
            effective_steps = [s for s in effective_steps if s != "send"]

        logger.info("Pipeline automatico INICIANDO", extra={
            "triggered_by": triggered_by,
            "autonomy_level": autonomy,
            "steps": effective_steps,
        })

        limits = cfg.get("limits", {})
        report = run_pipeline(
            qualify_limit=limits.get("qualify_limit", 20),
            enrich_limit=limits.get("enrich_limit", 10),
            write_limit=limits.get("write_limit", 10),
            send_approved=effective_send,
            dry_run=cfg.get("dry_run", False),
            write_mode=cfg.get("write_mode", "ai"),
            steps=effective_steps,
        )

        finished = datetime.now()
        duration_min = int((finished - started).total_seconds() // 60)

        message = self._format_pipeline_summary(
            cfg=cfg,
            report=report,
            started=started,
            finished=finished,
            duration_min=duration_min,
            triggered_by=triggered_by,
        )
        self._send_to_owner(message)

        pipeline_config.update_last_run(
            status="success",
            summary=report.get("summary", {}),
        )

    def _format_pipeline_summary(
        self,
        cfg: dict,
        report: dict,
        started: datetime,
        finished: datetime,
        duration_min: int,
        triggered_by: str,
    ) -> str:
        """Formata o resumo do pipeline para enviar no WhatsApp."""
        from integrations.pipeline_config import pipeline_config as pc

        steps_data = report.get("steps", {}) or {}
        summary = report.get("summary", {}) or {}
        qualified = steps_data.get("qualify", {}).get("output", 0) if "qualify" in steps_data else None
        enriched = steps_data.get("enrich", {}).get("output", 0) if "enrich" in steps_data else None
        contacts_found = steps_data.get("contacts", {}).get("output", 0) if "contacts" in steps_data else None
        written = steps_data.get("write", {}).get("output", 0) if "write" in steps_data else None
        sent = steps_data.get("send", {}).get("sent", 0) if "send" in steps_data else None

        # Fila pendente
        try:
            from database.supabase_client import db as _db
            q = _db.client.table("approval_queue").select("id", count="exact").eq(
                "status", "pending"
            ).execute()
            pending = q.count or 0
        except Exception:
            pending = None

        day_name = pc.day_label(pc.weekday_short_from_date(started))
        date_str = started.strftime("%d/%m")
        time_range = f"{started.strftime('%H:%M')}-{finished.strftime('%H:%M')}"

        header = (
            "🤖 *Pipeline automatico executado*"
            if triggered_by == "schedule"
            else "🤖 *Pipeline executado manualmente*"
        )

        lines = [
            header,
            f"📅 {day_name}, {date_str} — {time_range} ({duration_min} min)",
            "",
            "📊 *Resultado:*",
        ]
        if qualified is not None:
            lines.append(f"   ✅ Qualificadas: {qualified}")
        if enriched is not None:
            lines.append(f"   ✅ Enriquecidas: {enriched}")
        if contacts_found is not None:
            lines.append(f"   ✅ Contatos encontrados: {contacts_found}")
        if written is not None:
            lines.append(f"   ✅ Emails gerados: {written}")
        if sent is not None:
            lines.append(f"   ✅ Emails enviados: {sent}")

        if not any(v is not None and v > 0 for v in [qualified, enriched, contacts_found, written, sent]):
            lines.append("   _Nenhuma acao necessaria — tudo em dia._")

        lines.append("")
        if pending is not None:
            lines.append(f"📋 *Fila de aprovacao:* {pending} email(s) aguardando")
        lines.append("")
        lines.append("⚡ *Proximo passo:* revise a fila no dashboard")

        return "\n".join(lines)

    def run_pipeline_now(self) -> Dict[str, Any]:
        """Executa o pipeline automatico imediatamente (manual/teste).
        Respeita o autonomy_level: em modo manual, apenas GERA (nao envia),
        mesmo que o usuario clique no botao de teste.
        """
        try:
            from integrations.pipeline_config import pipeline_config
            lvl = pipeline_config.get_autonomy_level()
            if lvl == "manual":
                return {
                    "ok": False,
                    "reason": "autonomy_manual",
                    "message": (
                        "Modo MANUAL: execucao automatica bloqueada. "
                        "Mude para SEMI-AUTO ou FULL-AUTO em Configuracoes para rodar."
                    ),
                }
        except Exception:
            pass
        self._run_automated_pipeline(triggered_by="manual")
        return {"ok": True}

    # ============================================================
    # FOLLOW-UPS COMPORTAMENTAIS (Item 6)
    # ============================================================

    def _register_automated_followup(self):
        """Registra job diario de follow-ups comportamentais com base na config.
        Gate de autonomia: nao registra se autonomy_level='manual'.
        """
        try:
            from integrations.pipeline_config import pipeline_config
            cfg = pipeline_config.get_config()
            if cfg.get("autonomy_level") == "manual":
                logger.info("Follow-ups automaticos BLOQUEADOS (modo manual)")
                return
            if not cfg.get("followup_enabled", False):
                logger.info("Follow-ups automaticos desabilitados")
                return
            time_str = cfg.get("followup_time", "09:30")
            schedule.every().day.at(time_str).do(
                self._run_follow_up_generation
            ).tag(self.FOLLOWUP_TAG)
            logger.info("Follow-ups automaticos registrados", extra={
                "time": time_str,
                "limit": cfg.get("followup_limit", 20),
                "types": cfg.get("followup_types"),
            })
        except Exception as e:
            logger.error(f"Erro ao registrar follow-ups automaticos: {e}")

    def reload_followup_schedule(self):
        """Limpa jobs antigos de follow-up e re-registra."""
        try:
            schedule.clear(self.FOLLOWUP_TAG)
        except Exception:
            pass
        self._register_automated_followup()

    def _run_follow_up_generation(self, triggered_by: str = "schedule"):
        """Executa geracao de follow-ups comportamentais com feedback garantido."""
        def _task():
            self.__run_followup_inner(triggered_by)

        self._run_background_with_feedback(
            task_name="Follow-ups",
            task_fn=_task,
            timeout_minutes=10,
        )

    def __run_followup_inner(self, triggered_by: str):
        """Logica interna de follow-ups (chamada pelo wrapper com feedback)."""
        from workflows.follow_up_manager import run_follow_up_check
        from integrations.pipeline_config import pipeline_config

        cfg = pipeline_config.get_config()
        limit = cfg.get("followup_limit", 20)
        allowed = cfg.get("followup_types") or None

        logger.info("Follow-ups automaticos: INICIANDO", extra={
            "triggered_by": triggered_by,
            "limit": limit,
            "allowed_types": allowed,
        })

        result = run_follow_up_check(limit=limit, allowed_types=allowed)
        message = self._format_followup_summary(result, triggered_by)
        self._send_to_owner(message)

    def _format_followup_summary(self, result: dict, triggered_by: str) -> str:
        """Formata o resumo de follow-ups para WhatsApp."""
        generated = result.get("generated", 0)
        errors = result.get("errors", 0)
        due = result.get("due_found", 0)
        by_type = result.get("by_type", {}) or {}

        emoji_map = {
            "hot_click": "🔥",
            "curious_open": "👀",
            "silent_open": "📬",
            "revival": "🧊",
        }
        label_map = {
            "hot_click": "hot click (alta prioridade)",
            "curious_open": "curious open",
            "silent_open": "silent open",
            "revival": "revival",
        }

        header = (
            "🔄 *Follow-ups automaticos*"
            if triggered_by == "schedule"
            else "🔄 *Follow-ups (manual)*"
        )

        lines = [header]
        lines.append(f"📅 {datetime.now().strftime('%d/%m %H:%M')}")
        lines.append("")
        lines.append(f"📊 *Resumo:* {generated} gerados | {errors} erros | {due} detectados")

        if generated > 0:
            lines.append("")
            lines.append("*Por tipo comportamental:*")
            for t, n in by_type.items():
                if n > 0:
                    emoji = emoji_map.get(t, "•")
                    label = label_map.get(t, t)
                    lines.append(f"   {emoji} {label}: {n}")

        # Fila pendente total
        try:
            from database.supabase_client import db as _db
            q = _db.client.table("approval_queue").select("id", count="exact").eq(
                "status", "pending"
            ).execute()
            pending = q.count or 0
            lines.append("")
            lines.append(f"📋 *Fila de aprovacao:* {pending} email(s) aguardando")
        except Exception:
            pass

        if generated == 0 and due == 0:
            lines.append("")
            lines.append("_Nenhum lead esta pronto para follow-up agora._")
        elif generated > 0:
            lines.append("")
            lines.append("⚡ *Proximo passo:* revise na fila de aprovacao")

        return "\n".join(lines)

    def run_followup_now(self) -> Dict[str, Any]:
        """Executa geracao de follow-ups imediatamente (manual/teste).
        Follow-ups SEMPRE geram em status=pending, entao sao seguros em
        qualquer nivel de autonomia. Apenas bloqueia em modo 'manual' total.
        """
        try:
            from integrations.pipeline_config import pipeline_config
            if pipeline_config.get_autonomy_level() == "manual":
                return {
                    "ok": False,
                    "reason": "autonomy_manual",
                    "message": (
                        "Modo MANUAL: geracao automatica de follow-ups bloqueada. "
                        "Mude para SEMI-AUTO ou FULL-AUTO em Configuracoes."
                    ),
                }
        except Exception:
            pass
        self._run_follow_up_generation(triggered_by="manual")
        return {"ok": True}

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
