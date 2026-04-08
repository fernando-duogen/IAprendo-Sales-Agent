-- Migration 008: Segurança — Ativar Row-Level Security (RLS) em todas as tabelas
--
-- PROBLEMA: O Supabase alertou que tabelas estão publicamente acessíveis.
-- Qualquer pessoa com a URL do projeto pode ler/editar/deletar dados.
--
-- SOLUÇÃO: Ativar RLS em TODAS as tabelas e criar policy que permite
-- acesso APENAS via service_role key (usada pelo backend Python).
-- A anon key (pública) NÃO terá acesso a nenhuma tabela.
--
-- IMPORTANTE: O IAprendo acessa o banco via service_role key (SUPABASE_KEY no .env),
-- que BYPASS RLS automaticamente. Portanto, o backend continua funcionando
-- normalmente — apenas acesso direto via anon key é bloqueado.
--
-- APLICAR: Execute este SQL COMPLETO no Supabase SQL Editor.
-- ======================================================================

-- 1. Ativar RLS em TODAS as tabelas públicas
ALTER TABLE IF EXISTS companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS approval_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS api_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS sync_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS message_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS conversation_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS follow_up_sequences ENABLE ROW LEVEL SECURITY;

-- 2. Criar policies que permitem TUDO para authenticated users (service_role)
-- Estas policies garantem que o backend Python (service_role) funciona normalmente.
-- A anon key NÃO tem acesso (sem policy = sem acesso quando RLS ativo).

-- companies
CREATE POLICY IF NOT EXISTS "service_role_all_companies" ON companies
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- contacts
CREATE POLICY IF NOT EXISTS "service_role_all_contacts" ON contacts
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- approval_queue
CREATE POLICY IF NOT EXISTS "service_role_all_approval_queue" ON approval_queue
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- interactions
CREATE POLICY IF NOT EXISTS "service_role_all_interactions" ON interactions
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- meetings
CREATE POLICY IF NOT EXISTS "service_role_all_meetings" ON meetings
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- api_usage
CREATE POLICY IF NOT EXISTS "service_role_all_api_usage" ON api_usage
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- campaigns
CREATE POLICY IF NOT EXISTS "service_role_all_campaigns" ON campaigns
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- sync_state
CREATE POLICY IF NOT EXISTS "service_role_all_sync_state" ON sync_state
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- message_templates
CREATE POLICY IF NOT EXISTS "service_role_all_message_templates" ON message_templates
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- conversation_memory
CREATE POLICY IF NOT EXISTS "service_role_all_conversation_memory" ON conversation_memory
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- follow_up_sequences
CREATE POLICY IF NOT EXISTS "service_role_all_follow_up_sequences" ON follow_up_sequences
    FOR ALL USING (auth.role() = 'authenticated' OR auth.role() = 'service_role');

-- 3. Verificar que a SUPABASE_KEY no .env é a service_role key (NÃO a anon key)
-- A service_role key começa com "eyJhbGciOiJIUzI1NiIs..." e tem "role":"service_role" no payload.
-- Se estiver usando anon key, o backend vai parar de funcionar após ativar RLS.
-- Para verificar: no painel Supabase → Settings → API → copie a service_role key.

-- ======================================================================
-- APÓS APLICAR:
-- 1. Verifique se o backend continua funcionando: curl localhost:5001/health
-- 2. Verifique no Supabase → Database → Tables → cada tabela deve mostrar "RLS enabled"
-- 3. O alerta de segurança do Supabase deve desaparecer em alguns minutos
-- ======================================================================
