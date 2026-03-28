"""
SnovClient - Busca emails via Snov.io API.

Free tier: 50 creditos/mes.
Requer no .env:
  SNOV_CLIENT_ID  = seu User ID  (em snov.io -> Profile -> API -> Client ID)
  SNOV_API_KEY    = seu Client Secret (em snov.io -> Profile -> API -> Secret)
"""
import requests
from typing import Dict, Any, List, Optional
from config.settings import settings
from utils.logger import logger


class SnovClient:
    """Cliente para Snov.io Domain Search API.

    Usa OAuth2 client_credentials para autenticacao.
    Busca emails profissionais associados ao dominio de uma escola.
    """

    TOKEN_URL = "https://api.snov.io/v1/oauth/access_token"
    BASE_URL = "https://api.snov.io/v1"

    def __init__(self) -> None:
        self.client_id: str = settings.SNOV_CLIENT_ID
        self.client_secret: str = settings.SNOV_API_KEY
        self._access_token: Optional[str] = None

    def is_available(self) -> bool:
        """Verifica se as credenciais estao configuradas."""
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> Optional[str]:
        """Obtém token OAuth2 do Snov.io (cacheado na sessao atual)."""
        if self._access_token:
            return self._access_token

        try:
            resp = requests.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                self._access_token = resp.json().get("access_token")
                logger.debug("Snov: token OAuth2 obtido com sucesso")
                return self._access_token
            else:
                logger.warning(
                    "Snov: falha ao obter token OAuth2",
                    extra={"status": resp.status_code},
                )
        except Exception as e:
            logger.error("Snov: erro ao autenticar", extra={"error": str(e)})

        return None

    def search_domain(
        self,
        domain: str,
        company_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca emails de um dominio via Snov.io.

        Args:
            domain: Dominio (ex: farroupilha.com.br)
            company_name: Nome da empresa para log
            limit: Maximo de resultados

        Returns:
            Lista de contatos: [{full_name, email, role, source}]
        """
        if not self.is_available():
            logger.debug("Snov credenciais nao configuradas - pulando")
            return []

        # Limpar dominio
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not domain or "." not in domain:
            return []

        token = self._get_access_token()
        if not token:
            return []

        try:
            params = {
                "domain": domain,
                "type": "personal",
                "limit": limit,
                "access_token": token,
            }
            resp = requests.get(
                f"{self.BASE_URL}/get-domain-emails-with-info",
                params=params,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                emails_data = data.get("emails", [])
                contacts: List[Dict[str, Any]] = []
                for item in emails_data:
                    email = item.get("email")
                    if not email:
                        continue
                    first = item.get("firstName") or ""
                    last = item.get("lastName") or ""
                    full_name = f"{first} {last}".strip() or "Responsavel"
                    position = item.get("position") or "Responsavel"
                    contacts.append({
                        "full_name": full_name,
                        "email": email,
                        "role": position,
                        "source": "snov",
                    })
                logger.info(
                    "Snov: busca concluida",
                    extra={"domain": domain, "found": len(contacts), "company": company_name},
                )
                return contacts

            elif resp.status_code == 401:
                logger.warning("Snov: token invalido ou expirado")
                self._access_token = None  # Resetar para proxima tentativa
            elif resp.status_code == 429:
                logger.warning("Snov: limite de creditos atingido")
            else:
                logger.warning(
                    "Snov: resposta inesperada",
                    extra={"status": resp.status_code, "domain": domain},
                )

        except requests.exceptions.Timeout:
            logger.warning("Snov: timeout na requisicao", extra={"domain": domain})
        except Exception as e:
            logger.error("Snov: erro inesperado", extra={"error": str(e), "domain": domain})

        return []


snov_client = SnovClient()
