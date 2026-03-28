"""IAprendo Sales Agent - Central de Comando (Material Design)."""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme, metric_card, section_header, alert_banner,
    COLORS, STATUS_COLORS, timeline_item,
)

apply_theme()

# =========================================================================
# SIDEBAR BRANDING
# =========================================================================
with st.sidebar:
    st.markdown(
        '<p style="text-align:center;padding:16px 0 8px 0;margin:0;border-bottom:1px solid #E0E0E0">'
        '<strong style="font-size:18px;color:#1976D2">🎓 IAprendo</strong><br/>'
        '<span style="font-size:11px;color:#9E9E9E">Agente de Vendas</span></p>',
        unsafe_allow_html=True,
    )

# =========================================================================
# HEADER
# =========================================================================
st.markdown(
    '<h1 style="margin-bottom:0">IAprendo Sales Agent</h1>'
    '<p style="color:#757575;margin-top:4px;font-size:15px">'
    'Central de comando &mdash; prospeccao B2B para escolas</p>',
    unsafe_allow_html=True,
)

# =========================================================================
# BUSCA GLOBAL
# =========================================================================
search_query = st.text_input(
    "Busca rapida",
    placeholder="Digite nome de escola, contato ou email...",
    key="global_search",
    label_visibility="collapsed",
)

