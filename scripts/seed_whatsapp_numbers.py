"""
seed_whatsapp_numbers.py — Popula contacts.phone_whatsapp em lote
para escolas com Fit IAprendo alto que ainda nao tem WhatsApp cadastrado.

Fluxo:
1. Busca escolas qualificadas (qualification_score > 0)
2. Calcula Fit IAprendo para cada uma
3. Filtra escolas SEM nenhum contato com phone_whatsapp
4. Ordena por Fit desc
5. Roda whatsapp_finder.process_batch() no top N

Uso:
    venv/Scripts/python.exe scripts/seed_whatsapp_numbers.py --dry-run
    venv/Scripts/python.exe scripts/seed_whatsapp_numbers.py --limit 10 --yes
    venv/Scripts/python.exe scripts/seed_whatsapp_numbers.py --limit 15 --min-fit 40 --yes
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from tools.whatsapp_finder import whatsapp_finder
from utils.fit_score import calcular_fit_score
from utils.logger import logger


def _list_candidate_schools(min_score: int, min_fit: int) -> list:
    """Retorna escolas qualificadas SEM phone_whatsapp, ordenadas por Fit desc."""
    # 1. Busca escolas qualificadas
    try:
        companies = db.client.table("companies").select(
            "id,name,city,state,qualification_score,admin_category,"
            "matriculas_fund_af,matriculas_medio,nivel_tecnologico,"
            "qt_coordenadores,categoria_privada,fonte_dados"
        ).gte("qualification_score", min_score).limit(500).execute().data or []
    except Exception as e:
        logger.error(f"Erro ao buscar companies: {e}")
        return []

    if not companies:
        return []

    # 2. Filtra escolas SEM phone_whatsapp em nenhum contato
    company_ids = [c["id"] for c in companies]
    try:
        contacts_with_wpp = db.client.table("contacts").select("company_id").in_(
            "company_id", company_ids
        ).not_.is_("phone_whatsapp", "null").execute().data or []
    except Exception as e:
        logger.error(f"Erro ao buscar contacts: {e}")
        return []

    has_wpp = {c["company_id"] for c in contacts_with_wpp}
    candidates = [c for c in companies if c["id"] not in has_wpp]

    # 3. Calcula Fit e ordena
    for c in candidates:
        fit = calcular_fit_score(c)
        c["_fit_score"] = fit.get("score") or 0
        c["_fit_level"] = fit.get("level") or "sem_dados"

    if min_fit > 0:
        candidates = [c for c in candidates if (c["_fit_score"] or 0) >= min_fit]

    candidates.sort(key=lambda x: x["_fit_score"] or 0, reverse=True)
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed phone_whatsapp via WhatsApp Finder")
    parser.add_argument("--limit", type=int, default=15, help="Max escolas a processar (default 15)")
    parser.add_argument("--min-score", type=int, default=1, help="qualification_score minimo (default 1)")
    parser.add_argument("--min-fit", type=int, default=0, help="Fit score minimo (0 = sem filtro)")
    parser.add_argument("--dry-run", action="store_true", help="So lista, nao executa")
    parser.add_argument("--yes", action="store_true", help="Nao pede confirmacao")
    args = parser.parse_args()

    print(f"\n=== SEED WhatsApp Numbers ===")
    print(f"  min-score: {args.min_score}")
    print(f"  min-fit:   {args.min_fit}")
    print(f"  limit:     {args.limit}")
    print(f"  dry-run:   {args.dry_run}")

    candidates = _list_candidate_schools(args.min_score, args.min_fit)
    if not candidates:
        print("\nNenhuma escola candidata (ou todas ja tem phone_whatsapp).")
        return 0

    top = candidates[: args.limit]
    print(f"\nEscolas candidatas: {len(candidates)} total, processando top {len(top)}:\n")
    for i, c in enumerate(top, 1):
        nome = (c.get("name") or "")[:50]
        cidade = c.get("city") or "?"
        fit = c.get("_fit_score") or 0
        score = c.get("qualification_score") or 0
        print(f"  {i:2}. [{fit:3}fit / {score:3}score] {nome} ({cidade})")

    if args.dry_run:
        print("\n[DRY-RUN] Nada foi executado.")
        return 0

    if not args.yes:
        resp = input(f"\nConfirmar busca de WhatsApp para {len(top)} escolas? (s/N): ")
        if resp.strip().lower() not in ("s", "sim", "y", "yes"):
            print("Cancelado.")
            return 0

    print(f"\nRodando whatsapp_finder.process_batch (max {len(top)})...\n")
    # Prepara formato esperado pelo process_batch
    batch_input = [
        {"id": c["id"], "name": c["name"], "city": c.get("city"), "state": c.get("state")}
        for c in top
    ]
    result = whatsapp_finder.process_batch(batch_input, max_per_run=len(top))

    print("\n=== RESULTADO ===")
    print(f"  processadas: {result.get('processed', 0)}")
    print(f"  encontradas: {result.get('found', 0)}")
    print(f"  puladas:     {result.get('skipped', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
