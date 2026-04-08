-- Migration 007: Templates de follow-up por tipo comportamental
-- Adiciona campo target_type à tabela message_templates para diferenciar
-- templates de email inicial vs follow-ups (hot_click, curious_open, etc.)
--
-- APLICAR: Execute este SQL no Supabase SQL Editor

ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS target_type VARCHAR(50) DEFAULT 'initial';

COMMENT ON COLUMN message_templates.target_type IS 'Tipo alvo: initial (email inicial), follow_up_hot_click, follow_up_curious_open, follow_up_silent_open, follow_up_revival';

-- Templates existentes permanecem como 'initial' (default)
