"""Pagina 1 - Pipeline: selecione escolas e execute etapas do pipeline de prospeccao."""
import streamlit as st
import sys
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header, alert_banner,
    pipeline_stepper, breadcrumb, status_badge, COLORS, STATUS_COLORS,
)

apply_theme_no_config()

# ======================================================================
# HEADER
# ======================================================================
breadcrumb(["Home", "Pipeline de Prospeccao"])
st.markdown(
    '<h1 style="margin-bottom:0">Pipeline de Prospeccao</h1>'
    '<p style="color:#757575;margin-top:4px;font-size:15px">'
    'Selecione escolas, execute etapas e acompanhe o funil de vendas.</p>',
    unsafe_allow_html=True,
)

try:
    from config.settings import settings
    from database.supabase_client import db
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.stop()

# ======================================================================
# Status mappings
# ======================================================================
STATUS_PT = {
    "raw": "Nova", "qualified": "Qualificada", "enriched": "Enriquecida",
    "contacted": "Contatada", "responded": "Respondeu", "converted": "Convertida",
}
STATUS_ICON = {
    "raw": "\u26aa", "qualified": "\U0001f535", "enriched": "\U0001f7e2",
    "contacted": "\U0001f7e0", "responded": "\U0001f7e3", "converted": "\u2705",
}

# ======================================================================
# PIPELINE STEPPER
# ======================================================================
try:
    all_companies = db.client.table("companies").select(
        "id,name,city,state,status,qualification_score,admin_dependency,admin_category,"
        "categoria_privada,school_size,fonte_dados,matriculas_fund_af,matriculas_medio,"
        "nivel_tecnologico,qt_coordenadores"
    ).order("qualification_score", desc=True).execute().data or []

    # Calcular alvo (Fund AF + Medio) e Fit Score IAprendo para cada escola
    from utils.fit_score import calcular_fit_score
    for _c in all_companies:
        _c["_alvo"] = int((_c.get("matriculas_fund_af") or 0) + (_c.get("matriculas_medio") or 0))
        _fit = calcular_fit_score(_c)
        _c["_fit"] = _fit["score"] or 0

    status_counts = {}
    for c in all_companies:
        s = c.get("status", "raw")
        status_counts[s] = status_counts.get(s, 0) + 1

    pending_count = 0
    approved_count = 0
    sent_count = 0
    try:
        q_data = db.client.table("approval_queue").select("status").execute().data or []
        for q in q_data:
            qs = q.get("status", "")
            if qs == "pending":
                pending_count += 1
            elif qs == "approved":
                approved_count += 1
            elif qs == "sent":
                sent_count += 1
    except Exception:
        pass

    # Stepper at top
    pipeline_stepper([
        {"label": "Novas", "count": status_counts.get("raw", 0), "color": STATUS_COLORS["raw"]},
        {"label": "Qualificadas", "count": status_counts.get("qualified", 0), "color": STATUS_COLORS["qualified"]},
        {"label": "Enriquecidas", "count": status_counts.get("enriched", 0), "color": STATUS_COLORS["enriched"]},
        {"label": "Contatadas", "count": status_counts.get("contacted", 0), "color": STATUS_COLORS["contacted"]},
        {"label": "Pendentes", "count": pending_count, "color": STATUS_COLORS["pending"]},
        {"label": "Aprovadas", "count": approved_count, "color": STATUS_COLORS["approved"]},
        {"label": "Enviadas", "count": sent_count, "color": STATUS_COLORS["sent"]},
    ])

except Exception as e:
    st.warning(f"Nao foi possivel carregar metricas: {e}")
    all_companies = []

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ======================================================================
# SCHOOL SELECTION
# ======================================================================
section_header("Selecionar Escolas", "checklist")

if "pipeline_selected_ids" not in st.session_state:
    st.session_state["pipeline_selected_ids"] = []

# --- Selecao rapida ---
st.caption("SELEÇÃO RÁPIDA")
preset_cols = st.columns(6)
with preset_cols[0]:
    if st.button("Top 10 por score", use_container_width=True, icon=":material/trending_up:"):
        scored = [c for c in all_companies if c.get("qualification_score")]
        scored.sort(key=lambda x: x.get("qualification_score", 0), reverse=True)
        st.session_state["pipeline_selected_ids"] = [c["id"] for c in scored[:10]]
        st.toast("Top 10 por score selecionadas!")
        st.rerun()
