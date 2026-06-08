-- =====================================================================
-- APLICAR TUDO QUE ESTA PENDENTE (consolidado — Junho 2026)
-- =====================================================================
-- Rode este bloco INTEIRO no Supabase (SQL Editor) UMA vez.
-- Eh seguro: todos usam "IF NOT EXISTS" — pode rodar de novo sem problema.
-- 1 execucao cobre o app no Cloud E o local (mesmo banco Supabase).
--
-- O que cada parte habilita:
--   1) WhatsApp da escola (campo separado do telefone fixo)
--   2) Selecao automatica de template por alvo (publico x dados)
--   3) Ownership de leads + autoria (dono da escola, quem fez cada acao,
--      metricas por vendedor, alerta de leads parados)
-- =====================================================================

-- 1) WhatsApp da escola ------------------------------------------------
ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone_whatsapp VARCHAR(50);
CREATE INDEX IF NOT EXISTS idx_companies_phone_whatsapp
    ON companies(phone_whatsapp) WHERE phone_whatsapp IS NOT NULL;

-- 2) Selecao automatica de template por alvo --------------------------
ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS audience_type VARCHAR(20);
ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS data_profile VARCHAR(20);

-- 3) Ownership de leads + atribuicao de autoria -----------------------
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_assigned_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);
ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_companies_owner
    ON companies(owner_username) WHERE owner_username IS NOT NULL;

-- =====================================================================
-- FIM. Se aparecer "Success. No rows returned" = deu tudo certo.
-- =====================================================================
