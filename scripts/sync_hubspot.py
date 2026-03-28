"""
sync_hubspot.py - Sincroniza todas as escolas e contatos com o HubSpot.

Uso:
    venv/Scripts/python.exe scripts/sync_hubspot.py                  # sync tudo
    venv/Scripts/python.exe scripts/sync_hubspot.py --only-sent      # sync apenas escolas com emails enviados
    venv/Scripts/python.exe scripts/sync_hubspot.py --company "NOME" # sync escola especifica
"""
import sys
import time
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.supabase_client import db
from integrations.hubspot_sync import hubspot_sync


def sync_all(only_sent: bool = False, company_name: str = None) -> None:
    if not hubspot_sync.enabled:
        print("HubSpot nao esta habilitado. Verifique HUBSPOT_API_KEY no .env")
        return

    print("=== Sync HubSpot ===\n")

    # Selecionar escolas
    sent_contact_ids = set()  # contatos que receberam email (para sync --only-sent)
    if company_name:
        companies = db.client.table("companies").select("*").ilike("name", f"%{company_name}%").execute().data or []
        print(f"Buscando escolas com nome '{company_name}': {len(companies)} encontrada(s)")
    elif only_sent:
        sent = db.client.table("approval_queue").select("company_id,contact_id").eq("status", "sent").execute().data or []
        sent_ids = list(set(s["company_id"] for s in sent))
        sent_contact_ids = set(s["contact_id"] for s in sent if s.get("contact_id"))
        companies = []
        for cid in sent_ids:
            c = db.get_company_detail(cid)
            if c:
                companies.append(c)
        print(f"Escolas com emails enviados: {len(companies)}")
    else:
        companies = db.client.table("companies").select("*").execute().data or []
        print(f"Total de escolas: {len(companies)}")

    if not companies:
        print("Nenhuma escola para sincronizar.")
        return

    synced_companies = 0
    synced_contacts = 0
    synced_deals = 0
    errors = 0

    for i, company in enumerate(companies):
        name = company.get("name", "?")
        print(f"\n[{i+1}/{len(companies)}] {name}")

        # 1. Sync company
        result = hubspot_sync.sync_company(company)
        if result["success"]:
            print(f"  Company: {result['action']} (ID: {result['hubspot_id']})")
            synced_companies += 1
        else:
            print(f"  Company: FALHOU")
            errors += 1
            time.sleep(1)
            continue

        # Recarregar para pegar hubspot_company_id
        company = db.get_company_detail(company["id"]) or company
        hs_company_id = company.get("hubspot_company_id")

        # 2. Sync contacts (apenas os relevantes)
        contacts = db.get_contacts_by_company(company["id"])
        if only_sent and sent_contact_ids:
            # Sync apenas contatos que receberam email
            contacts_to_sync = [ct for ct in contacts if ct.get("id") in sent_contact_ids]
        else:
            # Sync apenas contatos com email
            contacts_to_sync = [ct for ct in contacts if ct.get("email")]

        for ct in contacts_to_sync:
            ct_result = hubspot_sync.sync_contact(ct, hs_company_id)
            if ct_result["success"]:
                print(f"  Contact: {ct.get('full_name', '?')} ({ct_result['action']})")
                synced_contacts += 1
            time.sleep(0.5)

        # 3. Create deal
        if not company.get("hubspot_deal_id"):
            best_contact = contacts_to_sync[0] if contacts_to_sync else (contacts[0] if contacts else None)
            deal_result = hubspot_sync.create_deal(company, best_contact)
            if deal_result["success"]:
                print(f"  Deal: criado (ID: {deal_result['hubspot_deal_id']})")
                synced_deals += 1

        # Rate limiting
        time.sleep(1)

    print(f"\n=== Sync concluido ===")
    print(f"Companies: {synced_companies} | Contacts: {synced_contacts} | Deals: {synced_deals} | Erros: {errors}")


if __name__ == "__main__":
    only_sent = "--only-sent" in sys.argv
    company_name = None
    if "--company" in sys.argv:
        idx = sys.argv.index("--company")
        if idx + 1 < len(sys.argv):
            company_name = sys.argv[idx + 1]

    sync_all(only_sent=only_sent, company_name=company_name)
