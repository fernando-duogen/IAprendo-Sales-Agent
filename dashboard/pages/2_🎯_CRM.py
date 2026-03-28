"""
CRM - Visao unificada: Kanban + Metricas + Emails Enviados + WhatsApp.
Consolida a antiga pagina de Visao Geral com o CRM Kanban.
Material Design theme.
"""
import streamlit as st
import sys
import os
import urllib.parse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header, alert_banner,
    kanban_card, breadcrumb, status_badge, score_color, timeline_item,
    COLORS, STATUS_COLORS,
)

apply_theme_no_config()

# ======================================================================
# HEADER
# ======================================================================
breadcrumb(["Home", "CRM"])
st.markdown(
    '<h1 style="margin-bottom:0">CRM</h1>'
    '<p style="color:#757575;margin-top:4px;font-size:15px">'
    'Pipeline visual de vendas, metricas, emails enviados e WhatsApp.</p>',
    unsafe_allow_html=True,
)

KANBAN_STAGES = [
    {"key": "prospectado", "label": "Prospectado", "icon": "inventory_2", "color": "#5BA8E0", "desc": "Importadas e qualificadas"},
    {"key": "contatado", "label": "Contatado", "icon": "outgoing_mail", "color": "#48E0C0", "desc": "Email enviado"},
    {"key": "respondeu", "label": "Respondeu", "icon": "forum", "color": "#7B6FE0", "desc": "Recebemos resposta"},
    {"key": "reuniao", "label": "Reuniao", "icon": "event", "color": "#C47BD0", "desc": "Reuniao agendada/realizada"},
    {"key": "proposta", "label": "Proposta", "icon": "description", "color": "#E88FC5", "desc": "Proposta enviada"},
    {"key": "cliente", "label": "Cliente", "icon": "emoji_events", "color": "#2E7D32", "desc": "Fechou!"},
]

