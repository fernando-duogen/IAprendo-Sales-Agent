"""Pre-gera OPR + graficos de insight FORA do Cloud (local/Oracle).

Por que: o Streamlit Cloud nao roda kaleido (render de PNG do Plotly). Com
RENDER_CHARTS="false" nos secrets do Cloud, o app apenas CONSOME artefatos
pre-gerados: o OPR em reports/{inep}.html e os graficos em
insight-charts/{inep}/radar.png|gap.png|trend_mat.png (paths deterministicos).
Este script gera/atualiza esses artefatos. Rode no local/Oracle (onde kaleido
funciona), idealmente periodicamente (ou via o scheduler do IAlex).

ROBUSTEZ: o lote roda cada escola num SUBPROCESSO isolado com TIMEOUT duro
(kaleido/rede isolados; uma escola que trava e MORTA e o lote continua) e grava
progresso (`logs/pregen_progress.txt`) p/ RETOMAR de onde parou.

Uso:
    python scripts/pregenerate_artifacts.py                 # todas do CRM (retoma)
    python scripts/pregenerate_artifacts.py --fresh         # idem, ignora progresso
    python scripts/pregenerate_artifacts.py 22144714 ...    # INEPs especificos
    python scripts/pregenerate_artifacts.py --one 22144714  # 1 escola, em processo
"""
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import db  # noqa: E402
from utils.logger import logger  # noqa: E402

# Timeout por escola (subprocesso isolado). Escola normal leva ~45s; 180s mata
# travamento real sem matar escola lenta.
DEFAULT_TIMEOUT_S = 180
_PROGRESS_FILE = ROOT / "logs" / "pregen_progress.txt"


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


def _load_progress() -> set:
    try:
        if _PROGRESS_FILE.exists():
            return {ln.strip() for ln in _PROGRESS_FILE.read_text(
                encoding="utf-8").splitlines() if ln.strip()}
    except Exception:
        pass
    return set()


def _mark_progress(inep: str):
    try:
        _PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PROGRESS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{inep}\n")
    except Exception:
        pass


def run_one_isolated(inep: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> str:
    """Roda 1 escola num SUBPROCESSO isolado com timeout duro.

    Subprocesso => kaleido/rede isolados (sem cascata de travamento) e o timeout
    MATA o processo travado, deixando o lote prosseguir. Retorna 'ok'|'timeout'|'fail'.
    """
    try:
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--one", str(inep)],
            timeout=timeout_s, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return "ok"
        logger.warning(f"pregen {inep} fail: {(r.stderr or '')[-200:]}")
        return "fail"
    except subprocess.TimeoutExpired:
        logger.warning(f"pregen {inep} TIMEOUT ({timeout_s}s) — pulada")
        return "timeout"
    except Exception as e:
        logger.warning(f"pregen {inep} erro no subprocesso: {e}")
        return "fail"


def pregenerate_batch(
    ineps: list,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    resume: bool = True,
    fresh: bool = False,
) -> dict:
    """Pre-gera um lote com isolamento+timeout por escola e retomada.

    resume=True pula escolas ja concluidas (logs/pregen_progress.txt).
    fresh=True zera o progresso antes (refresh completo).
    """
    if fresh:
        try:
            _PROGRESS_FILE.unlink()
        except Exception:
            pass
    done = _load_progress() if resume else set()
    todo = [i for i in ineps if str(i) not in done]
    stats = {"total": len(ineps), "todo": len(todo),
             "skipped": len(ineps) - len(todo),
             "ok": 0, "timeout": 0, "fail": 0}
    for idx, inep in enumerate(todo, 1):
        status = run_one_isolated(inep, timeout_s)
        stats[status] = stats.get(status, 0) + 1
        if status == "ok":
            _mark_progress(inep)
        print(f"[{idx}/{len(todo)}] {inep}: {status}")
    return stats


def main(argv):
    # Folha: --one <inep> roda EM PROCESSO (e o alvo de run_one_isolated).
    if len(argv) >= 3 and argv[1] == "--one":
        r = pregenerate_school_artifacts(argv[2])
        sys.exit(0 if r.get("ok") else 1)

    args = argv[1:]
    fresh = "--fresh" in args
    explicit = [a for a in args if not a.startswith("--")]
    if explicit:
        ineps, resume = explicit, False   # re-rodar explicito sempre regenera
    else:
        ineps, resume = _crm_ineps(), True

    print(f"Pre-gerando artefatos para {len(ineps)} escola(s) "
          f"(timeout {DEFAULT_TIMEOUT_S}s/escola, isolado; resume={resume})...")
    stats = pregenerate_batch(ineps, resume=resume, fresh=fresh)
    print(f"\nConcluido: ok={stats['ok']} timeout={stats['timeout']} "
          f"fail={stats['fail']} skip={stats['skipped']} de {stats['total']}.")


if __name__ == "__main__":
    main(sys.argv)
