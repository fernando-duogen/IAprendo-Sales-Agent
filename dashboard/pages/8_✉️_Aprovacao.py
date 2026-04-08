"""Pagina 6 - Fila de Aprovacao: interface central de revisao humana com Material Design."""
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, avatar, breadcrumb, COLORS, STATUS_COLORS, score_color,
)

apply_theme_no_config()

try:
    from approval_queue import queue_manager
    from database.supabase_client import db
    from utils.role_classifier import POWER_MAP_ROLES, ROLE_LABELS
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.stop()

if "current_idx" not in st.session_state:
    st.session_state.current_idx = 0
if "refresh" not in st.session_state:
    st.session_state.refresh = 0

# ===========================================================================
# HEADER
# ===========================================================================
section_header("Fila de Aprovacao", "fact_check")
st.caption("Revise, edite e aprove cada mensagem antes do envio. Nenhuma mensagem e enviada sem sua aprovacao.")

# ===========================================================================
# CARREGAR DADOS
# ===========================================================================
pending = queue_manager.get_pending(limit=50)
total = len(pending)

# Contar por status
try:
    approved_count = (db.client.table("approval_queue").select("id", count="exact").eq("status", "approved").execute()).count or 0
except Exception:
    approved_count = 0
try:
    sent_count = (db.client.table("approval_queue").select("id", count="exact").eq("status", "sent").execute()).count or 0
except Exception:
    sent_count = 0
try:
    rejected_count = (db.client.table("approval_queue").select("id", count="exact").eq("status", "rejected").execute()).count or 0
except Exception:
    rejected_count = 0

# ===========================================================================
# METRICAS RAPIDAS
# ===========================================================================
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

# ===========================================================================
# TABS: Pendentes / Aprovadas (aguardando envio) / Enviadas
# ===========================================================================
import pandas as pd

tab_pending, tab_approved, tab_sent = st.tabs([
    f"📝 Pendentes ({total})",
    f"✅ Aprovadas ({approved_count})",
    f"📤 Enviadas ({sent_count})",
])

# --- TAB: APROVADAS (aguardando envio) ---
with tab_approved:
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
                    from datetime import datetime as _dt
                    sched_dt = _dt.fromisoformat(sched.replace("Z", "+00:00"))
                    sched_label = f" | ⏰ Agendado: {sched_dt.strftime('%d/%m %H:%M')}"
                except Exception:
                    sched_label = f" | ⏰ {sched[:16]}"
            else:
                sched_label = " | 📤 Envio imediato (proximo ciclo)"

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
            "💡 Mensagens sem agendamento serao enviadas automaticamente pelo scheduler (a cada 5 min). "
            "Mensagens agendadas serao enviadas no horario definido."
        )

# --- TAB: ENVIADAS (historico com corpo completo) ---
with tab_sent:
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

            # Tracking icons
            icons = []
            if msg.get("replied_at"):
                icons.append("💬 Respondeu")
            elif msg.get("clicked_at"):
                icons.append("🔗 Clicou")
            elif msg.get("opened_at"):
                icons.append("👀 Abriu")
            else:
                icons.append("📤 Enviado")
            tracking = " · ".join(icons)

            border_color = COLORS["success"] if msg.get("replied_at") else (
                COLORS["info"] if msg.get("clicked_at") or msg.get("opened_at") else "#9E9E9E"
            )

            escola_nome = comp.get("name", "?")
            sent_date = (msg.get("sent_at") or "")[:10]
            contato_info = f'{cont.get("full_name", "?")} ({cont.get("email", "?")})'

            with st.expander(f"{escola_nome}{fu_tag} — {msg.get('subject', '')[:50]} | {sent_date} | {tracking}"):
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

# --- TAB: PENDENTES (tela principal de aprovação) ---
with tab_pending:

    if total == 0:
        alert_banner("Nenhuma mensagem aguardando aprovacao.", "success")
        alert_banner("Execute o pipeline para gerar novas mensagens e volte aqui para aprova-las.", "info")
        if st.button("Verificar novamente", icon=":material/refresh:"):
            st.rerun()
        st.stop()

    st.markdown("")

