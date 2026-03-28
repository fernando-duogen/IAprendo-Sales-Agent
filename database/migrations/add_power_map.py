"""
Migration 003 - Mapa de Poder (Power Map).

Adiciona colunas ao contacts para classificacao de decisores,
cria tabela message_templates para mensagens padrao,
e migra contatos existentes com classificacao automatica.

Usage:
    python database/migrations/003_add_power_map.py
"""
import sys
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.supabase_client import db
from utils.logger import logger
from utils.role_classifier import classify_role, classify_email_prefix


# SQL Statements
ALTER_CONTACTS_SQL = [
    """ALTER TABLE contacts ADD COLUMN IF NOT EXISTS decision_maker_type VARCHAR(50) DEFAULT 'outro'""",
    """ALTER TABLE contacts ADD COLUMN IF NOT EXISTS outreach_priority INTEGER DEFAULT 99""",
    """ALTER TABLE contacts ADD COLUMN IF NOT EXISTS phone_whatsapp VARCHAR(50)""",
    """CREATE INDEX IF NOT EXISTS idx_contacts_decision_maker ON contacts(company_id, decision_maker_type, outreach_priority)""",
]

CONSTRAINT_SQL = [
    """DO 319 BEGIN
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
END 319""",
    """DO 319 BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
               WHERE constraint_name = 'at_least_one_contact'
               AND table_name = 'contacts') THEN
        ALTER TABLE contacts DROP CONSTRAINT at_least_one_contact;
    END IF;
    ALTER TABLE contacts ADD CONSTRAINT at_least_one_contact
    CHECK (email IS NOT NULL OR phone IS NOT NULL
           OR phone_whatsapp IS NOT NULL OR linkedin_url IS NOT NULL);
END 319""",
]

CREATE_TEMPLATES_SQL = """CREATE TABLE IF NOT EXISTS message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    subject_template VARCHAR(500) NOT NULL,
    body_template TEXT NOT NULL,
    target_role VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
)"""

CREATE_TEMPLATES_IDX = """CREATE INDEX IF NOT EXISTS idx_message_templates_active ON message_templates(is_active, is_default)"""

CREATE_TEMPLATES_TRIGGER = """DO 319 BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'update_message_templates_updated_at') THEN
        CREATE TRIGGER update_message_templates_updated_at
            BEFORE UPDATE ON message_templates
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    END IF;
END 319"""


def _exec_sql(sql: str, desc: str) -> bool:
    """Executa SQL via Supabase. Retorna True se sucesso."""
    try:
        db.client.rpc("exec_sql", {"query": sql}).execute()
        print(f"   OK: {desc}")
        return True
    except Exception as e:
        err = str(e).lower()
        if "already exists" in err or "duplicate" in err:
            print(f"   (ja existe) {desc}")
            return True
        if "could not find" in err or "function" in err:
            # exec_sql nao existe - SQL precisa ser manual
            return False
        print(f"   WARN: {desc} -> {e}")
        return False


def run_migration() -> None:
    """Executa a migration completa."""
    print("=" * 60)
    print("Migration 003 - Mapa de Poder (Power Map)")
    print("=" * 60)
    print()

    all_sql = []
    all_sql.extend(ALTER_CONTACTS_SQL)
    all_sql.extend(CONSTRAINT_SQL)
    all_sql.append(CREATE_TEMPLATES_SQL)
    all_sql.append(CREATE_TEMPLATES_IDX)
    all_sql.append(CREATE_TEMPLATES_TRIGGER)

    # Salvar SQL para execucao manual
    sql_file = ROOT_DIR / "database" / "migrations" / "003_power_map.sql"
    header = "-- Migration 003: Mapa de Poder (Power Map)" + chr(10)
    header += "-- Execute no Supabase SQL Editor" + chr(10)
    header += "-- " + "=" * 50 + chr(10) + chr(10)
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(header)
        for i, sql in enumerate(all_sql, 1):
            f.write(f"-- Statement {i}" + chr(10))
            f.write(sql.strip() + ";" + chr(10) + chr(10))
    print(f"SQL salvo em: {sql_file}")
    print()

    # Tentar executar
    print("[1/3] Alterando tabela contacts...")
    manual_needed = False
    for sql in ALTER_CONTACTS_SQL:
        if not _exec_sql(sql, sql.strip()[:60] + "..."):
            manual_needed = True

    print()
    print("[2/3] Atualizando constraints + criando message_templates...")
    for sql in CONSTRAINT_SQL:
        if not _exec_sql(sql, "constraint"):
            manual_needed = True
    if not _exec_sql(CREATE_TEMPLATES_SQL, "CREATE TABLE message_templates"):
        manual_needed = True
    if not _exec_sql(CREATE_TEMPLATES_IDX, "CREATE INDEX message_templates"):
        manual_needed = True
    if not _exec_sql(CREATE_TEMPLATES_TRIGGER, "CREATE TRIGGER message_templates"):
        manual_needed = True

    if manual_needed:
        print()
        print("   ACAO NECESSARIA: Execute o SQL manualmente no Supabase SQL Editor.")
        print(f"   Arquivo: {sql_file}")
        print()

    # Classificar contatos existentes
    print("[3/3] Classificando contatos existentes...")
    try:
        contacts = db.client.table("contacts").select("id,role,email,source").execute().data or []
        classified = 0
        for contact in contacts:
            role_text = contact.get("role") or ""
            email = contact.get("email") or ""
            source = contact.get("source") or ""

            dm_type, priority = classify_role(role_text)

            # Se cargo generico, tentar pelo prefixo do email
            if dm_type == "outro" and email and "@" in email:
                dm_type2, priority2 = classify_email_prefix(email)
                if dm_type2 != "outro":
                    dm_type, priority = dm_type2, priority2

            # Placeholder sem cargo = assume diretor
            if source == "placeholder" and dm_type == "outro":
                dm_type, priority = "diretor", 1

            try:
                db.client.table("contacts").update({
                    "decision_maker_type": dm_type,
                    "outreach_priority": priority,
                }).eq("id", contact["id"]).execute()
                classified += 1
            except Exception as e:
                print(f"   WARN: {contact['id']}: {e}")

        print(f"   {classified}/{len(contacts)} contatos classificados!")

        # Resumo
        summary = db.client.table("contacts").select("decision_maker_type").execute().data or []
        counts = Counter(c.get("decision_maker_type", "outro") for c in summary)
        print(f"   Distribuicao: {dict(counts)}")

    except Exception as e:
        print(f"   Erro: {e}")

    print()
    print("=" * 60)
    print("Migration 003 concluida!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
