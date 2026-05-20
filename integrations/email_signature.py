"""
Email Signature — Assinatura por usuario (multi-user).

Armazena a configuracao da assinatura em conversation_memory:
- Por usuario:    scope='user',  scope_id=<username>  marker [EMAIL_SIGNATURE_V1]
- Global (legado): scope='global', scope_id=NULL      marker [EMAIL_SIGNATURE_V1]

A assinatura e injetada automaticamente pelo brevo_sender ao enviar qualquer
email. Resolve qual usuario usar via utils.sender_profile.get_active_sender_username()
ou parametro username explicito.

Backward compat: se um usuario nao tem assinatura propria, cai pra global
(comportamento antigo). Quando salva pela primeira vez, vira a do usuario.

Usage:
    from integrations.email_signature import email_signature

    # Carregar assinatura do usuario ativo (dashboard logado ou IAlex thread)
    sig = email_signature.get_signature()

    # Carregar a de um usuario especifico
    sig = email_signature.get_signature(username="lizianne")

    # Salvar a do usuario ativo
    email_signature.save_signature({
        "enabled": True,
        "text": "Lizianne Nienaber\\nIAprendo - Plataforma Educacional",
        "image_url": "https://example.com/logo.png",
        "image_width": 200,
        "link_url": "https://iaprendo.com.br",
    })

    # Gerar HTML da assinatura do usuario ativo
    html = email_signature.render_html()

    # Gerar HTML da assinatura de um usuario especifico (workflows de envio)
    html = email_signature.render_html(username="fernando")
"""
import json
from typing import Any, Dict, Optional

from database.supabase_client import db
from utils.logger import logger

MARKER = "[EMAIL_SIGNATURE_V1]"


def _resolve_active_username() -> Optional[str]:
    """Resolve o username ativo (dashboard logado ou IAlex thread). None se fallback."""
    try:
        from utils.sender_profile import get_active_sender_username
        return get_active_sender_username()
    except Exception:
        return None


class EmailSignature:
    """Gerenciador da assinatura de email (por usuario, com fallback global)."""

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

    # IMPORTANTE: conversation_memory tem CHECK (scope IN ('global','company',
    # 'contact')) e scope_id eh UUID. Por isso a assinatura por usuario NAO usa
    # scope='user'/scope_id=username — usa scope='global', scope_id=NULL e um
    # MARKER distinto embutido no `content`:
    #   - Global/legado:  [EMAIL_SIGNATURE_V1]{json}
    #   - Por usuario:     [EMAIL_SIGNATURE_USER:<username>]{json}
    # Os markers sao mutuamente exclusivos (um nunca eh prefixo do outro).

    @staticmethod
    def _user_marker(username: str) -> str:
        return f"[EMAIL_SIGNATURE_USER:{username}]"

    def _find_user_signature(self, username: str) -> Optional[Dict[str, Any]]:
        """Busca assinatura do usuario (marker [EMAIL_SIGNATURE_USER:<username>])."""
        try:
            r = (
                db.client.table(self.TABLE)
                .select("*")
                .eq("scope", "global")
                .ilike("content", f"{self._user_marker(username)}%")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return (r.data or [None])[0]
        except Exception:
            return None

    def _find_global_signature(self) -> Optional[Dict[str, Any]]:
        """Busca a assinatura global/legado (marker [EMAIL_SIGNATURE_V1])."""
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

    def get_signature(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Retorna assinatura. Se username=None, resolve do sender ativo.

        Ordem de resolucao:
        1. Assinatura do usuario explicito ou ativo (scope=user)
        2. Fallback: assinatura global (legado, compat)
        3. Default vazio
        """
        u = username or _resolve_active_username()

        # 1. Tentar buscar a do usuario
        if u:
            user_sig = self._find_user_signature(u)
            if user_sig:
                return self._parse_payload(user_sig)

        # 2. Fallback: global
        global_sig = self._find_global_signature()
        if global_sig:
            return self._parse_payload(global_sig)

        # 3. Default vazio
        return self.default_signature()

    def _parse_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai o JSON apos o marker. Markers tem tamanho variavel
        ([EMAIL_SIGNATURE_V1] vs [EMAIL_SIGNATURE_USER:lizianne]) — o primeiro
        ']' fecha o marker, entao split(']', 1)[1] pega o payload."""
        try:
            content = row.get("content", "")
            if "]" not in content:
                return self.default_signature()
            payload = content.split("]", 1)[1].strip()
            data = json.loads(payload)
            defaults = self.default_signature()
            return {**defaults, **data}
        except Exception:
            return self.default_signature()

    def save_signature(self, sig: Dict[str, Any], username: Optional[str] = None) -> bool:
        """Salva assinatura para o usuario (default = sender ativo).

        Sempre grava scope='global', scope_id=NULL (respeita CHECK + tipo UUID
        de conversation_memory). O usuario eh distinguido pelo MARKER no content.
        Se username=None e sem sender ativo, salva como global (compat legado).
        """
        u = username or _resolve_active_username()
        marker = self._user_marker(u) if u else MARKER
        insert_payload = {
            "scope": "global",
            "scope_id": None,
            "category": "fact",
            "content": (marker + json.dumps(sig, ensure_ascii=False))[:2000],
            "importance": 8,
            "source": "ialex",
        }
        try:
            # Remover antigas do MESMO marker (mesma assinatura logica)
            (
                db.client.table(self.TABLE)
                .delete()
                .eq("scope", "global")
                .ilike("content", f"{marker}%")
                .execute()
            )
            # Inserir nova
            db.client.table(self.TABLE).insert(insert_payload).execute()
            logger.info(
                f"Assinatura de email salva (user={u or 'global'})"
            )
            return True
        except Exception as e:
            # Log enriquecido para diagnostico: revela payload exato + tipo do erro.
            # Util para identificar regressao (ex: scope_id=username string) ou
            # cache do Streamlit Cloud rodando versao antiga.
            logger.error(
                "Erro ao salvar assinatura",
                extra={
                    "username": u,
                    "marker": marker,
                    "scope_sent": insert_payload["scope"],
                    "scope_id_sent": insert_payload["scope_id"],
                    "scope_id_type": type(insert_payload["scope_id"]).__name__,
                    "error_type": type(e).__name__,
                    "error_msg": str(e)[:300],
                },
                exc_info=True,
            )
            return False

    def render_html(self, username: Optional[str] = None) -> str:
        """Gera HTML da assinatura para injetar no email.
        Retorna string vazia se assinatura desabilitada ou vazia."""
        sig = self.get_signature(username=username)
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

    def render_text(self, username: Optional[str] = None) -> str:
        """Gera versao texto puro da assinatura (para textContent)."""
        sig = self.get_signature(username=username)
        if not sig.get("enabled"):
            return ""
        text = (sig.get("text") or "").strip()
        if not text:
            return ""
        return "\n--\n" + text


email_signature = EmailSignature()
