"""
inspect_db.py - Inspeciona o estado atual do banco de dados.
Util para debugging e monitoramento.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from database.supabase_client import db
from approval_queue import queue_manager


def inspect():
    print("=" * 60)
    print("IAprendo Sales Agent - Estado do Banco")
    print("=" * 60)

    # Companies
    result = db.client.table("companies").select("status").execute()
    status_counts = {}
    for r in result.data:
        s = r.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    print(chr(10) + "ESCOLAS:")
    for s, count in sorted(status_counts.items()):
        print(f"  {s}: {count}")
    print(f"  TOTAL: {len(result.data)}")

    # Approval Queue
    stats = queue_manager.get_stats()
    print(chr(10) + "APPROVAL QUEUE:")
    for s, count in sorted(stats.items()):
        print(f"  {s}: {count}")
    total_q = sum(stats.values())
    print(f"  TOTAL: {total_q}")

    # Contacts
    contacts = db.client.table("contacts").select("id", count="exact").execute()
    print(chr(10) + f"CONTATOS: {contacts.count or len(contacts.data)}")

    # Interactions
    interactions = db.client.table("interactions").select("type").execute()
    int_counts = {}
    for r in interactions.data:
        t = r.get("type", "unknown")
        int_counts[t] = int_counts.get(t, 0) + 1
    print(chr(10) + "INTERACOES:")
    for t, count in sorted(int_counts.items()):
        print(f"  {t}: {count}")
    print(f"  TOTAL: {len(interactions.data)}")
    print(chr(10) + "=" * 60)


if __name__ == "__main__":
    inspect()