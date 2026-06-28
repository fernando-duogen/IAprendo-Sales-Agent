"""Testes: P0 (ordenacao de buscar_escolas_por_enem) + P1 (ranking_evolucao_enem).

P0 — "melhor nota" nao pode cair em ordem por gap:
  - sem filtro de oportunidade -> ordena por enem_media_geral desc (melhores).
  - com filtro de oportunidade (potencial/area_fraca/...) -> gap asc (leads).
  - ordenar_por='media' / 'gap' forca.
P1 — ranking_evolucao_enem (evolucao da nota PROPRIA entre anos, cross-escola):
  - delta = nota para_ano - nota de_ano.
  - so escolas confiaveis nos DOIS anos e com a nota presente nos dois.
  - ordem desc=mais evoluiu / asc=mais caiu.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.tools import enem_tools as et


# ---------------------------------------------------------------------------
# P0 — ordenacao do buscar_escolas_por_enem
# ---------------------------------------------------------------------------

def _order_capture_db():
    db = MagicMock()
    q = MagicMock()
    for m in ["select", "eq", "ilike", "lte", "in_", "order", "limit", "gte"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    q.execute.return_value = SimpleNamespace(data=[], count=0)
    db.client.table.return_value = q
    return db, q


def _order_call(params):
    db, q = _order_capture_db()
    with patch.object(et, "db", db), \
         patch.object(et, "_resolve_school_names", return_value={}):
        et._handle_buscar_escolas_por_enem(params)
    args, kwargs = q.order.call_args
    return args[0], kwargs.get("desc"), kwargs.get("nullsfirst")


def test_sem_filtro_oportunidade_ordena_por_media():
    col, desc, nf = _order_call({"uf": "RS"})
    assert col == "enem_media_geral"
    assert desc is True
    assert nf is False


def test_com_filtro_oportunidade_ordena_por_gap():
    col, desc, _ = _order_call({"uf": "RS", "potencial": "Alto"})
    assert col == "enem_gap_vs_peer_2025"
    assert desc is False


def test_ordenar_por_media_forca_mesmo_com_filtro():
    col, desc, _ = _order_call({"uf": "RS", "potencial": "Alto", "ordenar_por": "media"})
    assert col == "enem_media_geral"
    assert desc is True


def test_ordenar_por_gap_forca_sem_filtro():
    col, desc, _ = _order_call({"uf": "RS", "ordenar_por": "gap"})
    assert col == "enem_gap_vs_peer_2025"
    assert desc is False


# ---------------------------------------------------------------------------
# P1 — ranking_evolucao_enem
# ---------------------------------------------------------------------------

class _FakeYearly:
    """Fake da query school_enem_yearly: filtra por vintage_enem + amostra."""

    def __init__(self, rows_by_vintage):
        self._rbv = rows_by_vintage
        self._v = None
        self._conf = None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        if col == "vintage_enem":
            self._v = val
        if col == "enem_amostra_confiavel":
            self._conf = val
        return self

    @property
    def not_(self):
        outer = self

        class _N:
            def is_(self, *a, **k):
                return outer
        return _N()

    def like(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        rows = list(self._rbv.get(self._v, []))
        if self._conf is True:
            rows = [r for r in rows if r.get("enem_amostra_confiavel") is True]
        return SimpleNamespace(data=rows, count=len(rows))


def _y(inep, red, conf=True):
    return {
        "inep_code": inep, "enem_media_redacao": red,
        "enem_amostra_confiavel": conf, "enem_dependencia": "Estadual",
        "enem_presentes": 40,
    }


# A: +100 ; B: -50 ; C: so 2025 (exclui) ; D: 2025 nao confiavel (exclui) ;
# E: redacao None em 2024 (exclui)
ROWS = {
    2024: [_y("43000001", 500.0), _y("43000002", 700.0),
           _y("43000004", 480.0), _y("43000005", None)],
    2025: [_y("43000001", 600.0), _y("43000002", 650.0), _y("43000003", 620.0),
           _y("43000004", 620.0, conf=False), _y("43000005", 600.0)],
}
_NAMES = {i: {"name": f"Escola {i}", "city": "Bage", "state": "RS",
              "company_id": None, "fonte_nome": "censo_yearly"} for i in
          ["43000001", "43000002", "43000003", "43000004", "43000005"]}


def _run_evolucao(params):
    with patch.object(et, "db") as mock_db, \
         patch.object(et, "_resolve_school_names", return_value=_NAMES):
        mock_db.client.table.return_value = _FakeYearly(ROWS)
        return json.loads(et._handle_ranking_evolucao_enem(params))


def test_evolucao_desc_mais_evoluiu():
    out = _run_evolucao({"area": "redacao", "uf": "RS", "ordem": "desc"})
    res = out["resultado"]
    assert out["n_consideradas"] == 2  # so A e B (confiaveis nos 2 anos, com nota)
    assert res[0]["inep"] == "43000001"
    assert res[0]["delta"] == 100.0
    ineps = {r["inep"] for r in res}
    assert ineps == {"43000001", "43000002"}
    # excluidos: C (so 1 ano), D (2025 nao confiavel), E (nota None)
    assert "43000003" not in ineps
    assert "43000004" not in ineps
    assert "43000005" not in ineps


def test_evolucao_asc_mais_caiu():
    out = _run_evolucao({"area": "redacao", "uf": "RS", "ordem": "asc"})
    assert out["resultado"][0]["inep"] == "43000002"
    assert out["resultado"][0]["delta"] == -50.0


def test_evolucao_default_anos_2024_2025():
    out = _run_evolucao({"area": "redacao", "uf": "RS"})
    assert out["de_ano"] == 2024 and out["para_ano"] == 2025


def test_uf_invalida_retorna_erro():
    out = _run_evolucao({"area": "redacao", "uf": "ZZ"})
    assert "erro" in out and "ZZ" in out["erro"]


def test_area_invalida_retorna_erro():
    out = _run_evolucao({"area": "biologia", "uf": "RS"})
    assert "erro" in out and "areas_validas" in out
