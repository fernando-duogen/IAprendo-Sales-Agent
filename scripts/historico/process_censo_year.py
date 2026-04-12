"""
Processa 1 ano do microdado do Censo Escolar e carrega em school_censo_yearly.

Cobertura: 2020-2024 (arquivo monolitico microdados_ed_basica_{ANO}.csv).
2025+ usa script separado (seed_censo_2025_from_companies.py) porque esta
num formato multi-tabela que ja foi integrado em companies.

Estrategia:
  - Le apenas as colunas relevantes (usecols) -> baixo uso de memoria
  - Deteccao dinamica: campos que existem no header sao usados, ausentes
    viram NULL (INEP muda o schema entre anos)
  - Encoding: 2020 usa latin-1, 2021+ usa utf-8 (detectado automaticamente)
  - UPSERT por (inep_code, vintage_censo) via Supabase

Uso:
    python scripts/historico/process_censo_year.py 2023
    python scripts/historico/process_censo_year.py 2020 2021 2022 2023 2024
    python scripts/historico/process_censo_year.py --sample 1000 2023
    python scripts/historico/process_censo_year.py --dry-run 2023
"""
import argparse
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

from database.supabase_client import db
from utils.logger import logger


# ===========================================================================
# PATHS — onde estao os microdados em disco (Fernando tem tudo centralizado
# em Downloads/microdados_enem_2024/microdados_censo_escolar_{ano})
# ===========================================================================

DOWNLOADS_BASE = Path(
    r"C:\Users\Fernando Nienaber\Downloads\microdados_censo_escolar_2025"
)


def censo_path_for(ano: int) -> Optional[Path]:
    """Resolve o caminho do microdado monolitico para um dado ano.

    2020: usa extensao .CSV (uppercase)
    2021-2024: usa .csv (lowercase)
    2025: formato multi-tabela (nao processado aqui — usar seed_censo_2025)
    """
    if ano < 2020 or ano > 2024:
        return None
    ext = "CSV" if ano == 2020 else "csv"
    return (
        DOWNLOADS_BASE
        / f"microdados_censo_escolar_{ano}"
        / "dados"
        / f"microdados_ed_basica_{ano}.{ext}"
    )


# ===========================================================================
# MAPEAMENTO DE CAMPOS
# ===========================================================================
# (nome_no_csv, nome_no_db, converter)
#
# Os nomes no CSV podem variar entre anos — se um campo nao existir no header
# de um ano, ele vira NULL silenciosamente. Isso e intencional: prefiro
# missing do que crash.

FIELD_MAP: List[tuple] = [
    # Identidade
    ("CO_ENTIDADE", "inep_code", str),
    ("NU_ANO_CENSO", "vintage_censo", int),
    ("NO_ENTIDADE", "name", str),
    ("NO_MUNICIPIO", "city", str),
    ("SG_UF", "state", str),
    ("NO_BAIRRO", "bairro", str),
    ("CO_CEP", "cep", str),
    ("TP_DEPENDENCIA", "tp_dependencia", int),
    ("TP_CATEGORIA_ESCOLA_PRIVADA", "categoria_privada", int),
    ("TP_LOCALIZACAO", "localizacao", int),
    ("TP_SITUACAO_FUNCIONAMENTO", "situacao_funcionamento", int),

    # Matriculas
    ("QT_MAT_BAS", "qt_mat_bas", int),
    ("QT_MAT_INF", "qt_mat_inf", int),
    ("QT_MAT_FUND", "qt_mat_fund", int),
    ("QT_MAT_FUND_AI", "qt_mat_fund_ai", int),
    ("QT_MAT_FUND_AF", "qt_mat_fund_af", int),
    ("QT_MAT_MED", "qt_mat_med", int),
    ("QT_MAT_EJA", "qt_mat_eja", int),
    ("QT_MAT_PROF", "qt_mat_prof", int),

    # Equipe
    ("QT_DOC_BAS", "qt_doc_bas", int),
    ("QT_DOC_FUND", "qt_doc_fund", int),
    ("QT_DOC_MED", "qt_doc_med", int),

    # Tecnologia
    ("IN_INTERNET", "in_internet", bool),
    ("IN_INTERNET_ALUNOS", "in_internet_alunos", bool),
    ("IN_INTERNET_APRENDIZAGEM", "in_internet_aprendizagem", bool),
    ("IN_LABORATORIO_INFORMATICA", "in_laboratorio_informatica", bool),
    ("QT_DESKTOP_ALUNO", "qt_desktop_aluno", int),
    ("QT_COMP_PORTATIL_ALUNO", "qt_comp_portatil_aluno", int),
    ("QT_TABLET_ALUNO", "qt_tablet_aluno", int),

    # Infraestrutura
    ("IN_BIBLIOTECA", "in_biblioteca", bool),
    ("IN_BIBLIOTECA_SALA_LEITURA", "in_biblioteca_sala_leitura", bool),
    ("IN_QUADRA_ESPORTES", "in_quadra_esportes", bool),
    ("IN_LABORATORIO_CIENCIAS", "in_laboratorio_ciencias", bool),
    ("IN_ALIMENTACAO", "in_alimentacao", bool),
]


