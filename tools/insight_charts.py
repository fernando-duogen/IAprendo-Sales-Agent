"""Gerador de graficos de insight para emails de prospecçao.

Gera PNGs otimizados para email (600x400px, fundo branco, fontes grandes)
com dados personalizados por escola vs benchmarks. Tres tipos de grafico:

1. Radar ENEM — 5 areas do ENEM, escola vs municipio/estado
2. Gap indicator — card visual com gap numerico na area mais fraca
3. Trend chart — evolucao de matriculas ou docentes vs benchmark

Cada funcao retorna bytes PNG (ou None se dados insuficientes).
Upload para Supabase Storage e feito pelo caller (supabase_client.upload_chart).

Requer: pip install kaleido (export estatico do Plotly)

Usage:
    from tools.insight_charts import generate_radar_chart, generate_gap_indicator, generate_trend_chart

    png_bytes = generate_radar_chart("43238203", benchmark="municipio")
    if png_bytes:
        url = db.upload_chart("43238203/radar_20260412.png", png_bytes)
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import plotly.graph_objects as go
except ImportError:
    go = None  # type: ignore

from utils.logger import logger


# ============================================================================
# CONSTANTES DE DESIGN (otimizado para email)
# ============================================================================

# Cores
COLOR_SCHOOL = "#2563EB"        # Azul forte (escola)
COLOR_SCHOOL_FILL = "rgba(37, 99, 235, 0.15)"
COLOR_BENCHMARK = "#9CA3AF"     # Cinza (benchmark)
COLOR_BENCHMARK_FILL = "rgba(156, 163, 175, 0.08)"
COLOR_GAP_NEGATIVE = "#EF4444"  # Vermelho (gap negativo)
COLOR_GAP_POSITIVE = "#10B981"  # Verde (gap positivo)
COLOR_TREND_SCHOOL = "#2563EB"
COLOR_TREND_BENCH = "#9CA3AF"

# Labels PT-BR para as 5 areas do ENEM
AREA_LABELS = {
    "enem_media_mt": "Matematica",
    "enem_media_cn": "Ciencias\nda Natureza",
    "enem_media_ch": "Ciencias\nHumanas",
    "enem_media_lc": "Linguagens",
    "enem_media_redacao": "Redacao",
}
AREA_KEYS = list(AREA_LABELS.keys())

# Labels PT-BR para as 5 competencias da redacao
COMP_LABELS = {
    "enem_redacao_comp1_media": "C1: Norma\nCulta",
    "enem_redacao_comp2_media": "C2: Compreensao\ndo Tema",
    "enem_redacao_comp3_media": "C3: Argumentacao",
    "enem_redacao_comp4_media": "C4: Coesao\nTextual",
    "enem_redacao_comp5_media": "C5: Proposta\nde Intervencao",
}
COMP_KEYS = list(COMP_LABELS.keys())

# Dimensoes (px)
RADAR_WIDTH = 600
RADAR_HEIGHT = 420
GAP_WIDTH = 500
GAP_HEIGHT = 200
TREND_WIDTH = 600
TREND_HEIGHT = 320
EXPORT_SCALE = 2  # 2x para retina


# ============================================================================
# HELPERS INTERNOS
# ============================================================================

def _get_db():
    """Lazy import do database client."""
    from database.supabase_client import db
    return db


def _fetch_school_data(inep: str) -> Optional[Dict[str, Any]]:
    """Busca dados da escola em school_analytics."""
    db = _get_db()
    try:
        fields = ",".join(AREA_KEYS + COMP_KEYS + [
            "inep_code", "enem_dependencia", "enem_gap_vs_peer_2024",
            "enem_area_mais_fraca", "enem_potencial_melhoria",
            "enem_amostra_confiavel", "enem_presentes",
            "peer_mun_nome", "peer_uf_sigla",
        ])
        r = db.client.table("school_analytics").select(fields).eq(
            "inep_code", str(inep).strip()
        ).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        logger.warning(f"insight_charts: fetch school failed: {e}")
        return None


def _fetch_benchmark(
    municipio: str, uf: str, dependencia: str, metrics: List[str]
) -> Dict[str, Optional[float]]:
    """Busca media do benchmark (municipio x dependencia) para as metricas."""
    db = _get_db()
    try:
        fields = ",".join(metrics + ["inep_code"])
        q = db.client.table("school_analytics").select(fields).eq(
            "enem_amostra_confiavel", True
        )
        if municipio:
            q = q.ilike("peer_mun_nome", f"%{municipio}%")
        if uf:
            q = q.eq("peer_uf_sigla", uf.upper())
        if dependencia:
            q = q.eq("enem_dependencia", dependencia)
        r = q.limit(1000).execute()
        rows = r.data or []
        if not rows:
            return {}
        # Calcular media por metrica
        result = {}
        for m in metrics:
            vals = [float(row[m]) for row in rows if row.get(m) is not None]
            result[m] = round(sum(vals) / len(vals), 2) if vals else None
        return result
    except Exception as e:
        logger.warning(f"insight_charts: fetch benchmark failed: {e}")
        return {}


def _resolve_school_name(inep: str) -> str:
    """Resolve nome da escola via companies ou school_censo_yearly."""
    try:
        from agent.tools.enem_tools import _resolve_school_names
        names = _resolve_school_names([inep])
        return names.get(inep, {}).get("name") or f"INEP {inep}"
    except Exception:
        return f"INEP {inep}"


def _to_png(fig: "go.Figure", width: int, height: int) -> Optional[bytes]:
    """Exporta Plotly figure para PNG bytes."""
    if go is None:
        return None
    try:
        return fig.to_image(
            format="png", width=width, height=height, scale=EXPORT_SCALE
        )
    except Exception as e:
        logger.warning(f"insight_charts: to_image failed: {e}")
        return None


# ============================================================================
# GERADOR 1: RADAR ENEM (5 areas)
# ============================================================================

def generate_radar_chart(
    inep: str,
    benchmark: str = "municipio",
    include_comps: bool = False,
) -> Optional[bytes]:
    """Gera radar ENEM 5 areas (+ opcionalmente 5 competencias redacao).

    Args:
        inep: Codigo INEP da escola.
        benchmark: "municipio" (default), "estado" ou "brasil".
        include_comps: Se True, gera segundo radar com competencias de redacao.

    Returns:
        PNG bytes ou None se dados insuficientes.
    """
    if go is None:
        return None

    school = _fetch_school_data(inep)
    if not school or school.get("enem_amostra_confiavel") is not True:
        return None

    nome = _resolve_school_name(inep)
    municipio = school.get("peer_mun_nome") or ""
    uf = school.get("peer_uf_sigla") or ""
    dep = school.get("enem_dependencia") or ""

    # Metricas da escola
    metrics = AREA_KEYS
    labels_map = AREA_LABELS
    school_vals = [school.get(m) for m in metrics]
    if not any(v is not None for v in school_vals):
        return None

    # Benchmark
    bench_data = _fetch_benchmark(
        municipio if benchmark == "municipio" else "",
        uf if benchmark in ("municipio", "estado") else "",
        dep,
        metrics,
    )
    bench_vals = [bench_data.get(m) for m in metrics]

    # Labels
    labels = [labels_map[m] for m in metrics]

    # Fechar poligono
    s_vals = [float(v) if v is not None else 0 for v in school_vals]
    b_vals = [float(v) if v is not None else 0 for v in bench_vals]
    s_closed = s_vals + [s_vals[0]]
    b_closed = b_vals + [b_vals[0]]
    l_closed = labels + [labels[0]]

    # Benchmark label
    if benchmark == "municipio":
        bench_label = f"Media {dep} de {municipio}"
    elif benchmark == "estado":
        bench_label = f"Media {dep} do {uf}"
    else:
        bench_label = f"Media {dep} Brasil"

    # Construir figura
    fig = go.Figure()

    # Benchmark trace (cinza, atras)
    if any(v > 0 for v in b_closed):
        fig.add_trace(go.Scatterpolar(
            r=b_closed,
            theta=l_closed,
            fill="toself",
            name=bench_label,
            line=dict(color=COLOR_BENCHMARK, width=2, dash="dot"),
            fillcolor=COLOR_BENCHMARK_FILL,
            opacity=0.6,
        ))

    # Escola trace (azul, frente)
    fig.add_trace(go.Scatterpolar(
        r=s_closed,
        theta=l_closed,
        fill="toself",
        name=nome[:40],
        line=dict(color=COLOR_SCHOOL, width=3),
        fillcolor=COLOR_SCHOOL_FILL,
        opacity=0.9,
    ))

    # Range
    all_vals = [v for v in s_vals + b_vals if v > 0]
    max_val = max(all_vals) * 1.1 if all_vals else 800

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max_val],
                tickfont=dict(size=10, color="#999"),
                gridcolor="#E5E7EB",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color="#333"),
                gridcolor="#E5E7EB",
            ),
            bgcolor="white",
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.12,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
        ),
        title=dict(
            text=f"Performance ENEM 2024<br><span style='font-size:12px;color:#666'>"
                 f"{nome[:50]} vs {bench_label}</span>",
            font=dict(size=14, color="#333"),
            x=0.5,
            xanchor="center",
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=70, r=70, t=70, b=60),
        height=RADAR_HEIGHT,
        width=RADAR_WIDTH,
    )

    return _to_png(fig, RADAR_WIDTH, RADAR_HEIGHT)


# ============================================================================
# GERADOR 2: GAP INDICATOR
# ============================================================================

def generate_gap_indicator(inep: str) -> Optional[bytes]:
    """Gera card visual com o gap numerico na area mais fraca.

    Returns:
        PNG bytes ou None se sem gap significativo.
    """
    if go is None:
        return None

    school = _fetch_school_data(inep)
    if not school:
        return None

    gap = school.get("enem_gap_vs_peer_2024")
    area_fraca = school.get("enem_area_mais_fraca")
    if gap is None or area_fraca is None:
        return None

    gap_val = float(gap)
    if abs(gap_val) < 3:
        return None  # Gap insignificante

    nome = _resolve_school_name(inep)
    color = COLOR_GAP_NEGATIVE if gap_val < 0 else COLOR_GAP_POSITIVE
    icon = "▼" if gap_val < 0 else "▲"
    label = "abaixo" if gap_val < 0 else "acima"

    fig = go.Figure()

    # Card como anotacao (Plotly nao tem cards nativos)
    fig.add_annotation(
        text=f"<b style='font-size:48px;color:{color}'>{icon} {abs(gap_val):.0f} pts</b>",
        xref="paper", yref="paper",
        x=0.5, y=0.65,
        showarrow=False,
        font=dict(size=48, color=color),
    )
    fig.add_annotation(
        text=f"<b>{label} do peer</b> em <b>{area_fraca}</b>",
        xref="paper", yref="paper",
        x=0.5, y=0.3,
        showarrow=False,
        font=dict(size=16, color="#555"),
    )
    fig.add_annotation(
        text=f"{nome[:45]}",
        xref="paper", yref="paper",
        x=0.5, y=0.08,
        showarrow=False,
        font=dict(size=11, color="#999"),
    )

    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
        height=GAP_HEIGHT,
        width=GAP_WIDTH,
    )

    return _to_png(fig, GAP_WIDTH, GAP_HEIGHT)


# ============================================================================
# GERADOR 3: TREND CHART (serie temporal)
# ============================================================================

def generate_trend_chart(
    inep: str,
    metric: str = "qt_mat_bas",
    metric_label: str = "Matriculas Totais",
) -> Optional[bytes]:
    """Gera grafico de linhas: escola vs media do municipio ao longo dos anos.

    Args:
        inep: Codigo INEP.
        metric: Campo do school_censo_yearly (ex: qt_mat_bas, qt_doc_bas).
        metric_label: Label em PT-BR para o eixo Y.

    Returns:
        PNG bytes ou None se dados insuficientes.
    """
    if go is None:
        return None

    db = _get_db()
    nome = _resolve_school_name(inep)

    # Buscar serie da escola
    try:
        r = db.client.table("school_censo_yearly").select(
            f"vintage_censo,{metric},city,state"
        ).eq("inep_code", str(inep).strip()).order("vintage_censo").execute()
        school_series = r.data or []
    except Exception:
        return None

    if len(school_series) < 2:
        return None

    years = [row["vintage_censo"] for row in school_series]
    school_vals = [row.get(metric) for row in school_series]
    city = school_series[0].get("city") or ""
    state = school_series[0].get("state") or ""

    # Buscar benchmark (media do municipio por ano)
    bench_vals = []
    for year in years:
        try:
            r = db.client.table("school_censo_yearly").select(metric).eq(
                "vintage_censo", year
            ).eq("city", city).execute()
            vals = [float(row[metric]) for row in (r.data or []) if row.get(metric) is not None]
            bench_vals.append(round(sum(vals) / len(vals), 1) if vals else None)
        except Exception:
            bench_vals.append(None)

    fig = go.Figure()

    # Benchmark
    b_valid = [(y, v) for y, v in zip(years, bench_vals) if v is not None]
    if b_valid:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in b_valid],
            y=[p[1] for p in b_valid],
            mode="lines+markers",
            name=f"Media {city}",
            line=dict(color=COLOR_TREND_BENCH, width=2, dash="dot"),
            marker=dict(size=6, color=COLOR_TREND_BENCH),
        ))

    # Escola
    s_valid = [(y, v) for y, v in zip(years, school_vals) if v is not None]
    if s_valid:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in s_valid],
            y=[p[1] for p in s_valid],
            mode="lines+markers+text",
            name=nome[:35],
            line=dict(color=COLOR_TREND_SCHOOL, width=3),
            marker=dict(size=8, color=COLOR_TREND_SCHOOL),
            text=[str(int(p[1])) for p in s_valid],
            textposition="top center",
            textfont=dict(size=10, color=COLOR_TREND_SCHOOL),
        ))

    fig.update_layout(
        title=dict(
            text=f"Evolucao {metric_label}<br>"
                 f"<span style='font-size:12px;color:#666'>"
                 f"{nome[:45]} vs Media de {city}</span>",
            font=dict(size=14, color="#333"),
            x=0.5, xanchor="center",
        ),
        xaxis=dict(
            title="Ano", dtick=1,
            gridcolor="#F3F4F6",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title=metric_label,
            gridcolor="#F3F4F6",
            tickfont=dict(size=11),
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.18,
            xanchor="center", x=0.5, font=dict(size=11),
        ),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=60, r=30, t=70, b=60),
        height=TREND_HEIGHT,
        width=TREND_WIDTH,
    )

    return _to_png(fig, TREND_WIDTH, TREND_HEIGHT)


# ============================================================================
# HELPER: Gerar todos os charts relevantes para uma escola
# ============================================================================

def generate_all_relevant_charts(
    inep: str,
    benchmark: str = "municipio",
) -> List[Dict[str, Any]]:
    """Gera todos os graficos relevantes para uma escola.

    Decide automaticamente quais charts gerar baseado nos dados disponiveis.

    Returns:
        Lista de dicts: [{"type": "radar", "bytes": PNG, "filename": "..."}, ...]
    """
    from datetime import date
    today = date.today().strftime("%Y%m%d")
    charts: List[Dict[str, Any]] = []

    # 1. Radar ENEM (sempre, se tiver amostra confiavel)
    radar = generate_radar_chart(inep, benchmark=benchmark)
    if radar:
        charts.append({
            "type": "radar",
            "bytes": radar,
            "filename": f"{inep}/radar_{today}.png",
            "alt": "Performance ENEM 2024 por area",
        })

    # 2. Gap indicator (se gap significativo)
    gap = generate_gap_indicator(inep)
    if gap:
        charts.append({
            "type": "gap",
            "bytes": gap,
            "filename": f"{inep}/gap_{today}.png",
            "alt": "Gap vs peer group",
        })

    # 3. Trend de matriculas (se tiver serie historica)
    trend = generate_trend_chart(inep, "qt_mat_bas", "Matriculas Totais")
    if trend:
        charts.append({
            "type": "trend",
            "bytes": trend,
            "filename": f"{inep}/trend_mat_{today}.png",
            "alt": "Evolucao de matriculas",
        })

    return charts
