"""
Re-qualifica todas as escolas do banco usando os dados ricos do Censo 2025.

Uso:
    venv/Scripts/python.exe scripts/rescore_all.py              # re-qualifica TODAS
    venv/Scripts/python.exe scripts/rescore_all.py --only-censo # so censo_2025
    venv/Scripts/python.exe scripts/rescore_all.py --limit 10   # so 10 escolas (teste)
    venv/Scripts/python.exe scripts/rescore_all.py --dry-run    # simulacao

O qualifier agora tem acesso a:
- Total de matriculas + matriculas Fund AF + Medio
- Equipe (docentes, gestores, coordenadores, turmas)
- Nivel tecnologico (Alto/Medio/Baixo)
- Infraestrutura (banda larga, lab, etc.)

Escolas com fonte_dados=catalogo_inep tem dados limitados — o qualifier
ja sabe disso pelo aviso no format_school_data e ajusta o criterio.
"""
import sys
import os
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from agents.qualifier import QualifierAgent
from database.supabase_client import db
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-censo", action="store_true",
                        help="Re-qualifica so escolas com fonte_dados=censo_2025")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximo de escolas (util para teste)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem chamar API nem salvar")
    parser.add_argument("--only-missing", action="store_true",
                        help="So escolas sem qualification_score")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Pula confirmacao interativa (para rodar em CI/batch)")
    args = parser.parse_args()

    print("=" * 70)
    print("RE-QUALIFICACAO EM BATCH")
    print("=" * 70)

    # Buscar escolas do banco
    query = db.client.table("companies").select("*")
    if args.only_censo:
        query = query.eq("fonte_dados", "censo_2025")
    if args.only_missing:
        query = query.is_("qualification_score", "null")
    if args.limit:
        query = query.limit(args.limit)

    result = query.execute()
    schools = result.data or []

    print(f"\nEscolas encontradas: {len(schools)}")
    if args.only_censo:
        print("  Filtro: so fonte_dados=censo_2025")
    if args.only_missing:
        print("  Filtro: so sem qualification_score")

    if not schools:
        print("\nNada para processar.")
        return

    # Mostrar preview
    print("\nPreview (primeiras 5):")
    for s in schools[:5]:
        fonte = s.get("fonte_dados") or "?"
        score_atual = s.get("qualification_score") or "-"
        mat = s.get("total_matriculas") or 0
        tech = s.get("nivel_tecnologico") or "-"
        print(f"  [{s.get('inep_code')}] {s['name'][:45]} | score={score_atual} | mat={mat} | tech={tech} | {fonte}")

    if args.dry_run:
        print("\n[DRY RUN] Nenhuma alteracao foi feita.")
        return

    # Confirmar (exceto se --yes)
    print(f"\nIsso vai chamar o LLM {len(schools)} vezes (GPT-4.1-mini — rapido/barato).")
    print(f"Custo estimado: ~R$ {len(schools) * 0.02:.2f}")
    if not args.yes:
        resposta = input("\nProsseguir? (sim/nao): ").strip().lower()
        if resposta not in ("sim", "s", "y", "yes"):
            print("Cancelado.")
            return
    else:
        print("\n[--yes] Pulando confirmacao.")

    # Re-qualificar
    print("\nRe-qualificando...")
    print("-" * 70)

    qualifier = QualifierAgent()
    resultados = qualifier.execute(schools)

    print("-" * 70)
    print(f"\n[OK] Re-qualificadas: {len(resultados)} / {len(schools)}")

    # Mostrar mudancas top/bottom
    if resultados:
        # Buscar scores antigos
        old_scores = {s["id"]: s.get("qualification_score") or 0 for s in schools}
        mudancas = []
        for r in resultados:
            cid = r.get("company_id")
            new_score = r.get("score", 0)
            old = old_scores.get(cid, 0)
            diff = new_score - old
            mudancas.append({
                "nome": r.get("company_name", "?"),
                "old": old,
                "new": new_score,
                "diff": diff,
                "reasoning": r.get("reasoning", ""),
            })

        # Maiores altas
        mudancas.sort(key=lambda x: x["diff"], reverse=True)
        print("\n=== Top 5 ALTAS ===")
        for m in mudancas[:5]:
            sinal = "+" if m["diff"] >= 0 else ""
            print(f"  {m['nome'][:45]:45s}  {m['old']} -> {m['new']}  ({sinal}{m['diff']})")

        # Maiores quedas
        mudancas.sort(key=lambda x: x["diff"])
        print("\n=== Top 5 QUEDAS ===")
        for m in mudancas[:5]:
            sinal = "+" if m["diff"] >= 0 else ""
            print(f"  {m['nome'][:45]:45s}  {m['old']} -> {m['new']}  ({sinal}{m['diff']})")

        # Estatisticas
        news = [m["new"] for m in mudancas]
        print(f"\n=== Estatisticas dos novos scores ===")
        print(f"  Min: {min(news)} | Max: {max(news)} | Media: {sum(news)/len(news):.0f}")
        print(f"  Escolas >= 70: {sum(1 for n in news if n >= 70)}")
        print(f"  Escolas 40-69: {sum(1 for n in news if 40 <= n < 70)}")
        print(f"  Escolas < 40: {sum(1 for n in news if n < 40)}")


if __name__ == "__main__":
    main()
