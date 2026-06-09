-- =====================================================================
-- mec_catalog: policy de LEITURA publica (RLS ja esta ligado)
-- =====================================================================
-- Contexto: add_mec_catalog.sql ligou RLS na mec_catalog. Com RLS ligado e
-- SEM policy, a chave anon (publica) fica BLOQUEADA de ler a tabela. Se o app
-- no Cloud estiver usando a chave anon (em vez de service_role), a busca online
-- veria 0 escolas ("catalogo nao carregado"), mesmo com as 185k carregadas.
--
-- Esta policy libera SELECT pra todos (anon/authenticated/service_role). E
-- seguro: mec_catalog e dado PUBLICO do MEC (so colunas de busca/display).
-- ESCRITA continua restrita (so service_role, que ignora RLS) — nenhuma policy
-- de INSERT/UPDATE/DELETE e criada aqui.
--
-- Rode este bloco no Supabase SQL Editor 1x. Idempotente (DROP IF EXISTS antes).
-- =====================================================================

DROP POLICY IF EXISTS mec_catalog_public_read ON mec_catalog;

CREATE POLICY mec_catalog_public_read
    ON mec_catalog
    FOR SELECT
    USING (true);

-- =====================================================================
-- "Success. No rows returned" = policy criada. A busca online passa a
-- funcionar mesmo que o Cloud use a chave anon.
-- =====================================================================
