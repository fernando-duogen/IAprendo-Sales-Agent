"""Gerador de Report Comparativo — 2 escolas lado a lado.

Gera HTML auto-contido comparando Escola A (alvo) vs Escola B (referencia),
com radar ENEM sobreposto, cards de metricas por area, evolucao de matriculas
e insights focados na escola-alvo.

Modos:
  1. Escola vs Escola: comparar 2 INEPs especificos
  2. Escola vs Grupo: comparar 1 INEP vs media filtrada (cidade/dep/porte)

Usage:
    from tools.comparison_report import generate_comparison_report, generate_and_upload_comparison

    result = generate_and_upload_comparison("43104924", "43105009")
    print(result["html_url"])
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
# TEMPLATE HTML COMPARATIVO
# ============================================================================

_COMP_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Comparativo ENEM 2024 — {nome1} vs {nome2}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; color: #333; background: #f5f7fa; line-height: 1.6; }}
  .container {{ max-width: 720px; margin: 0 auto; background: white; box-shadow: 0 2px 20px rgba(0,0,0,0.08); }}
  .header {{
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: white; padding: 40px 32px 32px;
  }}
  .header h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
  .header .subtitle {{ font-size: 14px; opacity: 0.85; margin-bottom: 16px; }}
  .header .badges {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: rgba(255,255,255,0.2); }}
  .section {{ padding: 28px 32px; border-bottom: 1px solid #f0f0f0; }}
  .section:last-child {{ border-bottom: none; }}
  .section-title {{ font-size: 16px; font-weight: 700; color: #1e3a5f; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
  .icon {{ font-size: 20px; }}
  .schools-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  .school-card {{
    padding: 20px; border-radius: 12px; text-align: center;
  }}
  .school-card.alvo {{ background: #EFF6FF; border: 2px solid #2563EB; }}
  .school-card.ref {{ background: #FFF7ED; border: 2px solid #F97316; }}
  .school-card h3 {{ font-size: 14px; margin-bottom: 8px; }}
  .school-card .media {{ font-size: 32px; font-weight: 800; }}
  .school-card.alvo .media {{ color: #2563EB; }}
  .school-card.ref .media {{ color: #F97316; }}
  .school-card .meta {{ font-size: 12px; color: #666; margin-top: 4px; }}
  .chart-container {{ text-align: center; margin: 8px 0; }}
  .chart-container img {{ max-width: 100%; height: auto; border-radius: 8px; }}
  .chart-caption {{ color: #999; font-size: 11px; margin-top: 4px; }}
  .area-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .area-card {{
    padding: 14px; border-radius: 10px; background: #f8f9fa; text-align: center;
  }}
  .area-card .area-name {{ font-size: 12px; color: #666; margin-bottom: 6px; font-weight: 600; }}
  .area-card .vals {{ display: flex; justify-content: center; gap: 16px; align-items: baseline; }}
  .area-card .v1 {{ font-size: 20px; font-weight: 800; color: #2563EB; }}
  .area-card .v2 {{ font-size: 20px; font-weight: 800; color: #F97316; }}
  .area-card .diff {{ font-size: 11px; margin-top: 4px; }}
  .area-card .diff.pos {{ color: #10B981; }}
  .area-card .diff.neg {{ color: #EF4444; }}
  .insight-card {{ padding: 16px; border-radius: 10px; margin-bottom: 10px; border-left: 4px solid; }}
  .insight-card.opportunity {{ background: #FEF3C7; border-left-color: #F59E0B; }}
  .insight-card.highlight {{ background: #ECFDF5; border-left-color: #10B981; }}
  .card-title {{ font-weight: 700; font-size: 13px; margin-bottom: 6px; }}
  .cta {{ text-align: center; padding: 32px; background: #f8f9fa; }}
  .cta a {{
    display: inline-block; padding: 14px 32px; background: #2563EB; color: white;
    border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 15px;
  }}
  .footer {{ padding: 20px 32px; text-align: center; color: #999; font-size: 11px; background: #fafafa; }}
  .footnote {{ color: #aaa; font-size: 10px; margin-top: 12px; font-style: italic; }}
  @media (max-width: 600px) {{
    .schools-grid, .area-grid {{ grid-template-columns: 1fr; }}
    .header {{ padding: 24px 16px 20px; }}
    .section {{ padding: 20px 16px; }}
  }}
</style>
</head>
<body>
<div class="container">
  <!-- HEADER -->
  <div class="header">
    {logo_html}
    <h1>Comparativo de Performance ENEM 2024</h1>
    <div class="subtitle">{nome1} vs {nome2} &bull; {cidade}/{uf}</div>
  </div>

  <!-- METRICAS LADO A LADO -->
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Visao Geral</div>
    <div class="schools-grid">
      <div class="school-card alvo">
        <h3>{nome1_short}</h3>
        <div class="media">{media1}</div>
        <div class="meta">Media Geral ENEM</div>
        <div class="meta">{presentes1} alunos &bull; {dep1}</div>
      </div>
      <div class="school-card ref">
        <h3>{nome2_short}</h3>
        <div class="media">{media2}</div>
        <div class="meta">Media Geral ENEM</div>
        <div class="meta">{presentes2} alunos &bull; {dep2}</div>
      </div>
    </div>
  </div>

  <!-- RADAR COMPARATIVO -->
  {radar_section}

  <!-- COMPARACAO POR AREA -->
  {areas_section}

  <!-- EVOLUCAO MATRICULAS -->
  {trend_section}

  <!-- INSIGHTS (escola-alvo) -->
  {insights_section}

  <!-- CTA -->
  <div class="cta" style="text-align:left">
    <div style="display:flex;align-items:center;gap:28px;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <p style="font-size:16px;font-weight:700;margin-bottom:8px">Pronto para transformar o aprendizado?</p>
        <p style="font-size:13px;color:#666;margin-bottom:16px">Exercícios adaptativos, alinhados à BNCC, que ajudam cada aluno no seu ritmo.</p>
        <a href="{meeting_link}" style="display:inline-block;padding:12px 28px;background:#2563EB;color:white;border-radius:8px;text-decoration:none;font-weight:700">Conhecer a IAprendo</a>
      </div>
      {qr_html}
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    Fonte: Microdados ENEM 2024 e Censo Escolar 2020-2025 (INEP/MEC)<br>
    Comparativo gerado por IAprendo &bull; {data_geracao}<br>
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
# GERADOR PRINCIPAL
# ============================================================================

def generate_comparison_report(
    inep1: str,
    inep2: str,
) -> Optional[Dict[str, Any]]:
    """Gera HTML comparativo entre 2 escolas.

    Args:
        inep1: INEP da escola-alvo (insights focados nela).
        inep2: INEP da escola de referencia.

    Returns:
        Dict com {"html": str, "nome1": str, "nome2": str} ou None.
    """
    from tools.insight_charts import (
        _fetch_school_data, _fetch_benchmark, _resolve_school_name,
        generate_comparison_radar, generate_comparison_trend,
        AREA_KEYS, AREA_LABELS,
    )

    s1 = _fetch_school_data(str(inep1))
    s2 = _fetch_school_data(str(inep2))
    if not s1 or not s2:
        logger.warning(f"comparison_report: dados insuficientes para {inep1} ou {inep2}")
        return None

    nome1 = _resolve_school_name(str(inep1))
    nome2 = _resolve_school_name(str(inep2))
    cidade = s1.get("peer_mun_nome") or s2.get("peer_mun_nome") or "?"
    uf = s1.get("peer_uf_sigla") or s2.get("peer_uf_sigla") or "?"

    # Medias gerais
    media1 = s1.get("enem_media_geral")
    media2 = s2.get("enem_media_geral")
    from tools.report_generator import _fetch_media_geral
    if not media1:
        mg = _fetch_media_geral(str(inep1))
        media1 = mg if mg else None
    if not media2:
        mg = _fetch_media_geral(str(inep2))
        media2 = mg if mg else None

    # --- RADAR ---
    radar_section = ""
    confiavel1 = s1.get("enem_amostra_confiavel") is True
    confiavel2 = s2.get("enem_amostra_confiavel") is True
    if confiavel1 and confiavel2:
        radar_png = generate_comparison_radar(str(inep1), str(inep2))
        if radar_png:
            radar_b64 = _img_to_base64(radar_png)
            radar_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">🎯</span> Radar ENEM por Area</div>
    <div class="chart-container">
      <img src="{radar_b64}" alt="Radar comparativo ENEM" />
      <div class="chart-caption">Azul: {nome1[:30]} &bull; Laranja: {nome2[:30]} &bull; Cinza: Media municipal</div>
    </div>
    <div class="footnote">Fonte: Microdados ENEM 2024 (INEP).</div>
  </div>'''

    # --- AREAS LADO A LADO ---
    areas_section = ""
    if confiavel1 and confiavel2:
        area_cards = []
        for m in AREA_KEYS:
            v1 = s1.get(m)
            v2 = s2.get(m)
            if v1 is not None and v2 is not None:
                v1f = float(v1)
                v2f = float(v2)
                diff = v1f - v2f
                diff_class = "pos" if diff >= 0 else "neg"
                diff_text = f"{diff:+.0f} pts"
                area_cards.append(
                    f'<div class="area-card">'
                    f'<div class="area-name">{AREA_LABELS[m]}</div>'
                    f'<div class="vals"><span class="v1">{v1f:.0f}</span>'
                    f'<span style="color:#999;font-size:12px">vs</span>'
                    f'<span class="v2">{v2f:.0f}</span></div>'
                    f'<div class="diff {diff_class}">{diff_text}</div>'
                    f'</div>'
                )
        if area_cards:
            cards_html = "\n      ".join(area_cards)
            areas_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Comparação por Área</div>
    <div class="area-grid">
      {cards_html}
    </div>
    <div class="footnote">Azul: {nome1[:25]} | Laranja: {nome2[:25]}. Diferença em pontos.</div>
  </div>'''

    # --- TREND ---
    trend_section = ""
    trend_png = generate_comparison_trend(str(inep1), str(inep2))
    if trend_png:
        trend_b64 = _img_to_base64(trend_png)
        trend_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📈</span> Evolução de Matrículas (2020-2025)</div>
    <div class="chart-container">
      <img src="{trend_b64}" alt="Evolução comparativa de matrículas" />
      <div class="chart-caption">Variação percentual desde o primeiro ano disponível</div>
    </div>
    <div class="footnote">Fonte: Censo Escolar INEP 2020-2025.</div>
  </div>'''

    # --- INSIGHTS (so da escola-alvo) ---
    insights_section = ""
    try:
        from agent.tools.enem_tools import _handle_analisar_trajetoria_escola
        from tools.report_generator import _reframe_insight_as_opportunity
        import json
        traj_raw = _handle_analisar_trajetoria_escola({"inep": str(inep1)})
        traj_data = json.loads(traj_raw)
        insights_list = traj_data.get("insights_detectados") or []
        if insights_list:
            cards = []
            for idx, insight in enumerate(insights_list[:4]):
                title, reframed, css_class = _reframe_insight_as_opportunity(insight, index=idx)
                icon = "\U0001f4a1" if css_class == "opportunity" else "\u2705"
                cards.append(
                    f'<div class="insight-card {css_class}">'
                    f'<div class="card-title">{icon} {title}</div>'
                    f'{reframed}'
                    f'</div>'
                )
            cards_html = "\n    ".join(cards)
            insights_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">\U0001f4a1</span> Oportunidades para {nome1[:30]}</div>
    {cards_html}
    <div class="footnote">Insights baseados nos dados do ENEM e Censo Escolar.</div>
  </div>'''
    except Exception as e:
        logger.debug(f"comparison insights failed: {e}")

    # --- LOGO / ROBOT ---
    logo_html = ""
    robot_html = ""
    brand_dir = ROOT / "data" / "brand"
    logo_path = brand_dir / "logo_iaprendo.png"
    robot_path = brand_dir / "robot_icon.png"
    if logo_path.exists():
        logo_b64 = _img_to_base64(logo_path.read_bytes())
        logo_html = (
            f'<a href="https://iaprendo.com.br" target="_blank" style="text-decoration:none">'
            f'<img src="{logo_b64}" alt="IAprendo" style="height:45px;border-radius:6px;margin-bottom:12px">'
            f'</a>'
        )
    if robot_path.exists():
        robot_b64 = _img_to_base64(robot_path.read_bytes())
        robot_html = (
            f'<a href="https://iaprendo.com.br" target="_blank" style="text-decoration:none">'
            f'<img src="{robot_b64}" alt="IAprendo" style="height:35px;border-radius:50%">'
            f'</a>'
        )

    meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "https://iaprendo.com.br/contato")

    # QR Code
    qr_html = ""
    try:
        from tools.report_generator import _generate_qr_svg
        qr_svg = _generate_qr_svg(meeting_link, size_mm=28)
        if qr_svg:
            qr_html = (
                f'<div style="background:white;padding:8px;border-radius:8px;text-align:center">'
                f'{qr_svg}'
                f'<div style="font-size:10px;color:#1e3a5f;margin-top:4px;font-weight:600">Agende aqui</div>'
                f'</div>'
            )
    except Exception:
        pass

    html = _COMP_TEMPLATE.format(
        nome1=nome1,
        nome2=nome2,
        nome1_short=nome1[:25],
        nome2_short=nome2[:25],
        cidade=cidade,
        uf=uf,
        media1=f"{float(media1):.1f}" if media1 else "—",
        media2=f"{float(media2):.1f}" if media2 else "—",
        presentes1=int(float(s1.get("enem_presentes") or 0)),
        presentes2=int(float(s2.get("enem_presentes") or 0)),
        dep1=s1.get("enem_dependencia") or "?",
        dep2=s2.get("enem_dependencia") or "?",
        radar_section=radar_section,
        areas_section=areas_section,
        trend_section=trend_section,
        insights_section=insights_section,
        meeting_link=meeting_link,
        qr_html=qr_html,
        data_geracao=date.today().strftime("%d/%m/%Y"),
        logo_html=logo_html,
        robot_html=robot_html,
    )

    return {
        "html": html,
        "nome1": nome1,
        "nome2": nome2,
        "inep1": str(inep1),
        "inep2": str(inep2),
        "cidade": cidade,
        "uf": uf,
    }


# ============================================================================
# UPLOAD
# ============================================================================

_REPORTS_DIR = ROOT / "docs" / "reports"
_REPORT_BASE_URL = os.getenv("REPORT_BASE_URL", "https://dados.iaprendo.com.br")


def generate_and_upload_comparison(
    inep1: str,
    inep2: str,
) -> Optional[Dict[str, str]]:
    """Gera report comparativo e faz upload para Supabase Storage.

    Returns:
        Dict com {"html_url": str, "nome1": str, "nome2": str} ou None.
    """
    result = generate_comparison_report(inep1, inep2)
    if not result:
        return None

    try:
        # Backup local
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{inep1}_vs_{inep2}.html"
        filepath = _REPORTS_DIR / filename
        filepath.write_text(result["html"], encoding="utf-8")

        # Upload Supabase
        url = None
        try:
            from database.supabase_client import db
            url = db.upload_report(f"reports/{filename}", result["html"])
        except Exception as e:
            logger.warning(f"comparison upload failed: {e}")

        if url:
            public_url = f"{_REPORT_BASE_URL}/reports/{filename}"
        else:
            public_url = f"file:///{filepath}"

        logger.info("comparison_report_generated", extra={
            "inep1": inep1, "inep2": inep2, "url": public_url[:80],
        })

        return {
            "html_url": public_url,
            "nome1": result["nome1"],
            "nome2": result["nome2"],
            "inep1": inep1,
            "inep2": inep2,
        }
    except Exception as e:
        logger.error(f"comparison_report failed: {e}")
        return None


# CLI
if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) >= 3:
        r = generate_and_upload_comparison(_sys.argv[1], _sys.argv[2])
        if r:
            print(f"URL: {r['html_url']}")
            print(f"{r['nome1']} vs {r['nome2']}")
        else:
            print("FALHOU")
    else:
        print("Usage: python tools/comparison_report.py <inep1> <inep2>")
