"""
Popula o banco de memorias (conversation_memory) com insights concretos
extraidos dos dados ricos do Censo 2025 das escolas ja cadastradas.

Para cada escola com fonte_dados='censo_2025':
- Escala: 'X alunos em Fund AF+Medio (Y total)' — se alvo >= 100
- Nivel tec Alto: 'Nivel tecnologico Alto: banda larga, lab, ...' — se nivel=Alto
- Coordenacao: 'Escola tem N coordenadores pedagogicos' — se N >= 3
- Rede: 'Pertence a rede X (N unidades, M alvo total)' — se faz parte

Idempotente: nao duplica memorias existentes (memory_capture usa dedupe_query).

Uso:
    # Preview (sem aplicar)
    venv/Scripts/python.exe scripts/seed_census_memories.py --dry-run

    # Aplicar (pede confirmacao)
    venv/Scripts/python.exe scripts/seed_census_memories.py

    # Aplicar sem perguntar (batch/CI)
    venv/Scripts/python.exe scripts/seed_census_memories.py --yes
"""
import sys
import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv()

from database.supabase_client import db
from tools.memory_capture import capture_census_insights, capture_network_insight
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview sem aplicar")
    parser.add_argument("--yes", "-y", action="store_true", help="Pula confirmacao")
    parser.add_argument("--limit", type=int, default=None, help="Max escolas (para teste)")
    args = parser.parse_args()

    print("=" * 70)
    print("SEED CENSUS MEMORIES")
    print("=" * 70)

    # Buscar escolas com fonte_dados='censo_2025'
    query = db.client.table("companies").select(
        "id,name,city,state,fonte_dados,total_matriculas,matriculas_fund_af,"
        "matriculas_medio,nivel_tecnologico,qt_coordenadores,cnpj_mantenedora,"
        "banda_larga,lab_informatica,internet_alunos,internet_aprendizagem"
    ).eq("fonte_dados", "censo_2025")

    if args.limit:
        query = query.limit(args.limit)

    result = query.execute()
    escolas = result.data or []
    print(f"\nEscolas Censo 2025 encontradas: {len(escolas)}")

    if not escolas:
        print("Nada para processar.")
        return

    # Agrupar por cnpj_mantenedora para detectar redes
    por_cnpj = defaultdict(list)
    for e in escolas:
        cnpj = e.get("cnpj_mantenedora")
        if cnpj:
            por_cnpj[cnpj].append(e)

    # Identificar redes (2+ unidades)
    redes = {cnpj: escolas_rede for cnpj, escolas_rede in por_cnpj.items() if len(escolas_rede) >= 2}
    print(f"Redes detectadas: {len(redes)}")
    for cnpj, escolas_rede in list(redes.items())[:5]:
        nomes = [e["name"][:30] for e in escolas_rede[:3]]
        print(f"  [{cnpj}] {len(escolas_rede)} unidades: {', '.join(nomes)}...")

    # Helper para derivar nome da rede (reusa logica do brain)
    try:
        from agent.brain import _derivar_nome_rede
    except ImportError:
        def _derivar_nome_rede(escolas):
            return "Rede sem nome"

    # Preview: contar quantas memorias seriam criadas
    print(f"\n=== PREVIEW ===")
    preview_escala = 0
    preview_tech = 0
    preview_coord = 0
    preview_rede = 0
    for e in escolas:
        fund_af = int(e.get("matriculas_fund_af") or 0)
        medio = int(e.get("matriculas_medio") or 0)
        alvo = fund_af + medio
        if alvo >= 100:
            preview_escala += 1
        if (e.get("nivel_tecnologico") or "") == "Alto":
            preview_tech += 1
        if int(e.get("qt_coordenadores") or 0) >= 3:
            preview_coord += 1
        cnpj = e.get("cnpj_mantenedora")
        if cnpj and cnpj in redes:
            preview_rede += 1

    total_preview = preview_escala + preview_tech + preview_coord + preview_rede
    print(f"  Memoria de escala (>=100 alvo): {preview_escala}")
    print(f"  Memoria de tech Alto: {preview_tech}")
    print(f"  Memoria de coordenacao forte (>=3 coord): {preview_coord}")
    print(f"  Memoria de rede educacional: {preview_rede}")
    print(f"  TOTAL (bruto, antes de dedupe): {total_preview}")
    print(f"\n  OBS: idempotencia remove duplicatas via memory.search() antes de gravar.")
    print(f"  Se ja rodou antes, resultado final sera MENOR.")

    if args.dry_run:
        print("\n[DRY RUN] Nenhuma memoria foi gravada.")
        return

    if not args.yes:
        print(f"\nIsso vai gravar ate {total_preview} memorias na tabela conversation_memory.")
        resposta = input("Prosseguir? (sim/nao): ").strip().lower()
        if resposta not in ("sim", "s", "y", "yes"):
            print("Cancelado.")
            return
    else:
        print("\n[--yes] Pulando confirmacao.")

    # Executar
    print("\nGravando memorias...")
    print("-" * 70)
    total_criadas = 0
    for i, e in enumerate(escolas, 1):
        # 1. Insights basicos (escala, tech, coord)
        criadas = capture_census_insights(e)

        # 2. Insight de rede (so se for rede)
        cnpj = e.get("cnpj_mantenedora")
        if cnpj and cnpj in redes:
            escolas_rede = redes[cnpj]
            nome_rede = _derivar_nome_rede(escolas_rede)
            alvo_total = sum(
                int((er.get("matriculas_fund_af") or 0) + (er.get("matriculas_medio") or 0))
                for er in escolas_rede
            )
            mem_id = capture_network_insight(
                company_id=e["id"],
                nome_rede=nome_rede,
                n_unidades=len(escolas_rede),
                alvo_total=alvo_total,
            )
            if mem_id:
                criadas += 1

        total_criadas += criadas
        if i % 10 == 0:
            print(f"  Processadas: {i}/{len(escolas)} escolas, {total_criadas} memorias criadas")

    print("-" * 70)
    print(f"\n=== RESULTADO ===")
    print(f"  Escolas processadas: {len(escolas)}")
    print(f"  Memorias criadas: {total_criadas}")
    print(f"  (Ja existentes foram ignoradas via idempotencia.)")

    # Total final
    try:
        r_final = db.client.table("conversation_memory").select("id", count="exact").execute()
        print(f"\n  Total geral na tabela: {r_final.count}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
