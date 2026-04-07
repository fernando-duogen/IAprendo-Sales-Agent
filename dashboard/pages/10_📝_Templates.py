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
breadcrumb(["IAprendo", "Templates e Assinatura"])
st.markdown("# Templates e Assinatura")
st.caption("Gerencie mensagens padrao e configure a assinatura que vai em todos os emails.")

# =============================================================================
# ASSINATURA DE EMAIL (no topo, antes dos templates)
# =============================================================================
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
        sig_enabled = st.toggle("Assinatura ativa", value=sig.get("enabled", True), key="sig_enabled")
        sig_text = st.text_area(
            "Texto da assinatura",
            value=sig.get("text", ""),
            height=120,
            key="sig_text",
            placeholder="Fernando Nienaber\nIAprendo - Plataforma Educacional\n(51) 99642-2564\nwww.iaprendo.com.br",
            help="Cada linha aparece separada. Use para nome, cargo, empresa, telefone, site.",
        )
        sig_image_url = st.text_input(
            "URL da imagem (logo/banner)",
            value=sig.get("image_url", ""),
            key="sig_image_url",
            placeholder="https://exemplo.com/logo.png",
            help="Cole a URL publica da imagem. Use um servico de hospedagem (Imgur, Google Drive publico, etc).",
        )
        sig_col_a, sig_col_b = st.columns(2)
        with sig_col_a:
            sig_image_width = st.number_input(
                "Largura da imagem (px)",
                min_value=50, max_value=600, step=10,
                value=int(sig.get("image_width", 200)),
                key="sig_image_width",
            )
        with sig_col_b:
            sig_link_url = st.text_input(
                "Link ao clicar na imagem (opcional)",
                value=sig.get("link_url", ""),
                key="sig_link_url",
                placeholder="https://iaprendo.com.br",
            )
        sig_separator = st.checkbox(
            "Mostrar linha separadora acima da assinatura",
            value=sig.get("separator", True),
            key="sig_separator",
        )

        if st.button("💾 Salvar assinatura", type="primary", use_container_width=True, key="btn_save_sig"):
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
        # Gerar preview em tempo real
        preview_sig = {
            "enabled": sig_enabled,
            "text": sig_text,
            "image_url": sig_image_url.strip(),
            "image_width": int(sig_image_width),
            "image_alt": "Logo",
            "link_url": sig_link_url.strip(),
            "separator": sig_separator,
        }
        # Temporariamente gerar HTML sem salvar
        from integrations.email_signature import EmailSignature
        temp_sig = EmailSignature()
        temp_sig.get_signature = lambda: preview_sig
        preview_html = temp_sig.render_html()

        if preview_html:
            # Simular um email com assinatura
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
        test_email = st.text_input(
            "Email para teste",
            placeholder="seu@email.com",
            key="sig_test_email",
        )
    with test_col2:
        st.markdown('<div style="margin-top:28px"></div>', unsafe_allow_html=True)
        if st.button("📧 Enviar teste", use_container_width=True, key="btn_test_sig"):
            if not test_email or "@" not in test_email:
                st.error("Digite um email valido.")
            else:
                try:
                    from tools.brevo_sender import BrevoSender
                    sender = BrevoSender()
                    result = sender.send_email(
                        to_email=test_email.strip(),
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
                        st.success(f"Email de teste enviado para {test_email}! Verifique sua caixa de entrada.")
                    else:
                        st.error(f"Falha no envio: {result.get('error', 'erro desconhecido')}")
                except Exception as e:
                    st.error(f"Erro: {e}")

except Exception as e:
    st.warning(f"Assinatura indisponivel: {e}")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# TEMPLATES DE MENSAGEM (conteudo original da pagina)
# =============================================================================

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
