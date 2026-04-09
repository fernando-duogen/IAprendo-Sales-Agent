-- Migration 011: Adicionar coluna fonte_dados para identificar origem
-- do registro (censo_2025 / catalogo_inep / manual).
--
-- Use case: marcar escolas que vieram do catalogo INEP (nao participaram
-- do Censo 2025) com dados basicos apenas. Permite ao IAlex saber quando
-- dados ricos (matriculas, equipe, tech) nao estao disponiveis.
--
-- APLICAR: Execute no Supabase SQL Editor
-- ============================================================================

ALTER TABLE companies ADD COLUMN IF NOT EXISTS fonte_dados VARCHAR(30);
CREATE INDEX IF NOT EXISTS idx_companies_fonte_dados ON companies(fonte_dados);

COMMENT ON COLUMN companies.fonte_dados IS
  'Origem do registro: censo_2025 (dados ricos completos), catalogo_inep (dados basicos — escola ativa mas sem Censo), manual (cadastro manual).';

-- Marcar registros existentes como censo_2025 (ja foram atualizados em migration 010)
UPDATE companies
SET fonte_dados = 'censo_2025'
WHERE fonte_dados IS NULL
  AND total_matriculas IS NOT NULL;

-- Os registros sem total_matriculas (as 8 escolas que nao estavam no Censo 2025)
-- vao ser marcadas como catalogo_inep quando o script update_existing_schools
-- rodar de novo com a base mesclada.
