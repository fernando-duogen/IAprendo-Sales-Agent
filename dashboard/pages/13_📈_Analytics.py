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

    # Companies por status
    try:
        comps = db.client.table("companies").select(
            "id,status,city,admin_category,qualification_score,created_at"
        ).execute().data or []
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
                delta=f"{total_credits} credits")

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
        "Score": s.get("qualification_score", 0),
        "Status": s.get("status", ""),
    } for s in top_schools]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100)})
else:
    st.info("Nenhuma escola qualificada ainda.")
