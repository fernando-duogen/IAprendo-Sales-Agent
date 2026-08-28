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

# Ano do ENEM vigente (rodape dos graficos no email) — fonte unica em enem_tools.
try:
    from agent.tools.enem_tools import ENEM_VINTAGE as _ENEM_VINTAGE
except Exception:
    _ENEM_VINTAGE = 2025


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
                   queue_id: str = None, chart_urls: list = None,
                   from_email: str = None, from_name: str = None,
                   from_username: str = None,
                   attachments: list = None) -> Dict[str, Any]:
        """
        Envia um email via Brevo. Retorna dict com status, message_id e tracking_id.

        Args:
            chart_urls: Lista opcional de dicts {"type": str, "url": str, "alt": str}
                        para injetar graficos de insight no HTML do email.
            from_email: Email do remetente. Se None, resolve via get_active_sender()
                        e cai em settings.BREVO_SENDER_EMAIL/YOUR_EMAIL como fallback.
                        IMPORTANTE: o email deve estar verificado como sender no Brevo.
            from_name: Nome do remetente. Mesma resolucao do from_email.
            from_username: Username do perfil para resolver email/name/assinatura
                        (ex: 'fernando', 'lizianne'). Se passado, sobrescreve a
                        resolucao automatica e usa a ASSINATURA desse usuario.
            attachments: Lista de dicts [{"name": str, "url": str}] para anexar
                        PDFs/arquivos. Brevo baixa do URL no momento do envio.
                        Se None, resolve dos anexos ativos do sender (sticky).
                        Se lista vazia [], envia SEM anexos (override pra desligar).
        """
        if not self._enabled:
            logger.warning("BREVO DESABILITADO - email NAO enviado (configure BREVO_API_KEY no .env)",
                extra={"to": to_email, "subject": subject[:40]})
            return {"success": False, "error": "BREVO_API_KEY nao configurada"}

        # Resolver remetente — explicitamente passado > username > sender ativo > fallback
        # IMPORTANTE: from_name usa `email_sender_name` (ex: "Lizianne | DUOGEN")
        # ao inves de `name` (ex: "Lizianne"). Esse campo eh especifico do email
        # — outros lugares (saudacao IAlex, dashboard, prompts LLM) usam `name`.
        # get_email_identity (e nao get_active_sender): quem OPERA pode ser
        # diferente de quem ASSINA. O agente "vendedor1" prospecta em nome
        # proprio — leads e created_by ficam com ele — mas o e-mail sai como o
        # Fernando, inclusive assinatura e anexos (que sao indexados por
        # signature_username, resolvido aqui para a IDENTIDADE, nao para o
        # operador). Sem heranca configurada, identidade == operador.
        signature_username = from_username
        if from_username:
            try:
                from utils.sender_profile import (
                    get_email_identity, get_email_identity_username)
                _p = get_email_identity(from_username)
                signature_username = (get_email_identity_username(from_username)
                                      or from_username)
                from_email = from_email or _p.get("email") or self.from_email
                from_name = (from_name or _p.get("email_sender_name")
                             or _p.get("name") or self.from_name)
            except Exception:
                pass
        if not from_email or not from_name or not signature_username:
            try:
                from utils.sender_profile import (
                    get_email_identity, get_email_identity_username)
                _active = get_email_identity()
                from_email = from_email or _active.get("email") or self.from_email
                from_name = (from_name or _active.get("email_sender_name")
                             or _active.get("name") or self.from_name)
                if not signature_username:
                    signature_username = get_email_identity_username()
            except Exception:
                from_email = from_email or self.from_email
                from_name = from_name or self.from_name

        # Gerar tracking ID unico para rastreamento
        tracking_id = str(uuid.uuid4())

        # Resolver anexos: explicitos > sticky do sender ativo (None) >
        # nenhum (lista vazia explicita = override pra desligar)
        if attachments is None:
            try:
                from integrations.email_attachments import email_attachments
                resolved_attachments = email_attachments.get_active_attachments(
                    username=signature_username
                )
            except Exception:
                resolved_attachments = []
        else:
            resolved_attachments = attachments or []

        payload = {
            "sender": {"name": from_name, "email": from_email},
            "to": [{"email": to_email, "name": to_name}],
            "subject": subject,
            "htmlContent": self._text_to_html(
                body, with_signature=True, chart_urls=chart_urls,
                signature_username=signature_username,
            ),
            "textContent": body + self._get_text_signature(username=signature_username),
        }
        if resolved_attachments:
            # Brevo espera [{"name": str, "url": str}] — baixa do URL no envio.
            # Filtrar entries invalidas pra evitar 400 do Brevo.
            valid = [
                {"name": a.get("name") or "anexo.pdf", "url": a["url"]}
                for a in resolved_attachments
                if isinstance(a, dict) and a.get("url")
            ]
            if valid:
                payload["attachment"] = valid
        if queue_id:
            payload["tags"] = [f"queue:{queue_id}"]
        # Adicionar header customizado com tracking_id para correlacao
        payload["headers"] = {"X-Tracking-Id": tracking_id}

        # Envio com retry em falhas TRANSITORIAS (5xx do Brevo/Cloudflare ex 522/503,
        # timeouts de rede). 4xx = erro do cliente (sender invalido, payload ruim) ->
        # nao adianta repetir. Sem isto, um blip transitorio derruba um email aprovado.
        import time as _time
        last_err: Dict[str, Any] = {"error": "falha desconhecida"}
        for _attempt in range(1, 4):  # ate 3 tentativas
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
                               "message_id": msg_id, "tracking_id": tracking_id,
                               "attempt": _attempt})

                    # Atualizar approval_queue com tracking_id e brevo_message_id
                    if queue_id:
                        self._update_queue_tracking(queue_id, tracking_id, msg_id)

                    return {
                        "success": True,
                        "message_id": msg_id,
                        "tracking_id": tracking_id,
                    }

                # 4xx = erro do cliente -> retornar imediatamente (retry nao ajuda)
                if 400 <= resp.status_code < 500:
                    logger.error("Erro Brevo (cliente, sem retry)",
                        extra={"status": resp.status_code, "body": resp.text[:200]})
                    return {"success": False, "error": resp.text[:200],
                            "status_code": resp.status_code}

                # 5xx transitorio -> registrar e tentar de novo
                last_err = {"error": resp.text[:200], "status_code": resp.status_code}
                logger.warning("Erro Brevo transitorio (vai tentar de novo)",
                    extra={"status": resp.status_code, "attempt": _attempt})
            except Exception as e:
                last_err = {"error": str(e)}
                logger.warning("Excecao ao enviar email (vai tentar de novo)",
                    extra={"error": str(e), "attempt": _attempt})

            if _attempt < 3:
                _time.sleep(2 * _attempt)  # backoff: 2s, 4s

        logger.error("Email NAO enviado apos 3 tentativas",
            extra={"to": to_email, **last_err})
        return {"success": False, **last_err}

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
    def _get_text_signature(self, username: Optional[str] = None) -> str:
        """Retorna assinatura em texto puro (para textContent).

        Se username=None, resolve do sender ativo automaticamente.
        """
        try:
            from integrations.email_signature import email_signature
            return email_signature.render_text(username=username)
        except Exception:
            return ""

    def _get_html_signature(self, username: Optional[str] = None) -> str:
        """Retorna assinatura em HTML (para htmlContent)."""
        try:
            from integrations.email_signature import email_signature
            return email_signature.render_html(username=username)
        except Exception:
            return ""

    def _text_to_html(self, text: str, with_signature: bool = False,
                      chart_urls: list = None, signature_username: Optional[str] = None) -> str:
        """Converte texto plano para HTML com links clicaveis, graficos e assinatura.

        Se o body ja contem tags HTML (ex: <img>, <a href>, <div>),
        preserva essas tags e so converte URLs do texto plano.
        """
        import re
        meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "")
        meeting_link_text = os.getenv("HUBSPOT_MEETING_LINK_TEXT", "Agendar conversa com Fernando")

        # Detectar se o body tem HTML embutido (charts/report inline).
        # IMPORTANTE: casar `<a `, `<img `, `<div ` — o padrao antigo
        # (`<(img|a\s+href|div)\s`) NAO casava `<a href="..."` (exigia espaco
        # depois de `href`, mas vem `=`), entao o report_link era tratado como
        # texto puro e o linkificador de URL re-embrulhava a URL DENTRO da
        # ancora -> link aninhado/quebrado.
        _has_html = bool(re.search(r'<(?:a|img|div)\s', text))

        if _has_html:
            # Body ja tem HTML — proteger tags existentes antes de converter URLs
            # 1. Extrair todos os blocos HTML para placeholders
            _html_blocks = []
            def _protect_html(match):
                _html_blocks.append(match.group(0))
                return f"__HTML_BLOCK_{len(_html_blocks) - 1}__"
            # Proteger tags completas: <div...>...</div>, <img.../>, <a...>...</a>
            protected = re.sub(r'<div\s[^>]*>.*?</div>', _protect_html, text, flags=re.DOTALL)
            protected = re.sub(r'<img\s[^>]*/>', _protect_html, protected)
            protected = re.sub(r'<a\s[^>]*>.*?</a>', _protect_html, protected, flags=re.DOTALL)

            # 2. Converter URLs restantes (texto plano) em links
            def _url_to_link(match):
                url = match.group(0)
                if meeting_link and meeting_link in url:
                    return f'<a href="{url}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>'
                return f'<a href="{url}" style="color:#3BB8C4">{url}</a>'
            protected = re.sub(r'https?://[^\s<>"\')\]]+', _url_to_link, protected)

            # 3. Converter meeting link text em hyperlink
            if meeting_link and meeting_link_text and meeting_link_text in protected and meeting_link not in protected:
                protected = protected.replace(
                    meeting_link_text,
                    f'<a href="{meeting_link}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>',
                    1,
                )

            # 4. Restaurar blocos HTML protegidos
            for i, block in enumerate(_html_blocks):
                protected = protected.replace(f"__HTML_BLOCK_{i}__", block)

            # 5. Converter quebras de linha em <div> (mas preservar blocos HTML)
            lines = protected.split(chr(10))
            html_lines = []
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    html_lines.append('<div style="margin:0;padding:0;height:12px">&nbsp;</div>')
                elif stripped.startswith("<div") or stripped.startswith("<img") or stripped.startswith("<a "):
                    html_lines.append(stripped)  # HTML puro, nao envolver em <div>
                else:
                    html_lines.append(f'<div style="margin:0;padding:0;line-height:1.5">{line}</div>')
            body_html = chr(10).join(html_lines)
        else:
            # Body e texto puro — converter tudo normalmente
            def _url_to_link(match):
                url = match.group(0)
                if meeting_link and meeting_link in url:
                    return f'<a href="{url}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>'
                return f'<a href="{url}" style="color:#3BB8C4">{url}</a>'
            text_with_links = re.sub(r'https?://[^\s<>"\')\]]+', _url_to_link, text)

            if meeting_link and meeting_link_text and meeting_link_text in text_with_links and meeting_link not in text_with_links:
                text_with_links = text_with_links.replace(
                    meeting_link_text,
                    f'<a href="{meeting_link}" style="color:#3BB8C4;font-weight:bold">{meeting_link_text}</a>',
                    1,
                )

            lines = text_with_links.split(chr(10))
            html_lines = []
            for line in lines:
                if line.strip():
                    html_lines.append(f'<div style="margin:0;padding:0;line-height:1.5">{line}</div>')
                else:
                    html_lines.append('<div style="margin:0;padding:0;height:12px">&nbsp;</div>')
            body_html = chr(10).join(html_lines)

        # Graficos de insight (se houver e se nao estao ja inline no body)
        charts_html = ""
        _body_has_inline_charts = '<img src=' in body_html and 'insight-charts' in body_html
        if chart_urls and not _body_has_inline_charts:
            for chart in chart_urls:
                url = chart.get("url", "")
                alt = chart.get("alt", "Grafico de analise")
                if not url:
                    continue
                charts_html += (
                    '<div style="background:#f8f9fa;padding:16px;border-radius:8px;'
                    'margin:20px 0;text-align:center">'
                    f'<img src="{url}" alt="{alt}" '
                    'style="width:100%;max-width:560px;display:block;margin:0 auto;'
                    'border-radius:4px" />'
                    '<p style="color:#999;font-size:11px;margin-top:8px;margin-bottom:0">'
                    f'Fonte: Microdados ENEM {_ENEM_VINTAGE} / Censo Escolar (INEP)</p>'
                    '</div>'
                )

        # Assinatura HTML (se habilitada). Usa username explicito (multi-user)
        # ou cai no sender ativo (resolvido por email_signature).
        signature_html = ""
        if with_signature:
            signature_html = self._get_html_signature(username=signature_username)

        return (
            '<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;'
            'line-height:1.5;margin:0;padding:20px">'
            + body_html
            + charts_html
            + signature_html
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