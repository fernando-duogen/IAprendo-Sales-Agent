"""
Atualiza as escolas existentes no banco com dados da base MESCLADA
(Censo 2025 + Catalogo INEP). NAO apaga nada — apenas preenche colunas novas.

A base mesclada cobre:
- 180.540 escolas do Censo 2025 (dados ricos: matriculas, equipe, tech)
- 4.739 escolas do Catalogo INEP que nao foram ao Censo (dados basicos)

Escolas do Censo ganham fonte_dados='censo_2025' e todos os campos ricos.
Escolas do Catalogo ganham fonte_dados='catalogo_inep' com campos basicos.

Pre-requisitos:
- migration 010 (APLICAR-010-NOVA-BASE-2025.sql) aplicada
- migration 011 (APLICAR-011-FONTE-DADOS.sql) aplicada
- merge_catalogo_inep.py ja rodado (gera escolas_brasil_merged.csv)

Usage:
    python database/migrations/update_existing_schools.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from database.supabase_client import db
from utils.logger import logger

# Usa base mesclada (Censo 2025 + Catalogo INEP exclusivas)
CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "raw", "escolas_brasil_merged.csv"
)
# Fallback para Censo puro se merged ainda nao existir
if not os.path.exists(CSV_PATH):
    CSV_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data", "raw", "escolas_brasil_crm.csv"
    )

# Mapeamento CSV → banco
COLUMN_MAP = {
    "REGIAO": "regiao",
    "BAIRRO": "bairro",
    "CEP": "cep",
    "CNPJ_ESCOLA": "cnpj_escola",
    "CNPJ_MANTENEDORA": "cnpj_mantenedora",
    "CATEGORIA_PRIVADA": "categoria_privada",
    "LOCALIZACAO": "localizacao",
    "REGULAMENTACAO": "regulamentacao",
    "PERFIL_ENSINO": "perfil_ensino",
    "NIVEL_TECNOLOGICO": "nivel_tecnologico",
    "TOTAL_MATRICULAS": "total_matriculas",
    "MATRICULAS_INFANTIL": "matriculas_infantil",
    "MATRICULAS_FUNDAMENTAL": "matriculas_fundamental",
    "MATRICULAS_FUND_AI": "matriculas_fund_ai",
    "MATRICULAS_FUND_AF": "matriculas_fund_af",
    "MATRICULAS_MEDIO": "matriculas_medio",
    "MATRICULAS_INTEGRAL": "matriculas_integral",
    "PERC_INTEGRAL": "perc_integral",
    "MATRICULAS_EJA": "matriculas_eja",
    "MAT_1_ANO": "mat_1_ano",
    "MAT_2_ANO": "mat_2_ano",
    "MAT_3_ANO": "mat_3_ano",
    "MAT_4_ANO": "mat_4_ano",
    "MAT_5_ANO": "mat_5_ano",
    "MAT_6_ANO": "mat_6_ano",
    "MAT_7_ANO": "mat_7_ano",
    "MAT_8_ANO": "mat_8_ano",
    "MAT_9_ANO": "mat_9_ano",
    "MAT_MEDIO_1_ANO": "mat_medio_1",
    "MAT_MEDIO_2_ANO": "mat_medio_2",
    "MAT_MEDIO_3_ANO": "mat_medio_3",
    "TOTAL_DOCENTES": "total_docentes",
    "TOTAL_GESTORES": "total_gestores",
    "QT_COORDENADORES": "qt_coordenadores",
    "QT_ADMINISTRATIVOS": "qt_administrativos",
    "TOTAL_TURMAS": "total_turmas",
    "ALUNOS_POR_DOCENTE": "alunos_por_docente",
    "TEM_INTERNET": "tem_internet",
    "INTERNET_ALUNOS": "internet_alunos",
    "INTERNET_APRENDIZAGEM": "internet_aprendizagem",
    "BANDA_LARGA": "banda_larga",
    "LAB_INFORMATICA": "lab_informatica",
    "QT_DESKTOP_ALUNO": "qt_desktop_aluno",
    "QT_NOTEBOOK_ALUNO": "qt_notebook_aluno",
    "QT_TABLET_ALUNO": "qt_tablet_aluno",
    "TEM_ALIMENTACAO": "tem_alimentacao",
    "TEM_BIBLIOTECA": "tem_biblioteca",
    "TEM_QUADRA_ESPORTES": "tem_quadra",
    "TEM_LAB_CIENCIAS": "tem_lab_ciencias",
    "OFERECE_FUND_ANOS_FINAIS": "oferece_fund_af",
    "OFERECE_ENSINO_MEDIO": "oferece_medio",
    "OFERECE_EJA": "oferece_eja",
    "OFERECE_PROFISSIONALIZANTE": "oferece_profissionalizante",
}

# Campos que devem ser atualizados também (dados básicos que podem ter mudado)
BASIC_UPDATE_MAP = {
    "NOME_ESCOLA": "name",
    "ENDERECO": "address",
    "MUNICIPIO": "city",
    "UF": "state",
    "TELEFONE": "phone",
    "LATITUDE": "latitude",
    "LONGITUDE": "longitude",
    "DEPENDENCIA": "admin_dependency",
    "PORTE_ESCOLA": "school_size",
}

SIM_NAO_FIELDS = {
    "tem_internet", "internet_alunos", "internet_aprendizagem", "banda_larga",
    "lab_informatica", "tem_alimentacao", "tem_biblioteca", "tem_quadra",
    "tem_lab_ciencias", "oferece_fund_af", "oferece_medio", "oferece_eja",
    "oferece_profissionalizante",
}


def _convert_value(db_col: str, value):
    """Converte valor do CSV para formato do banco (Supabase exige tipos Python nativos)."""
    import numpy as np

    if pd.isna(value) or value == "" or value is None:
        return None
    if db_col in SIM_NAO_FIELDS:
        return str(value).strip().lower() == "sim"
    # numpy int -> Python int
    if isinstance(value, (np.integer,)):
        return int(value)
    # numpy float -> Python float/int
    if isinstance(value, (np.floating,)):
        f = float(value)
        return int(f) if f == int(f) else round(f, 2)
    # Python float sem casas decimais -> int
    if isinstance(value, float):
        return int(value) if value == int(value) else round(value, 2)
    # numpy bool -> Python bool
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def main():
    print("=== Atualizacao de escolas existentes com nova base MEC 2025 ===\n")

    if not os.path.exists(CSV_PATH):
        print(f"ERRO: CSV nao encontrado em {CSV_PATH}")
        return

    # Carregar nova base
    print(f"Carregando {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", low_memory=False)
    print(f"  {len(df)} escolas na nova base, {len(df.columns)} colunas")

    # Indexar por INEP para busca rapida
    df["_inep_str"] = df["CODIGO_INEP"].astype(str).str.strip()
    csv_index = df.set_index("_inep_str")

    # Buscar escolas existentes no banco
    existing = db.client.table("companies").select("id,inep_code,name").execute().data or []
    print(f"  {len(existing)} escolas no banco\n")

    updated = 0
    not_found = 0
    errors = 0

    for school in existing:
        inep = str(school.get("inep_code", "")).strip()
        school_id = school["id"]

        if inep not in csv_index.index:
            not_found += 1
            print(f"  SKIP: {inep} ({school.get('name', '?')[:30]}) — nao encontrado na nova base")
            continue

        row = csv_index.loc[inep]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        # Montar update com todas as colunas novas
        update_data = {}

        # Colunas novas
        for csv_col, db_col in COLUMN_MAP.items():
            if csv_col in row.index:
                val = _convert_value(db_col, row[csv_col])
                if val is not None:
                    update_data[db_col] = val

        # Colunas basicas (atualizar se estavam vazias) — usa _convert_value
        # para normalizar numpy -> tipos Python nativos (JSON-safe)
        for csv_col, db_col in BASIC_UPDATE_MAP.items():
            if csv_col in row.index:
                val = _convert_value(db_col, row[csv_col])
                if val is not None:
                    # name/address/city/state/phone devem ser string
                    if db_col in ("name", "address", "city", "state", "phone", "school_size", "admin_dependency"):
                        update_data[db_col] = str(val)
                    else:
                        update_data[db_col] = val

        # Admin category (mapear DEPENDENCIA -> admin_category)
        dep = row.get("DEPENDENCIA", "")
        if dep:
            if "Privada" in str(dep):
                update_data["admin_category"] = "Privada"
            elif "Municipal" in str(dep) or "Estadual" in str(dep) or "Federal" in str(dep):
                update_data["admin_category"] = "Publica"

        # Education levels (mapear PERFIL_ENSINO)
        perfil = row.get("PERFIL_ENSINO", "")
        if perfil and pd.notna(perfil):
            update_data["education_levels"] = str(perfil)

        # Fonte dados (censo_2025 ou catalogo_inep)
        fonte = row.get("FONTE_DADOS", "")
        if fonte and pd.notna(fonte):
            update_data["fonte_dados"] = str(fonte)

        if update_data:
            try:
                db.client.table("companies").update(update_data).eq("id", school_id).execute()
                updated += 1
                if updated % 10 == 0:
                    print(f"  Atualizado: {updated}...")
            except Exception as e:
                errors += 1
                print(f"  ERRO: {inep} — {str(e)[:100]}")

    print(f"\n=== RESULTADO ===")
    print(f"  Atualizadas: {updated}")
    print(f"  Nao encontradas: {not_found}")
    print(f"  Erros: {errors}")

    # Resumo por fonte
    try:
        r_censo = db.client.table("companies").select("id", count="exact").eq("fonte_dados", "censo_2025").execute()
        r_cat = db.client.table("companies").select("id", count="exact").eq("fonte_dados", "catalogo_inep").execute()
        print(f"\n  Por fonte:")
        print(f"    censo_2025: {r_censo.count}")
        print(f"    catalogo_inep: {r_cat.count}")
    except Exception:
        pass

    print(f"\nContatos, emails, memorias e scores NAO foram alterados.")


if __name__ == "__main__":
    main()
