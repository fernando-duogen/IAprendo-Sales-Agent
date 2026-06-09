"""
Setup HubSpot - Cria custom properties, grupo e pipeline no HubSpot.

Executar UMA VEZ antes de usar a integracao:
  venv/Scripts/python.exe scripts/setup_hubspot_properties.py

Idempotente: pode rodar multiplas vezes sem duplicar (properties ja existentes sao ignoradas).
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from integrations.hubspot_client import hubspot_client


def setup() -> None:
    if not hubspot_client._enabled:
        print("HUBSPOT_API_KEY nao configurada no .env. Abortando.")
        return

    print("=== Setup HubSpot para IAprendo ===\n")

    # -----------------------------------------------------------------
    # 1. Grupo de propriedades customizadas (requer scope extra)
    # -----------------------------------------------------------------
    print("1. Tentando criar grupo de propriedades 'iaprendo'...")
    group_ok = True
    for obj_type in ["companies", "contacts", "deals"]:
        if not hubspot_client.create_property_group(obj_type, "iaprendo", "IAprendo"):
            group_ok = False
    if group_ok:
        print("   OK\n")
    else:
        print("   Pulado (requer scope crm.schemas.*.write no Private App)")
        print("   Properties serao criadas no grupo padrao.\n")

    # -----------------------------------------------------------------
    # 2. Custom properties em Companies
    # -----------------------------------------------------------------
    print("2. Criando propriedades em Companies...")
    company_props = [
        {"name": "inep_code", "label": "Codigo INEP", "prop_type": "string", "field_type": "text"},
        {"name": "iaprendo_score", "label": "Score IAprendo", "prop_type": "number", "field_type": "number"},
        {"name": "iaprendo_status", "label": "Status IAprendo", "prop_type": "enumeration", "field_type": "select",
         "options": [
             {"label": "Novo", "value": "raw"},
             {"label": "Qualificado", "value": "qualified"},
             {"label": "Enriquecido", "value": "enriched"},
             {"label": "Contatado", "value": "contacted"},
             {"label": "Respondeu", "value": "responded"},
             {"label": "Convertido", "value": "converted"},
             {"label": "Descartado", "value": "rejected"},
         ]},
        {"name": "iaprendo_priority", "label": "Prioridade IAprendo", "prop_type": "enumeration", "field_type": "select",
         "options": [
             {"label": "Alta", "value": "alta"},
             {"label": "Media", "value": "media"},
             {"label": "Baixa", "value": "baixa"},
         ]},
    ]
    for prop in company_props:
        opts = prop.pop("options", None)
        ok = hubspot_client.create_property("companies", options=opts, **prop)
        status = "OK" if ok else "FALHOU"
        print(f"   {prop['name']}: {status}")
    print()

    # -----------------------------------------------------------------
    # 3. Custom properties em Contacts
    # -----------------------------------------------------------------
    print("3. Criando propriedades em Contacts...")
    contact_props = [
        {"name": "decision_maker_type", "label": "Tipo de Decisor", "prop_type": "enumeration", "field_type": "select",
         "options": [
             {"label": "Diretor(a)", "value": "diretor"},
             {"label": "Vice-Diretor(a)", "value": "vice"},
             {"label": "Coord. Pedagogico(a)", "value": "coordenador"},
             {"label": "Gestor(a) TI", "value": "gestor_ti"},
             {"label": "Outro", "value": "outro"},
         ]},
        {"name": "outreach_priority", "label": "Prioridade de Contato", "prop_type": "number", "field_type": "number"},
    ]
    for prop in contact_props:
        opts = prop.pop("options", None)
        ok = hubspot_client.create_property("contacts", options=opts, **prop)
        status = "OK" if ok else "FALHOU"
        print(f"   {prop['name']}: {status}")
    print()

    # -----------------------------------------------------------------
    # 4. Custom properties em Deals
    # -----------------------------------------------------------------
    print("4. Criando propriedades em Deals...")
    deal_props = [
        {"name": "iaprendo_score", "label": "Score IAprendo", "prop_type": "number", "field_type": "number"},
    ]
    for prop in deal_props:
        ok = hubspot_client.create_property("deals", **prop)
        status = "OK" if ok else "FALHOU"
        print(f"   {prop['name']}: {status}")
    print()

    # -----------------------------------------------------------------
    # 5. Pipeline de Deals — esquema PT no UNICO pipeline (free tier = 1)
    # -----------------------------------------------------------------
    print("5. Configurando pipeline de Deals (esquema PT)...")
    from config.settings import settings
    pipeline_name = getattr(settings, "HUBSPOT_PIPELINE_NAME", "IAprendo Sales")

    # O free tier do HubSpot permite SO 1 pipeline de deals ("You have reached
    # your limit of 1 deal pipelines"), entao NAO criamos um "IAprendo Sales"
    # separado: renomeamos o pipeline default + seus 7 stages pro esquema PT,
    # casando por STAGE ID (estavel, independe de label/locale). Os labels
    # resultantes batem 1:1 com STAGE_MAP/LABEL_TO_STAGE (utils/stage_sync.py).
    # Idempotente: roda quantas vezes quiser.
    DEFAULT_STAGE_TO_PT = {
        "appointmentscheduled":  "Prospectado",
        "qualifiedtobuy":        "Contatado",
        "presentationscheduled": "Respondeu",
        "decisionmakerboughtin": "Reuniao Agendada",
        "contractsent":          "Proposta Enviada",
        "closedwon":             "Convertido",
        "closedlost":            "Perdido",
    }

    pipelines = hubspot_client.get_deal_pipelines()
    if not pipelines:
        print("   Nenhum pipeline de deals encontrado — nada a configurar.")
    else:
        # Alvo: por nome configurado, senao o unico/primeiro.
        target = next((p for p in pipelines if p["label"] == pipeline_name), None) or pipelines[0]
        pid = target["id"]
        print(f"   Pipeline alvo: '{target['label']}' (ID: {pid})")

        # Renomear o pipeline pro nome configurado (best-effort, cosmetico).
        if target["label"] != pipeline_name:
            ok = hubspot_client.update_deal_pipeline_label(pid, pipeline_name)
            print(f"   Renomear pipeline -> '{pipeline_name}': {'OK' if ok else 'NAO PERMITIDO/SKIP'}")

        # Renomear stages pro esquema PT (por stage ID). Preserva display_order e
        # metadata (isClosed/probability dos closed stages).
        renamed = 0
        unknown = []
        for s in sorted(target["stages"], key=lambda x: x["display_order"]):
            pt = DEFAULT_STAGE_TO_PT.get(s["id"])
            if pt is None:
                unknown.append((s["id"], s["label"]))
                continue
            if s["label"] == pt:
                continue  # ja PT (idempotente)
            ok = hubspot_client.update_pipeline_stage_label(
                pid, s["id"], pt, display_order=s["display_order"], metadata=s.get("metadata"),
            )
            print(f"     {s['label']!r} -> {pt!r}: {'OK' if ok else 'FALHOU'}")
            if ok:
                renamed += 1
        if renamed == 0:
            print("   Stages ja no esquema PT (nada a renomear).")
        if unknown:
            # Pipeline nao-default (stage IDs fora do mapa) — nao mexer por ID.
            print(f"   {len(unknown)} stage(s) fora do mapa default (ignorados): {unknown}")

        # Estado final
        final = next((p for p in hubspot_client.get_deal_pipelines() if p["id"] == pid), target)
        print("   Stages atuais:")
        for s in sorted(final["stages"], key=lambda x: x["display_order"]):
            print(f"     {s['display_order']}. {s['label']} (ID: {s['id']})")
    print()

    # -----------------------------------------------------------------
    # Resumo
    # -----------------------------------------------------------------
    print("=== Setup concluido ===")
    print("Proximo passo: rode o pipeline normalmente. As escolas serao sincronizadas automaticamente.")


if __name__ == "__main__":
    setup()
