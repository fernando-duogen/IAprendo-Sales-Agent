"""Pagina 3 - Gestao de Escolas: tabela com edicao inline e detalhe Material Design."""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, avatar, breadcrumb, timeline_item, COLORS, STATUS_COLORS,
    score_color,
)
from utils.fit_score import calcular_fit_score, fit_emoji, fit_cor_hex

apply_theme_no_config()

STATUS_PT = {
    "raw": "Novo",
    "qualified": "Qualificado",
    "enriched": "Enriquecido",
    "contacted": "Contatado",
    "responded": "Respondeu",
    "converted": "Convertido",
    "rejected": "Descartado",
}
PT_TO_EN = {v: k for k, v in STATUS_PT.items()}

QUEUE_STATUS_PT = {
    "pending": "Pendente",
    "approved": "Aprovada",
    "rejected": "Rejeitada",
    "sent": "Enviada",
}

PORTE_SHORT = {
    "Ate 50 matriculas de escolarizacao": "< 50",
    "Entre 51 e 200 matriculas de escolarizacao": "51-200",
    "Entre 201 e 500 matriculas de escolarizacao": "201-500",
    "Entre 501 e 1000 matriculas de escolarizacao": "501-1000",
    "Mais de 1000 matriculas de escolarizacao": "1000+",
}

try:
    from database.supabase_client import db
