-- Migration: adicionar companies.phone_whatsapp
-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel
-- ==================================================

-- Statement 1
ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone_whatsapp VARCHAR(50);

-- Statement 2
CREATE INDEX IF NOT EXISTS idx_companies_phone_whatsapp ON companies(phone_whatsapp) WHERE phone_whatsapp IS NOT NULL;

