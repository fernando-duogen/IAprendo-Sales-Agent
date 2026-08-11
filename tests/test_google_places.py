# -*- coding: utf-8 -*-
"""Testes das melhorias do Google Places (Ago/2026).

Cobre: cache (nao pagar 2x), captura de rating/reviews/maps_url (dados que ja
vinham pagos e eram descartados), custo por SKU e registro de falhas.
Zero chamadas de rede — requests e monkeypatched.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import integrations.google_places as gp  # noqa: E402


class _FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


_PLACE = {
    "displayName": {"text": "Colegio Teste"},
    "formattedAddress": "Rua X, 1, Porto Alegre, RS",
    "nationalPhoneNumber": "(51) 3333-3333",
    "websiteUri": "https://teste.com.br",
    "rating": 4.7,
    "userRatingCount": 128,
    "location": {"latitude": -30.03, "longitude": -51.21},
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "types": ["school"],
}


def _client(monkeypatch, resp, contador=None):
    """Client com chave fake e requests mockado."""
    c = gp.GooglePlacesClient()
    c.api_key = "fake-key"
    c._enabled = True

    def _post(*a, **k):
        if contador is not None:
            contador.append(1)
        return resp

    monkeypatch.setattr(gp.requests, "post", _post)
    monkeypatch.setattr(gp, "logger", gp.logger)
    return c


# ---------------------------------------------------------------------------
# Captura dos campos que antes eram descartados
# ---------------------------------------------------------------------------
def test_parse_captura_rating_reviews_e_url():
    c = gp.GooglePlacesClient()
    out = c._parse_place(_PLACE)
    assert out["rating"] == 4.7
    assert out["reviews"] == 128           # NOVO — antes nem era pedido
    assert out["google_maps_url"] == "https://maps.google.com/?cid=1"
    assert out["telefone"] == "(51) 3333-3333"


def test_fieldmask_pede_user_rating_count():
    """A contagem vem no mesmo SKU do rating — sem ela a nota engana."""
    assert "places.userRatingCount" in gp.DEFAULT_FIELDS
    assert "places.rating" in gp.DEFAULT_FIELDS


# ---------------------------------------------------------------------------
# Cache — nao pagar 2x pela mesma escola
# ---------------------------------------------------------------------------
def test_cache_evita_segunda_chamada(monkeypatch):
    chamadas = []
    resp = _FakeResp(payload={"places": [_PLACE]})
    c = _client(monkeypatch, resp, chamadas)
    monkeypatch.setattr(c, "_log_usage", lambda *a, **k: None)

    r1 = c.search_school("Colegio Teste", "Porto Alegre", "RS")
    r2 = c.search_school("Colegio Teste", "Porto Alegre", "RS")
    assert len(chamadas) == 1               # so 1 request de verdade
    assert r1 == r2
    assert c.cache_stats()["hits"] == 1


def test_cache_normaliza_espacos_e_caixa(monkeypatch):
    chamadas = []
    c = _client(monkeypatch, _FakeResp(payload={"places": [_PLACE]}), chamadas)
    monkeypatch.setattr(c, "_log_usage", lambda *a, **k: None)
    c.search_school("Colegio Teste", "Porto Alegre", "RS")
    c.search_school("COLEGIO   TESTE", "porto alegre", "rs")
    assert len(chamadas) == 1


def test_cache_nao_mistura_escolas(monkeypatch):
    chamadas = []
    c = _client(monkeypatch, _FakeResp(payload={"places": [_PLACE]}), chamadas)
    monkeypatch.setattr(c, "_log_usage", lambda *a, **k: None)
    c.search_school("Escola A", "Porto Alegre", "RS")
    c.search_school("Escola B", "Porto Alegre", "RS")
    assert len(chamadas) == 2


# ---------------------------------------------------------------------------
# Custo por SKU + registro de falhas
# ---------------------------------------------------------------------------
def test_custo_geocode_e_menor_que_busca(monkeypatch):
    registros = []
    c = gp.GooglePlacesClient()
    c._enabled = True
    monkeypatch.setattr(
        c, "_log_usage",
        lambda ep, n, success=True, erro="": registros.append((ep, success)),
    )
    # valores dos SKUs
    assert gp._COST_GEOCODE < gp._COST_SEARCH
    assert gp._COST_GEOCODE == 0.005 and gp._COST_SEARCH == 0.032


def test_falha_http_registra_sem_custo(monkeypatch):
    registros = []

    def _fake_insert(payload):
        registros.append(payload)

    class _DB:
        @staticmethod
        def insert_api_usage(p):
            registros.append(p)

    import database.supabase_client as sc
    monkeypatch.setattr(sc, "db", _DB)

    c = _client(monkeypatch, _FakeResp(status=500, text="erro"))
    out = c.search_school("X", "Y", "RS")
    assert out == []
    assert registros, "falha deveria ter sido registrada em api_usage"
    reg = registros[-1]
    assert reg["success"] is False
    assert reg["cost_usd"] == 0.0          # requisicao falha nao e cobrada
    assert "erro" in reg["context"]


def test_sem_chave_nao_chama_e_degrada(monkeypatch):
    c = gp.GooglePlacesClient()
    c._enabled = False
    assert c.is_available() is False
    assert c.search_school("X", "Y", "RS") == []
    assert c.geocode("Rua X") is None
