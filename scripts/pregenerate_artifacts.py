"""Pre-gera OPR + graficos de insight FORA do Cloud (local/Oracle).

Por que: o Streamlit Cloud nao roda kaleido (render de PNG do Plotly). Com
RENDER_CHARTS="false" nos secrets do Cloud, o app apenas CONSOME artefatos
pre-gerados: o OPR em reports/{inep}.html e os graficos em
insight-charts/{inep}/radar.png|gap.png|trend_mat.png (paths deterministicos).
Este script gera/atualiza esses artefatos. Rode no local/Oracle (onde kaleido
funciona), idealmente periodicamente (ou via workflows/daily_pipeline na Oracle).

Uso:
    python scripts/pregenerate_artifacts.py                 # todas as escolas do CRM com INEP
    python scripts/pregenerate_artifacts.py 22144714 43108164   # INEPs especificos
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import db  # noqa: E402
from utils.logger import logger  # noqa: E402


def pregenerate_school_artifacts(inep: str) -> dict:
    """Gera+upload do OPR e dos 3 graficos (paths deterministicos) p/ 1 escola."""
    inep = str(inep or "").strip()
    if not inep:
        return {"inep": inep, "ok": False, "reason": "sem inep"}
    out = {"inep": inep, "report": False, "charts": []}
    # 1. OPR (HTML auto-contido com charts base64) -> reports/{inep}.html
    try:
        from tools.report_generator import generate_and_upload_report
        if generate_and_upload_report(inep):
            out["report"] = True
    except Exception as e:
        logger.warning(f"pregenerate OPR {inep} falhou: {e}")
    # 2. Graficos PNG -> insight-charts/{inep}/{radar,gap,trend_mat}.png
    try:
        from tools.insight_charts import generate_all_relevant_charts
        for ch in generate_all_relevant_charts(inep):
            if db.upload_chart(ch["filename"], ch["bytes"]):
                out["charts"].append(ch["type"])
    except Exception as e:
        logger.warning(f"pregenerate charts {inep} falhou: {e}")
    out["ok"] = out["report"] or bool(out["charts"])
    return out


def _crm_ineps(limit: int = 5000) -> list:
    rows = (db.client.table("companies").select("inep_code")
            .not_.is_("inep_code", "null").limit(limit).execute().data or [])
    seen, ineps = set(), []
    for r in rows:
        i = str(r.get("inep_code") or "").strip()
        if i and i not in seen:
            seen.add(i)
            ineps.append(i)
    return ineps


def main(argv):
    ineps = argv[1:] or _crm_ineps()
    print(f"Pre-gerando artefatos para {len(ineps)} escola(s)...")
    ok = 0
    for i, inep in enumerate(ineps, 1):
        r = pregenerate_school_artifacts(inep)
        if r["ok"]:
            ok += 1
        print(f"[{i}/{len(ineps)}] {inep}: report={r['report']} charts={r['charts']}")
    print(f"\nConcluido: {ok}/{len(ineps)} com pelo menos 1 artefato.")


if __name__ == "__main__":
    main(sys.argv)
