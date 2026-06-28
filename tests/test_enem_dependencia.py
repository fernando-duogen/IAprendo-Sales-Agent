"""Testes: filtro de dependencia entende 'publica' como GRUPO (Federal+Estadual+
Municipal), nao so 'Estadual'.

Bug: "melhor escola publica do RS" trazia a melhor Estadual (Tiradentes Ijui,
702) em vez da melhor publica real (UFSM Politecnico, Federal, 720) — o filtro
excluia as Federais. _apply_dependencia_filter trata publica/privada como grupo.
"""
from unittest.mock import MagicMock

from agent.tools import enem_tools as et

_PUB = ["Federal", "Estadual", "Municipal"]


def _q():
    q = MagicMock()
    q.in_.return_value = q
    q.eq.return_value = q
    return q


def test_publica_usa_grupo_federal_estadual_municipal():
    q = _q()
    et._apply_dependencia_filter(q, "publica")
    q.in_.assert_called_once_with("enem_dependencia", _PUB)
    q.eq.assert_not_called()


def test_publica_com_acento_e_caixa():
    for raw in ["Pública", "PUBLICA", "público", "escola publica"]:
        q = _q()
        et._apply_dependencia_filter(q, raw)
        q.in_.assert_called_once_with("enem_dependencia", _PUB)


def test_privada_vira_eq_privada():
    for raw in ["privada", "Privada", "particular"]:
        q = _q()
        et._apply_dependencia_filter(q, raw)
        q.eq.assert_called_once_with("enem_dependencia", "Privada")
        q.in_.assert_not_called()


def test_valor_exato_estadual_continua_eq():
    q = _q()
    et._apply_dependencia_filter(q, "Estadual")
    q.eq.assert_called_once_with("enem_dependencia", "Estadual")
    q.in_.assert_not_called()


def test_valor_exato_federal_canonicaliza():
    q = _q()
    et._apply_dependencia_filter(q, "federal")
    q.eq.assert_called_once_with("enem_dependencia", "Federal")


def test_vazio_nao_filtra():
    for raw in [None, "", "   "]:
        q = _q()
        assert et._apply_dependencia_filter(q, raw) is q
        q.in_.assert_not_called()
        q.eq.assert_not_called()
