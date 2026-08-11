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
# userRatingCount vem no MESMO SKU do rating (ja pago): nota sem qtd de
# avaliacoes engana (4.8 com 3 reviews != 4.8 com 300).
DEFAULT_FIELDS = (
    "places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
    "places.internationalPhoneNumber,places.websiteUri,places.rating,"
    "places.userRatingCount,places.location,places.types,places.googleMapsUri"
)

# Custos por SKU (US$/chamada) — usados so p/ registrar em api_usage.
# Antes o geocode era reportado como 0.032 (~6x o real), inflando o painel.
_COST_SEARCH = 0.032
_COST_GEOCODE = 0.005


class GooglePlacesClient:
    """Client para Google Places API (New) + Geocoding API."""

    def __init__(self) -> None:
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        # ENABLE_GEOCODING agora DESLIGA de verdade. Era config decorativa:
        # nenhum caminho que chama o Google a consultava, entao setar
        # ENABLE_GEOCODING=false nao impedia nenhuma chamada paga.
        _flag = os.getenv("ENABLE_GEOCODING", "true").strip().lower() != "false"
        self._enabled = bool(self.api_key) and _flag
        # Cache em memoria por processo: evita PAGAR duas vezes a mesma
        # pesquisa (ex.: enricher e depois whatsapp_finder na mesma escola,
        # ou reprocessar um lote). Chave = query normalizada.
        self._cache: Dict[str, Any] = {}
        self._cache_hits = 0
        if not self._enabled:
            logger.info(
                "Google Places desabilitado "
                + ("(ENABLE_GEOCODING=false)" if self.api_key and not _flag
                   else "(GOOGLE_MAPS_API_KEY vazio)")
            )

    def is_available(self) -> bool:
        return self._enabled

    @staticmethod
    def _cache_key(prefixo: str, texto: str) -> str:
        return f"{prefixo}:{' '.join(str(texto or '').lower().split())}"

    def cache_stats(self) -> Dict[str, int]:
        """Diagnostico: quantas chamadas o cache poupou nesta execucao."""
        return {"entradas": len(self._cache), "hits": self._cache_hits}

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
            "reviews": p.get("userRatingCount"),
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

        # Cache: mesma escola consultada 2x no mesmo processo nao paga 2x
        ckey = self._cache_key("search", query)
        if ckey in self._cache:
            self._cache_hits += 1
            logger.debug("Google Places cache hit", extra={"query": query})
            return self._cache[ckey][:limit]

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
                self._log_usage("searchText", 0, success=False,
                                erro=f"HTTP {r.status_code}")
                return []

            data = r.json()
            places = data.get("places", [])

            # Registrar uso
            self._log_usage("searchText", len(places))

            parsed = [self._parse_place(p) for p in places]
            self._cache[ckey] = parsed
            return parsed[:limit]
        except Exception as e:
            logger.error(f"Google Places search erro: {e}")
            self._log_usage("searchText", 0, success=False, erro=str(e)[:120])
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
        """Busca escolas próximas a uma coordenada.

        NAO E USADO em producao (auditoria Ago/2026: zero chamadores no repo).
        A busca por proximidade do produto usa a tool `escolas_proximas`
        (Haversine sobre o CRM/MEC, sem custo). Mantido porque e superficie
        paga do Places que pode ser util em descoberta de campo — mas se for
        chamado, LEMBRE que cada consulta custa (~US$0,032).
        """
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

        ckey = self._cache_key("geocode", address)
        if ckey in self._cache:
            self._cache_hits += 1
            return self._cache[ckey]

        try:
            r = requests.get(
                GEOCODE_BASE,
                params={"address": address, "key": self.api_key, "language": "pt-BR"},
                timeout=10,
            )
            if r.status_code != 200:
                self._log_usage("geocode", 0, success=False,
                                erro=f"HTTP {r.status_code}")
                return None

            data = r.json()
            results = data.get("results", [])
            if not results:
                # Chamada FOI cobrada mesmo sem resultado — registrar.
                self._log_usage("geocode", 0)
                return None

            loc = results[0].get("geometry", {}).get("location", {})
            self._log_usage("geocode", 1)
            out = {
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "formatted_address": results[0].get("formatted_address", ""),
                "fonte": "google_geocoding",
            }
            self._cache[ckey] = out
            return out
        except Exception as e:
            logger.error(f"Google Geocoding erro: {e}")
            self._log_usage("geocode", 0, success=False, erro=str(e)[:120])
            return None

    # =========================================================================
    # Logging de uso
    # =========================================================================

    def _log_usage(
        self,
        endpoint: str,
        results_count: int,
        success: bool = True,
        erro: str = "",
    ) -> None:
        """Registra uso da API para tracking de custo.

        Custo por SKU (geocode e ~6x mais barato que a busca — antes ambos
        eram reportados como 0.032, inflando o painel). Falhas tambem sao
        registradas (com cost_usd=0): antes sumiam, escondendo problemas.
        """
        try:
            from database.supabase_client import db
            ctx: Dict[str, Any] = {"results": results_count}
            if erro:
                ctx["erro"] = erro
            db.insert_api_usage({
                "api_name": "google_maps",
                "endpoint": endpoint,
                "credits_used": 1 if success else 0,
                "success": success,
                "context": ctx,
                # Requisicao que falhou (HTTP != 200 / excecao) nao e cobrada
                "cost_usd": 0.0 if not success else (
                    _COST_GEOCODE if endpoint == "geocode" else _COST_SEARCH
                ),
            })
        except Exception:
            pass


# Singleton
google_places = GooglePlacesClient()
