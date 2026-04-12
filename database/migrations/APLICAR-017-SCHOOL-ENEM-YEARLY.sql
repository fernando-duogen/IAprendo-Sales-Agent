-- Migration 017: school_enem_yearly (serie historica individual ENEM)
-- =====================================================================
-- Tabela pre-criada para receber dados historicos do ENEM por escola
-- a partir de 2025 em diante.
--
-- CONTEXTO (LEIA):
--   Microdados ENEM publicos 2020-2023 FORAM ANONIMIZADOS pelo INEP
--   (removeram CO_ESCOLA). Nao e' tecnicamente possivel gerar serie
--   historica individual pra essas vintages com dados publicos.
--
--   A partir de 2024, o INEP voltou a liberar CO_ESCOLA via arquivo
--   separado (RESULTADOS_2024.csv). O snapshot 2024 ja esta em
--   school_analytics. Esta tabela recebe 2024 como primeira vintage
--   e cresce a cada ENEM novo (2025, 2026...).
--
--   Como popular inicialmente:
--     - Vintage 2024: copiar de school_analytics (seed script)
--     - Vintage 2025+: quando sair o ENEM 2025, rodar o mesmo pipeline
--       do Cowork adaptado (01_aggregate_resultados.py + 03_merge_and_enrich.py)
--       e inserir na tabela com vintage_enem=2025
--
-- Schema similar ao school_censo_yearly para consistencia de consultas:
-- 1 linha por (inep_code, vintage_enem).
--
-- APLICAR: Execute no Supabase SQL Editor
-- =====================================================================

CREATE TABLE IF NOT EXISTS school_enem_yearly (
    -- Identidade
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inep_code VARCHAR(20) NOT NULL,
    vintage_enem SMALLINT NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,

    -- Amostra e qualidade
    enem_amostra_confiavel BOOLEAN,
    enem_inscritos INTEGER,
    enem_presentes INTEGER,
    enem_taxa_presenca NUMERIC(8,4),
    enem_dependencia TEXT,

    -- Medias por area (notas do ENEM)
    enem_media_cn NUMERIC(14,4),     -- Ciencias da Natureza
    enem_media_ch NUMERIC(14,4),     -- Ciencias Humanas
    enem_media_lc NUMERIC(14,4),     -- Linguagens e Codigos
    enem_media_mt NUMERIC(14,4),     -- Matematica
    enem_media_redacao NUMERIC(14,4),
    enem_media_geral NUMERIC(14,4),  -- oficial (com redacao)

    -- Derivado: media sem redacao (4 areas cognitivas)
    enem_media_geral_sem_redacao NUMERIC(14,4)
        GENERATED ALWAYS AS (
            CASE
                WHEN enem_media_cn IS NOT NULL AND enem_media_ch IS NOT NULL
                 AND enem_media_lc IS NOT NULL AND enem_media_mt IS NOT NULL
                THEN (enem_media_cn + enem_media_ch + enem_media_lc + enem_media_mt) / 4.0
                ELSE NULL
            END
        ) STORED,

    -- Competencias da redacao (snapshot do ano)
    enem_redacao_comp1_media NUMERIC(14,4),
    enem_redacao_comp2_media NUMERIC(14,4),
    enem_redacao_comp3_media NUMERIC(14,4),
    enem_redacao_comp4_media NUMERIC(14,4),
    enem_redacao_comp5_media NUMERIC(14,4),
    enem_redacao_pct_problemas NUMERIC(8,4),

    -- Area mais fraca e potencial (derivados)
    enem_area_mais_fraca TEXT,
    enem_potencial_melhoria TEXT,    -- Alto / Medio / Baixo

    -- Percentuais de prestigio
    enem_pct_acima_500 NUMERIC(8,4),
    enem_pct_acima_600 NUMERIC(8,4),
    enem_pct_acima_700 NUMERIC(8,4),

    -- Rankings (calculados no pipeline)
    enem_rank_br INTEGER,
    enem_rank_uf INTEGER,
    enem_rank_mun INTEGER,
    enem_rank_uf_dep INTEGER,
    enem_percentil_uf_dep NUMERIC(8,4),
    enem_quartil_br SMALLINT,

    -- Metadata
    source_file TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Chave composta natural
    UNIQUE (inep_code, vintage_enem),
    CONSTRAINT valid_enem_vintage CHECK (vintage_enem BETWEEN 2020 AND 2035)
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_sey_inep
    ON school_enem_yearly(inep_code);

CREATE INDEX IF NOT EXISTS idx_sey_vintage
    ON school_enem_yearly(vintage_enem);

CREATE INDEX IF NOT EXISTS idx_sey_inep_vintage
    ON school_enem_yearly(inep_code, vintage_enem);

CREATE INDEX IF NOT EXISTS idx_sey_confiavel
    ON school_enem_yearly(vintage_enem, enem_amostra_confiavel)
    WHERE enem_amostra_confiavel = TRUE;

-- Trigger
DROP TRIGGER IF EXISTS update_school_enem_yearly_updated_at ON school_enem_yearly;
CREATE TRIGGER update_school_enem_yearly_updated_at
    BEFORE UPDATE ON school_enem_yearly
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE school_enem_yearly IS
    'Serie historica individual por escola de metricas ENEM. Um registro '
    'por (inep_code, vintage_enem). Comeca em 2024 (quando INEP voltou a '
    'liberar CO_ESCOLA) e cresce a cada ENEM novo. Vintages anteriores '
    'a 2024 nao existem (microdados anonimizados).';

COMMENT ON COLUMN school_enem_yearly.enem_amostra_confiavel IS
    'CRITICO: indica se a escola teve presentes suficientes para os '
    'numeros serem estatisticamente validos. Se FALSE, nenhum ranking '
    'ou metrica individual desta linha pode ser exposto em analises.';

COMMENT ON COLUMN school_enem_yearly.enem_media_geral_sem_redacao IS
    'Coluna GENERATED: media das 4 areas cognitivas (cn+ch+lc+mt)/4, '
    'isolando o peso da redacao.';

-- =====================================================================
-- FIM MIGRATION 017
-- =====================================================================
-- Proximos passos:
--   1. Rodar scripts/historico/seed_enem_2024_from_analytics.py
--      (copia school_analytics -> school_enem_yearly com vintage=2024)
--   2. Quando ENEM 2025 sair: rodar o pipeline do Cowork adaptado
--      para produzir um novo parquet e inseri-lo com vintage=2025
