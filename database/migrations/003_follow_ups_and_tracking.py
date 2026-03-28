"""
Migration 003: Follow-ups, Tracking e Email Deduction
- Adiciona tabela follow_up_sequences (campanhas de follow-up)
- Adiciona coluna follow_up_number e parent_id na approval_queue
- Adiciona coluna tracking_id na approval_queue (para rastrear aberturas)
- Adiciona coluna email_pattern na companies (para deducao de emails)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.supabase_client import db
from utils.logger import logger


MIGRATIONS = [
    # 1. Tabela de sequencias de follow-up
    """
    CREATE TABLE IF NOT EXISTS follow_up_sequences (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name VARCHAR(200) NOT NULL,
        description TEXT,
        steps JSONB NOT NULL DEFAULT '[]',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """,

    # 2. Colunas de follow-up na approval_queue
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='follow_up_number') THEN
            ALTER TABLE approval_queue ADD COLUMN follow_up_number INTEGER DEFAULT 0;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='parent_id') THEN
            ALTER TABLE approval_queue ADD COLUMN parent_id UUID REFERENCES approval_queue(id) ON DELETE SET NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='tracking_id') THEN
            ALTER TABLE approval_queue ADD COLUMN tracking_id VARCHAR(100);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='brevo_message_id') THEN
            ALTER TABLE approval_queue ADD COLUMN brevo_message_id VARCHAR(200);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='opened_at') THEN
            ALTER TABLE approval_queue ADD COLUMN opened_at TIMESTAMP WITH TIME ZONE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='clicked_at') THEN
            ALTER TABLE approval_queue ADD COLUMN clicked_at TIMESTAMP WITH TIME ZONE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='replied_at') THEN
            ALTER TABLE approval_queue ADD COLUMN replied_at TIMESTAMP WITH TIME ZONE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='bounced_at') THEN
            ALTER TABLE approval_queue ADD COLUMN bounced_at TIMESTAMP WITH TIME ZONE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='approval_queue' AND column_name='sequence_id') THEN
            ALTER TABLE approval_queue ADD COLUMN sequence_id UUID REFERENCES follow_up_sequences(id) ON DELETE SET NULL;
        END IF;
    END $$;
    """,

    # 3. Coluna email_pattern nas companies (para deducao)
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='companies' AND column_name='email_pattern') THEN
            ALTER TABLE companies ADD COLUMN email_pattern VARCHAR(100);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='companies' AND column_name='email_domain') THEN
            ALTER TABLE companies ADD COLUMN email_domain VARCHAR(200);
        END IF;
    END $$;
    """,

    # 4. Coluna email_deduced e deduced_from nos contacts
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='contacts' AND column_name='email_deduced') THEN
            ALTER TABLE contacts ADD COLUMN email_deduced BOOLEAN DEFAULT FALSE;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name='contacts' AND column_name='email_verified_at') THEN
            ALTER TABLE contacts ADD COLUMN email_verified_at TIMESTAMP WITH TIME ZONE;
        END IF;
    END $$;
    """,

    # 5. Indices para performance
    """
    CREATE INDEX IF NOT EXISTS idx_approval_queue_parent ON approval_queue(parent_id);
    CREATE INDEX IF NOT EXISTS idx_approval_queue_follow_up ON approval_queue(follow_up_number);
    CREATE INDEX IF NOT EXISTS idx_approval_queue_tracking ON approval_queue(tracking_id);
    CREATE INDEX IF NOT EXISTS idx_approval_queue_sent_at ON approval_queue(sent_at);
    CREATE INDEX IF NOT EXISTS idx_companies_email_domain ON companies(email_domain);
    """,

    # 6. Inserir sequencia padrao de follow-up
    """
    INSERT INTO follow_up_sequences (name, description, steps, is_active)
    SELECT 'Sequencia Padrao', 'Sequencia padrao de 3 follow-ups',
        '[
            {"step": 1, "days_after": 0, "type": "initial", "label": "Email inicial"},
            {"step": 2, "days_after": 3, "type": "follow_up", "label": "Follow-up 1: Lembrete gentil"},
            {"step": 3, "days_after": 7, "type": "follow_up", "label": "Follow-up 2: Valor adicional"},
            {"step": 4, "days_after": 14, "type": "follow_up", "label": "Follow-up 3: Ultima tentativa"}
        ]'::jsonb, TRUE
    WHERE NOT EXISTS (SELECT 1 FROM follow_up_sequences WHERE name = 'Sequencia Padrao');
    """,
]


def run():
    """Executa todas as migrations."""
    logger.info("Executando migration 003: Follow-ups e Tracking")

    for i, sql in enumerate(MIGRATIONS, 1):
        try:
            db.client.rpc("exec_sql", {"query": sql}).execute()
            logger.info(f"Migration 003 step {i}/{len(MIGRATIONS)}: OK")
        except Exception as e:
            # Tentar via postgrest direto
            try:
                db.client.postgrest.rpc("exec_sql", {"query": sql}).execute()
                logger.info(f"Migration 003 step {i}/{len(MIGRATIONS)}: OK (via postgrest)")
            except Exception:
                logger.warning(f"Migration 003 step {i}: {str(e)[:100]} (pode ja existir)")


if __name__ == "__main__":
    run()
    print("Migration 003 concluida!")
