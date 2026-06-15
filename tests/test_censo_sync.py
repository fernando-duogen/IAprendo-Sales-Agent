# -*- coding: utf-8 -*-
"""Mapeamento school_censo_yearly -> matriculas/docentes da company.

Garante que o sync (usado na importacao via Recomendadas + backfill) traduz os
campos qt_mat_*/qt_doc_bas do censo pros campos matriculas_*/total_* da company.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import _censo_row_to_company_matriculas  # noqa: E402


def test_mapeia_campos_principais():
    censo = {
        "qt_mat_bas": 1211, "qt_mat_fund": 536, "qt_mat_fund_af": 536,
        "qt_mat_fund_ai": 0, "qt_mat_med": 675, "qt_mat_inf": 0,
        "qt_mat_eja": 0, "qt_doc_bas": 43,
    }
    out = _censo_row_to_company_matriculas(censo)
    assert out["total_matriculas"] == 1211
    assert out["matriculas_fund_af"] == 536
    assert out["matriculas_medio"] == 675
    assert out["matriculas_fundamental"] == 536
    assert out["total_docentes"] == 43


def test_ignora_none_e_nao_inventa():
    out = _censo_row_to_company_matriculas({"qt_mat_bas": 100, "qt_mat_med": None})
    assert out == {"total_matriculas": 100}  # None nao vira 0; campos ausentes fora


def test_row_vazia():
    assert _censo_row_to_company_matriculas({}) == {}
    assert _censo_row_to_company_matriculas(None) == {}
