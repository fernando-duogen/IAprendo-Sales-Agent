"""
seed_default_template.py - Cria um template padrao de mensagem no banco.

Cria um template exemplo para Fernando personalizar. Pode ser rodado
multiplas vezes sem duplicar (verifica se ja existe).

Uso: python scripts/seed_default_template.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from database.supabase_client import db
from utils.logger import logger


DEFAULT_TEMPLATE = {
    "name": "Primeiro Contato - Geral",
    "subject_template": "IAprendo -- tecnologia educacional para {school_name}",
    "body_template": (
        "Prezado(a) {contact_name},\n"
        "\n"
        "Sou {sender_name}, da IAprendo -- plataforma de tecnologia educacional "
        "100% alinhada a BNCC.\n"
        "\n"
        "Estou entrando em contato porque a {school_name}, em {city}, "
        "trabalha com {education_levels} e acredito que nossa plataforma pode "
        "contribuir significativamente com os resultados dos alunos.\n"
        "\n"
        "Nossos dados (Microsoft e McKinsey) mostram 30% de melhoria no "
        "desempenho dos estudantes que utilizam a plataforma, com 70% maior "
        "retencao do conteudo.\n"
        "\n"
        "Gostaria de agendar uma demonstracao gratuita de 20 minutos para "
        "mostrar como funciona na pratica.\n"
        "\n"
        "{meeting_link_text}\n"
        "\n"
        "Atenciosamente,\n"
        "{sender_name}\n"
        "{sender_email}"
    ),
    "target_role": None,  # Serve para todos os cargos
    "is_active": True,
    "is_default": True,
}


def seed() -> None:
    """Cria template padrao se nao existir."""
    try:
        # Verificar se ja existe
        existing = db.client.table("message_templates").select(
            "id,name"
        ).eq("name", DEFAULT_TEMPLATE["name"]).execute()

        if existing.data:
            print(f"Template '{DEFAULT_TEMPLATE['name']}' ja existe (id: {existing.data[0]['id']})")
            print("Nenhuma alteracao feita.")
            return

        # Inserir
        result = db.client.table("message_templates").insert(DEFAULT_TEMPLATE).execute()
        if result.data:
            template_id = result.data[0]["id"]
            print(f"Template criado com sucesso!")
            print(f"  Nome: {DEFAULT_TEMPLATE['name']}")
            print(f"  ID: {template_id}")
            print(f"  Padrao: Sim")
            print(f"\nEdite o template no dashboard: pagina 'Templates de Mensagem'")
            logger.info("Template padrao criado", extra={"template_id": template_id})
        else:
            print("Erro ao criar template (sem dados retornados)")

    except Exception as e:
        print(f"Erro: {e}")
        logger.error("Erro ao criar template padrao", extra={"error": str(e)})


if __name__ == "__main__":
    seed()
