"""Testes: benchmark do OPR/radar cai de municipio -> UF -> Brasil quando o
municipio tem poucas escolas (< _MIN_BENCH).

Bug: Colegio Regina Coeli (Veranopolis/RS) — cidade pequena com 2 privadas
confiaveis (< 3) — gerava OPR SEM radar e SEM notas por area (o gate
has_data = bench_count >= 3 zerava tudo). Com o fallback, cai pro RS (262
privadas) e a comparacao/radar aparecem; a caption reflete o nivel real.
"""
from unittest.mock import patch

from tools import insight_charts as ic


def _fake(counts):
    """Fabrica um _bench_query falso: counts = {'municipio':n,'estado':n,'brasil':n}."""
    # **kwargs: a assinatura ganhou excluir_inep/enem_ano (auditoria Ago/2026 —
    # a escola nao pode entrar no proprio benchmark, nem misturar safras).
    def _q(mun, uf, dep, metrics, **kwargs):
        if mun:
            scope = "municipio"
        elif uf:
            scope = "estado"
        else:
            scope = "brasil"
        n = counts.get(scope, 0)
        return ({"enem_media_geral": 600.0} if n else {}), n
    return _q


def test_municipio_escasso_cai_para_uf():
    with patch.object(ic, "_bench_query",
                      _fake({"municipio": 2, "estado": 262, "brasil": 5000})):
        data, count, scope = ic._fetch_benchmark(
            "Veranopolis", "RS", "Privada", ["enem_media_geral"])
    assert scope == "estado"
    assert count == 262


def test_municipio_suficiente_nao_cai():
    with patch.object(ic, "_bench_query",
                      _fake({"municipio": 49, "estado": 262, "brasil": 5000})):
        data, count, scope = ic._fetch_benchmark(
            "Teresina", "PI", "Privada", ["enem_media_geral"])
    assert scope == "municipio"
    assert count == 49


def test_cai_ate_brasil_quando_uf_tambem_escasso():
    with patch.object(ic, "_bench_query",
                      _fake({"municipio": 1, "estado": 2, "brasil": 4000})):
        data, count, scope = ic._fetch_benchmark(
            "CidadeX", "AC", "Federal", ["enem_media_geral"])
    assert scope == "brasil"
    assert count == 4000


def test_retorna_melhor_quando_nenhum_atinge_minimo():
    # caso degenerado: nem Brasil tem >=3 -> devolve o maior count achado
    with patch.object(ic, "_bench_query",
                      _fake({"municipio": 1, "estado": 2, "brasil": 0})):
        data, count, scope = ic._fetch_benchmark(
            "X", "RR", "Municipal", ["enem_media_geral"])
    assert count == 2 and scope == "estado"


def test_retorna_tripla_sempre():
    with patch.object(ic, "_bench_query", _fake({"estado": 10})):
        out = ic._fetch_benchmark("", "RS", "Estadual", ["enem_media_geral"])
    assert isinstance(out, tuple) and len(out) == 3
