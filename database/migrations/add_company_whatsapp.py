"""
Migration - Adiciona phone_whatsapp em companies.

Separar celular/WhatsApp do telefone fixo da escola, espelhando o que
ja existe em contacts.phone_whatsapp. Fallback usado em
workflows/send_approved.py e na tool enviar_whatsapp_escola do IAlex
quando nenhum contato da escola tem celular cadastrado.

Idempotente: pode rodar varias vezes (IF NOT EXISTS).

Usage:
    python database/migrations/add_company_whatsapp.py
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.supabase_client import db


ALTER_COMPANIES_SQL = [
    """ALTER TABLE companies ADD COLUMN IF NOT EXISTS phone_whatsapp VARCHAR(50)""",
    """CREATE INDEX IF NOT EXISTS idx_companies_phone_whatsapp ON companies(phone_whatsapp) WHERE phone_whatsapp IS NOT NULL""",
]


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
            return False
        print(f"   WARN: {desc} -> {e}")
        return False


def run_migration() -> None:
    print("=" * 60)
    print("Migration - companies.phone_whatsapp")
    print("=" * 60)
    print()

    sql_file = ROOT_DIR / "database" / "migrations" / "add_company_whatsapp.sql"
    header = (
        "-- Migration: adicionar companies.phone_whatsapp\n"
        "-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel\n"
        "-- " + "=" * 50 + "\n\n"
    )
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(header)
        for i, sql in enumerate(ALTER_COMPANIES_SQL, 1):
            f.write(f"-- Statement {i}\n")
            f.write(sql.strip() + ";\n\n")
    print(f"SQL salvo em: {sql_file}")
    print()

    print("[1/1] Alterando tabela companies...")
    manual_needed = False
    for sql in ALTER_COMPANIES_SQL:
        if not _exec_sql(sql, sql.strip()[:80] + "..."):
            manual_needed = True

    if manual_needed:
        print()
        print("   ACAO NECESSARIA: Execute o SQL manualmente no Supabase SQL Editor.")
        print(f"   Arquivo: {sql_file}")
        print()

    print()
    print("=" * 60)
    print("Migration concluida!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
