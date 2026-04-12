"""
Pagina 6 - Comunicacao: consolida Aprovacao, Follow-ups, Templates e Metricas.

Merge de 3 paginas originais em 4 tabs:
  - Aprovacao    (de 8_Aprovacao.py)
  - Follow-ups   (tabs 2+4 de 9_Follow-ups.py)
  - Templates    (de 10_Templates.py)
  - Metricas     (tabs 1+3 de 9_Follow-ups.py)
"""
import streamlit as st
import sys
import json
import re as _re
import pandas as pd
from pathlib import Path
from datetime import datetime, time as dtime, timedelta, timezone

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, avatar, timeline_item, breadcrumb, pipeline_stepper,
    COLORS, STATUS_COLORS, score_color,
)

apply_theme_no_config()

# ---------------------------------------------------------------------------
# Imports compartilhados (falha segura)
# ---------------------------------------------------------------------------
try:
    from approval_queue import queue_manager
    from database.supabase_client import db
    from utils.role_classifier import POWER_MAP_ROLES, ROLE_LABELS, ALL_ROLE_TYPES
    from utils.template_renderer import render_template, TEMPLATE_VARIABLES
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
breadcrumb(["IAprendo", "Comunicacao"])
st.markdown("# Comunicacao")
st.caption("Aprovacao, follow-ups, templates e metricas em um so lugar.")

# ---------------------------------------------------------------------------
# Session state defaults (prefixados para evitar colisao)
# ---------------------------------------------------------------------------
if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0
if "refresh" not in st.session_state:
    st.session_state.refresh = 0

# ---------------------------------------------------------------------------
# TABS PRINCIPAIS
# ---------------------------------------------------------------------------
tab_aprovacao, tab_followups, tab_templates, tab_metricas, tab_whatsapp = st.tabs([
    "📬 Aprovacao",
    "📨 Follow-ups",
    "📝 Templates",
    "📊 Metricas",
    "📱 WhatsApp",
])


