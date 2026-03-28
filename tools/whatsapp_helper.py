"""
WhatsApp Helper - Gera links wa.me para contato direto.

Nao envia mensagens diretamente (compliance).
Gera links formatados que podem ser usados no dashboard para
contato manual via WhatsApp Web/App.

Usage:
    from tools.whatsapp_helper import whatsapp_helper

    # Gerar link
    link = whatsapp_helper.generate_wa_link("51999887766", "Ola!")

    # Formatar telefone BR
    phone = whatsapp_helper.format_phone_brazil("(51) 99988-7766")

    # Mensagem pronta para escola
    msg = whatsapp_helper.get_whatsapp_message("Escola ABC", "Maria")

    # Contatos com telefone de uma empresa
    contacts = whatsapp_helper.get_contacts_with_whatsapp("company-uuid")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from database.supabase_client import db
from utils.logger import logger


# ============================================================================
# CONSTANTS
# ============================================================================

WA_BASE_URL: str = "https://wa.me"
MAX_MESSAGE_LENGTH: int = 200
BRAZIL_COUNTRY_CODE: str = "55"


# ============================================================================
# TEMPLATES
# ============================================================================

DEFAULT_TEMPLATE: str = (
    "Ola {contact_name}! Sou da equipe IAprendo. "
    "Gostaria de apresentar nossa plataforma de IA educacional para a {company_name}. "
    "Podemos conversar?"
)

MEETING_TEMPLATE: str = (
    "Ola {contact_name}! Sou da equipe IAprendo. "
    "Posso agendar 15min para mostrar como a IA pode ajudar a {company_name}? "
    "{meeting_link}"
)

SHORT_TEMPLATE: str = (
    "Ola {contact_name}! IAprendo aqui. "
    "Temos uma solucao de IA educacional ideal para a {company_name}. Posso explicar?"
)

TEMPLATES: Dict[str, str] = {
    "default": DEFAULT_TEMPLATE,
    "meeting": MEETING_TEMPLATE,
    "short": SHORT_TEMPLATE,
}


# ============================================================================
# WHATSAPP HELPER
# ============================================================================

class WhatsAppHelper:
    """Gera links wa.me e mensagens para contato via WhatsApp."""

    def __init__(self) -> None:
        """Inicializa helper com link de reuniao do HubSpot."""
        self.meeting_link: str = os.getenv("HUBSPOT_MEETING_LINK", "")

    # ========================================================================
    # PHONE FORMATTING
    # ========================================================================

    def format_phone_brazil(self, phone: str) -> str:
        """
        Formata telefone brasileiro para formato internacional (5551...).

        Args:
            phone: Telefone em qualquer formato BR.
                   Ex: "(51) 99988-7766", "51999887766", "+55 51 99988-7766"

        Returns:
            Telefone no formato 5551999887766 (somente digitos, com DDI+DDD).
        """
        if not phone:
            return ""

        # Remove tudo que nao e digito
        digits: str = re.sub(r"\D", "", phone)

        # Se ja comeca com 55 e tem 12-13 digitos, esta ok
        if digits.startswith("55") and len(digits) in (12, 13):
            return digits

        # Se tem 10-11 digitos (DDD + numero), adiciona 55
        if len(digits) in (10, 11):
            return f"{BRAZIL_COUNTRY_CODE}{digits}"

        # Se tem 8-9 digitos (sem DDD), nao da pra formatar sem DDD
        if len(digits) in (8, 9):
            logger.warning(
                f"Telefone sem DDD, nao e possivel formatar: {phone}"
            )
            return ""

        # Outro caso - retorna como esta (melhor tentar do que nada)
        if len(digits) >= 10:
            return digits

        return ""

    # ========================================================================
    # LINK GENERATION
    # ========================================================================

    def generate_wa_link(self, phone: str, message: str = "") -> str:
        """
        Gera link wa.me com mensagem pre-preenchida.

        Args:
            phone: Telefone (sera formatado automaticamente).
            message: Mensagem pre-preenchida (opcional).

        Returns:
            URL wa.me completa ou string vazia se telefone invalido.
        """
        formatted_phone: str = self.format_phone_brazil(phone)
        if not formatted_phone:
            return ""

        url: str = f"{WA_BASE_URL}/{formatted_phone}"

        if message:
            # Truncar se necessario
            truncated: str = message[:MAX_MESSAGE_LENGTH]
            url = f"{url}?text={quote(truncated)}"

        return url

    # ========================================================================
    # MESSAGE GENERATION
    # ========================================================================

    def get_whatsapp_message(
        self,
        company_name: str,
        contact_name: str,
        template: Optional[str] = None,
    ) -> str:
        """
        Gera mensagem curta para WhatsApp (max 200 chars).

        Args:
            company_name: Nome da escola/empresa.
            contact_name: Nome do contato (primeiro nome).
            template: Nome do template (default, meeting, short).
                      Se None, usa 'meeting' quando meeting_link existe,
                      senao usa 'default'.

        Returns:
            Mensagem formatada, truncada em 200 caracteres.
        """
        if template is None:
            template = "meeting" if self.meeting_link else "default"

        template_str: str = TEMPLATES.get(template, TEMPLATES["default"])

        message: str = template_str.format(
            contact_name=contact_name or "tudo bem",
            company_name=company_name or "sua escola",
            meeting_link=self.meeting_link,
        ).strip()

        # Truncar
        if len(message) > MAX_MESSAGE_LENGTH:
            message = message[: MAX_MESSAGE_LENGTH - 3] + "..."

        return message

    # ========================================================================
    # CONTACTS LOOKUP
    # ========================================================================

    def get_contacts_with_whatsapp(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        """
        Retorna contatos de uma empresa que possuem telefone.

        Args:
            company_id: UUID da empresa.

        Returns:
            Lista de dicts com name, phone, phone_formatted, wa_link.
        """
        contacts: List[Dict[str, Any]] = []

        try:
            result = (
                db.client.table("contacts")
                .select("id, name, phone, role")
                .eq("company_id", company_id)
                .execute()
            )

            if not result.data:
                return contacts

            for contact in result.data:
                phone: str = contact.get("phone") or ""
                if not phone:
                    continue

                formatted: str = self.format_phone_brazil(phone)
                if not formatted:
                    continue

                name: str = contact.get("name", "")
                company_name: str = self._get_company_name(company_id)
                message: str = self.get_whatsapp_message(company_name, name)

                contacts.append({
                    "contact_id": contact.get("id"),
                    "name": name,
                    "role": contact.get("role", ""),
                    "phone": phone,
                    "phone_formatted": formatted,
                    "wa_link": self.generate_wa_link(formatted, message),
                })

        except Exception as e:
            logger.error(
                f"Erro ao buscar contatos com WhatsApp: {e}",
                extra={"company_id": company_id},
            )

        return contacts

    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================

    def _get_company_name(self, company_id: str) -> str:
        """Busca nome da empresa no banco."""
        try:
            result = (
                db.client.table("companies")
                .select("name")
                .eq("id", company_id)
                .single()
                .execute()
            )
            if result.data:
                return result.data.get("name", "")
        except Exception:
            pass
        return ""


# ============================================================================
# SINGLETON
# ============================================================================

whatsapp_helper = WhatsAppHelper()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    # Teste rapido
    print("=== WhatsApp Helper - Teste ===\n")

    test_phones = [
        "(51) 99988-7766",
        "51999887766",
        "+55 51 99988-7766",
        "999887766",
        "",
    ]

    for phone in test_phones:
        formatted = whatsapp_helper.format_phone_brazil(phone)
        print(f"  {phone:25s} -> {formatted}")

    print()
    msg = whatsapp_helper.get_whatsapp_message("Escola Modelo", "Maria")
    print(f"Mensagem ({len(msg)} chars): {msg}")

    link = whatsapp_helper.generate_wa_link("51999887766", msg)
    print(f"Link: {link}")
