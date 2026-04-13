"""
Migration 006: Urgency Scores (F2)
- Adiciona colunas urgency_score, urgency_tier, urgency_updated_at em companies
- Cria tabela urgency_score_history para deteccao de tendencias
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.supabase_client import db
from utils.logger import logger


MIGRATIONS = [
    # --- Colunas em companies ---
    """
    ALTER TABLE companies ADD COLUMN IF NOT EXISTS urgency_score INTEGER DEFAULT 0;
    """,
    """
    ALTER TABLE companies ADD COLUMN IF NOT EXISTS urgency_tier VARCHAR(20) DEFAULT 'COLD';
    """,
    """
    ALTER TABLE companies ADD COLUMN IF NOT EXISTS urgency_updated_at TIMESTAMP WITH TIME ZONE;
    """,
    # --- Indice para queries por tier ---
    """
    CREATE INDEX IF NOT EXISTS idx_companies_urgency_tier ON companies(urgency_tier);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_companies_urgency_score ON companies(urgency_score DESC);
    """,
    # --- Tabela de historico ---
    """
    CREATE TABLE IF NOT EXISTS urgency_score_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        urgency_score INTEGER NOT NULL CHECK (urgency_score >= 0 AND urgency_score <= 100),
        urgency_tier VARCHAR(20) NOT NULL CHECK (urgency_tier IN ('CRITICAL', 'HOT', 'WARM', 'COLD')),
        sub_engagement INTEGER DEFAULT 0,
        sub_predictive INTEGER DEFAULT 0,
        sub_intent INTEGER DEFAULT 0,
        sub_enem INTEGER DEFAULT 0,
        weights_used JSONB,
        computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ush_company_time ON urgency_score_history(company_id, computed_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_ush_tier ON urgency_score_history(urgency_tier);
    """,
    """
    COMMENT ON TABLE urgency_score_history IS 'Historico de scores de urgencia para deteccao de tendencias (F2). Cada registro e um snapshot do score unificado com sub-scores.';
    """,
]


def run():
    """Executa migration 006: urgency scores."""
    logger.info("Iniciando migration 006: urgency_scores")
    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            db.client.rpc("exec_sql", {"query": sql}).execute()
            logger.info(f"Migration 006 step {i}/{len(MIGRATIONS)} OK")
        except Exception as e:
            logger.warning(
                f"Migration 006 step {i} via RPC falhou ({e}). "
                f"Execute manualmente no Supabase SQL Editor:\n{sql}"
            )
    logger.info("Migration 006 concluida")


if __name__ == "__main__":
    run()