# ===========================================================================
# ACOES EM MASSA — expander estilizado
# ===========================================================================
with st.expander("Acoes em massa", icon=":material/bolt:"):
    bulk_c1, bulk_c2, bulk_c3 = st.columns(3)
    with bulk_c1:
        if st.button(f"Rejeitar todas ({total})", icon=":material/block:",
                     help="Rejeita todas as mensagens pendentes", use_container_width=True):
            st.session_state["confirm_bulk_reject"] = True
    with bulk_c2:
        if st.button(f"Excluir todas ({total})", icon=":material/delete:",
                     help="Remove todas da fila (nao rejeita, apaga)", use_container_width=True):
            st.session_state["confirm_bulk_delete_queue"] = True
    with bulk_c3:
        if st.button("Aprovar todas", icon=":material/done_all:",
                     help="Aprova todas as mensagens pendentes", use_container_width=True):
            st.session_state["confirm_bulk_approve"] = True

    if st.session_state.get("confirm_bulk_reject"):
        reason = st.text_input("Motivo da rejeicao em massa (opcional):", key="bulk_reject_reason")
        br1, br2 = st.columns(2)
        with br1:
            if st.button("Sim, rejeitar todas", type="primary"):
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
            if st.button("Sim, excluir todas da fila", type="primary"):
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

        from datetime import datetime as _dt, time as _dtime, timedelta as _td, timezone as _tz
        bulk_schedule = st.toggle("⏰ Agendar envio em massa", value=False, key="bulk_schedule_toggle")
        bulk_sched_iso = None
        if bulk_schedule:
            bc1, bc2 = st.columns(2)
            with bc1:
                bulk_date = st.date_input("Data", value=_dt.now().date() + _td(days=1), min_value=_dt.now().date(), key="bulk_sched_date")
            with bc2:
                bulk_time = st.time_input("Horario", value=_dtime(8, 0), key="bulk_sched_time")
            bulk_sched_dt = _dt.combine(bulk_date, bulk_time, tzinfo=_tz(_td(hours=-3)))
            bulk_sched_iso = bulk_sched_dt.isoformat()
            st.caption(f"⏰ Todas serao enviadas em {bulk_date.strftime('%d/%m/%Y')} as {bulk_time.strftime('%H:%M')}")

        ba1, ba2 = st.columns(2)
        with ba1:
            label = "Sim, aprovar e agendar" if bulk_sched_iso else "Sim, aprovar todas"
            if st.button(label, type="primary"):
                count = 0
                for p in pending:
                    if queue_manager.approve(p["id"], scheduled_send_at=bulk_sched_iso):
                        count += 1
                msg = f"{count} mensagens aprovadas"
                if bulk_sched_iso:
                    msg += f" e agendadas para {bulk_date.strftime('%d/%m')} as {bulk_time.strftime('%H:%M')}"
                st.success(msg + ".")
                st.session_state.pop("confirm_bulk_approve", None)
                st.rerun()
        with ba2:
            if st.button("Cancelar", key="cancel_bulk_approve"):
                st.session_state.pop("confirm_bulk_approve", None)
                st.rerun()

# ===========================================================================
# NAVEGACAO — prev/next com indicador de posicao
# ===========================================================================
idx = min(st.session_state.current_idx, total - 1)
st.session_state.current_idx = idx

col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
with col_nav1:
    if st.button("Anterior", disabled=(idx == 0), icon=":material/chevron_left:",
                 use_container_width=True):
        st.session_state.current_idx = max(0, idx - 1)
        st.rerun()
with col_nav2:
    # Navigation dots / progress indicator
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
                 use_container_width=True):
        st.session_state.current_idx = min(total - 1, idx + 1)
        st.rerun()

st.markdown("")

# ===========================================================================
# ITEM ATUAL — card central de preview
# ===========================================================================
item = pending[idx]
queue_id = item.get("id", "")
company_data = item.get("companies") or {}
contact_data = item.get("contacts") or {}
contact_id = item.get("contact_id") or contact_data.get("id")
company_id = item.get("company_id")

col_info, col_msg = st.columns([1, 2])

# --- COLUNA ESQUERDA: Info da escola e destinatario ---
with col_info:
    # Card da escola
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

    # --- Buscar TODOS os contatos da escola ---
    all_school_contacts = []
    if company_id:
        try:
            all_school_contacts = db.client.table("contacts").select(
                "id,full_name,email,role,decision_maker_type,outreach_priority,source"
            ).eq("company_id", company_id).order("outreach_priority").execute().data or []
        except Exception:
            pass

    # --- Seletor de Destinatario ---
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
                    import re as _re
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

        # Destinatario card
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

    # --- Mini Mapa de Poder ---
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

    # --- Enviar tambem para outros contatos ---
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

