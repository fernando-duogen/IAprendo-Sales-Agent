"""
Migration - Adiciona audience_type + data_profile em message_templates.

Habilita a selecao automatica de template por "alvo":
- audience_type: 'nominal' | 'generico' | NULL (qualquer)
- data_profile:  'ambos' | 'matriculas' | 'enem' | 'nenhum' | NULL (qualquer)

Nullable = wildcard (retrocompat total — templates antigos continuam validos).

Idempotente (IF NOT EXISTS).

Usage:
    python database/migrations/add_template_selector_cols.py
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.supabase_client import db


ALTER_SQL = [
    "ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS audience_type VARCHAR(20)",
    "ALTER TABLE message_templates ADD COLUMN IF NOT EXISTS data_profile VARCHAR(20)",
]


def _exec_sql(sql: str, desc: str) -> bool:
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
    print("Migration - message_templates.audience_type + data_profile")
    print("=" * 60)
    print()

    sql_file = ROOT_DIR / "database" / "migrations" / "add_template_selector_cols.sql"
    header = (
        "-- Migration: audience_type + data_profile em message_templates\n"
        "-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel\n"
        "-- " + "=" * 50 + "\n\n"
    )
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(header)
        for i, sql in enumerate(ALTER_SQL, 1):
            f.write(f"-- Statement {i}\n{sql.strip()};\n\n")
    print(f"SQL salvo em: {sql_file}\n")

    print("[1/1] Alterando message_templates...")
    manual = False
    for sql in ALTER_SQL:
        if not _exec_sql(sql, sql.strip()[:70] + "..."):
            manual = True

    if manual:
        print("\n   ACAO NECESSARIA: rode o SQL manualmente no Supabase SQL Editor.")
        print(f"   Arquivo: {sql_file}\n")

    print("\n" + "=" * 60)
    print("Migration concluida!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
