"""Pagina 3 - Pipeline: execucao tecnica + descoberta + pipeline comercial.

3 abas:
- Execucao: selecao de escolas + 5 botoes do pipeline (qualificar -> enviar)
- Descoberta: enriquecimento web em lote + busca de sinais
- Pipeline Comercial: kanban de stages reais (prospectado -> cliente)
"""
import streamlit as st
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header, alert_banner,
    pipeline_stepper, breadcrumb, status_badge, COLORS, STATUS_COLORS,
)

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

# ======================================================================
# HEADER
# ======================================================================
breadcrumb(["Home", "Pipeline de Prospeccao"])
st.markdown(
    '<h1 style="margin-bottom:0">Pipeline de Prospeccao</h1>'
    '<p style="color:#757575;margin-top:4px;font-size:15px">'
    'Selecione escolas, execute etapas, descubra sinais e acompanhe o funil comercial.</p>',
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

# Cache de all_companies: evita SELECT+fit_score pesado a cada rerun
# (ex: ao marcar checkbox Forcar/Dry-run, mudar filtros, etc).
# TTL curto (30s) pra refletir mudancas razoavelmente rapido.
# Botao "Atualizar dados" abaixo invalida manualmente apos rodar pipeline.
@st.cache_data(ttl=30, show_spinner=False)
def _load_all_companies_cached() -> list:
    rows = db.client.table("companies").select(
        "id,name,city,state,status,qualification_score,admin_dependency,admin_category,"
        "categoria_privada,school_size,fonte_dados,matriculas_fund_af,matriculas_medio,"
        "nivel_tecnologico,qt_coordenadores,phone,website,latitude,longitude,urgency_score,urgency_tier"
    ).order("qualification_score", desc=True).execute().data or []
    from utils.fit_score import calcular_fit_score
    for _c in rows:
        _c["_alvo"] = int((_c.get("matriculas_fund_af") or 0) + (_c.get("matriculas_medio") or 0))
        _fit = calcular_fit_score(_c)
        _c["_fit"] = _fit["score"] or 0
    return rows


@st.cache_data(ttl=30, show_spinner=False)
def _load_queue_counts_cached() -> dict:
    counts = {"pending": 0, "approved": 0, "sent": 0}
    try:
        q_data = db.client.table("approval_queue").select("status").execute().data or []
        for q in q_data:
            qs = q.get("status", "")
            if qs in counts:
                counts[qs] += 1
    except Exception:
        pass
    return counts


try:
    all_companies = _load_all_companies_cached()

    status_counts = {}
    for c in all_companies:
        s = c.get("status", "raw")
        status_counts[s] = status_counts.get(s, 0) + 1

    _qc = _load_queue_counts_cached()
    pending_count = _qc["pending"]
    approved_count = _qc["approved"]
    sent_count = _qc["sent"]

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

# Botao "Atualizar dados" — DISCRETO, separado do stepper.
# Posicao: ESQUERDA (longe do card "Enviadas") + margem vertical de respiro.
# Cache TTL=30s; usuario pode forcar refresh apos rodar pipeline.
st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
_ref_cols = st.columns([1.5, 9])
with _ref_cols[0]:
    if st.button("🔄 Atualizar dados", key="pipe_refresh_cache",
                  use_container_width=True,
                  help=("Limpa cache local (TTL 30s) e recarrega dados do banco. "
                        "Use apos rodar pipeline pra ver contadores atualizados."),
                  type="secondary"):
        try:
            _load_all_companies_cached.clear()
        except Exception:
            pass
        try:
            _load_queue_counts_cached.clear()
        except Exception:
            pass
        st.rerun()

st.markdown('<hr class="divider">', unsafe_allow_html=True)


# ==========================================================================
# Helper: carregar contact stats (reusado pelo filtro "sem contato")
# ==========================================================================
@st.cache_data(ttl=60, show_spinner=False)
def _load_contact_stats() -> dict:
    """Carrega contact stats (cache 60s). Retorna dict vazio em caso de erro."""
    try:
        from utils.contact_stats import compute_contact_coverage
        _cts = db.client.table("contacts").select(
            "company_id,email,phone,phone_whatsapp,decision_maker_type,source"
        ).execute().data or []
        return compute_contact_coverage(all_companies, _cts)
    except Exception:
        return {}


# ==========================================================================
# Render helpers — uma funcao por aba
# ==========================================================================
def render_execucao():
    """Aba Execucao: selecao + filtros sem-contato + 5 botoes do pipeline."""
    section_header("Selecionar Escolas", "checklist")

    if "pipeline_selected_ids" not in st.session_state:
        st.session_state["pipeline_selected_ids"] = []

    def _reset_ckbox_keys():
        """Reset estado dos checkboxes + cache do data_editor.

        Chamar SEMPRE que pipeline_selected_ids for substituido externamente
        (presets, colar lista, limpar) pra forcar a tabela a regenerar com
        o novo valor de current_sel_set.
        """
        # Limpa checkboxes individuais (legado da tabela linha-a-linha)
        for _k in list(st.session_state.keys()):
            if _k.startswith("ck_pipe_"):
                del st.session_state[_k]
        # Invalida cache do data_editor (forca regenerar df_tbl + reset widget)
        for _k in ["_tbl_df_cached", "_tbl_filter_sig", "tbl_editor_v3"]:
            if _k in st.session_state:
                del st.session_state[_k]

    # --- Filtros rapidos de preparo (novo) ---
    contact_stats = _load_contact_stats()
    sem_contato_set = set(contact_stats.get("escolas_sem_contato_ids", []))
    sem_email_set = set(contact_stats.get("escolas_sem_email_ids", []))
    sem_whatsapp_set = set(contact_stats.get("escolas_sem_whatsapp_ids", []))

    with st.expander("Filtros rapidos de preparo", expanded=False,
                     icon=":material/filter_alt:"):
        st.caption(
            "Use estes filtros ANTES de enriquecer ou gerar emails pra evitar "
            "desperdicio de API e retrabalho. Combinam em AND."
        )
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filt_sem_contato = st.checkbox(
                f"Sem nenhum contato ({len(sem_contato_set)})",
                key="filt_sem_contato",
                help="Escolas sem email, whatsapp, telefone ou linkedin em nenhum contato",
            )
            filt_sem_email = st.checkbox(
                f"Sem email real ({len(sem_email_set)})",
                key="filt_sem_email",
                help="Escolas sem email valido (exclui placeholders)",
            )
        with fc2:
            filt_sem_whatsapp = st.checkbox(
                f"Sem WhatsApp ({len(sem_whatsapp_set)})",
                key="filt_sem_whatsapp",
            )
            filt_sem_website = st.checkbox(
                "Sem website",
                key="filt_sem_website",
                help="companies.website IS NULL",
            )
        with fc3:
            filt_sem_phone = st.checkbox(
                "Sem telefone no cadastro",
                key="filt_sem_phone",
                help="companies.phone IS NULL",
            )
            filt_sem_geo = st.checkbox(
                "Sem coordenadas",
                key="filt_sem_geo",
                help="Latitude/longitude ausentes (nao aparece no Mapa)",
            )

    # Aplica filtros de preparo na lista base
    def _passes_filters(comp: dict) -> bool:
        cid = comp.get("id")
        if filt_sem_contato and cid not in sem_contato_set:
            return False
        if filt_sem_email and cid not in sem_email_set:
            return False
        if filt_sem_whatsapp and cid not in sem_whatsapp_set:
            return False
        if filt_sem_website and comp.get("website"):
            return False
        if filt_sem_phone and comp.get("phone"):
            return False
        if filt_sem_geo and (comp.get("latitude") or comp.get("longitude")):
            return False
        return True

    filtered_base = [c for c in all_companies if _passes_filters(c)]
    total_filtered = len(filtered_base)
    if total_filtered != len(all_companies):
        alert_banner(
            f"Filtros de preparo ativos: <strong>{total_filtered}</strong> escola(s) "
            f"correspondem (de {len(all_companies)} totais).",
            "info",
        )

    # --- Selecao rapida (botoes de preset) ---
    st.caption("SELEÇÃO RÁPIDA")
    preset_cols = st.columns(6)
    with preset_cols[0]:
        if st.button("Top 10 por score", use_container_width=True,
                     icon=":material/trending_up:", key="preset_top_score"):
            scored = [c for c in filtered_base if c.get("qualification_score")]
            scored.sort(key=lambda x: x.get("qualification_score", 0), reverse=True)
            st.session_state["pipeline_selected_ids"] = [c["id"] for c in scored[:10]]
            _reset_ckbox_keys()
            st.toast("Top 10 por score selecionadas!")
            st.rerun()
    with preset_cols[1]:
        if st.button("Top 10 por Fit", use_container_width=True,
                     icon=":material/diamond:", key="preset_top_fit",
                     help="Escolas com maior Fit IAprendo (alvo x tech x coord x categoria)"):
            by_fit = sorted(filtered_base, key=lambda x: x.get("_fit", 0), reverse=True)
            by_fit = [c for c in by_fit if c.get("_fit", 0) > 0]
            st.session_state["pipeline_selected_ids"] = [c["id"] for c in by_fit[:10]]
            _reset_ckbox_keys()
            st.toast("Top 10 por Fit IAprendo selecionadas!")
            st.rerun()
    with preset_cols[2]:
        if st.button("Todas nao processadas", use_container_width=True,
                     icon=":material/fiber_new:", key="preset_raw"):
            raw = [c for c in filtered_base if c.get("status") == "raw"]
            st.session_state["pipeline_selected_ids"] = [c["id"] for c in raw]
            _reset_ckbox_keys()
            st.toast(f"{len(raw)} escolas selecionadas!")
            st.rerun()
    with preset_cols[3]:
        if st.button("Todas privadas", use_container_width=True,
                     icon=":material/lock:", key="preset_private"):
            private = [c for c in filtered_base if "privad" in (c.get("admin_dependency", "") or "").lower()]
            st.session_state["pipeline_selected_ids"] = [c["id"] for c in private]
            _reset_ckbox_keys()
            st.toast(f"{len(private)} escolas privadas selecionadas!")
            st.rerun()
    with preset_cols[4]:
        if st.button("Prontas p/ email", use_container_width=True,
                     icon=":material/mark_email_read:", key="preset_ready"):
            ready = [c for c in filtered_base if c.get("status") in ("qualified", "enriched", "contacted")]
            st.session_state["pipeline_selected_ids"] = [c["id"] for c in ready]
            _reset_ckbox_keys()
            st.toast(f"{len(ready)} escolas prontas selecionadas!")
            st.rerun()
    with preset_cols[5]:
        if st.button("Limpar selecao", use_container_width=True,
                     icon=":material/delete_sweep:", key="preset_clear"):
            st.session_state["pipeline_selected_ids"] = []
            _reset_ckbox_keys()
            st.toast("Selecao limpa!")
            st.rerun()

    # --- Tabela de selecao com checkbox (interativa, escala melhor que autocomplete) ---
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Tabela de Selecao", "checklist")

    # Filtros inline acima da tabela (combinam em AND, alem dos filtros de preparo)
    tf1, tf2, tf3, tf4 = st.columns([2, 2, 2, 2])
    with tf1:
        cidades_disp = sorted({c.get("city") or "?" for c in filtered_base})
        tbl_cidade = st.multiselect(
            "Cidade:", cidades_disp, default=[],
            key="tbl_filter_cidade", placeholder="Todas",
        )
    with tf2:
        status_disp = sorted({c.get("status") or "raw" for c in filtered_base})
        tbl_status = st.multiselect(
            "Status:", status_disp, default=[],
            key="tbl_filter_status",
            format_func=lambda s: f"{STATUS_ICON.get(s, '')} {STATUS_PT.get(s, s)}",
            placeholder="Todos",
        )
    with tf3:
        tbl_score_min = st.slider(
            "Score min:", 0, 100, 0, key="tbl_filter_score",
        )
    with tf4:
        tbl_busca = st.text_input(
            "Buscar nome:", key="tbl_filter_busca",
            placeholder="Digite parte do nome...",
        )

    def _passes_tbl_filter(c):
        if tbl_cidade and (c.get("city") or "?") not in tbl_cidade:
            return False
        if tbl_status and (c.get("status") or "raw") not in tbl_status:
            return False
        if (c.get("qualification_score") or 0) < tbl_score_min:
            return False
        if tbl_busca and tbl_busca.lower() not in (c.get("name", "") or "").lower():
            return False
        return True

    tbl_filtered = [c for c in filtered_base if _passes_tbl_filter(c)]
    current_sel_set = set(st.session_state.get("pipeline_selected_ids", []))

    # ----- Contador destacado (substitui o caption + painel "Selecionadas") -----
    _sel_count = len(current_sel_set)
    _color = "#4CAF50" if _sel_count > 0 else "#9E9E9E"
    st.markdown(
        f'<div style="background:{_color}15; border-left:4px solid {_color}; '
        f'padding:10px 14px; border-radius:4px; margin:8px 0">'
        f'<span style="font-size:16px; font-weight:600; color:{_color}">'
        f'✓ {_sel_count} escola(s) selecionada(s) no total'
        f'</span><br/>'
        f'<span style="font-size:12px; color:#757575">'
        f'Tabela mostra {len(tbl_filtered)} (de {len(filtered_base)} apos filtros de preparo). '
        f'Escolas selecionadas FORA do filtro atual permanecem.'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    if not tbl_filtered:
        alert_banner("Nenhuma escola corresponde aos filtros da tabela.", "info")
    else:
        # ============================================================
        # st.data_editor com df_tbl CACHEADO por filter_signature.
        # Sem reconstruir df a cada run → sem reconciliation do widget →
        # SEM LOOP. Regenera so quando filtros ou selecao externa muda.
        # ============================================================
        filter_signature = (
            tuple(sorted(tbl_cidade)),
            tuple(sorted(tbl_status)),
            tbl_score_min,
            tbl_busca or "",
            tuple(c["id"] for c in tbl_filtered),
            frozenset(current_sel_set),
        )
        cached_sig = st.session_state.get("_tbl_filter_sig")

        if cached_sig != filter_signature:
            # Regenera df_tbl com novo "Sel" baseado em current_sel_set
            df_tbl = pd.DataFrame([{
                "Sel": c["id"] in current_sel_set,
                "Escola": (c.get("name") or "?")[:60],
                "Cidade": c.get("city") or "",
                "UF": c.get("state") or "",
                "Status": f"{STATUS_ICON.get(c.get('status',''), '')} {STATUS_PT.get(c.get('status',''), '')}",
                "Score": c.get("qualification_score") or 0,
                "Fit": c.get("_fit") or 0,
                "Tipo": (c.get("admin_dependency") or "")[:20],
            } for c in tbl_filtered])
            st.session_state["_tbl_df_cached"] = df_tbl
            st.session_state["_tbl_filter_sig"] = filter_signature
            # Reset widget state pra picotar o novo df (sem confusao de edited_rows)
            if "tbl_editor_v3" in st.session_state:
                del st.session_state["tbl_editor_v3"]
        else:
            df_tbl = st.session_state["_tbl_df_cached"]

        edited_tbl = st.data_editor(
            df_tbl[["Sel", "Escola", "Cidade", "UF", "Status", "Score", "Fit", "Tipo"]],
            use_container_width=True,
            hide_index=True,
            height=400,
            column_config={
                "Sel": st.column_config.CheckboxColumn(
                    "✓", default=False, width="small",
                    help="Marcar pra incluir na selecao do pipeline",
                ),
                "Score": st.column_config.ProgressColumn(
                    "Score", width="small", min_value=0, max_value=100, format="%d",
                ),
                "Fit": st.column_config.ProgressColumn(
                    "Fit", width="small", min_value=0, max_value=100, format="%d",
                ),
            },
            disabled=["Escola", "Cidade", "UF", "Status", "Score", "Fit", "Tipo"],
            key="tbl_editor_v3",
        )

        # Sincronizacao: ler edited_tbl (com edited_rows aplicado),
        # comparar com current_sel_set, atualizar session_state,
        # disparar rerun pra mostrar a secao "Executar Pipeline" imediato.
        new_sel_in_view = set()
        for _i in range(len(edited_tbl)):
            if bool(edited_tbl.iloc[_i]["Sel"]) and _i < len(tbl_filtered):
                new_sel_in_view.add(tbl_filtered[_i]["id"])
        _visible_ids = {c["id"] for c in tbl_filtered}
        _preserved_outside = current_sel_set - _visible_ids
        _next_sel = _preserved_outside | new_sel_in_view
        if frozenset(_next_sel) != frozenset(current_sel_set):
            st.session_state["pipeline_selected_ids"] = sorted(_next_sel)
            # IMPORTANTE: NAO chamar st.rerun() aqui — engoliria clicks de outros
            # widgets (botoes Enriquecer/Qualificar, selectbox Modo, etc).
            # A secao "Executar Pipeline" aparece naturalmente no MESMO run
            # porque selected_ids = st.session_state.get(...) (linha 530+) le
            # o valor JA atualizado nesta linha. Sem rerun extra necessario.

    # --- Autocomplete multiselect + Colar Lista (fallback pra busca por nome / cola externa) ---
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Busca avancada (opcional)", "search")
    sub_tab_auto, sub_tab_paste = st.tabs(["Autocomplete", "Colar Lista"])

    with sub_tab_auto:
        # Opts_map: display label -> id
        opts_map = {}
        for c in filtered_base:
            fit = c.get("_fit") or 0
            score = c.get("qualification_score") or 0
            label = f"{c.get('name', '?')[:50]} — {c.get('city','?')} · Score {score} · Fit {fit}"
            opts_map[label] = c["id"]

        current_ids = set(st.session_state.get("pipeline_selected_ids", []))
        expected_labels = [lbl for lbl, cid in opts_map.items() if cid in current_ids]

        # CRITICO: sincronizar state interno do multiselect com pipeline_selected_ids
        # ANTES de renderizar. Sem isso, o widget mantem seu state antigo e
        # SOBRESCREVE pipeline_selected_ids com valor desatualizado, zerando
        # a selecao recem feita via tabela (checkbox).
        _multi_key = "pipeline_multiselect"
        if _multi_key in st.session_state:
            if set(st.session_state[_multi_key]) != set(expected_labels):
                st.session_state[_multi_key] = expected_labels
        else:
            # Primeira renderizacao — inicializar com valor atual
            st.session_state[_multi_key] = expected_labels

        selected_labels = st.multiselect(
            "Escolas para o pipeline",
            options=list(opts_map.keys()),
            # SEM default= — session_state ja foi setado acima e eh fonte da verdade
            help="Digite o nome pra buscar. Seleciona multiplas. Resultado sincroniza com a selecao global.",
            key=_multi_key,
            placeholder="Digite pra buscar escolas...",
        )
        new_ids = [opts_map[lbl] for lbl in selected_labels]
        # So atualizar se houve mudanca REAL (user interagiu com o multiselect)
        if set(new_ids) != current_ids:
            st.session_state["pipeline_selected_ids"] = new_ids
            _reset_ckbox_keys()
            st.rerun()

    with sub_tab_paste:
        paste_text = st.text_area("Cole nomes ou codigos INEP (um por linha):",
                                   height=150, placeholder="Colegio ABC\nEscola XYZ\n12345678",
                                   key="pipeline_paste")
        if st.button("Buscar e adicionar", icon=":material/search:", key="pipeline_paste_btn"):
            if paste_text.strip():
                lines = [l.strip() for l in paste_text.strip().split("\n") if l.strip()]
                found_ids = []
                not_found = []
                for line in lines:
                    match = None
                    for c in filtered_base:
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
                    _reset_ckbox_keys()
                    st.toast(f"{len(found_ids)} escolas encontradas e adicionadas!")
                if not_found:
                    st.warning(f"{len(not_found)} nao encontradas: {', '.join(not_found[:5])}")
                if found_ids:
                    st.rerun()

    # --- Selection preview ---
    selected_ids = st.session_state.get("pipeline_selected_ids", [])
    if not selected_ids:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        alert_banner(
            "Selecione escolas acima para ativar o pipeline. Use os botoes de selecao rapida, "
            "o autocomplete ou colar lista.",
            "info",
        )
        return

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
            "Urgencia": c.get("urgency_tier") or "COLD",
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

    # Ler o estado atual do checkbox Forcar (renderizado mais abaixo) pra
    # calcular contadores corretos. Quando Forcar=True, TODAS as selecionadas
    # viram elegiveis (porque o backend ignora filtro de status com force=True).
    # Sem Forcar: conta apenas escolas no status compativel com cada step.
    _force_active = bool(st.session_state.get("pipe_force_reprocess", False))
    _sel_total_for_cards = len(selected_ids)
    if _force_active:
        raw_count = _sel_total_for_cards
        qualified_count = _sel_total_for_cards
        enriched_count = _sel_total_for_cards
        contactable_count = _sel_total_for_cards
    else:
        raw_count = sel_by_status.get("raw", 0)
        qualified_count = sel_by_status.get("qualified", 0)
        enriched_count = sel_by_status.get("enriched", 0)
        contactable_count = qualified_count + enriched_count + sel_by_status.get("contacted", 0)

    # Controles do pipeline (3 colunas — Forcar fica em destaque mais abaixo)
    ctrl1, ctrl2, ctrl3 = st.columns(3)
    with ctrl1:
        write_mode_label = st.selectbox("Modo de mensagem:", ["IA (personalizada)", "Template (padrao)"],
                                         key="pipe_write_mode")
        write_mode = "ai" if "IA" in write_mode_label else "template"
    with ctrl2:
        score_min = st.slider("Score minimo para email:", 0, 100, 60, key="pipe_score_min")
    with ctrl3:
        dry_run = st.checkbox("Modo simulado (dry run)", value=False, key="pipe_dry_run",
                               help="Apenas simula, nao executa de verdade.")

    # Forcar reprocessar — destaque visual maior, perto dos botoes
    force_reprocess = st.checkbox(
        "🔁 **Forcar reprocessar** (use pra rodar enrich numa escola ja enriched, etc)",
        value=False,
        key="pipe_force_reprocess",
        help=(
            "Sem essa opcao, cada etapa pula escolas que ja passaram dela "
            "(ex: enrich nao roda em escolas em status enriched). "
            "Marque pra forcar a re-execucao. Agents tambem vao tentar refetch "
            "(re-buscar Google Places, re-rodar cascata de contatos, etc)."
        ),
    )

    # Callout grande quando Forcar esta ATIVO — fica obvio que precisa clicar
    # em um botao de step abaixo DEPOIS de marcar (nao executa automatico).
    if force_reprocess:
        st.success(
            f"✅ **Modo FORÇAR ATIVO** — agora clique em **qualquer botão abaixo** "
            f"(Qualificar / Enriquecer / Contatos / Gerar) pra rodar em "
            f"**todas as {len(selected_ids)} escola(s) selecionada(s)**, "
            f"ignorando o status atual.",
            icon="🚀",
        )

    # Pipeline steps as cards — cascata (cada botao roda TODAS as etapas
    # anteriores + a sua). Garante que Top N por Fit (em qualquer status)
    # consiga ir direto pra Buscar contatos ou Gerar emails.
    sel_total = len(selected_ids)
    no_selection = sel_total == 0

    # Mapa: cada step espera escolas em quais status?
    _STEP_INPUT_STATUS = {
        "qualify": {"raw"},
        "enrich": {"qualified"},
        "contacts": {"enriched"},
        "write": {"enriched", "qualified", "contacted"},
    }
    _STATUS_LABEL = {
        "raw": "Novas", "qualified": "Qualificadas", "enriched": "Enriquecidas",
        "contacted": "Contatadas", "responded": "Respondeu", "converted": "Convertida",
    }

    def _precheck_eligibility(step_list: list) -> dict:
        """Conta quantas escolas selecionadas se encaixam em cada step (por status).
        Considera cascata: o status pos-step anterior conta como entrada do proximo.
        """
        # Status atuais das escolas selecionadas
        sel_status_counts = dict(sel_by_status)  # {raw: N, qualified: M, ...}
        eligible_per_step = {}
        cum_counts = dict(sel_status_counts)  # simula avanco da cascata

        for step in step_list:
            expected = _STEP_INPUT_STATUS.get(step, set())
            elig = sum(cum_counts.get(s, 0) for s in expected)
            eligible_per_step[step] = elig
            # Simula avanco da cascata: o que rodou neste step "avanca" pro proximo
            if step == "qualify":
                advanced = cum_counts.pop("raw", 0)
                cum_counts["qualified"] = cum_counts.get("qualified", 0) + advanced
            elif step == "enrich":
                advanced = cum_counts.pop("qualified", 0)
                cum_counts["enriched"] = cum_counts.get("enriched", 0) + advanced
            elif step == "contacts":
                # contacts nao muda status — fica em enriched
                pass
            elif step == "write":
                advanced = (
                    cum_counts.pop("enriched", 0)
                    + cum_counts.pop("qualified", 0)
                    + cum_counts.pop("contacted", 0)
                )
                cum_counts["contacted"] = cum_counts.get("contacted", 0) + advanced
        return eligible_per_step

    def _cascade(step_name: str, step_list: list, extra_kwargs: dict = None):
        """Executa run_pipeline com pre-check + salva resultado em session_state.

        O resultado eh persistido pra continuar visivel mesmo apos reruns
        causados por outros widgets (marcar checkbox, etc).
        """
        from workflows.daily_pipeline import run_pipeline

        # PRE-CHECK: se nao em modo forcar, validar elegibilidade dos steps
        if not force_reprocess:
            elig = _precheck_eligibility(step_list)
            total_elig_last = elig.get(step_name, 0)
            if total_elig_last == 0:
                # Salvar o erro de pre-check pra renderizar de forma persistente
                status_atual = ", ".join(
                    f"{_STATUS_LABEL.get(s, s)}: {n}"
                    for s, n in sorted(sel_by_status.items())
                ) or "(vazio)"
                status_esperado_set = _STEP_INPUT_STATUS.get(step_name, set())
                status_esperado_txt = ", ".join(
                    _STATUS_LABEL.get(s, s) for s in sorted(status_esperado_set)
                )
                st.session_state["pipeline_last_run"] = {
                    "kind": "precheck_error",
                    "step_name": step_name,
                    "step_list": step_list,
                    "sel_total": sel_total,
                    "status_atual": status_atual,
                    "status_esperado": status_esperado_txt,
                    "timestamp": datetime.now().isoformat() if "datetime" in globals() else "",
                }
                return

        # Executar pipeline
        kwargs = {
            "qualify_limit": sel_total,
            "enrich_limit": sel_total,
            "write_limit": sel_total,
            "send_approved": False,
            "dry_run": dry_run,
            "write_mode": write_mode,
            "company_ids": selected_ids,
            "steps": step_list,
            "force": force_reprocess,
        }
        if extra_kwargs:
            kwargs.update(extra_kwargs)

        with st.spinner(
            f"Executando '{step_name}' em {sel_total} escola(s)"
            f"{' (modo FORCAR)' if force_reprocess else ''}..."
        ):
            report = run_pipeline(**kwargs)

        # Salvar resultado em session_state pra persistir entre reruns
        st.session_state["pipeline_last_run"] = {
            "kind": "execution",
            "step_name": step_name,
            "step_list": step_list,
            "report": report,
            "force_used": force_reprocess,
            "timestamp": datetime.now().isoformat() if "datetime" in globals() else "",
        }

    pc1, pc2, pc3, pc4, pc5 = st.columns(5)

    with pc1:
        metric_card("Qualificar", raw_count, icon="grading", color=STATUS_COLORS["raw"])
        if st.button("Qualificar", disabled=no_selection, key="btn_qualify",
                      use_container_width=True, type="primary",
                      help="Roda qualify na selecao (so processa schools em status raw)"):
            _cascade("qualify", ["qualify"])

    with pc2:
        metric_card("Enriquecer", qualified_count, icon="auto_fix_high", color=STATUS_COLORS["qualified"])
        if st.button("Enriquecer", disabled=no_selection, key="btn_enrich",
                      use_container_width=True, type="primary",
                      help="Cascata: qualify -> enrich. Qualifica raw e enriquece qualified."):
            _cascade("enrich", ["qualify", "enrich"])

    with pc3:
        metric_card("Contatos", enriched_count, icon="person_search", color=STATUS_COLORS["enriched"])
        if st.button("Buscar", disabled=no_selection, key="btn_contacts",
                      use_container_width=True, type="primary",
                      help="Cascata: qualify -> enrich -> contacts. Processa tudo ate busca de decisores."):
            _cascade("contacts", ["qualify", "enrich", "contacts"])

    with pc4:
        metric_card("Emails", contactable_count, icon="edit_note", color=STATUS_COLORS["contacted"])
        if st.button("Gerar", disabled=no_selection, key="btn_write",
                      use_container_width=True, type="primary",
                      help="Cascata: qualify -> enrich -> contacts -> write. Gera emails pra fila de aprovacao."):
            _cascade("write", ["qualify", "enrich", "contacts", "write"])

    with pc5:
        metric_card("Enviar", approved_count, icon="send", color=STATUS_COLORS["approved"])
        if st.button("Enviar", disabled=(approved_count == 0), key="btn_send",
                      use_container_width=True, type="primary",
                      help="Envia emails ja aprovados (independente da selecao)."):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner("Enviando emails aprovados..."):
                report = run_pipeline(
                    qualify_limit=0, enrich_limit=0, write_limit=0,
                    send_approved=True, dry_run=dry_run,
                    steps=["send"],
                )
            # Persistir em vez de toast (que some no proximo rerun)
            st.session_state["pipeline_last_run"] = {
                "kind": "execution",
                "step_name": "send",
                "step_list": ["send"],
                "report": report,
                "force_used": False,
                "timestamp": datetime.now().isoformat(),
            }

    # ======================================================================
    # FEEDBACK PERSISTENTE — sempre renderiza o ultimo resultado (sobrevive a reruns)
    # ======================================================================
    _last = st.session_state.get("pipeline_last_run")
    if _last:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        _hdr_cols = st.columns([5, 1])
        with _hdr_cols[0]:
            section_header(
                f"Ultimo resultado: {_last.get('step_name', '?')}"
                f"{' (FORCAR)' if _last.get('force_used') else ''}",
                "history",
            )
        with _hdr_cols[1]:
            if st.button("Limpar", key="clear_last_run", use_container_width=True,
                          icon=":material/close:"):
                st.session_state.pop("pipeline_last_run", None)
                st.rerun()

        _ts = _last.get("timestamp", "")
        if _ts:
            st.caption(f"Executado em {_ts[:19].replace('T', ' ')}")

        if _last.get("kind") == "precheck_error":
            st.error(
                f"**Nenhuma das {_last['sel_total']} escola(s) selecionada(s) eh elegivel "
                f"para '{_last['step_name']}'.**\n\n"
                f"- Status atual das selecionadas: {_last['status_atual']}\n"
                f"- A etapa '{_last['step_name']}' precisa de escolas em: **{_last['status_esperado']}**\n\n"
                f"💡 **Soluções:**\n"
                f"1. Marque o checkbox **'🔁 Forcar reprocessar'** acima e clique de novo "
                f"(vai rodar nas selecionadas mesmo que ja tenham passado dessa etapa).\n"
                f"2. OU selecione outras escolas que estejam no status necessario."
            )
        else:
            # kind=execution
            _report = _last.get("report", {}) or {}
            _steps_data = _report.get("steps", {})
            _step_name = _last.get("step_name", "?")
            _step_list = _last.get("step_list", [_step_name])

            if _step_name == "send":
                _send_r = _steps_data.get("send", {}) or {}
                _sent = _send_r.get("sent", 0)
                _failed = _send_r.get("failed", 0)
                if _sent > 0:
                    st.success(f"✅ **{_sent} email(s) enviado(s)** com sucesso. Falhas: {_failed}.")
                elif _failed > 0:
                    st.error(f"❌ **0 enviados, {_failed} falharam.** Veja detalhes abaixo.")
                else:
                    st.info("ℹ️ Nenhum email aprovado aguardando envio.")
            else:
                _last_step_out = _steps_data.get(_step_name, {}).get("output", 0)
                _total_proc = sum(
                    _steps_data.get(s, {}).get("output", 0) for s in _step_list
                )
                if _last_step_out > 0:
                    st.success(
                        f"✅ **'{_step_name}' concluido:** "
                        f"{_last_step_out} escola(s) processada(s) nesta etapa "
                        f"(total na cascata: {_total_proc})."
                    )
                elif _total_proc > 0:
                    st.warning(
                        f"⚠️ **Cascata rodou** mas a etapa final '{_step_name}' "
                        f"processou 0. Outras etapas processaram: {_total_proc}."
                    )
                else:
                    st.error(
                        f"❌ **Nenhuma escola foi processada em '{_step_name}'.**\n\n"
                        f"Possiveis causas:\n"
                        f"- API key faltando no Streamlit Cloud (OPENAI_API_KEY, "
                        f"ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY, APOLLO_API_KEY, etc)\n"
                        f"- Rate limit atingido\n"
                        f"- Escolas ja completas (todos os campos preenchidos) — "
                        f"agents 'inteligentes' so atualizam o que esta vazio. "
                        f"Use **'🔁 Forcar reprocessar'** pra forcar refetch."
                    )

            # Breakdown por etapa
            if _step_list and _step_name != "send":
                _bd_cols = st.columns(len(_step_list))
                for _i, _s in enumerate(_step_list):
                    _r = _steps_data.get(_s, {}) or {}
                    _inp = _r.get("input", 0)
                    _out = _r.get("output", 0)
                    with _bd_cols[_i]:
                        _color = "#4CAF50" if _out > 0 else ("#FF9800" if _inp > 0 else "#9E9E9E")
                        st.markdown(
                            f'<div style="border-left:4px solid {_color}; padding:8px 12px; '
                            f'background:#f5f5f5; border-radius:4px">'
                            f'<div style="font-size:11px; color:#757575; text-transform:uppercase">{_s}</div>'
                            f'<div style="font-size:18px; font-weight:600">{_out}/{_inp}</div>'
                            f'<div style="font-size:10px; color:#999">processadas/entradas</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            with st.expander("Ver relatorio JSON completo", expanded=False):
                st.json(_report)

    # Full pipeline button
    st.markdown("")
    full1, full2 = st.columns([1, 3])
    with full1:
        if st.button("Pipeline Completo", type="primary", use_container_width=True,
                      icon=":material/rocket_launch:"):
            from workflows.daily_pipeline import run_pipeline
            with st.spinner(
                f"Executando pipeline completo{'(modo FORCAR)' if force_reprocess else ''}..."
            ):
                report = run_pipeline(
                    qualify_limit=raw_count or 50,
                    enrich_limit=qualified_count or 50,
                    write_limit=contactable_count or 50,
                    send_approved=False,
                    dry_run=dry_run,
                    write_mode=write_mode,
                    company_ids=selected_ids,
                    force=force_reprocess,
                )
            # Persistir resultado (sobrevive a reruns)
            st.session_state["pipeline_last_run"] = {
                "kind": "execution",
                "step_name": "write",
                "step_list": ["qualify", "enrich", "contacts", "write"],
                "report": report,
                "force_used": force_reprocess,
                "timestamp": datetime.now().isoformat(),
            }
    with full2:
        st.caption(
            "Executa todas as etapas em sequencia: Qualificar \u2192 Enriquecer \u2192 "
            "Buscar Contatos \u2192 Gerar Emails. Emails nao sao enviados automaticamente "
            "\u2014 va para a Fila de Aprovacao para revisar e aprovar."
        )


def render_descoberta():
    """Aba Descoberta: enriquecimento web em lote + busca de sinais em lote."""
    from tools.discovery_engine import discovery_engine

    section_header("Enriquecer escolas com dados da web", "search")
    st.markdown(
        '<div style="font-size:13px;color:#757575;margin-bottom:12px">'
        'Busca na web informacoes sobre escolas que <strong>ja estao no banco</strong>. '
        'Atualiza dados faltantes (site, telefone) e adiciona sinais (rankings, premios, '
        'noticias) que serao usados automaticamente nos emails.'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.form("enrich_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            cidade = st.text_input(
                "Cidade *",
                placeholder="Ex: Porto Alegre, Canoas",
            )
            tipo = st.selectbox(
                "Tipo de escola",
                options=["privada", "publica", "qualquer"],
                index=0,
                format_func=lambda x: {"privada": "Privada", "publica": "Publica", "qualquer": "Qualquer"}[x],
            )
        with col_b:
            keyword = st.text_input(
                "Diferencial (opcional)",
                placeholder="Ex: bilingue, integral, tecnologia",
            )
            limite = st.number_input("Limite", min_value=1, max_value=30, value=10, step=1)

        submit = st.form_submit_button("🔍 Enriquecer agora", type="primary", use_container_width=True)

    if submit:
        if not cidade or len(cidade.strip()) < 2:
            st.error("Informe uma cidade valida.")
        else:
            with st.spinner(f"Buscando dados na web para escolas de {cidade}... (30-60 segundos)"):
                try:
                    result = discovery_engine.enriquecer_escolas_web(
                        cidade=cidade.strip(),
                        tipo=tipo,
                        keyword=keyword.strip(),
                        limit=int(limite),
                    )
                    enriquecidas = result.get("enriquecidas", [])
                    sinais = result.get("sinais_adicionados", 0)
                    dados = result.get("dados_atualizados", [])
                    erros = result.get("erros", [])

                    if enriquecidas:
                        st.success(
                            f"✅ {len(enriquecidas)} escola(s) enriquecida(s) | "
                            f"{sinais} sinal(is) adicionado(s) | "
                            f"{len(dados)} dado(s) atualizado(s)"
                        )
                        for e in enriquecidas:
                            extras = ""
                            if e.get("dados_novos"):
                                extras = f" | Novos: {', '.join(e['dados_novos'])}"
                            if e.get("diferenciais"):
                                extras += f" | Diferenciais: {', '.join(e['diferenciais'])}"
                            st.markdown(f"- **{e.get('escola', '?')}**{extras}")
                    else:
                        st.info(
                            "Nenhuma escola do banco encontrada nos resultados web. "
                            "Tente outra cidade ou tipo."
                        )
                    if erros:
                        for err in erros[:3]:
                            st.warning(f"⚠️ {err}")
                except Exception as e:
                    st.error(f"Erro: {e}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # ==================================================================
    # Buscar sinais em lote — tabela filtravel com checkboxes
    # ==================================================================
    section_header("Buscar sinais (rankings, premios, noticias)", "psychology")
    st.caption(
        "Filtre, selecione multiplas escolas e roda em lote. Resultados sao "
        "salvos como memorias e usados automaticamente nos proximos emails."
    )

    # --- Filtros horizontais ---
    flt_cols = st.columns([3, 2, 2, 2, 2])
    with flt_cols[0]:
        sig_search = st.text_input(
            "Buscar por nome",
            placeholder="Digite parte do nome...",
            key="sig_search",
            label_visibility="collapsed",
        )
    with flt_cols[1]:
        sig_cidades = sorted({(c.get("city") or "").strip() for c in all_companies if c.get("city")})
        sig_cidade_sel = st.multiselect(
            "Cidade",
            options=sig_cidades,
            key="sig_cidade",
            placeholder="Cidade...",
            label_visibility="collapsed",
        )
    with flt_cols[2]:
        sig_tipos = sorted({
            (c.get("admin_dependency") or "").strip()
            for c in all_companies if c.get("admin_dependency")
        })
        sig_tipo_sel = st.multiselect(
            "Tipo",
            options=sig_tipos,
            key="sig_tipo",
            placeholder="Tipo...",
            label_visibility="collapsed",
        )
    with flt_cols[3]:
        sig_score_min = st.slider("Score min", 0, 100, 0, key="sig_score_min")
    with flt_cols[4]:
        sig_fit_min = st.slider("Fit min", 0, 100, 0, key="sig_fit_min")

    # --- Filtrar lista ---
    def _passa_filtro_sig(c):
        if sig_search and sig_search.lower() not in (c.get("name") or "").lower():
            return False
        if sig_cidade_sel and c.get("city") not in sig_cidade_sel:
            return False
        if sig_tipo_sel and c.get("admin_dependency") not in sig_tipo_sel:
            return False
        if sig_score_min > 0 and (c.get("qualification_score") or 0) < sig_score_min:
            return False
        if sig_fit_min > 0 and (c.get("_fit") or 0) < sig_fit_min:
            return False
        return True

    filtered_sig = [c for c in all_companies if _passa_filtro_sig(c)]

    # --- Tabela com checkbox ---
    if not filtered_sig:
        alert_banner("Nenhuma escola corresponde aos filtros.", "info")
    else:
        df_sig = pd.DataFrame([{
            "Sel": False,
            "Escola": (c.get("name") or "?")[:50],
            "Cidade": c.get("city") or "",
            "Score": int(c.get("qualification_score") or 0),
            "Fit": int(c.get("_fit") or 0),
            "Alvo": int((c.get("matriculas_fund_af") or 0) + (c.get("matriculas_medio") or 0)),
            "Tech": c.get("nivel_tecnologico") or "-",
            "Urgencia": c.get("urgency_tier") or "COLD",
            "Tipo": (c.get("admin_dependency") or "")[:15],
            "id": c["id"],
        } for c in sorted(filtered_sig, key=lambda x: (x.get("_fit") or 0), reverse=True)])

        # Sinalizacao de contagem (1.1 Quick Win)
        from dashboard._table_count import render_count
        render_count(
            total=len(all_companies),
            filtered=len(filtered_sig),
            label_singular="escola",
            label_plural="escolas",
        )

        edited_sig = st.data_editor(
            df_sig[["Sel", "Escola", "Cidade", "Score", "Fit", "Alvo", "Tech", "Tipo"]],
            use_container_width=True,
            hide_index=True,
            height=350,
            column_config={
                "Sel": st.column_config.CheckboxColumn("✓", default=False, width="small"),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
                "Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%d"),
                "Alvo": st.column_config.NumberColumn("Alvo", width="small"),
                "Tech": st.column_config.TextColumn("Tech", width="small"),
            },
            disabled=["Escola", "Cidade", "Score", "Fit", "Alvo", "Tech", "Tipo"],
            key="sig_data_editor",
        )

        # Contar selecionados
        sel_mask = edited_sig["Sel"] == True
        n_selected = int(sel_mask.sum())
        selected_sig_ids = [df_sig.iloc[i]["id"] for i in edited_sig[sel_mask].index]
        selected_sig_names = [df_sig.iloc[i]["Escola"] for i in edited_sig[sel_mask].index]

        if st.button(
            f"🔍 Buscar sinais ({n_selected} selecionada(s))",
            disabled=n_selected == 0,
            type="primary",
            key="btn_buscar_sinais_lote",
        ):
            total_sinais = 0
            erros_lote = []
            with st.spinner(f"Buscando sinais de {n_selected} escola(s)... pode levar alguns minutos"):
                for cid, cname in zip(selected_sig_ids, selected_sig_names):
                    try:
                        result = discovery_engine.enrich_signals(cid)
                        n = result.get("sinais_adicionados", 0)
                        total_sinais += n
                        if n > 0:
                            st.markdown(f"- ✅ **{cname}**: {n} sinal(is)")
                            for preview in result.get("preview", [])[:3]:
                                st.markdown(f"    - {preview}")
                        else:
                            st.markdown(f"- ⚪ **{cname}**: nenhum sinal encontrado")
                        if result.get("erros"):
                            erros_lote.extend(result["erros"])
                    except Exception as e:
                        erros_lote.append(f"{cname}: {e}")
            if total_sinais > 0:
                st.success(f"✅ Total: {total_sinais} sinal(is) em {n_selected} escola(s)")
            if erros_lote:
                for err in erros_lote[:5]:
                    st.warning(f"⚠️ {err}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.info(
        "💡 **Dica:** voce tambem pode fazer isso pelo WhatsApp. "
        "Diga: _\"enriquece as escolas de Canoas\"_ ou _\"busca sinais do Marista\"_."
    )


def render_kanban_comercial():
    """Aba Pipeline Comercial: kanban de stages reais (zona 2 do commit anterior)."""
    from dashboard.theme import kanban_card_clickable

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
        # Carrega companies com stage + valores comerciais.
        # Fallback gracioso se migration 013 nao foi aplicada.
        try:
            comm_companies = db.client.table("companies").select(
                "id,name,city,qualification_score,commercial_stage,valor_mensal_proposto,"
                "valor_mensal_fechado,motivo_perda_texto,motivo_perda_categoria,data_fechamento,"
                "matriculas_fund_af,matriculas_medio,nivel_tecnologico,status"
            ).execute().data or []
        except Exception as _migration_err:
            if "commercial_stage" in str(_migration_err) or "42703" in str(_migration_err):
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

        # Meetings + emails enviados pra inferencia automatica de stage
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

        # Mapa do status tecnico (companies.status) -> stage do Kanban comercial.
        # Sem isto, mudar status para 'responded'/'contacted'/'converted' fazia a
        # escola SUMIR do Kanban (caia em return None).
        STATUS_TO_STAGE = {
            "responded": "respondeu",
            "contacted": "contatado",
            "converted": "cliente",
            "rejected": "perdido",
            "descartado": "perdido",
        }

        def _infer_stage(comp):
            """Prioridade: commercial_stage manual > status tecnico mapeado >
            inferencia (meeting/email) > prospectado (status inicial)."""
            manual = comp.get("commercial_stage")
            if manual:
                return manual
            st_tech = (comp.get("status") or "").lower()
            if st_tech in STATUS_TO_STAGE:
                return STATUS_TO_STAGE[st_tech]
            cid = comp["id"]
            if cid in _meeting_set:
                return "reuniao"
            if _email_map.get(cid, {}).get("replied"):
                return "respondeu"
            if cid in _email_map:
                return "contatado"
            if st_tech in ("raw", "qualified", "enriched", "filtered"):
                return "prospectado"
            return None

        stage_buckets = {s["key"]: [] for s in COMMERCIAL_STAGES}
        perdidos = []
        for _c in comm_companies:
            stage = _infer_stage(_c)
            if stage == "perdido":
                perdidos.append(_c)
            elif stage in stage_buckets:
                stage_buckets[stage].append(_c)

        # KPI row: MRR + Win rate
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

        # Kanban: contagem + top 6 cards por stage
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

                # Helper pra computar meta de cada escola
                def _card_meta(comp, stage_key=stage["key"]):
                    score = int(comp.get("qualification_score") or 0)
                    name = ((comp.get("name") or "?")[:28]).rstrip()
                    alvo_ = int((comp.get("matriculas_fund_af") or 0) + (comp.get("matriculas_medio") or 0))
                    tech = comp.get("nivel_tecnologico") or ""
                    sub = ""
                    if stage_key == "proposta" and comp.get("valor_mensal_proposto"):
                        sub = f"R$ {float(comp['valor_mensal_proposto']):,.0f}/mes".replace(",", ".")
                    elif stage_key == "cliente" and comp.get("valor_mensal_fechado"):
                        sub = f"R$ {float(comp['valor_mensal_fechado']):,.0f}/mes".replace(",", ".")
                    return score, name, alvo_, tech, sub

                # Top 6 cards visiveis (clicaveis)
                sorted_items = sorted(items, key=lambda x: x.get("qualification_score") or 0, reverse=True)
                for comp in sorted_items[:6]:
                    score, name, alvo_, tech, sub = _card_meta(comp)
                    if kanban_card_clickable(
                        name=name,
                        score=score,
                        alvo=alvo_,
                        nivel_tech=tech,
                        color=stage["color"],
                        key=f"kanban_{stage['key']}_{comp['id']}",
                        subtitle=sub,
                    ):
                        st.session_state["escola_detail_id"] = comp["id"]
                        st.switch_page("pages/2_🏫_Escolas.py")

                # Expander com os restantes (clicaveis tambem)
                if len(sorted_items) > 6:
                    with st.expander(f"Ver mais {len(sorted_items) - 6}", expanded=False):
                        for comp in sorted_items[6:]:
                            score, name, alvo_, tech, sub = _card_meta(comp)
                            if kanban_card_clickable(
                                name=name,
                                score=score,
                                alvo=alvo_,
                                nivel_tech=tech,
                                color=stage["color"],
                                key=f"kanban_exp_{stage['key']}_{comp['id']}",
                                subtitle=sub,
                            ):
                                st.session_state["escola_detail_id"] = comp["id"]
                                st.switch_page("pages/2_🏫_Escolas.py")

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

        st.caption(
            "💡 Os stages Proposta/Cliente/Perdido sao preenchidos pelo IAlex via WhatsApp: "
            "\"mandei proposta pro Marista, R$ 15k/mes\" · "
            "\"fechei o Anchieta, R$ 18k/mes\" · "
            "\"perdi o Adventista, foi pra concorrencia\""
        )
    except Exception as _e:
        st.warning(f"Erro ao carregar pipeline comercial: {_e}")


# ==========================================================================
# Render das 3 abas
# ==========================================================================
main_tab_exec, main_tab_desc, main_tab_kanban = st.tabs([
    "🔧 Execucao",
    "🔍 Descoberta",
    "📋 Pipeline Comercial",
])

with main_tab_exec:
    render_execucao()

with main_tab_desc:
    render_descoberta()

with main_tab_kanban:
    render_kanban_comercial()


# ======================================================================
# SYSTEM SECTION (fora das abas, rodape da pagina)
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
