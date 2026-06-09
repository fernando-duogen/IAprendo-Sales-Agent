"""
backup_crm.py - Backup diario das tabelas do CRM -> Supabase Storage (bucket
privado 'backups'). Rodado pela GitHub Action .github/workflows/backup.yml.

Standalone: so precisa do pacote `supabase`. Le SUPABASE_URL + SUPABASE_KEY
(a chave service_role) do ambiente (GitHub Secrets na Action; .env no local).

Pre-requisito (1x): criar no Supabase um bucket **PRIVADO** chamado 'backups'
(Storage -> New bucket -> Public = OFF). O script tenta criar best-effort.

Restauracao: baixe o JSON do bucket; cada chave em 'tables' e a lista de linhas
daquela tabela (re-inserir via upsert por id/inep_code se precisar).
"""
import os
import sys
import json
from datetime import datetime, timezone

from supabase import create_client

# Local: carrega .env (na GitHub Action o env vem dos Secrets; aqui o import
# pode nem existir e tudo bem).
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Tabelas com dados de negocio/PII que importam num backup.
TABLES = [
    "companies", "contacts", "interactions", "approval_queue",
    "message_templates", "meetings", "campaigns",
]
BUCKET = "backups"


def _fetch_all(client, table):
    """Pagina a tabela inteira (PostgREST limita ~1000 por request)."""
    rows, start, page = [], 0, 1000
    while True:
        r = (client.table(table).select("*")
             .order("id").range(start, start + page - 1).execute())
        batch = r.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        print("ERRO: SUPABASE_URL/SUPABASE_KEY ausentes "
              "(configure nos GitHub Secrets do repo).")
        sys.exit(1)

    client = create_client(url, key)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dump = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "tables": {}}
    counts = {}

    print(f"== Backup CRM {stamp} ==")
    for t in TABLES:
        try:
            rows = _fetch_all(client, t)
            dump["tables"][t] = rows
            counts[t] = len(rows)
            print(f"  {t}: {len(rows)} linhas")
        except Exception as e:
            dump["tables"][t] = {"error": str(e)[:300]}
            counts[t] = -1
            print(f"  {t}: ERRO {str(e)[:120]}")

    payload = json.dumps(dump, ensure_ascii=False, default=str).encode("utf-8")
    path = f"crm/backup_{stamp}.json"  # 1 por dia (re-run no mesmo dia sobrescreve)

    # Bucket privado (best-effort; se ja existe, ignora)
    try:
        client.storage.create_bucket(BUCKET, options={"public": False})
        print(f"  bucket privado '{BUCKET}' criado.")
    except Exception:
        pass

    try:
        client.storage.from_(BUCKET).upload(
            path=path, file=payload,
            file_options={"content-type": "application/json", "upsert": "true"},
        )
    except Exception as e:
        print(f"ERRO no upload: {str(e)[:200]}")
        print("Crie o bucket PRIVADO 'backups' no Supabase (Storage) e rode de novo.")
        sys.exit(1)

    print(f"OK -> {BUCKET}/{path} ({len(payload):,} bytes) | {counts}")


if __name__ == "__main__":
    main()
