-- ENEM 2025: adiciona as colunas novas em school_analytics + indices de Disk IO
-- Aplicar 1x no SQL Editor da Supabase. Idempotente (IF NOT EXISTS).
-- Aditivo: NAO altera/apaga dados existentes (2024 fica intacto).

-- 31 colunas novas (do CSV enriquecido 2025) --
ALTER TABLE school_analytics
  ADD COLUMN IF NOT EXISTS enem_classificacao TEXT,
  ADD COLUMN IF NOT EXISTS enem_gap_vs_peer_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS enem_percentil_nacional NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS enem_rank_dependencia SMALLINT,
  ADD COLUMN IF NOT EXISTS enem_rank_nacional SMALLINT,
  ADD COLUMN IF NOT EXISTS peer_delta_media_geral_2020_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_delta_media_geral_2022_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_delta_presentes_2020_2025 SMALLINT,
  ADD COLUMN IF NOT EXISTS peer_media_ch_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_media_cn_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_media_geral_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_media_lc_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_media_mt_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_media_redacao_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_pct_acima_500_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_pct_acima_600_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_pct_acima_700_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_pct_evolucao_alunos_2020_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_presentes_2025 SMALLINT,
  ADD COLUMN IF NOT EXISTS peer_redacao_pct_problemas_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_slope_media_geral_6y NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS peer_trajetoria_5y_ref TEXT,
  ADD COLUMN IF NOT EXISTS peer_trajetoria_6y TEXT,
  ADD COLUMN IF NOT EXISTS socio_delta_pais_superior_2020_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_delta_renda_2020_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_pct_evolucao_volume_2020_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_pct_pais_superior_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_pct_renda_acima_7sm_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_pct_renda_ate_1sm_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_renda_idx_media_2025 NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS socio_total_inscritos_2025 INTEGER;

-- Indices p/ cortar Disk IO (benchmark do radar + trend de matriculas) --
CREATE INDEX IF NOT EXISTS idx_sc_yearly_city_vintage
  ON school_censo_yearly (city, vintage_censo);
CREATE INDEX IF NOT EXISTS idx_sa_mun_dep
  ON school_analytics (peer_mun_nome, enem_dependencia)
  WHERE enem_amostra_confiavel = true;
