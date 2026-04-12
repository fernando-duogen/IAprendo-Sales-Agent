"""
Generate APLICAR-015-SCHOOL-ANALYTICS.sql from the JSON report produced by
inspect_enem_csv.py.

Creates:
  - school_analytics table keyed on inep_code (VARCHAR 20 UNIQUE NOT NULL)
  - Foreign-key company_id UUID NULLABLE REFERENCES companies(id)
  - All analytical columns (enem_*, peer_*, socio_*, pnt_*) with inferred types
  - enem_media_geral_sem_redacao GENERATED column (Scenario A only)
  - Partial indexes for P1/P2/P3 ranking queries
  - COMMENTs flagging sensitive pnt_* fields (blocked from LLM at whitelist level)
  - updated_at trigger reusing update_updated_at_column() from schemas.sql

Usage:
    python scripts/generate_migration_015.py
    python scripts/generate_migration_015.py --report scripts/enem_schema_report.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSON = ROOT / "scripts" / "enem_schema_report.json"
DEFAULT_SQL = ROOT / "database" / "migrations" / "APLICAR-015-SCHOOL-ANALYTICS.sql"

HEADER = """-- Migration 015: school_analytics (dados ENEM, peer group, socio e pnt)
-- =====================================================================
-- Cria tabela lateral para dados analiticos do CSV enriquecido (vintage 2024).
-- Chave natural: inep_code. company_id NULLABLE por design:
--   - 185k escolas no CSV vs ~88 em companies hoje
--   - Analytics existe para TODAS as escolas do Brasil
--   - company_id preenchido quando a escola foi importada para companies
--     (pelo import_school_analytics.py ou ao rodar importar_escola no IAlex)
--
-- Precedentes:
--   - schemas.sql (funcao update_updated_at_column ja definida)
--   - migrations 010, 013: padrao ALTER TABLE IF NOT EXISTS
--
-- APLICAR: Execute TUDO no Supabase SQL Editor de uma so vez.
-- =====================================================================
"""

BODY_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS school_analytics (
    -- Identidade
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inep_code VARCHAR(20) UNIQUE NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,

    -- Metadata (rastreabilidade de vintage)
    vintage_enem SMALLINT NOT NULL DEFAULT 2024,
    source_file TEXT NOT NULL DEFAULT 'escolas_brasil_enriquecido.csv',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

FOOTER_INDEXES_SCENARIO_A = """
-- =====================================================================
-- Coluna computada (Cenario A): media_geral SEM redacao
-- =====================================================================
-- Calculada como (cn + ch + lc + mt) / 4. Armazenada (STORED) para usar
-- em indices e filtros. Permite a tool analisar_dados_analytics responder
-- perguntas "com redacao" vs "sem redacao" na hora.
ALTER TABLE school_analytics
    ADD COLUMN IF NOT EXISTS enem_media_geral_sem_redacao NUMERIC(14,4)
    GENERATED ALWAYS AS (
        CASE
            WHEN enem_media_cn IS NOT NULL AND enem_media_ch IS NOT NULL
             AND enem_media_lc IS NOT NULL AND enem_media_mt IS NOT NULL
            THEN (enem_media_cn + enem_media_ch + enem_media_lc + enem_media_mt) / 4.0
            ELSE NULL
        END
    ) STORED;
"""

FOOTER_INDEXES = """
-- =====================================================================
-- Indices para P1/P2/P3 ranking queries
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_sa_inep
    ON school_analytics(inep_code);

CREATE INDEX IF NOT EXISTS idx_sa_company
    ON school_analytics(company_id)
    WHERE company_id IS NOT NULL;

-- Parcial: so amostra confiavel para ranking individual (regra 1 do IAlex)
CREATE INDEX IF NOT EXISTS idx_sa_p1_filter
    ON school_analytics(enem_potencial_melhoria, peer_trajetoria_5y, enem_presentes)
    WHERE enem_amostra_confiavel = TRUE;

-- Parcial: P2/P3 privada por trajetoria
CREATE INDEX IF NOT EXISTS idx_sa_p2_p3
    ON school_analytics(enem_dependencia, peer_trajetoria_5y)
    WHERE enem_amostra_confiavel = TRUE;

-- Gap ordenavel
CREATE INDEX IF NOT EXISTS idx_sa_gap
    ON school_analytics(enem_gap_vs_peer_2024)
    WHERE enem_gap_vs_peer_2024 IS NOT NULL;

-- Dependencia para aggregation rapida
CREATE INDEX IF NOT EXISTS idx_sa_dependencia
    ON school_analytics(enem_dependencia)
    WHERE enem_amostra_confiavel = TRUE;