try:
    from database.supabase_client import db
    from approval_queue import queue_manager
    import pandas as pd

    # =========================================================================
    # SHARED DATA
    # =========================================================================
    companies = db.client.table("companies").select(
        "id,name,status,qualification_score,last_contacted_at,email_domain,notes"
    ).order("name").execute().data or []

    sent_emails = db.client.table("approval_queue").select(
        "company_id,sent_at,opened_at,clicked_at,replied_at,follow_up_number"
    ).eq("status", "sent").execute().data or []

    meetings_data = db.client.table("meetings").select("company_id,status").execute().data or []

    email_map = {}
    for e in sent_emails:
        cid = e["company_id"]
        if cid not in email_map:
            email_map[cid] = {"sent": 0, "opened": False, "clicked": False, "replied": False}
        email_map[cid]["sent"] += 1
        if e.get("opened_at"):
            email_map[cid]["opened"] = True
        if e.get("clicked_at"):
            email_map[cid]["clicked"] = True
        if e.get("replied_at"):
            email_map[cid]["replied"] = True

    meeting_map = {}
    for m in meetings_data:
        meeting_map[m["company_id"]] = m.get("status", "scheduled")

    # Classify companies by stage
    stages = {s["key"]: [] for s in KANBAN_STAGES}
    for comp in companies:
        cid = comp["id"]
        notes = (comp.get("notes") or "").lower()
        crm_override = None
        for s in KANBAN_STAGES:
            if f"[crm:{s['key']}]" in notes:
                crm_override = s["key"]
                break
        if crm_override:
            stages[crm_override].append(comp)
        elif cid in meeting_map:
            stages["reuniao"].append(comp)
        elif email_map.get(cid, {}).get("replied"):
            stages["respondeu"].append(comp)
        elif cid in email_map:
            stages["contatado"].append(comp)
        elif comp.get("status") in ("qualified", "enriched", "raw", "filtered"):
            stages["prospectado"].append(comp)

    # =========================================================================
    # KPI CARDS AT TOP
    # =========================================================================
    kc = st.columns(len(KANBAN_STAGES))
    for i, stage in enumerate(KANBAN_STAGES):
        count = len(stages[stage["key"]])
        with kc[i]:
            metric_card(stage["label"], count, icon=stage["icon"], color=stage["color"])

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # =========================================================================
    # TABS
    # =========================================================================
    tab_kanban, tab_metrics, tab_sent, tab_whatsapp = st.tabs([
        "Pipeline Kanban",
        "Metricas & Funil",
        "Emails Enviados",
        "WhatsApp",
    ])

    # =====================================================================
    # TAB 1: KANBAN
    # =====================================================================
    with tab_kanban:
        section_header("Pipeline Kanban", "view_kanban")
        cols = st.columns(len(KANBAN_STAGES))
        for i, stage in enumerate(KANBAN_STAGES):
            with cols[i]:
                # Column header
                st.markdown(
                    f'<div style="background:{stage["color"]}15;border-left:4px solid {stage["color"]};'
                    f'padding:10px 14px;border-radius:8px;margin-bottom:10px">'
                    f'<div style="display:flex;align-items:center;gap:6px">'
                    f'<span class="material-icons-outlined" style="font-size:18px;color:{stage["color"]}">{stage["icon"]}</span>'
                    f'<strong style="font-size:14px">{stage["label"]}</strong>'
                    f'<span class="badge" style="background:{stage["color"]}20;color:{stage["color"]};margin-left:auto">'
                    f'{len(stages[stage["key"]])}</span></div>'
                    f'<div style="font-size:11px;color:#9E9E9E;margin-top:4px">{stage["desc"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                items = stages[stage["key"]]
                if not items:
                    st.caption("Nenhuma escola")
                    continue
                for comp in sorted(items, key=lambda x: x.get("qualification_score") or 0, reverse=True):
                    score = comp.get("qualification_score") or 0
                    name = comp.get("name", "?")
                    domain = comp.get("email_domain") or ""
                    emails_info = email_map.get(comp["id"], {})

                    # Build subtitle
                    subtitle_parts = []
                    if domain:
                        subtitle_parts.append(domain)
                    if emails_info.get("sent"):
                        subtitle_parts.append(f"Emails: {emails_info['sent']}")
                    if emails_info.get("opened"):
                        subtitle_parts.append("Aberto")
                    if emails_info.get("clicked"):
                        subtitle_parts.append("Clicado")
                    subtitle = " | ".join(subtitle_parts)

                    st.markdown(
                        kanban_card(
                            name=name[:28],
                            subtitle=subtitle,
                            score=score,
                            color=stage["color"],
                        ),
                        unsafe_allow_html=True,
                    )

        # Move school between stages
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Mover Escola de Estagio", "swap_horiz")

        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            all_names = {c["name"]: c["id"] for c in companies}
            selected_name = st.selectbox("Escola:", list(all_names.keys()), key="crm_move")
        with mc2:
            target_stage = st.selectbox(
                "Mover para:",
                [s["label"] for s in KANBAN_STAGES],
                key="crm_target",
            )
        with mc3:
            st.markdown("")
            if st.button("Mover", type="primary", icon=":material/swap_horiz:",
                          use_container_width=True):
                comp_id = all_names[selected_name]
                stage_key = [s["key"] for s in KANBAN_STAGES if s["label"] == target_stage][0]
                try:
                    current = db.client.table("companies").select("notes").eq("id", comp_id).execute().data
                    current_notes = (current[0].get("notes") or "") if current else ""
                    for s in KANBAN_STAGES:
                        current_notes = current_notes.replace(f"[crm:{s['key']}]", "").strip()
                    new_notes = f"{current_notes} [crm:{stage_key}]".strip()
                    db.client.table("companies").update({"notes": new_notes}).eq("id", comp_id).execute()
                    st.toast(f"{selected_name} movida para {target_stage}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")

    # =====================================================================
    # TAB 2: METRICAS & FUNIL
    # =====================================================================
    with tab_metrics:
        # Status counts
        status_counts = {}
        for r in companies:
            s = r.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        total = len(companies)
        raw = status_counts.get("raw", 0)
        qualified = status_counts.get("qualified", 0)
        enriched = status_counts.get("enriched", 0)

        queue_stats = queue_manager.get_stats()
        pending = queue_stats.get("pending", 0)
        approved = queue_stats.get("approved", 0)
        total_sent = queue_stats.get("sent", 0)

        # Pipeline metrics
        section_header("Pipeline de Escolas", "school")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Total importadas", total, icon="inventory_2", color=COLORS["primary"])
        with c2:
            metric_card("Aguardando qualificacao", raw, icon="pending", color=STATUS_COLORS["raw"])
        with c3:
            metric_card("Qualificadas", qualified, icon="verified", color=STATUS_COLORS["qualified"])
        with c4:
            metric_card("Enriquecidas", enriched, icon="auto_fix_high", color=STATUS_COLORS["enriched"])

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Mensagens", "mail")
        m1, m2, m3 = st.columns(3)
        with m1:
            metric_card("Aguardando aprovacao", pending, icon="pending_actions", color=COLORS["warning"])
        with m2:
            metric_card("Aprovadas (nao enviadas)", approved, icon="check_circle", color=COLORS["success"])
        with m3:
            metric_card("Enviadas", total_sent, icon="send", color=COLORS["secondary"])

        # Conversion funnel
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Funil de Conversao", "filter_alt")
        funil = pd.DataFrame({
            "Etapa": ["Importadas", "Qualificadas", "Enriquecidas", "Com Mensagem", "Enviadas"],
            "Quantidade": [total, qualified, enriched, pending + approved + total_sent, total_sent],
        })
        st.bar_chart(funil.set_index("Etapa"), height=300)

        # Score distribution
        scores = [r.get("qualification_score") for r in companies if r.get("qualification_score") is not None]
        if scores:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            section_header("Distribuicao de Scores", "leaderboard")
            score_df = pd.DataFrame({"Score": scores})
            st.bar_chart(score_df["Score"].value_counts().sort_index(), height=250)

        # Export
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Exportar Relatorio", "download")
        ex1, ex2 = st.columns(2)
        with ex1:
            if st.button("Exportar escolas (CSV)", icon=":material/download:"):
                try:
                    all_data = db.client.table("companies").select("*").execute().data or []
                    if all_data:
                        export_df = pd.DataFrame(all_data)
                        csv_data = export_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Baixar CSV",
                            csv_data,
                            f"escolas_{datetime.now().strftime('%Y%m%d')}.csv",
                            "text/csv",
                        )
                    else:
                        alert_banner("Nenhum dado para exportar.", "info")
                except Exception as exp_err:
                    st.error(f"Erro: {exp_err}")
        with ex2:
            if st.button("Exportar contatos (CSV)", icon=":material/download:"):
                try:
                    all_contacts = db.client.table("contacts").select("*,companies(name)").execute().data or []
                    if all_contacts:
                        rows_exp = []
                        for c in all_contacts:
                            comp = c.pop("companies", {}) or {}
                            c["escola"] = comp.get("name", "")
                            rows_exp.append(c)
                        export_df = pd.DataFrame(rows_exp)
                        csv_data = export_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "Baixar CSV",
                            csv_data,
                            f"contatos_{datetime.now().strftime('%Y%m%d')}.csv",
                            "text/csv",
                        )
                    else:
                        alert_banner("Nenhum dado para exportar.", "info")
                except Exception as exp_err:
                    st.error(f"Erro: {exp_err}")

    # =====================================================================
    # TAB 3: EMAILS ENVIADOS
    # =====================================================================
    with tab_sent:
        section_header("Emails Enviados", "outgoing_mail")
        try:
            sent_items = db.client.table("approval_queue").select(
                "id, subject, body, sent_at, contact_id, company_id, follow_up_number, "
                "opened_at, clicked_at, replied_at, bounced_at, "
                "companies(name, city), contacts(full_name, email, role)"
            ).eq("status", "sent").order("sent_at", desc=True).limit(50).execute().data or []

            if sent_items:
                st.caption(f"{len(sent_items)} email(s) enviado(s)")
                for item in sent_items:
                    company_info = item.get("companies") or {}
                    contact_info = item.get("contacts") or {}
                    school = company_info.get("name", "?")
                    to_name = contact_info.get("full_name", "?")
                    to_email = contact_info.get("email", "?")
                    to_role = contact_info.get("role", "")
                    subject_text = item.get("subject", "")
                    sent_at = (item.get("sent_at") or "")[:16].replace("T", " ")
                    fu = item.get("follow_up_number", 0)
                    fu_label = f" [FU-{fu}]" if fu > 0 else ""

                    # Status badges
                    badges = ""
                    if item.get("opened_at"):
                        badges += status_badge("opened", "Aberto") + " "
                    if item.get("clicked_at"):
                        badges += status_badge("meeting", "Clicado") + " "
                    if item.get("replied_at"):
                        badges += status_badge("replied", "Respondido") + " "
                    if item.get("bounced_at"):
                        badges += status_badge("rejected", "Bounce") + " "

                    with st.expander(f"{sent_at} | {school} | {to_name}{fu_label}"):
                        # Badges at top of expander
                        if badges:
                            st.markdown(badges, unsafe_allow_html=True)

                        ec1, ec2 = st.columns([1, 2])
                        with ec1:
                            st.markdown(f"**Escola:** {school}")
                            st.markdown(f"**Para:** {to_name} ({to_role})")
                            st.markdown(f"**Email:** {to_email}")
                            st.markdown(f"**Enviado:** {sent_at}")
                            if fu > 0:
                                st.markdown(f"**Tipo:** Follow-up {fu}")
                            if item.get("opened_at"):
                                st.markdown(f"**Aberto em:** {item['opened_at'][:16]}")
                            if item.get("replied_at"):
                                st.markdown(f"**Respondido em:** {item['replied_at'][:16]}")

                            if st.button("Encaminhar para mim", key=f"fwd_{item['id']}",
                                          icon=":material/forward_to_inbox:"):
                                try:
                                    from tools.brevo_sender import brevo_sender
                                    from config.settings import settings
                                    my_email = settings.YOUR_EMAIL
                                    fwd_result = brevo_sender.send_email(
                                        to_email=my_email,
                                        to_name=settings.YOUR_NAME,
                                        subject=f"[FWD] {subject_text}",
                                        body=f"--- Email enviado para {to_name} ({to_email}) em {sent_at} ---\n\n{item.get('body', '')}",
                                    )
                                    if fwd_result.get("success"):
                                        st.toast(f"Encaminhado para {my_email}!")
                                    else:
                                        st.error(f"Falha: {fwd_result.get('error', '')}")
                                except Exception as fwd_err:
                                    st.error(f"Erro: {fwd_err}")
                        with ec2:
                            st.markdown(f"**Assunto:** {subject_text}")
                            st.text_area("Corpo:", value=item.get("body", ""), height=150,
                                disabled=True, key=f"sent_body_{item['id']}")
            else:
                alert_banner("Nenhum email enviado ainda.", "info")
        except Exception as e:
            st.warning(f"Erro ao carregar enviados: {e}")

    # =====================================================================
    # TAB 4: WHATSAPP
    # =====================================================================
    with tab_whatsapp:
        section_header("Contato Rapido via WhatsApp", "chat")
        st.caption("Gere links para contato direto via WhatsApp com escolas que tem telefone cadastrado.")

        # Filter by stage - horizontal bar
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        wa_stage_filter = st.multiselect(
            "Filtrar por estagio:",
            [s["label"] for s in KANBAN_STAGES],
            default=["Respondeu", "Reuniao"],
            key="wa_filter",
        )
        st.markdown('</div>', unsafe_allow_html=True)

        selected_keys = [s["key"] for s in KANBAN_STAGES if s["label"] in wa_stage_filter]

        wa_candidates = []
        for key in selected_keys:
            wa_candidates.extend(stages.get(key, []))

        if wa_candidates:
            meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "")
            found_any = False

            for comp in wa_candidates:
                try:
                    contacts = db.client.table("contacts").select(
                        "full_name,phone,role"
                    ).eq("company_id", comp["id"]).not_.is_("phone", "null").execute().data or []

                    phone_contacts = [ct for ct in contacts if ct.get("phone")]
                    if phone_contacts:
                        found_any = True
                        st.markdown(
                            f'<div class="data-card">'
                            f'<div style="font-weight:600;font-size:15px;margin-bottom:8px">{comp["name"]}</div>',
                            unsafe_allow_html=True,
                        )
                        for ct in phone_contacts[:3]:
                            phone = ct.get("phone", "")
                            clean = "".join(c for c in phone if c.isdigit())
                            if len(clean) == 10 or len(clean) == 11:
                                clean = "55" + clean
                            elif len(clean) < 10:
                                continue

                            msg = f"Ola {ct.get('full_name', '')}! Sou Fernando da IAprendo. Gostaria de apresentar nossa plataforma de IA educacional para a {comp['name']}. Podemos conversar?"
                            if meeting_link:
                                msg += f" Veja minha agenda: {meeting_link}"

                            wa_url = f"https://wa.me/{clean}?text={urllib.parse.quote(msg)}"
                            st.markdown(
                                f"**{ct.get('full_name', '?')}** ({ct.get('role', '?')}) "
                                f"&mdash; `{phone}` &mdash; [Abrir WhatsApp]({wa_url})"
                            )
                        st.markdown('</div>', unsafe_allow_html=True)
                except Exception:
                    pass

            if not found_any:
                alert_banner("Nenhum contato com telefone encontrado nas escolas selecionadas.", "info")
        else:
            alert_banner("Nenhuma escola nos estagios selecionados.", "info")

except Exception as e:
    st.error(f"Erro ao carregar CRM: {e}")
    import traceback
    st.code(traceback.format_exc())
