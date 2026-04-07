"""
Email Signature — Assinatura padrao para todos os emails enviados pelo IAlex.

Armazena a configuracao da assinatura em conversation_memory (scope=global)
usando marker [EMAIL_SIGNATURE_V1]. Sem migration necessaria.

A assinatura e injetada automaticamente pelo brevo_sender ao enviar qualquer
email. Suporta texto livre + URL de imagem (logo, banner, etc).

Usage:
    from integrations.email_signature import email_signature

    # Carregar assinatura atual
    sig = email_signature.get_signature()

    # Salvar nova assinatura
    email_signature.save_signature({
        "enabled": True,
        "text": "Fernando Nienaber\\nIAprendo - Plataforma Educacional",
        "image_url": "https://example.com/logo.png",
        "image_width": 200,
        "link_url": "https://iaprendo.com.br",
    })

    # Gerar HTML da assinatura
    html = email_signature.render_html()
"""
import json
from typing import Any, Dict, Optional

from database.supabase_client import db
from utils.logger import logger

MARKER = "[EMAIL_SIGNATURE_V1]"


class EmailSignature:
    """Gerenciador da assinatura de email."""

    TABLE = "conversation_memory"

    def default_signature(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "text": "",
            "image_url": "",
            "image_width": 200,
            "image_alt": "Logo",
            "link_url": "",
            "separator": True,
        }

    def _find_existing(self) -> Optional[Dict[str, Any]]:
        try:
            r = (
                db.client.table(self.TABLE)
                .select("*")
                .eq("scope", "global")
                .ilike("content", f"{MARKER}%")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return (r.data or [None])[0]
        except Exception:
            return None

    def get_signature(self) -> Dict[str, Any]:
        existing = self._find_existing()
        if not existing:
            return self.default_signature()
        try:
            content = existing.get("content", "")
            payload = content[len(MARKER):].strip()
            data = json.loads(payload)
            defaults = self.default_signature()
            return {**defaults, **data}
        except Exception:
            return self.default_signature()

    def save_signature(self, sig: Dict[str, Any]) -> bool:
        try:
            # Remover antigas
            db.client.table(self.TABLE).delete().eq("scope", "global").ilike(
                "content", f"{MARKER}%"
            ).execute()
            # Inserir nova
            payload = MARKER + json.dumps(sig, ensure_ascii=False)
            db.client.table(self.TABLE).insert({
                "scope": "global",
                "scope_id": None,
                "category": "fact",
                "content": payload[:2000],
                "importance": 8,
                "source": "email_signature",
            }).execute()
            logger.info("Assinatura de email salva")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar assinatura: {e}")
            return False

    def render_html(self) -> str:
        """Gera HTML da assinatura para injetar no email.
        Retorna string vazia se assinatura desabilitada ou vazia."""
        sig = self.get_signature()
        if not sig.get("enabled"):
            return ""

        text = (sig.get("text") or "").strip()
        image_url = (sig.get("image_url") or "").strip()
        image_width = sig.get("image_width", 200)
        image_alt = sig.get("image_alt", "Logo")
        link_url = (sig.get("link_url") or "").strip()
        separator = sig.get("separator", True)

        if not text and not image_url:
            return ""

        parts = []

        # Separador
        if separator:
            parts.append(
                '<div style="margin:20px 0 12px 0;border-top:1px solid #E0E0E0"></div>'
            )

        # Texto da assinatura (cada linha em <div>)
        if text:
            for line in text.split("\n"):
                line = line.strip()
                if line:
                    parts.append(
                        f'<div style="margin:0;padding:0;font-size:13px;'
                        f'color:#555;line-height:1.5">{line}</div>'
                    )

        # Imagem (com link opcional)
        if image_url:
            img_tag = (
                f'<img src="{image_url}" alt="{image_alt}" '
                f'width="{image_width}" style="max-width:100%;height:auto;'
                f'margin-top:8px;border:0" />'
            )
            if link_url:
                img_tag = f'<a href="{link_url}" target="_blank">{img_tag}</a>'
            parts.append(f'<div style="margin-top:8px">{img_tag}</div>')

        return "\n".join(parts)

    def render_text(self) -> str:
        """Gera versao texto puro da assinatura (para textContent)."""
        sig = self.get_signature()
        if not sig.get("enabled"):
            return ""
        text = (sig.get("text") or "").strip()
        if not text:
            return ""
        return "\n--\n" + text


email_signature = EmailSignature()
