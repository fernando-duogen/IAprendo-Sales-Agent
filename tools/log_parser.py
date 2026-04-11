"""
Log parser — le logs/errors.log do IAlex e agrupa erros recentes.

Usado pelo health_check pra dar visibilidade proativa de falhas.
Fail-safe: se o arquivo nao existe ou esta corrompido, retorna um
dict de erro em vez de crashar.

Normalizacao: mensagens similares (mesmo erro em escolas diferentes)
sao agrupadas removendo UUIDs, numeros, e strings entre aspas.
"""
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


LOGS_DIR = Path(__file__).parent.parent / "logs"
ERRORS_LOG = LOGS_DIR / "errors.log"


# Padroes pra normalizar mensagens (agrupar erros similares)
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_NUMBER_RE = re.compile(r"\b\d+\b")
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _normalize_message(msg: str) -> str:
    """Remove UUIDs, numeros e strings quoted pra agrupar erros similares."""
    if not msg:
        return ""
    msg = _UUID_RE.sub("<uuid>", msg)
    msg = _QUOTED_RE.sub("<str>", msg)
    msg = _NUMBER_RE.sub("<n>", msg)
    return msg.strip()[:200]


def _parse_timestamp(ts: str) -> datetime:
    """Parse timestamp ISO ou formato do pythonjsonlogger."""
    if not ts:
        return datetime.now(timezone.utc) - timedelta(days=365)
    try:
        # Formato padrao: "2026-04-11 01:20:52,664"
        if "," in ts:
            ts = ts.replace(",", ".")
        if "T" not in ts:
            ts = ts.replace(" ", "T")
        if "+" not in ts and "Z" not in ts:
            ts += "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc) - timedelta(days=365)


def parse_recent_errors(hours: int = 24, top_n: int = 5) -> Dict[str, Any]:
    """Le errors.log e retorna sumario agrupado de erros recentes.

    Args:
        hours: janela de tempo pra considerar "recente" (default 24h).
        top_n: quantos erros mais frequentes retornar (default 5).

    Returns:
        Dict com {total, in_window, top_errors, modules, oldest, newest, error?}
    """
    if not ERRORS_LOG.exists():
        return {
            "error": f"Log file nao encontrado: {ERRORS_LOG}",
            "total": 0, "in_window": 0, "top_errors": [], "modules": {},
        }

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        content = ERRORS_LOG.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "error": f"Falha ao ler log: {e}",
            "total": 0, "in_window": 0, "top_errors": [], "modules": {},
        }

    lines = content.strip().split("\n")
    total = len(lines)

    counts_by_normalized: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last_seen": None, "sample": ""}
    )
    modules: Dict[str, int] = defaultdict(int)
    in_window = 0
    oldest_dt = None
    newest_dt = None

    # Itera de tras pra frente pra parar cedo quando sair da janela
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue

        ts_str = entry.get("timestamp") or entry.get("asctime") or ""
        dt = _parse_timestamp(ts_str)

        if oldest_dt is None or dt < oldest_dt:
            oldest_dt = dt
        if newest_dt is None or dt > newest_dt:
            newest_dt = dt

        if dt < cutoff:
            # Saiu da janela — como estamos iterando de tras pra frente,
            # podemos parar cedo SE tivermos certeza que o log e ordenado.
            # Como pode ter entradas fora de ordem por multiplas threads,
            # seguimos processando mas sem contar.
            continue

        in_window += 1
        msg = entry.get("message") or ""
        module = entry.get("module") or entry.get("name") or "unknown"
        modules[module] += 1

        normalized = _normalize_message(msg)
        bucket = counts_by_normalized[normalized]
        bucket["count"] += 1
        if bucket["last_seen"] is None or dt > bucket["last_seen"]:
            bucket["last_seen"] = dt
            bucket["sample"] = msg[:200]

    top_errors: List[Dict[str, Any]] = []
    for normalized, data in sorted(
        counts_by_normalized.items(), key=lambda x: x[1]["count"], reverse=True
    )[:top_n]:
        last_seen = data["last_seen"]
        top_errors.append({
            "message": data["sample"] or normalized,
            "normalized": normalized,
            "count": data["count"],
            "last_seen": last_seen.isoformat() if last_seen else None,
        })

    return {
        "total": total,
        "in_window": in_window,
        "top_errors": top_errors,
        "modules": dict(modules),
        "window_hours": hours,
        "oldest": oldest_dt.isoformat() if oldest_dt else None,
        "newest": newest_dt.isoformat() if newest_dt else None,
    }
