"""
Proactive Action Engine (F2) - Acoes proativas baseadas no score de urgencia.

Gera:
- Daily digest agrupado por tier (WhatsApp)
- Lista priorizada "o que fazer agora"
- Auto-draft de follow-ups para leads CRITICAL (na approval_queue, NUNCA envia direto)
- Alertas de mudanca de tier ("Lead X foi de COLD para HOT em 3 dias")
- Alertas de inatividade ("Lead Y respondeu ha 5 dias sem follow-up")

REGRA ABSOLUTA: auto-drafts SEMPRE vao para approval_queue com status='pending'.
NUNCA envia sem aprovacao humana.

Usage:
    from tools.proactive_actions import proactive_engine

    digest = proactive_engine.generate_daily_digest()
    actions = proactive_engine.get_prioritized_actions(limit=10)
    drafts = proactive_engine.generate_critical_drafts()
    trends = proactive_engine.detect_and_format_trends()
    inactive = proactive_engine.detect_inactivity(days=5)
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


# Emojis de tier para WhatsApp
TIER_EMOJI: Dict[str, str] = {
    "CRITICAL": "\U0001f534",  # red circle
    "HOT": "\U0001f7e0",       # orange circle
    "WARM": "\U0001f7e1",      # yellow circle
    "COLD": "\U0001f7e2",      # green circle
}

TIER_LABEL: Dict[str, str] = {
    "CRITICAL": "CRITICO",
    "HOT": "QUENTE",
    "WARM": "MORNO",
    "COLD": "FRIO",
}


class ProactiveActionEngine:
    """Gera acoes proativas baseadas nos scores de urgencia."""

    # ========================================================================
    # DAILY DIGEST
    # ========================================================================

    def generate_daily_digest(self) -> str:
        """Gera digest diario formatado para WhatsApp, agrupado por tier.

        Returns:
            String formatada WhatsApp com leads por tier.
        """
        try:
            from tools.urgency_scorer import urgency_scorer

            lines: List[str] = ["\U0001f4ca *Digest de Urgencia*\n"]

            # CRITICAL — detalhes completos
            critical = urgency_scorer.get_by_tier("CRITICAL", limit=10)
            if critical:
                lines.append(f"{TIER_EMOJI['CRITICAL']} *CRITICOS ({len(critical)}):*")
                for lead in critical[:5]:
                    name = lead.get("name", "?")[:40]
                    score = lead.get("urgency_score", 0)
                    city = lead.get("city", "")
                    lines.append(f"  \u2022 *{name}* ({city}) — score {score}")
                if len(critical) > 5:
                    lines.append(f"  _+{len(critical) - 5} mais..._")
                lines.append("")

            # HOT — resumo
            hot = urgency_scorer.get_by_tier("HOT", limit=20)
            if hot:
                lines.append(f"{TIER_EMOJI['HOT']} *QUENTES ({len(hot)}):*")
                for lead in hot[:3]:
                    name = lead.get("name", "?")[:40]
                    score = lead.get("urgency_score", 0)
                    lines.append(f"  \u2022 {name} — score {score}")
                if len(hot) > 3:
                    lines.append(f"  _+{len(hot) - 3} mais..._")
                lines.append("")

            # WARM — apenas contagem
            warm = urgency_scorer.get_by_tier("WARM", limit=100)
            if warm:
                lines.append(f"{TIER_EMOJI['WARM']} Mornos: {len(warm)} lead(s)")

            # COLD — omitido
            if not critical and not hot and not warm:
                lines.append("Nenhum lead com urgencia relevante hoje.")

            lines.append(f"\n_Atualizado {datetime.now().strftime('%d/%m %H:%M')}_")
            return "\n".join(lines)

        except Exception as e:
            logger.error(f"Erro ao gerar digest: {e}")
            return f"\u26a0\ufe0f Erro ao gerar digest de urgencia: {e}"

    # ========================================================================
    # PRIORITIZED ACTIONS
    # ========================================================================

    def get_prioritized_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna lista priorizada de acoes sugeridas.

        Combina:
        1. Leads CRITICAL sem follow-up recente (prioridade maxima)
        2. Leads que responderam mas nao tiveram follow-up (inatividade)
        3. Leads HOT que podem receber follow-up
        4. Leads WARM com potencial

        Args:
            limit: Max acoes retornadas.

        Returns:
            Lista ordenada por prioridade: [{priority, company_id, name, action_type, description, urgency_tier}]
        """
        actions: List[Dict[str, Any]] = []

        try:
            # 1. CRITICAL leads
            from tools.urgency_scorer import urgency_scorer
            critical = urgency_scorer.get_by_tier("CRITICAL", limit=20)
            for lead in critical:
                actions.append({
                    "priority": 1,
                    "company_id": lead["id"],
                    "name": lead.get("name", "?"),
                    "action_type": "follow_up_urgente",
                    "description": f"Lead CRITICO (score {lead.get('urgency_score', 0)}) — acao imediata",
                    "urgency_tier": "CRITICAL",
                })
        except Exception as e:
            logger.debug(f"Error fetching critical leads: {e}")

        try:
            # 2. Inatividade (responderam sem follow-up)
            inactive = self.detect_inactivity(days=settings.URGENCY_INACTIVITY_DAYS)
            for lead in inactive[:5]:
                actions.append({
                    "priority": 2,
                    "company_id": lead["company_id"],
                    "name": lead.get("company_name", "?"),
                    "action_type": "inatividade",
                    "description": f"Respondeu ha {lead['days_since_reply']}d sem follow-up",
                    "urgency_tier": lead.get("urgency_tier", "?"),
                })
        except Exception as e:
            logger.debug(f"Error detecting inactivity: {e}")

        try:
            # 3. HOT leads
            from tools.urgency_scorer import urgency_scorer
            hot = urgency_scorer.get_by_tier("HOT", limit=10)
            for lead in hot[:5]:
                actions.append({
                    "priority": 3,
                    "company_id": lead["id"],
                    "name": lead.get("name", "?"),
                    "action_type": "follow_up_agendado",
                    "description": f"Lead QUENTE (score {lead.get('urgency_score', 0)}) — agendar follow-up",
                    "urgency_tier": "HOT",
                })
        except Exception as e:
            logger.debug(f"Error fetching hot leads: {e}")

        # Ordenar por prioridade e limitar
        actions.sort(key=lambda x: x["priority"])
        return actions[:limit]

    def format_actions_for_whatsapp(self, actions: List[Dict[str, Any]]) -> str:
        """Formata lista de acoes para WhatsApp.

        Args:
            actions: Lista de acoes priorizadas.

        Returns:
            String formatada para WhatsApp.
        """
        if not actions:
            return "\u2705 Nenhuma acao urgente no momento."

        lines: List[str] = ["\U0001f3af *O que fazer agora:*\n"]
        for i, action in enumerate(actions[:10], 1):
            emoji = TIER_EMOJI.get(action.get("urgency_tier", "COLD"), "\u26aa")
            name = action.get("name", "?")[:35]
            desc = action.get("description", "")[:60]
            lines.append(f"{i}. {emoji} *{name}*\n   {desc}")

        return "\n".join(lines)

    # ========================================================================
    # AUTO-DRAFT FOR CRITICAL
    # ========================================================================

    def auto_draft_followup(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Gera draft de follow-up para lead CRITICAL e coloca na approval_queue.

        NUNCA envia direto. Sempre status='pending' para revisao humana.

        Args:
            company_id: UUID da empresa.

        Returns:
            Dict com queue_id, subject, body_preview ou None se falhar.
        """
        try:
            # Buscar ultimo email enviado para esta empresa
            last_email = db.client.table("approval_queue").select(
                "id,contact_id,subject,body,follow_up_number"
            ).eq("company_id", company_id).eq(
                "status", "sent"
            ).order("sent_at", desc=True).limit(1).execute()

            if not last_email.data:
                logger.debug(f"Nenhum email anterior para {company_id}, skip auto-draft")
                return None

            email = last_email.data[0]
            fu_number = (email.get("follow_up_number") or 0) + 1

            # Verificar se ja tem draft pendente
            existing = db.client.table("approval_queue").select(
                "id", count="exact"
            ).eq("company_id", company_id).eq(
                "status", "pending_approval"
            ).execute()
            if existing.count and existing.count > 0:
                logger.debug(f"Ja existe draft pendente para {company_id}")
                return None

            # Gerar follow-up usando o follow_up_manager
            from workflows.follow_up_manager import generate_follow_up
            result = generate_follow_up(
                company_id=company_id,
                contact_id=email.get("contact_id"),
                original_queue_id=email["id"],
                follow_up_number=fu_number,
                original_subject=email.get("subject", ""),
                original_body=email.get("body", ""),
                follow_up_type="hot_click",
                tracking_signal={"opened": True, "clicked": True, "days_silent": 0, "current_fu_number": fu_number - 1},
            )

            if result:
                # Marcar metadata com fonte urgency
                try:
                    import json
                    db.client.table("approval_queue").update({
                        "metadata": json.dumps({
                            "source": "urgency_auto_draft",
                            "urgency_tier": "CRITICAL",
                        })
                    }).eq("id", result["queue_id"]).execute()
                except Exception:
                    pass

                logger.info(f"Auto-draft gerado para {company_id}", extra={
                    "queue_id": result.get("queue_id"),
                    "follow_up_number": fu_number,
                })
                return {
                    "queue_id": result.get("queue_id"),
                    "subject": result.get("subject", "")[:60],
                    "body_preview": result.get("body", "")[:100],
                    "company_id": company_id,
                }

            return None

        except Exception as e:
            logger.error(f"Erro no auto-draft: {e}", extra={"company_id": company_id})
            return None

    def generate_critical_drafts(self) -> Dict[str, Any]:
        """Gera auto-drafts para todos os leads CRITICAL sem follow-up recente.

        Returns:
            Dict com generated (count) e details (lista).
        """
        generated: int = 0
        details: List[Dict[str, Any]] = []

        try:
            from tools.urgency_scorer import urgency_scorer
            critical = urgency_scorer.get_by_tier("CRITICAL", limit=20)

            for lead in critical:
                cid = lead["id"]
                # Verificar se ja tem follow-up recente (ultimas 48h)
                try:
                    recent = db.client.table("approval_queue").select(
                        "id", count="exact"
                    ).eq("company_id", cid).gte(
                        "created_at",
                        (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
                    ).execute()
                    if recent.count and recent.count > 0:
                        continue  # Ja tem algo recente
                except Exception:
                    pass

                result = self.auto_draft_followup(cid)
                if result:
                    generated += 1
                    details.append({
                        "company_id": cid,
                        "name": lead.get("name", "?"),
                        "subject": result.get("subject", ""),
                    })

        except Exception as e:
            logger.error(f"Erro ao gerar critical drafts: {e}")

        return {"generated": generated, "details": details}

    # ========================================================================
    # TREND ALERTS
    # ========================================================================

    def detect_and_format_trends(self) -> Optional[str]:
        """Detecta mudancas de tier e formata para WhatsApp.

        Returns:
            String formatada ou None se sem mudancas.
        """
        try:
            from tools.urgency_scorer import urgency_scorer
            changes = urgency_scorer.detect_tier_changes(
                hours=settings.URGENCY_TREND_HOURS
            )

            if not changes:
                return None

            # Separar upgrades e downgrades
            tier_order = {"COLD": 0, "WARM": 1, "HOT": 2, "CRITICAL": 3}
            upgrades = [c for c in changes if tier_order.get(c["new_tier"], 0) > tier_order.get(c["old_tier"], 0)]
            downgrades = [c for c in changes if tier_order.get(c["new_tier"], 0) < tier_order.get(c["old_tier"], 0)]

            lines: List[str] = ["\U0001f4c8 *Mudancas de Tier:*\n"]

            if upgrades:
                lines.append("*Esquentando:*")
                for c in upgrades[:5]:
                    old_e = TIER_EMOJI.get(c["old_tier"], "")
                    new_e = TIER_EMOJI.get(c["new_tier"], "")
                    lines.append(
                        f"  \u2b06\ufe0f {old_e}\u2192{new_e} *{c['name'][:35]}* "
                        f"({c['old_score']}\u2192{c['new_score']})"
                    )

            if downgrades:
                lines.append("\n*Esfriando:*")
                for c in downgrades[:3]:
                    old_e = TIER_EMOJI.get(c["old_tier"], "")
                    new_e = TIER_EMOJI.get(c["new_tier"], "")
                    lines.append(
                        f"  \u2b07\ufe0f {old_e}\u2192{new_e} {c['name'][:35]} "
                        f"({c['old_score']}\u2192{c['new_score']})"
                    )

            return "\n".join(lines)

        except Exception as e:
            logger.debug(f"Trends detection: {e}")
            return None

    # ========================================================================
    # INACTIVITY DETECTION
    # ========================================================================

    def detect_inactivity(
        self, days: int = 5
    ) -> List[Dict[str, Any]]:
        """Detecta leads que responderam ha N+ dias sem follow-up posterior.

        Args:
            days: Threshold de dias sem follow-up apos reply.

        Returns:
            Lista: [{company_id, company_name, replied_at, days_since_reply, contact_name, urgency_tier}]
        """
        inactive: List[Dict[str, Any]] = []
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

            # Emails com reply anterior ao cutoff
            replied = db.client.table("approval_queue").select(
                "company_id,contact_id,replied_at,subject"
            ).eq("status", "sent").not_.is_("replied_at", "null").lte(
                "replied_at", cutoff
            ).execute().data or []

            for r in replied:
                cid = r.get("company_id")
                if not cid:
                    continue

                # Verificar se houve follow-up posterior
                try:
                    reply_dt = r["replied_at"]
                    subsequent = db.client.table("approval_queue").select(
                        "id", count="exact"
                    ).eq("company_id", cid).gte(
                        "created_at", reply_dt
                    ).neq("id", r.get("id", "")).execute()

                    if subsequent.count and subsequent.count > 0:
                        continue  # Ja tem follow-up posterior
                except Exception:
                    continue

                # Buscar nome da escola e tier
                name = "?"
                tier = "?"
                try:
                    comp = db.client.table("companies").select(
                        "name,urgency_tier"
                    ).eq("id", cid).limit(1).execute()
                    if comp.data:
                        name = comp.data[0].get("name", "?")
                        tier = comp.data[0].get("urgency_tier", "?")
                except Exception:
                    pass

                # Buscar nome do contato
                contact_name = "?"
                ct_id = r.get("contact_id")
                if ct_id:
                    try:
                        ct = db.client.table("contacts").select(
                            "full_name"
                        ).eq("id", ct_id).limit(1).execute()
                        if ct.data:
                            contact_name = ct.data[0].get("full_name", "?")
                    except Exception:
                        pass

                # Calcular dias desde reply
                try:
                    reply_time = datetime.fromisoformat(reply_dt.replace("Z", "+00:00"))
                    days_since = (datetime.now(timezone.utc) - reply_time).days
                except Exception:
                    days_since = days

                inactive.append({
                    "company_id": cid,
                    "company_name": name,
                    "replied_at": reply_dt,
                    "days_since_reply": days_since,
                    "contact_name": contact_name,
                    "urgency_tier": tier,
                    "subject": r.get("subject", "")[:50],
                })

        except Exception as e:
            logger.error(f"Erro ao detectar inatividade: {e}")

        # Ordenar por dias_since_reply DESC (mais urgente primeiro)
        inactive.sort(key=lambda x: x.get("days_since_reply", 0), reverse=True)
        return inactive

    def format_inactivity_for_whatsapp(
        self, inactive: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Formata alertas de inatividade para WhatsApp.

        Args:
            inactive: Lista de leads inativos.

        Returns:
            String formatada ou None se lista vazia.
        """
        if not inactive:
            return None

        lines: List[str] = ["\u23f3 *Leads aguardando follow-up:*\n"]
        for lead in inactive[:5]:
            name = lead.get("company_name", "?")[:35]
            days = lead.get("days_since_reply", 0)
            contact = lead.get("contact_name", "?")[:20]
            lines.append(
                f"  \u26a0\ufe0f *{name}*\n"
                f"     {contact} respondeu ha {days} dia(s)"
            )

        if len(inactive) > 5:
            lines.append(f"\n  _+{len(inactive) - 5} mais..._")

        return "\n".join(lines)


# Singleton
proactive_engine = ProactiveActionEngine()


# ============================================================================
# CLI para testes
# ============================================================================

if __name__ == "__main__":
    import sys as _sys

    cmd = _sys.argv[1] if len(_sys.argv) > 1 else "--digest"

    if cmd == "--digest":
        print(proactive_engine.generate_daily_digest())
    elif cmd == "--actions":
        actions = proactive_engine.get_prioritized_actions()
        print(proactive_engine.format_actions_for_whatsapp(actions))
    elif cmd == "--inactivity":
        inactive = proactive_engine.detect_inactivity()
        msg = proactive_engine.format_inactivity_for_whatsapp(inactive)
        print(msg or "Nenhuma inatividade detectada.")
    elif cmd == "--trends":
        msg = proactive_engine.detect_and_format_trends()
        print(msg or "Nenhuma mudanca de tier detectada.")
    elif cmd == "--drafts":
        result = proactive_engine.generate_critical_drafts()
        print(f"Drafts gerados: {result['generated']}")
        for d in result["details"]:
            print(f"  - {d['name']}: {d['subject']}")
    else:
        print("Usage: python tools/proactive_actions.py [--digest|--actions|--inactivity|--trends|--drafts]")
