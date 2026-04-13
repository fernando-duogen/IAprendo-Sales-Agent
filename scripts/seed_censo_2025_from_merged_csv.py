"""Seed school_censo_yearly vintage 2025 from escolas_brasil_merged.csv.

O merged CSV tem 184.8k escolas com dados do Censo 2025 (formato CRM),
mas school_censo_yearly so tinha ~80 escolas (seeded do companies).
Este script popula vintage_censo=2025 com TODAS as escolas do merged CSV.

Usage:
    venv/Scripts/python.exe scripts/seed_censo_2025_from_merged_csv.py --sample 100 --dry-run
    venv/Scripts/python.exe scripts/seed_censo_2025_from_merged_csv.py
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.supabase_client import db
from utils.logger import logger

CSV_PATH = ROOT / "data" / "raw" / "escolas_brasil_merged.csv"
VINTAGE = 2025
BATCH_SIZE = 250
MAX_RETRIES = 3
INTER_BATCH_SLEEP = 0.05

# Mapeamento: coluna merged CSV → coluna school_censo_yearly
COLUMN_MAP = {
    "CODIGO_INEP": "inep_code",
    "NOME_ESCOLA": "name",
    "MUNICIPIO": "city",
    "UF": "state",
    "BAIRRO": "bairro",
    "CEP": "cep",
    # Matrículas
    "TOTAL_MATRICULAS": "qt_mat_bas",
    "MATRICULAS_INFANTIL": "qt_mat_inf",
    "MATRICULAS_FUNDAMENTAL": "qt_mat_fund",
    "MATRICULAS_FUND_AI": "qt_mat_fund_ai",
    "MATRICULAS_FUND_AF": "qt_mat_fund_af",
    "MATRICULAS_MEDIO": "qt_mat_med",
    "MATRICULAS_EJA": "qt_mat_eja",
    "MATRICULAS_PROFISSIONAL": "qt_mat_prof",
    # Docentes
    "TOTAL_DOCENTES": "qt_doc_bas",
    # Tecnologia
    "TEM_INTERNET": "in_internet",
    "INTERNET_ALUNOS": "in_internet_alunos",
    "INTERNET_APRENDIZAGEM": "in_internet_aprendizagem",
    "LAB_INFORMATICA": "in_laboratorio_informatica",
    "QT_DESKTOP_ALUNO": "qt_desktop_aluno",
    "QT_NOTEBOOK_ALUNO": "qt_comp_portatil_aluno",
    "QT_TABLET_ALUNO": "qt_tablet_aluno",
    # Infraestrutura
    "TEM_BIBLIOTECA": "in_biblioteca",
    "TEM_QUADRA_ESPORTES": "in_quadra_esportes",
    "TEM_LAB_CIENCIAS": "in_laboratorio_ciencias",
    "TEM_ALIMENTACAO": "in_alimentacao",
    # Dependência
    "DEPENDENCIA": "tp_dependencia",
}

# Campos booleanos (converter "Sim"/"Não"/1/0/True/False → bool)
BOOL_FIELDS = {
    "in_internet", "in_internet_alunos", "in_internet_aprendizagem",
    "in_laboratorio_informatica", "in_biblioteca", "in_quadra_esportes",
    "in_laboratorio_ciencias", "in_alimentacao",
}

# Dependência: texto → código numérico (tp_dependencia no Censo)
DEP_MAP = {
    "Federal": 1, "Estadual": 2, "Municipal": 3, "Privada": 4,
}


def _clean_val(val: Any) -> Any:
    """Limpa valor para inserção no DB."""
    if pd.isna(val):
        return None
    if isinstance(val, float) and (val != val):  # NaN
        return None
    return val


def _to_bool(val: Any) -> Optional[bool]:
    """Converte valor para booleano."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("sim", "true", "1", "s", "yes"):
        return True
    if s in ("nao", "não", "false", "0", "n", "no"):
        return False
    return None


def _row_to_record(row: pd.Series) -> Optional[Dict[str, Any]]:
    """Converte uma linha do CSV para registro do school_censo_yearly."""
    inep = str(row.get("CODIGO_INEP", "")).strip()
    if not inep or inep.lower() == "nan":
        return None

    record: Dict[str, Any] = {
        "inep_code": inep,
        "vintage_censo": VINTAGE,
    }

    for csv_col, db_col in COLUMN_MAP.items():
        if csv_col == "CODIGO_INEP":
            continue  # já mapeado
        val = row.get(csv_col)
        val = _clean_val(val)

        if db_col in BOOL_FIELDS:
            val = _to_bool(val)
        elif db_col == "tp_dependencia":
            val = DEP_MAP.get(str(val).strip(), None) if val else None
        elif db_col in ("qt_mat_bas", "qt_mat_inf", "qt_mat_fund", "qt_mat_fund_ai",
                        "qt_mat_fund_af", "qt_mat_med", "qt_mat_eja", "qt_mat_prof",
                        "qt_doc_bas", "qt_doc_fund", "qt_doc_med",
                        "qt_desktop_aluno", "qt_comp_portatil_aluno", "qt_tablet_aluno"):
            try:
                val = int(float(val)) if val is not None else None
            except (ValueError, TypeError):
                val = None
        elif db_col in ("cep",):
            val = str(val).strip() if val else None

        if val is not None:
            record[db_col] = val

    return record


def _upsert_batch(records: List[Dict], dry_run: bool = False) -> tuple:
    """UPSERT batch com retry."""
    if dry_run or not records:
        return (len(records), 0)
    for attempt in range(MAX_RETRIES):
        try:
            db.client.table("school_censo_yearly").upsert(
                records, on_conflict="inep_code,vintage_censo"
            ).execute()
            return (len(records), 0)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))
            else:
                logger.warning(f"Batch failed after {MAX_RETRIES} retries: {str(e)[:100]}")
                return (0, len(records))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Carregando {CSV_PATH.name}...")
    t0 = time.time()
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False, nrows=args.sample)
    print(f"  {len(df):,} linhas em {time.time() - t0:.1f}s")

    batch: List[Dict] = []
    total = ok = errs = 0
    t0 = time.time()

    for idx, row in df.iterrows():
        record = _row_to_record(row)
        if not record:
            continue
        batch.append(record)
        total += 1

        if len(batch) >= BATCH_SIZE:
            _ok, _err = _upsert_batch(batch, dry_run=args.dry_run)
            ok += _ok
            errs += _err
            batch = []
            time.sleep(INTER_BATCH_SLEEP)

            if total % 5000 == 0:
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed > 0 else 0
                remaining = (len(df) - total) / rate if rate > 0 else 0
                print(f"  {total:,}/{len(df):,} ({total/len(df)*100:.1f}%) "
                      f"ok={ok:,} err={errs} rate={rate:.0f}/s ETA={remaining:.0f}s")

    # Último batch
    if batch:
        _ok, _err = _upsert_batch(batch, dry_run=args.dry_run)
        ok += _ok
        errs += _err

    elapsed = time.time() - t0
    print()
    print(f"{'DRY-RUN' if args.dry_run else 'RESULTADO'}:")
    print(f"  Total processado: {total:,}")
    print(f"  OK: {ok:,}")
    print(f"  Erros: {errs}")
    print(f"  Tempo: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
