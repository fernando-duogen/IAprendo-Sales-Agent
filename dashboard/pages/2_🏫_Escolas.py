"""Pagina 5 - Gestao de Escolas: tabela com edicao inline, detalhe Material
Design e aba Redes (escolas agrupadas por CNPJ mantenedora)."""
import streamlit as st
import pandas as pd
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, avatar, breadcrumb, timeline_item, COLORS, STATUS_COLORS,
    score_color,
)
from dashboard.helpers.table_select import (
    reset_if_rows_changed, selected_positions,
)
from dashboard.helpers.school_lookup import invalidate_crm_schools
from utils.fit_score import calcular_fit_score, fit_emoji, fit_cor_hex
from utils.rede_name import resolver_nome_rede, set_rede_override, has_rede_overrides_table

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

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

# Ano do ENEM vigente nos analytics — fonte unica (evita rotulo defasado
# quando os dados virarem 2026+). Fallback defensivo se o import falhar.
try:
    from agent.tools.enem_tools import ENEM_VINTAGE
except Exception:
    ENEM_VINTAGE = 2025

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "escola_detail_id" not in st.session_state:
    st.session_state.escola_detail_id = None
# Deep-link opcional: ?escola=<id> na URL abre a ficha direto (ex: link externo).
# A lista abre a ficha por SELECAO DE LINHA (mesma sessao), nao por este param.
_qp_escola = st.query_params.get("escola")
if _qp_escola:
    st.session_state.escola_detail_id = _qp_escola
    try:
        del st.query_params["escola"]
    except Exception:
        pass
if "escola_msg" not in st.session_state:
    st.session_state.escola_msg = None


# Confirmacoes pendentes NAO podem sobreviver a troca de contexto: senao, ao
# voltar para a mesma escola (ou reselecionar), o banner vermelho de exclusao
# reaparece ja aberto, sem o usuario ter pedido — e a protecao de 2 cliques
# vira 1 clique.
_CONFIRM_KEYS = ("confirm_delete", "confirm_sel_delete",
                 "confirm_single_delete", "confirm_bulk_delete")


def _clear_confirms() -> None:
    for _k in _CONFIRM_KEYS:
        st.session_state.pop(_k, None)


def go_to_detail(company_id: str) -> None:
    st.session_state.escola_detail_id = company_id
    _clear_confirms()


def go_to_list() -> None:
    st.session_state.escola_detail_id = None
    _clear_confirms()


# ---------------------------------------------------------------------------
# Performance ENEM — fetch separado em school_analytics (R6 do plano)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)
def _fetch_analytics_by_inep_list(inep_list: tuple) -> dict:
    """Batch fetch de school_analytics para uma lista de INEPs.
    Retorna dict {inep: row}. Cached 5 min. Falha silenciosa -> {}.
    Usado pela coluna Potencial na tabela principal.
    """
    if not inep_list:
        return {}
    try:
        rows = db.fetch_in_chunks(
            "school_analytics",
            "inep_code,enem_amostra_confiavel,enem_potencial_melhoria,"
            "peer_trajetoria_6y,enem_gap_vs_peer_2025,enem_dependencia,"
            "enem_media_geral,enem_media_geral_sem_redacao,enem_area_mais_fraca,"
            "enem_presentes,peer_delta_media_geral_2022_2025",
            "inep_code", list(inep_list),
        )
        return {str(row["inep_code"]): row for row in rows}
    except Exception as e:
        return {}


@st.cache_data(ttl=300)
def _fetch_analytics_single(inep_code: str) -> dict | None:
    """Fetch completo de school_analytics para 1 escola. Falha silenciosa."""
    if not inep_code:
        return None
    try:
        r = db.client.table("school_analytics").select("*").eq(
            "inep_code", str(inep_code).strip()
        ).limit(1).execute()
        if r.data:
            return r.data[0]
    except Exception:
        pass
    return None


def _potencial_badge(row: dict | None) -> str:
    """Retorna badge HTML para coluna Potencial. '' se sem dado."""
    if not row or not row.get("enem_amostra_confiavel"):
        return "—"
    pot = row.get("enem_potencial_melhoria")
    if pot == "Alto":
        return "🔥 Alto"
    if pot == "Medio" or pot == "Médio":
        return "🟡 Medio"
    if pot == "Baixo":
        return "🟢 Baixo"
    return "—"


@st.cache_data(ttl=300)
def _fetch_censo_yearly_by_inep(inep: str) -> list:
    """Busca serie historica Censo 2020-2025 de uma escola. Cache 5min.
    Retorna lista ordenada por vintage. Falha silenciosa -> []."""
    if not inep:
        return []
    try:
        r = db.client.table("school_censo_yearly").select(
            "vintage_censo,name,qt_mat_bas,qt_mat_inf,qt_mat_fund,"
            "qt_mat_fund_ai,qt_mat_fund_af,qt_mat_med,qt_mat_eja,qt_mat_prof,"
            "qt_doc_bas,qt_doc_fund,qt_doc_med,"
            "in_internet,in_internet_alunos,in_internet_aprendizagem,"
            "in_laboratorio_informatica,qt_desktop_aluno,"
            "qt_comp_portatil_aluno,qt_tablet_aluno,"
            "in_biblioteca,in_quadra_esportes,in_laboratorio_ciencias,"
            "in_alimentacao"
        ).eq("inep_code", str(inep).strip()).order("vintage_censo").execute()
        return r.data or []
    except Exception:
        return []


