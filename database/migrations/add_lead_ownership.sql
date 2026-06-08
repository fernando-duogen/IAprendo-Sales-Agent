-- Migration: ownership de leads + created_by (Fase 2)
-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel
-- ==================================================

-- Statement 1
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100);

-- Statement 2
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_assigned_at TIMESTAMP WITH TIME ZONE;

-- Statement 3
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);

-- Statement 4
ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);

-- Statement 5
CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner_username) WHERE owner_username IS NOT NULL;