with preset_cols[1]:
    if st.button("Top 10 por Fit", use_container_width=True, icon=":material/diamond:",
                 help="Escolas com maior Fit IAprendo (alvo x tech x coord x categoria)"):
        by_fit = sorted(all_companies, key=lambda x: x.get("_fit", 0), reverse=True)
        by_fit = [c for c in by_fit if c.get("_fit", 0) > 0]
        st.session_state["pipeline_selected_ids"] = [c["id"] for c in by_fit[:10]]
        st.toast(f"Top 10 por Fit IAprendo selecionadas!")
        st.rerun()
with preset_cols[2]:
    if st.button("Todas nao processadas", use_container_width=True, icon=":material/fiber_new:"):
        raw = [c for c in all_companies if c.get("status") == "raw"]
        st.session_state["pipeline_selected_ids"] = [c["id"] for c in raw]
        st.toast(f"{len(raw)} escolas selecionadas!")
        st.rerun()
with preset_cols[3]:
    if st.button("Todas privadas", use_container_width=True, icon=":material/lock:"):
        private = [c for c in all_companies if "privad" in (c.get("admin_dependency", "") or "").lower()]
        st.session_state["pipeline_selected_ids"] = [c["id"] for c in private]
        st.toast(f"{len(private)} escolas privadas selecionadas!")
        st.rerun()
with preset_cols[4]:
    if st.button("Prontas p/ email", use_container_width=True, icon=":material/mark_email_read:"):
        ready = [c for c in all_companies if c.get("status") in ("qualified", "enriched", "contacted")]
        st.session_state["pipeline_selected_ids"] = [c["id"] for c in ready]
        st.toast(f"{len(ready)} escolas prontas selecionadas!")
        st.rerun()
with preset_cols[5]:
    if st.button("Limpar selecao", use_container_width=True, icon=":material/delete_sweep:"):
        st.session_state["pipeline_selected_ids"] = []
        st.toast("Selecao limpa!")
        st.rerun()

# --- Selection tabs ---
tab_filter, tab_manual, tab_paste = st.tabs([
    "Filtros", "Selecao Manual", "Colar Lista",
])

with tab_filter:
    # Filtros horizontais — linha 1
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        filter_status = st.multiselect("Status:", list(STATUS_PT.keys()),
                                        format_func=lambda x: f"{STATUS_ICON.get(x, '')} {STATUS_PT.get(x, x)}",
                                        default=[])
    with fc2:
        types_available = sorted(set(c.get("admin_dependency", "") or "" for c in all_companies if c.get("admin_dependency")))
        filter_type = st.multiselect("Tipo:", types_available)
    with fc3:
        filter_score = st.slider("Score minimo:", 0, 100, 0)
    with fc4:
        filter_name = st.text_input("Buscar por nome:", placeholder="Nome da escola...")

    # Linha 2 — filtros do Censo 2025
    fc5, fc6, fc7, fc8 = st.columns(4)
    with fc5:
        filter_tech = st.multiselect(
            "Nivel tecnologico:",
            ["Alto", "Medio", "Baixo"],
            default=[],
            help="Filtra por nivel tecnologico do Censo 2025",
        )
    with fc6:
        filter_min_alvo = st.number_input(
            "Min alunos alvo:",
            min_value=0, max_value=5000, value=0, step=50,
            help="Minimo de matriculas Fund AF + Medio",
        )
    with fc7:
        filter_fonte = st.multiselect(
            "Fonte dos dados:",
            ["censo_2025", "catalogo_inep"],
            default=[],
            format_func=lambda x: {"censo_2025": "Censo 2025", "catalogo_inep": "Catalogo INEP"}.get(x, x),
        )
    with fc8:
        filter_com_coord = st.checkbox(
            "Com coordenador pedagogico",
            value=False,
            help="Escolas que tem pelo menos 1 coordenador pedagogico (decisor tecnico)",
        )

    # Linha 3 — filtro de Fit Score IAprendo
    fc9, _, _, _ = st.columns(4)
    with fc9:
        filter_min_fit = st.number_input(
            "Min Fit IAprendo:",
            min_value=0, max_value=100, value=0, step=5,
            help="Fit Score minimo (0-100, deterministico, baseado no Censo 2025)",
        )

    if st.button("Aplicar filtros e selecionar", type="primary", icon=":material/filter_alt:"):
        filtered = all_companies
        if filter_status:
            filtered = [c for c in filtered if c.get("status") in filter_status]
        if filter_type:
            filtered = [c for c in filtered if c.get("admin_dependency") in filter_type]
        if filter_score > 0:
            filtered = [c for c in filtered if (c.get("qualification_score") or 0) >= filter_score]
        if filter_name:
            filtered = [c for c in filtered if filter_name.lower() in (c.get("name", "") or "").lower()]
        if filter_tech:
            filtered = [c for c in filtered if c.get("nivel_tecnologico") in filter_tech]
        if filter_min_alvo > 0:
            filtered = [c for c in filtered if c.get("_alvo", 0) >= filter_min_alvo]
        if filter_fonte:
            filtered = [c for c in filtered if c.get("fonte_dados") in filter_fonte]
        if filter_com_coord:
            filtered = [c for c in filtered if (c.get("qt_coordenadores") or 0) > 0]
        if filter_min_fit > 0:
            filtered = [c for c in filtered if (c.get("_fit") or 0) >= filter_min_fit]
        new_ids = [c["id"] for c in filtered]
        current = set(st.session_state["pipeline_selected_ids"])
        current.update(new_ids)
        st.session_state["pipeline_selected_ids"] = list(current)
        st.toast(f"{len(new_ids)} escolas adicionadas! Total: {len(current)}")
        st.rerun()