# =============================================================================
# TAB 1: APROVACAO  (fonte: 8_Aprovacao.py)
# =============================================================================
with tab_aprovacao:

    # --- Carregar dados ---
    pending = queue_manager.get_pending(limit=50)
    total = len(pending)

    try:
        approved_count = (
            db.client.table("approval_queue")
            .select("id", count="exact")
            .eq("status", "approved")
            .execute()
        ).count or 0
    except Exception:
        approved_count = 0
    try:
        sent_count = (
            db.client.table("approval_queue")
            .select("id", count="exact")
            .eq("status", "sent")
            .execute()
        ).count or 0
    except Exception:
        sent_count = 0
    try:
        rejected_count = (
            db.client.table("approval_queue")
            .select("id", count="exact")
            .eq("status", "rejected")
            .execute()
        ).count or 0
    except Exception:
        rejected_count = 0

    # --- Metricas rapidas ---
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Pendentes", total, COLORS["warning"], icon="pending_actions")
    with mc2:
        metric_card("Aprovadas", approved_count, COLORS["success"], icon="check_circle")
    with mc3:
        metric_card("Enviadas", sent_count, COLORS["info"], icon="send")
    with mc4:
        metric_card("Rejeitadas", rejected_count, COLORS["error"], icon="cancel")

    st.markdown("")

    # --- Sub-tabs dentro de Aprovacao ---
    aprov_tab_pending, aprov_tab_approved, aprov_tab_sent = st.tabs([
        f"Pendentes ({total})",
        f"Aprovadas ({approved_count})",
        f"Enviadas ({sent_count})",
    ])

    # ---- Sub-tab: Aprovadas (aguardando envio) ----
    with aprov_tab_approved:
        try:
            approved_msgs = db.client.table("approval_queue").select(
                "id,subject,company_id,contact_id,channel,approved_at,scheduled_send_at,"
                "companies(name,city),contacts(full_name,email)"
            ).eq("status", "approved").is_("sent_at", "null").order(
                "approved_at", desc=True
            ).limit(50).execute().data or []
        except Exception:
            approved_msgs = []

        if not approved_msgs:
            alert_banner("Nenhuma mensagem aprovada aguardando envio.", "info")
        else:
            st.caption(f"{len(approved_msgs)} mensagem(ns) aprovada(s), aguardando envio.")

            for msg in approved_msgs:
                comp = msg.get("companies") or {}
                cont = msg.get("contacts") or {}
                sched = msg.get("scheduled_send_at")
                sched_label = ""
                if sched:
                    try:
                        sched_dt = datetime.fromisoformat(sched.replace("Z", "+00:00"))
                        sched_label = f" | Agendado: {sched_dt.strftime('%d/%m %H:%M')}"
                    except Exception:
                        sched_label = f" | {sched[:16]}"
                else:
                    sched_label = " | Envio imediato (proximo ciclo)"

                st.markdown(
                    f'<div class="data-card" style="border-left:4px solid {COLORS["success"]};padding:10px 14px">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<strong style="font-size:14px">{comp.get("name", "?")}</strong>'
                    f'<span style="font-size:11px;color:#757575">{(msg.get("approved_at") or "")[:10]}</span>'
                    f'</div>'
                    f'<div style="font-size:12px;color:#424242;margin-top:2px">{msg.get("subject", "")}</div>'
                    f'<div style="font-size:11px;color:#757575;margin-top:2px">'
                    f'Para: {cont.get("full_name", "?")} ({cont.get("email", "?")}){sched_label}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

            st.caption(
                "Mensagens sem agendamento serao enviadas automaticamente pelo scheduler (a cada 5 min). "
                "Mensagens agendadas serao enviadas no horario definido."
            )

    # ---- Sub-tab: Enviadas (historico com corpo completo) ----
    with aprov_tab_sent:
        try:
            sent_msgs = db.client.table("approval_queue").select(
                "id,subject,body,company_id,contact_id,sent_at,opened_at,clicked_at,replied_at,"
                "follow_up_number,companies(name,city),contacts(full_name,email)"
            ).eq("status", "sent").order("sent_at", desc=True).limit(50).execute().data or []
        except Exception:
            sent_msgs = []

        if not sent_msgs:
            alert_banner("Nenhuma mensagem enviada ainda.", "info")
        else:
            st.caption(f"Ultimas {len(sent_msgs)} mensagem(ns) enviada(s). Clique para ver o corpo completo.")

            for i, msg in enumerate(sent_msgs):
                comp = msg.get("companies") or {}
                cont = msg.get("contacts") or {}
                fu = msg.get("follow_up_number", 0) or 0
                fu_tag = f" (FU#{fu})" if fu > 0 else ""

                icons = []
                if msg.get("replied_at"):
                    icons.append("Respondeu")
                elif msg.get("clicked_at"):
                    icons.append("Clicou")
                elif msg.get("opened_at"):
                    icons.append("Abriu")
                else:
                    icons.append("Enviado")
                tracking = " / ".join(icons)

                border_color = COLORS["success"] if msg.get("replied_at") else (
                    COLORS["info"] if msg.get("clicked_at") or msg.get("opened_at") else "#9E9E9E"
                )

                escola_nome = comp.get("name", "?")
                sent_date = (msg.get("sent_at") or "")[:10]
                contato_info = f'{cont.get("full_name", "?")} ({cont.get("email", "?")})'

                with st.expander(f"{escola_nome}{fu_tag} -- {msg.get('subject', '')[:50]} | {sent_date} | {tracking}"):
                    st.markdown(
                        f'<div class="data-card" style="border-left:4px solid {border_color};padding:12px 16px">'
                        f'<div style="font-size:14px;font-weight:600;color:#212121">{escola_nome}{fu_tag}</div>'
                        f'<div style="font-size:12px;color:#757575;margin-top:2px">'
                        f'{comp.get("city", "")} | Para: {contato_info} | {tracking} | {sent_date}'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Assunto:** {msg.get('subject', '')}")
                    st.markdown("**Corpo:**")
                    st.text_area(
                        "Email enviado",
                        value=msg.get("body", ""),
                        height=250,
                        disabled=True,
                        key=f"sent_body_{msg['id']}",
                        label_visibility="collapsed",
                    )

    # ---- Sub-tab: Pendentes (tela principal de aprovacao) ----
    with aprov_tab_pending:

        if total == 0:
            alert_banner("Nenhuma mensagem aguardando aprovacao.", "success")
            alert_banner("Execute o pipeline para gerar novas mensagens e volte aqui para aprova-las.", "info")
            if st.button("Verificar novamente", icon=":material/refresh:", key="aprov_refresh"):
                st.rerun()
        else:
            st.markdown("")

            # --- Acoes em massa ---
            with st.expander("Acoes em massa", icon=":material/bolt:"):
                bulk_c1, bulk_c2, bulk_c3 = st.columns(3)
                with bulk_c1:
                    if st.button(f"Rejeitar todas ({total})", icon=":material/block:",
                                 help="Rejeita todas as mensagens pendentes", use_container_width=True,
                                 key="bulk_reject_btn"):
                        st.session_state["confirm_bulk_reject"] = True
                with bulk_c2:
                    if st.button(f"Excluir todas ({total})", icon=":material/delete:",
                                 help="Remove todas da fila (nao rejeita, apaga)", use_container_width=True,
                                 key="bulk_delete_btn"):
                        st.session_state["confirm_bulk_delete_queue"] = True
                with bulk_c3:
                    if st.button("Aprovar todas", icon=":material/done_all:",
                                 help="Aprova todas as mensagens pendentes", use_container_width=True,
                                 key="bulk_approve_btn"):
                        st.session_state["confirm_bulk_approve"] = True

                if st.session_state.get("confirm_bulk_reject"):
                    reason = st.text_input("Motivo da rejeicao em massa (opcional):", key="bulk_reject_reason")
                    br1, br2 = st.columns(2)
                    with br1:
                        if st.button("Sim, rejeitar todas", type="primary", key="confirm_bulk_reject_yes"):
                            count = 0
                            for p in pending:
                                if queue_manager.reject(p["id"], reason=reason):
                                    count += 1
                            st.success(f"{count} mensagens rejeitadas.")
                            st.session_state.pop("confirm_bulk_reject", None)
                            st.rerun()
                    with br2:
                        if st.button("Cancelar", key="cancel_bulk_reject"):
                            st.session_state.pop("confirm_bulk_reject", None)
                            st.rerun()

                if st.session_state.get("confirm_bulk_delete_queue"):
                    alert_banner("Isso vai APAGAR as mensagens da fila (nao apenas rejeitar). As escolas poderao receber novas mensagens no proximo pipeline.", "warning")
                    bd1, bd2 = st.columns(2)
                    with bd1:
                        if st.button("Sim, excluir todas da fila", type="primary", key="confirm_bulk_delete_yes"):
                            count = 0
                            for p in pending:
                                try:
                                    db.client.table("approval_queue").delete().eq("id", p["id"]).execute()
                                    count += 1
                                except Exception:
                                    pass
                            st.success(f"{count} mensagens excluidas da fila.")
                            st.session_state.pop("confirm_bulk_delete_queue", None)
                            st.rerun()
                    with bd2:
                        if st.button("Cancelar", key="cancel_bulk_delete"):
                            st.session_state.pop("confirm_bulk_delete_queue", None)
                            st.rerun()

                if st.session_state.get("confirm_bulk_approve"):
                    alert_banner("Isso vai APROVAR todas as mensagens pendentes.", "warning")

                    bulk_schedule = st.toggle("Agendar envio em massa", value=False, key="bulk_schedule_toggle")
                    bulk_sched_iso = None
                    if bulk_schedule:
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            bulk_date = st.date_input("Data", value=datetime.now().date() + timedelta(days=1), min_value=datetime.now().date(), key="bulk_sched_date")
                        with bc2:
                            bulk_time = st.time_input("Horario", value=dtime(8, 0), key="bulk_sched_time")
                        bulk_sched_dt = datetime.combine(bulk_date, bulk_time, tzinfo=timezone(timedelta(hours=-3)))
                        bulk_sched_iso = bulk_sched_dt.isoformat()
                        st.caption(f"Todas serao enviadas em {bulk_date.strftime('%d/%m/%Y')} as {bulk_time.strftime('%H:%M')}")

                    ba1, ba2 = st.columns(2)
                    with ba1:
                        label = "Sim, aprovar e agendar" if bulk_sched_iso else "Sim, aprovar todas"
                        if st.button(label, type="primary", key="confirm_bulk_approve_yes"):
                            count = 0
                            for p in pending:
                                if queue_manager.approve(p["id"], scheduled_send_at=bulk_sched_iso):
                                    count += 1
                            _msg = f"{count} mensagens aprovadas"
                            if bulk_sched_iso:
                                _msg += f" e agendadas para {bulk_date.strftime('%d/%m')} as {bulk_time.strftime('%H:%M')}"
                            st.success(_msg + ".")
                            st.session_state.pop("confirm_bulk_approve", None)
                            st.rerun()
                    with ba2:
                        if st.button("Cancelar", key="cancel_bulk_approve"):
                            st.session_state.pop("confirm_bulk_approve", None)
                            st.rerun()

            # --- Navegacao prev/next ---
            idx = min(st.session_state.current_idx, total - 1)
            st.session_state.current_idx = idx

            col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
            with col_nav1:
                if st.button("Anterior", disabled=(idx == 0), icon=":material/chevron_left:",
                             use_container_width=True, key="nav_prev"):
                    st.session_state.current_idx = max(0, idx - 1)
                    st.rerun()
            with col_nav2:
                progress_pct = (idx + 1) / total
                st.markdown(f"""
                <div style="text-align:center; padding:8px 0;">
                    <div style="font-size:18px; font-weight:600; color:#212121;">{idx+1} / {total}</div>
                    <div style="font-size:12px; color:#757575; margin-top:2px;">mensagens pendentes</div>
                    <div style="margin-top:8px; background:#E0E0E0; border-radius:4px; height:4px; width:100%;">
                        <div style="background:{COLORS['primary']}; border-radius:4px; height:4px; width:{progress_pct*100:.0f}%;"></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_nav3:
                if st.button("Proximo", disabled=(idx == total - 1), icon=":material/chevron_right:",
                             use_container_width=True, key="nav_next"):
                    st.session_state.current_idx = min(total - 1, idx + 1)
                    st.rerun()

            st.markdown("")

            # --- Item atual ---
            item = pending[idx]
            queue_id = item.get("id", "")
            company_data = item.get("companies") or {}
            contact_data = item.get("contacts") or {}
            contact_id = item.get("contact_id") or contact_data.get("id")
            company_id = item.get("company_id")

            col_info, col_msg = st.columns([1, 2])

            # --- Coluna esquerda: Info da escola e destinatario ---
            with col_info:
                school_name = company_data.get("name") or "Desconhecida"
                city = company_data.get("city") or ""
                state = company_data.get("state") or ""
                score = company_data.get("qualification_score")
                sc_val = score if score is not None else 0
                sc_col = score_color(sc_val) if score is not None else COLORS["on_surface_secondary"]

                score_html = ""
                if score is not None:
                    score_html = (
                        f'<div style="text-align:right;">'
                        f'<div style="font-size:24px;font-weight:700;color:{sc_col};">{sc_val}</div>'
                        f'<div style="font-size:10px;color:#757575;">score</div></div>'
                    )
                school_card_html = (
                    f'<div class="data-card" style="border-left:4px solid {COLORS["primary"]}">'
                    f'<div style="display:flex;align-items:center;gap:10px">'
                    f'{avatar(school_name, COLORS["primary"])}'
                    f'<div style="flex:1">'
                    f'<div style="font-weight:600;font-size:15px;color:#212121">{school_name}</div>'
                    f'<div style="font-size:12px;color:#757575">{city}{", " + state if state else ""}</div>'
                    f'</div>{score_html}</div></div>'
                )
                st.markdown(school_card_html, unsafe_allow_html=True)

                reasoning = company_data.get("qualification_reasoning", "")
                if reasoning:
                    with st.expander("Ver raciocinio da IA", icon=":material/psychology:"):
                        st.write(reasoning)

                # Buscar TODOS os contatos da escola
                all_school_contacts = []
                if company_id:
                    try:
                        all_school_contacts = db.client.table("contacts").select(
                            "id,full_name,email,role,decision_maker_type,outreach_priority,source"
                        ).eq("company_id", company_id).order("outreach_priority").execute().data or []
                    except Exception:
                        pass

                # Seletor de Destinatario
                section_header("Destinatario", "person")

                contacts_with_email = [c for c in all_school_contacts if c.get("email")]
                contact_email = contact_data.get("email") or ""

                if contacts_with_email:
                    option_ids = [c["id"] for c in contacts_with_email]
                    option_labels = []
                    best_priority_id = contacts_with_email[0]["id"]
                    for c in contacts_with_email:
                        role_label = c.get("role", "") or ROLE_LABELS.get(c.get("decision_maker_type", "outro"), "Outro")
                        marker = " (recomendado)" if c["id"] == best_priority_id else ""
                        option_labels.append(f"{c.get('full_name', '?')} ({role_label}) -- {c['email']}{marker}")

                    current_idx_sel = 0
                    if contact_id and contact_id in option_ids:
                        current_idx_sel = option_ids.index(contact_id)

                    selected_idx = st.selectbox(
                        "Enviar para:",
                        range(len(option_ids)),
                        format_func=lambda i: option_labels[i],
                        index=current_idx_sel,
                        key=f"recipient_{queue_id}",
                    )
                    selected_contact_id = option_ids[selected_idx]
                    selected_contact = contacts_with_email[selected_idx]

                    # Se mudou destinatario
                    if selected_contact_id != contact_id:
                        if st.button("Confirmar troca de destinatario", key=f"change_recipient_{queue_id}",
                                     icon=":material/swap_horiz:"):
                            ok = db.set_contact_on_queue(queue_id, selected_contact_id)
                            if ok:
                                new_name = selected_contact.get("full_name", "")
                                new_first = new_name.split()[0] if new_name and new_name != "Diretor(a)" else ""
                                fresh = db.client.table("approval_queue").select("body").eq("id", queue_id).single().execute()
                                current_body = fresh.data.get("body", "") if fresh.data else item.get("body", "")
                                updated_body = current_body

                                if new_first:
                                    updated_body = _re.sub(
                                        r'(Prezad[oa](?:\(a\))?|Car[oa](?:\(a\))?|Ol[aá])\s+'
                                        r'[A-Za-z\u00C0-\u00FC]+(?:\(a\))?',
                                        lambda m: f"{m.group(1)} {new_first}",
                                        updated_body,
                                        count=1,
                                    )
                                    old_name = contact_data.get("full_name", "") if contact_data else ""
                                    if old_name and old_name != new_name and old_name in updated_body:
                                        updated_body = updated_body.replace(old_name, new_name)

                                try:
                                    db.client.table("approval_queue").update({"body": updated_body}).eq("id", queue_id).execute()
                                except Exception:
                                    pass
                                st.success("Destinatario atualizado e nome no corpo ajustado!")
                                st.rerun()
                            else:
                                st.error("Falha ao atualizar destinatario.")

                    # Warning se nao e diretor
                    sel_dm = selected_contact.get("decision_maker_type", "outro")
                    if sel_dm != "diretor":
                        sel_label = ROLE_LABELS.get(sel_dm, "Outro")
                        alert_banner(f"Enviando para {sel_label}, nao para Diretor(a)", "warning")

                    contact_email = selected_contact.get("email", "")
                    contact_name = selected_contact.get("full_name", "?")
                    sel_source = selected_contact.get("source", "")

                    dest_color = COLORS["success"] if contact_email else COLORS["error"]
                    pattern_warning = (
                        '<div style="font-size:10px;color:#9E9E9E">Email gerado automaticamente -- verifique</div>'
                        if sel_source == "email_pattern" else ""
                    )
                    contact_card_html = (
                        f'<div class="data-card" style="border-left:4px solid {dest_color}">'
                        f'<div style="display:flex;align-items:center;gap:10px">'
                        f'{avatar(contact_name, dest_color)}'
                        f'<div>'
                        f'<div style="font-weight:600;font-size:14px">{contact_name}</div>'
                        f'<div style="font-size:12px;color:{dest_color}">{contact_email}</div>'
                        f'{pattern_warning}'
                        f'</div></div></div>'
                    )
                    st.markdown(contact_card_html, unsafe_allow_html=True)
                else:
                    alert_banner("Nenhum contato com email nesta escola!", "warning")
                    contact_name = contact_data.get("full_name") or "Nao identificado"
                    new_email = st.text_input(
                        "Email do contato:",
                        placeholder="diretor@escola.com.br",
                        key=f"new_email_{queue_id}"
                    )
                    if st.button("Salvar Email", key=f"save_email_{queue_id}", icon=":material/save:"):
                        if new_email and "@" in new_email and "." in new_email:
                            saved = False
                            if contact_id:
                                saved = db.update_contact(contact_id, {"email": new_email})
                            else:
                                name_to_use = contact_name if contact_name != "Nao identificado" else "Diretor(a)"
                                new_cid = db.insert_contact({
                                    "company_id": company_id,
                                    "full_name": name_to_use,
                                    "role": "Diretor(a)",
                                    "email": new_email,
                                    "source": "manual",
                                    "decision_maker_type": "diretor",
                                    "outreach_priority": 1,
                                })
                                if new_cid:
                                    saved = db.set_contact_on_queue(queue_id, new_cid)
                            if saved:
                                st.success("Email salvo! Pode aprovar e enviar agora.")
                                st.rerun()
                            else:
                                st.error("Falha ao salvar email.")
                        else:
                            st.error("Digite um email valido (ex: contato@escola.com.br)")

                # Mini Mapa de Poder
                if company_id and all_school_contacts:
                    st.markdown("")
                    section_header("Mapa de Poder", "account_tree")
                    for role_key in POWER_MAP_ROLES:
                        role_label = ROLE_LABELS.get(role_key, role_key)
                        role_cts = [c for c in all_school_contacts if c.get("decision_maker_type") == role_key]
                        if not role_cts:
                            st.markdown(f"""
                            <div style="font-size:13px; padding:3px 0; color:#9E9E9E;">
                                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#E0E0E0; margin-right:6px;"></span>
                                {role_label}: <em>nenhum</em>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            has_email = any(c.get("email") for c in role_cts)
                            dot_color = COLORS["success"] if has_email else COLORS["warning"]
                            is_current = any(c.get("id") == contact_id for c in role_cts)
                            arrow = ' <span style="color:#1976D2; font-weight:600; font-size:11px;">&#8592; esta msg</span>' if is_current else ""
                            names = ", ".join(c.get("full_name", "?") for c in role_cts)
                            st.markdown(f"""
                            <div style="font-size:13px; padding:3px 0;">
                                <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:{dot_color}; margin-right:6px;"></span>
                                <strong>{role_label}:</strong> {names}{arrow}
                            </div>
                            """, unsafe_allow_html=True)

                # Enviar tambem para outros contatos
                if contacts_with_email and len(contacts_with_email) > 1:
                    st.markdown("")
                    section_header("Enviar tambem para", "group_add")
                    st.caption("Selecione outros contatos para receber a mesma mensagem ao aprovar.")
                    extra_contact_ids = []
                    for c in contacts_with_email:
                        if c["id"] == (selected_contact_id if contacts_with_email else contact_id):
                            continue
                        role_label = c.get("role", "") or ROLE_LABELS.get(c.get("decision_maker_type", "outro"), "Outro")
                        label = f"{c.get('full_name', '?')} ({role_label}) -- {c['email']}"
                        if st.checkbox(label, key=f"extra_{queue_id}_{c['id']}"):
                            extra_contact_ids.append(c["id"])
                    if extra_contact_ids:
                        alert_banner(f"{len(extra_contact_ids)} destinatario(s) extra(s) serao adicionados a fila ao aprovar.", "info")
                        st.session_state[f"extra_contacts_{queue_id}"] = extra_contact_ids
                    else:
                        st.session_state.pop(f"extra_contacts_{queue_id}", None)

            # --- Coluna direita: Preview e edicao da mensagem ---
            with col_msg:
                current_subject = item.get("subject", "")
                current_body = item.get("body", "")
                follow_up_number = item.get("follow_up_number", 0) or 0
                parent_id = item.get("parent_id")

                # Historico de mensagens anteriores (para follow-ups)
                if follow_up_number > 0 and parent_id:
                    chain = []
                    current_parent = parent_id
                    visited = set()
                    while current_parent and current_parent not in visited and len(chain) < 5:
                        visited.add(current_parent)
                        try:
                            prev = db.client.table("approval_queue").select(
                                "id,subject,body,follow_up_number,sent_at,status,parent_id,"
                                "opened_at,clicked_at,replied_at"
                            ).eq("id", current_parent).single().execute()
                            if prev.data:
                                chain.append(prev.data)
                                current_parent = prev.data.get("parent_id")
                            else:
                                break
                        except Exception:
                            break

                    if chain:
                        chain.reverse()

                        fu_type_tag = ""
                        for tag in ("hot_click", "curious_open", "silent_open", "revival"):
                            if tag in (item.get("original_body") or "") or tag in (item.get("body") or ""):
                                fu_type_tag = tag
                                break

                        fu_label = f"Follow-up #{follow_up_number}"
                        st.markdown(
                            f'<div class="data-card" style="border-left:4px solid #FF6D00;padding:12px 16px">'
                            f'<div style="display:flex;align-items:center;gap:8px">'
                            f'<span class="material-icons-outlined" style="color:#FF6D00;font-size:20px">history</span>'
                            f'<span style="font-weight:600;font-size:14px;color:#FF6D00">'
                            f'{fu_label} -- {len(chain)} mensagem(ns) anterior(es)</span>'
                            f'</div></div>',
                            unsafe_allow_html=True,
                        )

                        with st.expander(f"Ver mensagens anteriores ({len(chain)})", expanded=True):
                            for i_prev, prev_msg in enumerate(chain):
                                prev_fu = prev_msg.get("follow_up_number", 0) or 0
                                prev_label = "Email original" if prev_fu == 0 else f"Follow-up #{prev_fu}"
                                prev_sent = (prev_msg.get("sent_at") or "")[:10]
                                prev_status = prev_msg.get("status", "")

                                tracking_icons = []
                                if prev_msg.get("opened_at"):
                                    tracking_icons.append("Abriu")
                                if prev_msg.get("clicked_at"):
                                    tracking_icons.append("Clicou")
                                if prev_msg.get("replied_at"):
                                    tracking_icons.append("Respondeu")
                                if not tracking_icons and prev_status == "sent":
                                    tracking_icons.append("Enviado, sem abertura")
                                tracking_text = " / ".join(tracking_icons) if tracking_icons else ""

                                border_color = "#E0E0E0" if prev_fu == 0 else "#BDBDBD"
                                st.markdown(
                                    f'<div style="border-left:3px solid {border_color};padding:8px 12px;'
                                    f'margin-bottom:8px;background:#FAFAFA;border-radius:0 6px 6px 0">'
                                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                                    f'<strong style="font-size:13px;color:#424242">{prev_label}</strong>'
                                    f'<span style="font-size:11px;color:#9E9E9E">{prev_sent}</span>'
                                    f'</div>'
                                    f'<div style="font-size:12px;color:#1976D2;margin:2px 0">{prev_msg.get("subject", "")}</div>'
                                    f'<div style="font-size:12px;color:#616161;white-space:pre-wrap;'
                                    f'max-height:120px;overflow-y:auto;margin-top:4px">'
                                    f'{prev_msg.get("body") or ""}</div>'
                                    f'{f"<div style=font-size:11px;color:#757575;margin-top:4px>{tracking_text}</div>" if tracking_text else ""}'
                                    f'</div>',
                                    unsafe_allow_html=True,
                                )

                # Email preview card
                preview_label = f"Follow-up #{follow_up_number}" if follow_up_number > 0 else "Email"
                preview_icon_color = "#FF6D00" if follow_up_number > 0 else COLORS["info"]
                st.markdown(
                    f'<div class="data-card" style="border-left:4px solid {preview_icon_color};padding:20px">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
                    f'<span class="material-icons-outlined" style="color:{preview_icon_color}">email</span>'
                    f'<span style="font-weight:600;font-size:16px;color:#212121">Preview -- {preview_label}</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

                edited_subject = st.text_input("Assunto:", value=current_subject, key=f"subj_{queue_id}")
                edited_body = st.text_area("Corpo:", value=current_body, height=350, key=f"body_{queue_id}")
                subject_changed = edited_subject != current_subject
                body_changed = edited_body != current_body
                if subject_changed or body_changed:
                    alert_banner("Mensagem editada -- sera salva ao aprovar.", "info")
                if not contact_email:
                    alert_banner("Adicione o email do contato (coluna esquerda) antes de aprovar para garantir o envio.", "warning")

                # --- Preview de graficos de insight (se houver) ---
                _raw_charts = item.get("chart_urls")
                _parsed_charts = None
                if _raw_charts:
                    try:
                        _parsed_charts = json.loads(_raw_charts) if isinstance(_raw_charts, str) else _raw_charts
                    except Exception:
                        _parsed_charts = None
                if _parsed_charts:
                    st.markdown("**📊 Graficos incluidos no email:**")
                    for _ch in _parsed_charts:
                        _ch_url = _ch.get("url", "")
                        _ch_alt = _ch.get("alt", "Grafico")
                        if _ch_url:
                            st.image(_ch_url, caption=_ch_alt, use_container_width=True)
                    st.caption("Estes graficos serao inseridos no final do email, antes da assinatura.")

                # --- Botao enviar teste para mim ---
                import os as _os
                _test_email = _os.getenv("YOUR_EMAIL", "")
                if _test_email and st.button(
                    f"📧 Enviar teste para {_test_email.split('@')[0]}",
                    key=f"test_send_{queue_id}",
                ):
                    try:
                        from tools.brevo_sender import brevo_sender as _bs
                        _test_result = _bs.send_email(
                            to_email=_test_email,
                            to_name="Teste",
                            subject=f"[TESTE] {edited_subject if subject_changed else current_subject}",
                            body=edited_body if body_changed else current_body,
                            chart_urls=_parsed_charts,
                        )
                        if _test_result.get("success"):
                            st.success(f"Teste enviado para {_test_email}")
                        else:
                            st.error(f"Erro: {_test_result.get('error', '?')}")
                    except Exception as _e:
                        st.error(f"Erro ao enviar teste: {_e}")

            # --- Agendamento de envio ---
            existing_sched = item.get("scheduled_send_at")
            if existing_sched:
                try:
                    sched_preview = datetime.fromisoformat(existing_sched.replace("Z", "+00:00"))
                    st.markdown(
                        f'<div style="font-size:13px;color:#FF6D00;margin-bottom:8px">'
                        f'Envio sugerido: {sched_preview.strftime("%d/%m/%Y as %H:%M")} '
                        f'(calendario inteligente)</div>',
                        unsafe_allow_html=True,
                    )
                except Exception:
                    pass

            schedule_send = st.toggle(
                "Alterar horario de envio",
                value=False,
                key=f"schedule_toggle_{queue_id}",
                help="Altere o horario sugerido ou defina um novo.",
            )

            scheduled_send_at_iso = existing_sched  # Manter sugestao por default

            if schedule_send:
                col_date, col_time = st.columns(2)
                with col_date:
                    tomorrow = datetime.now().date() + timedelta(days=1)
                    sched_date = st.date_input(
                        "Data de envio",
                        value=tomorrow,
                        min_value=datetime.now().date(),
                        key=f"sched_date_{queue_id}",
                    )
                with col_time:
                    sched_time = st.time_input(
                        "Horario de envio",
                        value=dtime(8, 0),
                        key=f"sched_time_{queue_id}",
                    )
                sched_dt = datetime.combine(sched_date, sched_time, tzinfo=timezone(timedelta(hours=-3)))
                scheduled_send_at_iso = sched_dt.isoformat()
                st.markdown(
                    f'<div style="font-size:13px;color:#FF6D00;margin-top:4px">'
                    f'Email sera enviado em <strong>{sched_date.strftime("%d/%m/%Y")} as {sched_time.strftime("%H:%M")}</strong> (horario de Brasilia)'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # --- Botoes de acao ---
            st.markdown("")

            st.markdown("""
            <style>
            div[data-testid="stHorizontalBlock"] > div:nth-child(1) .stButton > button {
                background-color: #2E7D32 !important;
                color: white !important;
                font-size: 16px !important;
                padding: 12px 24px !important;
                font-weight: 600 !important;
            }
            div[data-testid="stHorizontalBlock"] > div:nth-child(1) .stButton > button:hover {
                background-color: #1B5E20 !important;
                box-shadow: 0 4px 12px rgba(46,125,50,0.3) !important;
            }
            </style>
            """, unsafe_allow_html=True)

            btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

            with btn_col1:
                if st.button("Aprovar", type="primary", use_container_width=True, key=f"approve_{queue_id}",
                             icon=":material/check_circle:"):
                    sub = edited_subject if subject_changed else None
                    bod = edited_body if body_changed else None
                    ok = queue_manager.approve(
                        queue_id, edited_subject=sub, edited_body=bod,
                        scheduled_send_at=scheduled_send_at_iso,
                    )
                    if ok:
                        extra_ids = st.session_state.get(f"extra_contacts_{queue_id}", [])
                        extra_count = 0
                        for extra_cid in extra_ids:
                            try:
                                final_subject = edited_subject if subject_changed else current_subject
                                final_body = edited_body if body_changed else current_body
                                extra_data = {
                                    "company_id": company_id,
                                    "contact_id": extra_cid,
                                    "subject": final_subject,
                                    "body": final_body,
                                    "channel": "email",
                                    "status": "approved",
                                    "original_subject": current_subject,
                                    "original_body": current_body,
                                }
                                if scheduled_send_at_iso:
                                    extra_data["scheduled_send_at"] = scheduled_send_at_iso
                                db.client.table("approval_queue").insert(extra_data).execute()
                                extra_count += 1
                            except Exception:
                                pass
                        st.session_state.pop(f"extra_contacts_{queue_id}", None)
                        _msg = "Mensagem aprovada!"
                        if extra_count:
                            _msg += f" + {extra_count} copia(s) para outros contatos."
                        st.success(_msg)
                        st.session_state.current_idx = max(0, idx)
                        st.session_state.refresh += 1
                        st.rerun()
                    else:
                        st.error("Falha ao aprovar.")

            with btn_col2:
                if st.button("Usar Template", use_container_width=True, key=f"template_{queue_id}",
                             help="Substitui a mensagem IA pelo seu template padrao",
                             icon=":material/description:"):
                    st.session_state[f"show_template_{queue_id}"] = True

            with btn_col3:
                if st.button("Enviar Teste", use_container_width=True, key=f"test_{queue_id}",
                             help="Envia esta mensagem para um email de teste (sem aprovar)",
                             icon=":material/send:"):
                    st.session_state[f"show_test_{queue_id}"] = True

            with btn_col4:
                if st.button("Rejeitar", use_container_width=True, key=f"reject_{queue_id}",
                             icon=":material/cancel:"):
                    st.session_state[f"show_reject_{queue_id}"] = True

            # --- Paineis expandiveis: Rejeicao, Template, Teste ---

            # Rejeitar
            if st.session_state.get(f"show_reject_{queue_id}", False):
                st.divider()
                st.markdown(f"""
                <div class="data-card" style="border-left: 4px solid {COLORS['error']};">
                    <div style="font-weight:600; color:{COLORS['error']};">Rejeitar mensagem</div>
                </div>
                """, unsafe_allow_html=True)
                reason = st.text_input("Motivo da rejeicao (opcional):", key=f"reason_{queue_id}")
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    if st.button("Confirmar Rejeicao", type="primary", key=f"confirm_reject_{queue_id}",
                                 icon=":material/block:"):
                        ok = queue_manager.reject(queue_id, reason=reason)
                        if ok:
                            st.warning("Mensagem rejeitada.")
                            st.session_state[f"show_reject_{queue_id}"] = False
                            st.session_state.refresh += 1
                            st.rerun()
                with rcol2:
                    if st.button("Cancelar", key=f"cancel_reject_{queue_id}"):
                        st.session_state[f"show_reject_{queue_id}"] = False
                        st.rerun()

            # Template
            if st.session_state.get(f"show_template_{queue_id}", False):
                st.divider()
                st.markdown(f"""
                <div class="data-card" style="border-left: 4px solid {COLORS['info']};">
                    <div style="font-weight:600; color:{COLORS['info']};">Substituir mensagem pelo template padrao</div>
                </div>
                """, unsafe_allow_html=True)
                try:
                    tmpl_result = db.client.table("message_templates").select("*").eq("is_active", True).eq("is_default", True).limit(1).execute()
                    if not tmpl_result.data:
                        tmpl_result = db.client.table("message_templates").select("*").eq("is_active", True).limit(1).execute()
                    if tmpl_result.data:
                        tmpl = tmpl_result.data[0]
                        full_company = db.get_company_detail(company_id) if company_id else company_data
                        sel_contact = {}
                        if contacts_with_email:
                            sel_contact = selected_contact
                        elif contact_data:
                            sel_contact = contact_data
                        rendered = render_template(tmpl["subject_template"], tmpl["body_template"], full_company or company_data, sel_contact)
                        st.text_input("Assunto (template):", value=rendered["subject"], disabled=True, key=f"tmpl_subj_{queue_id}")
                        st.text_area("Corpo (template):", value=rendered["body"], height=200, disabled=True, key=f"tmpl_body_{queue_id}")
                        tc1, tc2 = st.columns(2)
                        with tc1:
                            if st.button("Aplicar template", type="primary", key=f"apply_tmpl_{queue_id}",
                                         icon=":material/check:"):
                                try:
                                    db.client.table("approval_queue").update({
                                        "subject": rendered["subject"],
                                        "body": rendered["body"],
                                    }).eq("id", queue_id).execute()
                                    st.session_state[f"subj_{queue_id}"] = rendered["subject"]
                                    st.session_state[f"body_{queue_id}"] = rendered["body"]
                                    st.session_state[f"show_template_{queue_id}"] = False
                                    st.success("Mensagem substituida pelo template!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                        with tc2:
                            if st.button("Cancelar", key=f"cancel_tmpl_{queue_id}"):
                                st.session_state[f"show_template_{queue_id}"] = False
                                st.rerun()
                    else:
                        alert_banner("Nenhum template ativo encontrado. Crie um na aba 'Templates'.", "warning")
                        if st.button("Fechar", key=f"close_tmpl_{queue_id}"):
                            st.session_state[f"show_template_{queue_id}"] = False
                            st.rerun()
                except Exception as e:
                    st.error(f"Erro ao carregar template: {e}")

            # Enviar Teste
            if st.session_state.get(f"show_test_{queue_id}", False):
                st.divider()
                st.markdown(f"""
                <div class="data-card" style="border-left: 4px solid {COLORS['secondary']};">
                    <div style="font-weight:600; color:{COLORS['secondary']};">Enviar email de teste (nao aprova, apenas envia para voce conferir)</div>
                </div>
                """, unsafe_allow_html=True)
                test_email = st.text_input("Email de teste:", placeholder="seu@email.com", key=f"test_email_{queue_id}")
                te1, te2 = st.columns(2)
                with te1:
                    if st.button("Enviar teste agora", type="primary", key=f"send_test_{queue_id}",
                                 icon=":material/send:"):
                        if test_email and "@" in test_email:
                            try:
                                from tools.brevo_sender import brevo_sender
                                final_subject = edited_subject if subject_changed else current_subject
                                final_body = edited_body if body_changed else current_body
                                result = brevo_sender.send_email(
                                    to_email=test_email,
                                    to_name="Teste",
                                    subject=f"[TESTE] {final_subject}",
                                    body=final_body,
                                )
                                if result.get("success"):
                                    st.success(f"Email de teste enviado para {test_email}!")
                                else:
                                    st.error(f"Falha: {result.get('error', 'erro desconhecido')}")
                            except Exception as e:
                                st.error(f"Erro: {e}")
                        else:
                            st.error("Digite um email valido.")
                with te2:
                    if st.button("Cancelar", key=f"cancel_test_{queue_id}"):
                        st.session_state[f"show_test_{queue_id}"] = False
                        st.rerun()


# =============================================================================
# TAB 2: FOLLOW-UPS  (fonte: tabs 2+4 de 9_Follow-ups.py)
# =============================================================================
with tab_followups:

    # ---- Secao: Gerenciar Follow-ups (tab 2 original) ----
    try:
        section_header("Gerenciar Follow-ups", "autorenew")
        alert_banner(
            "O sistema gera follow-ups automaticamente para escolas que receberam email "
            "mas nao responderam. Cada follow-up passa pela fila de aprovacao antes do envio.",
            "info",
        )

        # Sequencias configuradas
        try:
            sequences = db.client.table("follow_up_sequences").select("*").execute().data or []
        except Exception:
            sequences = []

        if sequences:
            for seq in sequences:
                active = seq.get("is_active", False)
                badge = status_badge("active", "Ativo") if active else status_badge("paused", "Pausado")
                st.markdown(
                    f'<div class="data-card"><div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<strong>{seq["name"]}</strong>{badge}</div></div>',
                    unsafe_allow_html=True,
                )

                steps = seq.get("steps", [])
                if isinstance(steps, str):
                    steps = json.loads(steps)

                if steps:
                    stepper_stages = []
                    colors_cycle = [COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"], "#7B1FA2"]
                    for i_step, step in enumerate(steps):
                        stepper_stages.append({
                            "label": step.get("label", f"Passo {step['step']}"),
                            "count": f"+{step['days_after']}d" if step["days_after"] > 0 else "Agora",
                            "color": colors_cycle[i_step % len(colors_cycle)],
                        })
                    pipeline_stepper(stepper_stages)

        # Verificar follow-ups pendentes
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Follow-ups Pendentes", "pending_actions")

        if st.button("Verificar follow-ups pendentes", type="primary", key="fu_check_pending"):
            try:
                from workflows import follow_up_manager
                with st.spinner("Verificando escolas que precisam de follow-up..."):
                    due = follow_up_manager.get_due_follow_ups()

                if due:
                    alert_banner(f"{len(due)} escolas precisam de follow-up!", "success")
                    rows = []
                    for d in due:
                        rows.append({
                            "Escola": d.get("company_name", "?"),
                            "Contato": d.get("contact_name", "?"),
                            "Email": d.get("contact_email", "?"),
                            "Ultimo envio": (d.get("last_sent_at") or "")[:10],
                            "Dias sem resposta": d.get("days_since_last", 0),
                            "Proximo FU": f"Follow-up {d.get('next_follow_up', 1)}",
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    if st.button("Gerar follow-ups para aprovacao", key="fu_generate"):
                        with st.spinner("Gerando mensagens de follow-up..."):
                            result = follow_up_manager.run_follow_up_check()
                        alert_banner(
                            f"Gerados {result.get('generated', 0)} follow-ups! Veja na aba Aprovacao.",
                            "success",
                        )
                else:
                    alert_banner("Nenhuma escola precisa de follow-up no momento.", "info")
            except ImportError:
                alert_banner("Modulo de follow-up nao disponivel. Verifique workflows/follow_up_manager.py", "warning")
            except Exception as e:
                st.error(f"Erro: {e}")

        # Historico de follow-ups — timeline visual
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Historico de Follow-ups", "history")
        try:
            fups = db.client.table("approval_queue").select(
                "id,subject,status,sent_at,follow_up_number,opened_at,replied_at"
            ).gt("follow_up_number", 0).order("created_at", desc=True).limit(20).execute().data or []

            if fups:
                timeline_html = ""
                for f in fups:
                    fu_num = f.get("follow_up_number", 0)
                    status = f.get("status", "?")
                    date_str = (f.get("sent_at") or "--")[:10]
                    subject = (f.get("subject") or "")[:50]
                    detail_parts = [f"FU #{fu_num}"]
                    if f.get("opened_at"):
                        detail_parts.append("Aberto")
                    if f.get("replied_at"):
                        detail_parts.append("Respondido")
                    color = STATUS_COLORS.get(status, COLORS["primary"])
                    timeline_html += timeline_item(
                        date=date_str,
                        title=subject,
                        detail=" | ".join(detail_parts) + f" | {status_badge(status)}",
                        color=color,
                    )
                st.markdown(timeline_html, unsafe_allow_html=True)
            else:
                st.caption("Nenhum follow-up enviado ainda.")
        except Exception as e:
            st.error(f"Erro: {e}")

    except Exception as e:
        st.error(f"Erro: {e}")

    # ---- Secao: Deducao de Emails (tab 3 original) ----
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    try:
        section_header("Deducao Inteligente de Emails", "psychology")
        alert_banner(
            "Quando encontramos 1 email pessoal de uma escola (ex: fernanda.radajeski@escola.com), "
            "deduzimos o padrao e aplicamos para os outros contatos da mesma escola.",
            "info",
        )

        # Selecionar empresa
        comm_companies_deduce = db.client.table("companies").select(
            "id,name,email_pattern,email_domain"
        ).order("name").execute().data or []

        if comm_companies_deduce:
            options_deduce = {f"{c['name']} ({c.get('email_domain', '?')})": c["id"] for c in comm_companies_deduce}
            selected_deduce = st.selectbox("Selecione uma escola:", list(options_deduce.keys()), key="comm_deduce_school")
            company_id_deduce = options_deduce[selected_deduce]

            col1_ded, col2_ded = st.columns(2)

            with col1_ded:
                if st.button("Analisar padroes", type="primary", key="comm_analyze_patterns"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Analisando..."):
                        analysis = email_deducer.analyze(company_id_deduce)

                    st.session_state["comm_deduce_analysis"] = analysis
                    personal_count = analysis.get(
                        "personal_emails", analysis.get("personal_emails_found", 0)
                    )

                    if analysis.get("pattern"):
                        alert_banner(
                            f"Padrao detectado: <strong>{analysis['pattern']}</strong> ({analysis['domain']})",
                            "success",
                        )
                        st.write(f"Emails pessoais encontrados: {personal_count}")
                    elif analysis.get("domain"):
                        alert_banner(
                            f"Dominio encontrado ({analysis['domain']}), mas sem email pessoal para detectar padrao.",
                            "warning",
                        )
                        st.write("Sera usado o padrao mais comum: **nome.sobrenome**")
                        st.caption(
                            "Dica: busque contatos no Perplexity (pagina Escolas) "
                            "para encontrar emails pessoais que ajudem a detectar o padrao."
                        )
                    elif analysis.get("suggested_patterns"):
                        alert_banner(
                            "Nenhum email pessoal encontrado, mas podemos tentar o padrao "
                            "<strong>nome.sobrenome</strong> se voce souber o dominio.",
                            "info",
                        )
                    else:
                        alert_banner(
                            "Nenhum email (pessoal ou de departamento) encontrado para esta escola.",
                            "warning",
                        )
                        st.caption(
                            "Dica: busque contatos no Perplexity (pagina Escolas ou Mapa) "
                            "para encontrar emails que permitam detectar o dominio e padrao."
                        )

            with col2_ded:
                if st.button("Deduzir emails (preview)", key="comm_deduce_preview"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Deduzindo..."):
                        result = email_deducer.deduce_for_company(company_id_deduce, dry_run=True)

                    st.session_state["comm_deduce_result"] = result

                    if result.get("deduced"):
                        alert_banner(
                            f"{len(result['deduced'])} emails deduzidos (padrao: {result['pattern']})",
                            "success",
                        )
                    elif result.get("error"):
                        st.error(result["error"])
                    else:
                        alert_banner(
                            "Todos os contatos ja tem email ou nao ha nomes suficientes.",
                            "info",
                        )

            # Mostrar preview
            if st.session_state.get("comm_deduce_result", {}).get("deduced"):
                st.markdown('<hr class="divider">', unsafe_allow_html=True)
                result = st.session_state["comm_deduce_result"]

                section_header(
                    f"Emails deduzidos (padrao: {result['pattern']}@{result['domain']})",
                    "alternate_email",
                )
                rows = []
                for d in result["deduced"]:
                    rows.append({
                        "Nome": d["name"],
                        "Cargo": d.get("role", ""),
                        "Email deduzido": d["deduced_email"],
                        "Confianca": f"{d['confidence']}%",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                alert_banner(
                    "Emails deduzidos nao sao verificados. Podem nao existir.",
                    "warning",
                )

                if st.button("Salvar emails deduzidos no banco", type="primary", key="comm_save_deduced"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Salvando..."):
                        save_result = email_deducer.deduce_for_company(company_id_deduce, dry_run=False)
                    alert_banner(f"Salvos {save_result.get('saved', 0)} emails!", "success")
                    st.session_state.pop("comm_deduce_result", None)
                    st.rerun()

            # Deducao em massa
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            section_header("Deducao em Massa", "rocket_launch")
            st.caption("Deduz emails para TODAS as escolas que tem pelo menos 1 email pessoal.")

            if st.button("Deduzir para todas as escolas (preview)", key="comm_mass_deduce_preview"):
                from tools.email_deducer import email_deducer
                with st.spinner("Analisando todas as escolas..."):
                    mass_result = email_deducer.deduce_all(dry_run=True)

                st.session_state["comm_mass_deduce"] = mass_result

                if mass_result.get("total_deduced", 0) > 0:
                    alert_banner(
                        f"{mass_result['total_deduced']} emails podem ser deduzidos "
                        f"em {mass_result['total_companies']} escolas!",
                        "success",
                    )
                else:
                    alert_banner("Nenhum email pode ser deduzido no momento.", "info")

            if st.session_state.get("comm_mass_deduce", {}).get("total_deduced", 0) > 0:
                mass = st.session_state["comm_mass_deduce"]
                rows = []
                for d in mass["details"]:
                    for email in d["emails"]:
                        rows.append({
                            "Escola": d["company"],
                            "Padrao": d["pattern"],
                            "Email deduzido": email,
                        })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if st.button("Salvar todos os emails deduzidos", type="primary", key="comm_mass_save"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Salvando..."):
                        save_result = email_deducer.deduce_all(dry_run=False)
                    alert_banner(
                        f"Salvos {save_result.get('total_deduced', 0)} emails "
                        f"em {save_result.get('total_companies', 0)} escolas!",
                        "success",
                    )
                    st.session_state.pop("comm_mass_deduce", None)
                    st.rerun()

        else:
            alert_banner("Nenhuma escola importada ainda.", "info")

    except Exception as e:
        st.error(f"Erro: {e}")

    # ---- Secao: Timeline por Escola (tab 4 original) ----
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    try:
        section_header("Timeline de Interacoes", "timeline")
        st.caption("Veja todo o historico de comunicacao com cada escola.")

        comm_companies_tl = db.client.table("companies").select("id,name,inep_code").order("name").execute().data or []
        if comm_companies_tl:
            from dashboard.helpers.school_lookup import format_school_option as _fmt_fu, parse_inep_from_option as _parse_fu
            _fu_opts = [_fmt_fu(c["name"], str(c.get("inep_code", ""))) for c in comm_companies_tl]
            _fu_ids = {_fmt_fu(c["name"], str(c.get("inep_code", ""))): c["id"] for c in comm_companies_tl}
            selected_tl = st.selectbox(
                "Selecione uma escola:", _fu_opts, key="comm_timeline_school"
            )
            company_id_tl = _fu_ids.get(selected_tl)
            if company_id_tl:

                # Filtros
                fc1, fc2 = st.columns(2)
                with fc1:
                    event_filter = st.multiselect(
                        "Filtrar por tipo de evento:",
                        ["Enviado", "Pendente", "Aberto", "Clicado", "Respondido", "Rejeitado"],
                        default=[],
                        key="comm_timeline_filter",
                    )
                with fc2:
                    sort_order = st.radio(
                        "Ordenar por:",
                        ["Mais recente primeiro", "Mais antigo primeiro"],
                        horizontal=True,
                        key="comm_timeline_sort",
                    )

                # Buscar emails enviados
                emails_tl = db.client.table("approval_queue").select(
                    "id,subject,status,sent_at,opened_at,clicked_at,replied_at,bounced_at,follow_up_number,created_at"
                ).eq("company_id", company_id_tl).order("created_at", desc=True).execute().data or []

                if emails_tl:
                    events = []
                    type_colors = {
                        "Enviado": COLORS["primary"],
                        "Pendente": COLORS["warning"],
                        "Aberto": COLORS["secondary"],
                        "Clicado": COLORS["info"],
                        "Respondido": COLORS["success"],
                        "Rejeitado": COLORS["error"],
                    }

                    for e in emails_tl:
                        fu = e.get("follow_up_number", 0)
                        tl_label = f"Follow-up {fu}" if fu > 0 else "Email inicial"
                        status = e.get("status", "?")

                        if status == "sent":
                            events.append({
                                "data": (e.get("sent_at") or e.get("created_at") or "")[:19],
                                "tipo": "Enviado",
                                "evento": f"{tl_label} enviado",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        elif status == "pending":
                            events.append({
                                "data": (e.get("created_at") or "")[:19],
                                "tipo": "Pendente",
                                "evento": f"{tl_label} aguardando aprovacao",
                                "detalhe": (e.get("subject") or "")[:60],
                            })

                        if e.get("opened_at"):
                            events.append({
                                "data": e["opened_at"][:19],
                                "tipo": "Aberto",
                                "evento": "Email aberto",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("clicked_at"):
                            events.append({
                                "data": e["clicked_at"][:19],
                                "tipo": "Clicado",
                                "evento": "Link clicado",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("replied_at"):
                            events.append({
                                "data": e["replied_at"][:19],
                                "tipo": "Respondido",
                                "evento": "Resposta recebida!",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("bounced_at"):
                            events.append({
                                "data": e["bounced_at"][:19],
                                "tipo": "Rejeitado",
                                "evento": "Email bounced",
                                "detalhe": (e.get("subject") or "")[:60],
                            })

                    # Aplicar filtro de tipo
                    if event_filter:
                        events = [ev for ev in events if ev["tipo"] in event_filter]

                    # Ordenar
                    reverse = sort_order == "Mais recente primeiro"
                    events.sort(key=lambda x: x["data"], reverse=reverse)

                    if events:
                        st.caption(f"{len(events)} evento(s) encontrado(s)")
                        tl_html = ""
                        for ev in events:
                            color = type_colors.get(ev["tipo"], COLORS["primary"])
                            tl_html += timeline_item(
                                date=ev["data"],
                                title=ev["evento"],
                                detail=ev["detalhe"],
                                color=color,
                            )
                        st.markdown(tl_html, unsafe_allow_html=True)
                    else:
                        alert_banner("Nenhum evento corresponde aos filtros selecionados.", "info")
                else:
                    alert_banner("Nenhuma interacao registrada para esta escola.", "info")
        else:
            alert_banner("Nenhuma escola importada ainda.", "info")

    except Exception as e:
        st.error(f"Erro: {e}")


# =============================================================================
# TAB 3: TEMPLATES  (fonte: 10_Templates.py)
# =============================================================================
with tab_templates:

    # ---- Assinatura de Email ----
    section_header("Assinatura de Email", "draw")

    st.markdown(
        '<div style="font-size:13px;color:#757575;margin-bottom:12px">'
        'A assinatura e adicionada automaticamente ao final de <strong>todo email</strong> '
        'enviado pelo IAlex (emails iniciais, follow-ups, etc). Suporta texto + imagem.'
        '</div>',
        unsafe_allow_html=True,
    )

    try:
        from integrations.email_signature import email_signature

        sig = email_signature.get_signature()

        sig_col1, sig_col2 = st.columns([1, 1])

        with sig_col1:
            sig_enabled = st.toggle("Assinatura ativa", value=sig.get("enabled", True), key="comm_sig_enabled")
            sig_text = st.text_area(
                "Texto da assinatura",
                value=sig.get("text", ""),
                height=120,
                key="comm_sig_text",
                placeholder="Fernando Teixeira\nIAprendo - Plataforma Educacional\n(51) 99642-2564\nwww.iaprendo.com.br",
                help="Cada linha aparece separada. Use para nome, cargo, empresa, telefone, site.",
            )
            sig_image_url = st.text_input(
                "URL da imagem (logo/banner)",
                value=sig.get("image_url", ""),
                key="comm_sig_image_url",
                placeholder="https://exemplo.com/logo.png",
                help="Cole a URL publica da imagem. Use um servico de hospedagem (Imgur, Google Drive publico, etc).",
            )
            sig_col_a, sig_col_b = st.columns(2)
            with sig_col_a:
                sig_image_width = st.number_input(
                    "Largura da imagem (px)",
                    min_value=50, max_value=600, step=10,
                    value=int(sig.get("image_width", 200)),
                    key="comm_sig_image_width",
                )
            with sig_col_b:
                sig_link_url = st.text_input(
                    "Link ao clicar na imagem (opcional)",
                    value=sig.get("link_url", ""),
                    key="comm_sig_link_url",
                    placeholder="https://iaprendo.com.br",
                )
            sig_separator = st.checkbox(
                "Mostrar linha separadora acima da assinatura",
                value=sig.get("separator", True),
                key="comm_sig_separator",
            )

            if st.button("Salvar assinatura", type="primary", use_container_width=True, key="comm_btn_save_sig"):
                new_sig = {
                    "enabled": sig_enabled,
                    "text": sig_text,
                    "image_url": sig_image_url.strip(),
                    "image_width": int(sig_image_width),
                    "image_alt": "Logo",
                    "link_url": sig_link_url.strip(),
                    "separator": sig_separator,
                }
                if email_signature.save_signature(new_sig):
                    st.success("Assinatura salva! Todos os proximos emails usarao essa assinatura.")
                    st.rerun()
                else:
                    st.error("Falha ao salvar assinatura.")

        with sig_col2:
            st.markdown("**Preview da assinatura:**")
            preview_sig = {
                "enabled": sig_enabled,
                "text": sig_text,
                "image_url": sig_image_url.strip(),
                "image_width": int(sig_image_width),
                "image_alt": "Logo",
                "link_url": sig_link_url.strip(),
                "separator": sig_separator,
            }
            from integrations.email_signature import EmailSignature
            temp_sig = EmailSignature()
            temp_sig.get_signature = lambda: preview_sig
            preview_html = temp_sig.render_html()

            if preview_html:
                sample_body = (
                    '<div style="font-family:Arial,sans-serif;font-size:14px;color:#333;'
                    'padding:16px;border:1px solid #E0E0E0;border-radius:8px;background:#FAFAFA">'
                    '<div style="color:#999;font-size:12px;margin-bottom:8px">Preview do email:</div>'
                    '<div style="margin:0;line-height:1.5">Oi Joao, tudo bem?</div>'
                    '<div style="height:8px">&nbsp;</div>'
                    '<div style="margin:0;line-height:1.5">Gostariamos de apresentar o IAprendo...</div>'
                    + preview_html
                    + '</div>'
                )
                st.markdown(sample_body, unsafe_allow_html=True)
            else:
                st.info("Configure o texto e/ou imagem ao lado para ver o preview.")

        # Botao de email de teste
        st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)
        section_header("Testar assinatura por email", "send")

        test_col1, test_col2 = st.columns([2, 1])
        with test_col1:
            test_email_sig = st.text_input(
                "Email para teste",
                placeholder="seu@email.com",
                key="comm_sig_test_email",
            )
        with test_col2:
            st.markdown('<div style="margin-top:28px"></div>', unsafe_allow_html=True)
            if st.button("Enviar teste", use_container_width=True, key="comm_btn_test_sig"):
                if not test_email_sig or "@" not in test_email_sig:
                    st.error("Digite um email valido.")
                else:
                    try:
                        from tools.brevo_sender import BrevoSender
                        sender = BrevoSender()
                        result = sender.send_email(
                            to_email=test_email_sig.strip(),
                            to_name="Teste",
                            subject="[TESTE] Preview da assinatura IAprendo",
                            body=(
                                "Oi! Este e um email de teste para verificar como a assinatura "
                                "aparece para o destinatario.\n\n"
                                "Se a assinatura abaixo estiver correta (texto + imagem), "
                                "esta tudo configurado!\n\n"
                                "Atenciosamente,\nFernando"
                            ),
                        )
                        if result.get("success"):
                            st.success(f"Email de teste enviado para {test_email_sig}! Verifique sua caixa de entrada.")
                        else:
                            st.error(f"Falha no envio: {result.get('error', 'erro desconhecido')}")
                    except Exception as e:
                        st.error(f"Erro: {e}")

    except Exception as e:
        st.warning(f"Assinatura indisponivel: {e}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ---- Templates de Follow-up (por tipo comportamental) ----
    section_header("Templates de Follow-up", "autorenew")

    st.markdown(
        '<div style="font-size:13px;color:#757575;margin-bottom:12px">'
        'Configure templates especificos para cada tipo de follow-up comportamental. '
        'Se um template existir, sera usado em vez da IA. Se nao, a IA gera do zero.'
        '</div>',
        unsafe_allow_html=True,
    )

    FU_TYPES_INFO = [
        ("follow_up_hot_click", "Hot Click", "Lead clicou em link -- tom comercial direto"),
        ("follow_up_curious_open", "Curious Open", "Abriu 2+ vezes sem responder -- valor adicional"),
        ("follow_up_silent_open", "Silent Open", "Abriu 1x e sumiu -- lembrete gentil"),
        ("follow_up_revival", "Revival", "Nao abriu nada -- angulo totalmente novo"),
    ]

    try:
        for fu_type, fu_label, fu_desc in FU_TYPES_INFO:
            existing_tpl = None
            try:
                r = db.client.table("message_templates").select("*").eq(
                    "target_type", fu_type
                ).eq("is_active", True).limit(1).execute()
                existing_tpl = (r.data or [None])[0]
            except Exception:
                pass

            with st.expander(f"{fu_label} -- {fu_desc}", expanded=False):
                if existing_tpl:
                    st.success(f"Template ativo: {existing_tpl.get('name', '?')}")
                    st.text_area(
                        "Assunto",
                        value=existing_tpl.get("subject_template", ""),
                        disabled=True,
                        height=40,
                        key=f"comm_fu_tpl_subj_{fu_type}",
                    )
                    st.text_area(
                        "Corpo",
                        value=existing_tpl.get("body_template", ""),
                        disabled=True,
                        height=150,
                        key=f"comm_fu_tpl_body_{fu_type}",
                    )
                    st.caption("Para editar, use a secao de Templates abaixo.")
                else:
                    st.info(
                        f"Sem template configurado -- IA gera automaticamente. "
                        f"Para criar, use a secao de Templates abaixo e defina target_type = '{fu_type}'."
                    )

        st.caption(
            "Para criar template de follow-up: crie um template normal na secao abaixo. "
            "Apos aplicar a migration 007 (target_type), edite o campo target_type no banco "
            "para o tipo desejado (ex: 'follow_up_hot_click')."
        )

    except Exception as e:
        st.warning(f"Templates de follow-up indisponiveis: {e}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ---- Templates de Mensagem (CRUD) ----

    # Carregar templates existentes
    try:
        templates = db.client.table("message_templates").select("*").order("created_at", desc=True).execute().data or []
    except Exception as e:
        st.error(f"Erro ao buscar templates: {e}")
        templates = []

    # Sub-tabs: Gerenciar / Criar / Variaveis / Preview
    tpl_tab_manage, tpl_tab_create, tpl_tab_vars, tpl_tab_preview = st.tabs([
        "Templates", "Criar Novo", "Variaveis", "Preview",
    ])

    # --- Gerenciar Templates ---
    with tpl_tab_manage:
        if not templates:
            alert_banner("Nenhum template criado ainda. Use a aba 'Criar Novo' para criar o primeiro.", "info")
        else:
            total_tpl = len(templates)
            active_count_tpl = len([t for t in templates if t.get("is_active")])
            default_count_tpl = len([t for t in templates if t.get("is_default")])
            c1, c2, c3 = st.columns(3)
            with c1:
                metric_card("Total", total_tpl, icon="description", color=COLORS["primary"])
            with c2:
                metric_card("Ativos", active_count_tpl, icon="check_circle", color=COLORS["success"])
            with c3:
                metric_card("Padrao", default_count_tpl, icon="star", color=COLORS["accent"])

            st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)

            for tmpl in templates:
                tid = tmpl["id"]
                name = tmpl.get("name", "?")
                is_default = tmpl.get("is_default", False)
                is_active = tmpl.get("is_active", True)
                target = tmpl.get("target_role")
                target_label = ROLE_LABELS.get(target, "Todos") if target else "Todos"

                badges = ""
                if is_default:
                    badges += status_badge("approved", "Padrao")
                if is_active:
                    badges += " " + status_badge("active", "Ativo")
                else:
                    badges += " " + status_badge("paused", "Inativo")

                st.markdown(
                    f'<div class="data-card">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">'
                    f'<strong style="font-size:15px">{name}</strong>'
                    f'<div>{badges}</div></div>'
                    f'<div style="font-size:13px;color:#757575">Cargo: {target_label} | '
                    f'Assunto: {(tmpl.get("subject_template") or "")[:50]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                is_editing = st.session_state.get(f"comm_editing_{tid}", False)

                if not is_editing:
                    with st.expander(f"Ver corpo e acoes: {name}", expanded=False):
                        st.markdown(f"**Assunto:** {tmpl.get('subject_template', '')}")
                        st.text_area(
                            "Corpo:", value=tmpl.get("body_template", ""), height=150,
                            disabled=True, key=f"comm_view_body_{tid}",
                        )
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if st.button("Editar", key=f"comm_edit_{tid}"):
                                st.session_state[f"comm_editing_{tid}"] = True
                                st.rerun()
                        with col2:
                            if not is_default and is_active:
                                if st.button("Tornar Padrao", key=f"comm_default_{tid}"):
                                    try:
                                        db.client.table("message_templates").update(
                                            {"is_default": False}
                                        ).eq("is_default", True).execute()
                                        db.client.table("message_templates").update(
                                            {"is_default": True}
                                        ).eq("id", tid).execute()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
                        with col3:
                            if is_active:
                                if st.button("Desativar", key=f"comm_deactivate_{tid}"):
                                    try:
                                        db.client.table("message_templates").update(
                                            {"is_active": False, "is_default": False}
                                        ).eq("id", tid).execute()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
                            else:
                                if st.button("Reativar", key=f"comm_reactivate_{tid}"):
                                    try:
                                        db.client.table("message_templates").update(
                                            {"is_active": True}
                                        ).eq("id", tid).execute()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Erro: {e}")
                        with col4:
                            if st.button("Excluir", key=f"comm_delete_{tid}"):
                                try:
                                    db.client.table("message_templates").delete().eq("id", tid).execute()
                                    alert_banner("Template excluido!", "success")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                else:
                    with st.expander(f"Editando: {name}", expanded=True):
                        with st.form(key=f"comm_edit_form_{tid}"):
                            edit_name = st.text_input(
                                "Nome:", value=tmpl.get("name", ""), key=f"comm_edit_name_{tid}"
                            )
                            edit_role = st.selectbox(
                                "Para qual cargo?",
                                ["Todos"] + [ROLE_LABELS[r] for r in ALL_ROLE_TYPES],
                                index=(
                                    0 if not target
                                    else (
                                        [0] + [
                                            i + 1
                                            for i, r in enumerate(ALL_ROLE_TYPES)
                                            if r == target
                                        ] or [0]
                                    )[0]
                                    if target in ALL_ROLE_TYPES
                                    else 0
                                ),
                                key=f"comm_edit_role_{tid}",
                            )
                            edit_subject = st.text_input(
                                "Assunto:", value=tmpl.get("subject_template", ""), key=f"comm_edit_subj_{tid}"
                            )
                            edit_body = st.text_area(
                                "Corpo:", value=tmpl.get("body_template", ""), height=250, key=f"comm_edit_body_{tid}"
                            )
                            fc1, fc2 = st.columns(2)
                            with fc1:
                                save_btn = st.form_submit_button("Salvar alteracoes", type="primary")
                            with fc2:
                                cancel_btn = st.form_submit_button("Cancelar")

                            if save_btn:
                                new_target = None
                                for key, label in ROLE_LABELS.items():
                                    if label == edit_role:
                                        new_target = key
                                        break
                                try:
                                    db.client.table("message_templates").update({
                                        "name": edit_name,
                                        "subject_template": edit_subject,
                                        "body_template": edit_body,
                                        "target_role": new_target,
                                    }).eq("id", tid).execute()
                                    st.session_state[f"comm_editing_{tid}"] = False
                                    alert_banner("Template atualizado!", "success")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar: {e}")
                            if cancel_btn:
                                st.session_state[f"comm_editing_{tid}"] = False
                                st.rerun()

    # --- Criar Novo Template ---
    with tpl_tab_create:
        section_header("Novo Template", "add_circle_outline")
        with st.form(key="comm_new_template_form"):
            t_name = st.text_input("Nome do template:", placeholder="Primeiro contato - Geral")
            t_role = st.selectbox(
                "Para qual cargo?", ["Todos"] + [ROLE_LABELS[r] for r in ALL_ROLE_TYPES],
                key="comm_new_tpl_role",
            )
            t_subject = st.text_input(
                "Assunto (max 60 chars):",
                placeholder="IAprendo -- tecnologia para {school_name}",
            )
            t_body = st.text_area(
                "Corpo da mensagem:", height=250,
                placeholder="Prezado(a) {contact_name}, Sou {sender_name}, da IAprendo... Att, {sender_name}",
            )
            t_default = st.checkbox("Marcar como padrao", value=not templates)
            submit = st.form_submit_button("Salvar Template", type="primary")
            if submit:
                if not t_name or not t_subject or not t_body:
                    st.error("Preencha todos os campos.")
                else:
                    target = None
                    for key, label in ROLE_LABELS.items():
                        if label == t_role:
                            target = key
                            break
                    try:
                        if t_default:
                            db.client.table("message_templates").update(
                                {"is_default": False}
                            ).eq("is_default", True).execute()
                        new_tmpl = {
                            "name": t_name,
                            "subject_template": t_subject,
                            "body_template": t_body,
                            "target_role": target,
                            "is_active": True,
                            "is_default": t_default,
                        }
                        db.client.table("message_templates").insert(new_tmpl).execute()
                        alert_banner(f"Template '{t_name}' criado!", "success")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

    # --- Variaveis Disponiveis ---
    with tpl_tab_vars:
        section_header("Variaveis Disponiveis", "data_object")
        st.markdown(
            "Use estas variaveis no assunto e corpo do template. "
            "Elas serao substituidas automaticamente pelos dados reais de cada escola."
        )

        for var, desc in TEMPLATE_VARIABLES.items():
            var_code = "{" + var + "}"
            st.markdown(
                f'<div class="data-card" style="display:flex;align-items:center;gap:16px;padding:10px 16px">'
                f'<code style="background:#E3F2FD;color:#1565C0;padding:4px 12px;border-radius:6px;'
                f'font-size:13px;font-weight:600;white-space:nowrap">{var_code}</code>'
                f'<span style="font-size:13px;color:#757575">{desc}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- Preview com Dados Reais ---
    with tpl_tab_preview:
        section_header("Preview com Dados Reais", "preview")
        active_templates = [t for t in templates if t.get("is_active")]
        if not active_templates:
            alert_banner("Crie um template ativo para ver o preview.", "info")
        else:
            try:
                schools_preview = db.client.table("companies").select(
                    "id,name,city,state,education_levels,admin_category,qualification_score"
                ).order("qualification_score", desc=True).limit(20).execute().data or []
            except Exception:
                schools_preview = []

            if schools_preview:
                col_tmpl, col_school = st.columns(2)
                with col_tmpl:
                    selected_tmpl = st.selectbox(
                        "Template:",
                        active_templates,
                        format_func=lambda t: t.get("name", "?"),
                        key="comm_preview_tmpl",
                    )
                with col_school:
                    selected_school = st.selectbox(
                        "Escola:",
                        schools_preview,
                        format_func=lambda s: f"{s.get('name', '?')} ({s.get('city', '')})",
                        key="comm_preview_school",
                    )

                if selected_tmpl and selected_school:
                    contacts_preview = db.client.table("contacts").select("*").eq(
                        "company_id", selected_school["id"]
                    ).order("outreach_priority").execute().data or []
                    contact_preview = contacts_preview[0] if contacts_preview else {"full_name": "Diretor(a)", "role": "Diretor(a)"}

                    rendered = render_template(
                        selected_tmpl["subject_template"],
                        selected_tmpl["body_template"],
                        selected_school,
                        contact_preview,
                    )

                    st.markdown(
                        f'<div class="data-card" style="border-left:4px solid {COLORS["primary"]}">'
                        f'<div style="font-size:13px;color:#757575;margin-bottom:4px">Assunto:</div>'
                        f'<div style="font-size:15px;font-weight:600;margin-bottom:12px">{rendered["subject"]}</div>'
                        f'<div style="font-size:13px;color:#757575;margin-bottom:4px">Corpo:</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.text_area(
                        "Corpo renderizado:",
                        value=rendered["body"],
                        height=200,
                        disabled=True,
                        key="comm_preview_result",
                    )
            else:
                alert_banner("Nenhuma escola no banco para preview.", "info")


# =============================================================================
# TAB 4: METRICAS  (fonte: tabs 1+3 de 9_Follow-ups.py)
# =============================================================================
with tab_metricas:

    # ---- Secao: Metricas de Email (tab 1 original) ----
    try:
        # Buscar dados
        met_sent = db.client.table("approval_queue").select(
            "id,sent_at,opened_at,clicked_at,replied_at,bounced_at,company_id,contact_id,subject,follow_up_number"
        ).eq("status", "sent").execute().data or []
        met_pending = db.client.table("approval_queue").select("id").eq("status", "pending").execute().data or []
        met_approved = db.client.table("approval_queue").select("id").eq("status", "approved").execute().data or []

        total_sent = len(met_sent)
        total_opened = len([s for s in met_sent if s.get("opened_at")])
        total_clicked = len([s for s in met_sent if s.get("clicked_at")])
        total_replied = len([s for s in met_sent if s.get("replied_at")])
        total_bounced = len([s for s in met_sent if s.get("bounced_at")])

        # KPIs
        section_header("Performance de Emails", "analytics")
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card(
                "Enviados", total_sent,
                color=COLORS["primary"], icon="send",
            )
        with c2:
            metric_card(
                "Abertos", total_opened,
                color=COLORS["secondary"],
                delta=f"{total_opened/total_sent*100:.0f}%" if total_sent else "0%",
                icon="visibility",
            )
        with c3:
            metric_card(
                "Clicados", total_clicked,
                color=COLORS["info"],
                delta=f"{total_clicked/total_sent*100:.0f}%" if total_sent else "0%",
                icon="touch_app",
            )

        st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        with c4:
            metric_card(
                "Respondidos", total_replied,
                color=COLORS["success"],
                delta=f"{total_replied/total_sent*100:.0f}%" if total_sent else "0%",
                icon="reply",
            )
        with c5:
            metric_card(
                "Rejeitado", total_bounced,
                color=COLORS["error"],
                delta=f"{total_bounced/total_sent*100:.0f}%" if total_sent else "0%",
                icon="error_outline",
            )
        with c6:
            metric_card(
                "Pendentes", len(met_pending) + len(met_approved),
                color=COLORS["warning"], icon="schedule",
            )

        # Funil visual
        if total_sent > 0:
            st.markdown('<div class="mt-3"></div>', unsafe_allow_html=True)
            section_header("Funil de Conversao", "filter_alt")
            pipeline_stepper([
                {"label": "Enviados", "count": total_sent, "color": COLORS["primary"]},
                {"label": "Abertos", "count": total_opened, "color": COLORS["secondary"]},
                {"label": "Clicados", "count": total_clicked, "color": COLORS["info"]},
                {"label": "Respondidos", "count": total_replied, "color": COLORS["success"]},
            ])

            funil_data = pd.DataFrame({
                "Etapa": ["Enviados", "Abertos", "Clicados", "Respondidos"],
                "Quantidade": [total_sent, total_opened, total_clicked, total_replied],
            })
            st.bar_chart(funil_data.set_index("Etapa"), height=300)

        # Sync tracking
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Sincronizar Tracking", "sync")
        st.caption("Busca eventos de abertura e clique no Brevo para atualizar as metricas.")

        if st.button("Sincronizar eventos do Brevo", type="primary", key="comm_sync_brevo"):
            try:
                from tools.email_tracker import email_tracker as tracker
                with st.spinner("Buscando eventos no Brevo..."):
                    result = tracker.sync_tracking_events()
                if result.get("error"):
                    st.error(f"Erro: {result['error']}")
                else:
                    updated = result.get("updated", 0)
                    alert_banner(f"Sincronizado! {updated} eventos atualizados.", "success")
                    if updated > 0:
                        st.rerun()
            except ImportError:
                alert_banner("Modulo de tracking nao disponivel. Verifique tools/email_tracker.py", "warning")
            except Exception as e:
                st.error(f"Erro: {e}")

        # Tabela de emails enviados com status de tracking
        if met_sent:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            section_header("Emails Enviados - Status de Tracking", "email")
            rows = []
            for s in sorted(met_sent, key=lambda x: x.get("sent_at", ""), reverse=True):
                fu = s.get("follow_up_number", 0)
                fu_label = f"FU-{fu}" if fu > 0 else "Inicial"
                rows.append({
                    "Assunto": (s.get("subject") or "")[:50],
                    "Tipo": fu_label,
                    "Enviado": (s.get("sent_at") or "")[:16],
                    "Aberto": "Sim" if s.get("opened_at") else "Nao",
                    "Clicado": "Sim" if s.get("clicked_at") else "Nao",
                    "Respondido": "Sim" if s.get("replied_at") else "Nao",
                    "Rejeitado": "Sim" if s.get("bounced_at") else "--",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Erro ao carregar metricas: {e}")


# =============================================================================
# TAB 5: WHATSAPP
# =============================================================================
with tab_whatsapp:
    section_header("WhatsApp", "smartphone")
    st.caption(
        "Gerencie mensagens WhatsApp enviadas pelo IAlex, templates de mensagem "
        "e numeros descobertos. Mensagens de WhatsApp passam pela mesma fila "
        "de aprovacao que emails (canal 'whatsapp')."
    )

    wa_sub1, wa_sub2, wa_sub3 = st.tabs([
        "📋 Fila WhatsApp",
        "📝 Templates WhatsApp",
        "📱 Numeros Descobertos",
    ])

    # --- Sub-tab 1: Fila WhatsApp ---
    with wa_sub1:
        try:
            # Mensagens WhatsApp na fila (canal = whatsapp)
            wa_pending = db.client.table("approval_queue").select(
                "id,subject,body,status,created_at,sent_at,company_id,"
                "companies(name)"
            ).eq("channel", "whatsapp").order(
                "created_at", desc=True
            ).limit(50).execute().data or []

            if not wa_pending:
                st.info(
                    "Nenhuma mensagem WhatsApp na fila. Use o IAlex (WhatsApp) "
                    "para enviar mensagens — elas aparecerão aqui para aprovacao."
                )
            else:
                # KPIs
                wa_p = len([m for m in wa_pending if m.get("status") == "pending"])
                wa_a = len([m for m in wa_pending if m.get("status") == "approved"])
                wa_s = len([m for m in wa_pending if m.get("status") == "sent"])
                wk1, wk2, wk3 = st.columns(3)
                with wk1:
                    metric_card("Pendentes", str(wa_p), COLORS.get("warning", "#FFA94D"), icon="pending")
                with wk2:
                    metric_card("Aprovados", str(wa_a), COLORS.get("success", "#51CF66"), icon="check")
                with wk3:
                    metric_card("Enviados", str(wa_s), COLORS.get("info", "#339AF0"), icon="send")

                # Tabela
                wa_rows = []
                for m in wa_pending:
                    comp = m.get("companies") or {}
                    wa_rows.append({
                        "Escola": comp.get("name", "?"),
                        "Mensagem": (m.get("body") or "")[:80] + ("..." if len(m.get("body") or "") > 80 else ""),
                        "Status": {"pending": "Pendente", "approved": "Aprovado", "sent": "Enviado", "rejected": "Rejeitado"}.get(m.get("status"), m.get("status", "?")),
                        "Criado": (m.get("created_at") or "")[:16],
                        "Enviado": (m.get("sent_at") or "")[:16] if m.get("sent_at") else "—",
                    })
                st.dataframe(pd.DataFrame(wa_rows), use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"Erro ao carregar fila WhatsApp: {e}")

    # --- Sub-tab 2: Templates WhatsApp ---
    with wa_sub2:
        st.caption(
            "Templates padrao para mensagens WhatsApp. Use variaveis "
            "{contact_name} e {company_name} para personalizacao automatica."
        )

        # Templates hardcoded do whatsapp_helper.py
        try:
            from tools.whatsapp_helper import TEMPLATES as WA_TEMPLATES
        except ImportError:
            WA_TEMPLATES = {
                "default": "Ola {contact_name}! Sou da equipe IAprendo. Gostaria de apresentar nossa plataforma de IA educacional para a {company_name}. Podemos conversar?",
                "meeting": "Ola {contact_name}! Sou da equipe IAprendo. Posso agendar 15min para mostrar como a IA pode ajudar a {company_name}? {meeting_link}",
                "short": "Ola {contact_name}! IAprendo aqui. Temos uma solucao de IA educacional ideal para a {company_name}. Posso explicar?",
            }

        _WA_TEMPLATE_LABELS = {
            "default": "Apresentacao (padrao)",
            "meeting": "Agendamento de reuniao",
            "short": "Mensagem curta",
        }

        for key, template in WA_TEMPLATES.items():
            label = _WA_TEMPLATE_LABELS.get(key, key)
            with st.expander(f"📱 {label}", expanded=(key == "default")):
                st.code(template, language=None)
                # Preview com dados exemplo
                preview = template.replace("{contact_name}", "Maria Silva").replace(
                    "{company_name}", "Colegio Exemplo"
                ).replace("{meeting_link}", "https://cal.com/iaprendo/15min")
                st.markdown(f"**Preview:** {preview}")

        st.markdown("---")

        # Templates personalizados do banco (message_templates com target_type whatsapp)
        section_header("Templates personalizados", "edit_note")
        st.caption(
            "Crie templates WhatsApp customizados salvos no banco. "
            "Use as variaveis {contact_name}, {company_name}, {city}."
        )

        try:
            wa_custom = db.client.table("message_templates").select("*").ilike(
                "target_type", "whatsapp%"
            ).order("created_at", desc=True).execute().data or []

            if wa_custom:
                for t in wa_custom:
                    with st.expander(f"✏️ {t.get('name', '?')}"):
                        st.text_area(
                            "Corpo",
                            value=t.get("body_template", ""),
                            key=f"wa_tpl_{t['id']}",
                            disabled=True,
                            height=100,
                        )
            else:
                st.info("Nenhum template personalizado criado ainda.")

            # Formulario para criar novo
            with st.expander("➕ Criar novo template WhatsApp"):
                wa_new_name = st.text_input("Nome do template", key="wa_new_name", placeholder="Ex: Follow-up pos-reuniao")
                wa_new_body = st.text_area(
                    "Corpo da mensagem",
                    key="wa_new_body",
                    placeholder="Ola {contact_name}! ...",
                    height=100,
                )
                if st.button("Salvar template", key="wa_save_tpl"):
                    if wa_new_name and wa_new_body:
                        try:
                            db.client.table("message_templates").insert({
                                "name": wa_new_name,
                                "body_template": wa_new_body,
                                "subject_template": "",
                                "target_type": "whatsapp_custom",
                                "is_active": True,
                            }).execute()
                            st.success(f"Template '{wa_new_name}' salvo!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar: {e}")
                    else:
                        alert_banner("Preencha nome e corpo do template.", "error")

        except Exception as e:
            st.warning(f"Erro ao carregar templates personalizados: {e}")

    # --- Sub-tab 3: Numeros Descobertos ---
    with wa_sub3:
        try:
            # Contar contatos com/sem telefone
            all_contacts = db.client.table("contacts").select(
                "id,full_name,phone,company_id,companies(name)"
            ).not_.is_("phone", "null").order("full_name").limit(200).execute().data or []

            total_contacts = db.client.table("contacts").select(
                "id", count="exact"
            ).limit(1).execute().count or 0

            with_phone = len(all_contacts)
            without_phone = total_contacts - with_phone

            wn1, wn2, wn3 = st.columns(3)
            with wn1:
                metric_card("Com telefone", str(with_phone), COLORS.get("success", "#51CF66"), icon="phone")
            with wn2:
                metric_card("Sem telefone", str(without_phone), COLORS.get("warning", "#FFA94D"), icon="phone_disabled")
            with wn3:
                pct = round(with_phone / total_contacts * 100, 1) if total_contacts > 0 else 0
                metric_card("Cobertura", f"{pct}%", COLORS.get("info", "#339AF0"), icon="percent")

            if all_contacts:
                st.markdown("")
                section_header("Contatos com telefone", "contacts_phone")
                wa_contact_rows = []
                for c in all_contacts[:100]:
                    comp = c.get("companies") or {}
                    wa_contact_rows.append({
                        "Nome": c.get("full_name", "?"),
                        "Telefone": c.get("phone", "—"),
                        "Escola": comp.get("name", "?"),
                    })
                st.dataframe(
                    pd.DataFrame(wa_contact_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info(
                    "Nenhum contato com telefone encontrado. Use o Pipeline "
                    "(Descoberta) ou o IAlex para descobrir numeros de telefone."
                )

        except Exception as e:
            st.error(f"Erro ao carregar numeros: {e}")
