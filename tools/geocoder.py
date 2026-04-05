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

    def geocode_company(self, company: Dict[str, Any], use_perplexity_fallback: bool = False) -> Dict[str, Any]:
        """Geocodifica uma empresa.

        Args:
            company: Dict com dados da escola (id, name, address, city, state)
            use_perplexity_fallback: Se True, quando Nominatim falha, pede endereco
                                      ao Perplexity e tenta novamente.

        Retorna dict com:
            - found: True/False
            - latitude, longitude: coordenadas (se found)
            - method: 'nominatim_direct' ou 'perplexity_fallback' ou '' (se falhou)
            - error: mensagem de erro (se falhou)
            - perplexity_address: endereco encontrado pelo Perplexity (se usado)
        """
        if company.get("latitude") and company.get("longitude"):
            return {"found": False, "existing": True}
        address = company.get("address", "")
        city = company.get("city", "Porto Alegre")
        state = company.get("state", "RS")
        school_name = company.get("name", "")

        # Tentativa 1: Nominatim com endereco do banco
        if address:
            coords = self.geocode(address, city, state)
            time.sleep(1)  # Nominatim: max 1 req/seg
            if coords:
                return {
                    "found": True,
                    "latitude": coords[0],
                    "longitude": coords[1],
                    "method": "nominatim_direct",
                }

        # Tentativa 2: Fallback Perplexity -> pedir endereco mais completo
        if use_perplexity_fallback and school_name:
            try:
                from tools.perplexity_browser import perplexity_browser
                if not perplexity_browser.is_available():
                    return {"found": False, "error": "sem endereco e perplexity indisponivel"}
                logger.info(f"Geocoder: fallback Perplexity para {school_name}")
                ppx_address = perplexity_browser.search_school_address(school_name, city, state)
                if not ppx_address:
                    return {"found": False, "error": "perplexity nao encontrou endereco"}
                # Retry Nominatim com o novo endereco
                coords2 = self.geocode(ppx_address, city, state)
                time.sleep(1)
                if coords2:
                    return {
                        "found": True,
                        "latitude": coords2[0],
                        "longitude": coords2[1],
                        "method": "perplexity_fallback",
                        "perplexity_address": ppx_address,
                    }
                return {
                    "found": False,
                    "error": "nominatim falhou mesmo com endereco do perplexity",
                    "perplexity_address": ppx_address,
                }
            except Exception as e:
                logger.error(f"Erro no fallback Perplexity: {e}")
                return {"found": False, "error": f"perplexity falhou: {str(e)[:100]}"}

        # Sem endereco e sem fallback
        if not address:
            return {"found": False, "error": "sem endereco"}
        return {"found": False, "error": "nominatim nao encontrou"}

    def process_batch(
        self,
        companies: List[Dict[str, Any]],
        max_per_run: int = 50,
        use_perplexity_fallback: bool = False,
    ) -> Dict[str, Any]:
        """Geocodifica um lote de escolas.

        Args:
            companies: Lista de escolas
            max_per_run: Max escolas para processar
            use_perplexity_fallback: Se True, usa Perplexity quando Nominatim falha
        """
        from database.supabase_client import db
        processed = found = skipped = fallback_used = 0
        failed_details = []
        for company in companies[:max_per_run]:
            company_id = company.get("id")
            company_name = company.get("name", "?")
            result = self.geocode_company(company, use_perplexity_fallback=use_perplexity_fallback)
            if result.get("existing"):
                skipped += 1
            elif result.get("found"):
                try:
                    updates = {
                        "latitude": result["latitude"],
                        "longitude": result["longitude"],
                    }
                    # Se veio do Perplexity, atualizar tambem o endereco no banco
                    if result.get("method") == "perplexity_fallback" and result.get("perplexity_address"):
                        updates["address"] = result["perplexity_address"]
                        fallback_used += 1
                    db.update_company(company_id, updates)
                    found += 1
                except Exception as e:
                    logger.error("Erro ao salvar coords", extra={"error": str(e)})
                    failed_details.append({"name": company_name, "error": f"salvar: {e}"})
            else:
                failed_details.append({
                    "name": company_name,
                    "error": result.get("error", "desconhecido"),
                    "perplexity_address": result.get("perplexity_address"),
                })
            processed += 1
        return {
            "processed": processed,
            "found": found,
            "skipped": skipped,
            "failed": processed - found - skipped,
            "fallback_used": fallback_used,
            "failed_details": failed_details,
        }


geocoder = Geocoder()