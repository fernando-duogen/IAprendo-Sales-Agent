-- Migration 009: Expandir api_usage para aceitar OpenAI + salvar tokens
--
-- PROBLEMA: CHECK constraint só aceita 'anthropic', 'apollo', etc.
-- 'openai' é rejeitado — NENHUM uso de OpenAI está sendo registrado!
--
-- APLICAR: Execute no Supabase SQL Editor

-- 1. Dropar constraint antiga
ALTER TABLE api_usage DROP CONSTRAINT IF EXISTS valid_api_name;

-- 2. Criar constraint expandida (inclui openai + outros possíveis)
ALTER TABLE api_usage ADD CONSTRAINT valid_api_name
    CHECK (api_name IN ('anthropic', 'openai', 'apollo', 'snov', 'hunter', 'google_maps', 'brevo', 'hubspot', 'perplexity', 'duckduckgo'));

-- 3. Adicionar colunas para tokens (custo preciso)
ALTER TABLE api_usage ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER;
ALTER TABLE api_usage ADD COLUMN IF NOT EXISTS completion_tokens INTEGER;
ALTER TABLE api_usage ADD COLUMN IF NOT EXISTS total_tokens INTEGER;
ALTER TABLE api_usage ADD COLUMN IF NOT EXISTS model VARCHAR(100);
ALTER TABLE api_usage ADD COLUMN IF NOT EXISTS cost_usd DECIMAL(10, 6);

COMMENT ON COLUMN api_usage.prompt_tokens IS 'Tokens de entrada (prompt)';
COMMENT ON COLUMN api_usage.completion_tokens IS 'Tokens de saída (resposta)';
COMMENT ON COLUMN api_usage.total_tokens IS 'Total de tokens';
COMMENT ON COLUMN api_usage.model IS 'Modelo usado (ex: gpt-4.1-mini)';
COMMENT ON COLUMN api_usage.cost_usd IS 'Custo calculado em USD baseado no modelo e tokens';
