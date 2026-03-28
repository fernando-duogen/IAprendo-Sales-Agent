"""
Geocoder - Converte enderecos em coordenadas lat/long.

Usa Nominatim (OpenStreetMap) - 100% gratuito, sem API key.
Limite: 1 request/segundo (respeitado automaticamente).
"""
import time
import requests
from typing import Optional, Tuple, Dict, Any, List
from utils.logger import logger


class Geocoder:
    """Geocodifica enderecos usando Nominatim (OpenStreetMap)."""

    BASE_URL = "https://nominatim.openstreetmap.org/search"
    HEADERS = {"User-Agent": "IAprendo-SalesAgent/1.0 (contato@duogen.com.br)"}

    def geocode(self, address: str, city: str = "Porto Alegre", state: str = "RS",
                country: str = "Brazil") -> Optional[Tuple[float, float]]:
        """Converte endereco em (latitude, longitude). Retorna None se nao encontrar."""
        query = f"{address}, {city}, {state}, {country}"
        params = {"q": query, "format": "json", "limit": 1, "countrycodes": "br"}
        try:
            resp = requests.get(self.BASE_URL, params=params, headers=self.HEADERS, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    lat = float(data[0]["lat"])
                    lon = float(data[0]["lon"])
                    logger.debug("Geocodificado", extra={"address": address[:40], "lat": lat, "lon": lon})
                    return (lat, lon)
            return None
        except Exception as e:
            logger.debug("Erro geocoding", extra={"address": address[:40], "error": str(e)})
            return None

    def geocode_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Geocodifica uma empresa. Retorna dict com resultado."""
        if company.get("latitude") and company.get("longitude"):
            return {"found": False, "existing": True}
        address = company.get("address", "")
        city = company.get("city", "Porto Alegre")
        state = company.get("state", "RS")
        if not address:
            return {"found": False, "error": "sem endereco"}
        coords = self.geocode(address, city, state)
        time.sleep(1)  # Nominatim: max 1 req/seg
        if coords:
            return {"found": True, "latitude": coords[0], "longitude": coords[1]}
        return {"found": False}

    def process_batch(self, companies: List[Dict[str, Any]], max_per_run: int = 50) -> Dict[str, Any]:
        """Geocodifica um lote de escolas."""
        from database.supabase_client import db
        processed = found = skipped = 0
        for company in companies[:max_per_run]:
            company_id = company.get("id")
            result = self.geocode_company(company)
            if result.get("existing"):
                skipped += 1
            elif result.get("found"):
                try:
                    db.update_company(company_id, {
                        "latitude": result["latitude"],
                        "longitude": result["longitude"],
                    })
                    found += 1
                except Exception as e:
                    logger.error("Erro ao salvar coords", extra={"error": str(e)})
            processed += 1
        return {"processed": processed, "found": found, "skipped": skipped}


geocoder = Geocoder()