def _render_performance_tab(company: dict, company_id: str) -> None:
    """Renderiza a aba Performance ENEM do detalhe de escola.

    - Fail-safe: se school_analytics indisponivel, mostra banner
    - Respeita regra #1 (amostra_confiavel): nao mostra metricas
      individuais quando False
    - Peer group sempre com rotulo "suas concorrentes"
    - Socio sempre com rotulo "perfil do municipio"
    """
    from utils.fit_score import fit_cor_hex
    try:
        import plotly.graph_objects as go
    except Exception:
        alert_banner("plotly nao instalado.", "error")
        return

    inep = company.get("inep_code")
    if not inep:
        alert_banner("Escola sem codigo INEP — nao ha como buscar dados ENEM.", "info")
        return

    row = _fetch_analytics_single(str(inep))
    if not row:
        alert_banner(
            f"Escola sem dados ENEM no school_analytics (provavelmente Catalogo INEP, "
            f"escola sem Ensino Medio, ou nao participou do ENEM {ENEM_VINTAGE}).",
            "info",
        )
        return

    amostra_ok = row.get("enem_amostra_confiavel") is True
    potencial = row.get("enem_potencial_melhoria")

    # Safra REAL desta escola. Nem toda linha de school_analytics esta em 2025;
    # ler colunas *_2025 fixas fazia as escolas de 2024 perderem gap/peer/socio.
    try:
        from agent.tools.enem_tools import campo_por_safra as _safra, trajetoria_peer as _traj_peer
    except Exception:  # pragma: no cover
        def _safra(r, base, anos=(2025, 2024)):
            return r.get(f"{base}_2025")

        def _traj_peer(r):
            return r.get("peer_trajetoria_6y")
    try:
        _ano_row = int(row.get("enem_ano") or ENEM_VINTAGE)
    except (TypeError, ValueError):
        _ano_row = ENEM_VINTAGE

    # --- Banner de prioridade P1/P2/P3 via handler (fonte unica da verdade) ---
    try:
        from agent.tools.enem_tools import _classificar_prioridade, _aviso_p3
        # Merge company fields pro helper funcionar
        row_for_helper = dict(row)
        for k in ("city", "state", "admin_dependency"):
            if company.get(k) and k not in row_for_helper:
                row_for_helper[k] = company[k]
        prio = _classificar_prioridade(row_for_helper)
        aviso = _aviso_p3(prio)
    except Exception:
        prio = None
        aviso = None

    if prio == "P1":
        alert_banner(
            f"🔥 LEAD P1 — potencial Alto + peer Subindo. Pitch ofensivo recomendado.",
            "success",
        )
    elif prio == "P2":
        alert_banner(
            f"⚡ LEAD P2 — privada com gap negativo vs peer. Oportunidade clara.",
            "info",
        )
    elif prio == "P3":
        alert_banner(
            f"⚠️ LEAD P3 — URGENCIA DEFENSIVA. {aviso or 'Revise tom do email antes de aprovar.'}",
            "warning",
        )

    if not amostra_ok:
        alert_banner(
            "Amostra ENEM NAO confiavel (poucos presentes, dados estatisticamente "
            "fracos). Metricas individuais desta escola NAO serao exibidas (regra "
            "etica #1). Voce ainda tem dados do peer_group e do contexto municipal.",
            "warning",
        )

    st.markdown("")

    # --- Metricas principais (so se amostra confiavel) ---
    if amostra_ok and row.get("enem_media_geral") is not None:
        # Rotulo usa a safra REAL da linha (nem toda escola esta em 2025)
        section_header(f"Performance ENEM {_ano_row}", "trending_up")
        media_com = float(row.get("enem_media_geral") or 0)
        media_sem = row.get("enem_media_geral_sem_redacao")
        gap = _safra(row, "enem_gap_vs_peer")
        presentes = row.get("enem_presentes") or 0

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            metric_card("Media com redacao", f"{media_com:.1f}",
                        COLORS["primary"], icon="school")
        with mc2:
            if media_sem is not None:
                # Delta > 0: redacao eleva a media (media_com > media_sem)
                # Delta < 0: redacao baixa a media (raro mas possivel)
                delta = media_com - float(media_sem)
                direction = "puxa p/ cima" if delta > 0 else "puxa p/ baixo" if delta < 0 else "neutra"
                metric_card(
                    "Media sem redacao",
                    f"{float(media_sem):.1f}",
                    COLORS["info"],
                    icon="functions",
                )
                st.caption(f"Redacao {direction}: Δ={delta:+.1f}")
        with mc3:
            if gap is not None:
                gap_f = float(gap)
                metric_card(
                    f"Gap vs peer {_ano_row}",
                    f"{gap_f:+.1f}",
                    COLORS["success"] if gap_f > 0 else COLORS["error"],
                    icon="compare_arrows",
                )
        with mc4:
            metric_card(
                "Presentes",
                f"{presentes}",
                COLORS["secondary"],
                icon="how_to_reg",
            )

        # Potencial badge
        st.markdown(f"**Potencial de melhoria:** `{potencial or 'N/A'}`")

        # --- Area mais fraca ---
        area_fraca = row.get("enem_area_mais_fraca")
        if area_fraca:
            alert_banner(
                f"**Area mais fraca:** {area_fraca}. Esta e a disciplina onde a escola "
                f"tem a menor media nas 5 provas — angulo mais forte para o pitch.",
                "info",
            )

        # --- Radar das competencias da redacao ---
        comps = {}
        for i in range(1, 6):
            v = row.get(f"enem_redacao_comp{i}_media")
            if v is not None:
                _COMP_NAMES = {1: "Norma Culta", 2: "Compreensao", 3: "Argumentacao", 4: "Coesao", 5: "Intervencao"}; comps[_COMP_NAMES.get(i, f"Comp {i}")] = float(v)
        if comps:
            st.markdown("")
            section_header(f"Competencias da redacao (ENEM {ENEM_VINTAGE})", "radar")
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=list(comps.values()) + [list(comps.values())[0]],
                theta=list(comps.keys()) + [list(comps.keys())[0]],
                fill="toself",
                name="Desta escola",
                line_color=COLORS["primary"],
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 200])),
                showlegend=False,
                height=300,
                margin=dict(l=40, r=40, t=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Medias por area ---
        areas = {
            "Ciencias da Natureza": row.get("enem_media_cn"),
            "Ciencias Humanas": row.get("enem_media_ch"),
            "Linguagens e Codigos": row.get("enem_media_lc"),
            "Matematica": row.get("enem_media_mt"),
            "Redacao": row.get("enem_media_redacao"),
        }
        areas = {k: float(v) for k, v in areas.items() if v is not None}
        if areas:
            st.markdown("")
            section_header("Medias por area", "bar_chart")
            df_areas = pd.DataFrame([
                {"Area": k, "Media": v} for k, v in areas.items()
            ])
            fig2 = go.Figure(go.Bar(
                x=df_areas["Area"], y=df_areas["Media"],
                marker_color=[COLORS["error"] if v == min(areas.values())
                              else COLORS["primary"] for v in df_areas["Media"]],
                text=[f"{v:.0f}" for v in df_areas["Media"]],
                textposition="outside", textfont=dict(size=13),
            ))
            fig2.update_layout(
                yaxis=dict(range=[0, max(areas.values()) * 1.15], title="Media"),
                height=280, margin=dict(l=0, r=0, t=30, b=0),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("")

    # --- Peer group (sempre mostra, mesmo sem amostra individual) ---
    # Fallback 6y -> 5y: escolas na safra 2024 so tem a coluna de 5 anos, e a
    # secao INTEIRA sumia por causa disso.
    peer_traj = _traj_peer(row)
    if peer_traj:
        section_header("Peer group — escolas do mesmo municipio x mesma dependencia", "groups")
        st.caption(
            "⚠️ **REGRA ETICA:** dados abaixo referem-se ao GRUPO DE PARES "
            "(concorrentes diretas), NUNCA a esta escola individualmente."
        )
        mun = row.get("peer_mun_nome") or company.get("city")
        dep = row.get("enem_dependencia") or company.get("admin_dependency")

        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            # Rotulo era "5 anos" lendo a coluna _6y (existem AS DUAS colunas)
            _label_traj = ("Trajetoria 6 anos" if row.get("peer_trajetoria_6y")
                           else "Trajetoria 5 anos")
            metric_card(_label_traj, str(peer_traj),
                        COLORS["accent"], icon="timeline")
        with pc2:
            delta = row.get("peer_delta_media_geral_2022_2025") \
                or row.get("peer_delta_media_geral_2022_2024")
            if delta is not None:
                delta_f = float(delta)
                metric_card(
                    f"Delta 2022-{_ano_row}",
                    f"{delta_f:+.1f}",
                    COLORS["success"] if delta_f > 0 else COLORS["error"],
                    icon="trending_flat",
                )
        with pc3:
            media_2024 = _safra(row, "peer_media_geral")
            if media_2024 is not None:
                metric_card(f"Media peer {_ano_row}", f"{float(media_2024):.1f}",
                            COLORS["info"], icon="analytics")
        with pc4:
            presentes_2024 = _safra(row, "peer_presentes")
            if presentes_2024 is not None:
                metric_card("Presentes peer", f"{int(presentes_2024):,}".replace(",", "."),
                            COLORS["secondary"], icon="groups")

        # --- Serie historica 2020-2024 ---
        serie = {}
        for ano in range(2020, 2026):
            v = row.get(f"peer_media_geral_{ano}")
            if v is not None:
                serie[ano] = float(v)
        if len(serie) >= 2:
            st.markdown("")
            fig3 = go.Figure(go.Scatter(
                x=[str(y) for y in serie.keys()], y=list(serie.values()),
                mode="lines+markers",
                line=dict(color=COLORS["primary"], width=3),
                marker=dict(size=12),
                text=[f"{v:.0f}" for v in serie.values()],
                textposition="top center",
            ))
            fig3.update_layout(
                title=f"Media ENEM do peer group em {mun} ({dep}) 2020-{ENEM_VINTAGE}",
                yaxis=dict(title="Media"),
                height=280, margin=dict(l=0, r=0, t=40, b=0),
                plot_bgcolor="white",
            )
            st.plotly_chart(fig3, use_container_width=True)

    st.markdown("")

    # --- Contexto municipal (sempre rotulado) ---
    renda_2024 = _safra(row, "socio_renda_idx_media")
    if renda_2024 is not None:
        section_header("Contexto do municipio (perfil socioeconomico)", "location_city")
        st.caption(
            "⚠️ **REGRA ETICA:** dados abaixo sao do MUNICIPIO onde a escola esta "
            "localizada, NUNCA dos alunos desta escola individualmente."
        )
        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            metric_card(f"Indice de renda {_ano_row}", f"{float(renda_2024):.2f}",
                        COLORS["primary"], icon="paid")
        with sc2:
            pais_sup = _safra(row, "socio_pct_pais_superior")
            if pais_sup is not None:
                pct = float(pais_sup) * 100 if float(pais_sup) < 1 else float(pais_sup)
                metric_card("% pais com superior", f"{pct:.1f}%",
                            COLORS["info"], icon="school")
        with sc3:
            delta_renda = row.get("socio_delta_renda_2020_2025") \
                or row.get("socio_delta_renda_2020_2024")
            if delta_renda is not None:
                metric_card(
                    f"Delta renda 2020-{_ano_row}",
                    f"{float(delta_renda):+.2f}",
                    COLORS["success"] if float(delta_renda) > 0 else COLORS["error"],
                    icon="trending_up",
                )

    # --- SERIE HISTORICA INDIVIDUAL (Censo 2020-2025) ---
    # Fetch separado (padrao R6 do plano), falha silenciosa se indisponivel.
    st.markdown("")
    try:
        sc_rows = _fetch_censo_yearly_by_inep(str(inep))
    except Exception:
        sc_rows = []

    if sc_rows and len(sc_rows) >= 2:
        section_header("Serie historica individual (Censo 2020-2025)", "timeline")
        st.caption(
            "Evolucao ano a ano desta escola em matriculas, equipe e tecnologia. "
            "Dados administrativos declarados ao INEP — nao dependem de amostra "
            "estatistica."
        )

        # Ordena por ano
        sc_rows = sorted(sc_rows, key=lambda r: r.get("vintage_censo") or 0)
        anos = [r.get("vintage_censo") for r in sc_rows]

        # === CHART 1: Matriculas por etapa ===
        def _series(key):
            return [r.get(key) for r in sc_rows]

        mat_bas = _series("qt_mat_bas")
        mat_fund_af = _series("qt_mat_fund_af")
        mat_med = _series("qt_mat_med")
        mat_fund_ai = _series("qt_mat_fund_ai")

        fig_mat = go.Figure()
        fig_mat.add_trace(go.Scatter(
            x=anos, y=mat_bas, mode="lines+markers+text",
            name="Total Basica",
            line=dict(color=COLORS["primary"], width=3),
            marker=dict(size=10),
            text=[str(int(v)) if v else "" for v in mat_bas],
            textposition="top center",
        ))
        fig_mat.add_trace(go.Scatter(
            x=anos, y=mat_fund_ai, mode="lines+markers",
            name="Fund. Anos Iniciais (1-5)",
            line=dict(color=COLORS["info"], width=2, dash="dot"),
            marker=dict(size=8),
        ))
        fig_mat.add_trace(go.Scatter(
            x=anos, y=mat_fund_af, mode="lines+markers",
            name="Fund. Anos Finais (6-9)",
            line=dict(color=COLORS["accent"], width=2),
            marker=dict(size=8),
        ))
        fig_mat.add_trace(go.Scatter(
            x=anos, y=mat_med, mode="lines+markers",
            name="Ensino Medio",
            line=dict(color=COLORS["success"], width=2),
            marker=dict(size=8),
        ))
        fig_mat.update_layout(
            title="Matriculas por etapa",
            height=320,
            margin=dict(l=0, r=0, t=40, b=0),
            plot_bgcolor="white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_mat, use_container_width=True)

        # === CHART 2: Equipe docente ===
        docentes = _series("qt_doc_bas")
        fig_doc = go.Figure(go.Scatter(
            x=anos, y=docentes, mode="lines+markers+text",
            line=dict(color=COLORS["accent"], width=3),
            marker=dict(size=12),
            text=[str(int(v)) if v else "" for v in docentes],
            textposition="top center",
        ))
        fig_doc.update_layout(
            title="Equipe docente total",
            height=220,
            margin=dict(l=0, r=0, t=40, b=0),
            plot_bgcolor="white",
            showlegend=False,
        )
        st.plotly_chart(fig_doc, use_container_width=True)

        # === KPIs de crescimento (deltas calculados localmente) ===
        def _delta_pct(series):
            vals = [v for v in series if v is not None]
            if len(vals) < 2 or vals[0] == 0:
                return None
            return round((vals[-1] - vals[0]) / vals[0] * 100, 1)

        delta_total = _delta_pct(mat_bas)
        delta_med = _delta_pct(mat_med)
        delta_fund_af = _delta_pct(mat_fund_af)
        delta_doc = _delta_pct(docentes)

        st.markdown("")
        st.markdown(f"**Deltas totais ({anos[0]} → {anos[-1]})**")
        dc1, dc2, dc3, dc4 = st.columns(4)
        with dc1:
            if delta_total is not None:
                metric_card(
                    "Matriculas base",
                    f"{delta_total:+.1f}%",
                    COLORS["success"] if delta_total > 0 else COLORS["error"],
                    icon="school",
                )
        with dc2:
            if delta_med is not None:
                metric_card(
                    "Ensino Medio",
                    f"{delta_med:+.1f}%",
                    COLORS["success"] if delta_med > 0 else COLORS["error"],
                    icon="menu_book",
                )
        with dc3:
            if delta_fund_af is not None:
                metric_card(
                    "Fund. Anos Finais",
                    f"{delta_fund_af:+.1f}%",
                    COLORS["success"] if delta_fund_af > 0 else COLORS["error"],
                    icon="groups",
                )
        with dc4:
            if delta_doc is not None:
                metric_card(
                    "Docentes",
                    f"{delta_doc:+.1f}%",
                    COLORS["success"] if delta_doc > 0 else COLORS["error"],
                    icon="record_voice_over",
                )

        # === CHART 3: Tecnologia (dados binarios) ===
        tech_fields = [
            ("in_internet", "Internet"),
            ("in_internet_alunos", "Internet p/ alunos"),
            ("in_internet_aprendizagem", "Internet p/ aprendizagem"),
            ("in_laboratorio_informatica", "Lab. Informatica"),
            ("in_biblioteca", "Biblioteca"),
            ("in_quadra_esportes", "Quadra"),
            ("in_laboratorio_ciencias", "Lab. Ciencias"),
            ("in_alimentacao", "Alimentacao"),
        ]
        tech_rows = []
        for ano, row_sc in zip(anos, sc_rows):
            for field, label in tech_fields:
                val = row_sc.get(field)
                if val is not None:
                    tech_rows.append({"Ano": ano, "Item": label, "Presente": 1 if val else 0})
        if tech_rows:
            df_tech = pd.DataFrame(tech_rows)
            pivot = df_tech.pivot_table(index="Item", columns="Ano", values="Presente", fill_value=0)
            # Preserve order
            label_order = [lbl for _, lbl in tech_fields if lbl in pivot.index]
            pivot = pivot.loc[label_order]
            st.markdown("")
            st.markdown("**Tecnologia e infraestrutura (presente/ausente por ano)**")
            st.dataframe(
                pivot.replace({1: "✅", 0: "❌"}),
                use_container_width=True,
                height=320,
            )
    elif sc_rows:
        alert_banner(
            f"Serie historica disponivel para apenas {len(sc_rows)} ano(s) — "
            "pelo menos 2 anos sao necessarios para mostrar evolucao.",
            "info",
        )


# ---------------------------------------------------------------------------


def render_redes_view() -> None:
    """Renderiza a aba Redes: agrupa escolas por cnpj_mantenedora, mostra
    KPIs, grafico top 10, e expanders por rede com metricas + unidades +
    botao de correcao manual de nome (override).

    Migrado de dashboard/pages/14_🔗_Redes.py (deletada) e integrado como
    aba da pagina Escolas porque as duas funcionalidades sao irmas.
    """
    try:
        import plotly.express as px
    except Exception:
        alert_banner("plotly nao instalado — instale com 'pip install plotly'.", "error")
        return

    # Carrega escolas com mantenedora
    try:
        r = db.client.table("companies").select(
            "id,name,city,state,bairro,status,qualification_score,"
            "cnpj_mantenedora,cnpj_escola,categoria_privada,"
            "total_matriculas,matriculas_fund_af,matriculas_medio,"
            "total_docentes,qt_coordenadores,total_turmas,nivel_tecnologico,fonte_dados"
        ).not_.is_("cnpj_mantenedora", "null").execute()
    except Exception as e:
        alert_banner(f"Erro ao carregar escolas: {e}", "error")
        return

    grupos = defaultdict(list)
    for e in r.data or []:
        cnpj = e.get("cnpj_mantenedora")
        if cnpj:
            grupos[cnpj].append(e)

    if not grupos:
        alert_banner(
            "Nenhuma escola com CNPJ de mantenedora encontrada. Rode o update_existing_schools.py "
            "para preencher os dados do Censo 2025.",
            "info",
        )
        return

    # Aviso se migration 014 ainda nao foi aplicada
    if not has_rede_overrides_table():
        alert_banner(
            "Migration 014 nao aplicada — correcao manual de nome de rede indisponivel. "
            "Rode <code>database/migrations/APLICAR-014-REDE-OVERRIDES.sql</code> no Supabase SQL Editor.",
            "warning",
        )

    # Build redes summary
    redes = []
    for cnpj, escolas in grupos.items():
        if len(escolas) < 2:
            continue
        alvo_total = sum(
            int((e.get("matriculas_fund_af") or 0) + (e.get("matriculas_medio") or 0))
            for e in escolas
        )
        total_alunos = sum(int(e.get("total_matriculas") or 0) for e in escolas)
        docentes = sum(int(e.get("total_docentes") or 0) for e in escolas)
        coord = sum(int(e.get("qt_coordenadores") or 0) for e in escolas)
        turmas = sum(int(e.get("total_turmas") or 0) for e in escolas)
        scores = [e.get("qualification_score") for e in escolas if e.get("qualification_score")]
        score_medio = round(sum(scores) / len(scores), 1) if scores else 0
        cidades = sorted(set(e.get("city") or "" for e in escolas))
        ufs = sorted(set(e.get("state") or "" for e in escolas))

        tech_counts = defaultdict(int)
        for e in escolas:
            t = e.get("nivel_tecnologico") or "Sem dado"
            tech_counts[t] += 1
        tech_predom = max(tech_counts.items(), key=lambda x: x[1])[0]

        redes.append({
            "cnpj": cnpj,
            "nome_rede": resolver_nome_rede(cnpj, escolas),
            "unidades": len(escolas),
            "alunos_alvo": alvo_total,
            "total_alunos": total_alunos,
            "docentes": docentes,
            "coordenadores": coord,
            "turmas": turmas,
            "score_medio": score_medio,
            "cidades": cidades,
            "ufs": ufs,
            "tech_predom": tech_predom,
            "escolas": escolas,
        })

    singletons_cnpjs = [cnpj for cnpj, esc in grupos.items() if len(esc) == 1]
    n_singletons = len(singletons_cnpjs)

    # Metricas topo
    total_escolas_em_rede = sum(r["unidades"] for r in redes)
    total_alvo_rede = sum(r["alunos_alvo"] for r in redes)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Redes identificadas", len(redes), COLORS["primary"], icon="hub")
    with mc2:
        metric_card("Escolas em rede", f"{total_escolas_em_rede}",
                    COLORS["accent"], icon="account_tree")
    with mc3:
        metric_card("Alunos alvo (redes)",
                    f"{total_alvo_rede:,}".replace(",", "."),
                    COLORS["info"], icon="groups")
    with mc4:
        metric_card("Escolas independentes", n_singletons,
                    COLORS["secondary"], icon="domain_disabled")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # Filtros
    fc1, fc2 = st.columns([2, 1])
    with fc1:
        ordenar_por = st.selectbox(
            "Ordenar por",
            ["Alunos alvo (maior)", "Unidades (mais)", "Score medio (maior)", "Nome da rede"],
            key="redes_ordenar",
        )
    with fc2:
        min_unid = st.number_input(
            "Minimo de unidades", min_value=2, max_value=20, value=2, step=1,
            key="redes_min_unid",
        )

    ordem_map = {
        "Alunos alvo (maior)": lambda r: -r["alunos_alvo"],
        "Unidades (mais)": lambda r: -r["unidades"],
        "Score medio (maior)": lambda r: -r["score_medio"],
        "Nome da rede": lambda r: r["nome_rede"],
    }
    redes_filt = [r for r in redes if r["unidades"] >= min_unid]
    redes_filt.sort(key=ordem_map[ordenar_por])

    # Grafico Top 10
    section_header("Top redes por alunos alvo", "leaderboard")
    top10 = redes_filt[:10]
    if top10:
        df_top = pd.DataFrame([{
            "Rede": r["nome_rede"],
            "Unidades": r["unidades"],
            "Alunos alvo": r["alunos_alvo"],
            "Score medio": r["score_medio"],
            "Tech": r["tech_predom"],
        } for r in top10])
        fig = px.bar(
            df_top, y="Rede", x="Alunos alvo", orientation="h", color="Tech",
            color_discrete_map={
                "Alto": COLORS["success"], "Medio": COLORS["warning"],
                "Médio": COLORS["warning"], "Baixo": COLORS["error"],
                "Sem dado": "#bdbdbd",
            },
            text="Alunos alvo", hover_data=["Unidades", "Score medio"], height=420,
        )
        fig.update_traces(textposition="outside", textfont=dict(size=13), cliponaxis=False)
        fig.update_layout(
            yaxis=dict(autorange="reversed", title=""),
            xaxis_title="Alunos alvo (Fund AF + Medio)",
            margin=dict(l=0, r=60, t=10, b=0), plot_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # Cards das redes
    section_header(f"Detalhes das {len(redes_filt)} redes", "account_tree")
    if not redes_filt:
        alert_banner("Nenhuma rede encontrada com os filtros atuais.", "info")
        return

    for rede in redes_filt:
        with st.expander(
            f"🏫 **{rede['nome_rede']}** · {rede['unidades']} unidades · "
            f"{rede['alunos_alvo']:,} alunos alvo · score {rede['score_medio']}".replace(",", "."),
            expanded=(rede == redes_filt[0]),
        ):
            # Metricas da rede
            rm1, rm2, rm3, rm4 = st.columns(4)
            with rm1:
                metric_card("Unidades", rede["unidades"], COLORS["primary"], icon="domain")
            with rm2:
                metric_card("Alunos alvo",
                            f"{rede['alunos_alvo']:,}".replace(",", "."),
                            COLORS["accent"], icon="track_changes")
            with rm3:
                metric_card("Docentes totais",
                            f"{rede['docentes']:,}".replace(",", "."),
                            COLORS["info"], icon="record_voice_over")
            with rm4:
                metric_card("Coordenadores", rede["coordenadores"],
                            COLORS["secondary"], icon="supervisor_account")

            # Metadata
            cnpj_display = rede["cnpj"]
            cidades_str = ", ".join(rede["cidades"])
            ufs_str = ", ".join(rede["ufs"])
            st.caption(
                f"**CNPJ mantenedora:** {cnpj_display} · **Cidades:** {cidades_str} · "
                f"**UFs:** {ufs_str} · **Nivel tec predominante:** {rede['tech_predom']}"
            )

            # Correcao de nome (override manual) — so se migration aplicada
            if has_rede_overrides_table():
                corr_key = f"corrigir_rede_{rede['cnpj']}"
                if corr_key not in st.session_state:
                    st.session_state[corr_key] = False
                cc1, cc2 = st.columns([3, 1])
                with cc1:
                    if st.session_state[corr_key]:
                        novo_nome = st.text_input(
                            "Nome oficial da rede",
                            value=rede["nome_rede"],
                            key=f"novo_nome_{rede['cnpj']}",
                            help="Ex: 'Rede ICM', 'Rede Marista', 'La Salle'",
                        )
                    else:
                        st.caption(f"Nome atual: **{rede['nome_rede']}** (heuristico se nao ha override)")
                with cc2:
                    if not st.session_state[corr_key]:
                        if st.button("✏️ Corrigir nome", key=f"btn_corr_{rede['cnpj']}",
                                     use_container_width=True):
                            st.session_state[corr_key] = True
                            st.rerun()
                    else:
                        if st.button("Salvar", key=f"btn_save_{rede['cnpj']}",
                                     type="primary", use_container_width=True):
                            novo = st.session_state.get(f"novo_nome_{rede['cnpj']}", "").strip()
                            if novo and len(novo) >= 2:
                                if set_rede_override(rede["cnpj"], novo):
                                    st.toast(f"Nome da rede atualizado para '{novo}'")
                                    st.session_state[corr_key] = False
                                    st.rerun()
                                else:
                                    st.error("Falha ao salvar — verifique os logs")
                            else:
                                st.warning("Nome deve ter pelo menos 2 caracteres")

            # Tabela das unidades
            df_unid = pd.DataFrame([{
                "Escola": e["name"][:50],
                "Cidade": e.get("city") or "",
                "UF": e.get("state") or "",
                "Bairro": e.get("bairro") or "",
                "Alvo": int((e.get("matriculas_fund_af") or 0) + (e.get("matriculas_medio") or 0)),
                "Fund AF": int(e.get("matriculas_fund_af") or 0),
                "Medio": int(e.get("matriculas_medio") or 0),
                "Tech": e.get("nivel_tecnologico") or "-",
                "Score": e.get("qualification_score") or 0,
                "Status": e.get("status") or "",
                "id": e["id"],
            } for e in sorted(rede["escolas"], key=lambda x: (x.get("qualification_score") or 0), reverse=True)])

            st.dataframe(
                df_unid[["Escola", "Cidade", "Bairro", "Alvo", "Fund AF", "Medio", "Tech", "Score", "Status"]],
                use_container_width=True, hide_index=True,
                column_config={
                    "Alvo": st.column_config.NumberColumn("Alvo", help="Fund AF + Medio"),
                    "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                },
            )

            # Quick action: abrir unidade no detalhe
            ac1, ac2 = st.columns([2, 1])
            with ac1:
                escola_sel = st.selectbox(
                    "Abrir unidade:", df_unid["Escola"].tolist(),
                    key=f"sel_{rede['cnpj']}", label_visibility="collapsed",
                )
            with ac2:
                if st.button("Ver detalhe", key=f"btn_{rede['cnpj']}",
                              icon=":material/open_in_new:", use_container_width=True):
                    sel_id = df_unid[df_unid["Escola"] == escola_sel]["id"].iloc[0]
                    st.session_state["escola_detail_id"] = sel_id
                    st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.info(
        "💡 **Dica de venda em rede:** abordar a mantenedora permite negociar uma unica vez "
        "e fechar varias unidades simultaneamente. Para redes grandes vale tentar contato direto "
        "com a coordenacao nacional/regional. Pergunte ao IAlex 'me mostra a rede X'."
    )


# ===========================================================================
# MODO DETALHE
# ===========================================================================
if st.session_state.escola_detail_id:
    company_id = st.session_state.escola_detail_id
    company = db.get_company_detail(company_id)

    if not company:
        # escola_msg (e nao st.error): o st.rerun() logo abaixo descarta
        # qualquer elemento do corpo. A pagina ja tem renderizador proprio
        # dessa chave — reusar em vez de trazer um segundo mecanismo.
        st.session_state.escola_msg = ("error", "Escola nao encontrada.")
        go_to_list()
        st.rerun()

    # --- Breadcrumb ---
    breadcrumb(["Escolas", company.get("name", "Detalhe")])

    # --- Voltar + acoes rapidas no header ---
    header_cols = st.columns([1, 1, 2])
    with header_cols[0]:
        if st.button("Voltar a lista", icon=":material/arrow_back:",
                     use_container_width=True, key="escola_back"):
            go_to_list()
            st.rerun()
    with header_cols[1]:
        if st.button("Buscar sinais", icon=":material/psychology:",
                     use_container_width=True, key="escola_buscar_sinais",
                     help="Pesquisa rankings, premios e noticias na web (busca por IA + DuckDuckGo). Salva como memorias."):
            try:
                from tools.discovery_engine import discovery_engine
                with st.status(f"Buscando sinais de {company.get('name', '?')}...",
                                expanded=True) as status:
                    st.write("🔍 Buscando rankings, premios e noticias na web "
                             "(busca por IA; DuckDuckGo como reserva)...")
                    sinais_result = discovery_engine.enrich_signals(company_id)
                    n_sinais = sinais_result.get("sinais_adicionados", 0)
                    n_found = sinais_result.get("sinais_encontrados", 0)
                    fonte = sinais_result.get("fonte_usada") or "nenhuma"
                    erros = sinais_result.get("erros") or []
                    st.write(f"📊 Fonte usada: **{fonte}** | encontrados: {n_found} | salvos: {n_sinais}")
                    for e in erros[:3]:
                        st.write(f"⚠️ {e}")
                    if sinais_result.get("preview"):
                        st.write("✨ Preview:")
                        for p in sinais_result["preview"][:5]:
                            st.write(f"  • {p}")
                    status.update(
                        label=f"Concluido: {n_sinais} sinal(is) novo(s) salvos",
                        state="complete" if n_sinais > 0 else "error",
                        expanded=(n_sinais == 0),  # expande se falhou pra usuario ver o motivo
                    )
                if n_sinais > 0:
                    st.session_state.escola_msg = (
                        "success",
                        f"{n_sinais} sinal(is) salvo(s) (de {n_found} encontrado(s) via {fonte}).",
                    )
                elif erros:
                    st.session_state.escola_msg = (
                        "warning",
                        f"Sem sinais novos. Motivo: {erros[0]}",
                    )
                else:
                    st.session_state.escola_msg = (
                        "info",
                        "Nenhum sinal novo encontrado (busca completou sem erros).",
                    )
                st.rerun()
            except Exception as e:
                st.session_state.escola_msg = ("error", f"Erro ao buscar sinais: {e}")
                st.rerun()

    # --- Mensagem de feedback ---
    if st.session_state.escola_msg:
        msg_type, msg_text = st.session_state.escola_msg
        if msg_type == "success":
            alert_banner(msg_text, "success")
        elif msg_type == "error":
            alert_banner(msg_text, "error")
        elif msg_type == "info":
            alert_banner(msg_text, "info")
        elif msg_type == "warning":
            # Faltava: mensagens 'warning' (ex.: motivo de "sem sinais novos")
            # eram descartadas silenciosamente e o usuario nao via nada.
            alert_banner(msg_text, "warning")
        else:
            alert_banner(str(msg_text), "info")
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

    # F-strings concatenadas single-line evitam o bug de "4+ espacos = code block"
    # que o Markdown aplica antes do unsafe_allow_html=True processar o HTML.
    # (Padrao identico ao `section_header` em theme.py.)
    st.markdown(
        f'<div class="data-card" style="border-left: 4px solid {COLORS["primary"]}; padding: 20px 24px;">'
        f'<div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">'
        f'{avatar(company.get("name", "?"), COLORS["primary"])}'
        f'<div style="flex:1;">'
        f'<div style="font-size:22px; font-weight:700; color:#212121;">{company.get("name", "?")}</div>'
        f'<div style="font-size:14px; color:#757575; margin-top:2px;">'
        f'{company.get("city", "")}/{company.get("state", "")}{bairro_txt} &middot; INEP: {company.get("inep_code", "")}'
        f'</div>'
        f'{fonte_badge_html}'
        f'</div>'
        f'<div style="display:flex; gap:12px; align-items:center;">'
        f'{status_badge(status_en, status_label)}'
        f'{fit_badge_html}'
        f'<div style="display:flex; flex-direction:column; align-items:center;">'
        f'<span style="font-size:9px; color:#757575; font-weight:600; text-transform:uppercase; letter-spacing:0.5px;">Score IA</span>'
        f'<span style="font-size:22px; font-weight:700; color:{score_color(sc)};">{sc}</span>'
        f'<span style="font-size:9px; color:#757575;">/ 100</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Caption com motivo do Fit
    if fit_val is not None and fit_motivo:
        st.caption(f"**Fit IAprendo:** {fit_motivo}")

    # === CTA Contextual (1.3 Quick Win): proxima acao sugerida ===
    # Sugere a proxima coisa a fazer baseado no estado da escola.
    # Helper inline para nao precisar refatorar imports.
    def _next_action_for_school(comp: Dict[str, Any], cid: str) -> Optional[Dict[str, str]]:
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        st_status = (comp.get("status") or "raw").lower()

        # Quantos contatos com email?
        try:
            _contacts_resp = db.client.table("contacts").select(
                "id, email"
            ).eq("company_id", cid).execute()
            _contacts = _contacts_resp.data or []
            n_contacts = len(_contacts)
            n_with_email = sum(1 for c in _contacts if (c.get("email") or "").strip())
        except Exception:
            n_contacts, n_with_email = 0, 0

        # Mensagens na fila e ultimas enviadas
        try:
            _q = db.client.table("approval_queue").select(
                "id, status, sent_at, replied_at, follow_up_number"
            ).eq("company_id", cid).order("created_at", desc=True).execute()
            _queue = _q.data or []
        except Exception:
            _queue = []

        n_pending = sum(1 for q in _queue if q.get("status") == "pending")
        sent_items = [q for q in _queue if q.get("status") == "sent" and q.get("sent_at")]
        last_sent = sent_items[0] if sent_items else None
        has_reply = any(q.get("replied_at") for q in _queue)

        # Decision tree (do mais especifico para o mais geral)
        if has_reply:
            return {"label": "Responder a escola (resposta recebida)", "icon": "reply",
                    "page": "mensagens", "type": "success"}
        if n_pending > 0:
            return {"label": f"Aprovar mensagem(ns) na fila ({n_pending})", "icon": "mark_email_read",
                    "page": "mensagens", "type": "warning"}
        if last_sent:
            try:
                _sent_dt = _dt.fromisoformat(str(last_sent["sent_at"]).replace("Z", "+00:00"))
                _days_since = (_dt.now(_tz.utc) - _sent_dt).days
            except Exception:
                _days_since = 0
            if _days_since < 3:
                return {"label": f"Aguardando resposta (enviado ha {_days_since} dia(s))", "icon": "schedule",
                        "page": None, "type": "info"}
            else:
                return {"label": f"Gerar follow-up ({_days_since} dias sem resposta)", "icon": "autorenew",
                        "page": "mensagens", "type": "warning"}
        if st_status == "raw":
            return {"label": "Qualificar com IA (selecione no Pipeline)", "icon": "grading",
                    "page": "prospectar", "type": "info"}
        if st_status in ("qualified", "filtered") and n_contacts == 0:
            return {"label": "Buscar decisores (Enriquecer no Pipeline)", "icon": "person_search",
                    "page": "prospectar", "type": "info"}
        if n_contacts > 0 and n_with_email == 0:
            return {"label": "Buscar emails dos contatos (Pipeline > Enriquecer)", "icon": "alternate_email",
                    "page": "prospectar", "type": "warning"}
        if st_status in ("qualified", "enriched") and n_with_email > 0:
            return {"label": "Gerar email (Pipeline > Gerar)", "icon": "edit_note",
                    "page": "prospectar", "type": "info"}
        return None

    _next = _next_action_for_school(company, company_id)
    if _next:
        _color_map = {"warning": "#FFA726", "info": "#29B6F6", "success": "#66BB6A"}
        _bg = _color_map.get(_next["type"], "#90A4AE")
        # Mapa pagina-logica -> arquivo (pra st.switch_page = navegacao INTERNA,
        # sem reload/re-login. Link <a href> fazia reload total -> pisca login).
        _page_file_map = {
            "mensagens": "pages/6_✉️_Comunicacao.py",
            "prospectar": "pages/5_📊_Pipeline.py",
        }
        _pg_file = _page_file_map.get(_next.get("page") or "")
        _na_c1, _na_c2 = st.columns([4, 1.1])
        with _na_c1:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 16px;'
                f'background:{_bg}15;border-left:4px solid {_bg};border-radius:6px;margin:8px 0">'
                f'<span style="font-size:14px;color:#212121">'
                f'<strong>Proxima acao:</strong> {_next["label"]}</span></div>',
                unsafe_allow_html=True,
            )
        with _na_c2:
            if _pg_file:
                st.markdown('<div style="margin-top:10px"></div>', unsafe_allow_html=True)
                _cta_lbl = "Ir para Mensagens" if _next["page"] == "mensagens" else "Ir para Prospectar"
                if st.button(_cta_lbl, key="cta_next_action", use_container_width=True,
                             icon=":material/arrow_forward:"):
                    # Levar a escola junto. O CTA diz "selecione no Pipeline" e
                    # depois jogava o usuario numa lista de centenas sem nenhuma
                    # selecao — o company_id estava em escopo e era descartado.
                    if _next.get("page") == "prospectar":
                        st.session_state["pipeline_selected_ids"] = [company_id]
                        # Invalida o cache da tabela pra ela ja abrir marcada
                        # (mesmas chaves de _reset_ckbox_keys no Pipeline).
                        for _k in ("_tbl_df_cached", "_tbl_filter_sig", "tbl_editor_v3"):
                            st.session_state.pop(_k, None)
                    st.switch_page(_pg_file)

    st.markdown("")

    # --- Tabs (v2: 7 -> 4, mockup escola-ficha.html) ---
    tab_dados, tab_performance, tab_contatos, tab_msgs = st.tabs([
        "📋 Visao Geral", "📊 Desempenho", "👥 Pessoas", "💬 Conversas"
    ])
    # Aliases: blocos da v1 renderizam dentro das 4 novas abas, sem mover codigo
    tab_registrar = tab_msgs   # Registrar contato vive em Conversas
    tab_hist = tab_msgs        # Historico fecha a aba Conversas
    tab_acoes = tab_dados      # Acoes (relatorio/graficos/admin) no fim da Visao Geral

    # === TAB VISAO GERAL ===
    with tab_dados:
        # --- Argumentos de venda (mockup escola-ficha.html) ---
        try:
            from agent.tools.agenda_tools import _build_argumentos
            _args_venda = _build_argumentos(company)
        except Exception:
            _args_venda = []
        if _args_venda:
            _itens = "".join(
                f'<div style="padding:7px 0;border-bottom:1px solid #F1F5F9;'
                f'font-size:13.5px;color:#334155;line-height:1.45">{a}</div>'
                for a in _args_venda
            )
            st.markdown(
                f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;'
                f'border-left:4px solid #6C5CE7;border-radius:10px;'
                f'padding:14px 18px;margin-bottom:14px">'
                f'<div style="font-size:11px;font-weight:700;color:#6C5CE7;'
                f'text-transform:uppercase;letter-spacing:0.7px;margin-bottom:4px">'
                f'💡 Argumentos de venda</div>{_itens}</div>',
                unsafe_allow_html=True,
            )
        # --- Reputacao no Google (vem do enriquecimento; ja paga no Places) ---
        _g_rating = company.get("google_rating")
        if _g_rating:
            try:
                _r = float(_g_rating)
                _n = company.get("google_reviews_count") or 0
                _estrelas = "★" * int(round(_r)) + "☆" * (5 - int(round(_r)))
                # Poucas avaliacoes => nota pouco confiavel; sinalizar
                _nota_ctx = (
                    f"{_n} avaliacoes" if _n >= 20
                    else f"apenas {_n} avaliacao(oes) — leia com cautela"
                ) if _n else "sem contagem de avaliacoes"
                _cor = COLORS["success"] if _r >= 4.5 else (
                    COLORS["warning"] if _r >= 3.5 else COLORS["error"])
                _link = company.get("google_maps_url")
                _link_html = (
                    f'<a href="{_link}" target="_blank" rel="noopener" '
                    f'style="font-size:12px;margin-left:10px">ver no Maps ↗</a>'
                ) if _link else ""
                st.markdown(
                    f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;'
                    f'border-left:4px solid {_cor};border-radius:10px;'
                    f'padding:10px 16px;margin-bottom:14px">'
                    f'<span style="font-size:11px;font-weight:700;color:#64748B;'
                    f'text-transform:uppercase;letter-spacing:0.7px">Reputacao Google</span><br>'
                    f'<span style="font-size:18px;font-weight:700;color:{_cor}">'
                    f'{_r:.1f}</span> '
                    f'<span style="color:{_cor}">{_estrelas}</span> '
                    f'<span style="font-size:12px;color:#64748B">({_nota_ctx})</span>'
                    f'{_link_html}</div>',
                    unsafe_allow_html=True,
                )
            except Exception:
                # Bloco decorativo: nunca pode derrubar a ficha da escola
                pass

        section_header("Informacoes da Escola", "edit")

        # ----- OWNERSHIP: badge do dono + reatribuicao (admin) -----
        try:
            from utils.sender_profile import (
                get_active_sender_username as _gau, is_admin as _is_admin,
                list_profiles as _list_profiles,
            )
            _owner = company.get("owner_username")
            _owner_at = (company.get("owner_assigned_at") or "")[:10]
            _me = _gau()
            if _owner:
                _since = f" desde {_owner_at[8:10]}/{_owner_at[5:7]}/{_owner_at[0:4]}" if len(_owner_at) == 10 else ""
                if _owner == _me:
                    alert_banner(f"🔒 Este lead e seu (sob sua gestao{_since}).", "success")
                else:
                    alert_banner(
                        f"🔒 <strong>Sob gestao de {_owner}</strong>{_since}. "
                        f"Voce pode agir, mas combine com {_owner} pra evitar contato duplicado.",
                        "warning",
                    )
            else:
                alert_banner(
                    "Sem dono ainda — vira de quem fizer o 1o contato (email/registro de contato).",
                    "info",
                )
            # Admin pode reatribuir/limpar (correcao, nao claim self-service)
            if _is_admin(_me):
                with st.expander("Gestao do dono (admin)", icon=":material/manage_accounts:"):
                    _users = [p.get("username") for p in _list_profiles() if p.get("username")]
                    _opts = ["(sem dono)"] + _users
                    _cur_idx = _opts.index(_owner) if _owner in _opts else 0
                    _ga1, _ga2 = st.columns([3, 1])
                    with _ga1:
                        _new_owner = st.selectbox("Reatribuir lead para:", _opts,
                                                  index=_cur_idx, key=f"reassign_{company_id}")
                    with _ga2:
                        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                        if st.button("Aplicar", key=f"reassign_btn_{company_id}",
                                     use_container_width=True, type="primary"):
                            _val = None if _new_owner == "(sem dono)" else _new_owner
                            if db.set_company_owner(company_id, _val):
                                st.session_state.escola_msg = ("success", f"Dono atualizado: {_new_owner}")
                            else:
                                st.session_state.escola_msg = ("error", "Falha ao atualizar dono.")
                            st.rerun()
        except Exception as _e_own:
            pass  # nunca quebra a aba por causa do badge de dono

        with st.form("edit_company"):
            c1, c2 = st.columns(2)
            with c1:
                edit_name = st.text_input("Nome", value=company.get("name", ""))
                edit_city = st.text_input("Cidade", value=company.get("city", ""))
                edit_state = st.text_input("UF", value=company.get("state", ""), max_chars=2)
                edit_address = st.text_input("Endereco", value=company.get("address", "") or "")
                edit_phone = st.text_input("Telefone (fixo)", value=company.get("phone", "") or "")
                edit_whatsapp = st.text_input(
                    "📱 WhatsApp da Escola",
                    value=company.get("phone_whatsapp", "") or "",
                    help="Celular/WhatsApp da secretaria (separado do telefone fixo). Usado como fallback no envio se nenhum contato tiver WhatsApp.",
                )
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
                    "phone_whatsapp": (edit_whatsapp or "").strip() or None,
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
                    fig.update_traces(textposition="outside", textfont=dict(size=13), cliponaxis=False)
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

    # === TAB PERFORMANCE ENEM ===
    with tab_performance:
        _render_performance_tab(company, company_id)

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
                phone_str = ct.get("phone", "") or ""
                whatsapp_str = ct.get("phone_whatsapp", "") or ""
                wpp_html = (
                    f'<div style="font-size:12px; color:#25D366; margin-top:2px;">📱 WhatsApp: {whatsapp_str}</div>'
                    if whatsapp_str else ''
                )
                phone_html = f' &middot; ☎️ {phone_str}' if phone_str else ''
                # HTML compactado em UMA linha logica (sem newlines/indent) para
                # nao acionar o parser de markdown como code-block quando
                # wpp_html for vazio (regra: 4+ espacos de indent = <pre>).
                card_html = (
                    f'<div class="data-card" style="border-left: 4px solid {ct_color};">'
                    f'<div style="display:flex; align-items:center; gap:12px;">'
                    f'{avatar(ct.get("full_name", "?"), ct_color)}'
                    f'<div style="flex:1;">'
                    f'<div style="font-weight:600; font-size:14px; color:#212121;">{ct.get("full_name", "?")}</div>'
                    f'<div style="font-size:12px; color:#757575;">{ct.get("role", "?")} &middot; {ct.get("decision_maker_type", "")} &middot; {ct.get("source", "")}</div>'
                    f'<div style="font-size:12px; color:#757575; margin-top:2px;">{email_str}{phone_html}</div>'
                    f'{wpp_html}'
                    f'</div></div></div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

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

            # clear_on_submit: sem isso os campos continuavam preenchidos apos o
            # envio, parecia que "nao foi", e o usuario clicava de novo — criando
            # contato duplicado. (O form de EDICAO acima nao leva isso: ele
            # mostra os dados atuais do registro e deve continuar mostrando.)
            with st.form("add_contact_form", clear_on_submit=True):
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

        # Busca de contatos na web (IA). Ago/2026: era Perplexity via Chrome +
        # subprocess (so Windows, 30-60s); agora e API (roda em qualquer lugar,
        # ~4s, ~R$0,02). Sem gate de ambiente — funciona tambem na VM.
        st.divider()
        if st.button(
            "Buscar contatos na web (IA)",
            icon=":material/search:",
            help=(
                "Pesquisa na web a equipe de gestao e os contatos institucionais "
                "desta escola. Costuma achar email/telefone da secretaria; nomes "
                "de diretores raramente estao publicados."
            ),
        ):
            from tools import web_search as _ws
            found = []
            if not _ws.is_available():
                st.error("Busca web indisponivel (OPENAI_API_KEY ausente).")
            else:
                # Dominio da escola: permite deduzir email de quem so tem nome
                _dom = (company.get("email_domain") or "").strip()
                if not _dom and company.get("website"):
                    _dom = re.sub(r"^https?://(www\.)?", "",
                                  company["website"]).split("/")[0].strip()
                with st.spinner("Buscando na web (alguns segundos)..."):
                    try:
                        found = _ws.search_school_contacts(
                            company.get("name", ""),
                            company.get("city", ""),
                            company.get("state", ""),
                            dominio=_dom,
                        )
                    except Exception as e:
                        found = []
                        st.error(f"Erro na busca: {e}")
                if found:
                    st.session_state["perplexity_results"] = found
                    st.session_state["perplexity_company_id"] = company_id
                    st.rerun()
                else:
                    st.warning("Nenhum contato encontrado na web. Tente Apollo/Hunter ou pesquise manualmente.")

        # --- Exibir resultados da busca web para confirmacao ---
        if st.session_state.get("perplexity_company_id") == company_id and st.session_state.get("perplexity_results"):
            found = st.session_state["perplexity_results"]
            has_suggested = any(ct.get("_suggested_email") for ct in found)
            alert_banner(f"Busca web encontrou {len(found)} contato(s). Selecione quais importar:", "success")
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
                if ct.get("phone_whatsapp"):
                    label_parts.append(f"| WhatsApp: {ct['phone_whatsapp']}")
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
                        # dict.get("k", "") retorna None se "k" existe com valor None.
                        # Usar (... or "") pra garantir string antes de .lower().
                        existing_match = [c for c in (contacts or []) if
                            ((c.get("full_name") or "").lower() == (ct.get("full_name") or "").lower()) or
                            (ct.get("email") and (c.get("email") or "").lower() == (ct.get("email") or "").lower())]
                        if existing_match:
                            continue
                        dm_type, priority = classify_role(ct.get("role", ""))
                        ct_data_new = {
                            "company_id": company_id,
                            "full_name": ct["full_name"],
                            "role": ct.get("role", ""),
                            "source": "web_search",
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
                        if ct.get("phone_whatsapp"):
                            ct_data_new["phone_whatsapp"] = ct["phone_whatsapp"]
                        if ct.get("_is_general_email"):
                            ct_data_new["decision_maker_type"] = "administrativo"
                            ct_data_new["outreach_priority"] = 99
                        if db.insert_contact(ct_data_new):
                            saved_count += 1
                    st.session_state.pop("perplexity_results", None)
                    st.session_state.pop("perplexity_company_id", None)
                    st.session_state.escola_msg = ("success", f"{saved_count} contatos importados via busca web!")
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

    # === TAB REGISTRAR CONTATO ===
    with tab_registrar:
        section_header("Registrar contato manual", "phone_in_talk")
        st.caption(
            "Use esta aba quando voce contatou (ou foi contatado pela) escola **fora** "
            "da plataforma — WhatsApp, ligacao ou email pessoal. O registro entra no "
            "Historico, atualiza `last_contacted_at` e (opcional) avanca o status."
        )

        # Buscar contatos da escola (para o seletor)
        contatos_escola: List[Dict[str, Any]] = []
        try:
            r = db.client.table("contacts").select(
                "id, full_name, role, email, phone_e164"
            ).eq("company_id", company_id).execute()
            contatos_escola = r.data or []
        except Exception:
            pass

        # clear_on_submit: mesma armadilha do form de contato — o texto ficava
        # na tela apos registrar e gerava interacao duplicada.
        with st.form(f"registrar_contato_{company_id}", clear_on_submit=True):
            r1c1, r1c2, r1c3 = st.columns([1.2, 1, 1])
            with r1c1:
                canal_pt = st.radio(
                    "Canal usado",
                    ["WhatsApp", "Ligacao", "Email"],
                    horizontal=True,
                    key=f"reg_canal_{company_id}",
                )
            with r1c2:
                direcao_pt = st.radio(
                    "Direcao",
                    ["Eu contatei", "Eles me contataram"],
                    horizontal=True,
                    key=f"reg_direcao_{company_id}",
                )
            with r1c3:
                from datetime import date as _date, datetime as _dt
                data_contato = st.date_input(
                    "Data",
                    value=_date.today(),
                    key=f"reg_data_{company_id}",
                )

            r2c1, r2c2 = st.columns([1.2, 1])
            with r2c1:
                if contatos_escola:
                    opcoes_contato = ["(nao especificar)"] + [
                        f'{c.get("full_name", "?")} - {c.get("role", "?")}'
                        for c in contatos_escola
                    ]
                    sel_contato = st.selectbox(
                        "Contato (decisor)",
                        opcoes_contato,
                        key=f"reg_contato_{company_id}",
                    )
                    contato_idx = opcoes_contato.index(sel_contato) - 1
                    contact_id_sel = (
                        contatos_escola[contato_idx]["id"]
                        if contato_idx >= 0 else None
                    )
                else:
                    st.caption("Nenhum contato cadastrado para esta escola.")
                    contact_id_sel = None
            with r2c2:
                avancar_status_chk = st.checkbox(
                    "Mover status para 'Contatado'",
                    value=True,
                    help="Aplica apenas se status atual for Novo/Filtrado/Qualificado/Enriquecido.",
                    key=f"reg_avancar_{company_id}",
                )
                avancar_kanban_chk = st.checkbox(
                    "Mover Kanban comercial para 'Contatado'",
                    value=False,
                    help="Atualiza commercial_stage (pipeline Kanban). Aplica se atual for vazio/'prospectado'.",
                    key=f"reg_kanban_{company_id}",
                )

            obs_text = st.text_area(
                "Observacao (o que conversaram, proximos passos, etc)",
                key=f"reg_obs_{company_id}",
                max_chars=500,
                placeholder="Ex: Falamos sobre matricula 2027. Pediram proposta para 80 alunos do EM.",
            )

            submit = st.form_submit_button(
                "Registrar contato", icon=":material/check_circle:"
            )

        if submit:
            CHANNEL_MAP = {"WhatsApp": "whatsapp", "Ligacao": "phone", "Email": "email"}
            DIRECTION_MAP = {"Eu contatei": "sent", "Eles me contataram": "received"}
            try:
                # Combinar data escolhida com hora atual (registro sempre tem horario)
                from datetime import datetime as _dt2
                _now = _dt2.now()
                interaction_dt = _dt2.combine(
                    data_contato,
                    _now.time().replace(microsecond=0),
                ).isoformat()

                result = db.register_manual_interaction(
                    company_id=company_id,
                    channel=CHANNEL_MAP[canal_pt],
                    direction=DIRECTION_MAP[direcao_pt],
                    contact_id=contact_id_sel,
                    notes=obs_text or "",
                    interaction_date=interaction_dt,
                    advance_status=avancar_status_chk,
                    advance_commercial_stage=avancar_kanban_chk,
                    source="dashboard",
                )
                msg_parts = [f"Contato registrado ({result['type']})"]
                if result.get("status_changed"):
                    msg_parts.append(f"status -> {result['status_changed']}")
                if result.get("commercial_stage_changed"):
                    msg_parts.append(f"kanban -> {result['commercial_stage_changed']}")
                st.session_state.escola_msg = ("success", " | ".join(msg_parts))
            except Exception as _e:
                st.session_state.escola_msg = ("error", f"Erro ao registrar: {_e}")
            st.rerun()

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

        # === OPR + GRAFICOS (F1/F2) ===
        section_header("Relatorios e Graficos", "analytics")
        _inep_report = company.get("inep_code")
        if _inep_report:
            from tools.insight_charts import charts_renderable as _can_render
            _render_ok = _can_render()
            if not _render_ok:
                alert_banner(
                    "A geracao de relatorio/graficos roda <strong>fora do app online</strong> "
                    "(local/Oracle, onde o motor de graficos funciona). Aqui voce so "
                    "<strong>abre</strong> o que ja foi gerado. Pra atualizar, rode "
                    "<code>scripts/pregenerate_artifacts.py</code> ou peca ao IAlex.",
                    "info",
                )
            rp1, rp2, rp3 = st.columns(3)
            with rp1:
                if st.button("Gerar One Page Report", icon=":material/description:",
                             key="btn_opr", disabled=not _render_ok):
                    with st.spinner("Gerando report..."):
                        try:
                            from tools.report_generator import generate_and_upload_report
                            _opr = generate_and_upload_report(str(_inep_report))
                            if _opr:
                                st.session_state["opr_result"] = _opr
                                st.session_state.escola_msg = ("success", f"Report gerado! URL: {_opr['html_url']}")
                            else:
                                st.session_state.escola_msg = ("error", "Falha ao gerar report (dados insuficientes?).")
                        except Exception as _e:
                            st.session_state.escola_msg = ("error", f"Erro: {_e}")
                    st.rerun()
            with rp2:
                if st.button("Gerar Graficos", icon=":material/bar_chart:",
                             key="btn_charts", disabled=not _render_ok):
                    with st.spinner("Gerando graficos..."):
                        try:
                            from tools.insight_charts import generate_all_relevant_charts
                            from database.supabase_client import db as _db_ch
                            _charts = generate_all_relevant_charts(str(_inep_report))
                            for _ch in _charts:
                                _db_ch.upload_chart(_ch["filename"], _ch["bytes"])
                            if _charts:
                                st.session_state["charts_result"] = _charts
                                st.session_state.escola_msg = ("success", f"{len(_charts)} grafico(s) gerado(s)!")
                            else:
                                st.session_state.escola_msg = ("error", "Nenhum grafico gerado (dados insuficientes?).")
                        except Exception as _e:
                            st.session_state.escola_msg = ("error", f"Erro: {_e}")
                    st.rerun()
            with rp3:
                _opr_data = st.session_state.get("opr_result")
                if _opr_data:
                    st.link_button("Abrir Report", _opr_data["html_url"], icon=":material/open_in_new:")

            # Mostrar graficos gerados
            _charts_data = st.session_state.get("charts_result")
            if _charts_data:
                st.markdown("**Graficos gerados:**")
                _ch_cols = st.columns(min(len(_charts_data), 3))
                for _ci, _ch in enumerate(_charts_data):
                    with _ch_cols[_ci % len(_ch_cols)]:
                        _b64 = __import__("base64").b64encode(_ch["bytes"]).decode(); st.markdown(f'<img src="data:image/png;base64,{_b64}" style="width:100%;border-radius:8px"><p style="color:#888;font-size:12px;text-align:center">{_ch.get("alt", _ch["type"])}</p>', unsafe_allow_html=True)
        else:
            st.info("Escola sem codigo INEP — nao e possivel gerar reports.")

        st.markdown('<hr class="divider">', unsafe_allow_html=True)

        section_header("Acoes", "settings")
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            queue_count = len(db.get_queue_by_company(company_id))
            if queue_count > 0:
                if st.button(f"Limpar fila ({queue_count} itens)", icon=":material/delete_sweep:"):
                    # Reporta o retorno REAL (int), nao a contagem pre-clique.
                    _n_rm = db.delete_queue_items(company_id)
                    _n_rm = queue_count if _n_rm is None else int(_n_rm)
                    st.session_state.escola_msg = ("success", f"{_n_rm} itens removidos.")
                    st.rerun()
        with ac2:
            if st.button("Resetar para Novo", icon=":material/restart_alt:"):
                if db.reset_company_status(company_id, "raw"):
                    st.session_state.escola_msg = ("success", "Status resetado.")
                else:
                    st.session_state.escola_msg = (
                        "error", "Nao foi possivel resetar o status. Nada foi alterado.")
                st.rerun()
        with ac3:
            if st.button("Excluir escola", type="primary", icon=":material/delete_forever:"):
                st.session_state["confirm_delete"] = company_id

        if st.session_state.get("confirm_delete") == company_id:
            alert_banner(f"Excluir {company.get('name')} e todos os dados relacionados?", "error")
            dc1, dc2 = st.columns(2)
            with dc1:
                if st.button("Sim, excluir tudo", type="primary"):
                    if db.delete_company(company_id):
                        invalidate_crm_schools()
                        st.session_state.escola_msg = (
                            "success", f"{company.get('name')} excluida.")
                        st.session_state.pop("confirm_delete", None)
                        go_to_list()
                    else:
                        st.session_state.escola_msg = (
                            "error", "Nao foi possivel excluir. A escola continua no banco.")
                    st.rerun()
            with dc2:
                if st.button("Cancelar"):
                    st.session_state.pop("confirm_delete", None)
                    st.rerun()

# ===========================================================================
# MODO LISTA (tabela com selecao de linha -> abre ficha na mesma tela)
# ===========================================================================
else:
    _ESC_SECOES = ["📋 Lista", "👥 Pessoas", "🔗 Redes", "🔬 Inteligencia"]
    if st.session_state.get("escolas_secao") not in _ESC_SECOES:
        st.session_state["escolas_secao"] = "📋 Lista"
    _esc_sec = st.segmented_control(
        "Secao", _ESC_SECOES, key="escolas_secao", label_visibility="collapsed",
    ) or "📋 Lista"
    if _esc_sec == "📋 Lista":
        section_header("Escolas", "school")

        # Buscar dados — inclui campos ricos do Censo 2025
        try:
            result = db.client.table("companies").select(
                "id, name, city, state, bairro, status, qualification_score, "
                "school_size, admin_dependency, admin_category, categoria_privada, "
                "inep_code, created_at, fonte_dados, "
                "matriculas_fund_af, matriculas_medio, total_docentes, "
                "qt_coordenadores, nivel_tecnologico, urgency_score, urgency_tier, "
                "commercial_stage, owner_username, latitude, longitude"
            ).order("created_at", desc=True).limit(1000).execute()
            rows = result.data or []
        except Exception as e:
            st.error(f"Erro ao carregar escolas: {e}")
            st.stop()

        if not rows:
            alert_banner("Nenhuma escola importada. Use 🔍 Prospectar → Buscar no Brasil para comecar.", "info")
            st.stop()

        df = pd.DataFrame(rows)

        # Preparar colunas para exibicao
        df["Status"] = df["status"].map(lambda x: STATUS_PT.get(x, x))
        df["Score"] = df["qualification_score"].fillna(0).astype(int)
        df["Porte"] = df["school_size"].fillna("").map(lambda x: PORTE_SHORT.get(x.strip(), x[:15] if x else ""))
        df["Tipo"] = df["admin_dependency"].fillna("")
        df["UF"] = df["state"].fillna("")
        df["Cidade"] = df["city"].fillna("")  # filtro de cidade le df["Cidade"] (nao "city")
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

        # v2 (mockup escolas.html): Etapa unica (labels), Potencial R$/mes e Dono
        from dashboard.labels import school_stage_label as _stage_lbl
        _cs = df["commercial_stage"] if "commercial_stage" in df.columns else None
        df["Etapa"] = [
            _stage_lbl(s_, (_cs.iloc[i] if _cs is not None else None))
            for i, s_ in enumerate(df["status"].fillna("raw"))
        ]
        try:
            from integrations.agenda_config import agenda_config as _ag_cfg
            _ticket = float(_ag_cfg.ticket_por_aluno())
        except Exception:
            _ticket = 7.99
        df["Potencial R$"] = ((df["Fund AF"] + df["Medio"]) * _ticket).round(0).astype(int)
        df["Dono"] = (df["owner_username"] if "owner_username" in df.columns
                      else "").fillna("—")

        # F2: Urgency badge
        try:
            from dashboard.helpers.urgency_widgets import urgency_badge_text
            df["Urgencia"] = df["urgency_tier"].fillna("COLD").map(urgency_badge_text)
        except Exception:
            df["Urgencia"] = "-"

        # --- Enriquecer com school_analytics (UI12b — fetch separado, falha silenciosa) ---
        # Regra R6 do plano: NUNCA fazer LEFT JOIN. Fetch separado in-memory merge.
        # Se analytics indisponivel, a coluna Potencial vem vazia e tabela nao quebra.
        inep_list = [str(x).strip() for x in df["inep_code"].dropna().tolist() if x]
        analytics_map = _fetch_analytics_by_inep_list(tuple(inep_list)) if inep_list else {}
        df["Potencial"] = df["inep_code"].apply(
            lambda i: _potencial_badge(analytics_map.get(str(i).strip()) if i else None)
        )
        df["Gap ENEM"] = df["inep_code"].apply(
            lambda i: (
                float(analytics_map.get(str(i).strip(), {}).get("enem_gap_vs_peer_2025") or 0)
                if i and analytics_map.get(str(i).strip(), {}).get("enem_amostra_confiavel")
                else None
            )
        )
        df["Trajet. Peer"] = df["inep_code"].apply(
            lambda i: (analytics_map.get(str(i).strip(), {}) or {}).get("peer_trajetoria_6y") or "—"
        )

        # --- Filtros inline (barra horizontal) ---
        st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
        fc1, fc2, fc3, fc4 = st.columns([3, 2, 2, 2])
        with fc1:
            from dashboard.helpers.school_lookup import get_crm_schools as _get_crm, format_school_option as _fmt_crm, parse_inep_from_option as _parse_crm
            _crm_list = _get_crm()
            _crm_opts = ["(todas)"] + [_fmt_crm(n, i) for n, i in _crm_list]
            search_sel = st.selectbox("Buscar escola", _crm_opts, label_visibility="collapsed",
                                     key="search_escola")
            search = ""  # compatibilidade com filtro existente abaixo
            if search_sel != "(todas)":
                _parsed_inep = _parse_crm(search_sel)
                if _parsed_inep:
                    search = _parsed_inep  # filtra por INEP (exato)
                else:
                    search = search_sel  # fallback: filtra por texto
        with fc2:
            # key= porque as OPCOES vem dos dados: sem ela, a identidade do
            # widget muda junto com a lista (importar escolas, alterar status em
            # massa, excluir a ultima escola de um status) e o filtro volta
            # sozinho para o default. Os demais filtros desta barra tem opcoes
            # literais, entao sao estaveis e nao precisam de key.
            all_statuses_pt = sorted(df["Status"].unique().tolist())
            sel_status = st.multiselect("Status", all_statuses_pt, default=all_statuses_pt,
                                        label_visibility="collapsed", placeholder="Filtrar status...",
                                        key="esc_flt_status")
        with fc3:
            all_types = sorted([t for t in df["Tipo"].dropna().unique().tolist() if t])
            sel_type = st.multiselect("Tipo", all_types, default=[], label_visibility="collapsed",
                                      placeholder="Filtrar tipo...", key="esc_flt_tipo")
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

        # Terceira linha: filtros ENEM analytics
        fc10, fc11, fc12 = st.columns([2, 2, 2])
        with fc10:
            pot_options = ["🔥 Alto", "🟡 Medio", "🟢 Baixo"]
            sel_pot = st.multiselect("Potencial", pot_options, default=[],
                                      label_visibility="collapsed",
                                      placeholder="Potencial ENEM...")
        with fc11:
            traj_options = ["Subindo forte", "Subindo", "Estavel", "Caindo", "Caindo forte"]
            sel_traj = st.multiselect("Trajet.", traj_options, default=[],
                                       label_visibility="collapsed",
                                       placeholder="Trajet. peer...")
        with fc12:
            max_gap = st.number_input("Max gap", min_value=-200, max_value=200, value=200, step=5,
                                       label_visibility="collapsed",
                                       placeholder="Max gap peer (negativo=oportunidade)",
                                       help="So escolas com gap <= este valor. -10 retorna escolas com gap <= -10 pts (abaixo do peer).")

        # Quarta linha: GEOGRAFICOS — UF + Cidade (cascata UF -> Cidade)
        # Padrao do Mapa.py / Importar.py (multiselect com cascata).
        fc_uf, fc_city, fc_owner, _fc_filler = st.columns([1.2, 2.4, 1.3, 1.1])
        with fc_uf:
            _all_ufs_esc = sorted([u for u in df["UF"].dropna().unique().tolist() if u]) if "UF" in df.columns else []
            sel_uf_esc = st.multiselect(
                "UF", _all_ufs_esc, default=[],
                label_visibility="collapsed", placeholder="UF...",
                key="esc_filter_uf",
            )
        with fc_city:
            # Cascata: cidades disponiveis dependem da UF selecionada
            if "Cidade" in df.columns:
                if sel_uf_esc:
                    _city_pool = df[df["UF"].isin(sel_uf_esc)]["Cidade"]
                else:
                    _city_pool = df["Cidade"]
                _all_cities_esc = sorted([c for c in _city_pool.dropna().unique().tolist() if c])
            else:
                _all_cities_esc = []
            sel_city_esc = st.multiselect(
                "Cidade", _all_cities_esc, default=[],
                label_visibility="collapsed", placeholder="Cidade...",
                key="esc_filter_city",
            )
        with fc_owner:
            _all_owners = sorted([o for o in df["Dono"].dropna().unique().tolist()
                                  if o and o != "—"]) if "Dono" in df.columns else []
            sel_owner_esc = st.multiselect(
                "Dono", _all_owners, default=[],
                label_visibility="collapsed", placeholder="Dono...",
                key="esc_filter_owner",
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Aplicar filtros
        df_f = df.copy()
        if sel_status:
            df_f = df_f[df_f["Status"].isin(sel_status)]
        if sel_type:
            df_f = df_f[df_f["Tipo"].isin(sel_type)]
        df_f = df_f[(df_f["Score"] >= score_range[0]) & (df_f["Score"] <= score_range[1])]
        if search:
            # Se search e um INEP (so digitos), filtra exato; senao busca por texto
            if search.isdigit():
                df_f = df_f[df_f["inep_code"].astype(str).str.strip() == search]
            else:
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
        if sel_pot:
            df_f = df_f[df_f["Potencial"].isin(sel_pot)]
        if sel_traj:
            df_f = df_f[df_f["Trajet. Peer"].isin(sel_traj)]
        if max_gap < 200:
            df_f = df_f[(df_f["Gap ENEM"].notna()) & (df_f["Gap ENEM"] <= max_gap)]
        # Filtros geograficos UF / Cidade
        if sel_uf_esc and "UF" in df_f.columns:
            df_f = df_f[df_f["UF"].isin(sel_uf_esc)]
        if sel_city_esc and "Cidade" in df_f.columns:
            df_f = df_f[df_f["Cidade"].isin(sel_city_esc)]
        if sel_owner_esc and "Dono" in df_f.columns:
            df_f = df_f[df_f["Dono"].isin(sel_owner_esc)]

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
        # Mesmo tratamento do renderizador da ficha (linha ~1010): 'warning' e
        # qualquer tipo desconhecido tem que aparecer. Este renderizador
        # descartava 'warning' em silencio — e e ele que recebe o resultado das
        # acoes em lote da lista ("alterado em N de M").
        if st.session_state.escola_msg:
            msg_type, msg_text = st.session_state.escola_msg
            if msg_type in ("success", "error", "info", "warning"):
                alert_banner(msg_text, msg_type)
            else:
                alert_banner(str(msg_text), "info")
            st.session_state.escola_msg = None

        # --- Alternador Tabela/Mapa (rodada 5 — pedido do dono/mockup) ---
        _ver_como = st.segmented_control(
            "Ver como", ["📋 Tabela", "🗺️ Mapa"],
            key="escolas_ver_como", label_visibility="collapsed",
        ) or "📋 Tabela"
        if _ver_como == "📋 Tabela":
            # --- Tabela interativa com selecao por clique ---
            _ALL_COLS = [c for c in [
                "name", "city", "UF", "Bairro", "Etapa", "Fund AF", "Medio",
                "Potencial R$", "Urgencia", "Dono", "Tipo", "Porte", "Tech",
                "Potencial", "Gap ENEM", "Trajet. Peer", "Coord", "Fit",
                "Score", "Status", "Fonte", "Importado",
            ] if c in df_f.columns]
            _COL_PRESETS = {
                "Comercial": ["name", "city", "UF", "Etapa", "Fund AF", "Medio",
                              "Potencial R$", "Urgencia", "Fit", "Dono"],
                "Essencial": ["name", "city", "UF", "Etapa", "Potencial R$", "Dono"],
                "Censo & ENEM": ["name", "city", "UF", "Tipo", "Porte", "Fund AF",
                                 "Medio", "Tech", "Coord", "Potencial", "Gap ENEM",
                                 "Trajet. Peer"],
                "Tudo": list(_ALL_COLS),
            }
            with st.popover("Colunas", icon=":material/view_column:"):
                _preset = st.radio(
                    "Conjunto", list(_COL_PRESETS.keys()), horizontal=True,
                    key="esc_cols_preset",
                )
                _default_cols = [c for c in _COL_PRESETS[_preset] if c in _ALL_COLS]
                table_cols = st.multiselect(
                    "Colunas visiveis", _ALL_COLS, default=_default_cols,
                    key=f"esc_cols_custom_{_preset}",
                    format_func=lambda c: {"name": "Escola", "city": "Cidade"}.get(c, c),
                )
            if not table_cols:
                table_cols = _COL_PRESETS["Comercial"]
            table_cols = [c for c in table_cols if c in df_f.columns]
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
                "Potencial": st.column_config.TextColumn(
                    "Potencial ENEM", width="small", disabled=True,
                    help=f"Potencial de melhoria ENEM {ENEM_VINTAGE} (Alto=🔥 / Medio=🟡 / Baixo=🟢 / —=sem amostra confiavel)",
                ),
                "Gap ENEM": st.column_config.NumberColumn(
                    "Gap peer", width="small", disabled=True, format="%+.1f",
                    help=f"Gap (pts) vs peer group em {ENEM_VINTAGE}. Negativo=abaixo dos pares (oportunidade).",
                ),
                "Trajet. Peer": st.column_config.TextColumn(
                    "Trajet. peer", width="small", disabled=True,
                    help="Trajetoria 5 anos do peer group (escolas do mesmo municipio × mesma dependencia). NAO e da escola individual.",
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
                "Etapa": st.column_config.TextColumn(
                    "Etapa", width="small", disabled=True,
                    help="Etapa unica da escola no funil (status + kanban)",
                ),
                "Potencial R$": st.column_config.NumberColumn(
                    "Potencial R$/mes", width="small", disabled=True, format="R$ %d",
                    help="Alunos-alvo (Fund AF + Medio) x ticket por aluno",
                ),
                "Urgencia": st.column_config.TextColumn(
                    "Prioridade", width="small", disabled=True,
                    help="Prioridade de atendimento (score de urgencia 0-100)",
                ),
                "Dono": st.column_config.TextColumn(
                    "Dono", width="small", disabled=True,
                    help="Vendedor responsavel pela escola",
                ),
                "Porte": st.column_config.TextColumn("Porte", width="small", disabled=True),
                "Fonte": st.column_config.TextColumn("Fonte", width="small", disabled=True),
                "Importado": st.column_config.TextColumn("Importado", width="small", disabled=True),
            }

            # Sinalizacao de contagem (1.1 Quick Win): total/filtrado/filtros ativos
            from dashboard._table_count import render_count, summarize_filters
            _filter_summary = summarize_filters({
                "status": sel_status if sel_status else None,
                "tipo": sel_type if sel_type else None,
                "score": f"{score_range[0]}-{score_range[1]}" if (score_range[0] > 0 or score_range[1] < 100) else None,
                "tech": sel_tech if sel_tech else None,
                "fonte": sel_fonte if sel_fonte else None,
                "fund>=": min_fund if min_fund > 0 else None,
                "medio>=": min_medio if min_medio > 0 else None,
                "fit>=": min_fit if min_fit > 0 else None,
                "potencial": sel_pot if sel_pot else None,
                "trajetoria": sel_traj if sel_traj else None,
                "gap<=": max_gap if max_gap < 200 else None,
                "busca": search if search else None,
                "dono": sel_owner_esc if sel_owner_esc else None,
            })
            render_count(
                total=len(df),
                filtered=len(df_f),
                filter_summary=_filter_summary,
                label_singular="escola",
                label_plural="escolas",
            )
            st.caption("Marque as caixas para acoes em grupo (status, exportar, excluir). "
                       "Para abrir uma ficha, selecione 1 escola e clique 'Abrir ficha' "
                       "(ou use o seletor por nome abaixo).")

            df_f_reset = df_f.reset_index(drop=True)
            # A selecao do st.dataframe e POSICIONAL e o Streamlit NAO a reseta
            # quando os dados mudam (ver dashboard/helpers/table_select.py).
            # Sem isto, mudar um filtro faz "Excluir (3)" apagar OUTRAS 3 escolas
            # — ou estourar IndexError se a lista nova for menor.
            _sel_dropped = reset_if_rows_changed("escola_table", df_f_reset["id"].tolist())
            _tbl_event = st.dataframe(
                df_f_reset[table_cols],
                use_container_width=True,
                hide_index=True,
                column_config=col_config,
                key="escola_table",
                on_select="rerun",
                selection_mode="multi-row",
            )
            if _sel_dropped:
                st.caption("A lista mudou (filtro ou ordenacao) — a selecao anterior "
                           "foi limpa para nao agir na escola errada.")
            # Checkbox = SELECIONAR escolas p/ acao em grupo (nao navega).
            _sel_rows = selected_positions(_tbl_event, len(df_f_reset))
            _sel_ids = [df_f_reset.iloc[i]["id"] for i in _sel_rows]
            _sel_names = [df_f_reset.iloc[i]["name"] for i in _sel_rows]
            if not _sel_ids:
                # Sem selecao, a confirmacao pendente perde o alvo: limpar pra nao
                # reaparecer aberta na proxima selecao (o "vermelho ja veio ligado").
                st.session_state.pop("confirm_sel_delete", None)

            # --- Barra de SELECAO (so quando ha escolas marcadas) ---
            if _sel_ids:
                st.markdown(
                    f'<p style="font-size:12px;font-weight:600;color:#1976D2;'
                    f'text-transform:uppercase;letter-spacing:0.5px;margin:12px 0 4px">'
                    f'{len(_sel_ids)} escola(s) selecionada(s)</p>',
                    unsafe_allow_html=True,
                )
                _sb1, _sb2, _sb3, _sb4 = st.columns([1.2, 2, 1.2, 1.2])
                with _sb1:
                    if st.button(
                        "📄 Abrir ficha", type="primary", use_container_width=True,
                        disabled=(len(_sel_ids) != 1),
                        help="Selecione exatamente 1 escola para abrir a ficha.",
                    ):
                        go_to_detail(_sel_ids[0])
                        st.rerun()
                with _sb2:
                    _sel_new_st = st.selectbox(
                        "Alterar status:", list(STATUS_PT.values()),
                        key="sel_bulk_status", label_visibility="collapsed",
                    )
                with _sb3:
                    if st.button(f"Alterar status ({len(_sel_ids)})",
                                 icon=":material/edit:", use_container_width=True):
                        _en = PT_TO_EN.get(_sel_new_st, "raw")
                        # Conta o que REALMENTE mudou: antes a mensagem afirmava
                        # o total selecionado mesmo se todas as chamadas falhassem.
                        _ok_n = sum(1 for _cid in _sel_ids
                                    if db.reset_company_status(_cid, _en))
                        if _ok_n < len(_sel_ids):
                            st.session_state.escola_msg = (
                                "warning",
                                f"Status alterado em {_ok_n} de {len(_sel_ids)} escola(s). "
                                f"As demais nao foram alteradas.")
                        else:
                            st.session_state.escola_msg = (
                                "success", f"Status de {_ok_n} escola(s) alterado.")
                        st.rerun()
                with _sb4:
                    if st.button(f"Excluir ({len(_sel_ids)})",
                                 icon=":material/delete:", use_container_width=True):
                        # Flag booleana, NAO snapshot de ids: a lista e relida ao
                        # confirmar, entao o que o banner diz e o que e apagado.
                        st.session_state["confirm_sel_delete"] = True

                # Exportar selecionadas (XLSX, colunas visiveis)
                try:
                    import io as _io_sel
                    _buf_sel = _io_sel.BytesIO()
                    _exp_sel_cols = [c for c in (["inep_code"] + table_cols)
                                     if c in df_f_reset.columns]
                    with pd.ExcelWriter(_buf_sel, engine="openpyxl") as _xw_sel:
                        # _sel_rows ja vem com clamp (table_select.selected_positions)
                        df_f_reset.iloc[_sel_rows][_exp_sel_cols].to_excel(
                            _xw_sel, index=False, sheet_name="Selecionadas")
                    st.download_button(
                        f"Exportar selecionadas ({len(_sel_ids)}) XLSX",
                        _buf_sel.getvalue(), "escolas_selecionadas.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        icon=":material/download:", key="sel_export_xlsx",
                    )
                except Exception:
                    pass

                # Confirmacao de exclusao das selecionadas (chave propria p/ nao
                # colidir com "Acoes em massa")
                if st.session_state.get("confirm_sel_delete"):
                    # Ao vivo: reflete a selecao que esta na tela AGORA.
                    _ids_del = list(_sel_ids)
                    alert_banner(
                        f"Confirma exclusao de {len(_ids_del)} escola(s) e todos os dados?",
                        "error")
                    _dc1, _dc2 = st.columns(2)
                    with _dc1:
                        if st.button("Sim, excluir selecionadas", type="primary",
                                     key="confirm_del_sel"):
                            _n = db.bulk_delete_companies(_ids_del)
                            invalidate_crm_schools()
                            st.session_state.escola_msg = ("success", f"{_n} escola(s) excluida(s).")
                            st.session_state.pop("confirm_sel_delete", None)
                            st.rerun()
                    with _dc2:
                        if st.button("Cancelar", key="cancel_del_sel"):
                            st.session_state.pop("confirm_sel_delete", None)
                            st.rerun()

                st.divider()

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
                        if db.reset_company_status(cid, new_en):
                            st.session_state.escola_msg = (
                                "success", f"Status alterado para {new_st}.")
                        else:
                            st.session_state.escola_msg = (
                                "error", "Nao foi possivel alterar o status. Nada mudou.")
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
                        if db.delete_company(del_id):
                            invalidate_crm_schools()
                            st.session_state.escola_msg = ("success", f"{del_name} excluida.")
                        else:
                            st.session_state.escola_msg = (
                                "error", f"Nao foi possivel excluir {del_name}. "
                                         f"A escola continua no banco.")
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
                        _alvo = df_f["id"].tolist()
                        _ok_b = sum(1 for cid in _alvo if db.reset_company_status(cid, new_en))
                        if _ok_b < len(_alvo):
                            st.session_state.escola_msg = (
                                "warning",
                                f"Status alterado em {_ok_b} de {len(_alvo)} escolas. "
                                f"As demais nao foram alteradas.")
                        else:
                            st.session_state.escola_msg = (
                                "success", f"Status de {_ok_b} escolas alterado.")
                        st.rerun()
                with am_col3:
                    if st.button(f"Excluir {len(df_f)} escolas", icon=":material/delete_forever:",
                                  use_container_width=True):
                        # Flag booleana, NAO snapshot: se o filtro mudar antes de
                        # confirmar, o banner e a exclusao seguem o filtro ATUAL.
                        st.session_state["confirm_bulk_delete"] = True

                if st.session_state.get("confirm_bulk_delete"):
                    ids_to_del = df_f["id"].tolist()
                    alert_banner(f"Confirma exclusao de {len(ids_to_del)} escolas e todos os dados?", "error")
                    cd1, cd2 = st.columns(2)
                    with cd1:
                        if st.button("Sim, excluir tudo", type="primary"):
                            deleted = db.bulk_delete_companies(ids_to_del)
                            invalidate_crm_schools()
                            st.session_state.escola_msg = ("success", f"{deleted} escolas excluidas.")
                            st.session_state.pop("confirm_bulk_delete", None)
                            st.rerun()
                    with cd2:
                        if st.button("Cancelar", key="cancel_del"):
                            st.session_state.pop("confirm_bulk_delete", None)
                            st.rerun()

            # --- Exportar (1-clique, respeita filtros + colunas visiveis) ---
            st.divider()
            _exp_cols = [c for c in (["inep_code"] + table_cols) if c in df_f.columns]
            _exp_x, _exp_c, _ = st.columns([1.6, 1, 3.4])
            with _exp_x:
                import io as _io
                try:
                    _buf = _io.BytesIO()
                    with pd.ExcelWriter(_buf, engine="openpyxl") as _xw:
                        df_f[_exp_cols].to_excel(_xw, index=False, sheet_name="Escolas")
                    st.download_button(
                        "Exportar XLSX", _buf.getvalue(), "escolas.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        icon=":material/download:", type="primary",
                        help="Escolas filtradas, com as colunas visiveis na tabela",
                    )
                except Exception:
                    pass
            with _exp_c:
                csv = df_f[_exp_cols].to_csv(index=False)
                st.download_button("CSV", csv, "escolas.csv", "text/csv")
        else:
            from dashboard.helpers.mapa_view import render_mapa_escolas
            render_mapa_escolas(df_f)

    elif _esc_sec == "👥 Pessoas":
        from dashboard.helpers.contatos_view import render_contatos
        render_contatos()

    elif _esc_sec == "🔗 Redes":
        render_redes_view()

    elif _esc_sec == "🔬 Inteligencia":
        from dashboard.helpers.inteligencia_view import render_inteligencia
        render_inteligencia()