"""Pagina 13 - Analytics: Dashboard de ROI e conversao com graficos Plotly.
KPIs, funil, evolucao temporal, performance por canal/cidade, custo e ROI."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, section_header, alert_banner,
    breadcrumb, metric_card, COLORS,
)
from database.supabase_client import db

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()
breadcrumb(["IAprendo", "Analytics"])
st.markdown("# 📈 Analytics — ROI e Conversao")
st.caption("Visao completa de performance: funil, taxas, custos e oportunidades.")

# =============================================================================
# FILTROS
# =============================================================================
col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
with col_f1:
    periodo = st.selectbox("Periodo", ["Ultimos 7 dias", "Ultimos 30 dias", "Ultimos 90 dias", "Tudo"],
                           index=1, key="analytics_periodo")
with col_f2:
    try:
        cities = db.client.table("companies").select("city").execute().data or []
        city_list = sorted(set(c.get("city", "") for c in cities if c.get("city")))
        filter_city = st.selectbox("Cidade", ["Todas"] + city_list, key="analytics_city")
    except Exception:
        filter_city = "Todas"
with col_f3:
    filter_tipo = st.selectbox("Tipo", ["Todos", "Privada", "Publica"], key="analytics_tipo")

# Calcular cutoff
days_map = {"Ultimos 7 dias": 7, "Ultimos 30 dias": 30, "Ultimos 90 dias": 90, "Tudo": 9999}
cutoff_days = days_map.get(periodo, 30)
cutoff_dt = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
cutoff_iso = cutoff_dt.isoformat()

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# DADOS
# =============================================================================
@st.cache_data(ttl=3600)
def get_usd_brl_rate() -> float:
    """Busca taxa USD/BRL atual via API gratuita. Cache 1h."""
    import requests
    try:
        r = requests.get("https://economia.awesomeapi.com.br/last/USD-BRL", timeout=5)
        if r.status_code == 200:
            data = r.json()
            rate = float(data.get("USDBRL", {}).get("bid", 5.50))
            return rate
    except Exception:
        pass
    return 5.50  # fallback

USD_BRL = get_usd_brl_rate()

@st.cache_data(ttl=300)
def load_analytics_data():
    """Carrega todos os dados necessarios para analytics."""
    data = {}

    # Companies por status + dados ricos do Censo 2025
    try:
        comps = db.client.table("companies").select(
            "id,name,status,city,state,admin_category,admin_dependency,categoria_privada,"
            "qualification_score,created_at,"
            "fonte_dados,total_matriculas,matriculas_fund_af,matriculas_medio,"
            "total_docentes,qt_coordenadores,nivel_tecnologico"
        ).execute().data or []
        # Calcular Fit IAprendo para cada empresa
        from utils.fit_score import calcular_fit_score
        for _c in comps:
            _fit = calcular_fit_score(_c)
            _c["_fit"] = _fit["score"] or 0
            _c["_fit_level"] = _fit["level"]
        data["companies"] = comps
    except Exception:
        data["companies"] = []

    # Approval queue (enviados)
    try:
        msgs = db.client.table("approval_queue").select(
            "id,status,channel,company_id,sent_at,opened_at,clicked_at,replied_at,"
            "bounced_at,created_at,follow_up_number"
        ).execute().data or []
        data["messages"] = msgs
    except Exception:
        data["messages"] = []

    # Meetings
    try:
        meets = db.client.table("meetings").select(
            "id,status,outcome,scheduled_at,company_id"
        ).execute().data or []
        data["meetings"] = meets
    except Exception:
        data["meetings"] = []

    # API usage (com tokens se disponivel)
    try:
        apis = db.client.table("api_usage").select(
            "api_name,credits_used,created_at,prompt_tokens,completion_tokens,"
            "total_tokens,model,cost_usd"
        ).execute().data or []
        data["api_usage"] = apis
    except Exception:
        data["api_usage"] = []

    return data

raw_data = load_analytics_data()

# Filtrar por cidade e tipo
companies = raw_data["companies"]
if filter_city != "Todas":
    companies = [c for c in companies if c.get("city") == filter_city]
if filter_tipo != "Todos":
    companies = [c for c in companies if filter_tipo.lower() in (c.get("admin_category") or "").lower()]
company_ids = {c["id"] for c in companies}

messages = [m for m in raw_data["messages"] if m.get("company_id") in company_ids] if filter_city != "Todas" or filter_tipo != "Todos" else raw_data["messages"]
sent_msgs = [m for m in messages if m.get("status") == "sent"]
meetings = raw_data["meetings"]
api_usage = raw_data["api_usage"]

# =============================================================================
# SECAO 1 — KPIs
# =============================================================================
section_header("KPIs principais", "dashboard")

total_escolas = len(companies)
total_enviados = len(sent_msgs)
total_abertos = len([m for m in sent_msgs if m.get("opened_at")])
total_respondidos = len([m for m in sent_msgs if m.get("replied_at")])
total_clicados = len([m for m in sent_msgs if m.get("clicked_at")])
total_reunioes = len([m for m in meetings if m.get("status") in ("scheduled", "completed")])

taxa_abertura = f"{total_abertos * 100 // total_enviados}%" if total_enviados else "—"
taxa_resposta = f"{total_respondidos * 100 // total_enviados}%" if total_enviados else "—"

# Custo total (usa cost_usd real quando disponivel, senao estima)
total_cost_usd_kpi = sum(float(a.get("cost_usd") or 0) or 0.02 for a in api_usage)
custo_brl_kpi = total_cost_usd_kpi * USD_BRL
custo_estimado = f"R$ {custo_brl_kpi:.2f}"

k1, k2, k3, k4, k5, k6 = st.columns(6)
with k1:
    metric_card("Escolas", total_escolas, icon="school", color=COLORS["primary"])
with k2:
    metric_card("Enviados", total_enviados, icon="send", color=COLORS["secondary"])
with k3:
    metric_card("Abertura", taxa_abertura, icon="mark_email_read", color=COLORS["info"],
                delta=f"{total_abertos} emails")
with k4:
    metric_card("Resposta", taxa_resposta, icon="reply", color=COLORS["success"],
                delta=f"{total_respondidos} emails")
with k5:
    metric_card("Reunioes", total_reunioes, icon="event", color=COLORS["accent"])
with k6:
    metric_card("Custo total", custo_estimado, icon="payments", color="#9E9E9E",
                delta=f"{len(api_usage)} chamadas")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 2 — Funil de conversao
# =============================================================================
section_header("Funil de conversao", "filter_alt")

status_order = ["raw", "qualified", "enriched", "contacted", "replied", "meeting", "closed"]
status_labels = {
    "raw": "Importadas",
    "qualified": "Qualificadas",
    "enriched": "Enriquecidas",
    "contacted": "Contatadas",
    "replied": "Responderam",
    "meeting": "Reuniao",
    "closed": "Fechadas",
}

# Calcular funil acumulativo
status_counts = Counter(c.get("status", "raw") for c in companies)
replied_count = len([m for m in sent_msgs if m.get("replied_at")])
meeting_count = len([m for m in meetings if m.get("status") in ("completed", "scheduled")])
closed_count = len([m for m in meetings if m.get("outcome") == "fechado"])

# Funil: cada etapa = escolas que chegaram ATE aqui (acumulado decrescente)
# raw = total | qualified = qualified + enriched + contacted | etc
progression = ["raw", "qualified", "enriched", "contacted"]
funnel_corrected = []
for i, s in enumerate(progression):
    # Escolas que estao neste status OU posterior
    val = sum(status_counts.get(ss, 0) for ss in progression[i:])
    funnel_corrected.append(max(val, 0))
# Replied, meeting, closed vem das tabelas de tracking
funnel_corrected.append(replied_count)
funnel_corrected.append(meeting_count)
funnel_corrected.append(closed_count)

fig_funnel = go.Figure(go.Funnel(
    y=[status_labels.get(s, s) for s in status_order],
    x=funnel_corrected,
    textposition="inside",
    textinfo="value+percent initial",
    marker=dict(color=[
        "#1976D2", "#00897B", "#FF6D00", "#7B1FA2",
        "#2E7D32", "#D32F2F", "#FFD600",
    ]),
))
fig_funnel.update_layout(
    height=350,
    margin=dict(l=10, r=10, t=10, b=10),
    font=dict(family="Inter", size=13),
)
st.plotly_chart(fig_funnel, use_container_width=True)

# Taxas entre etapas
if funnel_corrected[0] > 0:
    cols_tax = st.columns(len(status_order) - 1)
    for i in range(len(status_order) - 1):
        prev = funnel_corrected[i]
        curr = funnel_corrected[i + 1]
        taxa = f"{curr * 100 // prev}%" if prev > 0 else "—"
        with cols_tax[i]:
            st.markdown(
                f'<div style="text-align:center;font-size:12px;color:#757575">'
                f'{status_labels[status_order[i]][:6]} → {status_labels[status_order[i+1]][:6]}<br/>'
                f'<strong style="font-size:16px;color:{COLORS["primary"]}">{taxa}</strong></div>',
                unsafe_allow_html=True,
            )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 3 — Evolucao temporal
# =============================================================================
section_header("Evolucao temporal", "trending_up")

# Agrupar por semana
def _week_key(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-W%W")
    except Exception:
        return None

weeks_sent = Counter(_week_key(m.get("sent_at")) for m in sent_msgs if _week_key(m.get("sent_at")))
weeks_opened = Counter(_week_key(m.get("opened_at")) for m in sent_msgs if _week_key(m.get("opened_at")))
weeks_replied = Counter(_week_key(m.get("replied_at")) for m in sent_msgs if _week_key(m.get("replied_at")))

all_weeks = sorted(set(list(weeks_sent.keys()) + list(weeks_opened.keys()) + list(weeks_replied.keys())))
if all_weeks:
    df_temporal = pd.DataFrame({
        "Semana": all_weeks,
        "Enviados": [weeks_sent.get(w, 0) for w in all_weeks],
        "Abertos": [weeks_opened.get(w, 0) for w in all_weeks],
        "Respondidos": [weeks_replied.get(w, 0) for w in all_weeks],
    })

    fig_temporal = px.line(
        df_temporal, x="Semana", y=["Enviados", "Abertos", "Respondidos"],
        markers=True,
        color_discrete_sequence=[COLORS["primary"], COLORS["info"], COLORS["success"]],
    )
    fig_temporal.update_layout(
        height=300, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        font=dict(family="Inter", size=12),
    )
    st.plotly_chart(fig_temporal, use_container_width=True)
else:
    st.info("Sem dados temporais suficientes ainda.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 4 — Performance por canal
# =============================================================================
section_header("Performance por canal", "campaign")

channels = defaultdict(lambda: {"enviados": 0, "abertos": 0, "clicados": 0, "respondidos": 0})
for m in sent_msgs:
    ch = m.get("channel", "email")
    channels[ch]["enviados"] += 1
    if m.get("opened_at"):
        channels[ch]["abertos"] += 1
    if m.get("clicked_at"):
        channels[ch]["clicados"] += 1
    if m.get("replied_at"):
        channels[ch]["respondidos"] += 1

if channels:
    channel_icons = {"email": "📧", "whatsapp": "📱", "linkedin": "💼"}
    rows = []
    for ch, stats in sorted(channels.items()):
        env = stats["enviados"]
        rows.append({
            "Canal": f"{channel_icons.get(ch, '📧')} {ch.title()}",
            "Enviados": env,
            "Abertos": stats["abertos"],
            "Clicados": stats["clicados"],
            "Respondidos": stats["respondidos"],
            "Taxa abertura": f"{stats['abertos'] * 100 // env}%" if env else "—",
            "Taxa resposta": f"{stats['respondidos'] * 100 // env}%" if env else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Sem dados de envio por canal.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 5 — Performance por cidade/tipo
# =============================================================================
section_header("Performance por cidade e tipo", "location_city")

# Cruzar empresa → mensagens enviadas
company_map = {c["id"]: c for c in raw_data["companies"]}
city_stats = defaultdict(lambda: {"enviados": 0, "abertos": 0, "respondidos": 0})

for m in sent_msgs:
    comp = company_map.get(m.get("company_id"), {})
    key = f"{comp.get('city', '?')} | {comp.get('admin_category', '?')}"
    city_stats[key]["enviados"] += 1
    if m.get("opened_at"):
        city_stats[key]["abertos"] += 1
    if m.get("replied_at"):
        city_stats[key]["respondidos"] += 1

if city_stats:
    rows = []
    for key, stats in sorted(city_stats.items(), key=lambda x: x[1]["respondidos"], reverse=True):
        env = stats["enviados"]
        rows.append({
            "Cidade | Tipo": key,
            "Enviados": env,
            "Abertos": stats["abertos"],
            "Respondidos": stats["respondidos"],
            "Taxa resposta": f"{stats['respondidos'] * 100 // env}%" if env else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Sem dados suficientes.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 6 — Tempo de ciclo
# =============================================================================
section_header("Tempo de ciclo", "timer")

def _hours_between(iso_a, iso_b):
    if not iso_a or not iso_b:
        return None
    try:
        a = datetime.fromisoformat(iso_a.replace("Z", "+00:00"))
        b = datetime.fromisoformat(iso_b.replace("Z", "+00:00"))
        return max(0, (b - a).total_seconds() / 3600)
    except Exception:
        return None

time_to_open = [_hours_between(m.get("sent_at"), m.get("opened_at")) for m in sent_msgs]
time_to_open = [t for t in time_to_open if t is not None]

time_to_reply = [_hours_between(m.get("sent_at"), m.get("replied_at")) for m in sent_msgs]
time_to_reply = [t for t in time_to_reply if t is not None]

tc1, tc2, tc3 = st.columns(3)
with tc1:
    avg_open = f"{sum(time_to_open) / len(time_to_open):.1f}h" if time_to_open else "—"
    metric_card("Envio → Abertura", avg_open, icon="schedule", color=COLORS["info"],
                delta=f"{len(time_to_open)} amostras")
with tc2:
    avg_reply = f"{sum(time_to_reply) / len(time_to_reply) / 24:.1f} dias" if time_to_reply else "—"
    metric_card("Envio → Resposta", avg_reply, icon="schedule", color=COLORS["success"],
                delta=f"{len(time_to_reply)} amostras")
with tc3:
    metric_card("Melhor horario", "Ver Smart Scheduler", icon="access_time", color=COLORS["accent"])

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 7 — Custo e ROI
# =============================================================================
section_header("Custo e ROI", "payments")

# --- Custo do mes atual + projecao ---
from datetime import datetime, timedelta, timezone
_now = datetime.now(timezone.utc)
_primeiro_dia = _now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
_dias_corridos = max(1, (_now - _primeiro_dia).days + 1)

# Quantos dias tem o mes atual?
if _now.month == 12:
    _proximo_mes = _now.replace(year=_now.year + 1, month=1, day=1)
else:
    _proximo_mes = _now.replace(month=_now.month + 1, day=1)
_dias_do_mes = (_proximo_mes - _primeiro_dia).days

# Custo do mes atual (so rows com cost_usd preenchido)
_mes_cost_usd = 0.0
for a in api_usage:
    cost = a.get("cost_usd")
    if not cost:
        continue
    created = a.get("created_at") or ""
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created_dt >= _primeiro_dia:
            _mes_cost_usd += float(cost)
    except Exception:
        continue

_mes_cost_brl = _mes_cost_usd * USD_BRL
_projecao_usd = (_mes_cost_usd / _dias_corridos) * _dias_do_mes if _dias_corridos > 0 else 0
_projecao_brl = _projecao_usd * USD_BRL

_mes_nome_pt = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}[_now.month]

cc1, cc2 = st.columns(2)
with cc1:
    metric_card(
        f"Custo de {_mes_nome_pt}",
        f"R$ {_mes_cost_brl:.2f}",
        color=COLORS["primary"],
        icon="calendar_month",
        delta=f"USD {_mes_cost_usd:.4f} | {_dias_corridos}/{_dias_do_mes} dias",
    )
with cc2:
    metric_card(
        "Projecao do mes",
        f"R$ {_projecao_brl:.2f}",
        color=COLORS["accent"],
        icon="trending_up",
        delta=f"ritmo atual ate {_dias_do_mes}/{_now.month:02d}",
    )

st.markdown("")

api_stats = defaultdict(lambda: {"credits": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0})
for a in api_usage:
    api_name = a.get("api_name", "?")
    api_stats[api_name]["credits"] += (a.get("credits_used") or 0)
    # Custo real por tokens (se disponivel)
    if a.get("cost_usd"):
        api_stats[api_name]["cost_usd"] += float(a["cost_usd"])
    else:
        api_stats[api_name]["cost_usd"] += 0.02  # fallback: USD 0.02/credit
    api_stats[api_name]["tokens_in"] += (a.get("prompt_tokens") or 0)
    api_stats[api_name]["tokens_out"] += (a.get("completion_tokens") or 0)

if api_stats:
    rows = []
    for api, stats in sorted(api_stats.items(), key=lambda x: x[1]["cost_usd"], reverse=True):
        cost_brl = stats["cost_usd"] * USD_BRL
        tokens_info = ""
        if stats["tokens_in"] > 0:
            tokens_info = f'{stats["tokens_in"]:,}in / {stats["tokens_out"]:,}out'
        rows.append({
            "API": api,
            "Chamadas": stats["credits"],
            "Tokens": tokens_info or "—",
            "USD": f'$ {stats["cost_usd"]:.4f}',
            "BRL": f'R$ {cost_brl:.2f}',
        })
    total_cost_usd = sum(s["cost_usd"] for s in api_stats.values())
    total_cost = total_cost_usd * USD_BRL
    total_tokens_in = sum(s["tokens_in"] for s in api_stats.values())
    total_tokens_out = sum(s["tokens_out"] for s in api_stats.values())
    rows.append({
        "API": "TOTAL",
        "Chamadas": sum(s["credits"] for s in api_stats.values()),
        "Tokens": f"{total_tokens_in:,}in / {total_tokens_out:,}out" if total_tokens_in else "—",
        "USD": f"$ {total_cost_usd:.4f}",
        "BRL": f"R$ {total_cost:.2f}",
    })
    st.caption(f"_Taxa USD/BRL: {USD_BRL:.2f} | Custo calculado por tokens reais quando disponivel_")

    r1, r2 = st.columns([1, 1])
    with r1:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with r2:
        qualified_count = len([c for c in companies if c.get("status") not in ("raw",)])
        cost_per_lead = f"R$ {total_cost / qualified_count:.2f}" if qualified_count else "—"
        cost_per_reply = f"R$ {total_cost / total_respondidos:.2f}" if total_respondidos else "—"
        cost_per_sent = f"R$ {total_cost / total_enviados:.2f}" if total_enviados else "—"

        metric_card("Custo/lead qualificado", cost_per_lead, icon="person_search", color=COLORS["info"])
        metric_card("Custo/resposta", cost_per_reply, icon="reply_all", color=COLORS["success"])

    # --- Grafico temporal: custo por dia ultimos 30 dias ---
    st.markdown("")
    _30d_ago = _now - timedelta(days=30)
    _temporal_rows = []
    for a in api_usage:
        cost = a.get("cost_usd")
        if not cost:
            continue
        created = a.get("created_at") or ""
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_dt >= _30d_ago:
                _temporal_rows.append({
                    "dia": created_dt.strftime("%d/%m"),
                    "api": a.get("api_name", "?"),
                    "cost_usd": float(cost),
                })
        except Exception:
            continue

    if _temporal_rows:
        df_temp = pd.DataFrame(_temporal_rows)
        df_temp_agg = df_temp.groupby(["dia", "api"], as_index=False)["cost_usd"].sum()
        df_temp_agg["cost_brl"] = df_temp_agg["cost_usd"] * USD_BRL

        fig_temporal = px.bar(
            df_temp_agg,
            x="dia",
            y="cost_brl",
            color="api",
            title="Custo por dia (ultimos 30 dias) — agrupado por API",
            labels={"cost_brl": "Custo (R$)", "dia": "Dia", "api": "API"},
            height=320,
        )
        fig_temporal.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            plot_bgcolor="white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(categoryorder="category ascending"),
        )
        st.plotly_chart(fig_temporal, use_container_width=True)
    else:
        st.caption("_Sem custos registrados nos ultimos 30 dias._")
else:
    st.info("Sem dados de uso de API.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 8 — Top oportunidades
# =============================================================================
section_header("Top oportunidades (score preditivo)", "emoji_events")

top_schools = sorted(
    [c for c in companies if (c.get("qualification_score") or 0) > 0],
    key=lambda x: x.get("qualification_score", 0),
    reverse=True,
)[:10]

if top_schools:
    rows = [{
        "Escola": s.get("name", "?")[:40],
        "Cidade": s.get("city", ""),
        "Tipo": s.get("admin_category", ""),
        "Alvo": int((s.get("matriculas_fund_af") or 0) + (s.get("matriculas_medio") or 0)),
        "Tech": s.get("nivel_tecnologico") or "-",
        "Score": s.get("qualification_score", 0),
        "Status": s.get("status", ""),
    } for s in top_schools]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={
                     "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                     "Alvo": st.column_config.NumberColumn(
                         "Alvo",
                         help="Matriculas Fund AF + Medio (segmento IAprendo)",
                     ),
                 })
else:
    st.info("Nenhuma escola qualificada ainda.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# SECAO 9 — Perfil da carteira (Censo 2025)
# =============================================================================
section_header("Perfil da carteira (Censo 2025)", "insights")
st.caption(
    "Distribuicao das escolas do CRM por nivel tecnologico, fonte dos dados, "
    "e ranking por potencial de alunos alvo (Fund AF + Medio)."
)

# --- Preparar DataFrame enriquecido ---
import pandas as _pd
df_comp = _pd.DataFrame(companies)

if df_comp.empty:
    st.info("Nenhuma escola no CRM.")
else:
    # Calcular alunos alvo (Fund AF + Medio)
    df_comp["alvo"] = (
        df_comp["matriculas_fund_af"].fillna(0).astype(int)
        + df_comp["matriculas_medio"].fillna(0).astype(int)
    )
    df_comp["nivel_tech_label"] = df_comp["nivel_tecnologico"].fillna("Sem dado")
    df_comp["fonte_label"] = df_comp["fonte_dados"].fillna("Sem dado").map(
        lambda x: {"censo_2025": "Censo 2025", "catalogo_inep": "Catalogo INEP"}.get(x, "Sem dado")
    )

    # --- Graficos de distribuicao (pizza) ---
    pc1, pc2 = st.columns(2)

    with pc1:
        tech_counts = df_comp["nivel_tech_label"].value_counts().reset_index()
        tech_counts.columns = ["Nivel", "Escolas"]
        tech_color_map = {
            "Alto": COLORS["success"],
            "Medio": COLORS["warning"],
            "Médio": COLORS["warning"],
            "Baixo": COLORS["error"],
            "Sem dado": "#bdbdbd",
        }
        fig_tech = px.pie(
            tech_counts,
            values="Escolas",
            names="Nivel",
            title="Distribuicao por Nivel Tecnologico",
            color="Nivel",
            color_discrete_map=tech_color_map,
            hole=0.4,
        )
        fig_tech.update_traces(textposition="inside", textinfo="percent+label")
        fig_tech.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_tech, use_container_width=True)

    with pc2:
        fonte_counts = df_comp["fonte_label"].value_counts().reset_index()
        fonte_counts.columns = ["Fonte", "Escolas"]
        fig_fonte = px.pie(
            fonte_counts,
            values="Escolas",
            names="Fonte",
            title="Distribuicao por Fonte dos Dados",
            color="Fonte",
            color_discrete_map={
                "Censo 2025": COLORS["primary"],
                "Catalogo INEP": COLORS["warning"],
                "Sem dado": "#bdbdbd",
            },
            hole=0.4,
        )
        fig_fonte.update_traces(textposition="inside", textinfo="percent+label")
        fig_fonte.update_layout(height=320, margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig_fonte, use_container_width=True)

    # --- Distribuicao do Fit Score IAprendo ---
    st.markdown("")
    fit_counts = df_comp["_fit_level"].value_counts().reset_index()
    fit_counts.columns = ["Fit IAprendo", "Escolas"]
    # Ordenar manualmente: alto, medio, baixo, sem_dados
    _order_fit = {"alto": 0, "medio": 1, "baixo": 2, "sem_dados": 3}
    fit_counts["_order"] = fit_counts["Fit IAprendo"].map(_order_fit)
    fit_counts = fit_counts.sort_values("_order")
    fit_counts["Fit IAprendo"] = fit_counts["Fit IAprendo"].map({
        "alto": "🟢 Alto (70+)",
        "medio": "🟡 Medio (40-69)",
        "baixo": "🔴 Baixo (<40)",
        "sem_dados": "⚪ Sem dados",
    })

    fig_fit_dist = px.bar(
        fit_counts,
        x="Fit IAprendo",
        y="Escolas",
        color="Fit IAprendo",
        color_discrete_map={
            "🟢 Alto (70+)": COLORS["success"],
            "🟡 Medio (40-69)": COLORS["warning"],
            "🔴 Baixo (<40)": COLORS["error"],
            "⚪ Sem dados": "#bdbdbd",
        },
        text="Escolas",
        title="Distribuicao por Fit IAprendo",
        height=280,
    )
    fig_fit_dist.update_traces(textposition="outside")
    fig_fit_dist.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis_title="",
        plot_bgcolor="white",
    )
    st.plotly_chart(fig_fit_dist, use_container_width=True)

    # --- Metricas agregadas ---
    st.markdown("")
    total_alunos = int(df_comp["total_matriculas"].fillna(0).sum())
    total_alvo = int(df_comp["alvo"].sum())
    total_docentes = int(df_comp["total_docentes"].fillna(0).sum())
    n_com_coord = int((df_comp["qt_coordenadores"].fillna(0) > 0).sum())
    n_total = len(df_comp)
    pct_coord = (100 * n_com_coord / n_total) if n_total else 0

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card(
            "Alunos totais (carteira)",
            f"{total_alunos:,}".replace(",", "."),
            COLORS["primary"],
            icon="groups",
        )
    with mc2:
        metric_card(
            "Alunos alvo (Fund AF + Medio)",
            f"{total_alvo:,}".replace(",", "."),
            COLORS["accent"],
            icon="track_changes",
        )
    with mc3:
        metric_card(
            "Docentes na carteira",
            f"{total_docentes:,}".replace(",", "."),
            COLORS["info"],
            icon="record_voice_over",
        )
    with mc4:
        metric_card(
            "% com coordenador",
            f"{pct_coord:.0f}%",
            COLORS["secondary"],
            icon="supervisor_account",
        )

    st.markdown("")

    # --- Top 10 escolas por Alunos Alvo ---
    section_header("Top 10 escolas por potencial (alunos alvo)", "leaderboard")

    df_top = df_comp[df_comp["alvo"] > 0].sort_values("alvo", ascending=False).head(10).copy()
    if not df_top.empty:
        df_top["Escola"] = df_top["name"].str[:45]
        df_top["Fund AF"] = df_top["matriculas_fund_af"].fillna(0).astype(int)
        df_top["Medio"] = df_top["matriculas_medio"].fillna(0).astype(int)
        df_top["Tech"] = df_top["nivel_tech_label"]
        df_top["Alvo"] = df_top["alvo"]

        # Grafico horizontal: Fund AF vs Medio empilhado
        fig_top = go.Figure()
        fig_top.add_trace(go.Bar(
            y=df_top["Escola"],
            x=df_top["Fund AF"],
            name="Fund AF (6o-9o)",
            orientation="h",
            marker_color=COLORS["info"],
            text=df_top["Fund AF"],
            textposition="inside",
        ))
        fig_top.add_trace(go.Bar(
            y=df_top["Escola"],
            x=df_top["Medio"],
            name="Medio (1o-3o)",
            orientation="h",
            marker_color=COLORS["secondary"],
            text=df_top["Medio"],
            textposition="inside",
        ))
        fig_top.update_layout(
            barmode="stack",
            height=420,
            margin=dict(l=0, r=40, t=10, b=0),
            xaxis_title="Matriculas",
            yaxis=dict(autorange="reversed", title=""),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig_top, use_container_width=True)

        # Tabela resumo
        st.dataframe(
            df_top[["Escola", "city", "Fund AF", "Medio", "Alvo", "Tech"]].rename(
                columns={"city": "Cidade"}
            ),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Alvo": st.column_config.NumberColumn(
                    "Alvo",
                    help="Fund AF + Medio",
                ),
            },
        )
    else:
        st.info("Nenhuma escola com dados de matriculas para ranquear.")

    # --- Oportunidades ocultas: alto volume de alvo mas score baixo ---
    st.markdown("")
    section_header("Oportunidades ocultas", "visibility")
    st.caption(
        "Escolas com muito aluno alvo (Fund AF + Medio) mas score baixo — "
        "vale revisar o score manualmente."
    )

    df_oculta = df_comp[
        (df_comp["alvo"] >= 200)
        & (df_comp["qualification_score"].fillna(0) < 50)
    ].sort_values("alvo", ascending=False).head(10)

    if not df_oculta.empty:
        df_oculta_view = df_oculta[[
            "name", "city", "alvo", "qualification_score", "nivel_tech_label", "status"
        ]].rename(columns={
            "name": "Escola",
            "city": "Cidade",
            "alvo": "Alvo",
            "qualification_score": "Score",
            "nivel_tech_label": "Tech",
            "status": "Status",
        })
        df_oculta_view["Escola"] = df_oculta_view["Escola"].str[:45]
        st.dataframe(
            df_oculta_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                "Alvo": st.column_config.NumberColumn("Alvo"),
            },
        )
    else:
        st.info("Nenhuma oportunidade oculta detectada (ou todas ja estao bem qualificadas).")


# ============================================================================
# OPR TRACKING (F7 Fase 3)
# ============================================================================

st.divider()
section_header("OPR Tracking", "analytics")

st.caption(
    "Rastreamento dos relatorios OPR gerados. Cada abertura e clique em aba "
    "e um sinal de intencao do destinatario."
)

try:
    from database.supabase_client import db
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz

    # Filtro de periodo
    periodo_dias = st.selectbox(
        "Periodo",
        options=[7, 30, 90, 365],
        format_func=lambda x: f"Ultimos {x} dias",
        index=1,
        key="opr_periodo",
    )
    cutoff = (_dt.now(_tz.utc) - _td(days=periodo_dias)).isoformat()

    # Query raw events
    try:
        events_r = db.client.table("opr_pageviews").select(
            "id, inep, company_id, event_type, benchmark_viewed, session_id, viewed_at"
        ).gt("viewed_at", cutoff).execute()
        events = events_r.data or []
    except Exception as _e:
        if "opr_pageviews" in str(_e).lower() or "does not exist" in str(_e).lower():
            alert_banner(
                "Tabela `opr_pageviews` ainda nao foi criada. "
                "Rode o SQL em `database/migrations/016_opr_pageviews.sql` no Supabase.",
                "warning",
            )
            events = []
        else:
            raise

    # KPIs
    inep_set = set(ev["inep"] for ev in events if ev.get("inep"))
    page_loads = [ev for ev in events if ev.get("event_type") == "page_load"]
    tab_clicks = [ev for ev in events if ev.get("event_type") == "tab_click"]
    cta_clicks = [ev for ev in events if ev.get("event_type") == "cta_click"]
    unique_sessions = len(set(ev.get("session_id") for ev in events if ev.get("session_id")))

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("OPRs Abertos", len(inep_set), help="Numero de escolas cujos OPRs foram acessados")
    with c2:
        st.metric("Total Pageviews", len(page_loads))
    with c3:
        st.metric("Visitantes unicos", unique_sessions, help="Sessions unicas via localStorage")
    with c4:
        st.metric("Tab Clicks", len(tab_clicks))
    with c5:
        st.metric("CTA Clicks", len(cta_clicks), help="Cliques em 'Conhecer a IAprendo'")

    # Aba mais visualizada
    from collections import Counter
    bench_counts = Counter(ev.get("benchmark_viewed") for ev in tab_clicks if ev.get("benchmark_viewed"))
    if bench_counts:
        most_common = bench_counts.most_common(1)[0]
        st.markdown(f"**Aba mais visualizada**: {most_common[0]} ({most_common[1]} cliques de {sum(bench_counts.values())} totais)")

    # Top OPRs mais acessados
    if events:
        st.markdown("### Top OPRs Mais Acessados")
        # Agrupar por INEP
        by_inep: dict = {}
        for ev in events:
            inep = ev.get("inep")
            if not inep:
                continue
            if inep not in by_inep:
                by_inep[inep] = {
                    "pageviews": 0, "unique_sessions": set(),
                    "benchmarks": set(), "last_viewed": ev.get("viewed_at", ""),
                    "company_id": ev.get("company_id"),
                }
            by_inep[inep]["pageviews"] += 1
            if ev.get("session_id"):
                by_inep[inep]["unique_sessions"].add(ev.get("session_id"))
            if ev.get("benchmark_viewed"):
                by_inep[inep]["benchmarks"].add(ev.get("benchmark_viewed"))
            if ev.get("viewed_at", "") > by_inep[inep]["last_viewed"]:
                by_inep[inep]["last_viewed"] = ev.get("viewed_at", "")

        # Buscar nomes das escolas
        inep_ids = list(by_inep.keys())
        try:
            r = db.client.table("companies").select("id, inep_code, name, city, state").in_(
                "inep_code", inep_ids
            ).execute()
            inep_to_company = {str(c["inep_code"]): c for c in (r.data or [])}
        except Exception:
            inep_to_company = {}

        # Tabela
        rows = []
        for inep, data in by_inep.items():
            comp = inep_to_company.get(str(inep), {})
            rows.append({
                "Escola": comp.get("name", f"INEP {inep}"),
                "Cidade": f"{comp.get('city', '?')}/{comp.get('state', '?')}",
                "Pageviews": data["pageviews"],
                "Visitantes": len(data["unique_sessions"]),
                "Abas exploradas": ", ".join(sorted(data["benchmarks"])) or "-",
                "Ultimo acesso": data["last_viewed"][:16] if data["last_viewed"] else "-",
            })
        rows.sort(key=lambda x: x["Pageviews"], reverse=True)

        import pandas as _pd
        df_opr = _pd.DataFrame(rows[:20])
        if not df_opr.empty:
            st.dataframe(df_opr, use_container_width=True, hide_index=True)

    # Distribuicao por benchmark
    if tab_clicks:
        st.markdown("### Distribuicao de Cliques por Benchmark")
        import pandas as _pd
        df_bench = _pd.DataFrame([
            {"Benchmark": k, "Cliques": v}
            for k, v in bench_counts.most_common()
        ])
        if not df_bench.empty:
            st.bar_chart(df_bench.set_index("Benchmark")["Cliques"], height=220)

    if not events:
        st.info(
            "Ainda nao ha eventos de tracking registrados. "
            "Quando alguem abrir um OPR (com TRACK_URL configurado), os eventos aparecerao aqui."
        )

except Exception as _e:
    st.caption(f"OPR tracking indisponivel: {_e}")
