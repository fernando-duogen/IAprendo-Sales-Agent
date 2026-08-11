"""Visao "Inteligencia" (Radar comparativo + Explorador livre) — extraida de
7_🎯_Inteligencia.py (rodada 5). O Ranking P1/P2/P3 NAO veio junto: ja vive em
🔍 Prospectar → ⭐ Recomendadas (mesma tool priorizar_leads_enem).
"""
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.theme import metric_card, section_header, alert_banner, COLORS
from database.supabase_client import db

try:
    from agent.tools.enem_tools import (
        _handle_priorizar_leads_enem,
        _handle_analisar_dados_analytics,
        ALLOWED_ANALYTICS_METRICS,
        ALLOWED_GROUPINGS,
        ALLOWED_OPERATIONS,
        ALLOWED_AGGREGATIONS,
        ALLOWED_COMPARACAO_COM,
        ALLOWED_MODO_REDACAO,
    )
    _ENEM_OK, _ENEM_ERR = True, ""
except Exception as _e:
    _ENEM_OK, _ENEM_ERR = False, str(_e)


@st.cache_data(ttl=120)
def _global_kpis() -> dict:
    """Conta P1/P2/P3 no banco inteiro (usado nos cards de topo)."""
    try:
        total = db.client.table("school_analytics").select(
            "id", count="estimated"
        ).limit(1).execute().count or 0

        confiavel = db.client.table("school_analytics").select(
            "id", count="estimated"
        ).eq("enem_amostra_confiavel", True).limit(1).execute().count or 0

        linked = db.client.table("school_analytics").select(
            "id", count="estimated"
        ).not_.is_("company_id", "null").limit(1).execute().count or 0

        return {
            "total": total,
            "confiavel": confiavel,
            "linked": linked,
        }
    except Exception as e:
        return {"error": str(e)}



