"""
Google Places Client — Busca dados de escolas via Google Places API (New).

Retorna: nome, endereço completo, telefone, site, rating, coordenadas.
Usado como fonte PRIMARIA de enriquecimento. DuckDuckGo é fallback.

Custo: ~$0.032 por busca com detalhes. $200 grátis/mês = ~6000 buscas.

Usage:
    from integrations.google_places import google_places

    # Buscar escola por nome + cidade
    result = google_places.search_school("Colegio Marista", "Porto Alegre", "RS")

    # Buscar escolas proximas
    results = google_places.nearby_schools(-30.03, -51.21, radius_m=2000)

    # Geocodificar endereco
    coords = google_places.geocode("Rua X, 123, Porto Alegre, RS")
"""
import os
import requests
from typing import Any, Dict, List, Optional

from utils.logger import logger

API_BASE = "https://places.googleapis.com/v1"
GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"

# Campos a buscar (controla custo — Basic + Contact = $0.032/req)
DEFAULT_FIELDS = (
    "places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
    "places.internationalPhoneNumber,places.websiteUri,places.rating,"
    "places.location,places.types,places.googleMapsUri"
)


class GooglePlacesClient:
    """Client para Google Places API (New) + Geocoding API."""

    def __init__(self) -> None:
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        self._enabled = bool(self.api_key)
        if not self._enabled:
            logger.info("Google Places desabilitado (GOOGLE_MAPS_API_KEY vazio)")

    def is_available(self) -> bool:
        return self._enabled

    def _headers(self, fields: str = DEFAULT_FIELDS) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": fields,
        }

    def _parse_place(self, p: dict) -> Dict[str, Any]:
        """Converte resultado da API para formato padronizado."""
        loc = p.get("location", {})
        return {
            "nome": (p.get("displayName") or {}).get("text", ""),
            "endereco": p.get("formattedAddress", ""),
            "telefone": p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
            "site": p.get("websiteUri"),
            "rating": p.get("rating"),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "google_maps_url": p.get("googleMapsUri"),
            "tipos": p.get("types", []),
            "fonte": "google_places",
        }

    # =========================================================================
    # Busca por texto (escola + cidade)
    # =========================================================================

    def search_school(
        self,
        school_name: str,
        city: str = "",
        state: str = "",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca escola por nome + localização. Retorna lista de resultados."""
        if not self._enabled:
            return []

        query = f"{school_name} {city} {state}".strip()
        try:
            r = requests.post(
                f"{API_BASE}/places:searchText",
                headers=self._headers(),
                json={
                    "textQuery": query,
                    "languageCode": "pt-BR",
                    "maxResultCount": min(limit, 20),
                },
                timeout=15,
            )
            if r.status_code != 200:
                logger.warning(f"Google Places search: {r.status_code} {r.text[:200]}")
                return []

            data = r.json()
            places = data.get("places", [])

            # Registrar uso
            self._log_usage("searchText", len(places))

            return [self._parse_place(p) for p in places[:limit]]
        except Exception as e:
            logger.error(f"Google Places search erro: {e}")
            return []

    def search_school_single(
        self, school_name: str, city: str = "", state: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Busca e retorna o melhor resultado (1 escola)."""
        results = self.search_school(school_name, city, state, limit=3)
        if not results:
            return None
        # Priorizar resultado que contém o nome da escola
        name_lower = school_name.lower()
        for r in results:
            if name_lower[:10] in (r.get("nome") or "").lower():
                return r
        return results[0]

    # =========================================================================
    # Busca por proximidade
    # =========================================================================

    def nearby_schools(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 2000,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Busca escolas próximas a uma coordenada."""
        if not self._enabled:
            return []

        try:
            r = requests.post(
                f"{API_BASE}/places:searchText",
                headers=self._headers(),
                json={
                    "textQuery": "escola colégio",
                    "languageCode": "pt-BR",
                    "maxResultCount": min(limit, 20),
                    "locationBias": {
                        "circle": {
                            "center": {"latitude": latitude, "longitude": longitude},
                            "radius": float(radius_m),
                        }
                    },
                },
                timeout=15,
            )
            if r.status_code != 200:
                return []

            data = r.json()
            places = data.get("places", [])
            self._log_usage("nearbySearch", len(places))
            return [self._parse_place(p) for p in places[:limit]]
        except Exception as e:
            logger.error(f"Google Places nearby erro: {e}")
            return []

    # =========================================================================
    # Geocodificação
    # =========================================================================

    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """Geocodifica um endereço. Retorna {latitude, longitude, formatted_address}."""
        if not self._enabled:
            return None

        try:
            r = requests.get(
                GEOCODE_BASE,
                params={"address": address, "key": self.api_key, "language": "pt-BR"},
                timeout=10,
            )
            if r.status_code != 200:
                return None

            data = r.json()
            results = data.get("results", [])
            if not results:
                return None

            loc = results[0].get("geometry", {}).get("location", {})
            self._log_usage("geocode", 1)
            return {
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "formatted_address": results[0].get("formatted_address", ""),
                "fonte": "google_geocoding",
            }
        except Exception as e:
            logger.error(f"Google Geocoding erro: {e}")
            return None

    # =========================================================================
    # Logging de uso
    # =========================================================================

    def _log_usage(self, endpoint: str, results_count: int) -> None:
        """Registra uso da API para tracking de custo."""
        try:
            from database.supabase_client import db
            db.insert_api_usage({
                "api_name": "google_maps",
                "endpoint": endpoint,
                "credits_used": 1,
                "success": True,
                "context": {"results": results_count},
                "cost_usd": 0.032,  # Basic + Contact fields
            })
        except Exception:
            pass


# Singleton
google_places = GooglePlacesClient()
