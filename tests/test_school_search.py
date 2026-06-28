"""Testes da busca de escola por nome no IAlex (acento + parcial + nome+cidade/uf).

Cobre o fix de regressao da busca:
- `_resolve_company_strict`: nome acento-insensitivel no CRM, desambiguacao por
  cidade/uf, fallback para a base MEC (search_mec_catalog) retornando INEP, e
  caminho exato por INEP intacto.
- `_handle_consultar_escolas`: filtro de nome acento-insensitivel no CRM.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent import brain


def _make_db(crm_rows=None, mec_rows=None):
    """db mockado: companies retorna crm_rows; search_mec_catalog retorna mec_rows."""
    db = MagicMock()
    q = MagicMock()
    for m in ["select", "eq", "ilike", "order", "limit", "gte", "in_", "is_", "neq"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    q.execute.return_value = SimpleNamespace(
        data=list(crm_rows or []), count=len(crm_rows or [])
    )
    db.client.table.return_value = q
    db.search_mec_catalog.return_value = {
        "rows": list(mec_rows or []), "total": len(mec_rows or [])
    }
    db.catalog_available.return_value = True
    return db


def _row(id, name, city="Teresina", state="PI", inep="11111111", **extra):
    base = {
        "id": id, "name": name, "city": city, "state": state,
        "inep_code": inep, "bairro": "Centro", "admin_dependency": "Privada",
    }
    base.update(extra)
    return base


SJL = _row("u-sjl", "COLÉGIO SÃO JOSÉ LESTE", inep="22144714")
KENNEDY_POA = _row("u-k1", "COLEGIO KENNEDY", city="Porto Alegre", state="RS", inep="43000001")
KENNEDY_TER = _row("u-k2", "COLEGIO JOHN KENNEDY", city="Teresina", state="PI", inep="22000002")


# ---------------------------------------------------------------------------
# _resolve_company_strict — nome
# ---------------------------------------------------------------------------

def test_acento_insensitive_sem_acento():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL])):
        company, err = brain._resolve_company_strict({"escola_nome": "sao jose leste"})
    assert err is None
    assert company["id"] == "u-sjl"


def test_acento_insensitive_com_acento():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL])):
        company, err = brain._resolve_company_strict({"escola_nome": "São José Leste"})
    assert err is None
    assert company["id"] == "u-sjl"


def test_busca_parcial():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL, KENNEDY_POA])):
        company, err = brain._resolve_company_strict({"escola_nome": "kennedy"})
    assert err is None
    assert company["id"] == "u-k1"


def test_nome_ambiguo_sem_local_pede_desambiguacao():
    with patch.object(brain, "db", _make_db(crm_rows=[KENNEDY_POA, KENNEDY_TER])):
        company, err = brain._resolve_company_strict({"escola_nome": "kennedy"})
    assert company is None
    payload = json.loads(err)
    assert payload.get("ambiguidade") is True
    assert payload.get("n_matches") == 2


def test_nome_mais_cidade_desambigua():
    with patch.object(brain, "db", _make_db(crm_rows=[KENNEDY_POA, KENNEDY_TER])):
        company, err = brain._resolve_company_strict(
            {"escola_nome": "kennedy", "cidade": "teresina"}
        )
    assert err is None
    assert company["id"] == "u-k2"


def test_nome_mais_uf_desambigua():
    with patch.object(brain, "db", _make_db(crm_rows=[KENNEDY_POA, KENNEDY_TER])):
        company, err = brain._resolve_company_strict(
            {"escola_nome": "kennedy", "uf": "rs"}
        )
    assert err is None
    assert company["id"] == "u-k1"


def test_fallback_base_retorna_inep():
    """Escola fora do CRM -> sugere INEP da base MEC (fallback consertado)."""
    mec = [{
        "inep_code": "33044556", "name": "ESCOLA NOVA FUTURO",
        "city": "Recife", "state": "PE", "admin_dependency": "Privada",
    }]
    with patch.object(brain, "db", _make_db(crm_rows=[SJL], mec_rows=mec)):
        company, err = brain._resolve_company_strict(
            {"escola_nome": "escola nova futuro"}
        )
    assert company is None
    payload = json.loads(err)
    assert "nao esta no CRM" in payload.get("erro", "")
    assert payload.get("inep_sugerido") == "33044556"


def test_zero_matches_em_lugar_nenhum():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL], mec_rows=[])):
        company, err = brain._resolve_company_strict(
            {"escola_nome": "escola que nao existe xyz"}
        )
    assert company is None
    payload = json.loads(err)
    assert "Nenhuma escola encontrada" in payload.get("erro", "")


def test_inep_exato_intacto():
    """O caminho exato por INEP nao deve regredir."""
    with patch.object(brain, "db", _make_db(crm_rows=[SJL])):
        company, err = brain._resolve_company_strict({"inep": "22144714"})
    assert err is None
    assert company["id"] == "u-sjl"


def test_sem_parametro_retorna_none_none():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL])):
        company, err = brain._resolve_company_strict({})
    assert company is None and err is None


# ---------------------------------------------------------------------------
# _handle_consultar_escolas — filtro de nome acento-insensitivel
# ---------------------------------------------------------------------------

def test_consultar_escolas_nome_acento_insensitivel():
    with patch.object(brain, "db", _make_db(crm_rows=[SJL, KENNEDY_POA])):
        out = json.loads(brain._handle_consultar_escolas({"nome": "sao jose"}))
    assert out.get("fonte") == "banco_crm"
    assert out.get("total") == 1
    assert out["escolas"][0]["nome"] == "COLÉGIO SÃO JOSÉ LESTE"


def test_consultar_escolas_fallback_base_quando_crm_vazio():
    mec = [{
        "inep_code": "33044556", "name": "ESCOLA NOVA FUTURO",
        "city": "Recife", "state": "PE",
    }]
    with patch.object(brain, "db", _make_db(crm_rows=[SJL], mec_rows=mec)):
        out = json.loads(brain._handle_consultar_escolas({"nome": "escola nova futuro"}))
    # Caiu na base MEC (nao achou no CRM) -> traz escolas com aviso
    assert out.get("escolas")
    assert "MEC" in (out.get("aviso") or "")
