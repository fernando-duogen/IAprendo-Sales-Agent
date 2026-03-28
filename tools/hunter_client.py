"""
HunterClient - Busca emails via Hunter.io Domain Search API.

Free tier: 25 buscas/mes.
Requer: HUNTER_API_KEY no .env (obtida em hunter.io -> Dashboard -> API)
"""
import requests
from typing import Dict, Any, List, Optional
from config.settings import settings
from utils.logger import logger


class HunterClient:
    """Cliente para Hunter.io Domain Search API.

    Busca todos os emails profissionais associados a um dominio.
    Hunter especializa-se em encontrar emails de contato de organizacoes.
    """

    BASE_URL = "https://api.hunter.io/v2"

    def __init__(self) -> None:
        self.api_key: str = settings.HUNTER_API_KEY

    def is_available(self) -> bool:
        """Verifica se a API esta configurada."""
        return bool(self.api_key)

    def search_domain(
        self,
        domain: str,
        company_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca emails associados a um dominio.

        Args:
            domain: Dominio (ex: farroupilha.com.br)
            company_name: Nome da empresa para log
            limit: Maximo de resultados

        Returns:
            Lista de contatos: [{full_name, email, role, source, confidence_score}]
        """
        if not self.is_available():
            logger.debug("Hunter API key nao configurada - pulando")
            return []

        # Limpar dominio
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not domain or "." not in domain:
            return []

        try:
            params = {
                "domain": domain,
                "api_key": self.api_key,
                "limit": limit,
            }
            resp = requests.get(
                f"{self.BASE_URL}/domain-search",
                params=params,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                emails_data = data.get("data", {}).get("emails", [])
                contacts: List[Dict[str, Any]] = []
                for item in emails_data:
                    email = item.get("value")
                    if not email:
                        continue
                    first = item.get("first_name") or ""
                    last = item.get("last_name") or ""
                    full_name = f"{first} {last}".strip() or "Responsavel"
                    position = item.get("position") or "Responsavel"
                    confidence = item.get("confidence", 0)
                    contacts.append({
                        "full_name": full_name,
                        "email": email,
                        "role": position,
                        "source": "hunter",
                        "confidence_score": confidence,
                    })
                logger.info(
                    "Hunter: busca concluida",
                    extra={"domain": domain, "found": len(contacts), "company": company_name},
                )
                return contacts

            elif resp.status_code == 401:
                logger.warning("Hunter: API key invalida ou expirada")
            elif resp.status_code == 429:
                logger.warning("Hunter: limite mensal de buscas atingido")
            else:
                logger.warning(
                    "Hunter: resposta inesperada",
                    extra={"status": resp.status_code, "domain": domain},
                )

        except requests.exceptions.Timeout:
            logger.warning("Hunter: timeout na requisicao", extra={"domain": domain})
        except Exception as e:
            logger.error("Hunter: erro inesperado", extra={"error": str(e), "domain": domain})

        return []


hunter_client = HunterClient()
