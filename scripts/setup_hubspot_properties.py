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
    # 5. Pipeline de Deals
    # -----------------------------------------------------------------
    print("5. Configurando pipeline de Deals...")
    from config.settings import settings
    pipeline_name = getattr(settings, "HUBSPOT_PIPELINE_NAME", "IAprendo Sales")

    # Verificar se ja existe
    pipelines = hubspot_client.get_deal_pipelines()
    existing = next((p for p in pipelines if p["label"] == pipeline_name), None)
    if existing:
        print(f"   Pipeline '{pipeline_name}' ja existe (ID: {existing['id']})")
        print("   Stages:")
        for s in sorted(existing["stages"], key=lambda x: x["display_order"]):
            print(f"     {s['display_order']}. {s['label']} (ID: {s['id']})")
    else:
        stages = [
            {"label": "Prospectado", "display_order": 0, "probability": 0.1},
            {"label": "Email Enviado", "display_order": 1, "probability": 0.2},
            {"label": "Email Aberto", "display_order": 2, "probability": 0.3},
            {"label": "Respondeu", "display_order": 3, "probability": 0.5},
            {"label": "Reuniao Agendada", "display_order": 4, "probability": 0.7},
            {"label": "Convertido", "display_order": 5, "probability": 1.0},
            {"label": "Perdido", "display_order": 6, "probability": 0.0},
        ]
        pipeline_id = hubspot_client.create_deal_pipeline(pipeline_name, stages)
        if pipeline_id:
            print(f"   Pipeline '{pipeline_name}' criado (ID: {pipeline_id})")
        else:
            print(f"   FALHA ao criar pipeline '{pipeline_name}'")
    print()

    # -----------------------------------------------------------------
    # Resumo
    # -----------------------------------------------------------------
    print("=== Setup concluido ===")
    print("Proximo passo: rode o pipeline normalmente. As escolas serao sincronizadas automaticamente.")


if __name__ == "__main__":
    setup()
