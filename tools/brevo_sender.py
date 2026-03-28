"""
BrevoSender - Envio de emails via API Brevo.

CRITICO: So envia mensagens com status approved na approval_queue.
Nunca envia mensagem sem aprovacao humana previa.
"""
import requests
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import logger


class BrevoSender:
    """Envia emails via Brevo API (300/dia no plano gratuito)."""

    BASE_URL = "https://api.brevo.com/v3"

    def __init__(self) -> None:
        self.api_key = settings.BREVO_API_KEY if hasattr(settings, "BREVO_API_KEY") else ""
        # Usa BREVO_SENDER_EMAIL se configurado (deve ser um sender verificado no Brevo)
        # Fallback para YOUR_EMAIL se nao configurado
        self.from_email = os.getenv("BREVO_SENDER_EMAIL") or settings.YOUR_EMAIL
        self.from_name = os.getenv("BREVO_SENDER_NAME") or settings.YOUR_NAME
        self._enabled = bool(self.api_key)
        if not self._enabled:
            logger.warning("BREVO_API_KEY nao configurada - envio desabilitado")

    def send_email(self, to_email: str, to_name: str, subject: str, body: str,
                   queue_id: str = None) -> Dict[str, Any]:
        """
        Envia um email via Brevo. Retorna dict com status, message_id e tracking_id.

        Gera tracking_id unico antes do envio e salva tanto o tracking_id
        quanto o brevo_message_id na approval_queue apos envio com sucesso.
        """
        if not self._enabled:
            logger.warning("BREVO DESABILITADO - email NAO enviado (configure BREVO_API_KEY no .env)",
                extra={"to": to_email, "subject": subject[:40]})
            return {"success": False, "error": "BREVO_API_KEY nao configurada"}

        # Gerar tracking ID unico para rastreamento
        tracking_id = str(uuid.uuid4())

        payload = {
            "sender": {"name": self.from_name, "email": self.from_email},
            "to": [{"email": to_email, "name": to_name}],
            "subject": subject,
            "htmlContent": self._text_to_html(body),
            "textContent": body,
        }
        if queue_id:
            payload["tags"] = [f"queue:{queue_id}"]
        # Adicionar header customizado com tracking_id para correlacao
        payload["headers"] = {"X-Tracking-Id": tracking_id}

        try:
            resp = requests.post(
                f"{self.BASE_URL}/smtp/email",
                headers={"api-key": self.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            if resp.status_code == 201:
                data = resp.json()
                msg_id = data.get("messageId", "")
                logger.info("Email enviado via Brevo",
                    extra={"to": to_email, "queue_id": queue_id,
                           "message_id": msg_id, "tracking_id": tracking_id})

                # Atualizar approval_queue com tracking_id e brevo_message_id
                if queue_id:
                    self._update_queue_tracking(queue_id, tracking_id, msg_id)

                return {
                    "success": True,
                    "message_id": msg_id,
                    "tracking_id": tracking_id,
                }
            else:
                logger.error("Erro Brevo", extra={"status": resp.status_code, "body": resp.text[:200]})
                return {"success": False, "error": resp.text[:200], "status_code": resp.status_code}
        except Exception as e:
            logger.error("Excecao ao enviar email", extra={"error": str(e)})
            return {"success": False, "error": str(e)}

    def _update_queue_tracking(
        self, queue_id: str, tracking_id: str, brevo_message_id: str
    ) -> None:
        """
        Atualiza approval_queue com tracking_id e brevo_message_id apos envio.

        Args:
            queue_id: UUID do item na approval_queue.
            tracking_id: UUID de tracking gerado antes do envio.
            brevo_message_id: ID retornado pela API do Brevo.
        """
        try:
            from database.supabase_client import db
            db.client.table("approval_queue").update({
                "tracking_id": tracking_id,
                "brevo_message_id": brevo_message_id,
                "sent_at": datetime.utcnow().isoformat(),
            }).eq("id", queue_id).execute()
            logger.debug(
                "Queue atualizada com tracking",
                extra={
                    "queue_id": queue_id,
                    "tracking_id": tracking_id,
                    "brevo_message_id": brevo_message_id,
                },
            )
        except Exception as e:
            logger.error(
                "Erro ao atualizar queue com tracking (envio OK, tracking nao salvo)",
                extra={"queue_id": queue_id, "error": str(e)},
            )
    def _text_to_html(self, text: str) -> str:
        """Converte texto plano para HTML com links clicaveis."""
        import re
        # Primeiro, converter URLs em links HTML
        meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "")
        meeting_link_text = os.getenv("HUBSPOT_MEETING_LINK_TEXT", "Agendar conversa com Fernando")

        def _url_to_link(match):
            url = match.group(0)
            if meeting_link and meeting_link in url:
                return f'<a href="{url}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>'
            return f'<a href="{url}" style="color:#3BB8C4">{url}</a>'

        text_with_links = re.sub(r'https?://[^\s<>"\')\]]+', _url_to_link, text)

        # Converter texto do meeting link (sem URL) em hyperlink
        if meeting_link and meeting_link_text and meeting_link_text in text_with_links and meeting_link not in text_with_links:
            text_with_links = text_with_links.replace(
                meeting_link_text,
                f'<a href="{meeting_link}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>',
                1,
            )

        # Usar <div> com margin-bottom pequeno em vez de <p> (Outlook friendly)
        lines = text_with_links.split(chr(10))
        html_lines = []
        for line in lines:
            if line.strip():
                html_lines.append(f'<div style="margin:0;padding:0;line-height:1.5">{line}</div>')
            else:
                html_lines.append('<div style="margin:0;padding:0;height:12px">&nbsp;</div>')
        body_html = chr(10).join(html_lines)
        return (
            '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;'
            'line-height:1.5;margin:0;padding:20px">'
            + body_html
            + '</body></html>'
        )

    def check_quota(self) -> Dict[str, Any]:
        """Verifica quota de envios da conta Brevo."""
        if not self._enabled:
            return {"available": False, "error": "API nao configurada"}
        try:
            resp = requests.get(
                f"{self.BASE_URL}/account",
                headers={"api-key": self.api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"available": True, "plan": data.get("plan", [])}
            return {"available": False, "status_code": resp.status_code}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def check_senders(self) -> Dict[str, Any]:
        """Verifica se o from_email esta verificado como sender no Brevo."""
        if not self._enabled:
            return {"verified": False, "error": "API nao configurada"}
        try:
            resp = requests.get(
                f"{self.BASE_URL}/senders",
                headers={"api-key": self.api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                senders = resp.json().get("senders", [])
                verified_emails = [s["email"] for s in senders if s.get("active")]
                is_verified = self.from_email.lower() in [e.lower() for e in verified_emails]
                return {
                    "verified": is_verified,
                    "from_email": self.from_email,
                    "verified_senders": verified_emails,
                }
            return {"verified": False, "status_code": resp.status_code}
        except Exception as e:
            return {"verified": False, "error": str(e)}


# Singleton
brevo_sender = BrevoSender()