"""
Painel Diario Acionavel — Home Dashboard
===========================================

Transforma a Home de "KPIs + tiles" em "o que fazer agora?".

4 secoes ordenadas por prioridade:
1. Acao Imediata — CRITICAL urgency + replies high-intent + aprovados nao enviados
2. Aqueceu Hoje — tier changes 72h (principalmente para HOT/CRITICAL)
3. Agenda — reunioes proximas 24h (Outlook)
4. Aprovacao Pendente — fila > 24h sem action

Reaproveita:
- urgency_scorer.get_critical_leads(), detect_tier_changes()
- intent_detector.get_new_alerts()
- queue_manager.get_stats(), get_approved_not_sent()
- outlook_client.get_upcoming_events()
- proactive_engine.get_prioritized_actions()
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

import streamlit as st

try:
    from dashboard.theme import section_header, COLORS
except ImportError:
    def section_header(title: str, icon: str = "") -> None:
        st.markdown(f"### {title}")
    COLORS = {"primary": "#1976D2", "error": "#C62828", "warning": "#F57F17"}


# ============================================================================
# SECAO 1: ACAO IMEDIATA (CRITICAL + high intent + aprovados nao enviados)
# ============================================================================

def _acao_imediata_items() -> List[Dict[str, Any]]:
    """Coleta todas as acoes imediatas e retorna lista priorizada."""
    items: List[Dict[str, Any]] = []

    # 1a. Leads CRITICAL (urgency >= 80)
    try:
        from tools.urgency_scorer import urgency_scorer
        critical = urgency_scorer.get_critical_leads(limit=20) or []
        for lead in critical[:5]:  # so top 5 pra nao poluir
            items.append({
                "priority": 1,
                "icon": "\U0001f525",
                "title": f"Lead CRITICO: {lead.get('name', '?')}",
                "detail": f"Score {lead.get('urgency_score', '?')}/100 | {lead.get('city', '?')}/{lead.get('state', '?')}",
                "action_label": "Ver escola",
                "action_page": "pages/1_🏫_Escolas.py",
                "action_params": {"company_id": lead.get("id")},
                "company_id": lead.get("id"),
                "type": "critical_lead",
            })
    except Exception as e:
        pass

    # 1b. Replies com high intent (score >= 75)
    try:
        from tools.intent_detector import intent_detector
        alerts = intent_detector.get_new_alerts(days=7, min_score=75) or []
        for alert in alerts[:5]:
            items.append({
                "priority": 2,
                "icon": "\U0001f4ac",
                "title": f"Resposta recebida: {alert.get('company_name', '?')}",
                "detail": f"Score intent {alert.get('score', '?')}/100 | {', '.join(alert.get('reasons', [])[:2])}",
                "action_label": "Ver conversa",
                "action_page": "pages/6_✉️_Comunicacao.py",
                "action_params": {"filter": "replied", "queue_id": alert.get("queue_id")},
                "queue_id": alert.get("queue_id"),
                "type": "intent_reply",
            })
    except Exception as e:
        pass

    # 1c. Emails aprovados nao enviados
    try:
        from approval_queue.queue_manager import queue_manager
        approved_stuck = queue_manager.get_approved_not_sent(older_than_hours=1) if hasattr(queue_manager, "get_approved_not_sent") else []
        if approved_stuck:
            items.append({
                "priority": 3,
                "icon": "\U0001f4e4",
                "title": f"{len(approved_stuck)} emails aprovados aguardando envio",
                "detail": "Aprovados ha mais de 1h sem envio",
                "action_label": "Enviar todos",
                "action_page": "pages/6_✉️_Comunicacao.py",
                "action_params": {"tab": "approved"},
                "type": "approved_not_sent",
                "count": len(approved_stuck),
            })
    except Exception as e:
        pass

    # Ordenar por priority (menor = mais urgente)
    items.sort(key=lambda x: x.get("priority", 99))
    return items


# ============================================================================
# SECAO 2: AQUECEU HOJE (tier changes 72h)
# ============================================================================

def _aqueceu_hoje_items() -> List[Dict[str, Any]]:
    """Leads que mudaram de tier nas ultimas 72h (principalmente subindo)."""
    items: List[Dict[str, Any]] = []
    try:
        from tools.urgency_scorer import urgency_scorer
        changes = urgency_scorer.detect_tier_changes(hours=72) or []
        # Filtrar: so mostrar quem SUBIU de tier
        tier_order = {"COLD": 0, "WARM": 1, "HOT": 2, "CRITICAL": 3}
        upwards = [
            c for c in changes
            if tier_order.get(c.get("new_tier", "COLD"), 0) > tier_order.get(c.get("old_tier", "COLD"), 0)
        ]
        upwards.sort(key=lambda x: tier_order.get(x.get("new_tier", "COLD"), 0), reverse=True)

        for c in upwards[:5]:
            items.append({
                "name": c.get("name", "?"),
                "old_tier": c.get("old_tier", "?"),
                "new_tier": c.get("new_tier", "?"),
                "old_score": c.get("old_score", 0),
                "new_score": c.get("new_score", 0),
                "company_id": c.get("company_id"),
                "delta": (c.get("new_score", 0) - c.get("old_score", 0)),
            })
    except Exception:
        pass
    return items


# ============================================================================
# SECAO 3: AGENDA (Outlook upcoming 24h)
# ============================================================================

def _agenda_items() -> List[Dict[str, Any]]:
    """Reunioes proximas 24h via Outlook."""
    items: List[Dict[str, Any]] = []
    try:
        from integrations.outlook_client import outlook_client
        events = outlook_client.get_upcoming_events(hours=24) or []
        for ev in events[:10]:
            # Extrair info do evento (formato Microsoft Graph)
            subject = ev.get("subject", "?")
            start = ev.get("start", {}).get("dateTime", "")
            # Parse time pra exibir HH:MM
            try:
                dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                hour_str = dt.strftime("%H:%M")
                today = datetime.now(timezone.utc).date()
                if dt.date() == today:
                    when = f"Hoje {hour_str}"
                elif dt.date() == today + timedelta(days=1):
                    when = f"Amanha {hour_str}"
                else:
                    when = dt.strftime("%d/%m %H:%M")
            except Exception:
                when = start[:16] if start else "?"

            items.append({
                "when": when,
                "subject": subject,
                "location": (ev.get("location") or {}).get("displayName", ""),
            })
    except Exception:
        pass
    return items


# ============================================================================
# SECAO 4: APROVACAO PENDENTE (queue > 24h)
# ============================================================================

def _aprovacao_pendente_stats() -> Dict[str, int]:
    """Stats de aprovacao pendente + pendentes > 24h."""
    stats = {"pendentes": 0, "stuck_24h": 0}
    try:
        from approval_queue.queue_manager import queue_manager
        all_stats = queue_manager.get_stats() or {}
        stats["pendentes"] = all_stats.get("pending_approval", all_stats.get("pending", 0))

        # Query pendentes > 24h
        if hasattr(queue_manager, "get_pending_older_than"):
            stuck = queue_manager.get_pending_older_than(hours=24) or []
            stats["stuck_24h"] = len(stuck)
        else:
            # Fallback: query direta
            from database.supabase_client import db
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            r = db.client.table("approval_queue").select("id", count="exact").eq(
                "status", "pending_approval"
            ).lt("created_at", cutoff).execute()
            stats["stuck_24h"] = r.count or 0
    except Exception:
        pass
    return stats


# ============================================================================
# RENDER PRINCIPAL
# ============================================================================

def render_action_panel() -> None:
    """Renderiza o painel diario acionavel completo.

    4 secoes cronologicas:
    1. Acao Imediata
    2. Aqueceu Hoje
    3. Agenda
    4. Aprovacao Pendente
    """
    # =========== SECAO 1: ACAO IMEDIATA ===========
    acoes = _acao_imediata_items()
    section_header(f"Acao Imediata ({len(acoes)})", "priority_high")

    if not acoes:
        st.info("\U00002705 Nenhuma acao critica agora — pode focar em prospeccao.")
    else:
        for item in acoes[:8]:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f"<div style='padding:10px 14px; margin:4px 0; "
                    f"background:#FFF5F5; border-left:4px solid #E53935; border-radius:6px'>"
                    f"<b>{item['icon']} {item['title']}</b><br>"
                    f"<span style='color:#666; font-size:13px'>{item['detail']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col2:
                btn_key = f"action_{item['type']}_{item.get('company_id', item.get('queue_id', ''))}"
                if st.button(item["action_label"], key=btn_key, use_container_width=True):
                    if item.get("action_page"):
                        st.switch_page(item["action_page"])

    st.divider()

    # =========== SECAO 2: AQUECEU HOJE ===========
    aquecimentos = _aqueceu_hoje_items()
    section_header(f"Aqueceu nas Ultimas 72h ({len(aquecimentos)})", "trending_up")

    if not aquecimentos:
        st.caption("Sem mudancas de tier recentes.")
    else:
        try:
            from dashboard.helpers.urgency_widgets import urgency_badge_text
        except ImportError:
            urgency_badge_text = lambda t: t

        for item in aquecimentos:
            st.markdown(
                f"<div style='padding:8px 14px; margin:3px 0; background:#FFF3E0; border-radius:6px'>"
                f"<b>\U0001f4c8 {item['name']}</b>: "
                f"<span style='color:#888'>{item['old_tier']}</span> \u2192 "
                f"<b style='color:#FB8C00'>{item['new_tier']}</b> "
                f"(+{item['delta']:.0f} pts)"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # =========== SECAO 3: AGENDA ===========
    agenda = _agenda_items()
    section_header(f"Agenda 24h ({len(agenda)})", "event")

    if not agenda:
        st.caption("Sem reunioes agendadas para hoje/amanha.")
    else:
        for ev in agenda:
            st.markdown(
                f"<div style='padding:8px 14px; margin:3px 0; background:#E3F2FD; border-radius:6px'>"
                f"<b>\U0001f4c5 {ev['when']}</b> \u2014 {ev['subject']}"
                + (f"<br><span style='color:#888; font-size:12px'>\U0001f4cd {ev['location']}</span>" if ev['location'] else "")
                + f"</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # =========== SECAO 4: APROVACAO PENDENTE ===========
    queue_stats = _aprovacao_pendente_stats()
    pendentes = queue_stats.get("pendentes", 0)
    stuck = queue_stats.get("stuck_24h", 0)

    if pendentes > 0 or stuck > 0:
        section_header(f"Fila de Aprovacao ({pendentes} pendentes)", "mark_email_unread")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            st.metric("Total pendentes", pendentes)
        with c2:
            if stuck > 0:
                st.metric("Parados > 24h", stuck, delta="-0", delta_color="inverse")
            else:
                st.metric("Parados > 24h", 0)
        with c3:
            if st.button("Ir para fila", use_container_width=True, type="primary"):
                st.switch_page("pages/6_✉️_Comunicacao.py")
