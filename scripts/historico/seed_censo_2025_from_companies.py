"""
Seed school_censo_yearly com vintage=2025 copiando dados que ja estao
em companies (populados pela migration 010 / update_existing_schools.py).

Motivo: o Censo 2025 usa formato multi-arquivo (Tabela_Escola, Tabela_Matricula,
Tabela_Docente, etc), diferente do monolitico usado em 2020-2024. O projeto
ja carregou a versao integrada via escolas_brasil_merged.csv -> companies.
Para manter consistencia, este script copia os campos ja existentes em
companies para school_censo_yearly com vintage=2025.

Ja que so 88 escolas estao em companies (foco: Porto Alegre/RS), so teremos
88 linhas de 2025 no school_censo_yearly. Isso e consistente com o escopo
atual do CRM.

Uso:
    python scripts/historico/seed_censo_2025_from_companies.py
    python scripts/historico/seed_censo_2025_from_companies.py --dry-run
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv()

from database.supabase_client import db
from utils.logger import logger


# Mapeamento: campo em companies -> campo em school_censo_yearly
COMPANY_TO_YEARLY = {
    "inep_code": "inep_code",
    "name": "name",
    "city": "city",
    "state": "state",
    "bairro": "bairro",
    "cep": "cep",
    # Matriculas: o pipeline do Cowork ja agregou em companies
    "total_matriculas": "qt_mat_bas",
    "matriculas_infantil": "qt_mat_inf",
    "matriculas_fundamental": "qt_mat_fund",
    "matriculas_fund_ai": "qt_mat_fund_ai",
    "matriculas_fund_af": "qt_mat_fund_af",
    "matriculas_medio": "qt_mat_med",
    "matriculas_eja": "qt_mat_eja",
    # Equipe
    "total_docentes": "qt_doc_bas",
    # Tech: companies tem nomes friendly
    "tem_internet": "in_internet",
    "internet_alunos": "in_internet_alunos",
    "internet_aprendizagem": "in_internet_aprendizagem",
    "lab_informatica": "in_laboratorio_informatica",
    "qt_desktop_aluno": "qt_desktop_aluno",
    "qt_notebook_aluno": "qt_comp_portatil_aluno",
    "qt_tablet_aluno": "qt_tablet_aluno",
    # Infra
    "tem_biblioteca": "in_biblioteca",
    "tem_quadra": "in_quadra_esportes",
    "tem_lab_ciencias": "in_laboratorio_ciencias",
    "tem_alimentacao": "in_alimentacao",
}

# Mapeamento de dependencia textual -> codigo TP_DEPENDENCIA
DEP_MAP = {
    "Federal": 1,
    "Estadual": 2,
    "Municipal": 3,
    "Privada": 4,
}

# Mapeamento de localizacao
LOC_MAP = {
    "Urbana": 1,
    "Rural": 2,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 72)
    print("SEED Censo 2025 <- companies")
    print("=" * 72)
    print(f"dry_run: {args.dry_run}\n")

    # 1. Carregar todas as companies que tem fonte_dados='censo_2025'
    #    (as do catalogo_inep nao tem dados ricos do Censo)
    cols = (
        "id,inep_code,name,city,state,bairro,cep,admin_dependency,"
        "categoria_privada,localizacao,total_matriculas,matriculas_infantil,"
        "matriculas_fundamental,matriculas_fund_ai,matriculas_fund_af,"
        "matriculas_medio,matriculas_eja,total_docentes,"
        "tem_internet,internet_alunos,internet_aprendizagem,lab_informatica,"
        "qt_desktop_aluno,qt_notebook_aluno,qt_tablet_aluno,"
        "tem_biblioteca,tem_quadra,tem_lab_ciencias,tem_alimentacao"
    )
    print("Buscando companies com fonte_dados='censo_2025'...")
    r = (
        db.client.table("companies")
        .select(cols)
        .eq("fonte_dados", "censo_2025")
        .execute()
    )
    companies = r.data or []
    print(f"  {len(companies)} escolas encontradas\n")

    if not companies:
        print("Nenhuma escola com fonte_dados='censo_2025' em companies.")
        print("Rode update_existing_schools.py primeiro.")
        return

    # 2. Montar records para school_censo_yearly
    records: List[Dict[str, Any]] = []
    for c in companies:
        rec: Dict[str, Any] = {"vintage_censo": 2025, "company_id": c.get("id")}

        # Copiar campos via mapping
        for src, dst in COMPANY_TO_YEARLY.items():
            v = c.get(src)
            if v is not None and v != "":
                rec[dst] = v

        # Traduzir dependencia textual -> codigo
        dep_text = c.get("admin_dependency")
        if dep_text and dep_text in DEP_MAP:
            rec["tp_dependencia"] = DEP_MAP[dep_text]

        # Traduzir localizacao textual -> codigo
        loc_text = c.get("localizacao")
        if loc_text and loc_text in LOC_MAP:
            rec["localizacao"] = LOC_MAP[loc_text]

        # categoria_privada: ja existe como string em companies, converter
        cat = c.get("categoria_privada")
        if cat:
            # tentativa de converter se for numero em string
            try:
                rec["categoria_privada"] = int(cat)
            except (ValueError, TypeError):
                pass

        rec["source_file"] = "companies (censo_2025 snapshot)"
        records.append(rec)

    print(f"Records montados: {len(records)}")
    print(f"Primeiro: inep={records[0].get('inep_code')} "
          f"nome={records[0].get('name')}")
    print()

    if args.dry_run:
        print("*** DRY RUN — nada foi gravado ***")
        print(f"Seriam upsertados {len(records)} records.")
        return

    # 3. Upsert em batches
    print("Upsertando em school_censo_yearly...")
    batch_size = 100
    total_ok = 0
    total_err = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            db.client.table("school_censo_yearly").upsert(
                batch, on_conflict="inep_code,vintage_censo",
            ).execute()
            total_ok += len(batch)
        except Exception as e:
            logger.warning(f"Batch failed: {str(e)[:200]}")
            for rec in batch:
                try:
                    db.client.table("school_censo_yearly").upsert(
                        [rec], on_conflict="inep_code,vintage_censo",
                    ).execute()
                    total_ok += 1
                except Exception as ee:
                    total_err += 1
                    logger.warning(
                        f"Row failed: inep={rec.get('inep_code')} err={str(ee)[:150]}"
                    )

    print(f"\nUpserted: {total_ok} | Errors: {total_err}")
    print("\nVerificacao SQL:")
    print("  SELECT vintage_censo, COUNT(*) FROM school_censo_yearly")
    print("  WHERE vintage_censo=2025 GROUP BY vintage_censo;")


if __name__ == "__main__":
    main()
