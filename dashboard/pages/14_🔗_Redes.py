"""Pagina 14 - Redes Educacionais: agrupa escolas do banco por CNPJ mantenedora,
mostra oportunidades de venda em rede (negociar uma vez, fechar varias unidades).
"""
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, section_header, alert_banner,
    breadcrumb, metric_card, COLORS,
)
from database.supabase_client import db
from agent.brain import _derivar_nome_rede

apply_theme_no_config()
breadcrumb(["IAprendo", "Redes Educacionais"])
st.markdown("# 🔗 Redes Educacionais")
st.caption(
    "Escolas do banco agrupadas por CNPJ da mantenedora. Oportunidades de venda em rede — "
    "negociar uma vez e fechar todas as unidades."
)

# =============================================================================
# LOAD DATA
# =============================================================================
@st.cache_data(ttl=300)
def load_redes():
    """Carrega escolas com mantenedora e agrupa por CNPJ."""
    try:
        r = db.client.table("companies").select(
            "id,name,city,state,bairro,status,qualification_score,"
            "cnpj_mantenedora,cnpj_escola,categoria_privada,"
            "total_matriculas,matriculas_fund_af,matriculas_medio,"
            "total_docentes,qt_coordenadores,total_turmas,nivel_tecnologico,fonte_dados"
        ).not_.is_("cnpj_mantenedora", "null").execute()
    except Exception as e:
        st.error(f"Erro ao carregar escolas: {e}")
        return {}

    grupos = defaultdict(list)
    for e in r.data or []:
        cnpj = e.get("cnpj_mantenedora")
        if cnpj:
            grupos[cnpj].append(e)
    return grupos


grupos = load_redes()

if not grupos:
    alert_banner(
        "Nenhuma escola com CNPJ de mantenedora encontrada. Rode o update_existing_schools.py "
        "para preencher os dados do Censo 2025.",
        "info",
    )
    st.stop()

