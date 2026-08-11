# -*- coding: utf-8 -*-
"""Regressao dos achados de ANALISE/NUMERO ERRADO (auditoria Ago/2026).

Foco: a plataforma nao pode APRESENTAR numero errado com cara de certo.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent.brain as brain_mod  # noqa: E402
from agent.tools.enem_tools import campo_por_safra, trajetoria_peer  # noqa: E402

_ANALYTICS = ROOT / "dashboard" / "pages" / "8_📈_Analytics.py"


def _codigo(path: Path) -> str:
    """Fonte SEM comentarios — os fixes citam o bug antigo de proposito."""
    import re
    return "\n".join(
        re.sub(r"#.*$", "", linha) for linha in path.read_text(encoding="utf-8").splitlines()
    )


# ---------------------------------------------------------------------------
# Safra ENEM: linhas em 2024 nao podem "sumir" (colunas _2025 sao NULL nelas)
# ---------------------------------------------------------------------------
def test_campo_por_safra_usa_ano_da_linha():
    row_2024 = {"enem_ano": 2024, "enem_gap_vs_peer_2024": -44.5,
                "enem_gap_vs_peer_2025": None}
    assert campo_por_safra(row_2024, "enem_gap_vs_peer") == -44.5


def test_campo_por_safra_prefere_2025_quando_e_a_safra():
    row = {"enem_ano": 2025, "enem_gap_vs_peer_2025": 10.0,
           "enem_gap_vs_peer_2024": -44.5}
    assert campo_por_safra(row, "enem_gap_vs_peer") == 10.0


def test_campo_por_safra_sem_ano_cai_para_mais_recente():
    row = {"enem_gap_vs_peer_2025": None, "enem_gap_vs_peer_2024": -1.0}
    assert campo_por_safra(row, "enem_gap_vs_peer") == -1.0
    assert campo_por_safra({}, "enem_gap_vs_peer") is None
    assert campo_por_safra(None, "x") is None


def test_trajetoria_peer_cai_de_6y_para_5y():
    assert trajetoria_peer({"peer_trajetoria_6y": "Subindo"}) == "Subindo"
    assert trajetoria_peer({"peer_trajetoria_6y": None,
                            "peer_trajetoria_5y": "Caindo"}) == "Caindo"
    assert trajetoria_peer({}) is None


def test_classificar_prioridade_funciona_com_safra_2024():
    """Bug: escolas com enem_ano=2024 tinham gap/trajetoria só nas colunas _2024
    e _5y -> nunca eram classificadas em P1/P2/P3 (sumiam do ranking)."""
    from agent.tools.enem_tools import _classificar_prioridade
    row = {
        "enem_amostra_confiavel": True,
        "enem_ano": 2024,
        "enem_dependencia": "Privada",
        "enem_presentes": 50,
        "enem_gap_vs_peer_2024": -44.47,   # so a coluna de 2024 preenchida
        "enem_gap_vs_peer_2025": None,
        "peer_trajetoria_5y": "Subindo",   # so a de 5 anos preenchida
        "peer_trajetoria_6y": None,
    }
    assert _classificar_prioridade(row) == "P2"


# ---------------------------------------------------------------------------
# Funil: nao pode inventar gargalo em etapa inexistente
# ---------------------------------------------------------------------------
def test_funil_nao_usa_status_inexistentes():
    """Bug: consultava 'sent'/'opened'/'replied' em companies (nao existem) e
    recomendava gargalo numa etapa impossivel."""
    import inspect
    src = inspect.getsource(brain_mod._handle_funil_vendas)
    # etapas do funil = status REAIS do CHECK de companies
    assert '("responded", "Responderam")' in src
    for inexistente in ['("sent",', '("opened",', '("replied",']:
        assert inexistente not in src, f"funil ainda usa status inexistente: {inexistente}"


def test_funil_gargalo_honesto_sem_dados(monkeypatch):
    """Sem volume, o funil nao pode afirmar gargalo."""
    class _R:
        count = 0
        data = []

    class _Q:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def not_(self):
            return self

        def limit(self, *a, **k):
            return self

        def execute(self):
            return _R()

    class _Tbl(_Q):
        @property
        def not_(self):
            return self

        def is_(self, *a, **k):
            return self

    monkeypatch.setattr(brain_mod.db, "client",
                        type("C", (), {"table": lambda self, t: _Tbl()})())
    out = json.loads(brain_mod._handle_funil_vendas({}))
    assert out.get("gargalo") is None
    assert "volume suficiente" in out.get("recomendacao", "")


# ---------------------------------------------------------------------------
# Custo: nada de centavo fantasma
# ---------------------------------------------------------------------------
def test_analytics_sem_fallback_de_custo_fantasma():
    """Bug: `float(x or 0) or 0.02` somava 2 centavos para custo 0/NULL —
    inflava o total em ~39% e passou a somar por FALHA de API."""
    src = _codigo(_ANALYTICS)
    assert "or 0.02" not in src, "ainda ha fallback de custo fantasma"
    assert 'cost_usd") is not None' in src or 'cost_usd"] is not None' in src


def test_analytics_taxas_nao_truncam():
    """Bug: divisao inteira fazia qualquer taxa < 1% virar '0%'."""
    src = _codigo(_ANALYTICS)
    assert "* 100 //" not in src, "ainda ha taxa com divisao inteira"


def test_analytics_aplica_filtro_de_periodo():
    """Bug: cutoff_iso era calculado e NUNCA usado — todos os KPIs all-time."""
    src = _codigo(_ANALYTICS)
    assert src.count("cutoff_iso") >= 2, "cutoff_iso continua sem uso"
    assert "_no_periodo" in src


# ---------------------------------------------------------------------------
# Benchmark do OPR/radar: peer group nao pode conter a propria escola
# ---------------------------------------------------------------------------
def test_bench_query_exclui_a_propria_escola_e_pagina():
    import inspect
    import tools.insight_charts as ic
    src = inspect.getsource(ic._bench_query)
    assert "neq" in src, "benchmark ainda inclui a propria escola"
    assert "range(" in src, "benchmark ainda nao pagina (clamp de 1000)"
    assert 'eq("enem_ano"' in src, "benchmark ainda mistura safras"


def test_comparativo_avisa_safras_diferentes():
    import inspect
    import tools.comparison_report as cr
    src = inspect.getsource(cr.generate_comparison_html) \
        if hasattr(cr, "generate_comparison_html") else \
        (ROOT / "tools" / "comparison_report.py").read_text(encoding="utf-8")
    assert "safras diferentes" in src.lower() or "_aviso_safra" in src
