"""Fix mojibake in school_analytics.peer_mun_nome / socio_mun_nome.

Substitui bytes U+FFFD ( character) que chegaram ja corrompidos do CSV fonte
(`escolas_brasil_enriquecido.csv`) pelos nomes corretos vindos de
`school_censo_yearly.city` (mesma escola, vintage mais recente).

Estrategia:
  1. Construir mapa inep_code -> city limpo a partir de school_censo_yearly
     (paginado; pegamos apenas o vintage mais recente de cada inep).
  2. Buscar todas as rows de school_analytics com U+FFFD em peer_mun_nome
     OU em socio_mun_nome (paginado).
  3. Para cada, se encontrarmos a escola no mapa, UPDATE individual via
     .eq("inep_code", ...).update(). Se nao encontrarmos, skip (a camada
     de runtime _clean_text remove o U+FFFD na hora de exibir).

Idempotente: rodar de novo nao quebra nada.

Usage:
    venv/Scripts/python.exe scripts/fix_mojibake_school_analytics.py [--dry-run]
"""
import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.supabase_client import db  # noqa: E402
from utils.logger import logger  # noqa: E402


REPLACEMENT_CHAR = "\ufffd"
PAGE_SIZE = 1000


def _build_clean_city_map() -> Dict[str, str]:
    """Carrega inep_code -> city limpo de school_censo_yearly (vintage mais recente)."""
    print("Carregando mapa inep->city de school_censo_yearly (vintage mais recente)...")
    t0 = time.time()
    mapping: Dict[str, str] = {}

    # Pagina pela tabela para nao estourar limite de 1000 rows do PostgREST
    page = 0
    while True:
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE - 1
        try:
            r = (
                db.client.table("school_censo_yearly")
                .select("inep_code,city,vintage_censo")
                .not_.is_("city", "null")
                .order("vintage_censo", desc=True)
                .range(start, end)
                .execute()
            )
        except Exception as e:
            logger.error(f"Erro carregando school_censo_yearly page {page}: {e}")
            break

        rows = r.data or []
        if not rows:
            break

        for row in rows:
            inep = str(row.get("inep_code") or "").strip()
            city = row.get("city")
            if inep and city and inep not in mapping:
                # Primeira ocorrencia = vintage mais recente (ORDER BY vintage_censo DESC)
                mapping[inep] = city

        page += 1
        if page % 10 == 0:
            print(f"  ... {page * PAGE_SIZE:,} rows processadas, {len(mapping):,} inep unicos")

    print(f"Mapa carregado: {len(mapping):,} inep_codes unicos em {time.time() - t0:.1f}s")
    return mapping


def _fetch_corrupted_rows() -> List[Dict]:
    """Busca todas as rows de school_analytics com U+FFFD em peer_mun_nome ou socio_mun_nome."""
    print("Buscando rows corrompidas em school_analytics...")
    t0 = time.time()
    rows: List[Dict] = []

    # peer_mun_nome
    page = 0
    while True:
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE - 1
        r = (
            db.client.table("school_analytics")
            .select("inep_code,peer_mun_nome,socio_mun_nome")
            .ilike("peer_mun_nome", f"%{REPLACEMENT_CHAR}%")
            .range(start, end)
            .execute()
        )
        batch = r.data or []
        if not batch:
            break
        rows.extend(batch)
        page += 1

    seen_ineps = {str(r.get("inep_code")).strip() for r in rows}

    # socio_mun_nome (pode ter rows que NAO estavam no peer)
    page = 0
    while True:
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE - 1
        r = (
            db.client.table("school_analytics")
            .select("inep_code,peer_mun_nome,socio_mun_nome")
            .ilike("socio_mun_nome", f"%{REPLACEMENT_CHAR}%")
            .range(start, end)
            .execute()
        )
        batch = r.data or []
        if not batch:
            break
        for row in batch:
            inep = str(row.get("inep_code")).strip()
            if inep not in seen_ineps:
                rows.append(row)
                seen_ineps.add(inep)
        page += 1

    print(f"Encontradas {len(rows):,} rows corrompidas em {time.time() - t0:.1f}s")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    clean_map = _build_clean_city_map()
    if not clean_map:
        print("ERRO: mapa vazio — abortando.")
        sys.exit(1)

    corrupted = _fetch_corrupted_rows()
    if not corrupted:
        print("Nenhuma row corrompida — nada a fazer.")
        return

    print()
    print(f"Iniciando {'DRY-RUN' if args.dry_run else 'UPDATE'} de {len(corrupted):,} rows...")
    print()

    t0 = time.time()
    updated = 0
    no_match = 0
    errors = 0
    updates_breakdown = {"peer": 0, "socio": 0, "both": 0}

    for i, row in enumerate(corrupted):
        inep = str(row.get("inep_code") or "").strip()
        peer_broken = row.get("peer_mun_nome") or ""
        socio_broken = row.get("socio_mun_nome") or ""

        clean_city = clean_map.get(inep)
        if not clean_city:
            no_match += 1
            continue

        updates = {}
        if REPLACEMENT_CHAR in peer_broken:
            updates["peer_mun_nome"] = clean_city
        if REPLACEMENT_CHAR in socio_broken:
            updates["socio_mun_nome"] = clean_city

        if not updates:
            continue

        if "peer_mun_nome" in updates and "socio_mun_nome" in updates:
            updates_breakdown["both"] += 1
        elif "peer_mun_nome" in updates:
            updates_breakdown["peer"] += 1
        else:
            updates_breakdown["socio"] += 1

        if not args.dry_run:
            try:
                db.client.table("school_analytics").update(updates).eq(
                    "inep_code", inep
                ).execute()
                updated += 1
            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"Erro updating inep={inep}: {str(e)[:200]}")
        else:
            updated += 1

        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            remaining = (len(corrupted) - i - 1) / rate if rate > 0 else 0
            print(
                f"  {i + 1:,}/{len(corrupted):,} "
                f"({(i + 1) / len(corrupted) * 100:.1f}%) "
                f"updated={updated:,} no_match={no_match:,} errors={errors:,} "
                f"rate={rate:.0f}/s ETA={remaining:.0f}s"
            )

    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(f"{'DRY-RUN' if args.dry_run else 'RESULTADO'}:")
    print(f"  Total processado : {len(corrupted):,}")
    print(f"  Updated          : {updated:,}")
    print(f"    so peer        : {updates_breakdown['peer']:,}")
    print(f"    so socio       : {updates_breakdown['socio']:,}")
    print(f"    both           : {updates_breakdown['both']:,}")
    print(f"  Sem match em censo_yearly: {no_match:,}")
    print(f"  Erros            : {errors:,}")
    print(f"  Tempo            : {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
