"""
test_one_school.py - Testa o pipeline completo para UMA escola.

Uso:
    python scripts/test_one_school.py                        # Pega primeira escola raw
    python scripts/test_one_school.py --status qualified     # Pega primeira qualified
    python scripts/test_one_school.py --name "Farroupilha"   # Busca por nome
    python scripts/test_one_school.py --inep 43000001        # Busca por INEP
    python scripts/test_one_school.py --mode template        # Usa template (sem IA)
    python scripts/test_one_school.py --skip-qualify --skip-enrich  # Pula etapas
"""
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    """Executa pipeline E2E para uma escola."""
    parser = argparse.ArgumentParser(description="Teste E2E do pipeline para uma escola")
    parser.add_argument("--inep", help="Codigo INEP da escola")
    parser.add_argument("--name", help="Nome parcial da escola (busca com ILIKE)")
    parser.add_argument("--status", default="raw", help="Status para buscar (default: raw)")
    parser.add_argument("--mode", default="ai", choices=["ai", "template"],
                        help="Modo de escrita: ai (Claude) ou template (custo zero)")
    parser.add_argument("--skip-qualify", action="store_true", help="Pular qualificacao")
    parser.add_argument("--skip-enrich", action="store_true", help="Pular enriquecimento")
    parser.add_argument("--skip-contacts", action="store_true", help="Pular busca de contatos")
    parser.add_argument("--skip-write", action="store_true", help="Pular geracao de mensagem")
    args = parser.parse_args()

    from database.supabase_client import db

    # =========================================================================
    # 1. SELECIONAR ESCOLA
    # =========================================================================
    print("\n" + "=" * 60)
    print("TESTE E2E - PIPELINE PARA UMA ESCOLA")
    print("=" * 60)

    school = None
    if args.inep:
        print(f"\nBuscando escola por INEP: {args.inep}")
        school = db.get_company_by_inep(args.inep)
    elif args.name:
        print(f"\nBuscando escola por nome: {args.name}")
        try:
            result = db.client.table("companies").select("*").ilike(
                "name", f"%{args.name}%"
            ).limit(1).execute()
            school = result.data[0] if result.data else None
        except Exception as e:
            print(f"   Erro na busca: {e}")
    else:
        print(f"\nBuscando primeira escola com status '{args.status}'...")
        schools = db.get_companies_by_status(args.status, limit=1)
        school = schools[0] if schools else None

    if not school:
        print("\nEscola nao encontrada!")
        if not args.inep and not args.name:
            print(f"Nenhuma escola com status '{args.status}' no banco.")
            print("Tente: --status qualified, --status enriched, ou --name 'parte do nome'")
        sys.exit(1)

    company_id = school["id"]
    print(f"\n{'─' * 50}")
    print(f"  Escola:   {school['name']}")
    print(f"  INEP:     {school.get('inep_code', 'N/A')}")
    print(f"  Status:   {school.get('status', 'N/A')}")
    print(f"  Cidade:   {school.get('city', 'N/A')}, {school.get('state', '')}")
    print(f"  Website:  {school.get('website') or 'Nao encontrado'}")
    print(f"  Score:    {school.get('qualification_score', 'Nao qualificada')}")
    print(f"{'─' * 50}")

    # =========================================================================
    # 2. QUALIFICAR
    # =========================================================================
    if not args.skip_qualify and school.get("status") == "raw":
        print("\n[1/4] Qualificando escola (Claude Haiku)...")
        try:
            from agents.qualifier import QualifierAgent
            qa = QualifierAgent()
            result = qa.execute([school])
            # Recarregar dados
            school = db.client.table("companies").select("*").eq("id", company_id).single().execute().data
            print(f"   Score: {school.get('qualification_score', '?')}/100")
            print(f"   Status: {school.get('status')}")
            reasoning = school.get("qualification_reasoning", "")
            if reasoning:
                print(f"   Raciocinio: {reasoning[:150]}...")
        except Exception as e:
            print(f"   ERRO: {e}")
    else:
        reason = "pulada (--skip-qualify)" if args.skip_qualify else f"pulada (status={school.get('status')})"
        print(f"\n[1/4] Qualificacao {reason}")

    # =========================================================================
    # 3. ENRIQUECER
    # =========================================================================
    if not args.skip_enrich and school.get("status") in ("qualified", "raw") and not school.get("website"):
        print("\n[2/4] Enriquecendo dados (buscando website)...")
        try:
            from agents.enricher import EnricherAgent
            enricher = EnricherAgent()
            result = enricher.execute([school])
            # Recarregar dados
            school = db.client.table("companies").select("*").eq("id", company_id).single().execute().data
            print(f"   Website: {school.get('website') or 'Nao encontrado'}")
            print(f"   Status: {school.get('status')}")
        except Exception as e:
            print(f"   ERRO: {e}")
    else:
        website = school.get("website")
        if website:
            print(f"\n[2/4] Enriquecimento pulado (website ja existe: {website})")
        elif args.skip_enrich:
            print("\n[2/4] Enriquecimento pulado (--skip-enrich)")
        else:
            print(f"\n[2/4] Enriquecimento pulado (status={school.get('status')})")

    # =========================================================================
    # 4. BUSCAR CONTATOS
    # =========================================================================
    contacts = []
    if not args.skip_contacts:
        print("\n[3/4] Buscando decisores (Mapa de Poder)...")
        try:
            from agents.contact_finder import ContactFinderAgent
            cf = ContactFinderAgent()
            contacts = cf.find_contacts(school)
            print(f"   Contatos encontrados: {len(contacts)}")
            print()
            for c in contacts:
                dm = c.get("decision_maker_type", "outro")
                email = c.get("email") or "sem email"
                source = c.get("source", "?")
                name = c.get("full_name", "?")
                print(f"   {'🟢' if c.get('email') else '🔴'} {name} ({dm}) | {email} | fonte: {source}")
        except Exception as e:
            print(f"   ERRO: {e}")
    else:
        print("\n[3/4] Busca de contatos pulada (--skip-contacts)")
        try:
            contacts = db.get_contacts_by_company(company_id) or []
            print(f"   Contatos existentes: {len(contacts)}")
        except Exception:
            pass

    # =========================================================================
    # 5. GERAR MENSAGEM
    # =========================================================================
    if not args.skip_write:
        print(f"\n[4/4] Gerando mensagem (modo: {args.mode})...")
        try:
            from agents.writer import WriterAgent
            writer = WriterAgent()
            results = writer.execute([school], mode=args.mode)
            if results:
                r = results[0]
                print(f"   Queue ID: {r.get('queue_id')}")
                print(f"   Assunto:  {r.get('subject')}")
                print(f"   Preview:  {r.get('body_preview', '')[:200]}")
                if r.get("reasoning"):
                    print(f"   Razao:    {r.get('reasoning')}")
            else:
                print("   Nenhuma mensagem gerada (verifique logs)")
        except Exception as e:
            print(f"   ERRO: {e}")
    else:
        print("\n[4/4] Geracao de mensagem pulada (--skip-write)")

    # =========================================================================
    # 6. RESUMO FINAL
    # =========================================================================
    print("\n" + "=" * 60)
    print("RESUMO FINAL")
    print("=" * 60)

    # Recarregar escola
    try:
        school = db.client.table("companies").select("*").eq("id", company_id).single().execute().data
    except Exception:
        pass

    print(f"\n  Escola: {school.get('name')}")
    print(f"  Status: {school.get('status')}")
    print(f"  Score:  {school.get('qualification_score', 'N/A')}")

    # Contatos
    try:
        all_contacts = db.get_contacts_by_company(company_id) or []
        print(f"\n  Contatos: {len(all_contacts)}")
        directors = [c for c in all_contacts if c.get("decision_maker_type") == "diretor" and c.get("email")]
        if directors:
            print(f"  Diretor com email: {directors[0].get('email')}")
        else:
            print("  Diretor com email: NAO ENCONTRADO")
    except Exception:
        pass

    # Fila de aprovacao
    try:
        queue = db.client.table("approval_queue").select(
            "id,subject,status,sent_at"
        ).eq("company_id", company_id).order("created_at", desc=True).execute().data or []
        print(f"\n  Mensagens na fila: {len(queue)}")
        for q in queue:
            status_icon = {"pending": "⏳", "approved": "✅", "sent": "📨", "rejected": "❌"}.get(q["status"], "?")
            sent = " (enviada)" if q.get("sent_at") else ""
            print(f"    {status_icon} [{q['status']}] {q['subject']}{sent}")
    except Exception:
        pass

    # Proximos passos
    print(f"\n{'─' * 50}")
    print("PROXIMOS PASSOS:")
    print("  1. Abra o dashboard:  streamlit run dashboard/main.py")
    print("  2. Va para 'Fila de Aprovacao'")
    print("  3. Revise e aprove a mensagem")
    print("  4. Envie:  python workflows/send_approved.py")
    print()
    print("Se email nao chegar:")
    print("  python scripts/diagnose_email.py --send-test")
    print("=" * 60)


if __name__ == "__main__":
    main()
