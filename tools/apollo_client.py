"""
ApolloClient - Busca contatos de decisores via Apollo.io People Search API.

Free tier: 60 creditos/mes.
Requer: APOLLO_API_KEY no .env (obtida em app.apollo.io -> Settings -> API Keys)
"""
import requests
from typing import Dict, Any, List, Optional
from config.settings import settings
from utils.logger import logger


class ApolloClient:
    """Cliente para Apollo.io People Search API.

    Busca diretores e coordenadores pelo dominio da escola.
    Retorna lista de contatos com email quando disponivel.
    """

    BASE_URL = "https://api.apollo.io/v1"

    # Cargos relevantes para escolas brasileiras (pt + en para maior cobertura)
    TARGET_TITLES: List[str] = [
        "Diretor", "Diretora",
        "Coordenador Pedagogico", "Coordenadora Pedagogica",
        "Gestor de Tecnologia", "Gestora de Tecnologia",
        "Secretario", "Secretaria",
        "Director", "Principal", "Head of School",
    ]

    def __init__(self) -> None:
        self.api_key: str = settings.APOLLO_API_KEY

    def is_available(self) -> bool:
        """Verifica se a API esta configurada."""
        return bool(self.api_key)

    def search_contacts(
        self,
        domain: str,
        company_name: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca contatos de uma escola pelo dominio.

        Args:
            domain: Dominio da escola (ex: farroupilha.com.br)
            company_name: Nome da escola para log
            limit: Maximo de contatos a retornar

        Returns:
            Lista de contatos: [{full_name, email, role, source}]
        """
        if not self.is_available():
            logger.debug("Apollo API key nao configurada - pulando")
            return []

        # Limpar dominio (remover protocolo e caminhos)
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip()
        if not domain or "." not in domain:
            return []

        try:
            headers = {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "x-api-key": self.api_key,
            }
            payload: Dict[str, Any] = {
                "api_key": self.api_key,
                "q_organization_domains": [domain],
                "person_titles": self.TARGET_TITLES,
                "per_page": limit,
                "page": 1,
            }
            resp = requests.post(
                f"{self.BASE_URL}/people/search",
                json=payload,
                headers=headers,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                people = data.get("people", [])
                contacts: List[Dict[str, Any]] = []
                for person in people:
                    email: str = person.get("email", "")
                    # Ignorar emails nao revelados (plano gratuito Apollo)
                    if not email or "email_not_unlocked" in email:
                        continue
                    first = person.get("first_name") or ""
                    last = person.get("last_name") or ""
                    full_name = f"{first} {last}".strip() or "Responsavel"
                    title = person.get("title") or "Responsavel"
                    contacts.append({
                        "full_name": full_name,
                        "email": email,
                        "role": title,
                        "source": "apollo",
                    })
                logger.info(
                    "Apollo: busca concluida",
                    extra={"domain": domain, "found": len(contacts), "company": company_name},
                )
                return contacts

            elif resp.status_code == 401:
                logger.warning("Apollo: API key invalida ou sem permissao")
            elif resp.status_code == 422:
                logger.debug("Apollo: parametros invalidos", extra={"domain": domain})
            elif resp.status_code == 429:
                logger.warning("Apollo: limite de requisicoes atingido (rate limit)")
            else:
                logger.warning(
                    "Apollo: resposta inesperada",
                    extra={"status": resp.status_code, "domain": domain},
                )

        except requests.exceptions.Timeout:
            logger.warning("Apollo: timeout na requisicao", extra={"domain": domain})
        except Exception as e:
            logger.error("Apollo: erro inesperado", extra={"error": str(e), "domain": domain})

        return []


apollo_client = ApolloClient()
