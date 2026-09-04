"""
EnricherAgent - Enriquece dados de escolas em cascata com fallbacks.

Cascata: Apollo.io -> Snov.io -> Hunter.io -> Web Scraping (sempre disponivel).
Web Scraping e sempre a ultima opcao e nao consome creditos.
"""
import time
import requests
from urllib.parse import unquote
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from agents.base_agent import BaseAgent
from database.supabase_client import db
from config.settings import settings
from utils.logger import logger


class EnricherAgent(BaseAgent):
    """Enriquece dados de escolas em cascata com fallbacks.
    Busca: website, redes sociais, informacoes adicionais.
    """

    def __init__(self) -> None:
        super().__init__(agent_name="enricher")

    def execute(self, companies: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """Enriquece lista de escolas com dados adicionais.
        Args:
            companies: Lista de escolas qualificadas (status=qualified).
            force: Se True (kwarg), reenriquece sobrescrevendo campos ja
                   preenchidos (web/phone/coords/address vem do Google Places).
        Returns:
            Lista de escolas enriquecidas (count de mudancas).
        """
        force = bool(kwargs.get("force", False))
        results: List[Dict[str, Any]] = []
        _prog = kwargs.get("on_progress")
        for _i, company in enumerate(companies, start=1):
            try:
                self._tick(_prog, "enrich", _i, len(companies), company)
                result = self.enrich_company(company, force=force)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error("Erro ao enriquecer empresa",
                    extra={"company_id": company.get("id"), "error": str(e)})
        logger.info("Enriquecimento batch concluido",
            extra={"total": len(companies), "enriched": len(results), "force": force})
        return results

    def enrich_company(self, company: Dict[str, Any], force: bool = False) -> Optional[Dict[str, Any]]:
        """Enriquece uma empresa com Google Places (primary) + DuckDuckGo (fallback).

        Args:
            force: Se True, sobrescreve campos ja preenchidos (refetch).
                   Default False = preserva valores existentes (so preenche vazios).
        """
        company_id = company.get("id")
        school_name = company.get("name", "Desconhecida")
        city = company.get("city", "")
        state = company.get("state", "")
        logger.info("Enriquecendo empresa",
            extra={"company_id": company_id, "school_name": school_name, "force": force})
        updates: Dict[str, Any] = {}

        # === GOOGLE PLACES (primary) ===
        google_data = None
        try:
            from integrations.google_places import google_places
            if google_places.is_available():
                google_data = google_places.search_school_single(school_name, city, state)
                if google_data:
                    logger.info("Google Places: dados encontrados", extra={
                        "school": school_name, "telefone": google_data.get("telefone"),
                        "site": google_data.get("site"),
                    })
                    # force=True: sobrescreve. force=False: so preenche se vazio.
                    def _should_update(field_key: str) -> bool:
                        return force or not company.get(field_key)
                    if google_data.get("site") and _should_update("website"):
                        updates["website"] = google_data["site"]
                    if google_data.get("telefone") and _should_update("phone"):
                        updates["phone"] = google_data["telefone"]
                    if google_data.get("latitude") and _should_update("latitude"):
                        updates["latitude"] = google_data["latitude"]
                        updates["longitude"] = google_data["longitude"]
                    if google_data.get("endereco") and _should_update("address"):
                        updates["address"] = google_data["endereco"]
                    # Reputacao: JA vem paga no fieldMask (era descartada ate
                    # Ago/2026). Nota + qtd de avaliacoes = sinal de
                    # qualificacao; url = atalho pro Maps no painel.
                    # Sempre atualiza (nota muda com o tempo).
                    if google_data.get("rating") is not None:
                        updates["google_rating"] = google_data["rating"]
                    if google_data.get("reviews") is not None:
                        updates["google_reviews_count"] = google_data["reviews"]
                    if google_data.get("google_maps_url"):
                        updates["google_maps_url"] = google_data["google_maps_url"]
        except Exception as e:
            logger.debug(f"Google Places skip: {e}")

        # === DUCKDUCKGO (fallback — só se Google não retornou site) ===
        if not updates.get("website") and not company.get("website"):
            website = self._find_website(company)
            if website:
                updates["website"] = website

        if updates:
            self._update_company(company_id, {**updates, "status": "enriched"})
            company.update(updates)
            logger.info("Empresa enriquecida", extra={
                "company_id": company_id,
                "updates": list(updates.keys()),
                "fonte": "google_places" if google_data else "duckduckgo",
            })
        else:
            self._update_company(company_id, {"status": "enriched"})
        return company

    # Mapeamento de redes escolares conhecidas -> dominio principal
    KNOWN_CHAINS: Dict[str, str] = {
        "LA SALLE": "lasalle.edu.br",
        "MARISTA": "marista.edu.br",
        "ADVENTISTA": "adventistas.org",
        "SALESIANO": "salesiano.com.br",
        "JESUITA": "jesuita.org.br",
        "ANCHIETA": "colegioanchietapoa.com.br",
        "FARROUPILHA": "farroupilha.com.br",
        "ISRAELITA": "colegioIsraelitabrasileiro.com.br",
        "CONCORDIA": "concordia.org.br",
        "SINODAL": "colegiossinodal.com.br",
        "LUTHERANO": "ulbra.br",
        "JOAO XXIII": "cjxxiii.com.br",
        "NOSSA SENHORA": None,
    }

    def _find_website(self, company: Dict[str, Any]) -> Optional[str]:
        """Tenta encontrar website: (1) redes conhecidas, (2) DuckDuckGo com pausa."""
        name = (company.get("name") or "").upper()
        city = company.get("city", "")
        # 1. Verificar se eh rede escolar conhecida
        for chain_key, domain in self.KNOWN_CHAINS.items():
            if chain_key in name and domain:
                url = f"https://{domain}"
                logger.info("Website via rede conhecida", extra={"chain": chain_key, "url": url})
                return url
        # 2. Busca DuckDuckGo com pausa para evitar rate-limit
        query = f"{company.get('name', '')} {city} site oficial"
        try:
            time.sleep(4)  # Pausa de 4s para evitar bloqueio do DDG
            result = self._search_duckduckgo(query)
            if result:
                return result
        except Exception as e:
            logger.debug("DuckDuckGo search falhou", extra={"error": str(e)})
        return None

    def _search_duckduckgo(self, query: str) -> Optional[str]:
        """Busca no DuckDuckGo HTML para encontrar website da escola."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
            ddg_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            resp = requests.get(ddg_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                SKIP_DOMAINS = {"facebook.com", "twitter.com", "instagram.com",
                                "duckduckgo.com", "bing.com", "google.com",
                                "wikipedia.org", "inep.gov.br", "qedu.org.br"}
                for a in soup.select("a.result__url, a.result__a"):
                    href = a.get("href", "")
                    # Extract URL from DuckDuckGo redirect format
                    if "uddg=" in href:
                        raw = href.split("uddg=")[1].split("&")[0]
                        url = unquote(raw)
                    elif href.startswith("http"):
                        url = href
                    else:
                        continue
                    if not url.startswith("http"):
                        continue
                    # Skip social media and generic sites
                    domain = url.replace("https://", "").replace("http://", "").split("/")[0]
                    if any(skip in domain for skip in SKIP_DOMAINS):
                        continue
                    logger.debug("Website encontrado via DDG", extra={"url": url, "query": query})
                    return url
        except Exception as e:
            logger.debug("Falha no DuckDuckGo search", extra={"error": str(e)})
        return None

    def _try_apollo(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Tenta enriquecer via Apollo.io API (60 creditos/mes)."""
        apollo_key = settings.APOLLO_API_KEY
        if not apollo_key:
            return {}
        if not self._check_rate_limit("apollo"):
            logger.info("Limite Apollo atingido este mes")
            return {}
        try:
            db.insert_api_usage({"api_name": "apollo", "endpoint": "/organizations/enrich", "credits_used": 1})
            logger.info("Apollo enriquecimento tentado", extra={"company": company.get("name")})
            return {}
        except Exception as e:
            logger.warning("Apollo falhou", extra={"error": str(e)})
            return {}
