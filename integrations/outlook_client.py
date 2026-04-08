"""
Outlook Calendar Client — Integração bidirecional com Microsoft Outlook.

Usa Microsoft Graph API via MSAL para:
- Ler eventos do calendário do Fernando
- Detectar reuniões com escolas automaticamente
- Fornecer dados para briefings pré-reunião

Autenticação: Device Code Flow (Fernando faz login uma vez, token salvo em disco).

Pré-requisito: App Registration no Azure com permissões Calendars.Read + User.Read.
Credenciais no .env: MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_TENANT_ID.

Usage:
    from integrations.outlook_client import outlook_client

    # Autenticar (primeira vez abre browser)
    outlook_client.authenticate()

    # Buscar eventos das próximas 48h
    events = outlook_client.get_upcoming_events(hours=48)

    # Buscar eventos novos desde última verificação
    events = outlook_client.get_recent_events(minutes=15)
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from difflib import SequenceMatcher

from utils.logger import logger

TOKEN_CACHE_PATH = Path.home() / ".iaprendo-outlook-token.json"

# Scopes necessários (delegated)
SCOPES = ["Calendars.Read", "User.Read"]

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class OutlookCalendarClient:
    """Client para Microsoft Graph Calendar API."""

    def __init__(self) -> None:
        from dotenv import load_dotenv
        load_dotenv()

        self.client_id = os.getenv("MICROSOFT_CLIENT_ID", "")
        self.client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "")
        self.tenant_id = os.getenv("MICROSOFT_TENANT_ID", "")
        self._enabled = bool(self.client_id and self.tenant_id)
        self._access_token: Optional[str] = None
        self._last_poll_at: Optional[str] = None

        if not self._enabled:
            logger.info("Outlook Calendar desabilitado (MICROSOFT_CLIENT_ID nao configurado)")

    def is_available(self) -> bool:
        return self._enabled

    # =========================================================================
    # Autenticação via MSAL
    # =========================================================================

    def _load_token_cache(self) -> Optional[dict]:
        """Carrega token salvo em disco."""
        if TOKEN_CACHE_PATH.exists():
            try:
                data = json.loads(TOKEN_CACHE_PATH.read_text())
                return data
            except Exception:
                pass
        return None

    def _save_token_cache(self, token_data: dict) -> None:
        """Salva token em disco para reuso."""
        try:
            TOKEN_CACHE_PATH.write_text(json.dumps(token_data))
        except Exception as e:
            logger.warning(f"Erro ao salvar token Outlook: {e}")

    def authenticate(self) -> bool:
        """Autentica com Microsoft Graph. Usa token em cache ou device code flow."""
        if not self._enabled:
            return False

        try:
            import msal
        except ImportError:
            logger.error("MSAL nao instalado. Execute: pip install msal")
            return False

        # Tentar token em cache primeiro
        cached = self._load_token_cache()
        if cached and cached.get("access_token"):
            # Verificar se ainda é válido (expira em ~1h)
            expires_at = cached.get("expires_at", 0)
            if datetime.now().timestamp() < expires_at - 300:  # 5 min de margem
                self._access_token = cached["access_token"]
                return True

        # Criar app MSAL
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        app = msal.PublicClientApplication(
            self.client_id,
            authority=authority,
        )

        # Tentar refresh token se disponível
        if cached and cached.get("refresh_token"):
            try:
                result = app.acquire_token_by_refresh_token(
                    cached["refresh_token"],
                    scopes=SCOPES,
                )
                if "access_token" in result:
                    self._access_token = result["access_token"]
                    self._save_token_cache({
                        "access_token": result["access_token"],
                        "refresh_token": result.get("refresh_token", cached.get("refresh_token")),
                        "expires_at": datetime.now().timestamp() + result.get("expires_in", 3600),
                    })
                    logger.info("Outlook: token renovado via refresh")
                    return True
            except Exception:
                pass

        # Device code flow (primeira vez — requer interação do usuário)
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            logger.error(f"Outlook device flow falhou: {flow.get('error_description', '?')}")
            return False

        logger.info(
            f"Outlook: autenticacao necessaria. "
            f"Acesse {flow['verification_uri']} e digite: {flow['user_code']}"
        )

        # Notificar Fernando via WhatsApp (se bridge disponível)
        try:
            from agent.whatsapp_bridge import WhatsAppBridge
            bridge = WhatsAppBridge()
            owner = os.getenv("IALEX_OWNER_NUMBER", "")
            if owner:
                bridge.send_message(owner, (
                    f"🔐 *Autenticacao Outlook necessaria*\n\n"
                    f"Para conectar seu calendario, acesse:\n"
                    f"{flow['verification_uri']}\n\n"
                    f"E digite o codigo: `{flow['user_code']}`\n\n"
                    f"_Expira em {flow.get('expires_in', 900) // 60} minutos._"
                ))
        except Exception:
            pass

        # Aguardar login (blocking — timeout 5 min)
        result = app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self._access_token = result["access_token"]
            self._save_token_cache({
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_at": datetime.now().timestamp() + result.get("expires_in", 3600),
            })
            logger.info("Outlook: autenticado com sucesso")
            return True

        logger.error(f"Outlook auth falhou: {result.get('error_description', '?')}")
        return False

    def _ensure_auth(self) -> bool:
        """Garante que temos token válido."""
        if self._access_token:
            cached = self._load_token_cache()
            if cached and datetime.now().timestamp() < cached.get("expires_at", 0) - 300:
                return True
        return self.authenticate()

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    # =========================================================================
    # Leitura de eventos
    # =========================================================================

    def get_events(
        self,
        from_dt: datetime,
        to_dt: datetime,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Busca eventos do calendário num período."""
        if not self._ensure_auth():
            return []

        import requests

        from_iso = from_dt.strftime("%Y-%m-%dT%H:%M:%S")
        to_iso = to_dt.strftime("%Y-%m-%dT%H:%M:%S")

        url = (
            f"{GRAPH_BASE}/me/calendarView"
            f"?startDateTime={from_iso}&endDateTime={to_iso}"
            f"&$top={max_results}&$orderby=start/dateTime"
            f"&$select=subject,start,end,location,body,organizer,attendees,isAllDay"
        )

        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code == 401:
                # Token expirado — tentar renovar
                self._access_token = None
                if self._ensure_auth():
                    resp = requests.get(url, headers=self._get_headers(), timeout=15)

            if resp.status_code != 200:
                logger.warning(f"Outlook API {resp.status_code}: {resp.text[:200]}")
                return []

            data = resp.json()
            events = data.get("value", [])
            logger.info(f"Outlook: {len(events)} eventos encontrados")
            return events
        except Exception as e:
            logger.error(f"Outlook get_events erro: {e}")
            return []

    def get_upcoming_events(self, hours: int = 48) -> List[Dict[str, Any]]:
        """Eventos das próximas N horas."""
        now = datetime.now(timezone.utc)
        return self.get_events(now, now + timedelta(hours=hours))

    def get_recent_events(self, minutes: int = 15) -> List[Dict[str, Any]]:
        """Eventos criados/modificados nos últimos N minutos (para poll)."""
        now = datetime.now(timezone.utc)
        # Buscar próximas 72h e filtrar os que começam no futuro
        events = self.get_events(now, now + timedelta(hours=72))
        return events  # O scheduler filtra os já processados

    # =========================================================================
    # Match evento → escola
    # =========================================================================

    def match_event_to_school(
        self, event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Tenta encontrar escola no banco que corresponda ao evento.
        Busca pelo título e corpo do evento."""
        subject = (event.get("subject") or "").strip()
        body_preview = ""
        if event.get("body"):
            body_preview = (event["body"].get("content") or "")[:500]

        search_text = f"{subject} {body_preview}".lower()
        if not search_text.strip():
            return None

        try:
            from database.supabase_client import db
            # Buscar escolas do banco (top 200 por score)
            schools = db.client.table("companies").select(
                "id,name,city,status"
            ).order("qualification_score", desc=True).limit(200).execute().data or []

            best_match = None
            best_score = 0.0
            import unicodedata

            def _norm(s):
                nfkd = unicodedata.normalize("NFKD", str(s))
                return nfkd.encode("ASCII", "ignore").decode("ASCII").lower()

            for school in schools:
                school_name = school.get("name", "")
                if not school_name:
                    continue
                # Checar se nome da escola aparece no título/corpo
                norm_name = _norm(school_name)
                norm_text = _norm(search_text)
                if norm_name in norm_text:
                    return school  # Match exato
                # Fuzzy match
                ratio = SequenceMatcher(None, norm_name, norm_text[:len(norm_name) + 20]).ratio()
                if ratio > best_score and ratio > 0.6:
                    best_score = ratio
                    best_match = school

            return best_match
        except Exception as e:
            logger.debug(f"match_event_to_school erro: {e}")
            return None

    # =========================================================================
    # Helpers
    # =========================================================================

    def parse_event_time(self, event: Dict) -> Optional[datetime]:
        """Extrai datetime de início do evento."""
        start = event.get("start", {})
        dt_str = start.get("dateTime", "")
        tz_str = start.get("timeZone", "UTC")
        if not dt_str:
            return None
        try:
            # Graph retorna sem timezone info — assume UTC ou timezone do evento
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def parse_event_end(self, event: Dict) -> Optional[datetime]:
        """Extrai datetime de fim do evento."""
        end = event.get("end", {})
        dt_str = end.get("dateTime", "")
        if not dt_str:
            return None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None


# Singleton
outlook_client = OutlookCalendarClient()
