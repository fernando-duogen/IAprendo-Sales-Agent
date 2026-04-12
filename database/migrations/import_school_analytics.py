"""
Import ENEM analytics from escolas_brasil_enriquecido.csv into school_analytics.

- Keyed by inep_code (UPSERT on conflict)
- Populates company_id when the INEP matches a school already in companies
- Handles inf, NaN, outliers and dtype coercion
- Batched for speed (500 rows per batch by default)
- Idempotent: rerun updates updated_at + re-links company_id

Usage:
    python database/migrations/import_school_analytics.py --sample 1000 --dry-run
    python database/migrations/import_school_analytics.py --sample 1000
    python database/migrations/import_school_analytics.py
    python database/migrations/import_school_analytics.py --csv path/to/custom.csv
    python database/migrations/import_school_analytics.py --only-in-companies

Pre-req: migration 015 aplicada no Supabase (APLICAR-015-SCHOOL-ANALYTICS.sql).
"""
import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from database.supabase_client import db
from utils.logger import logger


DEFAULT_CSV = ROOT / "data" / "raw" / "escolas_brasil_enriquecido.csv"
DEFAULT_REPORT_JSON = ROOT / "scripts" / "enem_schema_report.json"
BATCH_SIZE = 500

# Unicode replacement char que chega do CSV fonte ja corrompido.
# Stripado em texto na importacao (prevent regression da migration 018).
_FFFD = "\ufffd"


def _load_report(path: Path) -> Dict[str, Any]:
    """Load the JSON report from inspect_enem_csv.py."""
    if not path.exists():
        raise FileNotFoundError(
            f"Relatorio nao encontrado em {path}. "
            f"Rode scripts/inspect_enem_csv.py primeiro."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_column_spec(report: Dict[str, Any]) -> Dict[str, str]:
    """Return {column_name: sql_type} for all analytical columns."""
    return {c["name"]: c["sql_type"] for c in report["analytical_columns"]}


def _clean_value(val: Any, sql_type: str) -> Optional[Any]:
    """Convert a pandas value to the right Python type for Supabase.

    Handles: NaN, None, inf, numpy scalars, boolean-like strings, int overflow.
    Returns None for NaN/inf/empty.
    """
    # Null handling
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, (np.floating,)):
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        val = f
    if isinstance(val, (np.integer,)):
        val = int(val)
    if isinstance(val, (np.bool_,)):
        val = bool(val)

    # String handling
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ("nan", "none", "null"):
            return None

        # Mojibake guard: U+FFFD ja chega do CSV fonte em campos com acentos
        # (ex: "S\uFFFDo Paulo"). Stripamos aqui no nivel de texto pra manter
        # o DB sempre limpo mesmo em re-imports futuros. Runtime (enem_tools
        # _resolve_school_names) prefere companies/censo_yearly como fonte
        # primaria de nomes, entao esse strip lossy e apenas safety net.
        if _FFFD in s:
            s = " ".join(s.replace(_FFFD, "").split())
            if not s:
                return None

        if sql_type == "BOOLEAN":
            lc = s.lower()
            if lc in ("true", "sim", "1", "verdadeiro", "t", "yes"):
                return True
            if lc in ("false", "nao", "não", "0", "falso", "f", "no"):
                return False
            return None
        if sql_type in ("SMALLINT", "INTEGER", "BIGINT"):
            try:
                f = float(s)
                if math.isnan(f) or math.isinf(f):
                    return None
                return int(f)
            except (ValueError, TypeError):
                return None
        if sql_type.startswith("NUMERIC"):
            try:
                f = float(s)
                if math.isnan(f) or math.isinf(f):
                    return None
                return round(f, 4)
            except (ValueError, TypeError):
                return None
        return s

    # Numeric handling
    if sql_type == "BOOLEAN":
        try:
            return bool(val)
        except Exception:
            return None
    if sql_type in ("SMALLINT", "INTEGER", "BIGINT"):
        try:
            i = int(val)
            # Clamp to SMALLINT range if needed (silently)
            if sql_type == "SMALLINT" and abs(i) > 32767:
                return None
            if sql_type == "INTEGER" and abs(i) > 2147483647:
                return None
            return i
        except (ValueError, TypeError, OverflowError):
            return None
    if sql_type.startswith("NUMERIC"):
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            return round(f, 4)
        except (ValueError, TypeError):
            return None
    if sql_type == "TEXT":
        return str(val).strip() or None

    return val


