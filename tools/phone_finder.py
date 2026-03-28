"""
PhoneFinder - Busca numero de telefone de escolas via pesquisa web.

Estrategia: Pesquisa no DuckDuckGo por nome da escola + cidade + telefone.
Gratuito, sem API key necessaria.
"""
import re
import time
import requests
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup
from utils.logger import logger


# Padroes de telefone brasileiro
PHONE_PATTERNS = [
    r"\(\d{2}\)\s*\d{4,5}[-\s]?\d{4}",  # (51) 3333-4444 ou (51) 99999-4444
    r"\d{2}\s*\d{4,5}[-\s]?\d{4}",        # 51 3333-4444
    r"\+55\s*\d{2}\s*\d{4,5}[-\s]?\d{4}",  # +55 51 3333-4444
]


class PhoneFinder:
    """Encontra telefone de escolas via pesquisa web."""

    SEARCH_URL = "https://html.duckduckgo.com/html/"
    HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SchoolResearch/1.0)"}

    def find_phone(self, school_name: str, city: str = "Porto Alegre", state: str = "RS") -> Optional[str]:
        """Busca telefone de uma escola. Retorna o telefone encontrado ou None."""
        query = f"{school_name} {city} {state} telefone"
        try:
            resp = requests.post(
                self.SEARCH_URL,
                data={"q": query},
                headers=self.HEADERS,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.debug("Busca falhou", extra={"status": resp.status_code})
                return None
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            phone = self._extract_phone(text)
            if phone:
                logger.info("Telefone encontrado", extra={"school": school_name[:40], "phone": phone})
            return phone
        except Exception as e:
            logger.debug("Erro ao buscar telefone", extra={"school": school_name[:40], "error": str(e)})
            return None

    def _extract_phone(self, text: str) -> Optional[str]:
        """Extrai o primeiro telefone valido do texto."""
        for pattern in PHONE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                phone = matches[0]
                # Limpar e normalizar
                phone = re.sub(r"[^\d+]", "", phone.replace("+55", "").strip())
                if len(phone) >= 10:
                    return phone
        return None
    def enrich_company_phone(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Busca telefone de uma empresa e retorna dict com resultado."""
        school_name = company.get("name", "")
        city = company.get("city", "Porto Alegre")
        state = company.get("state", "RS")
        phone = company.get("phone", "")
        if phone:
            logger.debug("Telefone ja existe", extra={"school": school_name[:40]})
            return {"found": False, "existing": True, "phone": phone}
        found_phone = self.find_phone(school_name, city, state)
        time.sleep(1)  # Respeitar rate limit
        return {"found": bool(found_phone), "phone": found_phone}

    def process_batch(self, companies: list, max_per_run: int = 20) -> Dict[str, Any]:
        """Busca telefones de um lote de escolas. Respeita limite diario."""
        from database.supabase_client import db
        processed = 0
        found = 0
        skipped = 0
        companies_limited = companies[:max_per_run]
        for company in companies_limited:
            company_id = company.get("id")
            result = self.enrich_company_phone(company)
            if result.get("existing"):
                skipped += 1
            elif result.get("found") and result.get("phone"):
                try:
                    db.update_company(company_id, {"phone": result["phone"]})
                    found += 1
                    logger.info("Telefone salvo", extra={"company_id": company_id, "phone": result["phone"]})
                except Exception as e:
                    logger.error("Erro ao salvar telefone", extra={"error": str(e)})
            processed += 1
        return {"processed": processed, "found": found, "skipped": skipped}


phone_finder = PhoneFinder()