except Exception as e:
    st.error(f"Erro ao conectar ao banco: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "escola_detail_id" not in st.session_state:
    st.session_state.escola_detail_id = None
if "escola_msg" not in st.session_state:
    st.session_state.escola_msg = None


def go_to_detail(company_id: str) -> None:
    st.session_state.escola_detail_id = company_id


def go_to_list() -> None:
    st.session_state.escola_detail_id = None


# ===========================================================================
# MODO DETALHE
# ===========================================================================
if st.session_state.escola_detail_id:
    company_id = st.session_state.escola_detail_id
    company = db.get_company_detail(company_id)

    if not company:
        st.error("Escola nao encontrada.")
        go_to_list()
        st.rerun()

    # --- Breadcrumb ---
    breadcrumb(["Escolas", company.get("name", "Detalhe")])

    # --- Voltar ---
    if st.button("Voltar a lista", icon=":material/arrow_back:"):
        go_to_list()
        st.rerun()

    # --- Mensagem de feedback ---
    if st.session_state.escola_msg:
        msg_type, msg_text = st.session_state.escola_msg
        if msg_type == "success":
            alert_banner(msg_text, "success")
        elif msg_type == "error":
            alert_banner(msg_text, "error")
        st.session_state.escola_msg = None

    # --- Cabecalho com card e metricas ---
    status_en = company.get("status", "raw")
    status_label = STATUS_PT.get(status_en, status_en)
    sc = company.get("qualification_score") or 0
    fonte_dados = company.get("fonte_dados") or ""

    # Calcular Fit Score IAprendo
    fit_result = calcular_fit_score(company)
    fit_val = fit_result["score"]
    fit_level = fit_result["level"]
    fit_motivo = fit_result["motivo"]

    # Badge de fonte dos dados (so mostra se for catalogo_inep — aviso)
    fonte_badge_html = ""
    if fonte_dados == "catalogo_inep":
        fonte_badge_html = (
            '<div style="display:inline-flex; align-items:center; gap:4px; '
            'background:#fff3e0; color:#e65100; padding:2px 10px; border-radius:12px; '
            'font-size:11px; font-weight:600; margin-top:4px;">'
            '&#9888; Catalogo INEP &middot; sem dados do Censo 2025'
            '</div>'
        )
    elif fonte_dados == "censo_2025":
        fonte_badge_html = (
            '<div style="display:inline-flex; align-items:center; gap:4px; '
            'background:#e8f5e9; color:#2e7d32; padding:2px 10px; border-radius:12px; '
            'font-size:11px; font-weight:600; margin-top:4px;">'
            '&#10004; Censo 2025'
            '</div>'
        )

    bairro_txt = f" &middot; {company.get('bairro')}" if company.get('bairro') else ""

    # Badge do Fit Score (so se tiver dados)
    fit_badge_html = ""
    if fit_val is not None:
        fit_color = fit_cor_hex(fit_level)
        fit_emoji_char = fit_emoji(fit_level)
        fit_badge_html = (
            f'<div style="display:flex; flex-direction:column; align-items:center; '
            f'padding:0 8px; border-right:1px solid #e0e0e0; margin-right:8px;">'
            f'<span style="font-size:9px; color:#757575; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Fit</span>'
            f'<span style="font-size:22px; font-weight:700; color:{fit_color};">{fit_emoji_char} {fit_val}</span>'
            f'<span style="font-size:9px; color:#757575;">/ 100</span>'
            f'</div>'
        )

    st.markdown(f"""
    <div class="data-card" style="border-left: 4px solid {COLORS['primary']}; padding: 20px 24px;">
        <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">
            {avatar(company.get('name', '?'), COLORS['primary'])}
            <div style="flex:1;">
                <div style="font-size:22px; font-weight:700; color:#212121;">{company.get('name', '?')}</div>
                <div style="font-size:14px; color:#757575; margin-top:2px;">
                    {company.get('city', '')}/{company.get('state', '')}{bairro_txt} &middot; INEP: {company.get('inep_code', '')}
                </div>
                {fonte_badge_html}
            </div>
            <div style="display:flex; gap:12px; align-items:center;">
                {status_badge(status_en, status_label)}
                {fit_badge_html}
                <div style="display:flex; flex-direction:column; align-items:center;">
                    <span style="font-size:9px; color:#757575; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Score IA</span>
                    <span style="font-size:22px; font-weight:700; color:{score_color(sc)};">{sc}</span>
                    <span style="font-size:9px; color:#757575;">/ 100</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Caption com motivo do Fit
    if fit_val is not None and fit_motivo:
        st.caption(f"**Fit IAprendo:** {fit_motivo}")

    st.markdown("")

    # --- Tabs ---
    tab_dados, tab_contatos, tab_msgs, tab_hist, tab_acoes = st.tabs([
        "Dados", "Contatos", "Mensagens", "Historico", "Acoes"
    ])

    # === TAB DADOS (edicao) ===
    with tab_dados:
        section_header("Informacoes da Escola", "edit")
        with st.form("edit_company"):
            c1, c2 = st.columns(2)
            with c1:
                edit_name = st.text_input("Nome", value=company.get("name", ""))
                edit_city = st.text_input("Cidade", value=company.get("city", ""))
                edit_state = st.text_input("UF", value=company.get("state", ""), max_chars=2)
                edit_address = st.text_input("Endereco", value=company.get("address", "") or "")
                edit_phone = st.text_input("Telefone", value=company.get("phone", "") or "")
                edit_website = st.text_input("Website", value=company.get("website", "") or "")
            with c2:
                status_options = list(STATUS_PT.values())
                current_status_pt = STATUS_PT.get(company.get("status", "raw"), "Novo")
                edit_status = st.selectbox("Status", status_options, index=status_options.index(current_status_pt))
                edit_score = st.number_input("Score", min_value=0, max_value=100,
                    value=int(company.get("qualification_score") or 0))
                st.text_input("INEP", value=company.get("inep_code", ""), disabled=True)
                st.text_input("Porte", value=company.get("school_size", "") or "", disabled=True)
                st.text_input("Niveis de ensino", value=company.get("education_levels", "") or "", disabled=True)
                st.text_input("Dep. Administrativa", value=company.get("admin_dependency", "") or "", disabled=True)

            if st.form_submit_button("Salvar alteracoes", type="primary", icon=":material/save:"):
                updates = {
                    "name": edit_name,
                    "city": edit_city,
                    "state": edit_state.upper(),
                    "address": edit_address,
                    "phone": edit_phone,
                    "website": edit_website,
                    "status": PT_TO_EN.get(edit_status, "raw"),
                    "qualification_score": edit_score,
                }
                result = db.update_company(company_id, updates)
                if result is not None:
                    st.session_state.escola_msg = ("success", "Dados salvos com sucesso!")
                else:
                    st.session_state.escola_msg = ("error", "Erro ao salvar.")
                st.rerun()

        # =====================================================================
        # CARDS DE DADOS DO CENSO 2025 (escala, equipe, tecnologia)
        # =====================================================================
        fonte = company.get("fonte_dados") or ""
        total_mat = company.get("total_matriculas") or 0

        if fonte == "catalogo_inep":
            # Aviso: escola do catalogo — sem dados ricos
            alert_banner(
                "Escola ativa no Cat&aacute;logo INEP mas n&atilde;o enviou dados ao Censo 2025. "
                "Dados de matr&iacute;culas, equipe e n&iacute;vel tecnol&oacute;gico n&atilde;o est&atilde;o dispon&iacute;veis.",
                "warning",
            )
        elif fonte == "censo_2025" and total_mat > 0:
            st.markdown("")
            section_header("Escala e Matr&iacute;culas (Censo 2025)", "groups")

            # Metricas rapidas
            mat_fund_af = int(company.get("matriculas_fund_af") or 0)
            mat_medio = int(company.get("matriculas_medio") or 0)
            alunos_alvo = mat_fund_af + mat_medio
            perc_integral = company.get("perc_integral")

            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                metric_card(
                    "Total alunos",
                    f"{int(total_mat):,}".replace(",", "."),
                    COLORS["primary"],
                    icon="groups",
                )
            with mcol2:
                metric_card(
                    "Alvo IAprendo",
                    f"{alunos_alvo:,}".replace(",", "."),
                    COLORS["accent"],
                    icon="track_changes",
                )
            with mcol3:
                metric_card(
                    "Fund AF (6o-9o)",
                    f"{mat_fund_af:,}".replace(",", "."),
                    COLORS["info"],
                    icon="school",
                )
            with mcol4:
                metric_card(
                    "Medio (1o-3o)",
                    f"{mat_medio:,}".replace(",", "."),
                    COLORS["secondary"],
                    icon="auto_stories",
                )

            # Grafico de barras horizontais: matriculas por ano
            series_data = []
            for label, key, segmento in [
                ("6o ano", "mat_6_ano", "Fund AF"),
                ("7o ano", "mat_7_ano", "Fund AF"),
                ("8o ano", "mat_8_ano", "Fund AF"),
                ("9o ano", "mat_9_ano", "Fund AF"),
                ("1o medio", "mat_medio_1", "Medio"),
                ("2o medio", "mat_medio_2", "Medio"),
                ("3o medio", "mat_medio_3", "Medio"),
            ]:
                val = company.get(key) or 0
                if val > 0:
                    series_data.append({"Ano/Serie": label, "Alunos": int(val), "Segmento": segmento})

            if series_data:
                try:
                    import plotly.express as px
                    df_series = pd.DataFrame(series_data)
                    fig = px.bar(
                        df_series,
                        x="Alunos",
                        y="Ano/Serie",
                        color="Segmento",
                        orientation="h",
                        color_discrete_map={"Fund AF": COLORS["info"], "Medio": COLORS["secondary"]},
                        text="Alunos",
                        height=320,
                    )
                    fig.update_traces(textposition="outside", cliponaxis=False)
                    fig.update_layout(
                        yaxis=dict(autorange="reversed", title=""),
                        xaxis=dict(title="Matriculas"),
                        margin=dict(l=0, r=40, t=30, b=0),
                        plot_bgcolor="white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.info("Plotly nao instalado — grafico nao disponivel.")
            else:
                st.caption("Sem dados de matriculas por ano/serie disponiveis.")

            # Info extra de escala
            info_escala = []
            if perc_integral:
                info_escala.append(f"**{perc_integral}%** em tempo integral")
            alunos_doc = company.get("alunos_por_docente")
            if alunos_doc:
                info_escala.append(f"**{alunos_doc}** alunos por docente")
            mat_integral = company.get("matriculas_integral") or 0
            if mat_integral > 0:
                info_escala.append(f"**{int(mat_integral)}** em integral")
            if info_escala:
                st.caption(" &middot; ".join(info_escala))

            # Equipe
            st.markdown("")
            section_header("Equipe e Decisores (Censo 2025)", "badge")
            docentes = int(company.get("total_docentes") or 0)
            gestores = int(company.get("total_gestores") or 0)
            coord = int(company.get("qt_coordenadores") or 0)
            turmas = int(company.get("total_turmas") or 0)

            ec1, ec2, ec3, ec4 = st.columns(4)
            with ec1:
                metric_card("Docentes", docentes, COLORS["primary"], icon="record_voice_over")
            with ec2:
                metric_card(
                    "Coordenadores",
                    coord,
                    COLORS["accent"],
                    icon="supervisor_account",
                )
            with ec3:
                metric_card("Gestores", gestores, COLORS["secondary"], icon="manage_accounts")
            with ec4:
                metric_card("Turmas", turmas, COLORS["info"], icon="class")

            if coord > 0:
                st.caption(
                    "&#9989; Coordenador pedagogico presente — decisor tecnico claro para venda de edtech."
                )
            else:
                st.caption(
                    "&#9888; Sem coordenador pedagogico cadastrado — decisao pode passar diretamente pelo(a) diretor(a)."
                )

            # Tecnologia
            st.markdown("")
            section_header("Tecnologia (Censo 2025)", "router")
            nivel_tech = company.get("nivel_tecnologico") or "-"
            tech_color = {
                "Alto": COLORS["success"],
                "Medio": COLORS["warning"],
                "M&eacute;dio": COLORS["warning"],
                "Médio": COLORS["warning"],
                "Baixo": COLORS["error"],
            }.get(nivel_tech, COLORS["secondary"])

            def _bool_badge(label, val):
                if val is True:
                    return f'<span style="display:inline-block;background:#e8f5e9;color:#2e7d32;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;margin:2px;">&#10004; {label}</span>'
                elif val is False:
                    return f'<span style="display:inline-block;background:#ffebee;color:#c62828;padding:4px 10px;border-radius:12px;font-size:12px;font-weight:600;margin:2px;">&#10006; {label}</span>'
                return ""

            nivel_html = (
                f'<span style="display:inline-block;background:{tech_color};color:white;'
                f'padding:6px 14px;border-radius:16px;font-size:13px;font-weight:700;margin-right:8px;">'
                f"Nivel {nivel_tech}</span>"
            )

            badges_html = (
                nivel_html
                + _bool_badge("Banda larga", company.get("banda_larga"))
                + _bool_badge("Internet alunos", company.get("internet_alunos"))
                + _bool_badge("Internet aprendizagem", company.get("internet_aprendizagem"))
                + _bool_badge("Lab informatica", company.get("lab_informatica"))
            )
            st.markdown(
                f'<div style="margin:8px 0 16px 0;">{badges_html}</div>',
                unsafe_allow_html=True,
            )

            # Dispositivos (se tiver)
            qt_desk = company.get("qt_desktop_aluno") or 0
            qt_note = company.get("qt_notebook_aluno") or 0
            qt_tab = company.get("qt_tablet_aluno") or 0
            if qt_desk + qt_note + qt_tab > 0:
                disp_cols = st.columns(3)
                with disp_cols[0]:
                    metric_card("Desktops p/ aluno", int(qt_desk), COLORS["secondary"], icon="computer")
                with disp_cols[1]:
                    metric_card("Notebooks p/ aluno", int(qt_note), COLORS["info"], icon="laptop")
                with disp_cols[2]:
                    metric_card("Tablets p/ aluno", int(qt_tab), COLORS["accent"], icon="tablet")

    # === TAB CONTATOS ===
    with tab_contatos:
        section_header("Contatos da Escola", "people")
        contacts = db.get_contacts_by_company(company_id)
        if not contacts:
            alert_banner("Nenhum contato encontrado. Use o botao abaixo para buscar.", "info")
        else:
            for ct in contacts:
                ct_color = COLORS["success"] if ct.get("email") else COLORS["warning"]
                email_str = ct.get("email", "") or "sem email"
                phone_str = ct.get("phone", "")
                st.markdown(f"""
                <div class="data-card" style="border-left: 4px solid {ct_color};">
                    <div style="display:flex; align-items:center; gap:12px;">
                        {avatar(ct.get('full_name', '?'), ct_color)}
                        <div style="flex:1;">
                            <div style="font-weight:600; font-size:14px; color:#212121;">{ct.get('full_name', '?')}</div>
                            <div style="font-size:12px; color:#757575;">{ct.get('role', '?')} &middot; {ct.get('decision_maker_type', '')} &middot; {ct.get('source', '')}</div>
                            <div style="font-size:12px; color:#757575; margin-top:2px;">{email_str}{' &middot; ' + phone_str if phone_str else ''}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("")
            with st.expander("Excluir contatos"):
                for ct in contacts:
                    if st.button(f"Excluir {ct.get('full_name', '?')}", key=f"del_ct_{ct['id']}"):
                        db.delete_contact(ct["id"])
                        st.session_state.escola_msg = ("success", "Contato excluido.")
                        st.rerun()

        # Formulario para adicionar contato manualmente
        with st.expander("➕ Adicionar contato manualmente"):
            CARGO_OPTIONS = [
                "Diretor(a)", "Vice-Diretor(a)", "Coordenador(a) Pedagógico(a)",
                "Secretário(a)", "Administrativo", "Professor(a)", "Outro",
            ]
            TIPO_DECISOR_OPTIONS = {
                "Diretor(a)": "diretor",
                "Vice-Diretor(a)": "vice_diretor",
                "Coordenador(a) Pedagógico(a)": "coordenador_pedagogico",
                "Secretário(a)": "secretaria",
                "Administrativo": "administrativo",
                "Professor(a)": "outro",
                "Outro": "outro",
            }
            PRIORIDADE_MAP = {
                "diretor": 1, "vice_diretor": 2, "coordenador_pedagogico": 3,
                "secretaria": 4, "administrativo": 5, "outro": 6,
            }

            with st.form("add_contact_form"):
                ac_col1, ac_col2 = st.columns(2)
                with ac_col1:
                    new_name = st.text_input("Nome completo *", placeholder="Ex: João da Silva")
                    new_email = st.text_input("Email", placeholder="Ex: joao@escola.com.br")
                    new_phone = st.text_input("Telefone", placeholder="Ex: (51) 99999-9999")
                with ac_col2:
                    new_cargo = st.selectbox("Cargo", options=CARGO_OPTIONS, index=0)
                    new_whatsapp = st.text_input("WhatsApp", placeholder="Ex: (51) 99999-9999")
                    new_linkedin = st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/...")

                if st.form_submit_button("💾 Adicionar contato", type="primary", use_container_width=True):
                    if not new_name or len(new_name.strip()) < 3:
                        st.error("Nome e obrigatorio (minimo 3 caracteres).")
                    elif not new_email and not new_phone and not new_whatsapp:
                        st.error("Informe pelo menos um dado de contato (email, telefone ou WhatsApp).")
                    else:
                        tipo_decisor = TIPO_DECISOR_OPTIONS.get(new_cargo, "outro")
                        prioridade = PRIORIDADE_MAP.get(tipo_decisor, 6)
                        contact_data = {
                            "company_id": company_id,
                            "full_name": new_name.strip(),
                            "role": new_cargo,
                            "decision_maker_type": tipo_decisor,
                            "outreach_priority": prioridade,
                            "source": "manual",
                        }
                        if new_email and "@" in new_email:
                            contact_data["email"] = new_email.strip()
                        if new_phone:
                            contact_data["phone"] = new_phone.strip()
                        if new_whatsapp:
                            contact_data["phone_whatsapp"] = new_whatsapp.strip()
                        if new_linkedin:
                            contact_data["linkedin_url"] = new_linkedin.strip()

                        try:
                            result = db.client.table("contacts").insert(contact_data).execute()
                            if result.data:
                                st.session_state.escola_msg = ("success", f"Contato {new_name} adicionado!")
                                st.rerun()
                            else:
                                st.error("Falha ao adicionar.")
                        except Exception as e:
                            st.error(f"Erro: {e}")

        # Botao Perplexity
        st.divider()
        if st.button("Buscar contatos no Perplexity", icon=":material/search:", help="Abre o Perplexity no navegador e busca a equipe de gestao desta escola"):
            import subprocess, json as json_mod
            school_name = company.get("name", "")
            city = company.get("city", "")
            state = company.get("state", "")
            python_exe = str(ROOT / "venv" / "Scripts" / "python.exe")
            script = (
                "import json, sys, os, logging; "
                "sys.stdout.reconfigure(encoding='utf-8'); "
                "sys.path.insert(0, '.'); "
                "logging.disable(logging.CRITICAL); "
                "os.environ['IAPRENDO_QUIET']='1'; "
                "from tools.perplexity_browser import perplexity_browser; "
                f"r = perplexity_browser.search_school_contacts({school_name!r}, {city!r}, {state!r}); "
                "perplexity_browser._close(); "
                "print('PERPLEXITY_JSON_START'); "
                "print(json.dumps(r, ensure_ascii=True)); "
                "print('PERPLEXITY_JSON_END')"
            )
            with st.spinner("Buscando no Perplexity (pode levar 30-60 segundos)..."):
                try:
                    import os as _os
                    env = _os.environ.copy()
                    env["PYTHONIOENCODING"] = "utf-8"
                    proc = subprocess.run(
                        [python_exe, "-c", script],
                        capture_output=True, text=True, timeout=120,
                        cwd=str(ROOT), encoding="utf-8", errors="replace",
                        env=env,
                    )
                    if proc.returncode == 0 and "PERPLEXITY_JSON_START" in proc.stdout:
                        json_text = proc.stdout.split("PERPLEXITY_JSON_START")[1].split("PERPLEXITY_JSON_END")[0].strip()
                        found = json_mod.loads(json_text)
                    else:
                        found = []
                        if proc.stderr:
                            st.caption(f"Log: {proc.stderr[-300:]}")
                except subprocess.TimeoutExpired:
                    found = []
                    st.warning("Timeout: a busca excedeu 2 minutos.")
                except Exception as e:
                    found = []
                    st.error(f"Erro ao executar: {e}")
            if found:
                st.session_state["perplexity_results"] = found
                st.session_state["perplexity_company_id"] = company_id
                st.rerun()
            else:
                st.warning("Nenhum contato encontrado. Tente pesquisar manualmente.")

        # --- Exibir resultados do Perplexity para confirmacao ---
        if st.session_state.get("perplexity_company_id") == company_id and st.session_state.get("perplexity_results"):
            found = st.session_state["perplexity_results"]
            has_suggested = any(ct.get("_suggested_email") for ct in found)
            alert_banner(f"Perplexity encontrou {len(found)} contato(s). Selecione quais importar:", "success")
            if has_suggested:
                alert_banner("Emails sugeridos por padrao detectado (marcados com ?). Verifique antes de importar.", "info")
            import json as json_mod
            from utils.role_classifier import classify_role
            selected_to_import = []
            for i, ct in enumerate(found):
                is_general = ct.get("_is_general_email", False)
                label_parts = [ct.get("full_name", "?"), f"-- {ct.get('role', '?')}"]
                if ct.get("email"):
                    label_parts.append(f"| {ct['email']}")
                elif ct.get("_suggested_email"):
                    label_parts.append(f"| {ct['_suggested_email']} (sugerido)")
                if ct.get("phone"):
                    label_parts.append(f"| {ct['phone']}")
                if is_general:
                    label_parts.append("[DEPARTAMENTO]")
                label = " ".join(label_parts)
                default = not is_general
                if st.checkbox(label, value=default, key=f"ppx_import_{company_id}_{i}"):
                    selected_to_import.append(ct)

            ic1, ic2 = st.columns(2)
            with ic1:
                if st.button(f"Importar {len(selected_to_import)} selecionados", type="primary", disabled=len(selected_to_import) == 0):
                    saved_count = 0
                    for ct in selected_to_import:
                        existing_match = [c for c in (contacts or []) if
                            (c.get("full_name", "").lower() == ct.get("full_name", "").lower()) or
                            (ct.get("email") and c.get("email", "").lower() == ct.get("email", "").lower())]
                        if existing_match:
                            continue
                        dm_type, priority = classify_role(ct.get("role", ""))
                        ct_data_new = {
                            "company_id": company_id,
                            "full_name": ct["full_name"],
                            "role": ct.get("role", ""),
                            "source": "perplexity",
                            "confidence_score": ct.get("confidence_score", 60),
                            "decision_maker_type": dm_type,
                            "outreach_priority": priority,
                        }
                        email = ct.get("email") or ct.get("_suggested_email")
                        if email:
                            ct_data_new["email"] = email
                            if ct.get("_suggested_email") and not ct.get("email"):
                                ct_data_new["email_verified"] = False
                                ct_data_new["notes"] = "Email sugerido por padrao (nao verificado)"
                        if ct.get("phone"):
                            ct_data_new["phone"] = ct["phone"]
                        if ct.get("_is_general_email"):
                            ct_data_new["decision_maker_type"] = "administrativo"
                            ct_data_new["outreach_priority"] = 99
                        if db.insert_contact(ct_data_new):
                            saved_count += 1
                    st.session_state.pop("perplexity_results", None)
                    st.session_state.pop("perplexity_company_id", None)
                    st.session_state.escola_msg = ("success", f"{saved_count} contatos importados via Perplexity!")
                    st.rerun()
            with ic2:
                if st.button("Descartar resultados"):
                    st.session_state.pop("perplexity_results", None)
                    st.session_state.pop("perplexity_company_id", None)
                    st.rerun()

    # === TAB MENSAGENS ===
    with tab_msgs:
        section_header("Mensagens na Fila", "mail")
        queue_items = db.get_queue_by_company(company_id)
        if not queue_items:
            alert_banner("Nenhuma mensagem na fila.", "info")
        else:
            for qi in queue_items:
                q_status = QUEUE_STATUS_PT.get(qi.get("status", ""), qi.get("status", ""))
                q_status_en = qi.get("status", "pending")
                created = qi.get("created_at", "")[:16].replace("T", " ") if qi.get("created_at") else ""
                with st.expander(f"{q_status} | {qi.get('subject', 'Sem assunto')} | {created}"):
                    st.text(qi.get("body", ""))
                    if qi.get("rejection_reason"):
                        st.caption(f"Motivo: {qi['rejection_reason']}")

    # === TAB HISTORICO ===
    with tab_hist:
        section_header("Historico de Interacoes", "history")
        interactions = db.get_interactions_by_company(company_id)
        if not interactions:
            alert_banner("Nenhuma interacao registrada.", "info")
        else:
            timeline_html = ""
            for ix in interactions:
                created = ix.get("created_at", "")[:16].replace("T", " ") if ix.get("created_at") else ""
                subject_str = f" -- {ix['subject']}" if ix.get("subject") else ""
                timeline_html += timeline_item(
                    date=created,
                    title=f"{ix.get('type', '?')} via {ix.get('channel', '?')}",
                    detail=subject_str,
                    color=COLORS["primary"],
                )
            st.markdown(timeline_html, unsafe_allow_html=True)

    # === TAB ACOES ===
    with tab_acoes:
        section_header("Acoes", "settings")
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            queue_count = len(db.get_queue_by_company(company_id))
            if queue_count > 0:
                if st.button(f"Limpar fila ({queue_count} itens)", icon=":material/delete_sweep:"):
                    db.delete_queue_items(company_id)
                    st.session_state.escola_msg = ("success", f"{queue_count} itens removidos.")
                    st.rerun()
        with ac2:
            if st.button("Resetar para Novo", icon=":material/restart_alt:"):
                db.reset_company_status(company_id, "raw")
                st.session_state.escola_msg = ("success", "Status resetado.")
                st.rerun()
        with ac3:
            if st.button("Excluir escola", type="primary", icon=":material/delete_forever:"):
                st.session_state["confirm_delete"] = company_id

        if st.session_state.get("confirm_delete") == company_id:
            alert_banner(f"Excluir {company.get('name')} e todos os dados relacionados?", "error")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("Sim, excluir tudo", type="primary"):
                    db.delete_company(company_id)
                    st.session_state.pop("confirm_delete", None)
                    go_to_list()
                    st.rerun()
            with dc2:
                if st.button("Cancelar"):
                    st.session_state.pop("confirm_delete", None)
                    st.rerun()

# ===========================================================================
# MODO LISTA (tabela com data_editor)
# ===========================================================================
else:
    section_header("Escolas", "school")

    # Buscar dados — inclui campos ricos do Censo 2025
    try:
        result = db.client.table("companies").select(
            "id, name, city, state, bairro, status, qualification_score, "
            "school_size, admin_dependency, admin_category, categoria_privada, "
            "inep_code, created_at, fonte_dados, "
            "matriculas_fund_af, matriculas_medio, total_docentes, "
            "qt_coordenadores, nivel_tecnologico"
        ).order("created_at", desc=True).limit(1000).execute()
        rows = result.data or []
    except Exception as e:
        st.error(f"Erro ao carregar escolas: {e}")
        st.stop()

    if not rows:
        alert_banner("Nenhuma escola importada. Use '1 - Importar Escolas' para comecar.", "info")
        st.stop()

    df = pd.DataFrame(rows)

    # Preparar colunas para exibicao
    df["Status"] = df["status"].map(lambda x: STATUS_PT.get(x, x))
    df["Score"] = df["qualification_score"].fillna(0).astype(int)
    df["Porte"] = df["school_size"].fillna("").map(lambda x: PORTE_SHORT.get(x.strip(), x[:15] if x else ""))
    df["Tipo"] = df["admin_dependency"].fillna("")
    df["UF"] = df["state"].fillna("")
    df["Bairro"] = df["bairro"].fillna("")
    df["Fund AF"] = df["matriculas_fund_af"].fillna(0).astype(int)
    df["Medio"] = df["matriculas_medio"].fillna(0).astype(int)
    df["Coord"] = df["qt_coordenadores"].fillna(0).astype(int)
    df["Tech"] = df["nivel_tecnologico"].fillna("-")
    df["Fonte"] = df["fonte_dados"].fillna("-").map(
        lambda x: {"censo_2025": "Censo 2025", "catalogo_inep": "Catalogo INEP"}.get(x, "-")
    )
    df["Importado"] = pd.to_datetime(df["created_at"]).dt.strftime("%d/%m/%Y")

    # Fit Score IAprendo (calculado em tempo real)
    def _calc_fit(row):
        fit = calcular_fit_score(row.to_dict())
        return fit["score"] if fit["score"] is not None else 0
    df["Fit"] = df.apply(_calc_fit, axis=1).astype(int)

    # --- Filtros inline (barra horizontal) ---
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
    with fc1:
        search = st.text_input("Buscar", placeholder="Nome da escola...", label_visibility="collapsed",
                               key="search_escola")
    with fc2:
        all_statuses_pt = sorted(df["Status"].unique().tolist())
        sel_status = st.multiselect("Status", all_statuses_pt, default=all_statuses_pt,
                                    label_visibility="collapsed", placeholder="Filtrar status...")
    with fc3:
        all_types = sorted([t for t in df["Tipo"].dropna().unique().tolist() if t])
        sel_type = st.multiselect("Tipo", all_types, default=[], label_visibility="collapsed",
                                  placeholder="Filtrar tipo...")
    with fc4:
        score_range = st.slider("Score", 0, 100, (0, 100), label_visibility="collapsed")

    # Segunda linha: filtros dos dados ricos do Censo
    fc5, fc6, fc7, fc8, fc9 = st.columns([2, 2, 2, 2, 2])
    with fc5:
        tech_options = ["Alto", "Medio", "Baixo"]
        sel_tech = st.multiselect("Tech", tech_options, default=[],
                                   label_visibility="collapsed", placeholder="Nivel tec...")
    with fc6:
        fonte_options = ["Censo 2025", "Catalogo INEP"]
        sel_fonte = st.multiselect("Fonte", fonte_options, default=[],
                                    label_visibility="collapsed", placeholder="Fonte dos dados...")
    with fc7:
        min_fund = st.number_input("Min Fund AF", min_value=0, max_value=5000, value=0, step=50,
                                    label_visibility="collapsed", placeholder="Min Fund AF")
    with fc8:
        min_medio = st.number_input("Min Medio", min_value=0, max_value=5000, value=0, step=50,
                                     label_visibility="collapsed", placeholder="Min Medio")
    with fc9:
        min_fit = st.number_input("Min Fit", min_value=0, max_value=100, value=0, step=5,
                                   label_visibility="collapsed", placeholder="Min Fit IAprendo",
                                   help="Fit IAprendo minimo (0-100)")
    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicar filtros
    df_f = df.copy()
    if sel_status:
        df_f = df_f[df_f["Status"].isin(sel_status)]
    if sel_type:
        df_f = df_f[df_f["Tipo"].isin(sel_type)]
    df_f = df_f[(df_f["Score"] >= score_range[0]) & (df_f["Score"] <= score_range[1])]
    if search:
        df_f = df_f[df_f["name"].str.contains(search, case=False, na=False)]
    if sel_tech:
        df_f = df_f[df_f["Tech"].isin(sel_tech)]
    if sel_fonte:
        df_f = df_f[df_f["Fonte"].isin(sel_fonte)]
    if min_fund > 0:
        df_f = df_f[df_f["Fund AF"] >= min_fund]
    if min_medio > 0:
        df_f = df_f[df_f["Medio"] >= min_medio]
    if min_fit > 0:
        df_f = df_f[df_f["Fit"] >= min_fit]

    # --- Metricas ---
    avg = df["Score"].replace(0, pd.NA).dropna().mean()
    total_alvo = int((df["Fund AF"] + df["Medio"]).sum())
    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Total", len(df), COLORS["primary"], icon="domain")
    with mc2:
        metric_card("Filtradas", len(df_f), COLORS["secondary"], icon="filter_alt")
    with mc3:
        metric_card("Alunos Alvo", f"{total_alvo:,}".replace(",", "."), COLORS["info"], icon="groups")
    with mc4:
        metric_card("Score Medio", f"{avg:.0f}" if pd.notna(avg) else "N/A", COLORS["success"], icon="analytics")

    st.markdown("")

    # --- Mensagem de feedback ---
    if st.session_state.escola_msg:
        msg_type, msg_text = st.session_state.escola_msg
        if msg_type == "success":
            alert_banner(msg_text, "success")
        elif msg_type == "error":
            alert_banner(msg_text, "error")
        st.session_state.escola_msg = None

    # --- Tabela interativa com selecao por clique ---
    table_cols = ["name", "city", "UF", "Bairro", "Tipo", "Fund AF", "Medio", "Tech", "Coord", "Fit", "Score", "Status"]
    col_config = {
        "name": st.column_config.TextColumn("Escola", width="large"),
        "city": st.column_config.TextColumn("Cidade", width="small"),
        "UF": st.column_config.TextColumn("UF", width="small", disabled=True),
        "Bairro": st.column_config.TextColumn("Bairro", width="small", disabled=True),
        "Tipo": st.column_config.TextColumn("Tipo", width="small", disabled=True),
        "Fund AF": st.column_config.NumberColumn(
            "Fund AF", width="small", disabled=True,
            help="Matriculas no Ensino Fundamental Anos Finais (6o-9o) — alvo IAprendo",
        ),
        "Medio": st.column_config.NumberColumn(
            "Medio", width="small", disabled=True,
            help="Matriculas no Ensino Medio (1o-3o) — alvo IAprendo",
        ),
        "Tech": st.column_config.TextColumn(
            "Tech", width="small", disabled=True,
            help="Nivel tecnologico da escola (Alto/Medio/Baixo)",
        ),
        "Coord": st.column_config.NumberColumn(
            "Coord", width="small", disabled=True,
            help="Quantidade de coordenadores pedagogicos",
        ),
        "Fit": st.column_config.ProgressColumn(
            "Fit", min_value=0, max_value=100, width="small",
            help="Fit IAprendo: 0-100, deterministico, baseado em alvo×tech×coord×categoria",
        ),
        "Score": st.column_config.NumberColumn("Score", min_value=0, max_value=100, width="small"),
        "Status": st.column_config.SelectboxColumn("Status", options=list(STATUS_PT.values()), width="small"),
    }

    st.caption("Clique em uma linha para ver acoes. Edite Status e Score diretamente na tabela.")

    df_f_reset = df_f.reset_index(drop=True)
    edited_df = st.data_editor(
        df_f_reset[table_cols],
        use_container_width=True,
        hide_index=True,
        column_config=col_config,
        num_rows="fixed",
        key="escola_table",
        on_change=None,
    )

    # Detect inline edits and save them
    if edited_df is not None:
        for idx_row in range(min(len(df_f_reset), len(edited_df))):
            orig_status = df_f_reset.iloc[idx_row]["Status"]
            orig_score = df_f_reset.iloc[idx_row]["Score"]
            new_status = edited_df.iloc[idx_row]["Status"]
            new_score = edited_df.iloc[idx_row]["Score"]
            if new_status != orig_status or new_score != orig_score:
                cid = df_f_reset.iloc[idx_row]["id"]
                updates = {}
                if new_status != orig_status:
                    updates["status"] = PT_TO_EN.get(new_status, "raw")
                if new_score != orig_score:
                    updates["qualification_score"] = int(new_score)
                if updates:
                    db.update_company(cid, updates)

    # --- Barra de acoes rapidas (logo abaixo da tabela) ---
    st.markdown(
        '<p style="font-size:12px;font-weight:600;color:#757575;text-transform:uppercase;'
        'letter-spacing:0.5px;margin-top:12px;margin-bottom:4px">Acoes rapidas</p>',
        unsafe_allow_html=True,
    )

    escola_options = df_f_reset[["id", "name"]].values.tolist()
    if escola_options:
        escola_names = [row[1] for row in escola_options]
        # Linha 1: Seletor + Ver detalhes
        ac_row1_1, ac_row1_2 = st.columns([4, 1])
        with ac_row1_1:
            selected_escola_idx = st.selectbox(
                "Escola:", range(len(escola_names)),
                format_func=lambda i: escola_names[i],
                label_visibility="collapsed",
                placeholder="Selecione uma escola...",
            )
        with ac_row1_2:
            if st.button("Ver detalhes", type="primary", icon=":material/open_in_new:",
                          use_container_width=True):
                go_to_detail(escola_options[selected_escola_idx][0])
                st.rerun()
        # Linha 2: Alterar status + Excluir
        ac_row2_1, ac_row2_2, ac_row2_3 = st.columns([2, 1, 1])
        with ac_row2_1:
            new_st = st.selectbox("Alterar status para:", list(STATUS_PT.values()), key="quick_st",
                                   label_visibility="collapsed")
        with ac_row2_2:
            if st.button("Alterar status", icon=":material/edit:", use_container_width=True):
                cid = escola_options[selected_escola_idx][0]
                new_en = PT_TO_EN.get(new_st, "raw")
                db.reset_company_status(cid, new_en)
                st.toast(f"Status alterado para {new_st}!")
                st.rerun()
        with ac_row2_3:
            if st.button("Excluir escola", icon=":material/delete:", use_container_width=True):
                st.session_state["confirm_single_delete"] = escola_options[selected_escola_idx]

    # Confirmacao de exclusao individual
    if st.session_state.get("confirm_single_delete"):
        del_id, del_name = st.session_state["confirm_single_delete"]
        alert_banner(f"Confirma exclusao de <strong>{del_name}</strong> e todos os dados?", "error")
        cd1, cd2 = st.columns(2)
        with cd1:
            if st.button("Sim, excluir", type="primary", key="confirm_del_single"):
                db.delete_company(del_id)
                st.session_state.escola_msg = ("success", f"{del_name} excluida.")
                st.session_state.pop("confirm_single_delete", None)
                st.rerun()
        with cd2:
            if st.button("Cancelar", key="cancel_del_single"):
                st.session_state.pop("confirm_single_delete", None)
                st.rerun()

    # --- Acoes em massa ---
    with st.expander("Acoes em massa (todas as filtradas)"):
        am_col1, am_col2, am_col3 = st.columns(3)
        with am_col1:
            new_status_pt = st.selectbox("Novo status:", list(STATUS_PT.values()), key="bulk_st")
        with am_col2:
            if st.button(f"Alterar {len(df_f)} escolas", icon=":material/edit:", use_container_width=True):
                new_en = PT_TO_EN.get(new_status_pt, "raw")
                for cid in df_f["id"].tolist():
                    db.reset_company_status(cid, new_en)
                st.session_state.escola_msg = ("success", f"Status de {len(df_f)} escolas alterado.")
                st.rerun()
        with am_col3:
            if st.button(f"Excluir {len(df_f)} escolas", icon=":material/delete_forever:",
                          use_container_width=True):
                st.session_state["confirm_bulk_delete"] = df_f["id"].tolist()

        if st.session_state.get("confirm_bulk_delete"):
            ids_to_del = st.session_state["confirm_bulk_delete"]
            alert_banner(f"Confirma exclusao de {len(ids_to_del)} escolas e todos os dados?", "error")
            cd1, cd2 = st.columns(2)
            with cd1:
                if st.button("Sim, excluir tudo", type="primary"):
                    deleted = db.bulk_delete_companies(ids_to_del)
                    st.session_state.escola_msg = ("success", f"{deleted} escolas excluidas.")
                    st.session_state.pop("confirm_bulk_delete", None)
                    st.rerun()
            with cd2:
                if st.button("Cancelar", key="cancel_del"):
                    st.session_state.pop("confirm_bulk_delete", None)
                    st.rerun()

    # --- Exportar ---
    st.divider()
    csv_cols = [c for c in [
        "name", "city", "UF", "Bairro", "inep_code", "Tipo", "Porte",
        "Fund AF", "Medio", "Tech", "Coord", "Fonte",
        "Status", "Score", "Fit",
    ] if c in df_f.columns]
    csv = df_f[csv_cols].to_csv(index=False)
    st.download_button("Exportar CSV", csv, "escolas.csv", "text/csv", icon=":material/download:")
