"""Pagina 12 - Inteligencia de Escolas: enriquecimento via web (Item 8 refatorado).

Busca informacoes extras (rankings, premios, noticias, sites, telefones) sobre
escolas que JA EXISTEM no banco. NAO cria registros novos.
"""
import sys
from pathlib import Path

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
breadcrumb(["IAprendo", "Inteligencia de Escolas"])
st.markdown("# 🔍 Inteligencia de Escolas")
st.caption(
    "Enriqueca escolas do banco com dados da web: rankings, premios, noticias, "
    "diferenciais, sites e telefones. Tudo e salvo automaticamente e usado nos emails."
)

# =============================================================================
# Secao 1 - Enriquecer escolas em lote
# =============================================================================
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

# =============================================================================
# Secao 2 - Buscar sinais de escola individual
# =============================================================================
section_header("Buscar sinais de escola individual", "psychology")

st.caption("Pesquisa rankings, premios, noticias e reconhecimentos de uma escola especifica.")

col_s1, col_s2 = st.columns([3, 1])
with col_s1:
    escola_nome = st.text_input("Nome da escola", placeholder="Ex: Colegio Marista Champagnat", key="sig_escola")
with col_s2:
    st.markdown('<div style="margin-top:28px"></div>', unsafe_allow_html=True)
    buscar_sinais = st.button("🔍 Buscar sinais", use_container_width=True, key="btn_sinais")

if buscar_sinais and escola_nome:
    # Buscar escola no banco
    try:
        r = db.client.table("companies").select("id,name,city").ilike(
            "name", f"%{escola_nome.strip()}%"
        ).limit(1).execute()
        if not r.data:
            st.error(f"Escola '{escola_nome}' nao encontrada no banco.")
        else:
            escola = r.data[0]
            with st.spinner(f"Buscando sinais de {escola['name']}..."):
                result = discovery_engine.enrich_signals(escola["id"])
                n = result.get("sinais_adicionados", 0)
                if n > 0:
                    st.success(f"✅ {n} sinal(is) adicionado(s) para {escola['name']}")
                    for preview in result.get("preview", []):
                        st.markdown(f"- {preview}")
                else:
                    st.info(f"Nenhum sinal encontrado para {escola['name']}.")
                if result.get("erros"):
                    for err in result["erros"][:3]:
                        st.warning(f"⚠️ {err}")
    except Exception as e:
        st.error(f"Erro: {e}")

st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.info(
    "💡 **Dica:** voce tambem pode fazer isso pelo WhatsApp. "
    "Diga: _\"enriquece as escolas de Canoas\"_ ou _\"busca sinais do Marista\"_."
)