def _row_to_record(
    row: pd.Series,
    col_spec: Dict[str, str],
    inep_to_company_id: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """Convert a CSV row to a dict ready for school_analytics upsert."""
    inep = str(row.get("CODIGO_INEP", "")).strip()
    if not inep or inep.lower() == "nan":
        return None

    record: Dict[str, Any] = {"inep_code": inep}

    company_id = inep_to_company_id.get(inep)
    if company_id:
        record["company_id"] = company_id

    for col_name, sql_type in col_spec.items():
        if col_name in row.index:
            cleaned = _clean_value(row[col_name], sql_type)
            if cleaned is not None:
                record[col_name] = cleaned

    return record


def _load_inep_to_company_map() -> Dict[str, str]:
    """Load a map {inep_code: company_id} for link-up during import."""
    print("Carregando mapa INEP -> company_id de companies...")
    data: List[Dict[str, Any]] = []
    page = 0
    page_size = 1000
    while True:
        resp = (
            db.client.table("companies")
            .select("id,inep_code")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        if not resp.data:
            break
        data.extend(resp.data)
        if len(resp.data) < page_size:
            break
        page += 1
    result = {
        str(r["inep_code"]).strip(): r["id"]
        for r in data
        if r.get("inep_code")
    }
    print(f"  {len(result):,} escolas em companies")
    return result


def _upsert_batch(
    records: List[Dict[str, Any]],
    dry_run: bool = False,
) -> Tuple[int, int]:
    """Upsert a batch of records. Returns (upserted, errors)."""
    if not records:
        return (0, 0)
    if dry_run:
        return (len(records), 0)
    try:
        db.client.table("school_analytics").upsert(
            records,
            on_conflict="inep_code",
        ).execute()
        return (len(records), 0)
    except Exception as e:
        # Fall back to row-by-row to isolate failures
        logger.warning(
            "Batch upsert failed, fallback to per-row",
            extra={"error": str(e)[:200], "batch_size": len(records)},
        )
        ok = 0
        errs = 0
        for rec in records:
            try:
                db.client.table("school_analytics").upsert(
                    [rec], on_conflict="inep_code",
                ).execute()
                ok += 1
            except Exception as ee:
                errs += 1
                logger.warning(
                    "Row upsert failed",
                    extra={"inep": rec.get("inep_code"), "error": str(ee)[:200]},
                )
        return (ok, errs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_JSON))
    parser.add_argument("--sample", type=int, default=None,
                        help="Import only first N rows (for testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write to database, just validate")
    parser.add_argument("--only-in-companies", action="store_true",
                        help="Import only rows whose INEP matches a school in companies")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    csv_path = Path(args.csv)
    report_path = Path(args.report)

    if not csv_path.exists():
        print(f"ERRO: CSV nao encontrado em {csv_path}", file=sys.stderr)
        sys.exit(1)

    print("=" * 72)
    print("IMPORT SCHOOL ANALYTICS")
    print("=" * 72)
    print(f"CSV:        {csv_path}")
    print(f"Relatorio:  {report_path}")
    print(f"Dry run:    {args.dry_run}")
    print(f"Sample:     {args.sample or 'full'}")
    print(f"Only CRM:   {args.only_in_companies}")
    print(f"Batch size: {args.batch_size}")
    print()

    report = _load_report(report_path)
    col_spec = _build_column_spec(report)
    print(f"Colunas analiticas: {len(col_spec)}")
    print(f"Cenario: {report['scenario']}")
    print()

    inep_to_company_id = _load_inep_to_company_map()

    print(f"Carregando CSV (pode demorar)...")
    t0 = time.time()
    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        low_memory=False,
        nrows=args.sample,
    )
    print(f"  {len(df):,} linhas, {len(df.columns)} colunas ({time.time() - t0:.1f}s)")
    print()

    if args.only_in_companies:
        before = len(df)
        df = df[df["CODIGO_INEP"].astype(str).str.strip().isin(inep_to_company_id.keys())]
        print(f"Filtrando so escolas em companies: {before:,} -> {len(df):,}")
        print()

    # Processing loop
    total = len(df)
    upserted = 0
    skipped = 0
    errors = 0
    linked = 0
    batch: List[Dict[str, Any]] = []
    t0 = time.time()
    last_progress = t0

    for idx, row in enumerate(df.itertuples(index=False)):
        # Convert namedtuple back to Series for index access
        row_series = pd.Series(row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns, row)))

        record = _row_to_record(row_series, col_spec, inep_to_company_id)
        if record is None:
            skipped += 1
            continue

        if "company_id" in record:
            linked += 1

        batch.append(record)

        if len(batch) >= args.batch_size:
            ok, errs = _upsert_batch(batch, dry_run=args.dry_run)
            upserted += ok
            errors += errs
            batch = []

            # Progress every 5s
            now = time.time()
            if now - last_progress > 5:
                pct = (idx + 1) / total * 100
                rate = (idx + 1) / (now - t0)
                eta = (total - idx - 1) / rate if rate > 0 else 0
                print(
                    f"  [{idx + 1:,}/{total:,} {pct:5.1f}%] "
                    f"upserted={upserted:,} errors={errors} "
                    f"linked={linked:,} rate={rate:.0f}/s ETA={eta:.0f}s"
                )
                last_progress = now

    # Final batch
    if batch:
        ok, errs = _upsert_batch(batch, dry_run=args.dry_run)
        upserted += ok
        errors += errs

    elapsed = time.time() - t0
    print()
    print("=" * 72)
    print("RESULTADO")
    print("=" * 72)
    print(f"  Total processado: {total:,}")
    print(f"  Upserted:         {upserted:,}")
    print(f"  Linked (company): {linked:,}")
    print(f"  Skipped:          {skipped:,}")
    print(f"  Erros:            {errors:,}")
    print(f"  Tempo:            {elapsed:.1f}s")
    print(f"  Taxa:             {total / max(elapsed, 0.01):.0f} rows/s")
    print()

    if args.dry_run:
        print("*** DRY RUN — nada foi gravado no banco ***")
    else:
        # Sanity check
        try:
            r = db.client.table("school_analytics").select(
                "id", count="exact"
            ).limit(1).execute()
            total_in_db = r.count or 0
            linked_resp = db.client.table("school_analytics").select(
                "id", count="exact"
            ).not_.is_("company_id", "null").limit(1).execute()
            total_linked = linked_resp.count or 0
            print(f"  DB: total em school_analytics:   {total_in_db:,}")
            print(f"  DB: com company_id preenchido:   {total_linked:,}")
        except Exception as e:
            print(f"  Sanity check falhou: {e}")


if __name__ == "__main__":
    main()