# =============================================================================
# BUILD redes summary
# =============================================================================
redes = []
for cnpj, escolas in grupos.items():
    if len(escolas) < 2:
        continue  # so grupos com 2+ unidades sao 'redes'
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

    # Nivel tec predominante
    tech_counts = defaultdict(int)
    for e in escolas:
        t = e.get("nivel_tecnologico") or "Sem dado"
        tech_counts[t] += 1
    tech_predom = max(tech_counts.items(), key=lambda x: x[1])[0]

    redes.append({
        "cnpj": cnpj,
        "nome_rede": _derivar_nome_rede(escolas),
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

# Escolas singleton (sem rede — 1 unidade por CNPJ)
singletons_cnpjs = [cnpj for cnpj, esc in grupos.items() if len(esc) == 1]
n_singletons = len(singletons_cnpjs)

# =============================================================================
# METRICAS TOPO
# =============================================================================
total_escolas_em_rede = sum(r["unidades"] for r in redes)
total_alvo_rede = sum(r["alunos_alvo"] for r in redes)

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    metric_card("Redes identificadas", len(redes), COLORS["primary"], icon="hub")
with mc2:
    metric_card(
        "Escolas em rede",
        f"{total_escolas_em_rede}",
        COLORS["accent"],
        icon="account_tree",
    )
with mc3:
    metric_card(
        "Alunos alvo (redes)",
        f"{total_alvo_rede:,}".replace(",", "."),
        COLORS["info"],
        icon="groups",
    )
with mc4:
    metric_card(
        "Escolas independentes",
        n_singletons,
        COLORS["secondary"],
        icon="domain_disabled",
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# FILTROS + ORDENAR
# =============================================================================
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
    )

ordem_map = {
    "Alunos alvo (maior)": lambda r: -r["alunos_alvo"],
    "Unidades (mais)": lambda r: -r["unidades"],
    "Score medio (maior)": lambda r: -r["score_medio"],
    "Nome da rede": lambda r: r["nome_rede"],
}
redes_filt = [r for r in redes if r["unidades"] >= min_unid]
redes_filt.sort(key=ordem_map[ordenar_por])

# =============================================================================
# GRAFICO GERAL: Top 10 redes por alunos alvo
# =============================================================================
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
        df_top,
        y="Rede",
        x="Alunos alvo",
        orientation="h",
        color="Tech",
        color_discrete_map={
            "Alto": COLORS["success"],
            "Medio": COLORS["warning"],
            "Médio": COLORS["warning"],
            "Baixo": COLORS["error"],
            "Sem dado": "#bdbdbd",
        },
        text="Alunos alvo",
        hover_data=["Unidades", "Score medio"],
        height=420,
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(
        yaxis=dict(autorange="reversed", title=""),
        xaxis_title="Alunos alvo (Fund AF + Medio)",
        margin=dict(l=0, r=60, t=10, b=0),
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# CARDS DAS REDES
# =============================================================================
section_header(f"Detalhes das {len(redes_filt)} redes", "account_tree")

if not redes_filt:
    alert_banner("Nenhuma rede encontrada com os filtros atuais.", "info")
    st.stop()

for rede in redes_filt:
    # Header da rede (card)
    tech_color_map = {
        "Alto": COLORS["success"],
        "Medio": COLORS["warning"],
        "Médio": COLORS["warning"],
        "Baixo": COLORS["error"],
    }
    tech_color = tech_color_map.get(rede["tech_predom"], "#bdbdbd")

    with st.expander(
        f"🏫 **{rede['nome_rede']}** · {rede['unidades']} unidades · "
        f"{rede['alunos_alvo']:,} alunos alvo · score {rede['score_medio']}".replace(",", "."),
        expanded=(rede == redes_filt[0]),  # so a primeira expandida
    ):
        # Metricas da rede
        rm1, rm2, rm3, rm4 = st.columns(4)
        with rm1:
            metric_card("Unidades", rede["unidades"], COLORS["primary"], icon="domain")
        with rm2:
            metric_card(
                "Alunos alvo",
                f"{rede['alunos_alvo']:,}".replace(",", "."),
                COLORS["accent"],
                icon="track_changes",
            )
        with rm3:
            metric_card(
                "Docentes totais",
                f"{rede['docentes']:,}".replace(",", "."),
                COLORS["info"],
                icon="record_voice_over",
            )
        with rm4:
            metric_card(
                "Coordenadores",
                rede["coordenadores"],
                COLORS["secondary"],
                icon="supervisor_account",
            )

        # Metadata
        cnpj_display = rede["cnpj"]
        cidades_str = ", ".join(rede["cidades"])
        ufs_str = ", ".join(rede["ufs"])
        st.caption(
            f"**CNPJ mantenedora:** {cnpj_display} · **Cidades:** {cidades_str} · "
            f"**UFs:** {ufs_str} · **Nivel tec predominante:** {rede['tech_predom']}"
        )

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
            use_container_width=True,
            hide_index=True,
            column_config={
                "Alvo": st.column_config.NumberColumn("Alvo", help="Fund AF + Medio"),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
            },
        )

        # Quick action: abrir a primeira unidade no detalhe
        ac1, ac2 = st.columns([2, 1])
        with ac1:
            escola_sel = st.selectbox(
                "Abrir unidade:",
                df_unid["Escola"].tolist(),
                key=f"sel_{rede['cnpj']}",
                label_visibility="collapsed",
            )
        with ac2:
            if st.button("Ver detalhe", key=f"btn_{rede['cnpj']}",
                          icon=":material/open_in_new:",
                          use_container_width=True):
                sel_id = df_unid[df_unid["Escola"] == escola_sel]["id"].iloc[0]
                st.session_state["escola_detail_id"] = sel_id
                st.switch_page("pages/5_🏫_Escolas.py")

# =============================================================================
# DICA
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.info(
    "💡 **Dica de venda em rede:** abordar a mantenedora permite negociar uma unica vez "
    "e fechar varias unidades simultaneamente. Para redes grandes (Marista, La Salle, "
    "Sinodal, etc.) vale tentar contato direto com a coordenacao nacional/regional. "
    "Pergunte ao IAlex 'me mostra a rede X' para ver todas as unidades e contatos disponiveis."
)
