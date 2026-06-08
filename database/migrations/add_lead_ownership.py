"""
Migration - Ownership de leads + atribuicao de autoria (Fase 2 da auditoria).

Adiciona:
- companies.owner_username        (VARCHAR) — dono do lead (quem trabalha)
- companies.owner_assigned_at     (TIMESTAMP) — quando virou dele
- interactions.created_by         (VARCHAR) — quem registrou a interacao
- approval_queue.created_by       (VARCHAR) — quem gerou a mensagem

Modelo: o dono emerge da ACAO (enviar email / registrar contato) — auto-claim
na 1a acao outbound se a escola nao tiver dono. Sem botao de claim. Admin
reatribui/limpa pra correcao. Tudo nullable = retrocompat total.

Idempotente (IF NOT EXISTS).

Usage:
    python database/migrations/add_lead_ownership.py
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.supabase_client import db


ALTER_SQL = [
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS owner_assigned_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS created_by VARCHAR(100)",
    "ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS created_by VARCHAR(100)",
    "CREATE INDEX IF NOT EXISTS idx_companies_owner ON companies(owner_username) WHERE owner_username IS NOT NULL",
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
    print("Migration - Lead Ownership + Autoria (Fase 2)")
    print("=" * 60)
    print()

    sql_file = ROOT_DIR / "database" / "migrations" / "add_lead_ownership.sql"
    header = (
        "-- Migration: ownership de leads + created_by (Fase 2)\n"
        "-- Execute no Supabase SQL Editor se exec_sql nao estiver disponivel\n"
        "-- " + "=" * 50 + "\n\n"
    )
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(header)
        for i, sql in enumerate(ALTER_SQL, 1):
            f.write(f"-- Statement {i}\n{sql.strip()};\n\n")
    print(f"SQL salvo em: {sql_file}\n")

    print("[1/1] Alterando companies / interactions / approval_queue...")
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
