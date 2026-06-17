# -*- coding: utf-8 -*-
"""Health-check ciente do Cloud: checks que batem em localhost (webhook :5001,
Evolution :8080) viram 'N/A' no Streamlit Cloud em vez de falso-vermelho."""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.health_check as hc  # noqa: E402


def test_localhost_checks_viram_na_no_cloud(monkeypatch):
    # Simula o Streamlit Community Cloud (repo montado em /mount/src)
    monkeypatch.setattr(hc.os.path, "isdir", lambda p: p == "/mount/src")
    assert hc._on_streamlit_cloud() is True
    w = hc._check_webhook_flask()
    b = hc._check_bridge_whatsapp()
    # status neutro (nao critico) + detalhe explicativo
    assert w["status"] == "unknown" and "Cloud" in w["detail"]
    assert b["status"] == "unknown" and "Cloud" in b["detail"]


def test_fora_do_cloud_checa_localhost(monkeypatch):
    # Sem /mount/src -> nao e Cloud -> tenta localhost (nao retorna o texto de Cloud)
    monkeypatch.setattr(hc.os.path, "isdir", lambda p: False)
    assert hc._on_streamlit_cloud() is False
    w = hc._check_webhook_flask()  # sem servidor local => critical, nao "N/A no Cloud"
    assert "N/A no Cloud" not in w.get("detail", "")