# --- COLUNA DIREITA: Preview e edicao da mensagem ---
with col_msg:
    current_subject = item.get("subject", "")
    current_body = item.get("body", "")
    follow_up_number = item.get("follow_up_number", 0) or 0
    parent_id = item.get("parent_id")

    # --- HISTORICO DE MENSAGENS ANTERIORES (para follow-ups) ---
    if follow_up_number > 0 and parent_id:
        # Buscar toda a cadeia de mensagens anteriores (do mais recente ao original)
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
            # Mostrar em ordem cronologica (original primeiro)
            chain.reverse()

            # Badge do tipo de follow-up
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
                f'{fu_label} — {len(chain)} mensagem(ns) anterior(es)</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            with st.expander(f"📨 Ver mensagens anteriores ({len(chain)})", expanded=True):
                for i, prev_msg in enumerate(chain):
                    prev_fu = prev_msg.get("follow_up_number", 0) or 0
                    prev_label = "Email original" if prev_fu == 0 else f"Follow-up #{prev_fu}"
                    prev_sent = (prev_msg.get("sent_at") or "")[:10]
                    prev_status = prev_msg.get("status", "")

                    # Indicadores de tracking
                    tracking_icons = []
                    if prev_msg.get("opened_at"):
                        tracking_icons.append("👀 Abriu")
                    if prev_msg.get("clicked_at"):
                        tracking_icons.append("🔗 Clicou")
                    if prev_msg.get("replied_at"):
                        tracking_icons.append("💬 Respondeu")
                    if not tracking_icons and prev_status == "sent":
                        tracking_icons.append("📤 Enviado, sem abertura")
                    tracking_text = " · ".join(tracking_icons) if tracking_icons else ""

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
        f'<span style="font-weight:600;font-size:16px;color:#212121">Preview — {preview_label}</span>'
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

# ===========================================================================
# AGENDAMENTO DE ENVIO
# ===========================================================================
from datetime import datetime, time as dtime, timedelta, timezone

# Verificar se ja tem scheduled_send_at sugerido pelo smart_scheduler
existing_sched = item.get("scheduled_send_at")
if existing_sched:
    try:
        sched_preview = datetime.fromisoformat(existing_sched.replace("Z", "+00:00"))
        st.markdown(
            f'<div style="font-size:13px;color:#FF6D00;margin-bottom:8px">'
            f'⏰ <strong>Envio sugerido:</strong> {sched_preview.strftime("%d/%m/%Y as %H:%M")} '
            f'(calendario inteligente — baseado em tracking + fase letiva + feriados)</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass

schedule_send = st.toggle(
    "⏰ Alterar horario de envio",
    value=False,
    key=f"schedule_toggle_{queue_id}",
    help="Altere o horario sugerido ou defina um novo. Se desativado, usa o horario sugerido acima (ou envia imediatamente se nao houver).",
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
        f'⏰ Email sera enviado em <strong>{sched_date.strftime("%d/%m/%Y")} as {sched_time.strftime("%H:%M")}</strong> (horario de Brasilia)'
        f'</div>',
        unsafe_allow_html=True,
    )

# ===========================================================================
# BOTOES DE ACAO — grandes e coloridos
# ===========================================================================
st.markdown("")

# Custom CSS for large colored action buttons
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
            msg = "Mensagem aprovada!"
            if extra_count:
                msg += f" + {extra_count} copia(s) para outros contatos."
            st.success(msg)
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

# ===========================================================================
# PAINEIS EXPANDIVEIS — Rejeicao, Template, Teste
# ===========================================================================

# --- Rejeitar ---
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

# --- Template ---
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
            from utils.template_renderer import render_template
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
            alert_banner("Nenhum template ativo encontrado. Crie um em '8 - Templates'.", "warning")
            if st.button("Fechar", key=f"close_tmpl_{queue_id}"):
                st.session_state[f"show_template_{queue_id}"] = False
                st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar template: {e}")

# --- Enviar Teste ---
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
