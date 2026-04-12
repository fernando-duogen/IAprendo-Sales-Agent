"""
Seed school_enem_yearly com vintage=2024 copiando dados que ja estao em
school_analytics. Prepara a tabela para receber ENEM 2025+ quando sair.

Motivo: o snapshot ENEM 2024 ja existe em school_analytics (migration 015).
Para deixar school_enem_yearly uniforme, copiamos essa vintage aqui. A
partir de ENEM 2025, os novos anos serao inseridos via pipeline adaptado.

Uso:
    python scripts/historico/seed_enem_2024_from_analytics.py
    python scripts/historico/seed_enem_2024_from_analytics.py --dry-run
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

from database.supabase_client import db
from utils.logger import logger


# Mapeamento 1:1 dos campos que queremos em school_enem_yearly
# (a tabela school_analytics tem mais colunas — aqui selecionamos so as
#  que vao para a visao historica)
ANALYTICS_COLS = [
    "inep_code", "company_id",
    "enem_amostra_confiavel", "enem_inscritos", "enem_presentes",
    "enem_taxa_presenca", "enem_dependencia",
    "enem_media_cn", "enem_media_ch", "enem_media_lc",
    "enem_media_mt", "enem_media_redacao", "enem_media_geral",
    "enem_redacao_comp1_media", "enem_redacao_comp2_media",
    "enem_redacao_comp3_media", "enem_redacao_comp4_media",
    "enem_redacao_comp5_media", "enem_redacao_pct_problemas",
    "enem_area_mais_fraca", "enem_potencial_melhoria",
    "enem_pct_acima_500", "enem_pct_acima_600", "enem_pct_acima_700",
    "enem_rank_br", "enem_rank_uf", "enem_rank_mun", "enem_rank_uf_dep",
    "enem_percentil_uf_dep", "enem_quartil_br",
]

BATCH_SIZE = 500


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("SEED ENEM 2024 <- school_analytics")
    print("=" * 72)
    print(f"dry_run: {args.dry_run}\n")

    # Paginar em school_analytics (185k rows, precisa paginar)
    print("Buscando school_analytics...")
    sel = ",".join(ANALYTICS_COLS)
    all_rows: List[Dict[str, Any]] = []
    page_size = 1000
    page = 0
    t0 = time.time()
    while True:
        r = (
            db.client.table("school_analytics")
            .select(sel)
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        if not r.data:
            break
        all_rows.extend(r.data)
        if len(r.data) < page_size:
            break
        page += 1
        if page % 10 == 0:
            print(f"  ...pagina {page}, total {len(all_rows):,}")
    print(f"  {len(all_rows):,} escolas em school_analytics ({time.time() - t0:.1f}s)")
    print()

    if not all_rows:
        print("school_analytics vazio — rode a migration 015 + import_school_analytics.py primeiro")
        return

    # Filtrar: so escolas com inep_code e que tem pelo menos algum dado
    records: List[Dict[str, Any]] = []
    for row in all_rows:
        if not row.get("inep_code"):
            continue
        # copiar campos 1:1
        rec = {
            k: v for k, v in row.items()
            if v is not None and k in ANALYTICS_COLS
        }
        rec["vintage_enem"] = 2024
        rec["source_file"] = "school_analytics (vintage 2024 snapshot)"
        records.append(rec)

    print(f"Records montados: {len(records):,}")
    print()

    if args.dry_run:
        print("*** DRY RUN — nada foi gravado ***")
        return

    # Upsert em batches
    print("Upsertando em school_enem_yearly...")
    total_ok = 0
    total_err = 0
    t_upsert = time.time()
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        try:
            db.client.table("school_enem_yearly").upsert(
                batch, on_conflict="inep_code,vintage_enem",
            ).execute()
            total_ok += len(batch)
        except Exception as e:
            logger.warning(f"Batch failed: {str(e)[:200]}")
            for rec in batch:
                try:
                    db.client.table("school_enem_yearly").upsert(
                        [rec], on_conflict="inep_code,vintage_enem",
                    ).execute()
                    total_ok += 1
                except Exception as ee:
                    total_err += 1
        if total_ok % 10000 == 0 and total_ok > 0:
            rate = total_ok / max(time.time() - t_upsert, 0.01)
            print(f"  {total_ok:,}/{len(records):,} rate={rate:.0f}/s")

    elapsed = time.time() - t_upsert
    print()
    print(f"Upserted: {total_ok:,}  Errors: {total_err}  Tempo: {elapsed:.0f}s")
    print()
    print("Verificacao SQL:")
    print("  SELECT vintage_enem, COUNT(*) FROM school_enem_yearly")
    print("  WHERE vintage_enem=2024 GROUP BY vintage_enem;")


if __name__ == "__main__":
    main()