with tab_manual:
    if all_companies:
        df_manual = pd.DataFrame([{
            "Selecionar": c["id"] in set(st.session_state.get("pipeline_selected_ids", [])),
            "Escola": c.get("name", "?"),
            "Cidade": c.get("city", ""),
            "Status": STATUS_PT.get(c.get("status", ""), c.get("status", "")),
            "Score": c.get("qualification_score") or 0,
            "Fit": c.get("_fit", 0),
            "Tipo": c.get("admin_dependency", ""),
            "Alvo": c.get("_alvo", 0),
            "Tech": c.get("nivel_tecnologico") or "-",
            "id": c["id"],
        } for c in all_companies])

        edited_df = st.data_editor(
            df_manual[["Selecionar", "Escola", "Cidade", "Status", "Score", "Fit", "Alvo", "Tech", "Tipo"]],
            use_container_width=True,
            hide_index=True,
            height=350,
            column_config={
                "Selecionar": st.column_config.CheckboxColumn("Sel.", default=False, width="small"),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                "Fit": st.column_config.ProgressColumn(
                    "Fit", min_value=0, max_value=100, format="%d",
                    help="Fit IAprendo: deterministico, baseado em alvo x tech x coord x categoria",
                ),
                "Alvo": st.column_config.NumberColumn(
                    "Alvo", width="small",
                    help="Matriculas Fund AF + Medio (segmento IAprendo)",
                ),
                "Tech": st.column_config.TextColumn(
                    "Tech", width="small",
                    help="Nivel tecnologico (Alto/Medio/Baixo)",
                ),
            },
            disabled=["Escola", "Cidade", "Status", "Score", "Fit", "Alvo", "Tech", "Tipo"],
            key="pipeline_manual_editor",
        )
        selected_rows = edited_df[edited_df["Selecionar"] == True]
        if len(selected_rows) > 0:
            btn_cols = st.columns([2, 1])
            with btn_cols[0]:
                if st.button(f"Adicionar {len(selected_rows)} selecionadas", type="primary",
                             icon=":material/add_circle:", use_container_width=True):
                    new_ids = [df_manual.iloc[i]["id"] for i in selected_rows.index]
                    current = set(st.session_state["pipeline_selected_ids"])
                    current.update(new_ids)
                    st.session_state["pipeline_selected_ids"] = list(current)
                    st.toast(f"{len(new_ids)} escolas adicionadas!")
                    st.rerun()
            with btn_cols[1]:
                if len(selected_rows) == 1:
                    sel_id = df_manual.iloc[selected_rows.index[0]]["id"]
                    if st.button("Ver detalhes →", use_container_width=True, key="pipeline_detail"):
                        st.session_state["escola_detail_id"] = sel_id
                        st.switch_page("pages/5_🏫_Escolas.py")
    else:
        alert_banner("Nenhuma escola importada.", "info")

