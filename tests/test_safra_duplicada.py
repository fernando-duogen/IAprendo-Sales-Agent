# -*- coding: utf-8 -*-
"""Safra ENEM duplicada: "sem dado novo" != "estagnou".

Contexto (Ago/2026): 141 escolas (5 no CRM) tem a linha de 2025 em
`school_enem_yearly` como COPIA exata da de 2024 — mesma media ate a 4a casa e
mesmo numero de presentes. Sao escolas que NAO tiveram resultado proprio na
safra nova (nao atingiram amostra minima).

Sem tratamento, "quanto a escola evoluiu de 2024 p/ 2025?" responde 0.0 e o
usuario le "estagnou" — conclusao comercial errada.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.tools.enem_tools import _mesma_medicao, _fetch_enem_series  # noqa: E402


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------
def test_detecta_copia_exata():
    a = {"enem_media_geral": 579.5985, "enem_presentes": 26}
    b = {"enem_media_geral": 579.5985, "enem_presentes": 26}
    assert _mesma_medicao(a, b) is True


def test_aceita_string_e_decimal():
    """O Supabase devolve numerico como string."""
    a = {"enem_media_geral": "579.5985", "enem_presentes": "26"}
    b = {"enem_media_geral": 579.5985, "enem_presentes": 26}
    assert _mesma_medicao(a, b) is True


def test_evolucao_real_nao_e_marcada():
    a = {"enem_media_geral": 579.5985, "enem_presentes": 26}
    b = {"enem_media_geral": 585.1000, "enem_presentes": 30}
    assert _mesma_medicao(a, b) is False


def test_mesma_media_com_presentes_diferentes_nao_e_copia():
    """Coincidencia improvavel, mas com turma diferente e medicao diferente."""
    a = {"enem_media_geral": 600.0, "enem_presentes": 26}
    b = {"enem_media_geral": 600.0, "enem_presentes": 41}
    assert _mesma_medicao(a, b) is False


def test_defensivo_com_none_e_lixo():
    assert _mesma_medicao(None, {"enem_media_geral": 1}) is False
    assert _mesma_medicao({}, {}) is False
    assert _mesma_medicao({"enem_media_geral": None}, {"enem_media_geral": None}) is False
    assert _mesma_medicao({"enem_media_geral": "abc"}, {"enem_media_geral": "abc"}) is False


# ---------------------------------------------------------------------------
# Ranking de evolucao: escola sem dado novo FICA DE FORA (e e contada)
# ---------------------------------------------------------------------------
def test_ranking_exclui_copias(monkeypatch):
    import agent.tools.enem_tools as et

    linhas = {
        2024: [
            {"inep_code": "43000001", "enem_media_geral": 500.0, "enem_presentes": 30,
             "enem_dependencia": "Privada", "enem_amostra_confiavel": True},
            {"inep_code": "43000002", "enem_media_geral": 579.5985, "enem_presentes": 26,
             "enem_dependencia": "Privada", "enem_amostra_confiavel": True},
        ],
        2025: [
            {"inep_code": "43000001", "enem_media_geral": 560.0, "enem_presentes": 33,
             "enem_dependencia": "Privada", "enem_amostra_confiavel": True},
            # copia exata de 2024 -> sem resultado proprio
            {"inep_code": "43000002", "enem_media_geral": 579.5985, "enem_presentes": 26,
             "enem_dependencia": "Privada", "enem_amostra_confiavel": True},
        ],
    }
    monkeypatch.setattr(et, "_resolve_school_names",
                        lambda ineps: {i: {"name": f"Escola {i}"} for i in ineps})

    # _fetch_year e uma closure interna: mockamos a camada de banco
    class _Not:
        """Reproduz a cadeia do PostgREST: q.not_.is_(col, "null")."""

        def __init__(self, q):
            self._q = q

        def is_(self, *a, **k):
            return self._q

    class _Q:
        def __init__(self, ano=None):
            self.ano = ano

        def select(self, *a, **k):
            return self

        def eq(self, col, val):
            if col == "vintage_enem":
                self.ano = val
            return self

        @property
        def not_(self):
            return _Not(self)

        def like(self, *a, **k):
            return self

        def in_(self, *a, **k):
            return self

        def range(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def execute(self):
            return type("R", (), {"data": linhas.get(self.ano, [])})()

    monkeypatch.setattr(et.db, "client",
                        type("C", (), {"table": lambda self, t: _Q()})())

    out = json.loads(et._handle_ranking_evolucao_enem({
        "area": "geral", "de_ano": 2024, "para_ano": 2025, "uf": "RS",
    }))

    ineps = [r["inep"] for r in out.get("resultado", [])]
    assert "43000001" in ineps, "escola com evolucao real deveria estar no ranking"
    assert "43000002" not in ineps, "copia de safra nao pode entrar como 'estagnada'"
    assert out.get("excluidas_sem_dado_novo") == 1
    assert "nao ha o que comparar" in out.get("nota_exclusao", "")


# ---------------------------------------------------------------------------
# Serie individual: a safra copiada vem MARCADA
# ---------------------------------------------------------------------------
def test_serie_marca_safra_repetida(monkeypatch):
    import agent.tools.enem_tools as et

    raw = [
        {"vintage_enem": 2024, "enem_amostra_confiavel": True,
         "enem_media_geral": 579.5985, "enem_presentes": 26},
        {"vintage_enem": 2025, "enem_amostra_confiavel": True,
         "enem_media_geral": 579.5985, "enem_presentes": 26},
    ]

    class _Q:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def execute(self):
            return type("R", (), {"data": raw})()

    monkeypatch.setattr(et.db, "client",
                        type("C", (), {"table": lambda self, t: _Q()})())

    serie = _fetch_enem_series("43000002")
    assert serie[0].get("dado_repetido_da_safra_anterior") is None
    assert serie[1].get("dado_repetido_da_safra_anterior") is True
    assert "NAO interprete como estabilidade" in serie[1].get("aviso", "")
