"""Pagina 8 - Templates de Mensagem: crie e gerencie mensagens padrao.
Redesigned com Material Design theme — two-panel layout com template cards."""
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, breadcrumb, COLORS,
)

apply_theme_no_config()

# --- Header ---
breadcrumb(["IAprendo", "Templates de Mensagem"])
st.markdown("# Templates de Mensagem")
st.caption("Crie e gerencie mensagens padrao. Variaveis como {school_name} sao substituidas automaticamente.")

try:
    from database.supabase_client import db
    from utils.template_renderer import render_template, TEMPLATE_VARIABLES
    from utils.role_classifier import ROLE_LABELS, ALL_ROLE_TYPES
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.stop()

# --- Carregar templates existentes ---
try:
    templates = db.client.table("message_templates").select("*").order("created_at", desc=True).execute().data or []
except Exception as e:
    st.error(f"Erro ao buscar templates: {e}")
    templates = []

# --- Tabs: Gerenciar / Criar / Variaveis / Preview ---
tab_manage, tab_create, tab_vars, tab_preview = st.tabs([
    "Templates", "Criar Novo", "Variaveis", "Preview",
])

# =============================================================================
# TAB 1: GERENCIAR TEMPLATES — two-panel layout
# =============================================================================
with tab_manage:
    if not templates:
        alert_banner("Nenhum template criado ainda. Use a aba 'Criar Novo' para criar o primeiro.", "info")
    else:
        # Metrics row
        total = len(templates)
        active_count = len([t for t in templates if t.get("is_active")])
        default_count = len([t for t in templates if t.get("is_default")])
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card("Total", total, icon="description", color=COLORS["primary"])
        with c2:
            metric_card("Ativos", active_count, icon="check_circle", color=COLORS["success"])
        with c3:
            metric_card("Padrao", default_count, icon="star", color=COLORS["accent"])

        st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)

        # Template list as cards
        for tmpl in templates:
            tid = tmpl["id"]
            name = tmpl.get("name", "?")
            is_default = tmpl.get("is_default", False)
            is_active = tmpl.get("is_active", True)
            target = tmpl.get("target_role")
            target_label = ROLE_LABELS.get(target, "Todos") if target else "Todos"

            # Build badge HTML
            badges = ""
            if is_default:
                badges += status_badge("approved", "Padrao")
            if is_active:
                badges += " " + status_badge("active", "Ativo")
            else:
                badges += " " + status_badge("paused", "Inativo")

            # Card header
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

            is_editing = st.session_state.get(f"editing_{tid}", False)

            if not is_editing:
                # View mode — action buttons
                with st.expander(f"Ver corpo e acoes: {name}", expanded=False):
                    st.markdown(f"**Assunto:** {tmpl.get('subject_template', '')}")
                    st.text_area(
                        "Corpo:", value=tmpl.get("body_template", ""), height=150,
                        disabled=True, key=f"view_body_{tid}",
                    )
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if st.button("Editar", key=f"edit_{tid}"):
                            st.session_state[f"editing_{tid}"] = True
                            st.rerun()
                    with col2:
                        if not is_default and is_active:
                            if st.button("Tornar Padrao", key=f"default_{tid}"):
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
                            if st.button("Desativar", key=f"deactivate_{tid}"):
                                try:
                                    db.client.table("message_templates").update(
                                        {"is_active": False, "is_default": False}
                                    ).eq("id", tid).execute()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                        else:
                            if st.button("Reativar", key=f"reactivate_{tid}"):
                                try:
                                    db.client.table("message_templates").update(
                                        {"is_active": True}
                                    ).eq("id", tid).execute()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro: {e}")
                    with col4:
                        if st.button("Excluir", key=f"delete_{tid}"):
                            try:
                                db.client.table("message_templates").delete().eq("id", tid).execute()
                                alert_banner("Template excluido!", "success")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")
            else:
                # Edit mode
                with st.expander(f"Editando: {name}", expanded=True):
                    with st.form(key=f"edit_form_{tid}"):
                        edit_name = st.text_input(
                            "Nome:", value=tmpl.get("name", ""), key=f"edit_name_{tid}"
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
                            key=f"edit_role_{tid}",
                        )
                        edit_subject = st.text_input(
                            "Assunto:", value=tmpl.get("subject_template", ""), key=f"edit_subj_{tid}"
                        )
                        edit_body = st.text_area(
                            "Corpo:", value=tmpl.get("body_template", ""), height=250, key=f"edit_body_{tid}"
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
                                st.session_state[f"editing_{tid}"] = False
                                alert_banner("Template atualizado!", "success")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")
                        if cancel_btn:
                            st.session_state[f"editing_{tid}"] = False
                            st.rerun()

# =============================================================================
# TAB 2: CRIAR NOVO TEMPLATE
# =============================================================================
with tab_create:
    section_header("Novo Template", "add_circle_outline")
    with st.form(key="new_template_form"):
        t_name = st.text_input("Nome do template:", placeholder="Primeiro contato - Geral")
        t_role = st.selectbox(
            "Para qual cargo?", ["Todos"] + [ROLE_LABELS[r] for r in ALL_ROLE_TYPES]
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

# =============================================================================
# TAB 3: VARIAVEIS DISPONIVEIS — copyable chips
# =============================================================================
with tab_vars:
    section_header("Variaveis Disponiveis", "data_object")
    st.markdown(
        "Use estas variaveis no assunto e corpo do template. "
        "Elas serao substituidas automaticamente pelos dados reais de cada escola."
    )

    # Render as styled chips
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

# =============================================================================
# TAB 4: PREVIEW COM DADOS REAIS
# =============================================================================
with tab_preview:
    section_header("Preview com Dados Reais", "preview")
    active_templates = [t for t in templates if t.get("is_active")]
    if not active_templates:
        alert_banner("Crie um template ativo para ver o preview.", "info")
    else:
        try:
            schools = db.client.table("companies").select(
                "id,name,city,state,education_levels,admin_category,qualification_score"
            ).order("qualification_score", desc=True).limit(20).execute().data or []
        except Exception:
            schools = []

        if schools:
            col_tmpl, col_school = st.columns(2)
            with col_tmpl:
                selected_tmpl = st.selectbox(
                    "Template:",
                    active_templates,
                    format_func=lambda t: t.get("name", "?"),
                    key="preview_tmpl",
                )
            with col_school:
                selected_school = st.selectbox(
                    "Escola:",
                    schools,
                    format_func=lambda s: f"{s.get('name', '?')} ({s.get('city', '')})",
                    key="preview_school",
                )

            if selected_tmpl and selected_school:
                # Buscar melhor contato
                contacts = db.client.table("contacts").select("*").eq(
                    "company_id", selected_school["id"]
                ).order("outreach_priority").execute().data or []
                contact = contacts[0] if contacts else {"full_name": "Diretor(a)", "role": "Diretor(a)"}

                rendered = render_template(
                    selected_tmpl["subject_template"],
                    selected_tmpl["body_template"],
                    selected_school,
                    contact,
                )

                # Render in a styled card
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
                    key="preview_result",
                )
        else:
            alert_banner("Nenhuma escola no banco para preview.", "info")