if search_query and len(search_query) >= 2:
    try:
        from database.supabase_client import db
        term = f"%{search_query}%"

        schools = db.client.table("companies").select(
            "id,name,city,status,qualification_score"
        ).ilike("name", term).limit(10).execute().data or []

        contacts_name = db.client.table("contacts").select(
            "id,full_name,email,role,company_id,companies(name)"
        ).ilike("full_name", term).limit(10).execute().data or []

        contacts_email = db.client.table("contacts").select(
            "id,full_name,email,role,company_id,companies(name)"
        ).ilike("email", term).limit(10).execute().data or []

        contacts_all = {c["id"]: c for c in contacts_name + contacts_email}.values()
        total_results = len(schools) + len(list(contacts_all))

        if total_results > 0:
            st.caption(f"{total_results} resultado(s) encontrado(s)")
            if schools:
                section_header("Escolas", "school")
                for s in schools:
                    score = s.get("qualification_score") or 0
                    st.markdown(
                        f'<div class="data-card">'
                        f'<strong>{s["name"]}</strong> &mdash; {s.get("city", "?")}'
                        f'<br><span style="color:#757575;font-size:13px">'
                        f'Status: {s.get("status", "?")} &bull; Score: {score}</span></div>',
                        unsafe_allow_html=True,
                    )
            contacts_list = list(contacts_all)
            if contacts_list:
                section_header("Contatos", "person")
                for c in contacts_list:
                    comp = c.get("companies") or {}
                    st.markdown(
                        f'<div class="data-card">'
                        f'<strong>{c.get("full_name", "?")}</strong> ({c.get("role", "?")})'
                        f'<br><span style="color:#757575;font-size:13px">'
                        f'{c.get("email", "\u2014")} &bull; Escola: {comp.get("name", "?")}</span></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.caption(f"Nenhum resultado para '{search_query}'")
    except Exception as e:
        st.warning(f"Erro na busca: {e}")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =========================================================================
# CENTRAL DE COMANDO - KPIs
# =========================================================================
try:
    from database.supabase_client import db
    from approval_queue import queue_manager

    all_companies = db.client.table("companies").select(
        "id,status,qualification_score"
    ).execute().data or []
    stats = queue_manager.get_stats()

    total = len(all_companies)
    raw = len([c for c in all_companies if c.get("status") == "raw"])
    qualified = len([c for c in all_companies if c.get("status") == "qualified"])
    enriched = len([c for c in all_companies if c.get("status") == "enriched"])
    pending = stats.get("pending", 0)
    approved = stats.get("approved", 0)
    sent = stats.get("sent", 0)

    sent_items = db.client.table("approval_queue").select(
        "id,sent_at,opened_at,clicked_at,replied_at,bounced_at,follow_up_number"
    ).eq("status", "sent").execute().data or []

    opened = len([s for s in sent_items if s.get("opened_at")])
    clicked = len([s for s in sent_items if s.get("clicked_at")])
    replied = len([s for s in sent_items if s.get("replied_at")])

    try:
        from workflows.follow_up_manager import get_due_follow_ups
        due_fups = get_due_follow_ups(limit=50)
        due_count = len(due_fups)
    except Exception:
        due_count = 0

    try:
        from tools.notification_manager import notification_manager
        unread = notification_manager.get_unread_count()
    except Exception:
        unread = 0

    # === ALERT BANNERS ===
    if pending > 0:
        alert_banner(f"<strong>{pending} email(s)</strong> aguardando sua aprovacao na Fila de Aprovacao", "warning")
    if approved > 0:
        alert_banner(f"<strong>{approved} email(s)</strong> aprovados prontos para envio", "success")
    if due_count > 0:
        alert_banner(f"<strong>{due_count} escola(s)</strong> precisam de follow-up", "info")
    if unread > 0:
        alert_banner(f"<strong>{unread} notificacao(oes)</strong> nao lida(s)", "info")

    # === KPI ROW ===
    section_header("Resumo", "dashboard")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        metric_card("Escolas", total, icon="school", color=COLORS["primary"])
    with k2:
        metric_card("Pendentes", pending, icon="pending_actions", color=COLORS["warning"],
                     delta="acao" if pending > 0 else "")
    with k3:
        metric_card("Enviados", sent, icon="send", color=COLORS["secondary"])
    with k4:
        open_pct = f"{opened * 100 // sent}%" if sent else "0%"
        metric_card("Abertos", opened, icon="mark_email_read", color=COLORS["info"], delta=open_pct)
    with k5:
        reply_pct = f"{replied * 100 // sent}%" if sent else "0%"
        metric_card("Respondidos", replied, icon="reply", color=COLORS["success"], delta=reply_pct)
    with k6:
        metric_card("Follow-ups", due_count, icon="autorenew", color=COLORS["accent"],
                     delta="pendentes" if due_count > 0 else "")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # === QUICK ACTIONS (3x2 grid) ===
    section_header("Acoes Rapidas", "bolt")

    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        st.markdown(
            '<div class="data-card">'
            '<span class="material-icons-outlined" style="color:#1976D2;font-size:28px">rocket_launch</span>'
            '<h3 style="margin:8px 0 4px 0;font-size:16px!important">Pipeline</h3>'
            '<p style="color:#757575;font-size:13px;margin:0">Executar qualificacao e gerar emails</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Abrir Pipeline", key="goto_pipeline", use_container_width=True, type="primary"):
            st.switch_page("pages/1_📊_Pipeline.py")
    with ac2:
        st.markdown(
            f'<div class="data-card">'
            f'<span class="material-icons-outlined" style="color:#2E7D32;font-size:28px">task_alt</span>'
            f'<h3 style="margin:8px 0 4px 0;font-size:16px!important">Fila de Aprovacao</h3>'
            f'<p style="color:#757575;font-size:13px;margin:0">{pending} mensagem(ns) pendente(s)</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Aprovar Emails", key="goto_queue", use_container_width=True):
            st.switch_page("pages/6_✉️_Aprovacao.py")
    with ac3:
        st.markdown(
            f'<div class="data-card">'
            f'<span class="material-icons-outlined" style="color:#FF6D00;font-size:28px">autorenew</span>'
            f'<h3 style="margin:8px 0 4px 0;font-size:16px!important">Follow-ups</h3>'
            f'<p style="color:#757575;font-size:13px;margin:0">{due_count} escola(s) para follow-up</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Ver Follow-ups", key="goto_fups", use_container_width=True):
            st.switch_page("pages/7_🔄_Follow-ups.py")

    ac4, ac5, ac6 = st.columns(3)
    with ac4:
        st.markdown(
            '<div class="data-card">'
            '<span class="material-icons-outlined" style="color:#7B1FA2;font-size:28px">view_kanban</span>'
            '<h3 style="margin:8px 0 4px 0;font-size:16px!important">CRM</h3>'
            '<p style="color:#757575;font-size:13px;margin:0">Pipeline visual de vendas</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Abrir CRM", key="goto_crm", use_container_width=True):
            st.switch_page("pages/2_🎯_CRM.py")
    with ac5:
        st.markdown(
            '<div class="data-card">'
            '<span class="material-icons-outlined" style="color:#00897B;font-size:28px">contacts</span>'
            '<h3 style="margin:8px 0 4px 0;font-size:16px!important">Contatos</h3>'
            '<p style="color:#757575;font-size:13px;margin:0">Gerenciar decisores e contatos</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Ver Contatos", key="goto_contatos", use_container_width=True):
            st.switch_page("pages/5_👥_Contatos.py")
    with ac6:
        st.markdown(
            '<div class="data-card">'
            '<span class="material-icons-outlined" style="color:#1565C0;font-size:28px">map</span>'
            '<h3 style="margin:8px 0 4px 0;font-size:16px!important">Mapa</h3>'
            '<p style="color:#757575;font-size:13px;margin:0">Visualizacao geografica das escolas</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Ver Mapa", key="goto_mapa", use_container_width=True):
            st.switch_page("pages/4_🗺️_Mapa.py")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # === ATIVIDADE RECENTE ===
    section_header("Atividade Recente", "history")
    try:
        recent_sent = db.client.table("approval_queue").select(
            "subject,sent_at,companies(name),contacts(full_name)"
        ).eq("status", "sent").order("sent_at", desc=True).limit(5).execute().data or []

        if recent_sent:
            timeline_html = ""
            for item in recent_sent:
                comp = item.get("companies") or {}
                ct = item.get("contacts") or {}
                sent_at = (item.get("sent_at") or "")[:16].replace("T", " ")
                timeline_html += timeline_item(
                    date=sent_at,
                    title=f'{comp.get("name", "?")} \u2192 {ct.get("full_name", "?")}',
                    detail=item.get("subject", "")[:60],
                    color=COLORS["primary"],
                )
            st.markdown(timeline_html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma atividade recente.")
    except Exception:
        st.caption("Nenhuma atividade recente.")

    # === API USAGE ===
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Uso de APIs (ultimos 7 dias)", "api")
    try:
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        api_usage = db.client.table("api_usage").select(
            "api_name,credits_used"
        ).gte("created_at", seven_days_ago).execute().data or []

        if api_usage:
            api_costs = {}
            for u in api_usage:
                name = u.get("api_name", "?")
                api_costs[name] = api_costs.get(name, 0) + (u.get("credits_used") or 1)

            api_icons = {
                "anthropic": "smart_toy", "apollo": "search", "hunter": "mail",
                "snov": "contact_mail", "brevo": "send", "google": "cloud",
            }
            cost_cols = st.columns(min(len(api_costs), 5))
            for i, (api_name, count) in enumerate(sorted(api_costs.items(), key=lambda x: -x[1])):
                with cost_cols[i % len(cost_cols)]:
                    icon = api_icons.get(api_name.lower(), "memory")
                    metric_card(api_name.capitalize(), f"{count}", icon=icon,
                                color=COLORS["secondary"])
        else:
            st.caption("Nenhum uso de API registrado nos ultimos 7 dias.")
    except Exception:
        st.caption("Tabela api_usage nao disponivel.")

except Exception as e:
    st.warning(f"Nao foi possivel carregar dados: {e}")
    section_header("Como usar", "help")
    st.markdown("Use o **menu lateral** para navegar entre as paginas.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.caption("Fluxo: Importar \u2192 Pipeline \u2192 Aprovar \u2192 Enviar \u2192 Acompanhar no CRM")
