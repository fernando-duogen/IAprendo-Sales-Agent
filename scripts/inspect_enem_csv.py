"""
Inspect the enriched ENEM CSV and emit a schema report that drives
generate_migration_015.py.

Groups detected:
  cadastral_* : 78 cadastral MEC columns (already in companies table)
  enem_*      : per-school ENEM 2024 metrics
  peer_*      : 2020-2024 peer group trajectory
  socio_*     : municipal socioeconomic series
  pnt_*       : socioeconomic profile of the school's ENEM takers
                (contains sensitive demographic fields)

Scenario detection:
  A = CSV has per-area columns (enem_media_cn/ch/lc/mt/redacao)
      -> migration creates enem_media_geral_sem_redacao GENERATED column
  B = CSV has only enem_media_geral + redacao competences
      -> migration uses modo_redacao = completo|foco_redacao|qualidade_escrita

Usage:
    python scripts/inspect_enem_csv.py
    python scripts/inspect_enem_csv.py --csv path/to/custom.csv
    python scripts/inspect_enem_csv.py --sample 5000
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

DEFAULT_CSV = ROOT / "data" / "raw" / "escolas_brasil_enriquecido.csv"
DEFAULT_REPORT_TXT = ROOT / "scripts" / "enem_schema_report.txt"
DEFAULT_REPORT_JSON = ROOT / "scripts" / "enem_schema_report.json"

# Cadastral columns that already exist in companies (migration 010) and
# MUST NOT be duplicated in school_analytics.
CADASTRAL_COLS = {
    "CODIGO_INEP", "NOME_ESCOLA", "CNPJ_ESCOLA", "CNPJ_MANTENEDORA",
    "ENDERECO", "BAIRRO", "CEP", "MUNICIPIO", "UF", "REGIAO", "TELEFONE",
    "LATITUDE", "LONGITUDE", "DEPENDENCIA", "CATEGORIA_PRIVADA",
    "LOCALIZACAO", "LOCALIZACAO_DIFERENCIADA", "REGULAMENTACAO",
    "PORTE_ESCOLA", "PERFIL_ENSINO", "NIVEL_TECNOLOGICO",
    "TOTAL_MATRICULAS", "MATRICULAS_INFANTIL", "MATRICULAS_CRECHE",
    "MATRICULAS_PRE", "MATRICULAS_FUNDAMENTAL", "MATRICULAS_FUND_AI",
    "MATRICULAS_FUND_AF", "MAT_1_ANO", "MAT_2_ANO", "MAT_3_ANO",
    "MAT_4_ANO", "MAT_5_ANO", "MAT_6_ANO", "MAT_7_ANO", "MAT_8_ANO",
    "MAT_9_ANO", "MATRICULAS_MEDIO", "MAT_MEDIO_1_ANO", "MAT_MEDIO_2_ANO",
    "MAT_MEDIO_3_ANO", "MAT_MEDIO_4_ANO", "MATRICULAS_EJA",
    "MATRICULAS_PROFISSIONAL", "MATRICULAS_ED_ESPECIAL",
    "MATRICULAS_INTEGRAL", "ALUNOS_POR_DOCENTE", "PERC_INTEGRAL",
    "TOTAL_TURMAS", "TOTAL_DOCENTES", "TOTAL_GESTORES",
    "QT_ADMINISTRATIVOS", "QT_COORDENADORES", "QT_SERVICOS_GERAIS",
    "OFERECE_CRECHE", "OFERECE_PRE_ESCOLA", "OFERECE_FUND_ANOS_INICIAIS",
    "OFERECE_FUND_ANOS_FINAIS", "OFERECE_ENSINO_MEDIO",
    "OFERECE_MEDIO_INTEGRADO", "OFERECE_EJA", "OFERECE_PROFISSIONALIZANTE",
    "OFERECE_EDUCACAO_ESPECIAL", "MEDIACAO_EAD", "TEM_INTERNET",
    "INTERNET_ALUNOS", "INTERNET_APRENDIZAGEM", "BANDA_LARGA",
    "LAB_INFORMATICA", "QT_DESKTOP_ALUNO", "QT_NOTEBOOK_ALUNO",
    "QT_TABLET_ALUNO", "TEM_ALIMENTACAO", "TEM_BIBLIOTECA",
    "TEM_QUADRA_ESPORTES", "TEM_LAB_CIENCIAS",
    "ACESSIBILIDADE_INEXISTENTE", "FONTE_DADOS",
}

# pnt_* fields that are ethically sensitive and must be BLOCKED at the
# tool whitelist layer even though they are imported. Used later by
# generate_migration_015 (for comments) and enem_tools.py (for the
# BLOCKED_FROM_LLM set).
PNT_BLOCKED_FIELDS = {
    # Demographic race
    "pnt_pct_branca", "pnt_pct_preta", "pnt_pct_parda",
    "pnt_pct_amarela", "pnt_pct_indigena",
    # Household infrastructure (classist if used in sales)
    "pnt_pct_com_empregada", "pnt_pct_sem_banheiro",
    "pnt_pct_com_internet", "pnt_pct_com_computador",
    # Gender (no commercial use)
    "pnt_pct_feminino",
}

# pnt_* fields that are safe for analytical use by IAlex (with socio rotulo)
PNT_SAFE_FIELDS = {
    "pnt_total_inscritos", "pnt_pct_treineiros", "pnt_pct_ja_concluiu",
    "pnt_pct_concluindo", "pnt_pct_ate_18_anos", "pnt_renda_idx_media",
    "pnt_pct_renda_ate_1sm", "pnt_pct_renda_ate_3sm",
    "pnt_pct_renda_acima_7sm", "pnt_escol_pais_media",
    "pnt_pct_pais_superior", "pnt_pct_pais_ate_fund1",
    "pnt_ocup_pais_media", "pnt_pct_so_publica", "pnt_pct_so_privada",
    # Metadata (not metrics)
    "pnt_uf", "pnt_mun_nome", "pnt_ano",
}

# Text / categorical enem_* fields (TEXT in SQL, not NUMERIC)
ENEM_TEXT_FIELDS = {
    "enem_uf_sigla", "enem_mun_nome", "enem_area_mais_fraca",
    "enem_potencial_melhoria", "enem_dependencia",
}

# Integer enem_* fields (SMALLINT/INT in SQL)
ENEM_INT_FIELDS = {
    "enem_inscritos", "enem_presentes", "enem_presentes_cn",
    "enem_presentes_ch", "enem_presentes_lc", "enem_presentes_mt",
    "enem_eliminados_cn", "enem_eliminados_ch", "enem_eliminados_lc",
    "enem_eliminados_mt", "enem_rank_br", "enem_rank_uf", "enem_rank_mun",
    "enem_rank_uf_dep", "enem_quartil_br", "enem_ano",
    "enem_dependencia_cod", "enem_localizacao_cod", "enem_uf_cod",
    "enem_mun_cod",
}

# Boolean enem_* fields
ENEM_BOOL_FIELDS = {
    "enem_amostra_confiavel",
}

PEER_TEXT_FIELDS = {
    "peer_uf_sigla", "peer_mun_nome", "peer_trajetoria_5y",
}

SOCIO_TEXT_FIELDS = {
    "socio_uf", "socio_mun_nome",
}

PNT_TEXT_FIELDS = {
    "pnt_uf", "pnt_mun_nome",
}


def classify_column(col: str) -> str:
    """Return the group a column belongs to."""
    if col in CADASTRAL_COLS:
        return "cadastral"
    lc = col.lower()
    if lc.startswith("enem_"):
        return "enem"
    if lc.startswith("peer_"):
        return "peer"
    if lc.startswith("socio_"):
        return "socio"
    if lc.startswith("pnt_"):
        return "pnt"
    return "unknown"


def infer_sql_type(col: str, series: pd.Series) -> tuple:
    """Infer (sql_type, data_quality_note) for a column.

    Handles inf/NaN edge cases properly so pipeline outliers don't push
    the type to TEXT.
    """
    import numpy as np

    # Explicit text fields
    if (col in ENEM_TEXT_FIELDS or col in PEER_TEXT_FIELDS or
            col in SOCIO_TEXT_FIELDS or col in PNT_TEXT_FIELDS):
        return ("TEXT", None)
    if col in ENEM_BOOL_FIELDS:
        return ("BOOLEAN", None)
    if col in ENEM_INT_FIELDS:
        return ("INTEGER", None)

    # Drop NaN for type detection
    non_null = series.dropna()
    if len(non_null) == 0:
        return ("NUMERIC(14,4)", "all null in sample")

    # Try numeric conversion (including inf-detection)
    try:
        numeric = pd.to_numeric(non_null, errors="raise")
        # Separate finite from inf to avoid falsely classifying the column
        finite = numeric[np.isfinite(numeric)]
        has_inf = len(finite) < len(numeric)
        note = None
        if has_inf:
            n_inf = len(numeric) - len(finite)
            note = f"has {n_inf} inf values (clamp to NULL at import)"
        if len(finite) == 0:
            return ("NUMERIC(14,4)", note or "only inf values in sample")

        # All finite values integer-like?
        if (finite == finite.astype("int64")).all():
            max_abs = finite.abs().max()
            if max_abs > 2147483647:
                note = (note + "; " if note else "") + (
                    f"max={int(max_abs):,} exceeds INT32, using BIGINT "
                    "(likely overflow bug in source)"
                )
                return ("BIGINT", note)
            if max_abs <= 32767:
                return ("SMALLINT", note)
            return ("INTEGER", note)

        # Float: NUMERIC(14,4) generous enough for ratios, % and large deltas
        return ("NUMERIC(14,4)", note)
    except (ValueError, TypeError):
        pass

    # Non-numeric: check for boolean-like
    sample_vals = non_null.astype(str).str.lower().str.strip().unique()
    bool_vals = {"true", "false", "sim", "nao", "não", "1", "0",
                 "verdadeiro", "falso"}
    if set(sample_vals).issubset(bool_vals):
        return ("BOOLEAN", None)

    # Default to text
    return ("TEXT", "heterogeneous values, not numeric")


def detect_scenario(columns: list) -> tuple:
    """Return (scenario, details_dict) describing the redacao scenario."""
    area_cols = ["enem_media_cn", "enem_media_ch", "enem_media_lc",
                 "enem_media_mt", "enem_media_redacao"]
    has_all_areas = all(c in columns for c in area_cols)
    has_media_geral = "enem_media_geral" in columns
    has_competencias = all(f"enem_redacao_comp{i}_media" in columns
                           for i in range(1, 6))

    if has_all_areas and has_media_geral:
        return ("A", {
            "label": "CENÁRIO A — áreas separadas disponíveis",
            "has_per_area_scores": True,
            "has_media_geral": True,
            "has_competencias_redacao": has_competencias,
            "supports_modo": ["com", "sem", "ambos"],
            "supports_computed_sem_redacao": True,
        })
    elif has_media_geral and has_competencias:
        return ("B", {
            "label": "CENÁRIO B — só media_geral + competências",
            "has_per_area_scores": False,
            "has_media_geral": True,
            "has_competencias_redacao": True,
            "supports_modo": ["completo", "foco_redacao", "qualidade_escrita"],
            "supports_computed_sem_redacao": False,
        })
    else:
        return ("unknown", {
            "label": "CENÁRIO DESCONHECIDO — nem A nem B",
            "has_per_area_scores": has_all_areas,
            "has_media_geral": has_media_geral,
            "has_competencias_redacao": has_competencias,
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV),
                        help="Path to the enriched CSV")
    parser.add_argument("--sample", type=int, default=10000,
                        help="Rows to sample for type inference")
    parser.add_argument("--report-txt", default=str(DEFAULT_REPORT_TXT))
    parser.add_argument("--report-json", default=str(DEFAULT_REPORT_JSON))
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERRO: CSV nao encontrado em {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Lendo {csv_path} (primeiras {args.sample:,} linhas) ...")
    df = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
        low_memory=False,
        nrows=args.sample,
    )
    total_rows = sum(1 for _ in open(csv_path, "rb")) - 1
    print(f"  Total de linhas no CSV: {total_rows:,}")
    print(f"  Amostra carregada: {len(df):,} linhas, {len(df.columns)} colunas\n")

    # Classify columns
    groups = {"cadastral": [], "enem": [], "peer": [],
              "socio": [], "pnt": [], "unknown": []}
    for col in df.columns:
        groups[classify_column(col)].append(col)

    print("=== Distribuicao por grupo ===")
    for g, cols in groups.items():
        print(f"  {g}: {len(cols)} colunas")
    print()

    # Detect scenario
    scenario, scenario_details = detect_scenario(list(df.columns))
    print(f"=== Deteccao de cenario ===")
    print(f"  {scenario_details['label']}")
    for k, v in scenario_details.items():
        if k != "label":
            print(f"    {k}: {v}")
    print()

    # For each analytical column, compute dtype, null pct, sample values
    analytical_cols = (groups["enem"] + groups["peer"]
                       + groups["socio"] + groups["pnt"])
    col_specs = []
    data_quality_warnings = []
    for col in analytical_cols:
        series = df[col]
        null_pct = 100.0 * series.isna().sum() / len(series)
        sql_type, quality_note = infer_sql_type(col, series)
        samples = series.dropna().head(3).tolist()
        samples_str = [str(x)[:30] for x in samples]

        is_blocked = col in PNT_BLOCKED_FIELDS
        is_safe_pnt = col in PNT_SAFE_FIELDS

        col_specs.append({
            "name": col,
            "group": classify_column(col),
            "sql_type": sql_type,
            "null_pct": round(null_pct, 2),
            "samples": samples_str,
            "blocked_from_llm": is_blocked,
            "safe_pnt": is_safe_pnt,
            "quality_note": quality_note,
        })
        if quality_note:
            data_quality_warnings.append(f"{col}: {quality_note}")

    # Write TXT report
    lines = []
    lines.append("=" * 72)
    lines.append("RELATORIO DE INSPECAO DO CSV ENRIQUECIDO")
    lines.append("=" * 72)
    lines.append(f"Arquivo: {csv_path}")
    lines.append(f"Total de linhas: {total_rows:,}")
    lines.append(f"Amostra analisada: {len(df):,}")
    lines.append(f"Total de colunas: {len(df.columns)}")
    lines.append("")
    lines.append("--- Distribuicao por grupo ---")
    for g, cols in groups.items():
        lines.append(f"  {g:12s}: {len(cols):3d} colunas")
    lines.append("")
    lines.append("--- Deteccao de cenario (com/sem redacao) ---")
    lines.append(f"  Cenario: {scenario}")
    lines.append(f"  Label:   {scenario_details['label']}")
    for k, v in scenario_details.items():
        if k != "label":
            lines.append(f"  {k}: {v}")
    lines.append("")

    lines.append("--- Colunas cadastrais (ja existem em companies, NAO importar) ---")
    for c in sorted(groups["cadastral"]):
        lines.append(f"  {c}")
    lines.append("")

    for group in ("enem", "peer", "socio", "pnt"):
        lines.append(f"--- Colunas {group}_* ({len(groups[group])}) ---")
        for spec in [s for s in col_specs if s["group"] == group]:
            flag = ""
            if spec["blocked_from_llm"]:
                flag = "  [BLOCKED FROM LLM]"
            elif spec["safe_pnt"]:
                flag = "  [SAFE PNT]"
            note = f"  !{spec['quality_note']}" if spec.get("quality_note") else ""
            samples = ", ".join(spec["samples"])
            lines.append(
                f"  {spec['name']:50s} {spec['sql_type']:15s} "
                f"null={spec['null_pct']:5.1f}%  ex=[{samples}]{flag}{note}"
            )
        lines.append("")

    if data_quality_warnings:
        lines.append("--- Avisos de qualidade de dados ---")
        for w in data_quality_warnings:
            lines.append(f"  {w}")
        lines.append("")

    lines.append("--- Colunas desconhecidas (nao classificadas) ---")
    for c in groups["unknown"]:
        lines.append(f"  {c}")
    lines.append("")
    lines.append("=" * 72)
    lines.append("FIM DO RELATORIO")
    lines.append("=" * 72)

    report_txt = "\n".join(lines)
    Path(args.report_txt).write_text(report_txt, encoding="utf-8")
    print(report_txt)
    print(f"\nRelatorio TXT salvo em: {args.report_txt}")

    # Write JSON report (for generate_migration_015.py to consume)
    report_data = {
        "csv_path": str(csv_path),
        "total_rows": total_rows,
        "sample_size": len(df),
        "total_columns": len(df.columns),
        "groups_count": {g: len(cols) for g, cols in groups.items()},
        "cadastral_columns": sorted(groups["cadastral"]),
        "unknown_columns": sorted(groups["unknown"]),
        "scenario": scenario,
        "scenario_details": scenario_details,
        "analytical_columns": col_specs,
        "data_quality_warnings": data_quality_warnings,
        "pnt_blocked_fields": sorted(PNT_BLOCKED_FIELDS),
        "pnt_safe_fields": sorted(PNT_SAFE_FIELDS),
    }
    Path(args.report_json).write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Relatorio JSON salvo em: {args.report_json}")


if __name__ == "__main__":
    main()