BATCH_SIZE = 250             # Menos agressivo que 500; PostgREST/Supabase digere melhor
MAX_BATCH_RETRIES = 3        # Retries antes de cair pro fallback row-by-row
INTER_BATCH_SLEEP_S = 0.05   # 50ms entre batches — alivia rate limit pre-emptivamente


def _detect_encoding(path: Path) -> str:
    """Detect if file is latin-1 or utf-8 by trying to read the header."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                f.readline()
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # fallback


def _clean_value(val: Any, converter) -> Optional[Any]:
    """Coerce a raw pandas value to the type expected by the DB."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, str):
        s = val.strip()
        if not s or s.lower() in ("nan", "null", "none"):
            return None
        val = s

    if converter is bool:
        # No Censo: 0/1, as vezes "0"/"1"
        try:
            i = int(float(val))
            return bool(i)
        except (ValueError, TypeError):
            return None

    if converter is int:
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return None
            i = int(f)
            if abs(i) > 2147483647:
                return None
            return i
        except (ValueError, TypeError):
            return None

    if converter is str:
        return str(val).strip()

    return val


def _load_company_id_map() -> Dict[str, str]:
    """Load {inep_code: company_id} from companies for linking."""
    print("Carregando mapa INEP -> company_id de companies...")
    data: List[Dict[str, Any]] = []
    page_size = 1000
    page = 0
    while True:
        r = (
            db.client.table("companies")
            .select("id,inep_code")
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        if not r.data:
            break
        data.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
    return {
        str(d["inep_code"]).strip(): d["id"]
        for d in data
        if d.get("inep_code")
    }


def _is_rate_limit_error(err_msg: str) -> bool:
    """Detecta erros que indicam rate limit ou sobrecarga transitoria."""
    lc = err_msg.lower()
    return any(s in lc for s in [
        "429", "503", "timeout", "rate limit", "too many",
        "service unavailable", "connection reset", "connection aborted",
    ])


def _upsert_batch(
    records: List[Dict[str, Any]],
    dry_run: bool = False,
) -> tuple:
    """Upsert com retry exponencial e fallback row-by-row inteligente.

    Estrategia:
      1. Tenta o batch inteiro ate MAX_BATCH_RETRIES vezes, com backoff
         exponencial (2s, 5s, 12s + jitter) entre tentativas.
      2. Se esgotar, cai pro fallback row-by-row — mas cada row tambem
         tem 1 retry com 1s de pausa. Evita o anti-padrao da versao
         anterior, onde o fallback virava 500 requests instantaneas que
         batiam em rate limit em cascata.
    """
    if not records:
        return (0, 0)
    if dry_run:
        return (len(records), 0)

    # --- Tentativa de batch com retry ---
    for attempt in range(MAX_BATCH_RETRIES + 1):
        try:
            db.client.table("school_censo_yearly").upsert(
                records,
                on_conflict="inep_code,vintage_censo",
            ).execute()
            return (len(records), 0)
        except Exception as e:
            err_msg = str(e)[:200]
            is_transient = _is_rate_limit_error(err_msg)

            if attempt < MAX_BATCH_RETRIES:
                # Backoff: 2, 5, 12s (+ jitter random 0-1s)
                wait = [2.0, 5.0, 12.0][attempt] + random.random()
                logger.warning(
                    f"Batch attempt {attempt + 1}/{MAX_BATCH_RETRIES + 1} failed "
                    f"(rate_limit={is_transient}), waiting {wait:.1f}s: {err_msg}"
                )
                time.sleep(wait)
                continue

            # --- Esgotou retries de batch -> row-by-row com retry leve ---
            logger.warning(
                f"Batch esgotou {MAX_BATCH_RETRIES + 1} tentativas, "
                f"fallback row-by-row: {err_msg}"
            )
            ok = 0
            errs = 0
            for rec in records:
                for row_attempt in range(2):  # 1 retry por row
                    try:
                        db.client.table("school_censo_yearly").upsert(
                            [rec], on_conflict="inep_code,vintage_censo",
                        ).execute()
                        ok += 1
                        break
                    except Exception as re:
                        if row_attempt == 0:
                            time.sleep(1.0)  # pausa entre retries de row
                        else:
                            errs += 1
                            logger.warning(
                                f"Row failed: inep={rec.get('inep_code')} "
                                f"vintage={rec.get('vintage_censo')} "
                                f"err={str(re)[:120]}"
                            )
            return (ok, errs)

    # unreachable
    return (0, len(records))


def process_year(
    ano: int,
    company_id_map: Dict[str, str],
    sample: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Process one year of Censo and upsert into school_censo_yearly."""
    path = censo_path_for(ano)
    if not path or not path.exists():
        print(f"[{ano}] ARQUIVO NAO ENCONTRADO: {path}")
        return {"ano": ano, "total": 0, "error": "not found"}

    print(f"[{ano}] {path.name} ({path.stat().st_size / 1024**2:.0f} MB)")

    # 1. Detect encoding and read header
    enc = _detect_encoding(path)
    print(f"[{ano}] encoding={enc}")

    with open(path, "r", encoding=enc) as f:
        header_line = f.readline().strip()
    available_cols = set(header_line.split(";"))

    # 2. Filter FIELD_MAP to cols that actually exist in this year
    active_map = [
        (csv_col, db_col, conv)
        for csv_col, db_col, conv in FIELD_MAP
        if csv_col in available_cols
    ]
    active_csv_cols = [csv_col for csv_col, _, _ in active_map]
    missing = [csv_col for csv_col, _, _ in FIELD_MAP if csv_col not in available_cols]
    if missing:
        print(f"[{ano}] campos ausentes (serao NULL): {missing}")
    print(f"[{ano}] campos usados: {len(active_csv_cols)}/{len(FIELD_MAP)}")

    # 3. Read the CSV with usecols (fast — ignores 340+ other columns)
    print(f"[{ano}] lendo CSV com usecols...")
    t_read = time.time()
    df = pd.read_csv(
        path,
        sep=";",
        encoding=enc,
        usecols=active_csv_cols,
        low_memory=False,
        nrows=sample,
    )
    print(f"[{ano}] {len(df):,} linhas em {time.time() - t_read:.1f}s")

    # 4. Convert rows to records
    print(f"[{ano}] convertendo e upsertando...")
    t_proc = time.time()
    batch: List[Dict[str, Any]] = []
    total = 0
    upserted = 0
    errors = 0
    skipped = 0
    linked = 0

    for row in df.itertuples(index=False):
        total += 1
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(
            zip(df.columns, row)
        )
        record: Dict[str, Any] = {}
        for csv_col, db_col, conv in active_map:
            if csv_col in row_dict:
                cleaned = _clean_value(row_dict[csv_col], conv)
                if cleaned is not None:
                    record[db_col] = cleaned

        # inep_code e' obrigatorio
        if not record.get("inep_code"):
            skipped += 1
            continue

        # Forcar vintage mesmo que o CSV tenha um NU_ANO_CENSO estranho
        record["vintage_censo"] = ano
        record["source_file"] = path.name

        # Link com companies quando existe match por INEP
        cid = company_id_map.get(str(record["inep_code"]).strip())
        if cid:
            record["company_id"] = cid
            linked += 1

        batch.append(record)

        if len(batch) >= BATCH_SIZE:
            ok, errs = _upsert_batch(batch, dry_run=dry_run)
            upserted += ok
            errors += errs
            batch = []
            # Sleep curto entre batches — alivia rate limit pre-emptivamente
            # e evita que o Supabase comece a retornar 429 em cascata
            if not dry_run:
                time.sleep(INTER_BATCH_SLEEP_S)
            if upserted % 10000 == 0:
                rate = upserted / max(time.time() - t_proc, 0.01)
                print(
                    f"[{ano}]   {upserted:,}/{len(df):,} "
                    f"({upserted / len(df) * 100:.0f}%) "
                    f"linked={linked:,} rate={rate:.0f}/s"
                )

    if batch:
        ok, errs = _upsert_batch(batch, dry_run=dry_run)
        upserted += ok
        errors += errs

    elapsed = time.time() - t_proc
    print(
        f"[{ano}] OK — total={total:,} upserted={upserted:,} "
        f"linked={linked:,} skipped={skipped:,} errors={errors:,} "
        f"tempo={elapsed:.1f}s"
    )
    return {
        "ano": ano,
        "total": total,
        "upserted": upserted,
        "linked": linked,
        "skipped": skipped,
        "errors": errors,
        "elapsed_s": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="+", type=int,
                        help="Anos a processar (ex: 2023 ou 2020 2021 2022)")
    parser.add_argument("--sample", type=int, default=None,
                        help="Processar apenas N linhas por ano (para teste)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Nao grava no banco (valida conversao apenas)")
    args = parser.parse_args()

    valid_years = [y for y in args.years if 2020 <= y <= 2024]
    invalid = [y for y in args.years if y not in valid_years]
    if invalid:
        print(f"ANOS INVALIDOS (fora de 2020-2024): {invalid}")
        print("Para 2025+, use seed_censo_2025_from_companies.py")
        sys.exit(1)

    print("=" * 72)
    print("PROCESS CENSO YEARLY")
    print("=" * 72)
    print(f"anos: {valid_years}")
    print(f"sample: {args.sample or 'full'}")
    print(f"dry_run: {args.dry_run}")
    print()

    # Cache INEP -> company_id uma unica vez
    company_id_map = _load_company_id_map()
    print(f"  {len(company_id_map):,} escolas em companies (referencia de link)\n")

    results = []
    for ano in valid_years:
        r = process_year(
            ano,
            company_id_map=company_id_map,
            sample=args.sample,
            dry_run=args.dry_run,
        )
        results.append(r)
        print()

    print("=" * 72)
    print("RESULTADO FINAL")
    print("=" * 72)
    for r in results:
        if "error" in r:
            print(f"  [{r['ano']}] ERRO: {r['error']}")
        else:
            print(
                f"  [{r['ano']}] upserted={r['upserted']:,} "
                f"linked={r['linked']:,} "
                f"errors={r['errors']} "
                f"tempo={r['elapsed_s']:.0f}s"
            )

    if args.dry_run:
        print()
        print("*** DRY RUN — nenhum dado foi gravado ***")
    else:
        print()
        print("Verificacao SQL recomendada:")
        print("  SELECT vintage_censo, COUNT(*) FROM school_censo_yearly")
        print("  GROUP BY vintage_censo ORDER BY vintage_censo;")


if __name__ == "__main__":
    main()
