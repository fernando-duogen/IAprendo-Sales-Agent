"""Testes do retry de envio em tools/brevo_sender.py.

Mocka requests.post (sem rede). Valida: sucesso na 1a, retry em 5xx
transitorio, falha apos esgotar tentativas, e SEM retry em 4xx.
"""
import pytest
from unittest.mock import patch, MagicMock

from tools.brevo_sender import BrevoSender


@pytest.fixture(autouse=True)
def _no_sleep():
    """Evita os backoffs reais (2s/4s) — testes instantaneos."""
    with patch("time.sleep", lambda *a, **k: None):
        yield


def _resp(status, json_data=None, text=""):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data or {}
    m.text = text
    return m


def _sender():
    s = BrevoSender()
    s.api_key = "test-key"
    s._enabled = True
    return s


def _send(s):
    return s.send_email(
        to_email="x@y.com", to_name="X", subject="s", body="b",
        from_email="a@b.com", from_name="A", attachments=[],
    )


@patch("tools.brevo_sender.requests.post")
def test_sucesso_primeira_tentativa(mpost):
    mpost.return_value = _resp(201, {"messageId": "<id>"})
    r = _send(_sender())
    assert r["success"] is True
    assert r["message_id"] == "<id>"
    assert mpost.call_count == 1


@patch("tools.brevo_sender.requests.post")
def test_retry_em_5xx_depois_sucesso(mpost):
    mpost.side_effect = [
        _resp(522, text="<html>522</html>"),
        _resp(503, text="busy"),
        _resp(201, {"messageId": "<id2>"}),
    ]
    r = _send(_sender())
    assert r["success"] is True
    assert mpost.call_count == 3  # tentou de novo ate passar


@patch("tools.brevo_sender.requests.post")
def test_falha_apos_esgotar_tentativas(mpost):
    mpost.return_value = _resp(522, text="down")
    r = _send(_sender())
    assert r["success"] is False
    assert r.get("status_code") == 522
    assert mpost.call_count == 3


@patch("tools.brevo_sender.requests.post")
def test_4xx_sem_retry(mpost):
    mpost.return_value = _resp(400, text="bad sender")
    r = _send(_sender())
    assert r["success"] is False
    assert r.get("status_code") == 400
    assert mpost.call_count == 1  # 4xx nao repete


@patch("tools.brevo_sender.requests.post")
def test_excecao_de_rede_depois_sucesso(mpost):
    mpost.side_effect = [Exception("conn reset"), _resp(201, {"messageId": "<id3>"})]
    r = _send(_sender())
    assert r["success"] is True
    assert mpost.call_count == 2


@patch("tools.brevo_sender.requests.post")
def test_desabilitado_nao_envia(mpost):
    s = BrevoSender()
    s._enabled = False
    s.api_key = ""
    r = _send(s)
    assert r["success"] is False
    assert mpost.call_count == 0