-- =====================================================================
-- Trigger updated_at (reusa funcao ja existente em schemas.sql)
-- =====================================================================
DROP TRIGGER IF EXISTS update_school_analytics_updated_at ON school_analytics;
CREATE TRIGGER update_school_analytics_updated_at
    BEFORE UPDATE ON school_analytics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================
-- Comments (documentacao inline no schema)
-- =====================================================================
COMMENT ON TABLE school_analytics IS
    'Dados analiticos ENEM por escola (vintage 2024). Chave natural: inep_code. '
    'company_id NULLABLE, preenchido quando a escola esta em companies. '
    'Importado de data/raw/escolas_brasil_enriquecido.csv via import_school_analytics.py.';

COMMENT ON COLUMN school_analytics.enem_amostra_confiavel IS
    'CRITICO: se FALSE, nenhum ranking/media individual da escola pode ser '
    'mencionado em emails ou analises (regra 1 do IAlex). Gate em 4 camadas: '
    'schema (comment), handler (strip), helper (return None), prompt (rule).';

COMMENT ON COLUMN school_analytics.peer_trajetoria_5y IS
    'Trajetoria do GRUPO DE PARES (escolas mesmo municipio x mesma dependencia), '
    'NUNCA da escola individual. Formulacao obrigatoria: "suas concorrentes '
    'diretas em [municipio] vem [trajetoria]".';

COMMENT ON COLUMN school_analytics.enem_media_geral IS
    'Media geral oficial do ENEM (COM redacao, media das 5 provas).';

COMMENT ON COLUMN school_analytics.enem_media_geral_sem_redacao IS
    'Media das 4 areas do conhecimento SEM considerar redacao (cn+ch+lc+mt)/4. '
    'Usada para isolar desempenho cognitivo do peso da escrita.';
"""


def sql_comment_for(col_name: str, is_blocked: bool, is_safe_pnt: bool) -> str:
    """Return a COMMENT ON COLUMN statement for sensitive fields."""
    if is_blocked:
        return (
            f"COMMENT ON COLUMN school_analytics.{col_name} IS\n"
            f"    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics "
            f"e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no "
            f"schema para integridade do import e auditoria interna.';\n"
        )
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default=str(DEFAULT_JSON))
    parser.add_argument("--out", default=str(DEFAULT_SQL))
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"ERRO: relatorio nao encontrado em {report_path}. "
              f"Rode inspect_enem_csv.py primeiro.", file=sys.stderr)
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)

    scenario = report["scenario"]
    cols = report["analytical_columns"]

    if scenario == "unknown":
        print("ERRO: cenario desconhecido no relatorio. Inspecione manualmente.",
              file=sys.stderr)
        sys.exit(1)

    # Split by group for ordered output
    groups_order = ["enem", "peer", "socio", "pnt"]
    grouped = {g: [c for c in cols if c["group"] == g] for g in groups_order}

    lines = [HEADER, BODY_CREATE_TABLE, "\n-- Adicionar colunas analiticas\n"]

    for group in groups_order:
        lines.append(f"-- --- {group}_* ({len(grouped[group])} colunas) ---")
        for col in grouped[group]:
            name = col["name"]
            sql_type = col["sql_type"]
            note = ""
            if col.get("blocked_from_llm"):
                note = "  -- SENSIVEL: bloqueado na whitelist"
            elif col.get("safe_pnt"):
                note = "  -- seguro para uso analitico"
            elif col.get("quality_note"):
                note = f"  -- {col['quality_note']}"
            lines.append(
                f"ALTER TABLE school_analytics "
                f"ADD COLUMN IF NOT EXISTS {name} {sql_type};{note}"
            )
        lines.append("")

    # Scenario A: computed column
    if scenario == "A":
        lines.append(FOOTER_INDEXES_SCENARIO_A)

    lines.append(FOOTER_INDEXES)

    # Sensitive comments
    lines.append("\n-- --- Comments em campos sensiveis (pnt_*) ---")
    for col in cols:
        comment = sql_comment_for(
            col["name"],
            col.get("blocked_from_llm", False),
            col.get("safe_pnt", False),
        )
        if comment:
            lines.append(comment)

    lines.append(
        "\n-- =====================================================================\n"
        "-- FIM DA MIGRATION 015\n"
        "-- =====================================================================\n"
        "-- Proximos passos:\n"
        "--   1. Rodar import_school_analytics.py --sample 1000 --dry-run\n"
        "--   2. Rodar import_school_analytics.py --sample 1000\n"
        "--   3. Spot check via SQL\n"
        "--   4. Rodar import_school_analytics.py (full)\n"
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Migration 015 gerada: {out_path}")
    print(f"  Scenario: {scenario}")
    print(f"  Total de ALTER TABLE: {sum(len(g) for g in grouped.values())}")
    print(f"  Tamanho: {out_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
