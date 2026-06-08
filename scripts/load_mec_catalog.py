"""
load_mec_catalog.py - Carrega o CSV do MEC (80MB, ~185k escolas) para a
tabela leve `mec_catalog` no Supabase, tornando a base PESQUISAVEL ONLINE
(Cloud) sem depender do arquivo local.

Pre-requisito: rodar `database/migrations/add_mec_catalog.sql` no Supabase 1x
(cria a tabela). Depois, rode ESTE script no PC local (que tem o CSV):

    venv\\Scripts\\python.exe scripts\\load_mec_catalog.py

Idempotente: usa upsert por inep_code (rodar de novo atualiza, nao duplica).
Quando a base MEC for atualizada (anual), rode de novo.
"""
import sys
import math
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from config.settings import settings
from database.supabase_client import db

CSV_PATH = ROOT / settings.CSV_PATH
BATCH = 500


def _norm(s) -> str:
    if not isinstance(s, str):
        return ""
    return (unicodedata.normalize("NFKD", s).encode("ASCII", "ignore")
            .decode("ASCII").lower().strip())


def _txt(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "nan":
        return None
    return s


def _num(v):
    try:
        if v is None:
            return None
        if isinstance(v, float) and math.isnan(v):
            return None
        s = str(v).strip().replace(",", ".")
        if not s or s.lower() == "nan":
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


def _float(v):
    try:
        if v is None:
            return None
        s = str(v).strip().replace(",", ".")
        if not s or s.lower() == "nan":
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _row_to_catalog(r) -> dict:
    inep = _txt(r.get("CODIGO_INEP"))
    if not inep:
        return None
    name = _txt(r.get("NOME_ESCOLA")) or ""
    city = _txt(r.get("MUNICIPIO")) or ""
    levels = _txt(r.get("PERFIL_ENSINO"))
    return {
        "inep_code": inep,
        "name": name or None,
        "name_norm": _norm(name),
        "city": city or None,
        "city_norm": _norm(city),
        "state": (_txt(r.get("UF")) or "")[:2] or None,
        "regiao": _txt(r.get("REGIAO")),
        "bairro": _txt(r.get("BAIRRO")),
        "cep": _txt(r.get("CEP")),
        "address": _txt(r.get("ENDERECO")),
        "phone": _txt(r.get("TELEFONE")),
        "latitude": _float(r.get("LATITUDE")),
        "longitude": _float(r.get("LONGITUDE")),
        "admin_category": _txt(r.get("DEPENDENCIA")),
        "admin_dependency": _txt(r.get("DEPENDENCIA")),
        "categoria_privada": _txt(r.get("CATEGORIA_PRIVADA")),
        "school_size": _txt(r.get("PORTE_ESCOLA")),
        "perfil_ensino": levels,
        "education_levels": levels,
        "levels_norm": _norm(levels or ""),
        "localizacao": _txt(r.get("LOCALIZACAO")),
        "nivel_tecnologico": _txt(r.get("NIVEL_TECNOLOGICO")),
        "total_matriculas": _num(r.get("TOTAL_MATRICULAS")),
        "matriculas_fund_af": _num(r.get("MATRICULAS_FUND_AF")),
        "matriculas_medio": _num(r.get("MATRICULAS_MEDIO")),
        "total_docentes": _num(r.get("TOTAL_DOCENTES")),
        "qt_coordenadores": _num(r.get("QT_COORDENADORES")),
        "fonte_dados": _txt(r.get("FONTE_DADOS")),
    }


def main() -> None:
    print("=" * 60)
    print("  Carga do catalogo MEC -> Supabase (mec_catalog)")
    print("=" * 60)
    if not CSV_PATH.exists():
        print(f"[ERRO] CSV nao encontrado: {CSV_PATH}")
        return

    # Sanidade: tabela existe?
    try:
        db.client.table("mec_catalog").select("inep_code").limit(1).execute()
    except Exception as e:
        print("[ERRO] Tabela mec_catalog nao existe. Rode primeiro o SQL:")
        print("       database/migrations/add_mec_catalog.sql (no Supabase SQL Editor)")
        print(f"       Detalhe: {str(e)[:150]}")
        return

    total = 0
    batch = []
    print(f"Lendo {CSV_PATH.name} em lotes de {BATCH}...")
    for chunk in pd.read_csv(CSV_PATH, encoding=settings.CSV_ENCODING,
                             low_memory=False, dtype=str, chunksize=BATCH):
        batch = []
        for _, r in chunk.iterrows():
            rec = _row_to_catalog(r)
            if rec:
                batch.append(rec)
        if batch:
            try:
                db.client.table("mec_catalog").upsert(batch, on_conflict="inep_code").execute()
                total += len(batch)
                if total % 5000 < BATCH:
                    print(f"   {total:,} escolas carregadas...")
            except Exception as e:
                print(f"   [WARN] lote falhou ({len(batch)} linhas): {str(e)[:120]}")

    print("=" * 60)
    print(f"OK — {total:,} escolas no catalogo (mec_catalog).")
    print("A base completa agora e pesquisavel ONLINE (Cloud).")
    print("=" * 60)


if __name__ == "__main__":
    main()
