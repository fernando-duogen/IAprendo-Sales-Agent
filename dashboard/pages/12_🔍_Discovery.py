"""Pagina 12 - Discovery: descoberta inteligente de escolas alem do MEC (Item 8).

Permite ao Fernando:
- Buscar escolas novas via Perplexity (cidade, tipo, keyword)
- Revisar escolas em staging (status='discovered')
- Aprovar/rejeitar em lote
- Buscar sinais contextuais (rankings, premios, noticias)
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config,
    alert_banner,
    breadcrumb,
    metric_card,
    section_header,
    COLORS,
)
from database.supabase_client import db
from tools.discovery_engine import discovery_engine

apply_theme_no_config()

# =============================================================================
# Header
# =============================================================================
breadcrumb(["IAprendo", "Discovery"])
st.markdown("# 🔍 Discovery inteligente")
st.caption(
    "Descubra escolas que NAO estao no CSV MEC via Perplexity e busque sinais "
    "contextuais (rankings, premios, noticias). Escolas novas entram em staging "
    "para sua revisao antes do pipeline."
)

# =============================================================================
# Metricas topo
# =============================================================================
try:
    stats_discovered = db.client.table("companies").select(
        "id", count="exact"
    ).eq("status", "discovered").execute()
    n_discovered = stats_discovered.count or 0
except Exception:
    n_discovered = 0

try:
    stats_raw = db.client.table("companies").select(
        "id", count="exact"
    ).eq("status", "raw").execute()
    n_raw = stats_raw.count or 0
except Exception:
    n_raw = 0

try:
    stats_rejected = db.client.table("companies").select(
        "id", count="exact"
    ).eq("status", "rejected").execute()
    n_rejected = stats_rejected.count or 0
except Exception:
    n_rejected = 0

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    metric_card("Em staging", n_discovered, color=COLORS["info"], icon="📥")
with col_m2:
    metric_card("No pipeline (raw)", n_raw, color=COLORS["primary"], icon="🎯")
with col_m3:
    metric_card("Rejeitadas", n_rejected, color="#9E9E9E", icon="🗑️")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 1 - Buscar novas escolas
# =============================================================================
section_header("Buscar novas escolas", "search")

with st.form("discovery_form"):
    col_a, col_b = st.columns(2)
    with col_a:
        cidade = st.text_input(
            "Cidade *",
            placeholder="Ex: Canoas, Porto Alegre, Sao Paulo",
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
            placeholder="Ex: bilingue, integral, Waldorf, Montessori",
        )
        limite = st.number_input(
            "Limite",
            min_value=1, max_value=30, value=10, step=1,
        )

    submit = st.form_submit_button("🔍 Buscar agora", type="primary", use_container_width=True)

if submit:
    if not cidade or len(cidade.strip()) < 2:
        st.error("Informe uma cidade valida.")
    else:
        with st.spinner(f"Buscando escolas {tipo} em {cidade}... (pode levar 30-90 segundos)"):
            try:
                result = discovery_engine.discover_schools(
                    cidade=cidade.strip(),
                    tipo=tipo,
                    keyword=keyword.strip(),
                    limit=int(limite),
                )
                novas = result.get("novas", [])
                existentes = result.get("existentes_atualizadas", [])
                erros = result.get("erros", [])

                if novas:
                    st.success(
                        f"✅ {len(novas)} nova(s) escola(s) em staging. "
                        f"Revise abaixo antes de aprovar."
                    )
                if existentes:
                    st.info(
                        f"ℹ️ {len(existentes)} escola(s) ja existia(m) no banco — "
                        f"sinal de discovery foi registrado no perfil."
                    )
                if erros:
                    alert_banner(
                        f"⚠️ Avisos: {'; '.join(erros[:3])}",
                        "warning",
                    )
                if not novas and not existentes:
                    alert_banner(
                        "Nenhuma escola retornada. Tente outra cidade, outro tipo ou "
                        "um keyword diferente. Verifique tambem se o Perplexity esta logado.",
                        "info",
                    )
            except Exception as e:
                st.error(f"Erro na busca: {e}")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 2 - Staging (revisao)
# =============================================================================
section_header("Staging — escolas aguardando revisao", "inbox")

col_filter1, col_filter2 = st.columns([2, 1])
with col_filter1:
    filter_cidade = st.text_input(
        "Filtrar por cidade",
        placeholder="Deixe vazio para ver todas",
        key="staging_filter_city",
    )
with col_filter2:
    refresh = st.button("🔄 Atualizar lista", use_container_width=True)

discovered = discovery_engine.list_discovered(
    limit=100,
    cidade=filter_cidade.strip() if filter_cidade else None,
)

if not discovered:
    st.info("📭 Nenhuma escola em staging no momento. Use o formulario acima para descobrir novas.")
else:
    # Montar dataframe
    rows = []
    for s in discovered:
        rows.append({
            "id": s["id"],
            "Nome": s.get("name", ""),
            "Cidade": s.get("city", ""),
            "UF": s.get("state", ""),
            "Tipo": s.get("admin_category", ""),
            "Site": s.get("website") or "",
            "Telefone": s.get("phone") or "",
            "Fonte": s.get("source", ""),
            "Descoberta em": (s.get("created_at") or "")[:10],
        })
    df = pd.DataFrame(rows)

    st.caption(f"Total em staging: **{len(df)}** escola(s). Selecione para aprovar ou rejeitar em lote.")

    # Dataframe com selecao multipla
    event = st.dataframe(
        df.drop(columns=["id"]),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="discovered_df",
    )

    selected_rows = event.selection.rows if event.selection else []
    selected_ids = [df.iloc[i]["id"] for i in selected_rows] if selected_rows else []

    if selected_ids:
        st.markdown(f"**{len(selected_ids)} escola(s) selecionada(s)**")
        col_act1, col_act2, col_act3 = st.columns(3)
        with col_act1:
            if st.button("✅ Aprovar selecionadas", type="primary", use_container_width=True):
                ok_count = 0
                for cid in selected_ids:
                    if discovery_engine.promote_to_raw(cid):
                        ok_count += 1
                st.success(f"✅ {ok_count}/{len(selected_ids)} escola(s) promovida(s) para 'raw'.")
                st.rerun()
        with col_act2:
            if st.button("❌ Rejeitar selecionadas", use_container_width=True):
                ok_count = 0
                for cid in selected_ids:
                    if discovery_engine.reject(cid, reason="rejeicao manual"):
                        ok_count += 1
                st.success(f"✅ {ok_count}/{len(selected_ids)} escola(s) rejeitada(s).")
                st.rerun()
        with col_act3:
            if st.button("🔍 Buscar sinais", use_container_width=True):
                with st.spinner("Buscando sinais no Perplexity..."):
                    total_sinais = 0
                    for cid in selected_ids:
                        try:
                            res = discovery_engine.enrich_signals(cid)
                            total_sinais += res.get("sinais_adicionados", 0) or 0
                        except Exception:
                            pass
                    st.success(f"✅ {total_sinais} sinal(is) adicionado(s) no total.")
                    st.rerun()

    # Detalhes individuais em expanders
    with st.expander("Ver detalhes (escolha uma escola)"):
        if len(df) > 0:
            options = [f"{r['Nome']} — {r['Cidade']}" for r in rows]
            sel = st.selectbox("Escola", options=[""] + options)
            if sel and sel != "":
                idx = options.index(sel)
                school = discovered[idx]
                st.markdown(f"### {school.get('name', '?')}")
                cols = st.columns(2)
                with cols[0]:
                    st.markdown(f"**Cidade:** {school.get('city', '?')}/{school.get('state', '')}")
                    st.markdown(f"**Tipo:** {school.get('admin_category', '?')}")
                    st.markdown(f"**Niveis:** {school.get('education_levels', '?')}")
                with cols[1]:
                    st.markdown(f"**Site:** {school.get('website') or '-'}")
                    st.markdown(f"**Telefone:** {school.get('phone') or '-'}")
                    st.markdown(f"**Fonte:** {school.get('source', '?')}")

                # Memories (sinais)
                try:
                    from integrations.memory import memory
                    mems = memory.get_for("company", school["id"], limit=10)
                    if mems:
                        st.markdown("**Sinais registrados:**")
                        for m in mems:
                            st.markdown(f"- {m.get('content', '')}")
                except Exception:
                    pass

                # Acoes individuais
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    if st.button("✅ Aprovar", key=f"btn_approve_{school['id']}", use_container_width=True):
                        if discovery_engine.promote_to_raw(school["id"]):
                            st.success("Aprovada!")
                            st.rerun()
                with col_i2:
                    if st.button("❌ Rejeitar", key=f"btn_reject_{school['id']}", use_container_width=True):
                        if discovery_engine.reject(school["id"]):
                            st.success("Rejeitada.")
                            st.rerun()
                with col_i3:
                    if st.button("🔍 Sinais", key=f"btn_signals_{school['id']}", use_container_width=True):
                        with st.spinner("Buscando sinais..."):
                            res = discovery_engine.enrich_signals(school["id"])
                            st.success(f"{res.get('sinais_adicionados', 0)} sinal(is) adicionado(s).")
                            st.rerun()

st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.info(
    "💡 **Dica:** voce tambem pode controlar pelo WhatsApp. "
    "Diga: _\"descobre escolas bilingues em Canoas\"_, _\"mostra as descobertas\"_, "
    "_\"aprova a escola X\"_, _\"busca sinais do Colegio Y\"_."
)
