"""
Migration 005: Conversation Memory
- Cria tabela conversation_memory para o IAlex lembrar de fatos entre sessoes
- Escopos: global (sobre Fernando/negocio), company (sobre uma escola), contact (sobre um contato)
- Permite busca por escopo + texto (preferencias, avisos, insights)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.supabase_client import db
from utils.logger import logger


MIGRATIONS = [
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_scope ON conversation_memory(scope, scope_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_importance ON conversation_memory(importance DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_created ON conversation_memory(created_at DESC);
    """,
    """
    COMMENT ON TABLE conversation_memory IS 'Memoria persistente do IAlex entre sessoes. Guarda fatos, preferencias e avisos sobre escolas, contatos e o negocio em geral.';
    """,
]


def run():
    logger.info("Iniciando migration 005: conversation_memory")
    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            db.client.rpc("exec_sql", {"query": sql}).execute()
            logger.info(f"Migration 005 step {i}/{len(MIGRATIONS)} OK")
        except Exception:
            logger.warning(
                f"Migration 005 step {i} via RPC falhou. Execute manualmente no Supabase SQL Editor:\n{sql}"
            )
    logger.info("Migration 005 concluida")


if __name__ == "__main__":
    run()