with tab_paste:
    paste_text = st.text_area("Cole nomes ou codigos INEP (um por linha):",
                               height=150, placeholder="Colegio ABC\nEscola XYZ\n12345678")
    if st.button("Buscar e selecionar", icon=":material/search:"):
        if paste_text.strip():
            lines = [l.strip() for l in paste_text.strip().split("\n") if l.strip()]
            found_ids = []
            not_found = []
            for line in lines:
                match = None
                for c in all_companies:
                    if line.lower() in (c.get("name", "") or "").lower():
                        match = c
                        break
                    if line == str(c.get("inep_code", "")):
                        match = c
                        break
                if match:
                    found_ids.append(match["id"])
                else:
                    not_found.append(line)
            if found_ids:
                current = set(st.session_state["pipeline_selected_ids"])
                current.update(found_ids)
                st.session_state["pipeline_selected_ids"] = list(current)
                st.toast(f"{len(found_ids)} escolas encontradas e adicionadas!")
            if not_found:
                st.warning(f"{len(not_found)} nao encontradas: {', '.join(not_found[:5])}")
            if found_ids:
                st.rerun()

# --- Selection preview ---
selected_ids = st.session_state.get("pipeline_selected_ids", [])
if selected_ids:
    selected_companies = [c for c in all_companies if c["id"] in set(selected_ids)]
    sel_by_status = {}
    for c in selected_companies:
        s = c.get("status", "raw")
        sel_by_status[s] = sel_by_status.get(s, 0) + 1

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    section_header(f"{len(selected_companies)} escolas selecionadas", "checklist")
    # Status summary as badges
    badges_html = " ".join([
        status_badge(s, f"{STATUS_PT.get(s, s)}: {n}")
        for s, n in sorted(sel_by_status.items())
    ])
    st.markdown(badges_html, unsafe_allow_html=True)

    with st.expander("Ver escolas selecionadas", expanded=False):
        df_sel = pd.DataFrame([{
            "Escola": c.get("name", "?"),
            "Cidade": c.get("city", ""),
            "Status": f"{STATUS_ICON.get(c.get('status',''), '')} {STATUS_PT.get(c.get('status',''), '')}",
            "Score": c.get("qualification_score") or 0,
            "Tipo": c.get("admin_dependency", ""),
        } for c in selected_companies])
        st.data_editor(
            df_sel, use_container_width=True, hide_index=True, height=200,
            disabled=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            },
            key="sel_preview_editor",
        )

    # ======================================================================
    # PIPELINE EXECUTION
    # ======================================================================
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Executar Pipeline", "play_circle")

    raw_count = sel_by_status.get("raw", 0)
    qualified_count = sel_by_status.get("qualified", 0)
    enriched_count = sel_by_status.get("enriched", 0)
    contactable_count = qualified_count + enriched_count + sel_by_status.get("contacted", 0)

    # Controles do pipeline
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        write_mode_label = st.selectbox("Modo de mensagem:", ["IA (personalizada)", "Template (padrao)"],
                                         key="pipe_write_mode")
        write_mode = "ai" if "IA" in write_mode_label else "template"
    with ctrl2:
        score_min = st.slider("Score minimo para email:", 0, 100, 60, key="pipe_score_min")
    with ctrl3:
        dry_run = st.checkbox("Modo simulado (dry run)", value=False, key="pipe_dry_run")
        if dry_run:
            alert_banner("Nenhuma acao real sera executada", "warning")

    # Pipeline steps as cards
    pc1, pc2, pc3, pc4, pc5 = st.columns(5)

    with pc1:
        metric_card("Qualificar", raw_count, icon="grading", color=STATUS_COLORS["raw"])
        if st.button("Qualificar", disabled=(raw_count == 0), key="btn_qualify",
                      use_container_width=True, type="primary"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner(f"Qualificando {raw_count} escolas..."):
                report = run_pipeline(
                    qualify_limit=raw_count, enrich_limit=0, write_limit=0,
                    send_approved=False, dry_run=dry_run,
                    company_ids=selected_ids, steps=["qualify"],
                )
            result = report.get("steps", {}).get("qualify", {})
            st.toast(f"{result.get('output', 0)} escolas qualificadas!")
            st.rerun()

    with pc2:
        metric_card("Enriquecer", qualified_count, icon="auto_fix_high", color=STATUS_COLORS["qualified"])
        if st.button("Enriquecer", disabled=(qualified_count == 0), key="btn_enrich",
                      use_container_width=True, type="primary"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner(f"Enriquecendo {qualified_count} escolas..."):
                report = run_pipeline(
                    qualify_limit=0, enrich_limit=qualified_count, write_limit=0,
                    send_approved=False, dry_run=dry_run,
                    company_ids=selected_ids, steps=["enrich"],
                )
            result = report.get("steps", {}).get("enrich", {})
            st.toast(f"{result.get('output', 0)} escolas enriquecidas!")
            st.rerun()

    with pc3:
        metric_card("Contatos", enriched_count, icon="person_search", color=STATUS_COLORS["enriched"])
        if st.button("Buscar", disabled=(enriched_count == 0), key="btn_contacts",
                      use_container_width=True, type="primary"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner(f"Buscando contatos de {enriched_count} escolas..."):
                report = run_pipeline(
                    qualify_limit=0, enrich_limit=enriched_count, write_limit=0,
                    send_approved=False, dry_run=dry_run,
                    company_ids=selected_ids, steps=["contacts"],
                )
            result = report.get("steps", {}).get("contacts", {})
            st.toast(f"{result.get('output', 0)} contatos encontrados!")
            st.rerun()

    with pc4:
        metric_card("Emails", contactable_count, icon="edit_note", color=STATUS_COLORS["contacted"])
        if st.button("Gerar", disabled=(contactable_count == 0), key="btn_write",
                      use_container_width=True, type="primary"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner(f"Gerando emails para {contactable_count} escolas..."):
                report = run_pipeline(
                    qualify_limit=0, enrich_limit=0, write_limit=contactable_count,
                    send_approved=False, dry_run=dry_run, write_mode=write_mode,
                    company_ids=selected_ids, steps=["write"],
                )
            result = report.get("steps", {}).get("write", {})
            st.toast(f"{result.get('output', 0)} emails gerados!")
            st.rerun()

    with pc5:
        metric_card("Enviar", approved_count, icon="send", color=STATUS_COLORS["approved"])
        if st.button("Enviar", disabled=(approved_count == 0), key="btn_send",
                      use_container_width=True, type="primary"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner("Enviando emails aprovados..."):
                report = run_pipeline(
                    qualify_limit=0, enrich_limit=0, write_limit=0,
                    send_approved=True, dry_run=dry_run,
                    steps=["send"],
                )
            result = report.get("steps", {}).get("send", {})
            st.toast(f"{result.get('sent', 0)} emails enviados!")
            st.rerun()

    # Full pipeline button
    st.markdown("")
    full1, full2 = st.columns([1, 3])
    with full1:
        if st.button("Pipeline Completo", type="primary", use_container_width=True,
                      icon=":material/rocket_launch:"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner("Executando pipeline completo..."):
                report = run_pipeline(
                    qualify_limit=raw_count or 50,
                    enrich_limit=qualified_count or 50,
                    write_limit=contactable_count or 50,
                    send_approved=False,
                    dry_run=dry_run,
                    write_mode=write_mode,
                    company_ids=selected_ids,
                )
            st.toast("Pipeline concluido!")
            with st.expander("Ver relatorio completo"):
                st.json(report)
            st.rerun()
    with full2:
        st.caption(
            "Executa todas as etapas em sequencia: Qualificar \u2192 Enriquecer \u2192 "
            "Buscar Contatos \u2192 Gerar Emails. Emails nao sao enviados automaticamente "
            "\u2014 va para a Fila de Aprovacao para revisar e aprovar."
        )

else:
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    alert_banner(
        "Selecione escolas acima para ativar o pipeline. Use os botoes de selecao rapida ou os filtros.",
        "info",
    )

# ======================================================================
# ZONA 2: PIPELINE COMERCIAL (kanban de stages reais)
# ======================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Pipeline Comercial", "view_kanban")

COMMERCIAL_STAGES = [
    {"key": "prospectado", "label": "Prospectado", "color": COLORS["primary"], "desc": "Novo lead"},
    {"key": "contatado", "label": "Contatado", "color": COLORS["info"], "desc": "Email/WhatsApp enviado"},
    {"key": "respondeu", "label": "Respondeu", "color": COLORS["secondary"], "desc": "Lead engajado"},
    {"key": "reuniao", "label": "Reuniao", "color": COLORS["warning"], "desc": "Meeting realizada"},
    {"key": "proposta", "label": "Proposta", "color": COLORS["accent"], "desc": "Orcamento enviado"},
    {"key": "cliente", "label": "Cliente", "color": COLORS["success"], "desc": "Deal fechado"},
]

try:
    from dashboard.theme import kanban_card

    # Carrega companies com stage + valores comerciais.
    # Se migration 013 nao foi aplicada ainda, cai pro SELECT basico (sem os
    # campos novos) e trata tudo como None — pipeline comercial ainda renderiza
    # via inferencia automatica.
    _migration_013_ok = True
    try:
        comm_companies = db.client.table("companies").select(
            "id,name,city,qualification_score,commercial_stage,valor_mensal_proposto,"
            "valor_mensal_fechado,motivo_perda_texto,motivo_perda_categoria,data_fechamento,"
            "matriculas_fund_af,matriculas_medio,nivel_tecnologico,status"
        ).execute().data or []
    except Exception as _migration_err:
        if "commercial_stage" in str(_migration_err) or "42703" in str(_migration_err):
            _migration_013_ok = False
            comm_companies = db.client.table("companies").select(
                "id,name,city,qualification_score,matriculas_fund_af,matriculas_medio,"
                "nivel_tecnologico,status"
            ).execute().data or []
            alert_banner(
                "Migration 013 ainda nao aplicada — pipeline comercial em modo read-only "
                "(inferencia automatica). Rode <code>database/migrations/APLICAR-013-COMMERCIAL-STAGES.sql</code> "
                "no Supabase SQL Editor pra habilitar campos Proposta/Cliente/Perdido.",
                "warning",
            )
        else:
            raise

    # Carrega meetings e emails pra inferencia
    _meetings = db.client.table("meetings").select("company_id").execute().data or []
    _meeting_set = {m["company_id"] for m in _meetings if m.get("company_id")}

    _sent_emails = db.client.table("approval_queue").select(
        "company_id,replied_at"
    ).eq("status", "sent").execute().data or []
    _email_map = {}
    for _e in _sent_emails:
        cid = _e.get("company_id")
        if not cid:
            continue
        entry = _email_map.setdefault(cid, {"sent": False, "replied": False})
        entry["sent"] = True
        if _e.get("replied_at"):
            entry["replied"] = True

    def _infer_stage(comp):
        """Prioridade: commercial_stage manual > inferencia automatica."""
        manual = comp.get("commercial_stage")
        if manual:
            return manual
        cid = comp["id"]
        if cid in _meeting_set:
            return "reuniao"
        if _email_map.get(cid, {}).get("replied"):
            return "respondeu"
        if cid in _email_map:
            return "contatado"
        if comp.get("status") in ("raw", "qualified", "enriched", "filtered"):
            return "prospectado"
        return None  # fora do pipeline comercial

    # Classifica escolas por stage
    stage_buckets = {s["key"]: [] for s in COMMERCIAL_STAGES}
    perdidos = []
    for _c in comm_companies:
        stage = _infer_stage(_c)
        if stage == "perdido":
            perdidos.append(_c)
        elif stage in stage_buckets:
            stage_buckets[stage].append(_c)

    # KPI row: counts + MRR
    mrr_potencial = sum(
        float(c.get("valor_mensal_proposto") or 0) for c in stage_buckets["proposta"]
    )
    mrr_ativo = sum(
        float(c.get("valor_mensal_fechado") or 0) for c in stage_buckets["cliente"]
    )
    total_fechados = len(stage_buckets["cliente"])
    total_perdidos = len(perdidos)
    win_rate = (
        (total_fechados / (total_fechados + total_perdidos) * 100)
        if (total_fechados + total_perdidos) > 0
        else 0
    )

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        metric_card("MRR Potencial", f"R$ {mrr_potencial:,.0f}".replace(",", "."),
                    icon="pending", color=COLORS["accent"],
                    delta=f"{len(stage_buckets['proposta'])} proposta(s)")
    with mc2:
        metric_card("MRR Ativo", f"R$ {mrr_ativo:,.0f}".replace(",", "."),
                    icon="payments", color=COLORS["success"],
                    delta=f"{total_fechados} cliente(s)")
    with mc3:
        metric_card("Win Rate", f"{win_rate:.0f}%",
                    icon="emoji_events", color=COLORS["primary"],
                    delta=f"{total_fechados}/{total_fechados + total_perdidos} decisoes")

    # KPI row: contagem por stage
    st.markdown("")
    kanban_header_cols = st.columns(len(COMMERCIAL_STAGES))
    for i, stage in enumerate(COMMERCIAL_STAGES):
        with kanban_header_cols[i]:
            count = len(stage_buckets[stage["key"]])
            st.markdown(
                f'<p style="background:{stage["color"]}12;border-left:4px solid {stage["color"]};'
                f'padding:10px 12px;border-radius:8px;margin-bottom:8px">'
                f'<strong style="font-size:13px">{stage["label"]}</strong>'
                f' <span style="font-size:11px;color:{stage["color"]};font-weight:700">({count})</span><br/>'
                f'<span style="font-size:10px;color:#9E9E9E">{stage["desc"]}</span></p>',
                unsafe_allow_html=True,
            )
            items = stage_buckets[stage["key"]]
            if not items:
                st.caption("—")
                continue
            # Mostra ate 6 cards ordenados por score desc
            for comp in sorted(items, key=lambda x: x.get("qualification_score") or 0, reverse=True)[:6]:
                score = int(comp.get("qualification_score") or 0)
                name = (comp.get("name") or "?")[:28]
                alvo_ = int((comp.get("matriculas_fund_af") or 0) + (comp.get("matriculas_medio") or 0))
                tech = comp.get("nivel_tecnologico") or ""

                # Subtitle especifico por stage (valores comerciais)
                sub = ""
                if stage["key"] == "proposta" and comp.get("valor_mensal_proposto"):
                    sub = f"R$ {float(comp['valor_mensal_proposto']):,.0f}/mes".replace(",", ".")
                elif stage["key"] == "cliente" and comp.get("valor_mensal_fechado"):
                    sub = f"R$ {float(comp['valor_mensal_fechado']):,.0f}/mes".replace(",", ".")

                st.markdown(
                    kanban_card(
                        name=name,
                        subtitle=sub,
                        score=score,
                        color=stage["color"],
                        alvo=alvo_,
                        nivel_tech=tech,
                    ),
                    unsafe_allow_html=True,
                )
            if len(items) > 6:
                st.caption(f"+ {len(items) - 6} mais")

    # Secao de perdidos colapsada
    if perdidos:
        with st.expander(f"Leads perdidos ({len(perdidos)})", expanded=False):
            for p in sorted(perdidos, key=lambda x: (x.get("data_fechamento") or ""), reverse=True)[:15]:
                data_str = (p.get("data_fechamento") or "")[:10]
                categoria = p.get("motivo_perda_categoria") or "—"
                motivo_txt = (p.get("motivo_perda_texto") or "")[:120]
                st.markdown(
                    f"**{p.get('name', '?')}** — {data_str} · "
                    f"<span style='background:#FFCDD2;color:#B71C1C;padding:2px 8px;"
                    f"border-radius:10px;font-size:11px;font-weight:600'>{categoria}</span>"
                    f"<br/><span style='color:#757575;font-size:12px'>{motivo_txt}</span>",
                    unsafe_allow_html=True,
                )

    # Dica de uso
    st.caption(
        "💡 Os stages Proposta/Cliente/Perdido sao preenchidos pelo IAlex via WhatsApp: "
        "\"mandei proposta pro Marista, R$ 15k/mes\" · "
        "\"fechei o Anchieta, R$ 18k/mes\" · "
        "\"perdi o Adventista, foi pra concorrencia\""
    )
except Exception as _e:
    st.warning(f"Erro ao carregar pipeline comercial: {_e}")

# ======================================================================
# SYSTEM SECTION
# ======================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Sistema", "settings")

with st.expander("API Status"):
    api_col1, api_col2 = st.columns(2)
    with api_col1:
        st.markdown("**IA**")
        ant_key = settings.ANTHROPIC_API_KEY
        if ant_key and len(ant_key) > 10:
            st.success("Anthropic Claude configurado")
        else:
            st.error("Anthropic Claude \u2014 Chave ausente")
        st.markdown("**Banco de Dados**")
        supa_url = settings.SUPABASE_URL
        supa_key = settings.SUPABASE_KEY
        if supa_url and supa_key:
            st.success(f"Supabase ({len(all_companies)} escolas)")
        else:
            st.error("Supabase \u2014 Nao configurado")
    with api_col2:
        st.markdown("**Enriquecimento**")
        for api, key_attr in [("Apollo", "APOLLO_API_KEY"), ("Hunter", "HUNTER_API_KEY"),
                               ("Snov", "SNOV_USER_ID"), ("HubSpot", "HUBSPOT_API_KEY")]:
            key = getattr(settings, key_attr, "")
            if key and len(str(key)) > 5:
                st.success(f"{api}")
            else:
                st.caption(f"{api} \u2014 Nao configurado")
        st.markdown("**Email**")
        brevo_key = getattr(settings, "BREVO_API_KEY", "")
        if brevo_key and len(brevo_key) > 5:
            st.success("Brevo")
        else:
            st.caption("Brevo \u2014 Nao configurado")

with st.expander("Uso de APIs (ultimas 24h)"):
    try:
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(hours=24)
        api_limits = {"apollo": 60, "hunter": 25, "snov": 50}
        u_cols = st.columns(len(api_limits) + 1)
        for col, (api_name, limit) in zip(u_cols, api_limits.items()):
            used = db.count_api_usage_since(api_name, cutoff)
            remaining = max(0, limit - used)
            with col:
                metric_card(api_name.capitalize(), f"{used}/{limit}",
                            color=COLORS["warning"] if used > limit * 0.8 else COLORS["secondary"],
                            delta=f"{remaining} restantes")
                st.progress(min(used / limit, 1.0) if limit > 0 else 0)
        with u_cols[-1]:
            anthropic_used = db.count_api_usage_since("anthropic", cutoff)
            metric_card("Anthropic", f"{anthropic_used}", icon="smart_toy",
                        color=COLORS["primary"], delta="pay-per-use")
    except Exception as e:
        st.warning(f"Erro: {e}")

with st.expander("Informacoes do Sistema"):
    info_col1, info_col2 = st.columns(2)
    with info_col1:
        st.markdown("**Remetente**")
        st.markdown(f"Nome: **{getattr(settings, 'YOUR_NAME', 'N/A')}**")
        st.markdown(f"Email: **{getattr(settings, 'YOUR_EMAIL', 'N/A')}**")
        st.markdown(f"Empresa: **{getattr(settings, 'COMPANY_NAME', 'N/A')}**")
    with info_col2:
        st.markdown("**Modelos de IA**")
        st.markdown(f"Qualificacao: `{getattr(settings, 'QUALIFIER_MODEL', 'claude-haiku-4-5')}`")
        st.markdown(f"Escrita: `{getattr(settings, 'WRITER_MODEL', 'claude-sonnet-4-5')}`")
        st.markdown(f"Alvo: **{getattr(settings, 'TARGET_CITY', 'Porto Alegre')}/{getattr(settings, 'TARGET_STATE', 'RS')}**")

with st.expander("Teste de Email (Brevo)"):
    try:
        from tools.brevo_sender import brevo_sender
        if brevo_sender._enabled:
            st.markdown(f"**Remetente:** `{brevo_sender.from_email}` ({brevo_sender.from_name})")
            test_email = st.text_input("Email de destino:", placeholder="seu@email.com", key="brevo_test")
            if st.button("Enviar Teste", disabled=not test_email, icon=":material/send:"):
                result = brevo_sender.send_email(
                    to_email=test_email, to_name="Teste",
                    subject="[IAprendo] Teste de Envio",
                    body="Este e um email de teste do IAprendo Sales Agent.",
                )
                if result.get("success"):
                    st.toast(f"Enviado! ID: {result.get('message_id', '')}")
                else:
                    st.error(f"Falha: {result.get('error', '?')}")
        else:
            alert_banner("Brevo nao configurado.", "warning")
    except Exception as e:
        st.error(f"Erro: {e}")
