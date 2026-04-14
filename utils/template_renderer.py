"""
template_renderer - Substitui variaveis em templates de mensagem.

Usado pelo WriterAgent no modo 'template' para gerar mensagens
a partir de um modelo padrao escrito pelo Fernando, substituindo
variaveis como {school_name}, {contact_name}, etc.

Funcao pura, sem dependencias externas alem de settings.
"""
from collections import defaultdict
from typing import Dict, Any, Optional


# Variaveis disponiveis e suas descricoes (para exibir no dashboard)
TEMPLATE_VARIABLES: Dict[str, str] = {
    "contact_name": "Nome completo do contato (ex: Maria Silva)",
    "contact_first_name": "Primeiro nome do contato (ex: Maria)",
    "contact_role": "Cargo do contato (ex: Diretora)",
    "school_name": "Nome da escola (ex: Colegio Farroupilha)",
    "city": "Cidade (ex: Porto Alegre)",
    "state": "UF (ex: RS)",
    "education_levels": "Niveis de ensino (ex: Fundamental, Medio)",
    "admin_category": "Categoria administrativa (ex: Privada)",
    "admin_dependency": "Dependencia administrativa (ex: Estadual)",
    "school_size": "Porte da escola (ex: Grande)",
    "score": "Score de qualificacao (ex: 85)",
    "sender_name": "Nome do remetente (config)",
    "sender_email": "Email do remetente (config)",
    "sender_phone": "Telefone do remetente (config)",
    "company_name": "Nome da empresa remetente (config)",
    "meeting_link": "URL do agendamento HubSpot (link cru, ex: https://meetings...)",
    "meeting_link_text": "Texto clicavel para agendamento (ex: 'Agendar conversa com Fernando'). Vira hyperlink no email.",
    "website": "Site da empresa remetente (config)",
    # Graficos e Report (gerados automaticamente ao enviar)
    "chart_radar": "Imagem do radar ENEM (5 areas vs escolas similares). URL publica do PNG.",
    "chart_gap": "Imagem do indicador de diferenca (area mais fraca vs escolas similares). URL publica do PNG.",
    "chart_trend": "Imagem da evolucao de matriculas (variacao % desde 2020). URL publica do PNG.",
    "report_link": "Link do diagnostico completo da escola (One Page Report com dados ENEM + Censo).",
}


def _build_variables(
    company: Dict[str, Any],
    contact: Dict[str, Any],
    sender_settings: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Constroi dicionario de variaveis para substituicao.

    Args:
        company: Dados da escola.
        contact: Dados do contato destinatario.
        sender_settings: Dados do remetente. Se None, carrega de settings.

    Returns:
        Dicionario {nome_variavel: valor_string}.
    """
    if sender_settings is None:
        try:
            from config.settings import settings
            meeting_url = getattr(settings, "HUBSPOT_MEETING_LINK", "")
            meeting_text = getattr(settings, "HUBSPOT_MEETING_LINK_TEXT", "Agendar conversa com Fernando")
            sender_settings = {
                "sender_name": settings.YOUR_NAME,
                "sender_email": settings.YOUR_EMAIL,
                "sender_phone": getattr(settings, "YOUR_PHONE", ""),
                "company_name": getattr(settings, "COMPANY_NAME", "IAprendo"),
                "meeting_link": meeting_url,
                "meeting_link_text": meeting_text,
                "website": getattr(settings, "COMPANY_WEBSITE", getattr(settings, "WEBSITE", "")),
            }
        except Exception:
            sender_settings = {
                "sender_name": "",
                "sender_email": "",
                "sender_phone": "",
                "company_name": "IAprendo",
            }

    full_name = contact.get("full_name") or "Diretor(a)"
    first_name = full_name.split()[0] if full_name and full_name != "Diretor(a)" else "Diretor(a)"

    variables: Dict[str, str] = {
        # Contato
        "contact_name": full_name,
        "contact_first_name": first_name,
        "contact_role": contact.get("role") or "Diretor(a)",
        # Escola
        "school_name": company.get("name", ""),
        "city": company.get("city", ""),
        "state": company.get("state", ""),
        "education_levels": company.get("education_levels", ""),
        "admin_category": company.get("admin_category", ""),
        "admin_dependency": company.get("admin_dependency", ""),
        "school_size": company.get("school_size", ""),
        "score": str(company.get("qualification_score", "")),
        # Remetente
        **sender_settings,
    }

    return variables


def render_template(
    subject_template: str,
    body_template: str,
    company: Dict[str, Any],
    contact: Dict[str, Any],
    sender_settings: Optional[Dict[str, str]] = None,
    extra_variables: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Substitui variaveis {variavel} no template.

    Variaveis nao encontradas ficam como string vazia.
    Usa format_map com defaultdict para evitar KeyError.

    Args:
        subject_template: Template do assunto com {variaveis}.
        body_template: Template do corpo com {variaveis}.
        company: Dados da escola.
        contact: Dados do contato destinatario.
        sender_settings: Dados do remetente (opcional).
        extra_variables: Variaveis extras (chart_radar, chart_gap, chart_trend,
            report_link, etc). Sobrescreve variaveis padrao se houver conflito.

    Returns:
        Dict com 'subject' e 'body' ja renderizados.

    Example:
        >>> result = render_template(
        ...     "Ola {contact_name}",
        ...     "Prezado(a) {contact_first_name}, a {school_name} em {city}...",
        ...     {"name": "Colegio X", "city": "POA"},
        ...     {"full_name": "Maria Silva", "role": "Diretora"},
        ... )
        >>> result["subject"]
        'Ola Maria Silva'
    """
    variables = _build_variables(company, contact, sender_settings)
    if extra_variables:
        variables.update(extra_variables)

    # defaultdict retorna "" para variaveis nao encontradas
    safe_vars = defaultdict(str, variables)

    try:
        subject = subject_template.format_map(safe_vars)
    except (ValueError, KeyError):
        subject = subject_template  # fallback: retorna original

    try:
        body = body_template.format_map(safe_vars)
    except (ValueError, KeyError):
        body = body_template  # fallback: retorna original

    return {"subject": subject, "body": body}
