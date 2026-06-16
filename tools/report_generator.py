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
# HELPERS
# ============================================================================

def _pluralize_dep(dep: str) -> str:
    """Pluraliza nome da dependência: Federal→federais, Privada→privadas, etc."""
    mapping = {
        "Federal": "federais", "Estadual": "estaduais",
        "Municipal": "municipais", "Privada": "privadas",
    }
    return mapping.get(dep, dep.lower() + "s" if dep else "")


# ============================================================================
# QR CODE HELPER (SVG, sem PIL)
# ============================================================================

def _generate_qr_svg(url: str, size_mm: int = 30) -> str:
    """Gera QR Code como SVG inline (sem dependencia de PIL).

    Args:
        url: URL destino do QR code.
        size_mm: Tamanho em mm.

    Returns:
        String SVG inline ou string vazia se falhar.
    """
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
        import io

        qr = qrcode.QRCode(version=1, box_size=10, border=1,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        svg = buf.getvalue().decode("utf-8")
        # Ajustar tamanho
        svg = svg.replace('width="', f'width="{size_mm}mm" _old_w="', 1)
        svg = svg.replace('height="', f'height="{size_mm}mm" _old_h="', 1)
        return svg
    except Exception as e:
        logger.debug(f"QR code generation failed: {e}")
        return ""


# ============================================================================
# TEMPLATE HTML (CSS inline, auto-contido, responsivo)
# ============================================================================

_REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Diagnóstico ENEM 2024 — {escola_nome}</title>
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
  /* Benchmark Switcher */
  .benchmark-switcher {{
    display: flex; gap: 8px; align-items: center; padding: 16px 20px;
    background: #f0f4f8; border-radius: 8px; margin: 20px 32px 8px;
    flex-wrap: wrap;
  }}
  .benchmark-switcher .switcher-label {{
    font-size: 13px; color: #475569; font-weight: 600; margin-right: 4px;
  }}
  .benchmark-switcher .tab {{
    padding: 8px 14px; border: 1px solid #cbd5e1; background: white;
    border-radius: 20px; cursor: pointer; font-size: 13px;
    transition: all .2s; font-weight: 600; color: #334155;
    display: inline-flex; align-items: center; gap: 6px;
    -webkit-tap-highlight-color: transparent;
  }}
  .benchmark-switcher .tab:hover:not(:disabled) {{
    background: #f1f5f9; border-color: #94a3b8;
  }}
  .benchmark-switcher .tab.active {{
    background: #1e3a8a; color: #ffffff; border-color: #1e3a8a;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(30,58,138,0.35);
    text-shadow: 0 1px 2px rgba(0,0,0,0.15);
  }}
  .benchmark-switcher .tab:disabled {{
    opacity: 0.4; cursor: not-allowed;
  }}
  .benchmark-switcher .tab .badge-icon {{
    font-size: 11px;
  }}
  .variant {{ display: block; }}
  .variant.hidden {{ display: none; }}
  @media (max-width: 600px) {{
    .benchmark-switcher {{ margin: 16px; padding: 12px; }}
    .benchmark-switcher .tab {{
      padding: 8px 12px; font-size: 13px; font-weight: 700;
    }}
    .benchmark-switcher .tab.active {{
      background: #1e3a8a; color: #ffffff;
      font-weight: 800;
      text-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }}
  }}
</style>
</head>
<body>
<div class="container">

  <!-- HEADER -->
  <div class="header">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div>
        <div class="subtitle">Diagnóstico de Performance ENEM 2024</div>
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

  <!-- BENCHMARK SWITCHER (topo — define contexto de tudo abaixo) -->
  {switcher_html}

  <!-- VARIANTES (Visão Geral + radar + cards + insights — tudo dependente do benchmark) -->
  {variants_html}

  <!-- EVOLUCAO MATRICULAS (dep-independente, fora do switcher) -->
  {trend_section}

  <!-- CTA -->
  <div class="cta" style="text-align:left">
    <div style="display:flex;align-items:center;gap:28px;flex-wrap:wrap">
      <div style="flex:1;min-width:200px">
        <h2 style="font-size:20px;margin-bottom:8px">Pronto para transformar o aprendizado?</h2>
        <p style="font-size:13px;opacity:0.9;margin-bottom:16px">Exercícios adaptativos, alinhados à BNCC, que ajudam cada aluno no seu ritmo.</p>
        <a href="{meeting_link}" class="cta-button">Conhecer a IAprendo</a>
      </div>
      {qr_html}
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer" style="display:flex;justify-content:space-between;align-items:center">
    <div>
      Fonte: Microdados ENEM 2024 e Censo Escolar 2020-2025 (INEP/MEC)<br>
      Análise gerada por <a href="https://iaprendo.com.br" target="_blank" style="color:#2563eb;text-decoration:none">IAprendo</a> &bull; {data_geracao}
    </div>
    {robot_html}
  </div>

</div>
<script>
  (function() {{
    var tabs = document.querySelectorAll('.benchmark-switcher .tab');
    var variants = document.querySelectorAll('.variant');
    var defaultDep = '{default_dep}';
    var OPR_INEP = '{inep}';
    var TRACK_URL = '{track_url}';

    // Session ID persistente (agrupa eventos do mesmo visitante)
    function genUUID() {{
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
      return 'sid-' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
    }}
    var sid;
    try {{
      sid = localStorage.getItem('opr_sid');
      if (!sid) {{ sid = genUUID(); localStorage.setItem('opr_sid', sid); }}
    }} catch(e) {{ sid = genUUID(); }}

    // Tracking fire-and-forget
    function track(event, benchmark) {{
      if (!TRACK_URL) return;
      try {{
        fetch(TRACK_URL, {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            inep: OPR_INEP,
            event: event,
            benchmark: benchmark || '',
            session_id: sid,
          }}),
          mode: 'cors',
          keepalive: true,
        }}).catch(function() {{}});
      }} catch(e) {{}}
    }}

    function selectTab(dep) {{
      tabs.forEach(function(t) {{ t.classList.toggle('active', t.dataset.dep === dep); }});
      variants.forEach(function(v) {{ v.classList.toggle('hidden', v.getAttribute('data-dep') !== dep); }});
      try {{ history.replaceState(null, '', '#' + dep.toLowerCase()); }} catch(e) {{}}
    }}

    tabs.forEach(function(t) {{
      if (t.dataset.noData === '1') {{ t.disabled = true; return; }}
      t.addEventListener('click', function() {{
        selectTab(t.dataset.dep);
        track('tab_click', t.dataset.dep);
      }});
    }});

    // CTA tracking ("Conhecer a IAprendo" button)
    document.querySelectorAll('.cta-button').forEach(function(b) {{
      b.addEventListener('click', function() {{
        var activeTab = document.querySelector('.benchmark-switcher .tab.active');
        var activeDep = activeTab ? activeTab.dataset.dep : defaultDep;
        track('cta_click', activeDep);
      }});
    }});

    // Init: seleciona tab default ou via hash
    var hash = (location.hash || '').replace('#', '').toLowerCase();
    var match = Array.from(tabs).find(function(t) {{
      return !t.disabled && t.dataset.dep.toLowerCase() === hash;
    }});
    var initialDep = match ? match.dataset.dep : defaultDep;
    selectTab(initialDep);

    // Track page_load inicial (apos init)
    track('page_load', initialDep);
  }})();
