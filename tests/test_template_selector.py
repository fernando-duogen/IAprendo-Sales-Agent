"""Testes de utils/template_selector.py — selecao automatica por alvo.

A deteccao de ENEM consulta o banco; semeamos `_enem_cache` para isolar
os testes (sem DB).
"""
import pytest

from utils import template_selector as ts
from utils.template_selector import (
    detectar_audience,
    detectar_dados,
    _data_requirement_met,
    _data_richness,
    selecionar_template,
    matriz_cobertura,
)


class TestDetectarAudience:
    def test_sem_contato_generico(self):
        assert detectar_audience(None) == "generico"

    @pytest.mark.parametrize("source", ["placeholder", "email_pattern"])
    def test_source_nao_pessoa_generico(self, source):
        assert detectar_audience({"full_name": "Maria", "source": source}) == "generico"

    def test_nome_vazio_generico(self):
        assert detectar_audience({"full_name": ""}) == "generico"

    def test_nome_generico_explicito(self):
        assert detectar_audience({"full_name": "Secretaria"}) == "generico"

    @pytest.mark.parametrize("email", [
        "secretaria@escola.com", "contato2@escola.com", "info@escola.com",
    ])
    def test_email_localpart_generico(self, email):
        assert detectar_audience({"full_name": "Maria Silva", "email": email}) == "generico"

    def test_nominal_com_email_pessoal(self):
        assert detectar_audience(
            {"full_name": "Maria Silva", "email": "maria.silva@escola.com"}
        ) == "nominal"

    def test_nominal_sem_email(self):
        assert detectar_audience({"full_name": "Joao Pereira"}) == "nominal"


class TestDataRequirementMet:
    @pytest.mark.parametrize("profile,mat,enem,expected", [
        (None, False, False, True),
        ("nenhum", False, False, True),
        ("ambos", True, True, True),
        ("ambos", True, False, False),
        ("ambos", False, True, False),
        ("matriculas", True, False, True),
        ("matriculas", False, False, False),
        ("enem", False, True, True),
        ("enem", False, False, False),
        ("xpto", False, False, True),  # desconhecido = wildcard (nao bloqueia)
    ])
    def test(self, profile, mat, enem, expected):
        assert _data_requirement_met(profile, mat, enem) == expected


class TestDataRichness:
    def test(self):
        assert _data_richness("ambos") == 3
        assert _data_richness("matriculas") == 2
        assert _data_richness("enem") == 2
        assert _data_richness("nenhum") == 0
        assert _data_richness(None) == 0


class TestDetectarDados:
    def test_matriculas_dos_campos(self):
        ts._enem_cache["999"] = False
        assert detectar_dados({"inep_code": "999", "total_matriculas": 120}) == {
            "matriculas": True, "enem": False,
        }

    def test_sem_dados(self):
        ts._enem_cache["888"] = False
        assert detectar_dados({"inep_code": "888"}) == {
            "matriculas": False, "enem": False,
        }

    def test_enem_do_cache(self):
        ts._enem_cache["777"] = True
        assert detectar_dados({"inep_code": "777", "matriculas_medio": 50}) == {
            "matriculas": True, "enem": True,
        }


def _tpls():
    return [
        {"id": "t_nom_ambos", "name": "nom_ambos", "audience_type": "nominal",
         "data_profile": "ambos", "is_active": True},
        {"id": "t_gen_nenhum", "name": "gen_nenhum", "audience_type": "generico",
         "data_profile": "nenhum", "is_active": True, "is_default": True},
    ]


class TestSelecionarTemplate:
    def test_escolhe_ideal_nominal_com_ambos_dados(self):
        ts._enem_cache["1"] = True
        tpl = selecionar_template(
            {"inep_code": "1", "total_matriculas": 100},
            {"full_name": "Maria Silva", "email": "maria@e.com"},
            _tpls(),
        )
        assert tpl["id"] == "t_nom_ambos"

    def test_degrada_para_generico_sem_dados_e_contato_generico(self):
        ts._enem_cache["2"] = False
        tpl = selecionar_template({"inep_code": "2"}, None, _tpls())
        assert tpl["id"] == "t_gen_nenhum"

    def test_exclui_template_que_exige_dado_ausente(self):
        # escola sem dados + contato nominal: nom_ambos exige dados (exclui),
        # gen_nenhum eh generico != nominal (exclui) -> None
        ts._enem_cache["3"] = False
        tpl = selecionar_template(
            {"inep_code": "3"},
            {"full_name": "Maria Silva", "email": "maria@e.com"},
            _tpls(),
        )
        assert tpl is None

    def test_lista_vazia_none(self):
        assert selecionar_template({"inep_code": "x"}, None, []) is None


class TestMatrizCobertura:
    def test_marca_combos_cobertos(self):
        m = matriz_cobertura([
            {"name": "A", "audience_type": "nominal", "data_profile": "ambos", "is_active": True},
            {"name": "B", "audience_type": "generico", "data_profile": "nenhum", "is_active": True},
        ])
        by = {(r["audience"], r["data_profile"]): r for r in m}
        assert by[("nominal", "ambos")]["coberto"] is True
        assert by[("generico", "nenhum")]["coberto"] is True
        assert by[("nominal", "enem")]["coberto"] is False

    def test_wildcard_cobre_tudo(self):
        m = matriz_cobertura([
            {"name": "W", "audience_type": None, "data_profile": None, "is_active": True},
        ])
        assert all(r["coberto"] for r in m)