def render_inteligencia() -> None:
    """Radar comparativo + Explorador livre sobre school_analytics."""
    if not _ENEM_OK:
        st.error(f"Modulo enem_tools indisponivel: {_ENEM_ERR}")
        return

    st.caption(
        "Analises livres sobre a base ENEM/Censo (185k escolas). Guardrails "
        "eticos do IAlex valem aqui (amostra confiavel, peer group, municipio)."
    )

    kpis = _global_kpis()
    if "error" in kpis:
        alert_banner(f"Erro carregando KPIs: {kpis['error']}", "error")
    else:
        kc1, kc2, kc3 = st.columns(3)
        with kc1:
            metric_card(
                "Escolas no school_analytics",
                f"{kpis['total']:,}".replace(",", "."),
                COLORS["primary"], icon="database",
            )
        with kc2:
            metric_card(
                "Amostra confiavel",
                f"{kpis['confiavel']:,}".replace(",", "."),
                COLORS["info"], icon="verified",
            )
        with kc3:
            metric_card(
                "Linked no CRM (companies)",
                str(kpis["linked"]),
                COLORS["success"], icon="link",
            )

    st.markdown("---")

    alert_banner(
        "Procurando o ranking de leads P1/P2/P3? Ele vive em "
        "🔍 Prospectar → ⭐ Recomendadas (com botao 'Trabalhar').", "info"
    )

    tab_radar, tab_explorer = st.tabs([
        "🎯 Radar Comparativo",
        "🧪 Explorador livre",
    ])

    with tab_radar:
        st.caption(
            "Compare o perfil de uma escola (ou grupo) contra referencias "
            "(municipio, estado, Brasil) nas 5 areas do ENEM e nas 5 "
            "competencias da redacao. Apenas escolas com amostra confiavel."
        )

        # 5 areas do ENEM + 5 competencias da redacao
        _RADAR_AREAS = [
            "enem_media_mt", "enem_media_cn", "enem_media_ch",
            "enem_media_lc", "enem_media_redacao",
        ]
        _RADAR_COMPS = [
            "enem_redacao_comp1_media", "enem_redacao_comp2_media",
            "enem_redacao_comp3_media", "enem_redacao_comp4_media",
            "enem_redacao_comp5_media",
        ]
        _AREA_LABELS = {
            "enem_media_mt": "Matematica",
            "enem_media_cn": "Ciencias Natureza",
            "enem_media_ch": "Ciencias Humanas",
            "enem_media_lc": "Linguagens",
            "enem_media_redacao": "Redacao",
        }
        _COMP_LABELS = {
            "enem_redacao_comp1_media": "C1: Norma Culta",
            "enem_redacao_comp2_media": "C2: Compreensao",
            "enem_redacao_comp3_media": "C3: Argumentacao",
            "enem_redacao_comp4_media": "C4: Coesao",
            "enem_redacao_comp5_media": "C5: Proposta",
        }

        # Color palette for traces
        _TRACE_COLORS = [
            COLORS.get("primary", "#4A90D9"),
            COLORS.get("error", "#FF6B6B"),
            COLORS.get("success", "#51CF66"),
            COLORS.get("warning", "#FFA94D"),
            COLORS.get("info", "#339AF0"),
        ]

        # ----- Form -----
        section_header("Alvo e Referencias", "compare_arrows")
        rc1, rc2 = st.columns(2)
        with rc1:
            radar_mode = st.selectbox(
                "Modo",
                [
                    "Uma escola vs referencias",
                    "Grupo (filtro) vs referencias",
                ],
            )
        with rc2:
            radar_chart_type = st.selectbox(
                "Tipo de radar",
                [
                    "📐 5 areas do ENEM (MT, CN, CH, LC, Redacao)",
                    "✍️ 5 competencias da redacao",
                    "📊 Ambos (lado a lado)",
                ],
            )

        # --- Cascata UF -> Municipio -> Escola (autocomplete) ---
        from dashboard.helpers.school_lookup import (
            get_ufs, get_cities, get_schools,
            format_school_option, parse_inep_from_option,
        )
        rc_uf, rc_mun, rc_dep = st.columns(3)
        with rc_uf:
            radar_uf = st.selectbox("UF:", [""] + get_ufs(), key="radar_uf")
        with rc_mun:
            _radar_cities = get_cities(radar_uf) if radar_uf else []
            radar_mun = st.selectbox("Municipio:", [""] + _radar_cities, key="radar_mun")
        with rc_dep:
            radar_dep = st.selectbox(
                "Dependencia",
                ["", "Privada", "Estadual", "Municipal", "Federal"],
                key="radar_dep",
            )

        # Escola (so aparece quando modo=Uma escola E UF+Mun preenchidos)
        radar_inep: str = ""
        radar_escola_nome: str = ""
        if radar_mode.startswith("Uma escola"):
            if radar_uf and radar_mun:
                _radar_schools = get_schools(radar_uf, radar_mun)
                _radar_opts = [""] + [format_school_option(n, i) for n, i in _radar_schools]
                radar_escola_sel = st.selectbox(
                    f"Escola ({len(_radar_schools)} encontradas):",
                    _radar_opts,
                    key="radar_escola",
                )
                radar_inep = parse_inep_from_option(radar_escola_sel) or ""
                # Extrair nome da escola do selectbox (formato "NOME (INEP: X)")
                if radar_escola_sel and " (INEP:" in radar_escola_sel:
                    radar_escola_nome = radar_escola_sel.split(" (INEP:")[0].strip()
                elif radar_escola_sel:
                    radar_escola_nome = radar_escola_sel
            else:
                st.info("Selecione **UF** e **Municipio** acima para ver as escolas disponiveis.")

        rc6, rc7 = st.columns(2)
        with rc7:
            _REF_LABELS = {
                "municipio": "🏙️ Municipio (mesma cidade)",
                "estado": "🗺️ Estado (mesma UF)",
                "brasil": "🌎 Brasil (media nacional)",
                "mesma_dependencia": "🏫 Mesma dependencia",
            }
            radar_refs_display = st.multiselect(
                "Comparar com",
                list(_REF_LABELS.values()),
                default=[_REF_LABELS["municipio"], _REF_LABELS["estado"]],
                key="radar_refs",
            )
            _ref_keys = list(_REF_LABELS.keys())
            _ref_vals = list(_REF_LABELS.values())
            radar_refs = [_ref_keys[_ref_vals.index(d)] for d in radar_refs_display]

        # ----- Execute -----
        if st.button("🎯 Gerar radar", type="primary", use_container_width=True, key="btn_radar"):
            # Determine which metrics to fetch
            show_areas = "areas" in radar_chart_type or "Ambos" in radar_chart_type
            show_comps = "competencias" in radar_chart_type or "Ambos" in radar_chart_type
            metricas = []
            if show_areas:
                metricas.extend(_RADAR_AREAS)
            if show_comps:
                metricas.extend(_RADAR_COMPS)

            # Build alvo filters
            alvo_filtros: dict = {}
            escala = "custom"
            if radar_mode.startswith("Uma escola"):
                escala = "escola"
                if radar_inep:
                    alvo_filtros["inep"] = radar_inep
                else:
                    # NAO usar st.stop() aqui: mataria a aba "Explorador"
                    # (Streamlit renderiza todas as abas no mesmo run).
                    alert_banner("Selecione uma escola na lista acima.", "error")
                    escala = None
            if radar_mun.strip():
                alvo_filtros["municipio"] = radar_mun.strip()
            if radar_uf.strip():
                alvo_filtros["uf"] = radar_uf.strip().upper()
            if radar_dep:
                alvo_filtros["dependencia"] = radar_dep

            if not radar_refs:
                alert_banner("Selecione pelo menos uma referencia em 'Comparar com'.", "error")
                escala = None

            result = {}
            if escala:
                with st.spinner("Buscando dados..."):
                    result_raw = _handle_analisar_dados_analytics({
                        "operacao": "comparacao",
                        "alvo": {"escala": escala, "filtros": alvo_filtros},
                        "metricas": metricas,
                        "comparar_com": radar_refs,
                        "agregacao": "media",
                    })
                    result = json.loads(result_raw)

            if not result:
                pass  # falta selecao — banner ja exibido acima
            elif "erro" in result:
                alert_banner(f"Erro: {result['erro']}", "error")
                if result.get("opcoes"):
                    st.info(f"Voce quis dizer: {', '.join(result['opcoes'][:5])}")
            else:
                # Warnings
                for w in result.get("warnings") or []:
                    alert_banner(w, "warning")

                resultado = result.get("resultado", {})
                alvo_vals = resultado.get("alvo", {})
                comparacoes = resultado.get("comparacoes", [])

                # Alvo label — preferir nome da escola, fallback para INEP
                if escala == "escola" and radar_escola_nome:
                    alvo_label = radar_escola_nome
                elif escala == "escola" and alvo_filtros.get("inep"):
                    alvo_label = f"INEP {alvo_filtros['inep']}"
                else:
                    parts = []
                    if alvo_filtros.get("municipio"):
                        parts.append(alvo_filtros["municipio"])
                    if alvo_filtros.get("uf"):
                        parts.append(alvo_filtros["uf"])
                    if alvo_filtros.get("dependencia"):
                        parts.append(alvo_filtros["dependencia"])
                    alvo_label = " · ".join(parts) if parts else "Alvo"

                def _make_radar(metrics_list, labels_map, title):
                    """Build a Plotly radar chart for the given metrics."""
                    labels = [labels_map.get(m, m) for m in metrics_list]

                    # Check if alvo has data
                    alvo_values = [alvo_vals.get(m) for m in metrics_list]
                    has_alvo = any(v is not None for v in alvo_values)
                    if not has_alvo and not comparacoes:
                        st.info(f"Sem dados para '{title}'.")
                        return

                    fig = go.Figure()

                    # Alvo trace
                    if has_alvo:
                        r_vals = [float(v) if v is not None else 0 for v in alvo_values]
                        # Close the polygon
                        r_vals_closed = r_vals + [r_vals[0]]
                        labels_closed = labels + [labels[0]]
                        fig.add_trace(go.Scatterpolar(
                            r=r_vals_closed,
                            theta=labels_closed,
                            fill="toself",
                            name=alvo_label,
                            line_color=_TRACE_COLORS[0],
                            fillcolor=_TRACE_COLORS[0].replace(")", ", 0.15)").replace("rgb", "rgba")
                                if _TRACE_COLORS[0].startswith("rgb") else None,
                            opacity=0.85,
                        ))

                    # Reference traces
                    for i, cmp in enumerate(comparacoes):
                        cmp_vals = cmp.get("valores", {})
                        r_vals = [float(cmp_vals.get(m) or 0) for m in metrics_list]
                        r_vals_closed = r_vals + [r_vals[0]]
                        labels_closed = labels + [labels[0]]
                        cmp_label = f"{cmp.get('escopo', '?').replace('_', ' ').title()} ({cmp.get('n_escolas', '?')} esc.)"
                        color = _TRACE_COLORS[(i + 1) % len(_TRACE_COLORS)]
                        fig.add_trace(go.Scatterpolar(
                            r=r_vals_closed,
                            theta=labels_closed,
                            fill="toself",
                            name=cmp_label,
                            line_color=color,
                            fillcolor=color.replace(")", ", 0.08)").replace("rgb", "rgba")
                                if color.startswith("rgb") else None,
                            opacity=0.7,
                        ))

                    # Compute axis range
                    all_vals = []
                    for v in alvo_values:
                        if v is not None:
                            all_vals.append(float(v))
                    for cmp in comparacoes:
                        for m in metrics_list:
                            v = cmp.get("valores", {}).get(m)
                            if v is not None:
                                all_vals.append(float(v))
                    max_val = max(all_vals) * 1.1 if all_vals else 800

                    fig.update_layout(
                        polar=dict(
                            radialaxis=dict(
                                visible=True,
                                range=[0, max_val],
                                tickfont=dict(size=10),
                            ),
                            angularaxis=dict(tickfont=dict(size=11)),
                        ),
                        showlegend=True,
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=-0.25,
                            xanchor="center",
                            x=0.5,
                        ),
                        height=450,
                        margin=dict(l=60, r=60, t=40, b=80),
                        title=dict(text=title, font=dict(size=14)),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # Render radar(s)
                if show_areas and show_comps:
                    col_a, col_c = st.columns(2)
                    with col_a:
                        _make_radar(_RADAR_AREAS, _AREA_LABELS, "5 Areas do ENEM")
                    with col_c:
                        _make_radar(_RADAR_COMPS, _COMP_LABELS, "5 Competencias da Redacao")
                elif show_areas:
                    _make_radar(_RADAR_AREAS, _AREA_LABELS, "5 Areas do ENEM")
                elif show_comps:
                    _make_radar(_RADAR_COMPS, _COMP_LABELS, "5 Competencias da Redacao")

                # Tabela de valores
                with st.expander("Tabela de valores"):
                    all_metrics = (_RADAR_AREAS if show_areas else []) + (_RADAR_COMPS if show_comps else [])
                    all_labels = {**_AREA_LABELS, **_COMP_LABELS}
                    rows_tbl = [{"Escopo": f"📍 {alvo_label}"}]
                    for m in all_metrics:
                        v = alvo_vals.get(m)
                        rows_tbl[0][all_labels.get(m, m)] = round(float(v), 2) if v is not None else None
                    for cmp in comparacoes:
                        row = {"Escopo": f"🔄 {cmp.get('escopo', '?').title()} ({cmp.get('n_escolas')} esc.)"}
                        for m in all_metrics:
                            v = cmp.get("valores", {}).get(m)
                            row[all_labels.get(m, m)] = round(float(v), 2) if v is not None else None
                        rows_tbl.append(row)
                    st.dataframe(pd.DataFrame(rows_tbl), use_container_width=True, hide_index=True)


    # ---------------------------------------------------------------------------
    # TAB EXPLORADOR LIVRE
    # ---------------------------------------------------------------------------
    with tab_explorer:
        st.caption(
            "Consulta livre ao school_analytics via analisar_dados_analytics. "
            "Mesma tool que o IAlex usa — os resultados aqui sao identicos aos "
            "retornados pelo agente no WhatsApp."
        )

        # Form de operacao
        _OP_LABELS = {
            "valor_unico": "📊 Valor unico (media/soma de um grupo)",
            "ranking": "🏆 Ranking (top N escolas)",
            "comparacao": "🔄 Comparacao (alvo vs referencias)",
            "serie_temporal": "📈 Serie temporal (evolucao por ano)",
            "distribuicao": "📋 Distribuicao (por grupo)",
        }
        _OP_ORDER = ["comparacao", "ranking", "valor_unico", "serie_temporal", "distribuicao"]

        ec1, ec2 = st.columns([1, 1])
        with ec1:
            exp_op_display = st.selectbox(
                "O que voce quer ver?",
                [_OP_LABELS.get(o, o) for o in _OP_ORDER],
            )
            exp_op = _OP_ORDER[[_OP_LABELS.get(o, o) for o in _OP_ORDER].index(exp_op_display)]
        with ec2:
            exp_agg = st.selectbox(
                "Agregacao",
                sorted(list(ALLOWED_AGGREGATIONS)),
                index=sorted(list(ALLOWED_AGGREGATIONS)).index("media"),
                help="Como combinar os valores das escolas: media, mediana, soma, contagem, etc.",
            )

        # Filtros do alvo (cascata UF -> Mun -> Escola com autocomplete)
        from dashboard.helpers.school_lookup import (
            get_ufs as _exp_get_ufs, get_cities as _exp_get_cities,
            get_schools as _exp_get_schools,
            format_school_option as _exp_fmt, parse_inep_from_option as _exp_parse,
        )
        section_header("Filtros do alvo", "search")
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            _ESCALA_LABELS = {
                "escola": "Escola (individual)",
                "municipio": "Municipio",
                "estado": "Estado",
                "brasil": "Brasil",
                "custom": "Personalizado (filtros livres)",
            }
            _escala_keys = list(_ESCALA_LABELS.keys())
            _escala_display = list(_ESCALA_LABELS.values())
            _escala_sel = st.selectbox(
                "Escala",
                _escala_display,
                index=4,
            )
            alvo_escala = _escala_keys[_escala_display.index(_escala_sel)]
        with fc2:
            alvo_uf = st.selectbox("UF:", [""] + _exp_get_ufs(), key="exp_uf")
        with fc3:
            _exp_cities = _exp_get_cities(alvo_uf) if alvo_uf else []
            alvo_mun = st.selectbox("Municipio:", [""] + _exp_cities, key="exp_mun")

        fc4, fc5, fc6 = st.columns(3)
        with fc4:
            alvo_dep = st.selectbox(
                "Dependencia",
                ["", "Privada", "Estadual", "Municipal", "Federal"],
            )
        with fc5:
            alvo_potencial = st.selectbox(
                "Potencial",
                ["", "Alto", "Medio", "Baixo"],
            )
        with fc6:
            alvo_inep_exp: str = ""
            if alvo_escala == "escola" and alvo_uf and alvo_mun:
                _exp_schools = _exp_get_schools(alvo_uf, alvo_mun)
                _exp_opts = [""] + [_exp_fmt(n, i) for n, i in _exp_schools]
                _exp_sel = st.selectbox(
                    f"Escola ({len(_exp_schools)}):", _exp_opts, key="exp_escola",
                )
                alvo_inep_exp = _exp_parse(_exp_sel) or ""
            elif alvo_escala == "escola":
                st.caption("Selecione UF e Municipio para ver escolas.")
            else:
                st.caption("(escola so para escala=escola)")

        # Metricas
        section_header("Metricas", "straighten")
        st.caption(
            "Apenas campos da whitelist sao aceitos. "
            f"Total disponivel: {len(ALLOWED_ANALYTICS_METRICS)} campos (enem_*, peer_*, socio_*, pnt_* safe)."
        )
        # Categorias rapidas
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            preset = st.selectbox(
                "Preset rapido",
                [
                    "(custom)",
                    "enem_media_geral",
                    "enem_media_mt (matematica)",
                    "enem_redacao_comp*_media (competencias redacao)",
                    "peer_media_geral_2020..2025 (serie temporal)",
                    "socio_renda_idx_media_2025",
                    "pnt_pct_pais_superior",
                ],
            )
        with mc2:
            exp_modo_redacao = st.selectbox(
                "Modo redacao",
                ["com", "sem", "ambos"],
                help="'com'=enem_media_geral oficial. 'sem'=enem_media_geral_sem_redacao (4 areas). 'ambos'=lado a lado.",
            )
        with mc3:
            exp_top_n = st.number_input("Top N", min_value=5, max_value=100, value=10, step=5)

        # Resolver preset -> metricas
        metricas_preset = {
            "(custom)": [],
            "enem_media_geral": ["enem_media_geral"],
            "enem_media_mt (matematica)": ["enem_media_mt"],
            "enem_redacao_comp*_media (competencias redacao)": [
                f"enem_redacao_comp{i}_media" for i in range(1, 6)
            ],
            "peer_media_geral_2020..2025 (serie temporal)": [
                f"peer_media_geral_{y}" for y in range(2020, 2026)
            ],
            "socio_renda_idx_media_2025": ["socio_renda_idx_media_2025"],
            "pnt_pct_pais_superior": ["pnt_pct_pais_superior"],
        }

        metricas_custom = st.text_area(
            "Metricas custom (uma por linha, OU deixe vazio para usar o preset)",
            placeholder="enem_media_geral\npeer_media_geral_2025\nenem_gap_vs_peer_2025",
            height=100,
        )
        metricas_final = [m.strip() for m in metricas_custom.split("\n") if m.strip()] if metricas_custom.strip() else metricas_preset.get(preset, [])

        # Grouping / comparison
        if exp_op in ("comparacao", "distribuicao"):
            ec3, ec4 = st.columns(2)
            with ec3:
                if exp_op == "distribuicao":
                    exp_agrupar = st.selectbox(
                        "Agrupar por",
                        [""] + sorted(list(ALLOWED_GROUPINGS)),
                        help="Como segmentar os dados (ex: por municipio, por dependencia).",
                    )
                else:
                    exp_agrupar = None
            with ec4:
                if exp_op == "comparacao":
                    _CMP_LABELS = {
                        "brasil": "🌎 Brasil (media nacional)",
                        "estado": "🗺️ Estado (mesma UF)",
                        "municipio": "🏙️ Municipio (mesma cidade)",
                        "mesma_dependencia": "🏫 Mesma dependencia",
                        "mesmo_porte": "📏 Mesmo porte",
                        "mesmo_nivel_tecnologico": "💻 Mesmo nivel tecnologico",
                    }
                    _cmp_options = list(_CMP_LABELS.values())
                    _cmp_keys = list(_CMP_LABELS.keys())
                    exp_comparar_display = st.multiselect(
                        "Comparar com (selecione 1 ou mais)",
                        _cmp_options,
                        default=[_cmp_options[0], _cmp_options[1]],  # brasil + estado
                        help="Referencias para comparacao. Ex: Brasil = media nacional, Estado = mesma UF.",
                    )
                    exp_comparar = [_cmp_keys[_cmp_options.index(d)] for d in exp_comparar_display]
                else:
                    exp_comparar = None
        else:
            exp_agrupar = None
            exp_comparar = None

        # ----- Label mapping for human-readable metric names -----
        _METRIC_LABELS = {
            "enem_media_geral": "Media Geral ENEM",
            "enem_media_geral_sem_redacao": "Media ENEM (sem Redacao)",
            "enem_media_mt": "Matematica",
            "enem_media_cn": "Ciencias da Natureza",
            "enem_media_ch": "Ciencias Humanas",
            "enem_media_lc": "Linguagens e Codigos",
            "enem_redacao_media": "Redacao",
            "enem_gap_vs_peer_2024": "Gap vs Peer 2024",
            "enem_gap_vs_peer_2025": "Gap vs Peer 2025",
            "enem_percentil_uf_dep": "Percentil UF×Dep",
            "enem_presentes": "Presentes ENEM",
            "enem_redacao_comp1_media": "Redacao Comp.1",
            "enem_redacao_comp2_media": "Redacao Comp.2",
            "enem_redacao_comp3_media": "Redacao Comp.3",
            "enem_redacao_comp4_media": "Redacao Comp.4",
            "enem_redacao_comp5_media": "Redacao Comp.5",
            "socio_renda_idx_media_2024": "Indice Renda (mun) 2024",
            "socio_renda_idx_media_2025": "Indice Renda (mun) 2025",
            "pnt_pct_pais_superior": "% Pais c/ Superior",
        }

        def _label(key: str) -> str:
            """Return a human-friendly metric label."""
            if key in _METRIC_LABELS:
                return _METRIC_LABELS[key]
            # Auto-generate readable label from snake_case
            return key.replace("_", " ").replace("enem ", "ENEM ").replace("peer ", "Peer ").title()

        def _fmt(val) -> str:
            """Format a numeric value for display."""
            if val is None:
                return "—"
            try:
                f = float(val)
                if abs(f) < 0.01 and f != 0:
                    return f"{f:.4f}"
                return f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (ValueError, TypeError):
                return str(val)

        # ----- Validation & execution -----
        if st.button("🧪 Executar query", type="primary", use_container_width=True):
            if not metricas_final:
                alert_banner("Escolha pelo menos uma metrica (preset ou custom).", "error")
            else:
                alvo_filtros = {}
                if alvo_uf:
                    alvo_filtros["uf"] = alvo_uf.strip().upper()
                if alvo_mun:
                    alvo_filtros["municipio"] = alvo_mun.strip()
                if alvo_dep:
                    alvo_filtros["dependencia"] = alvo_dep
                if alvo_potencial:
                    alvo_filtros["potencial"] = alvo_potencial
                if alvo_inep_exp:
                    alvo_filtros["inep"] = alvo_inep_exp

                # Validacao: warn if comparacao/ranking without filters
                if not alvo_filtros and exp_op in ("comparacao", "ranking"):
                    alert_banner(
                        "**Atenção**: sem nenhum filtro (UF, Municipio, Dependencia), "
                        "o alvo sera o Brasil inteiro e os resultados podem ser pouco "
                        "uteis. Aplique pelo menos um filtro para refinar a consulta.",
                        "warning",
                    )

                # Validacao: comparacao sem comparar_com.
                # `_pode_rodar` em vez de st.stop(): o helper roda dentro de uma
                # aba e o stop mataria o resto da pagina.
                _pode_rodar = True
                if exp_op == "comparacao" and not exp_comparar:
                    alert_banner(
                        "Selecione pelo menos uma opcao em **Comparar com** "
                        "(ex: municipio, estado, brasil).",
                        "error",
                    )
                    _pode_rodar = False

                params = {
                    "operacao": exp_op,
                    "alvo": {"escala": alvo_escala, "filtros": alvo_filtros},
                    "metricas": metricas_final,
                    "agregacao": exp_agg,
                    "modo_redacao": exp_modo_redacao,
                    "top_n": int(exp_top_n),
                }
                if exp_agrupar:
                    params["agrupar_por"] = exp_agrupar
                if exp_comparar:
                    params["comparar_com"] = exp_comparar

                result_raw = "{}"
                result = {}
                if _pode_rodar:
                    with st.spinner("Executando analisar_dados_analytics..."):
                        result_raw = _handle_analisar_dados_analytics(params)
                    result = json.loads(result_raw)

                st.markdown("")

                if not result:
                    pass  # faltou selecao — banner ja exibido acima
                elif "erro" in result:
                    alert_banner(f"Erro: {result['erro']}", "error")
                    if "metricas_rejeitadas" in result:
                        st.caption(f"Rejeitadas: {result['metricas_rejeitadas']}")
                    if "disponivel" in result:
                        with st.expander("Ver primeiras 30 metricas disponiveis"):
                            st.write(result["disponivel"])
                else:
                    # Warnings
                    warnings = result.get("warnings") or []
                    for w in warnings:
                        alert_banner(w, "warning")

                    # Disclaimers
                    if result.get("disclaimer_socio"):
                        alert_banner(
                            f"**Dado socio_*:** {result['disclaimer_socio']}",
                            "info",
                        )
                    if result.get("disclaimer_pnt"):
                        alert_banner(
                            f"**Dado pnt_*:** {result['disclaimer_pnt']}",
                            "info",
                        )

                    # ------- RESULTADOS POR OPERACAO -------
                    section_header("Resultado", "bar_chart")
                    resultado = result.get("resultado")

                    # === RANKING ===
                    if exp_op == "ranking" and isinstance(resultado, list):
                        n_total = result.get("n_consideradas", len(resultado))
                        st.caption(
                            f"Top {len(resultado)} de {n_total:,} escolas consideradas "
                            f"(agregacao: {exp_agg})"
                        )
                        df_r = pd.DataFrame(resultado)
                        # Rename metric columns for display
                        rename_map = {m: _label(m) for m in metricas_final if m in df_r.columns}
                        df_r = df_r.rename(columns=rename_map)
                        st.dataframe(df_r, use_container_width=True, hide_index=True)

                    # === DISTRIBUICAO ===
                    elif exp_op == "distribuicao" and isinstance(resultado, list):
                        df_r = pd.DataFrame(resultado)
                        rename_map = {m: _label(m) for m in metricas_final if m in df_r.columns}
                        df_r = df_r.rename(columns=rename_map)
                        st.dataframe(df_r, use_container_width=True, hide_index=True)
                        # Bar chart for the first metric
                        if len(resultado) > 1 and metricas_final:
                            chart_col = _label(metricas_final[0])
                            group_col = exp_agrupar or (df_r.columns[0] if len(df_r.columns) > 0 else None)
                            if chart_col in df_r.columns and group_col in df_r.columns:
                                try:
                                    st.bar_chart(
                                        df_r.set_index(group_col)[chart_col],
                                        use_container_width=True,
                                    )
                                except Exception:
                                    pass

                    # === COMPARACAO ===
                    elif exp_op == "comparacao" and isinstance(resultado, dict):
                        alvo_vals = resultado.get("alvo", {})
                        comparacoes = resultado.get("comparacoes", [])

                        # Scope description
                        scope_parts = []
                        if alvo_filtros.get("municipio"):
                            scope_parts.append(alvo_filtros["municipio"])
                        if alvo_filtros.get("uf"):
                            scope_parts.append(alvo_filtros["uf"])
                        if alvo_filtros.get("dependencia"):
                            scope_parts.append(alvo_filtros["dependencia"])
                        if alvo_filtros.get("nome"):
                            scope_parts.append(alvo_filtros["nome"])
                        alvo_desc = " · ".join(scope_parts) if scope_parts else "Brasil (sem filtros)"
                        n_alvo = result.get("n_escolas_agregadas", "?")

                        # Build comparison rows
                        rows_comp = []
                        row_alvo = {"Escopo": f"📍 Alvo: {alvo_desc}"}
                        for m in metricas_final:
                            row_alvo[_label(m)] = _fmt(alvo_vals.get(m))
                        rows_comp.append(row_alvo)

                        for cmp in comparacoes:
                            row_cmp = {
                                "Escopo": f"🔄 {cmp.get('escopo', '?').replace('_', ' ').title()} ({cmp.get('n_escolas', '?')} escolas)",
                            }
                            for m in metricas_final:
                                cmp_val = cmp.get("valores", {}).get(m)
                                alvo_val = alvo_vals.get(m)
                                formatted = _fmt(cmp_val)
                                # Show delta if both are numeric
                                if cmp_val is not None and alvo_val is not None:
                                    try:
                                        delta = float(alvo_val) - float(cmp_val)
                                        if abs(delta) > 0.01:
                                            sign = "+" if delta > 0 else ""
                                            formatted += f" (Δ {sign}{delta:,.2f})"
                                    except (ValueError, TypeError):
                                        pass
                                row_cmp[_label(m)] = formatted
                            rows_comp.append(row_cmp)

                        df_cmp = pd.DataFrame(rows_comp)
                        st.dataframe(
                            df_cmp,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Escopo": st.column_config.TextColumn("Escopo", width="large"),
                            },
                        )

                        # Metric cards for single-metric comparisons
                        if len(metricas_final) == 1:
                            m = metricas_final[0]
                            mc1, mc2 = st.columns(2)
                            with mc1:
                                metric_card(
                                    f"Alvo: {alvo_desc}",
                                    _fmt(alvo_vals.get(m)),
                                    COLORS["primary"],
                                    icon="target",
                                )
                            for i, cmp in enumerate(comparacoes):
                                cmp_val = cmp.get("valores", {}).get(m)
                                with mc2:
                                    metric_card(
                                        f"{cmp.get('escopo', '?').title()} ({cmp.get('n_escolas')} esc.)",
                                        _fmt(cmp_val),
                                        COLORS["info"],
                                        icon="compare_arrows",
                                    )

                    # === VALOR UNICO ===
                    elif exp_op == "valor_unico" and isinstance(resultado, dict):
                        n_agg = result.get("n_escolas_agregadas")
                        if n_agg:
                            st.caption(f"Agregado sobre {n_agg:,} escolas (agregacao: {exp_agg})")
                        cols = st.columns(min(len(metricas_final), 4))
                        for i, m in enumerate(metricas_final):
                            with cols[i % len(cols)]:
                                metric_card(
                                    _label(m),
                                    _fmt(resultado.get(m)),
                                    COLORS["primary"] if i % 2 == 0 else COLORS["info"],
                                    icon="analytics",
                                )

                    # === SERIE TEMPORAL ===
                    elif exp_op == "serie_temporal" and isinstance(resultado, dict):
                        # resultado has {metric_name: value_or_list}
                        # Build a chart from year-keyed metrics
                        chart_data = {}
                        for m in metricas_final:
                            val = resultado.get(m)
                            if val is not None:
                                # Extract year from field name if possible
                                year = None
                                for part in m.split("_"):
                                    if part.isdigit() and 2015 <= int(part) <= 2030:
                                        year = int(part)
                                if year:
                                    label = _label(m.rsplit("_", 1)[0])
                                    chart_data.setdefault(label, {})[year] = val
                                else:
                                    chart_data.setdefault(_label(m), {0: val})

                        if chart_data:
                            # Build DataFrame for line chart
                            all_years = sorted(
                                {yr for series in chart_data.values() for yr in series}
                            )
                            chart_rows = []
                            for yr in all_years:
                                row = {"Ano": yr}
                                for label, series in chart_data.items():
                                    row[label] = series.get(yr)
                                chart_rows.append(row)
                            df_chart = pd.DataFrame(chart_rows)
                            if "Ano" in df_chart.columns and len(df_chart) > 1:
                                st.line_chart(
                                    df_chart.set_index("Ano"),
                                    use_container_width=True,
                                )
                            st.dataframe(df_chart, use_container_width=True, hide_index=True)
                        else:
                            st.info("Nenhum dado temporal encontrado para os filtros aplicados.")

                    # === FALLBACK ===
                    else:
                        if isinstance(resultado, dict):
                            # Try to show as metric cards
                            cols = st.columns(min(len(resultado), 4)) if resultado else [st]
                            for i, (k, v) in enumerate(resultado.items()):
                                with cols[i % len(cols)]:
                                    metric_card(
                                        _label(k) if isinstance(k, str) else str(k),
                                        _fmt(v),
                                        COLORS["primary"],
                                        icon="analytics",
                                    )
                        else:
                            st.json(resultado)

                    with st.expander("JSON completo (debug)", expanded=False):
                        st.json(result)

