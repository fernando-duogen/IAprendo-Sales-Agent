"""Gerador de One Page Report — pagina HTML personalizada por escola.

Gera um HTML estatico auto-contido (charts embutidos como base64 PNG,
CSS inline, zero dependencias externas) que e hospedado via GitHub Pages
como URL publica permanente.

O report mostra:
- Header com nome da escola + cidade + badges (sem info interna)
- Metricas rapidas com media_geral SEMPRE visivel
- Radar ENEM 5 areas vs benchmark (gated por amostra_confiavel)
- Comparacao por area (HTML cards, escola vs benchmark, 5 areas ENEM)
- Evolucao de matriculas vs media local
- Insights reframed como oportunidades
- CTA orientado a solucao
- Footnotes por secao com fontes

Usage:
    from tools.report_generator import generate_report, generate_and_upload_report

    # Gerar HTML + upload → URL publica
    result = generate_and_upload_report("43216684")
    print(result["html_url"])  # https://...github.io/.../reports/43216684.html
"""
import base64
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.logger import logger


# ============================================================================
# TEMPLATE HTML (CSS inline, auto-contido, responsivo)
# ============================================================================

_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Diagnostico ENEM 2024 — {escola_nome}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #333;
    background: #f5f7fa;
    line-height: 1.6;
  }}
  .container {{
    max-width: 720px;
    margin: 0 auto;
    background: white;
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
  }}
  .header {{
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white;
    padding: 40px 32px 32px;
  }}
  .header h1 {{
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 4px;
  }}
  .header .subtitle {{
    font-size: 14px;
    opacity: 0.85;
    margin-bottom: 16px;
  }}
  .header .badges {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    background: rgba(255,255,255,0.2);
  }}
  .badge.warn {{ background: rgba(239,68,68,0.3); }}
  .badge.good {{ background: rgba(16,185,129,0.3); }}
  .section {{
    padding: 28px 32px;
    border-bottom: 1px solid #f0f0f0;
  }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{
    font-size: 16px;
    font-weight: 700;
    color: #1e3a5f;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .section-title .icon {{
    font-size: 20px;
  }}
  .chart-container {{
    text-align: center;
    margin: 16px 0;
  }}
  .chart-container img {{
    max-width: 100%;
    height: auto;
    border-radius: 8px;
  }}
  .chart-caption {{
    font-size: 11px;
    color: #999;
    margin-top: 6px;
  }}
  .insight-card {{
    background: #f8f9fa;
    border-left: 4px solid #2563eb;
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 0 8px 8px 0;
    font-size: 14px;
  }}
  .insight-card.warn {{
    border-left-color: #f59e0b;
  }}
  .insight-card.opportunity {{
    border-left-color: #f59e0b;
  }}
  .insight-card.highlight {{
    border-left-color: #10B981;
  }}
  .insight-card .card-title {{
    font-weight: 700;
    font-size: 13px;
    margin-bottom: 4px;
  }}
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin: 16px 0;
  }}
  .metric-box {{
    text-align: center;
    padding: 12px 8px;
    background: #f8f9fa;
    border-radius: 8px;
  }}
  .metric-box .value {{
    font-size: 24px;
    font-weight: 700;
    color: #1e3a5f;
  }}
  .metric-box .label {{
    font-size: 11px;
    color: #888;
    margin-top: 2px;
  }}
  .footnote {{
    font-size: 10px;
    color: #aaa;
    margin-top: 6px;
    font-style: italic;
  }}
  .comparison-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin: 16px 0;
  }}
  .comp-card {{
    text-align: center;
    padding: 14px 8px;
    border-radius: 8px;
    background: #f8f9fa;
    border-top: 3px solid #e0e0e0;
  }}
  .comp-card.above {{ border-top-color: #10B981; }}
  .comp-card.below {{ border-top-color: #EF4444; }}
  .comp-card .area-name {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  .comp-card .area-value {{ font-size: 20px; font-weight: 700; color: #333; }}
  .comp-card .area-diff {{ font-size: 12px; font-weight: 600; margin-top: 2px; }}
  .comp-card .area-diff.positive {{ color: #10B981; }}
  .comp-card .area-diff.negative {{ color: #EF4444; }}
  .comp-card .bench-val {{ font-size: 10px; color: #999; margin-top: 2px; }}
  .cta {{
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    color: white;
    padding: 32px;
    text-align: center;
  }}
  .cta h2 {{
    font-size: 20px;
    margin-bottom: 8px;
  }}
  .cta p {{
    font-size: 14px;
    opacity: 0.9;
    margin-bottom: 20px;
  }}
  .cta-button {{
    display: inline-block;
    padding: 14px 32px;
    background: white;
    color: #2563eb;
    font-weight: 700;
    font-size: 15px;
    border-radius: 8px;
    text-decoration: none;
    transition: transform 0.2s;
  }}
  .cta-button:hover {{
    transform: translateY(-2px);
  }}
  .footer {{
    padding: 20px 32px;
    text-align: center;
    font-size: 11px;
    color: #999;
    background: #f8f9fa;
  }}
  @media (max-width: 600px) {{
    .header {{ padding: 24px 16px; }}
    .section {{ padding: 20px 16px; }}
    .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .comparison-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .header h1 {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div class="subtitle">Diagnostico de Performance ENEM 2024</div>
        <h1>{escola_nome}</h1>
        <div class="subtitle">{cidade}/{uf} &bull; {dependencia}</div>
      </div>
      {logo_html}
    </div>
    <div class="badges" style="margin-top:12px">
      {info_badges_html}
    </div>
    <div class="badges" style="margin-top:6px">
      {ranking_badges_html}
    </div>
  </div>

  <!-- METRICAS RAPIDAS -->
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Visao Geral</div>
    <div class="metrics-grid">
      <div class="metric-box">
        <div class="value">{media_geral}</div>
        <div class="label">Media Geral ENEM</div>
      </div>
      <div class="metric-box">
        <div class="value">{presentes}</div>
        <div class="label">Alunos Presentes</div>
      </div>
      <div class="metric-box">
        <div class="value">{gap_display_html}</div>
        <div class="label">Diferenca vs Escolas Similares</div>
      </div>
    </div>
  </div>

  <!-- RADAR ENEM -->
  {radar_section}

  <!-- COMPARACAO POR AREA -->
  {comparison_section}

  <!-- EVOLUCAO MATRICULAS -->
  {trend_section}

  <!-- INSIGHTS -->
  {insights_section}

  <!-- CTA -->
  <div class="cta">
    <h2>Pronto para transformar o aprendizado?</h2>
    <p>Conheca a IAprendo: exercicios adaptativos, alinhados a BNCC, que ajudam cada aluno no seu ritmo. Melhore os resultados, inove na pedagogia e atraia mais matriculas.</p>
    <a href="{meeting_link}" class="cta-button">Conhecer a IAprendo</a>
  </div>

  <!-- FOOTER -->
  <div class="footer" style="display:flex;justify-content:space-between;align-items:center">
    <div>
      Fonte: Microdados ENEM 2024 e Censo Escolar 2020-2025 (INEP/MEC)<br>
      Analise gerada por <a href="https://iaprendo.com.br" target="_blank" style="color:#2563eb;text-decoration:none">IAprendo</a> &bull; {data_geracao}
    </div>
    {robot_html}
  </div>

</div>
</body>
</html>"""


def _img_to_base64(png_bytes: bytes) -> str:
    """Converte PNG bytes para data URI base64."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ============================================================================
# HELPERS: fetch media_geral e benchmark para comparison cards
# ============================================================================

def _fetch_media_geral(inep: str) -> Optional[float]:
    """Busca enem_media_geral diretamente de school_analytics, SEM gate de amostra_confiavel.

    media_geral e dado bruto do INEP — sempre valido para exibicao, independente
    do tamanho da amostra.
    """
    try:
        from database.supabase_client import db
        r = db.client.table("school_analytics").select(
            "enem_media_geral"
        ).eq("inep_code", str(inep).strip()).limit(1).execute()
        if r.data and r.data[0].get("enem_media_geral") is not None:
            return float(r.data[0]["enem_media_geral"])
        return None
    except Exception as e:
        logger.debug(f"report_generator: fetch media_geral failed: {e}")
        return None


def _build_comparison_cards(
    school: Dict[str, Any],
    bench_data: Dict[str, Optional[float]],
    bench_count: int,
    dep: str,
    cidade: str,
) -> str:
    """Gera HTML grid de cards comparativos: escola vs benchmark para cada area ENEM.

    Cada card mostra: area name, valor da escola, diferenca, valor do benchmark.
    Verde para acima do benchmark, vermelho para abaixo.
    """
    from tools.insight_charts import AREA_KEYS, AREA_LABELS

    area_display_names = {
        "enem_media_mt": "Matematica",
        "enem_media_cn": "Ciencias da Natureza",
        "enem_media_ch": "Ciencias Humanas",
        "enem_media_lc": "Linguagens",
        "enem_media_redacao": "Redacao",
    }

    cards_html = []

    # 6th card: Media Geral (placed first for 3x2 grid layout)
    mg_school = school.get("enem_media_geral")
    if mg_school is None:
        # fallback: fetch from dedicated helper
        mg_school_raw = _fetch_media_geral(str(school.get("inep_code", "")))
        mg_school = mg_school_raw
    if mg_school is not None:
        mg_sv = float(mg_school)
        mg_bv = bench_data.get("enem_media_geral")
        if mg_bv is not None:
            mg_bv = float(mg_bv)
            mg_diff = mg_sv - mg_bv
            mg_css = "above" if mg_diff >= 0 else "below"
            mg_diff_class = "positive" if mg_diff >= 0 else "negative"
            mg_diff_display = f"{mg_diff:+.0f} pts"
            mg_bench_display = f"Benchmark: {mg_bv:.0f}"
        else:
            mg_css = ""
            mg_diff_class = ""
            mg_diff_display = ""
            mg_bench_display = ""
        cards_html.append(
            f'<div class="comp-card {mg_css}">'
            f'<div class="area-name">Media Geral</div>'
            f'<div class="area-value">{mg_sv:.0f}</div>'
            f'<div class="area-diff {mg_diff_class}">{mg_diff_display}</div>'
            f'<div class="bench-val">{mg_bench_display}</div>'
            f'</div>'
        )

    for key in AREA_KEYS:
        school_val = school.get(key)
        bench_val = bench_data.get(key)
        area_name = area_display_names.get(key, AREA_LABELS.get(key, key))

        if school_val is None:
            continue

        sv = float(school_val)
        sv_display = f"{sv:.0f}"

        if bench_val is not None:
            bv = float(bench_val)
            diff = sv - bv
            css_class = "above" if diff >= 0 else "below"
            diff_class = "positive" if diff >= 0 else "negative"
            diff_display = f"{diff:+.0f} pts"
            bench_display = f"Benchmark: {bv:.0f}"
        else:
            css_class = ""
            diff_class = ""
            diff_display = ""
            bench_display = ""

        card = (
            f'<div class="comp-card {css_class}">'
            f'<div class="area-name">{area_name}</div>'
            f'<div class="area-value">{sv_display}</div>'
            f'<div class="area-diff {diff_class}">{diff_display}</div>'
            f'<div class="bench-val">{bench_display}</div>'
            f'</div>'
        )
        cards_html.append(card)

    if not cards_html:
        return ""

    return "\n      ".join(cards_html)


def _reframe_insight_as_opportunity(insight_text: str, index: int = 0) -> Tuple[str, str, str]:
    """Reframe um insight observacional como oportunidade ou destaque.

    Args:
        insight_text: Texto observacional gerado por _detectar_insights.
        index: Indice do insight na lista (para rotacionar templates).

    Returns:
        Tuple de (titulo, texto reframed, css_class).
        - Insights negativos -> oportunidade com sugestao pratica
        - Insights positivos -> destaque com beneficio de manter vantagem
    """
    negative_signals = [
        # Censo
        "piorou", "regrediu", "encolheu", "queda", "perda",
        "superou a contratacao", "pressao financeira",
        # ENEM
        "abaixo", "gap", "apenas", "fraca", "fraco",
        "menor", "deficit", "defasagem",
    ]

    is_negative = any(signal in insight_text.lower() for signal in negative_signals)

    # 5 templates rotativos para oportunidades (negative insights)
    opportunity_templates = [
        "{obs} — com aprendizado adaptativo e exercicios personalizados, e possivel reverter essa tendencia e posicionar a escola como referencia em inovacao.",
        "{obs} — a plataforma IAprendo oferece reforco personalizado alinhado a BNCC, ajudando cada aluno no seu ritmo e fortalecendo a confianca dos pais.",
        "{obs} — tecnologia educacional com exercicios adaptativos pode compensar essa lacuna, atrair mais matriculas e diferenciar a escola na regiao.",
        "{obs} — com apoio as familias e acompanhamento individualizado, a IAprendo ajuda a transformar esse desafio em oportunidade de crescimento.",
        "{obs} — exercicios adaptativos e reforco personalizado permitem que cada aluno evolua no seu ritmo, melhorando os resultados e a reputacao da escola.",
    ]

    # 5 templates rotativos para destaques (positive insights)
    highlight_templates = [
        "{obs} — manter essa vantagem com aprendizado adaptativo pode consolidar a escola como referencia e atrair ainda mais matriculas.",
        "{obs} — a plataforma IAprendo pode potencializar esse resultado com exercicios personalizados que mantem cada aluno em evolucao constante.",
        "{obs} — tecnologia educacional alinhada a BNCC ajuda a sustentar esse diferencial e fortalecer a confianca das familias na escola.",
        "{obs} — com reforco personalizado, a escola pode ampliar essa vantagem e se posicionar como lider em inovacao pedagogica na regiao.",
        "{obs} — exercicios adaptativos ajudam a manter esse patamar e garantem que os alunos sigam evoluindo de forma consistente.",
    ]

    if is_negative:
        template = opportunity_templates[index % len(opportunity_templates)]
        reframed = template.format(obs=insight_text)
    else:
        template = highlight_templates[index % len(highlight_templates)]
        reframed = template.format(obs=insight_text)

    # Bold em numeros e trechos chave (sem excessos)
    import re
    # Bold em valores numericos com unidade (ex: "5.2:1", "+30.2%", "-17.5 pts")
    reframed = re.sub(
        r'(\d+[.,]?\d*(?::\d+|%| pts| pontos| escolas| alunos))',
        r'<b>\1</b>',
        reframed,
    )
    # Bold em palavras-chave de oportunidade/destaque
    for keyword in ["IAprendo", "aprendizado adaptativo", "exercicios adaptativos",
                     "reforco personalizado", "tecnologia educacional"]:
        reframed = reframed.replace(keyword, f"<b>{keyword}</b>", 1)  # so 1x por keyword

    title = "Oportunidade" if is_negative else "Destaque"
    css_class = "opportunity" if is_negative else "highlight"
    return (title, reframed, css_class)


# ============================================================================
# GERADOR PRINCIPAL
# ============================================================================

def generate_report(inep: str) -> Optional[Dict[str, Any]]:
    """Gera o HTML do One Page Report para uma escola.

    Args:
        inep: Codigo INEP da escola.

    Returns:
        Dict com {"html": str, "escola_nome": str, "inep": str} ou None se dados insuficientes.
    """
    from database.supabase_client import db
    from tools.insight_charts import (
        generate_radar_chart,
        generate_trend_chart,
        _fetch_school_data,
        _fetch_benchmark,
        _resolve_school_name,
        AREA_KEYS,
    )

    # Buscar dados da escola
    school = _fetch_school_data(str(inep))
    if not school:
        logger.warning(f"report_generator: escola {inep} nao encontrada em school_analytics")
        return None

    nome = _resolve_school_name(str(inep))
    cidade = school.get("peer_mun_nome") or "?"
    uf = school.get("peer_uf_sigla") or "?"
    dep = school.get("enem_dependencia") or "?"
    presentes = school.get("enem_presentes")
    gap = school.get("enem_gap_vs_peer_2024")
    area_fraca = school.get("enem_area_mais_fraca")
    confiavel = school.get("enem_amostra_confiavel") is True

    # Fetch media_geral WITHOUT confiavel gate — raw INEP data, always valid
    media_geral_raw = _fetch_media_geral(str(inep))

    # --- Badges em 2 linhas: info (linha 1) + ranking (linha 2) ---
    info_badges = []
    if presentes:
        info_badges.append(f'<span class="badge">{int(presentes)} alunos no ENEM</span>')
    if dep and dep != "?":
        info_badges.append(f'<span class="badge">{dep}</span>')
    if area_fraca:
        info_badges.append(f'<span class="badge warn">Area fraca: {area_fraca}</span>')
    info_badges_html = "\n      ".join(info_badges)

    # Rankings (linha 2)
    ranking_badges = []
    rank_mun = school.get("enem_rank_mun")
    rank_uf = school.get("enem_rank_uf_dep")
    rank_br = school.get("enem_rank_br")
    if rank_mun:
        ranking_badges.append(f'<span class="badge">🏙️ #{int(rank_mun)}ª em {cidade}</span>')
    if rank_uf:
        ranking_badges.append(f'<span class="badge">🗺️ #{int(rank_uf)}ª no {uf}</span>')
    if rank_br:
        ranking_badges.append(f'<span class="badge">🇧🇷 #{int(rank_br)}ª no Brasil</span>')
    ranking_badges_html = "\n      ".join(ranking_badges)

    # --- Logo (header) e Robot (footer) ---
    # Tenta carregar imagens locais; se não existirem, não mostra
    logo_html = ""
    robot_html = ""
    brand_dir = ROOT / "data" / "brand"
    logo_path = brand_dir / "logo_iaprendo.png"
    robot_path = brand_dir / "robot_icon.png"
    if logo_path.exists():
        logo_b64 = _img_to_base64(logo_path.read_bytes())
        logo_html = (
            f'<a href="https://iaprendo.com.br" target="_blank" style="text-decoration:none">'
            f'<img src="{logo_b64}" alt="IAprendo" style="height:45px;border-radius:6px">'
            f'</a>'
        )
    if robot_path.exists():
        robot_b64 = _img_to_base64(robot_path.read_bytes())
        robot_html = (
            f'<a href="https://iaprendo.com.br" target="_blank" style="text-decoration:none">'
            f'<img src="{robot_b64}" alt="IAprendo" style="height:35px;border-radius:50%">'
            f'</a>'
        )

    # --- Metricas rapidas (media_geral ALWAYS shown) ---
    media_display = f"{media_geral_raw:.1f}" if media_geral_raw is not None else "—"
    pres_display = str(int(presentes)) if presentes else "—"
    if gap is not None:
        g = float(gap)
        gap_display = f"{g:+.0f} pts"
        color = "#10B981" if g >= 0 else "#EF4444"
        gap_display_html = f'<span style="color:{color}">{g:+.0f} pts</span>'
    else:
        gap_display = "—"
        gap_display_html = "—"

    # --- Fetch benchmark data for comparison cards and footnotes ---
    bench_data: Dict[str, Optional[float]] = {}
    bench_count = 0
    try:
        bench_data, bench_count = _fetch_benchmark(
            cidade if cidade != "?" else "",
            uf if uf != "?" else "",
            dep if dep != "?" else "",
            ["enem_media_geral"] + AREA_KEYS,
        )
    except Exception as e:
        logger.debug(f"report_generator: benchmark fetch failed: {e}")

    # --- Gerar charts (radar + trend gated by confiavel; trend always attempted) ---
    radar_png = generate_radar_chart(str(inep), benchmark="municipio") if confiavel else None
    trend_png = generate_trend_chart(str(inep), "qt_mat_bas", "Matriculas Totais")

    # --- RADAR SECTION ---
    radar_section = ""
    if radar_png:
        radar_b64 = _img_to_base64(radar_png)
        bench_caption = f"Media das {bench_count} escolas {dep} de {cidade}" if bench_count > 0 else f"Media das escolas {dep} de {cidade}"
        radar_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">🎯</span> Performance por Area</div>
    <div class="chart-container">
      <img src="{radar_b64}" alt="Radar ENEM 5 areas" />
      <div class="chart-caption">Azul: {nome[:30]} &bull; Cinza: {bench_caption}</div>
    </div>
    <div class="footnote">&#185; Fonte: Microdados ENEM 2024 (INEP). Comparacao com {bench_count} escolas {dep} de {cidade}.</div>
  </div>'''

    # --- COMPARISON CARDS SECTION (5 areas, escola vs benchmark) ---
    comparison_section = ""
    if bench_data and any(school.get(k) is not None for k in AREA_KEYS):
        cards_inner = _build_comparison_cards(school, bench_data, bench_count, dep, cidade)
        if cards_inner:
            bench_caption_comp = f"escolas {dep} de {cidade}" if cidade != "?" else "escolas do mesmo perfil"
            comparison_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Comparacao com Escolas do Mesmo Perfil</div>
    <div class="comparison-grid">
      {cards_inner}
    </div>
    <div class="footnote">&#178; Escolas similares = mesma dependencia administrativa ({dep}) + mesmo municipio ({cidade}).</div>
  </div>'''

    # --- TREND SECTION ---
    trend_section = ""
    if trend_png:
        trend_b64 = _img_to_base64(trend_png)
        trend_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📈</span> Evolucao de Matriculas (2020-2025)</div>
    <div class="chart-container">
      <img src="{trend_b64}" alt="Evolucao de matriculas" />
      <div class="chart-caption">Fonte: Censo Escolar INEP 2020-2025</div>
    </div>
    <div class="footnote">&#179; Fonte: Censo Escolar INEP 2020-2025.</div>
  </div>'''

    # --- INSIGHTS SECTION (reframed as opportunities) ---
    insights_section = ""
    try:
        from agent.tools.enem_tools import _handle_analisar_trajetoria_escola
        import json
        traj_raw = _handle_analisar_trajetoria_escola({"inep": str(inep)})
        traj_data = json.loads(traj_raw)
        insights_list = traj_data.get("insights_detectados") or []
        if insights_list:
            cards = []
            for idx, insight in enumerate(insights_list[:5]):
                title, reframed, css_class = _reframe_insight_as_opportunity(insight, index=idx)
                icon = "💡" if css_class == "opportunity" else "✅"
                cards.append(
                    f'<div class="insight-card {css_class}">'
                    f'<div class="card-title">{icon} {title}</div>'
                    f'{reframed}'
                    f'</div>'
                )
            cards_html = "\n    ".join(cards)
            insights_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">💡</span> Oportunidades Identificadas</div>
    {cards_html}
    <div class="footnote">&#8308; Analises baseadas na evolucao dos indicadores do Censo e ENEM.</div>
  </div>'''
        else:
            # No specific insights — show a positive fallback
            insights_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">✅</span> Oportunidades Identificadas</div>
    <div class="insight-card highlight">
      <div class="card-title">✅ Destaque</div>
      A escola esta bem posicionada nos indicadores analisados — com aprendizado adaptativo e exercicios personalizados, e possivel manter essa vantagem e impulsionar ainda mais os resultados.
    </div>
    <div class="footnote">&#8308; Analises baseadas na evolucao dos indicadores do Censo e ENEM.</div>
  </div>'''
    except Exception as e:
        logger.debug(f"report_generator: insights failed: {e}")

    # Meeting link
    meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "https://iaprendo.com.br/contato")

    # Montar HTML final
    html = _REPORT_TEMPLATE.format(
        escola_nome=nome,
        cidade=cidade,
        uf=uf,
        dependencia=dep,
        info_badges_html=info_badges_html,
        ranking_badges_html=ranking_badges_html,
        logo_html=logo_html,
        robot_html=robot_html,
        media_geral=media_display,
        presentes=pres_display,
        gap_display_html=gap_display_html,
        radar_section=radar_section,
        comparison_section=comparison_section,
        trend_section=trend_section,
        insights_section=insights_section,
        meeting_link=meeting_link,
        data_geracao=date.today().strftime("%d/%m/%Y"),
    )

    return {
        "html": html,
        "escola_nome": nome,
        "inep": str(inep),
        "cidade": cidade,
        "uf": uf,
    }


# ============================================================================
# UPLOAD E PUBLICACAO
# ============================================================================

# Reports config — servidos via Supabase Storage com proxy Cloudflare
# O dominio dados.iaprendo.com.br aponta para Supabase Storage via Cloudflare Worker
_REPORT_BASE_URL = os.getenv(
    "REPORT_BASE_URL",
    "https://dados.iaprendo.com.br",
)
# Fallback: URL direta do Supabase Storage (se dominio nao configurado)
_GITHUB_PAGES_BASE = os.getenv(
    "GITHUB_PAGES_URL",
    "https://fernando-duogen.github.io/IAprendo-Sales-Agent",
)
_REPORTS_DIR = ROOT / "docs" / "reports"


def generate_and_upload_report(inep: str) -> Optional[Dict[str, str]]:
    """Gera report HTML e faz upload para Supabase Storage.

    O report e servido como HTML publico via Supabase Storage CDN.
    Tambem salva copia local em docs/reports/ como backup.

    Returns:
        Dict com {"html_url": str, "escola_nome": str, "inep": str}
        ou None se falhar.
    """
    result = generate_report(inep)
    if not result:
        return None

    try:
        # Salvar copia local como backup
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = _REPORTS_DIR / f"{inep}.html"
        filepath.write_text(result["html"], encoding="utf-8")

        # Upload para Supabase Storage (rapido, sem git)
        supabase_ok = False
        try:
            from database.supabase_client import db
            supabase_url = db.upload_report(f"reports/{inep}.html", result["html"])
            if supabase_url:
                supabase_ok = True
        except Exception as upload_err:
            logger.warning(f"Supabase upload failed: {upload_err}")

        # URL final: dominio customizado se Supabase OK, senao fallback GitHub Pages
        if supabase_ok:
            url = f"{_REPORT_BASE_URL}/reports/{inep}.html"
        else:
            url = f"{_GITHUB_PAGES_BASE}/reports/{inep}.html"

        logger.info("report_generated", extra={"inep": inep, "url": url[:80]})

        return {
            "html_url": url,
            "escola_nome": result["escola_nome"],
            "inep": result["inep"],
            "cidade": result.get("cidade"),
            "uf": result.get("uf"),
        }
    except Exception as e:
        logger.error(f"report_generate failed: {e}")
        return None
