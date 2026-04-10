"""Pagina 15 - Memorias do IAlex: CRUD completo da memoria persistente.

A memoria do IAlex alimenta sugerir_angulos_email, gerar_email e follow-ups.
Esta pagina permite:
- Ver todas as memorias agregadas (KPIs + tabela + busca)
- Criar memoria manualmente (form)
- Editar importancia e conteudo
- Excluir memorias
- Ver top escolas por quantidade de memorias
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header, alert_banner,
    breadcrumb, COLORS,
)
from integrations.memory import memory
from database.supabase_client import db

apply_theme_no_config()
breadcrumb(["IAprendo", "Memorias"])
st.markdown("# 🧠 Memorias do IAlex")
st.caption(
    "Memorias persistentes usadas para personalizar emails, follow-ups e recomendar "
    "proximas acoes. Populadas automaticamente por eventos (email aberto, reuniao, "
    "qualifier) ou manualmente via chat WhatsApp / esta pagina."
)

if not memory.is_available():
    alert_banner(
        "Tabela conversation_memory nao disponivel. Aplique a migration 005.",
        "error",
    )
    st.stop()

# =============================================================================
# Labels (usados em todos os lugares)
# =============================================================================
CAT_LABELS = {
    "fact": "📌 Fato",
    "preference": "⭐ Preferencia",
    "insight": "💡 Insight",
    "warning": "⚠️ Alerta",
    "reminder": "🔔 Lembrete",
}
SCOPE_LABELS = {
    "global": "Global",
    "company": "Escola",
    "contact": "Contato",
}


def _render_create_form(companies):
    """Form reutilizavel para criar uma nova memoria."""
    with st.form("create_mem_form"):
        cm_c1, cm_c2 = st.columns([2, 1])
        with cm_c1:
            conteudo = st.text_area(
                "Conteudo *",
                placeholder="Ex: Diretora prefere ser contatada de manha.",
                height=90,
            )
        with cm_c2:
            cat = st.selectbox(
                "Categoria",
                ["fact", "preference", "insight", "warning", "reminder"],
                format_func=lambda x: CAT_LABELS.get(x, x),
            )
            imp = st.slider("Importancia", 1, 10, 5)

        cm_c3, cm_c4 = st.columns(2)
        with cm_c3:
            escopo = st.radio(
                "Escopo",
                ["global", "company"],
                format_func=lambda x: SCOPE_LABELS.get(x, x),
                horizontal=True,
            )
        with cm_c4:
            escola_sel_id = None
            if escopo == "company" and companies:
                escola_names = [f"{c.get('name', '?')} ({c.get('city', '')})" for c in companies]
                idx = st.selectbox(
                    "Escola",
                    range(len(companies)),
                    format_func=lambda i: escola_names[i][:50],
                )
                escola_sel_id = companies[idx]["id"]

        if st.form_submit_button("💾 Criar memoria", type="primary"):
            if not conteudo or len(conteudo.strip()) < 5:
                st.error("Conteudo muito curto (minimo 5 chars).")
            elif escopo == "company" and not escola_sel_id:
                st.error("Selecione uma escola.")
            else:
                mem_id = memory.remember(
                    content=conteudo,
                    scope=escopo,
                    scope_id=escola_sel_id if escopo == "company" else None,
                    category=cat,
                    importance=imp,
                    source="dashboard",
                )
                if mem_id:
                    st.success(f"Memoria criada: {mem_id[:8]}")
                    load_memories.clear()
                    st.rerun()
                else:
                    st.error("Falha ao criar.")


# =============================================================================
# LOAD
# =============================================================================
@st.cache_data(ttl=60)
def load_memories():
    try:
        r = db.client.table("conversation_memory").select("*").order("created_at", desc=True).execute()
        return r.data or []
    except Exception as e:
        st.error(f"Erro ao carregar memorias: {e}")
        return []


@st.cache_data(ttl=60)
def load_companies():
    try:
        r = db.client.table("companies").select("id,name,city,state").order("name").execute()
        return r.data or []
    except Exception:
        return []


all_memories = load_memories()
all_companies = load_companies()
company_by_id = {c["id"]: c for c in all_companies}
company_name_by_id = {c["id"]: c.get("name", "?") for c in all_companies}

# =============================================================================
# KPIs
# =============================================================================
total_mem = len(all_memories)
now = datetime.now(timezone.utc)
week_ago = now - timedelta(days=7)
mem_semana = 0
for m in all_memories:
    try:
        created = datetime.fromisoformat((m.get("created_at") or "").replace("Z", "+00:00"))
        if created >= week_ago:
            mem_semana += 1
    except Exception:
        pass

cats = Counter(m.get("category", "?") for m in all_memories)
top_cat = cats.most_common(1)[0] if cats else ("—", 0)

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    metric_card("Total de memorias", total_mem, COLORS["primary"], icon="psychology")
with mc2:
    metric_card("Criadas na semana", mem_semana, COLORS["accent"], icon="update")
with mc3:
    metric_card(
        "Top categoria",
        f"{CAT_LABELS.get(top_cat[0], top_cat[0])[:12]} ({top_cat[1]})",
        COLORS["info"],
        icon="category",
    )
with mc4:
    n_com_escola = sum(1 for m in all_memories if m.get("scope") == "company")
    metric_card("De escolas", n_com_escola, COLORS["secondary"], icon="school")

st.markdown("")

if not all_memories:
    alert_banner(
        "Nenhuma memoria ainda. O IAlex cria automaticamente quando emails sao abertos/clicados, "
        "reunioes sao registradas ou qualifier gera insights.",
        "info",
    )
    with st.expander("➕ Criar primeira memoria manualmente"):
        _render_create_form(all_companies)
    st.stop()

# =============================================================================
# FILTROS
# =============================================================================
st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
with fc1:
    sel_scope = st.multiselect(
        "Escopo",
        ["global", "company", "contact"],
        default=[],
        format_func=lambda x: SCOPE_LABELS.get(x, x),
        label_visibility="collapsed",
        placeholder="Escopo...",
    )
with fc2:
    sel_cat = st.multiselect(
        "Categoria",
        ["fact", "preference", "insight", "warning", "reminder"],
        default=[],
        format_func=lambda x: CAT_LABELS.get(x, x),
        label_visibility="collapsed",
        placeholder="Categoria...",
    )
with fc3:
    min_imp = st.slider("Importancia minima", 1, 10, 1, label_visibility="collapsed")
with fc4:
    search = st.text_input(
        "Buscar",
        placeholder="Buscar conteudo...",
        label_visibility="collapsed",
        key="mem_search",
    )
st.markdown('</div>', unsafe_allow_html=True)

# Aplicar filtros
mems_filt = all_memories
if sel_scope:
    mems_filt = [m for m in mems_filt if m.get("scope") in sel_scope]
if sel_cat:
    mems_filt = [m for m in mems_filt if m.get("category") in sel_cat]
mems_filt = [m for m in mems_filt if (m.get("importance") or 5) >= min_imp]
if search:
    s = search.lower()
    mems_filt = [m for m in mems_filt if s in (m.get("content") or "").lower()]

st.caption(f"Exibindo **{len(mems_filt)}** de {len(all_memories)} memorias")

# =============================================================================
# TABELA PRINCIPAL
# =============================================================================
if mems_filt:
    rows = []
    for m in mems_filt:
        scope = m.get("scope", "?")
        scope_id = m.get("scope_id")
        escola_nome = ""
        if scope == "company" and scope_id:
            escola_nome = company_name_by_id.get(scope_id, "?")[:40]

        created_raw = m.get("created_at") or ""
        try:
            created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            created_str = created_dt.strftime("%d/%m/%Y")
        except Exception:
            created_str = "?"

        rows.append({
            "id": m.get("id"),
            "Categoria": CAT_LABELS.get(m.get("category", "fact"), m.get("category", "?")),
            "Conteudo": (m.get("content") or "")[:100],
            "Escopo": SCOPE_LABELS.get(scope, scope),
            "Escola": escola_nome,
            "Importancia": m.get("importance") or 5,
            "Criado": created_str,
            "Usos": m.get("use_count") or 0,
            "Fonte": m.get("source") or "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df[["Categoria", "Conteudo", "Escola", "Importancia", "Usos", "Criado", "Fonte"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Importancia": st.column_config.ProgressColumn("Imp.", min_value=1, max_value=10),
            "Conteudo": st.column_config.TextColumn("Conteudo", width="large"),
            "Escola": st.column_config.TextColumn("Escola", width="medium"),
            "Fonte": st.column_config.TextColumn("Fonte", width="small"),
        },
        height=400,
    )

    # Selecionar memoria para excluir
    st.markdown("")
    exp_del = st.expander("🗑️ Excluir memoria")
    with exp_del:
        del_options = [
            f"{(m.get('content') or '')[:80]}... ({m.get('id', '')[:8]})"
            for m in mems_filt
        ]
        del_idx = st.selectbox(
            "Memoria a excluir",
            range(len(del_options)),
            format_func=lambda i: del_options[i],
            key="mem_del_select",
        )
        col_del_1, col_del_2 = st.columns([1, 4])
        with col_del_1:
            if st.button("Excluir", type="primary", icon=":material/delete:"):
                target_id = mems_filt[del_idx].get("id")
                if memory.forget(target_id):
                    st.success(f"Memoria {target_id[:8]} excluida.")
                    load_memories.clear()
                    st.rerun()
                else:
                    st.error("Falha ao excluir.")

# =============================================================================
# CRIAR MEMORIA
# =============================================================================
st.markdown("")
with st.expander("➕ Criar memoria manualmente"):
    _render_create_form(all_companies)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# TOP ESCOLAS POR MEMORIAS
# =============================================================================
section_header("Top 10 escolas por numero de memorias", "leaderboard")

by_school = Counter()
for m in all_memories:
    if m.get("scope") == "company" and m.get("scope_id"):
        by_school[m["scope_id"]] += 1

if by_school:
    top_10 = by_school.most_common(10)
    rows_top = []
    for cid, count in top_10:
        comp = company_by_id.get(cid, {})
        rows_top.append({
            "Escola": (comp.get("name") or cid[:8])[:45],
            "Cidade": comp.get("city") or "",
            "Memorias": count,
        })
    df_top = pd.DataFrame(rows_top)

    fig = px.bar(
        df_top,
        y="Escola",
        x="Memorias",
        orientation="h",
        color="Memorias",
        color_continuous_scale="Blues",
        title="Escolas com mais memorias registradas",
        height=380,
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False,
        plot_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "💡 Essas escolas estao bem 'mapeadas' — o IAlex vai personalizar mensagens "
        "usando essas informacoes. Escolas sem memorias podem gerar emails genericos."
    )
else:
    alert_banner(
        "Nenhuma memoria especifica de escola ainda. Registre reunioes ou deixe o "
        "tracking de emails (open/click/reply) capturar automaticamente.",
        "info",
    )

# =============================================================================
# DICA
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.info(
    "💡 **Como alimentar memorias sem esforco:**\n\n"
    "• Eventos de email (opens/clicks/replies) viram memorias automaticamente via Brevo webhook.\n"
    "• Reunioes registradas viram memorias (outcome=positivo, notas).\n"
    "• Qualifier salva insights de escolas com score alto + sinais de inovacao.\n"
    "• Voce pode gravar via WhatsApp: 'Lembre que o diretor do Anchieta prefere WhatsApp'.\n"
    "• Dados ricos do Censo podem ser 'seedados' em batch via "
    "`venv/Scripts/python.exe scripts/seed_census_memories.py --yes`."
)
