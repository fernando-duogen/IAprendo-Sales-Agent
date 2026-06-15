# -*- coding: utf-8 -*-
"""Regressao do _text_to_html do Brevo: o link do relatorio (report_link) nao
pode quebrar/aninhar.

Bug original: o detector de HTML nao casava `<a href="..."` (exigia espaco apos
`href`), entao o body era tratado como texto puro e o linkificador de URL crua
re-embrulhava a URL DENTRO da ancora -> `<a href="<a href="URL"...>...` (quebrado).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.brevo_sender import brevo_sender  # noqa: E402

_URL = "https://dados.iaprendo.com.br/reports/22144714.html"


def test_text_to_html_preserva_report_link():
    body = (
        "Olá!\n\n"
        f'Olhe que interessante essa análise sobre a escola: <a href="{_URL}" '
        'style="color:#3BB8C4;font-weight:bold">Ver diagnostico completo da SAO JOSE LESTE</a>\n\n'
        "Abraço."
    )
    html = brevo_sender._text_to_html(body)

    # Assinatura do bug: ancora aninhada
    assert 'href="<a' not in html, "Link aninhado/quebrado (bug do report_link)"
    # A URL aparece UMA vez (so no href; nao re-embrulhada)
    assert html.count(_URL) == 1, f"URL repetida {html.count(_URL)}x (re-embrulhada)"
    # href bem-formado + texto do link + fechamento da ancora preservados
    assert f'href="{_URL}"' in html
    assert "Ver diagnostico completo da SAO JOSE LESTE" in html
    assert "</a>" in html


def test_text_to_html_linkifica_url_crua():
    """Garante que o caminho de texto puro (sem HTML) ainda vira link."""
    html = brevo_sender._text_to_html("Veja o material: https://exemplo.com/material")
    assert '<a href="https://exemplo.com/material"' in html
    assert 'href="<a' not in html
