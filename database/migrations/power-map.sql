-- Migration 003: Mapa de Poder (Power Map)
-- Execute no Supabase SQL Editor
-- ==================================================

-- Statement 1
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS decision_maker_type VARCHAR(50) DEFAULT 'outro';

-- Statement 2
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS outreach_priority INTEGER DEFAULT 99;

-- Statement 3
ALTER TABLE contacts ADD COLUMN IF NOT EXISTS phone_whatsapp VARCHAR(50);

-- Statement 4
CREATE INDEX IF NOT EXISTS idx_contacts_decision_maker ON contacts(company_id, decision_maker_type, outreach_priority);

-- Statement 5
DO 319 BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'valid_decision_maker_type'
               AND table_name = 'contacts') THEN
        ALTER TABLE contacts DROP CONSTRAINT valid_decision_maker_type;
    END IF;
    ALTER TABLE contacts ADD CONSTRAINT valid_decision_maker_type
    CHECK (decision_maker_type IN (
        'diretor', 'vice_diretor', 'coordenador_pedagogico',
        'secretaria', 'administrativo', 'outro'
    ));
END 319;

-- Statement 6
DO 319 BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'at_least_one_contact'
               AND table_name = 'contacts') THEN
        ALTER TABLE contacts DROP CONSTRAINT at_least_one_contact;
    END IF;
    ALTER TABLE contacts ADD CONSTRAINT at_least_one_contact
    CHECK (email IS NOT NULL OR phone IS NOT NULL
           OR phone_whatsapp IS NOT NULL OR linkedin_url IS NOT NULL);
END 319;

-- Statement 7
CREATE TABLE IF NOT EXISTS message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    subject_template VARCHAR(500) NOT NULL,
    body_template TEXT NOT NULL,
    target_role VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Statement 8
CREATE INDEX IF NOT EXISTS idx_message_templates_active ON message_templates(is_active, is_default);

-- Statement 9
DO 319 BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_message_templates_updated_at') THEN
        CREATE TRIGGER update_message_templates_updated_at
            BEFORE UPDATE ON message_templates
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END 319;

