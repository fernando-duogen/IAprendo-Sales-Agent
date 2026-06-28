"""Regressao: buscar_escolas_por_enem nunca pode trazer escola SEM nota ENEM.

Bug original: uma escola so de educacao infantil (sem ENEM) apareceu como
"melhor nota do RS". Causa: o gate de amostra confiavel era desligavel pelo LLM
(only_confiavel=False) e a ordenacao jogava linhas NULL pro topo. Estes testes
travam o "piso de dado ENEM real": o handler so devolve escolas com
enem_media_geral utilizavel, mesmo com only_confiavel=False.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.tools import enem_tools as et


def _make_query(rows):
    q = MagicMock()
    for m in ["select", "eq", "ilike", "lte", "in_", "order", "limit", "is_", "gte"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    q.execute.return_value = SimpleNamespace(data=list(rows), count=len(rows))
    return q


def _row(inep, *, amostra, media, **extra):
    base = {
        "inep_code": inep,
        "enem_amostra_confiavel": amostra,
        "enem_media_geral": media,
        "enem_media_geral_sem_redacao": media,
        "enem_area_mais_fraca": "Matematica",
        "enem_potencial_melhoria": "Alto",
        "enem_gap_vs_peer_2025": -10.0 if media is not None else None,
        "enem_presentes": 40 if amostra else 0,
        "peer_trajetoria_6y": "Subindo",
        "peer_mun_nome": "Bage",
        "peer_uf_sigla": "RS",
        "enem_dependencia": "Privada",
    }
    base.update(extra)
    return base


# Mix realista: A=valida; B=confiavel mas media NULL; C=media real mas amostra
# NAO confiavel (sera suprimida pelo _strip_gated_fields -> media None); D=sem ENEM.
ROWS = [
    _row("43000001", amostra=True, media=520.0),     # KEEP
    _row("43000002", amostra=True, media=None),       # drop (sem nota)
    _row("43000003", amostra=False, media=480.0),     # drop (suprimida pelo gate)
    _row("43143288", amostra=None, media=None),       # drop (infantil, sem ENEM)
]

_NAMES = {
    "43000001": {"name": "COLEGIO BOM", "city": "Bage", "state": "RS",
                 "company_id": None, "fonte_nome": "censo_yearly"},
    "43000003": {"name": "COLEGIO PEQUENO", "city": "Bage", "state": "RS",
                 "company_id": None, "fonte_nome": "censo_yearly"},
    "43143288": {"name": "EEI BEM ME QUER", "city": "Bage", "state": "RS",
                 "company_id": None, "fonte_nome": "censo_yearly"},
}


def _run(params):
    with patch.object(et, "db") as mock_db, \
         patch.object(et, "_resolve_school_names", return_value=_NAMES):
        mock_db.client.table.return_value = _make_query(ROWS)
        return json.loads(et._handle_buscar_escolas_por_enem(params))


def test_so_escolas_com_nota_real_default():
    out = _run({"uf": "RS", "limite": 20})
    ineps = {e["inep"] for e in out["escolas"]}
    assert ineps == {"43000001"}
    assert all(e["media_geral"] is not None for e in out["escolas"])


def test_gate_nao_e_desligavel_only_confiavel_false():
    """O bug: com only_confiavel=False vazavam escolas sem ENEM. Nao pode mais."""
    out = _run({"uf": "RS", "only_confiavel": False, "limite": 20})
    ineps = {e["inep"] for e in out["escolas"]}
    assert "43143288" not in ineps  # EEI BEM ME QUER (infantil) NUNCA aparece
    assert ineps == {"43000001"}
    assert all(e["media_geral"] is not None for e in out["escolas"])


def test_escola_infantil_nunca_aparece():
    out = _run({"only_confiavel": False, "limite": 30})
    assert not any(e["inep"] == "43143288" for e in out["escolas"])
    assert not any(e["media_geral"] is None for e in out["escolas"])