</script>
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
        "enem_media_mt": "Matemática",
        "enem_media_cn": "Ciências da Natureza",
        "enem_media_ch": "Ciências Humanas",
        "enem_media_lc": "Linguagens",
        "enem_media_redacao": "Redação",
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
            mg_bench_display = f"Referência: {mg_bv:.0f}"
        else:
            mg_css = ""
            mg_diff_class = ""
            mg_diff_display = ""
            mg_bench_display = ""
        cards_html.append(
            f'<div class="comp-card {mg_css}">'
            f'<div class="area-name">Média Geral</div>'
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
            bench_display = f"Referência: {bv:.0f}"
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
        "abaixo", "gap", "apenas", "nenhum", "fraca", "fraco", "queda",
        "menor", "deficit", "defasagem",
    ]

    is_negative = any(signal in insight_text.lower() for signal in negative_signals)

    # 5 templates rotativos para oportunidades (negative insights)
    # REGRA: cada template usa uma abordagem DIFERENTE — sem repetir "aprendizado adaptativo"
    opportunity_templates = [
        "{obs} — com exercícios personalizados por aluno, é possível reverter essa tendência e posicionar a escola como referência em qualidade pedagógica.",
        "{obs} — um plano de reforço alinhado à BNCC, ajustado ao ritmo de cada aluno, pode transformar esse cenário e fortalecer a confiança das famílias.",
        "{obs} — acompanhamento individualizado permite identificar e corrigir lacunas antes que se acumulem, mudando a trajetória dos resultados.",
        "{obs} — investir em diagnóstico e reforço direcionado por aluno é a forma mais eficaz de reverter esse quadro e recuperar competitividade.",
        "{obs} — famílias valorizam escolas que atuam proativamente sobre pontos fracos. Mostrar que a escola age sobre esses dados é um diferencial real.",
    ]

    # 5 templates rotativos para destaques (positive insights)
    # REGRA: cada template usa uma abordagem DIFERENTE — sem correlacoes forcadas
    highlight_templates = [
        "{obs} — manter esse patamar exige acompanhamento contínuo. Escolas que investem em dados conseguem sustentar vantagens por mais tempo.",
        "{obs} — esse é um diferencial que as famílias percebem. Comunicar esse resultado de forma clara pode atrair novas matrículas.",
        "{obs} — resultados assim posicionam a escola entre as melhores da região e abrem espaço para estratégias de crescimento.",
        "{obs} — consolidar essa vantagem com ferramentas de acompanhamento individual garante que o progresso seja consistente.",
        "{obs} — escolas com bons indicadores têm mais facilidade para atrair e reter famílias que valorizam qualidade acadêmica.",
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
    for keyword in ["IAprendo", "aprendizado adaptativo", "exercícios adaptativos",
                     "reforço personalizado", "tecnologia educacional"]:
        reframed = reframed.replace(keyword, f"<b>{keyword}</b>", 1)  # so 1x por keyword

    title = "Oportunidade" if is_negative else "Destaque"
    css_class = "opportunity" if is_negative else "highlight"
    return (title, reframed, css_class)


# ============================================================================
# GERADOR PRINCIPAL
# ============================================================================

def generate_report(inep: str, benchmark_dep: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Gera o HTML do One Page Report para uma escola.

    Args:
        inep: Codigo INEP da escola.
        benchmark_dep: Dependencia administrativa forçada para o benchmark
            (ex: "Privada"). Se None, usa a mesma dependencia da escola.

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
        info_badges.append(f'<span class="badge warn">Área fraca: {area_fraca}</span>')
    info_badges_html = "\n      ".join(info_badges)

    # Rankings (linha 2)
    ranking_badges = []
    rank_mun = school.get("enem_rank_mun")
    rank_uf = school.get("enem_rank_uf")
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

    # --- Gerar TREND (dep-independente, so 1x) ---
    trend_png = generate_trend_chart(str(inep), "qt_mat_bas", "Matrículas Totais")

    # --- SWITCHER: Construir 4 variantes (Estadual, Municipal, Federal, Privada) em paralelo ---
    # Dependencia default: respeita benchmark_dep se fornecido, senao usa dep da escola
    default_dep = benchmark_dep if benchmark_dep else (dep if dep != "?" else "Privada")

    # Buscar trends e censo_series uma vez (dep-independente) para reusar no _detectar_insights
    trends_data: Dict = {}
    censo_series: List[Dict] = []
    try:
        from agent.tools.enem_tools import get_insight_ingredients
        _ingredients = get_insight_ingredients(str(inep))
        trends_data = _ingredients.get("trends") or {}
        censo_series = _ingredients.get("censo_series") or []
    except Exception as e:
        logger.debug(f"report_generator: insight ingredients fetch failed: {e}")

    def _build_variant(dep_name: str) -> Dict[str, Any]:
        """Constroi uma variante completa (visao_geral + radar + cards + insights + badge) para uma dependencia."""
        try:
            # 1. Benchmark data
            v_bench_data, v_bench_count = _fetch_benchmark(
                cidade if cidade != "?" else "",
                uf if uf != "?" else "",
                dep_name,
                ["enem_media_geral"] + AREA_KEYS,
            )
        except Exception:
            v_bench_data, v_bench_count = {}, 0

        v_dep_plural = _pluralize_dep(dep_name)
        has_data = v_bench_count >= 3

        # Computar gap vs este benchmark (dinamico, diferente do enem_gap_vs_peer_2024)
        # Usa media_geral_raw (fetch direto da base ENEM) porque school_analytics
        # pode ter enem_media_geral=None para algumas escolas
        v_gap_display_html = "—"
        v_gap_num: Optional[float] = None
        if has_data and v_bench_data.get("enem_media_geral") and media_geral_raw is not None:
            v_gap_num = float(media_geral_raw) - float(v_bench_data["enem_media_geral"])
            color = "#10B981" if v_gap_num >= 0 else "#EF4444"
            v_gap_display_html = f'<span style="color:{color}">{v_gap_num:+.0f} pts</span>'

        # 2. Visao Geral (dentro da variante — gap atualiza com benchmark)
        v_visao_geral_html = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Visão Geral</div>
    <div class="metrics-grid">
      <div class="metric-box">
        <div class="value">{media_display}</div>
        <div class="label">Média Geral ENEM</div>
      </div>
      <div class="metric-box">
        <div class="value">{pres_display}</div>
        <div class="label">Alunos Presentes</div>
      </div>
      <div class="metric-box">
        <div class="value">{v_gap_display_html}</div>
        <div class="label">Diferença vs Escolas {v_dep_plural.title()}</div>
      </div>
    </div>
  </div>'''

        # 3. Radar PNG (so se escola tem amostra confiavel E tem dados de benchmark)
        v_radar_html = ""
        if confiavel and has_data:
            try:
                # scale=1 porque temos 4 PNGs no mesmo HTML — prioriza leveza sobre retina
                v_radar_png = generate_radar_chart(str(inep), benchmark="municipio", benchmark_dep=dep_name, scale=1)
                if v_radar_png:
                    v_radar_b64 = _img_to_base64(v_radar_png)
                    v_caption = f"Média de {v_bench_count} escolas {v_dep_plural} de {cidade}"
                    v_radar_html = f'''
  <div class="section">
    <div class="section-title"><span class="icon">🎯</span> Performance por Área</div>
    <div class="chart-container">
      <img src="{v_radar_b64}" alt="Radar ENEM 5 áreas" />
      <div class="chart-caption">Azul: {nome[:30]} &bull; Cinza: {v_caption}</div>
    </div>
    <div class="footnote">&#185; Fonte: Microdados ENEM 2024 (INEP). Comparação com {v_bench_count} escolas {v_dep_plural} de {cidade}.</div>
  </div>'''
            except Exception as exc:
                logger.debug(f"variant {dep_name} radar fail: {exc}")

        # 3. Comparison cards
        v_cards_html = ""
        if v_bench_data and has_data and any(school.get(k) is not None for k in AREA_KEYS):
            try:
                cards_inner = _build_comparison_cards(school, v_bench_data, v_bench_count, dep_name, cidade)
                if cards_inner:
                    v_cards_html = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📊</span> Comparação com Escolas {v_dep_plural.title()} de {cidade}</div>
    <div class="comparison-grid">
      {cards_inner}
    </div>
    <div class="footnote">&#178; Referência: {v_bench_count} escolas {v_dep_plural} de {cidade}.</div>
  </div>'''
            except Exception as exc:
                logger.debug(f"variant {dep_name} cards fail: {exc}")

        # 4. Insights regenerados com esse benchmark
        v_insights_html = ""
        try:
            from agent.tools.enem_tools import _detectar_insights
            v_bench_for_insights = {
                "media_geral": v_bench_data.get("enem_media_geral") if v_bench_data else None,
                "media_cn": v_bench_data.get("enem_media_cn") if v_bench_data else None,
                "media_ch": v_bench_data.get("enem_media_ch") if v_bench_data else None,
                "media_lc": v_bench_data.get("enem_media_lc") if v_bench_data else None,
                "media_mt": v_bench_data.get("enem_media_mt") if v_bench_data else None,
                "media_redacao": v_bench_data.get("enem_media_redacao") if v_bench_data else None,
            } if v_bench_data else None
            v_insights_list = _detectar_insights(
                trends_data, censo_series,
                enem_data=school, benchmark_data=v_bench_for_insights
            )
            if v_insights_list:
                cards = []
                for idx, insight in enumerate(v_insights_list[:5]):
                    title, reframed, css_class = _reframe_insight_as_opportunity(insight, index=idx)
                    icon = "💡" if css_class == "opportunity" else "✅"
                    cards.append(
                        f'<div class="insight-card {css_class}">'
                        f'<div class="card-title">{icon} {title}</div>'
                        f'{reframed}'
                        f'</div>'
                    )
                cards_html = "\n    ".join(cards)
                v_insights_html = f'''
  <div class="section">
    <div class="section-title"><span class="icon">💡</span> Oportunidades vs Escolas {v_dep_plural.title()}</div>
    {cards_html}
    <div class="footnote">&#8308; Análises baseadas na evolução dos indicadores do Censo e ENEM.</div>
  </div>'''
            else:
                v_insights_html = f'''
  <div class="section">
    <div class="section-title"><span class="icon">✅</span> Destaque vs Escolas {v_dep_plural.title()}</div>
    <div class="insight-card highlight">
      <div class="card-title">✅ Destaque</div>
      A escola está bem posicionada em relação às escolas {v_dep_plural} de {cidade} — com aprendizado adaptativo e exercícios personalizados, é possível manter essa vantagem e impulsionar ainda mais os resultados.
    </div>
    <div class="footnote">&#8308; Análises baseadas na evolução dos indicadores do Censo e ENEM.</div>
  </div>'''
        except Exception as exc:
            logger.debug(f"variant {dep_name} insights fail: {exc}")

        # 5. Badge de oportunidade (baseado no gap geral)
        badge_icon = ""
        badge_label = ""
        if has_data and v_bench_data.get("enem_media_geral") and media_geral_raw is not None:
            gap = float(media_geral_raw) - float(v_bench_data["enem_media_geral"])
            if gap >= 0:
                badge_icon = "🟢"  # Destaque
                badge_label = "destaque"
            elif gap >= -20:
                badge_icon = "🟡"  # Gap pequeno
                badge_label = "proximo"
            elif gap >= -50:
                badge_icon = "🟠"  # Oportunidade moderada
                badge_label = "oportunidade"
            else:
                badge_icon = "🔴"  # Grande oportunidade
                badge_label = "grande oportunidade"

        return {
            "dep": dep_name,
            "dep_plural": v_dep_plural,
            "has_data": has_data,
            "bench_count": v_bench_count,
            "gap_num": v_gap_num,
            "bench_media_geral": v_bench_data.get("enem_media_geral") if v_bench_data else None,
            "visao_geral_html": v_visao_geral_html,
            "radar_html": v_radar_html,
            "cards_html": v_cards_html,
            "insights_html": v_insights_html,
            "badge_icon": badge_icon,
            "badge_label": badge_label,
        }

    # Gerar 4 variantes em paralelo (economiza ~30s vs sequencial)
    from concurrent.futures import ThreadPoolExecutor
    dependencias = ["Estadual", "Municipal", "Federal", "Privada"]
    variants: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _futures = {d: _ex.submit(_build_variant, d) for d in dependencias}
        for d, f in _futures.items():
            try:
                variants[d] = f.result(timeout=60)
            except Exception as exc:
                logger.warning(f"variant {d} timeout/fail: {exc}")
                variants[d] = {
                    "dep": d, "dep_plural": _pluralize_dep(d),
                    "has_data": False, "bench_count": 0,
                    "radar_html": "", "cards_html": "", "insights_html": "",
                    "badge_icon": "", "badge_label": "",
                }

    # Construir HTML do switcher
    _labels = {
        "Estadual": "Estaduais", "Municipal": "Municipais",
        "Federal": "Federais", "Privada": "Privadas",
    }
    # Se default_dep nao tem dados, fallback pra primeira dep com dados
    if not variants.get(default_dep, {}).get("has_data", False):
        for _d in dependencias:
            if variants.get(_d, {}).get("has_data", False):
                default_dep = _d
                break

    tabs_html_list = []
    for d in dependencias:
        v = variants.get(d, {})
        label = _labels[d]
        disabled_attr = ' data-no-data="1" title="Sem escolas suficientes nessa categoria"' if not v.get("has_data") else ""
        badge = f'<span class="badge-icon">{v.get("badge_icon", "")}</span>' if v.get("badge_icon") else ""
        tabs_html_list.append(
            f'<button class="tab" data-dep="{d}"{disabled_attr}>{label} {badge}</button>'
        )
    switcher_html = f'''
<div class="benchmark-switcher" role="tablist">
  <span class="switcher-label">📊 Comparar com escolas:</span>
  {"".join(tabs_html_list)}
</div>'''

    # Construir variantes embutidas (Visão Geral + radar + cards + insights)
    variants_html_list = []
    for d in dependencias:
        v = variants.get(d, {})
        content = (
            v.get("visao_geral_html", "")
            + v.get("radar_html", "")
            + v.get("cards_html", "")
            + v.get("insights_html", "")
        )
        if not v.get("has_data"):
            # Sem dados: mostrar so Visao Geral (com gap em "—") + aviso
            content = v.get("visao_geral_html", "") + f'''
  <div class="section">
    <div class="insight-card">
      <div class="card-title">ℹ️ Poucos dados para esta comparação</div>
      Apenas {v.get("bench_count", 0)} escolas {_labels[d].lower()} de {cidade} têm dados ENEM confiáveis —
      insuficiente para gerar um benchmark estatístico. Tente outra comparação usando as abas acima.
    </div>
  </div>'''
        variants_html_list.append(f'<div class="variant" data-dep="{d}">{content}</div>')
    variants_html = "\n".join(variants_html_list)

    # --- TREND SECTION (dep-independente, fora do switcher) ---
    trend_section = ""
    if trend_png:
        trend_b64 = _img_to_base64(trend_png)
        trend_section = f'''
  <div class="section">
    <div class="section-title"><span class="icon">📈</span> Evolução de Matrículas (2020-2025)</div>
    <div class="chart-container">
      <img src="{trend_b64}" alt="Evolução de matrículas" />
      <div class="chart-caption">Fonte: Censo Escolar INEP 2020-2025</div>
    </div>
    <div class="footnote">&#179; Fonte: Censo Escolar INEP 2020-2025.</div>
  </div>'''

    # Meeting link + QR Code
    meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "https://iaprendo.com.br/contato")
    qr_svg = _generate_qr_svg(meeting_link, size_mm=28)
    qr_html = ""
    if qr_svg:
        qr_html = (
            f'<div style="background:white;padding:8px;border-radius:8px;text-align:center">'
            f'{qr_svg}'
            f'<div style="font-size:10px;color:#1e3a5f;margin-top:4px;font-weight:600">Agende aqui</div>'
            f'</div>'
        )

    # Tracking URL (env var pra dev/prod)
    track_url = os.getenv("OPR_TRACK_URL", "")

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
        switcher_html=switcher_html,
        variants_html=variants_html,
        default_dep=default_dep,
        trend_section=trend_section,
        meeting_link=meeting_link,
        qr_html=qr_html,
        data_geracao=date.today().strftime("%d/%m/%Y"),
        inep=str(inep),
        track_url=track_url,
    )

    # Computar highlights de comparacao (para LLM usar no pitch balanceado)
    # - Maior oportunidade: benchmark onde o gap e mais negativo (escola atras)
    # - Ponto forte: benchmark onde o gap e mais positivo (escola acima)
    _labels_pt = {"Estadual": "estaduais", "Municipal": "municipais", "Federal": "federais", "Privada": "privadas"}
    _gaps = [(d, v.get("gap_num"), v.get("bench_count", 0)) for d, v in variants.items() if v.get("has_data") and v.get("gap_num") is not None]
    highlights: Dict[str, Any] = {}
    if _gaps:
        # Maior oportunidade = gap mais negativo (ou menos positivo)
        _gaps_sorted = sorted(_gaps, key=lambda x: x[1])
        pior = _gaps_sorted[0]
        melhor = _gaps_sorted[-1]
        highlights = {
            "maior_oportunidade": {
                "benchmark": pior[0],
                "benchmark_pt": _labels_pt.get(pior[0], pior[0].lower()),
                "gap": round(pior[1], 1),
                "bench_count": pior[2],
                "interpretacao": (
                    f"A escola esta {abs(round(pior[1]))} pontos ABAIXO da media das "
                    f"{pior[2]} escolas {_labels_pt.get(pior[0], '').lower()} de {cidade}"
                    if pior[1] < 0 else
                    f"A escola esta {round(pior[1])} pontos ACIMA da media das "
                    f"{pior[2]} escolas {_labels_pt.get(pior[0], '').lower()} de {cidade}"
                ),
            },
            "ponto_forte": {
                "benchmark": melhor[0],
                "benchmark_pt": _labels_pt.get(melhor[0], melhor[0].lower()),
                "gap": round(melhor[1], 1),
                "bench_count": melhor[2],
                "interpretacao": (
                    f"A escola esta {round(melhor[1])} pontos ACIMA da media das "
                    f"{melhor[2]} escolas {_labels_pt.get(melhor[0], '').lower()} de {cidade}"
                    if melhor[1] >= 0 else
                    f"A escola esta {abs(round(melhor[1]))} pontos abaixo da media das "
                    f"{melhor[2]} escolas {_labels_pt.get(melhor[0], '').lower()} de {cidade} "
                    f"(essa e a comparacao mais favoravel)"
                ),
            },
            "todos_gaps": [
                {"benchmark": d, "benchmark_pt": _labels_pt.get(d, d.lower()),
                 "gap": round(g, 1), "bench_count": c}
                for d, g, c in _gaps_sorted
            ],
        }

    return {
        "html": html,
        "escola_nome": nome,
        "inep": str(inep),
        "cidade": cidade,
        "uf": uf,
        "media_geral": media_geral_raw,
        "highlights": highlights,
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


def opr_version_suffix(inep, storage_items=None) -> str:
    """Sufixo '?v=<stamp>' p/ cache-busting do link do OPR (CDN/Cloudflare).

    Usa o `updated_at` do arquivo no Storage como versao -> cada regeneracao
    muda a URL e o usuario sempre pega a versao fresca. Retorna "" se nao achar.

    Args:
        inep: codigo INEP.
        storage_items: lista ja obtida de storage.list("reports") — passe-a p/
            evitar uma query extra quando o call-site ja listou.
    """
    try:
        if storage_items is None:
            from database.supabase_client import db as _db_v
            storage_items = _db_v.client.storage.from_("insight-charts").list(
                "reports", {"limit": 2000}) or []
        fname = f"{str(inep).strip()}.html"
        for it in storage_items:
            if it.get("name") == fname:
                ts = it.get("updated_at") or it.get("created_at") or ""
                import re as _re
                digits = _re.sub(r"\D", "", ts)[:14]
                return f"?v={digits}" if digits else ""
    except Exception:
        pass
    return ""


def generate_and_upload_report(inep: str, benchmark_dep: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Gera report HTML e faz upload para Supabase Storage.

    O report e servido como HTML publico via Supabase Storage CDN.
    Tambem salva copia local em docs/reports/ como backup.

    Args:
        inep: Codigo INEP da escola.
        benchmark_dep: Dependencia administrativa forçada para o benchmark
            (ex: "Privada"). Se None, usa a mesma dependencia da escola.

    Returns:
        Dict com {"html_url": str, "escola_nome": str, "inep": str}
        ou None se falhar.
    """
    # GATE: no Cloud (kaleido nao roda) NAO regenerar — senao sobrescreve o OPR
    # bom (pre-gerado fora do Cloud) por uma versao chartless. Retorna a URL do
    # OPR existente se houver no Storage. Geracao real roda local/Oracle.
    try:
        from tools.insight_charts import charts_renderable
        if not charts_renderable():
            _inep_s = str(inep or "").strip()
            try:
                from database.supabase_client import db as _db_gate
                _base = os.getenv("REPORT_BASE_URL", "https://dados.iaprendo.com.br").rstrip("/")
                _ls = _db_gate.client.storage.from_("insight-charts").list(
                    "reports", {"limit": 2000}) or []
                if _inep_s and f"{_inep_s}.html" in {it.get("name") for it in _ls}:
                    logger.info("OPR ja existe (Cloud nao regenera)", extra={"inep": _inep_s})
                    _v = opr_version_suffix(_inep_s, _ls)
                    return {"html_url": f"{_base}/reports/{_inep_s}.html{_v}", "inep": _inep_s}
            except Exception as _e:
                logger.debug(f"OPR lookup (Cloud) falhou: {_e}")
            logger.warning("OPR nao gerado: ambiente sem kaleido e sem pre-gerado",
                           extra={"inep": _inep_s})
            return None
    except Exception:
        pass

    result = generate_report(inep, benchmark_dep=benchmark_dep)
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
        # (+ cache-busting via ?v=<updated_at> p/ o CDN nao servir versao velha)
        if supabase_ok:
            url = f"{_REPORT_BASE_URL}/reports/{inep}.html{opr_version_suffix(inep)}"
        else:
            url = f"{_GITHUB_PAGES_BASE}/reports/{inep}.html"

        logger.info("report_generated", extra={"inep": inep, "url": url[:80]})

        return {
            "html_url": url,
            "escola_nome": result["escola_nome"],
            "inep": result["inep"],
            "cidade": result.get("cidade"),
            "uf": result.get("uf"),
            "media_geral": result.get("media_geral"),
            "highlights": result.get("highlights", {}),
        }
    except Exception as e:
        logger.error(f"report_generate failed: {e}")
        return None
