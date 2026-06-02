-- Migration: audience_type + data_profile em message_templates
-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel
-- ==================================================

-- Statement 1
ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS audience_type VARCHAR(20);

-- Statement 2
ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS data_profile VARCHAR(20);

