"""Gerador de One Page Report — pagina HTML personalizada por escola.

Gera um HTML estatico auto-contido (charts embutidos como base64 PNG,
CSS inline, zero dependencias externas) que e hospedado no Supabase
Storage como URL publica permanente.

O report mostra:
- Header com nome da escola + cidade + badges
- Radar ENEM 5 areas vs benchmark
- Gap indicator na area mais fraca
- Evolucao de matriculas vs media local
- Insights automaticos (ratio aluno/prof, tech, etc.)
- CTA para agendar conversa

Usage:
    from tools.report_generator import generate_report, generate_and_upload_report

    # Gerar HTML + upload → URL publica
    result = generate_and_upload_report("43216684")
    print(result["html_url"])  # https://...supabase.co/storage/.../report_2024.html
    print(result["pdf_url"])   # None (ou URL se weasyprint instalado)
"""
import base64
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    .header h1 {{ font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <div class="subtitle">Diagnostico de Performance ENEM 2024</div>
    <h1>{escola_nome}</h1>
    <div class="subtitle">{cidade}/{uf} &bull; {dependencia}</div>
    <div class="badges">
      {badges_html}
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
        <div class="value">{gap_display}</div>
        <div class="label">Gap vs Peer</div>
      </div>
    </div>
  </div>

  <!-- RADAR ENEM -->
  {radar_section}

  <!-- GAP INDICATOR -->
  {gap_section}

  <!-- EVOLUCAO MATRICULAS -->
  {trend_section}

  <!-- INSIGHTS -->
  {insights_section}

  <!-- CTA -->
  <div class="cta">
    <h2>Quer discutir esses resultados?</h2>
    <p>Nosso time pode ajudar a transformar esses dados em acoes concretas para melhorar o desempenho dos seus alunos.</p>
    <a href="{meeting_link}" class="cta-button">Agendar Conversa Gratuita</a>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    Fonte: Microdados ENEM 2024 e Censo Escolar 2020-2025 (INEP/MEC)<br>
    Analise gerada por IAprendo &bull; {data_geracao}
  </div>

</div>
</body>
</html>"""


def _img_to_base64(png_bytes: bytes) -> str:
    """Converte PNG bytes para data URI base64."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


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
        generate_gap_indicator,
        generate_trend_chart,
        _fetch_school_data,
        _resolve_school_name,
    )

    # Buscar dados
    school = _fetch_school_data(str(inep))
    if not school:
        logger.warning(f"report_generator: escola {inep} nao encontrada em school_analytics")
        return None

    nome = _resolve_school_name(str(inep))
    cidade = school.get("peer_mun_nome") or "?"
    uf = school.get("peer_uf_sigla") or "?"
    dep = school.get("enem_dependencia") or "?"
    media_geral = school.get("enem_media_geral")
    presentes = school.get("enem_presentes")
    gap = school.get("enem_gap_vs_peer_2024")
    area_fraca = school.get("enem_area_mais_fraca")
    potencial = school.get("enem_potencial_melhoria")
    confiavel = school.get("enem_amostra_confiavel") is True

    # Badges
    badges = []
    if potencial:
        cls = "good" if potencial == "Alto" else ("warn" if potencial == "Baixo" else "")
        badges.append(f'<span class="badge {cls}">Potencial: {potencial}</span>')
    if area_fraca:
        badges.append(f'<span class="badge warn">Area fraca: {area_fraca}</span>')
    if presentes and int(presentes) >= 30:
        badges.append(f'<span class="badge">Amostra confiavel</span>')
    badges_html = "\n      ".join(badges)

    # Metricas rapidas
    media_display = f"{float(media_geral):.1f}" if media_geral else "—"
    pres_display = str(int(presentes)) if presentes else "—"
    if gap is not None:
        g = float(gap)
        gap_display = f"{g:+.0f} pts"
    else:
        gap_display = "—"

    # Gerar charts
    radar_png = generate_radar_chart(str(inep), benchmark="municipio") if confiavel else None
    gap_png = generate_gap_indicator(str(inep)) if confiavel else None
    trend_png = generate_trend_chart(str(inep), "qt_mat_bas", "Matriculas Totais")

    # Montar secoes de charts
    radar_section = ""
    if radar_png:
        radar_b64 = _img_to_base64(radar_png)
        radar_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">🎯</span> Performance por Area</div>
    <div class="chart-container">
      <img src="{radar_b64}" alt="Radar ENEM 5 areas" />
      <div class="chart-caption">Azul: {nome[:30]} &bull; Cinza: Media das {dep} de {cidade}</div>
    </div>
  </div>'''

    gap_section = ""
    if gap_png:
        gap_b64 = _img_to_base64(gap_png)
        gap_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📉</span> Gap vs Escolas Similares</div>
    <div class="chart-container">
      <img src="{gap_b64}" alt="Gap indicator" />
    </div>
  </div>'''

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
  </div>'''

    # Insights
    insights_section = ""
    try:
        from agent.tools.enem_tools import _handle_analisar_trajetoria_escola
        import json
        traj_raw = _handle_analisar_trajetoria_escola({"inep": str(inep)})
        traj_data = json.loads(traj_raw)
        insights_list = traj_data.get("insights_detectados") or []
        if insights_list:
            cards = "\n    ".join(
                f'<div class="insight-card">{insight}</div>'
                for insight in insights_list[:5]
            )
            insights_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">💡</span> Insights Detectados</div>
    {cards}
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
        badges_html=badges_html,
        media_geral=media_display,
        presentes=pres_display,
        gap_display=gap_display,
        radar_section=radar_section,
        gap_section=gap_section,
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

def generate_and_upload_report(inep: str) -> Optional[Dict[str, str]]:
    """Gera report HTML + upload para Supabase Storage.

    Returns:
        Dict com {"html_url": str, "escola_nome": str, "inep": str}
        ou None se falhar.
    """
    result = generate_report(inep)
    if not result:
        return None

    from database.supabase_client import db
    today = date.today().strftime("%Y%m%d")
    path = f"reports/{inep}/diagnostico_{today}.html"

    html_bytes = result["html"].encode("utf-8")
    try:
        # Reusar upload_chart mas com content-type text/html
        bucket_name = "insight-charts"
        bucket = db.client.storage.from_(bucket_name)
        try:
            bucket.upload(
                path, html_bytes,
                file_options={"content-type": "text/html; charset=utf-8", "upsert": "true"},
            )
        except Exception:
            try:
                bucket.remove([path])
            except Exception:
                pass
            bucket.upload(
                path, html_bytes,
                file_options={"content-type": "text/html; charset=utf-8"},
            )
        url = bucket.get_public_url(path)
        logger.info("report_uploaded", extra={"inep": inep, "url": url[:80]})

        return {
            "html_url": url,
            "escola_nome": result["escola_nome"],
            "inep": result["inep"],
            "cidade": result.get("cidade"),
            "uf": result.get("uf"),
        }
    except Exception as e:
        logger.error(f"report_upload failed: {e}")
        return None
