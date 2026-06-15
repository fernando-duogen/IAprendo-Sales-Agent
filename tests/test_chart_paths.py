# -*- coding: utf-8 -*-
"""Paths deterministicos dos graficos + flag RENDER_CHARTS (gerar fora do Cloud)."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.insight_charts import chart_storage_path, charts_renderable  # noqa: E402


def test_chart_storage_path_deterministico():
    # path FIXO (sem data) -> Cloud referencia sem regenerar
    assert chart_storage_path("22144714", "radar") == "22144714/radar.png"
    assert chart_storage_path("22144714", "gap") == "22144714/gap.png"
    assert chart_storage_path("22144714", "trend") == "22144714/trend_mat.png"


def test_render_charts_flag(monkeypatch):
    monkeypatch.setenv("RENDER_CHARTS", "false")
    assert charts_renderable() is False
    monkeypatch.setenv("RENDER_CHARTS", "FALSE")
    assert charts_renderable() is False
    monkeypatch.setenv("RENDER_CHARTS", "true")
    assert charts_renderable() is True
    monkeypatch.delenv("RENDER_CHARTS", raising=False)
    assert charts_renderable() is True  # default: renderiza (local/Oracle)


def test_autodetect_streamlit_cloud(monkeypatch):
    """Sem flag, mas rodando no Streamlit Cloud (/mount/src) -> nao renderiza."""
    import tools.insight_charts as ic
    monkeypatch.delenv("RENDER_CHARTS", raising=False)
    monkeypatch.setattr(ic.os.path, "isdir", lambda p: p == "/mount/src")
    assert ic.charts_renderable() is False
