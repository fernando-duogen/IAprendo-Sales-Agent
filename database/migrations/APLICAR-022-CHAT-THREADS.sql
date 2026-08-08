-- =====================================================================
-- APLICAR-022 — Persistencia do Chat IAlex (operador v1, F4)
-- =====================================================================
-- Conversas do chat web sobrevivem a reload/troca de aparelho. Uma LINHA por
-- conversa (thread): o historico OpenAI-fiel vai em `history` (JSONB) e os
-- blocos ricos de render em `blocks` (JSONB, chaveados por hash do reply) —
-- upsert atomico por turno, imune ao trim do historico.
--
-- 100% ADDITIVE: nao altera nenhuma tabela existente. Idempotente.
-- Aplicar no Supabase SQL Editor. O codigo degrada com elegancia se a tabela
-- ainda nao existir (chat funciona so em memoria da sessao).
--
-- RLS: habilitado SEM policy para anon => anon bloqueado; o app usa a chave
-- service_role (BYPASSRLS) e continua funcionando (padrao migration 020).
-- =====================================================================

CREATE TABLE IF NOT EXISTS chat_threads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(50) NOT NULL,
    thread_id   UUID NOT NULL,
    title       TEXT,
    history     JSONB NOT NULL DEFAULT '[]'::jsonb,
    blocks      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chat_threads_user_thread_uniq UNIQUE (username, thread_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_user_updated
    ON chat_threads (username, updated_at DESC);

ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE chat_threads IS
    'Conversas do Chat IAlex (operador v1). 1 linha por thread; history=mensagens OpenAI-fiel; blocks=render ricos por hash de reply.';
COMMENT ON COLUMN chat_threads.history IS
    'Lista de mensagens role/content/tool_calls/tool_call_id (formato OpenAI, snapshot pos-trim).';
COMMENT ON COLUMN chat_threads.blocks IS
    'Mapa {md5(reply)[:16] -> [blocos de render]} paralelo ao history (nunca vai a API).';
