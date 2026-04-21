"""
Migration 007: Learned Skills (F6 - Fase 2)
- Cria tabela learned_skills para IAlex salvar padroes aprovados pelo Fernando
- Quando Fernando diz "padroniza isso", IAlex salva o padrao como skill reutilizavel
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.supabase_client import db
from utils.logger import logger


MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS learned_skills (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(200) NOT NULL,
        description TEXT,
        skill_type VARCHAR(30) NOT NULL CHECK (skill_type IN (
            'email_template', 'report_format', 'analysis_pattern',
            'response_style', 'whatsapp_template', 'other'
        )),
        trigger_pattern TEXT,
        template_content TEXT NOT NULL,
        example_input TEXT,
        example_output TEXT,
        applies_to JSONB DEFAULT '{}',
        metrics JSONB DEFAULT '{"times_used": 0, "success_count": 0, "last_used": null}',
        status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'draft', 'archived')),
        created_by VARCHAR(50) DEFAULT 'fernando',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_learned_skills_type ON learned_skills(skill_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_learned_skills_status ON learned_skills(status);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_learned_skills_name ON learned_skills(name);
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_learned_skills_unique_name
        ON learned_skills(name) WHERE status != 'archived';
    """,
    """
    COMMENT ON TABLE learned_skills IS 'Skills/modelos aprendidos pelo IAlex a partir de padroes aprovados pelo Fernando (F6 Fase 2). Reutilizados para manter consistencia em respostas similares.';
    """,
]


def run():
    """Executa migration 007: learned_skills."""
    logger.info("Iniciando migration 007: learned_skills")
    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            db.client.rpc("exec_sql", {"query": sql}).execute()
            logger.info(f"Migration 007 step {i}/{len(MIGRATIONS)} OK")
        except Exception as e:
            logger.warning(
                f"Migration 007 step {i} via RPC falhou ({e}). "
                f"Execute manualmente no Supabase SQL Editor:\n{sql}"
            )
    logger.info("Migration 007 concluida")


if __name__ == "__main__":
    run()
