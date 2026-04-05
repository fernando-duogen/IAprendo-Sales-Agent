"""
Migration 004: Sync State - Controle de sincronizacao bidirecional com HubSpot
- Cria tabela sync_state para armazenar timestamp do ultimo pull
- Permite que o agente puxe apenas mudancas incrementais desde o ultimo sync
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.supabase_client import db
from utils.logger import logger


MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS sync_state (
        id SERIAL PRIMARY KEY,
        source VARCHAR(50) NOT NULL UNIQUE,
        last_sync_at TIMESTAMP WITH TIME ZONE,
        last_status VARCHAR(20),
        last_error TEXT,
        records_updated INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,

    """
    CREATE INDEX IF NOT EXISTS idx_sync_state_source ON sync_state(source);
    """,

    """
    COMMENT ON TABLE sync_state IS 'Estado de sincronizacao com sistemas externos (HubSpot, etc). Armazena timestamp do ultimo pull.';
    """,
]


def run():
    """Aplica a migration."""
    logger.info("Iniciando migration 004: sync_state")
    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            db.client.rpc("exec_sql", {"query": sql}).execute()
            logger.info(f"Migration 004 step {i}/{len(MIGRATIONS)} OK")
        except Exception as e:
            # Fallback: tentar via query direta (se RPC nao disponivel)
            try:
                db.client.postgrest.schema("public").rpc("exec", {"sql": sql}).execute()
            except Exception:
                logger.warning(
                    f"Migration 004 step {i} falhou via RPC. Execute manualmente no Supabase SQL Editor:\n{sql}"
                )
    logger.info("Migration 004 concluida")


if __name__ == "__main__":
    run()
