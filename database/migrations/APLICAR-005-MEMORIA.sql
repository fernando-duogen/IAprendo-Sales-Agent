-- ============================================================================
-- Migration 005: Conversation Memory
-- Aplicar manualmente no Supabase SQL Editor
-- (https://supabase.com/dashboard/project/vgmvpghwkeirnjdbjcwl/sql/new)
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope VARCHAR(20) NOT NULL CHECK (scope IN ('global', 'company', 'contact')),
    scope_id UUID,
    category VARCHAR(30) DEFAULT 'fact' CHECK (category IN ('fact', 'preference', 'insight', 'warning', 'reminder')),
    content TEXT NOT NULL,
    importance INTEGER DEFAULT 5 CHECK (importance BETWEEN 1 AND 10),
    source VARCHAR(20) DEFAULT 'ialex' CHECK (source IN ('ialex', 'fernando', 'auto')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    use_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_memory_scope ON conversation_memory(scope, scope_id);
CREATE INDEX IF NOT EXISTS idx_memory_importance ON conversation_memory(importance DESC);
CREATE INDEX IF NOT EXISTS idx_memory_created ON conversation_memory(created_at DESC);

COMMENT ON TABLE conversation_memory IS 'Memoria persistente do IAlex entre sessoes. Guarda fatos, preferencias e avisos sobre escolas, contatos e o negocio em geral.';

-- Opcional: Habilitar RLS (Row Level Security) se usar autenticacao
-- ALTER TABLE conversation_memory ENABLE ROW LEVEL SECURITY;
