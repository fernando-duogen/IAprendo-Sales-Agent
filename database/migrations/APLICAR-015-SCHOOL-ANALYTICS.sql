-- Migration 015: school_analytics (dados ENEM, peer group, socio e pnt)
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


-- Adicionar colunas analiticas

-- --- enem_* (98 colunas) ---
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_inscritos INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_presentes INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_presentes_cn INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_eliminados_cn INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_presentes_ch INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_eliminados_ch INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_presentes_lc INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_eliminados_lc INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_presentes_mt INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_eliminados_mt INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_cn NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_ch NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_lc NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_mt NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_redacao NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_redacao NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_redacao SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_media_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mediana_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_std_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p25_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p75_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_p90_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_max_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_min_geral NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_pct_acima_500 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_pct_acima_600 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_pct_acima_700 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_ok NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_anulada NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_copia NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_em_branco NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_fuga_tema NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_fora_padrao NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_insuficiente NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_desconectada NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_comp1_media NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_comp2_media NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_comp3_media NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_comp4_media NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_comp5_media NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_pct_ingles NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_pct_espanhol NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_dependencia_cod INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_localizacao_cod INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_uf_cod INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_uf_sigla TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mun_cod INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_mun_nome TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_taxa_presenca NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_ano INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_rank_br INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_percentil_br NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_rank_uf INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_percentil_uf NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_rank_mun INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_rank_uf_dep INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_percentil_uf_dep NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_quartil_br INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_area_mais_fraca TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_redacao_pct_problemas NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_amostra_confiavel BOOLEAN;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_potencial_melhoria TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_dependencia TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS enem_gap_vs_peer_2024 NUMERIC(14,4);

-- --- peer_* (63 colunas) ---
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_uf_sigla TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_mun_nome TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_geral_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_geral_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_geral_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_geral_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_geral_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_cn_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_cn_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_cn_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_cn_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_cn_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_ch_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_ch_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_ch_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_ch_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_ch_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_lc_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_lc_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_lc_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_lc_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_lc_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_mt_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_mt_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_mt_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_mt_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_mt_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_redacao_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_redacao_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_redacao_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_redacao_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_media_redacao_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_presentes_2020 SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_presentes_2021 SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_presentes_2022 SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_presentes_2023 SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_presentes_2024 SMALLINT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_delta_media_geral_2020_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_delta_presentes_2020_2024 BIGINT;  -- max=4,294,967,291 exceeds INT32, using BIGINT (likely overflow bug in source)
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_pct_evolucao_alunos_2020_2024 NUMERIC(14,4);  -- has 7 inf values (clamp to NULL at import)
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_delta_media_geral_2022_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_slope_media_geral_ppa NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS peer_trajetoria_5y TEXT;

-- --- socio_* (30 colunas) ---
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_uf TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_mun_nome TEXT;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2020 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2021 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2022 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2023 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_total_inscritos_2020 INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_total_inscritos_2021 INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_total_inscritos_2022 INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_total_inscritos_2023 INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_total_inscritos_2024 INTEGER;
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_delta_renda_2020_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_delta_pais_superior_2020_2024 NUMERIC(14,4);
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS socio_pct_evolucao_volume_2020_2024 NUMERIC(14,4);

-- --- pnt_* (28 colunas) ---
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_total_inscritos INTEGER;  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_treineiros NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_feminino NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_branca NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_preta NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_parda NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_amarela NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_indigena NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_ja_concluiu NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_concluindo NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_ate_18_anos NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_renda_idx_media NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_renda_ate_1sm NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_renda_ate_3sm NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_renda_acima_7sm NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_escol_pais_media NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_pais_superior NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_pais_ate_fund1 NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_ocup_pais_media NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_com_empregada NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_sem_banheiro NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_com_internet NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_com_computador NUMERIC(14,4);  -- SENSIVEL: bloqueado na whitelist
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_so_publica NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_pct_so_privada NUMERIC(14,4);  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_uf TEXT;  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_mun_nome TEXT;  -- seguro para uso analitico
ALTER TABLE school_analytics ADD COLUMN IF NOT EXISTS pnt_ano SMALLINT;  -- seguro para uso analitico


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


-- --- Comments em campos sensiveis (pnt_*) ---
COMMENT ON COLUMN school_analytics.pnt_pct_feminino IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_branca IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_preta IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_parda IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_amarela IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_indigena IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_com_empregada IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_sem_banheiro IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_com_internet IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';

COMMENT ON COLUMN school_analytics.pnt_pct_com_computador IS
    'SENSIVEL: campo bloqueado na whitelist de analisar_dados_analytics e na UI. Nao usar em emails, analises ou pitches comerciais. Mantido no schema para integridade do import e auditoria interna.';


-- =====================================================================
-- FIM DA MIGRATION 015
-- =====================================================================
-- Proximos passos:
--   1. Rodar import_school_analytics.py --sample 1000 --dry-run
--   2. Rodar import_school_analytics.py --sample 1000
--   3. Spot check via SQL
--   4. Rodar import_school_analytics.py (full)
