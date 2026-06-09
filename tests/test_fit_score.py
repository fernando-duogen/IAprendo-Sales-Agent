"""Testes de utils/fit_score.py — robustez a None/NaN (regressao do crash
'float object has no attribute lower' na aba Escolas)."""
import pytest

from utils.fit_score import calcular_fit_score, _num, _txt

NAN = float("nan")


class TestSafeHelpers:
    @pytest.mark.parametrize("v,exp", [
        (None, 0), (NAN, 0), ("", 0), ("nan", 0), ("NaN", 0),
        ("123", 123), (45.0, 45), (7, 7), ("abc", 0), ("12.9", 12),
    ])
    def test_num(self, v, exp):
        assert _num(v) == exp

    @pytest.mark.parametrize("v,exp", [
        (None, ""), (NAN, ""), ("nan", ""), ("Privada", "Privada"),
        (123, "123"), ("  x  ", "x"),
    ])
    def test_txt(self, v, exp):
        assert _txt(v) == exp


class TestCalcularFitScore:
    def test_nan_em_todos_os_campos_nao_quebra(self):
        # Era exatamente isto que quebrava: row.to_dict() do pandas traz NaN.
        r = calcular_fit_score({
            "matriculas_fund_af": 100, "matriculas_medio": 50,
            "categoria_privada": NAN, "nivel_tecnologico": NAN,
            "qt_coordenadores": NAN, "admin_dependency": NAN, "fonte_dados": NAN,
        })
        assert isinstance(r["score"], int)
        assert r["level"] in ("alto", "medio", "baixo")

    def test_dict_vazio(self):
        assert calcular_fit_score({})["level"] == "sem_dados"

    def test_catalogo_inep_sem_dados(self):
        r = calcular_fit_score({"matriculas_fund_af": 100, "fonte_dados": "catalogo_inep"})
        assert r["level"] == "sem_dados"

    def test_valido(self):
        r = calcular_fit_score({
            "matriculas_fund_af": 200, "matriculas_medio": 300,
            "categoria_privada": "Privada Particular", "nivel_tecnologico": "Alto",
            "qt_coordenadores": 2, "admin_dependency": "Privada",
            "fonte_dados": "censo_2025",
        })
        assert r["score"] == 70 and r["level"] == "alto"

    def test_admin_dependency_nan_com_categoria_vazia(self):
        # categoria vazia + admin_dependency NaN -> nao pode quebrar no .lower()
        r = calcular_fit_score({
            "matriculas_fund_af": 100, "matriculas_medio": 0,
            "categoria_privada": "", "admin_dependency": NAN, "fonte_dados": "censo_2025",
        })
        assert isinstance(r["score"], int)
