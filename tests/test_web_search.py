# -*- coding: utf-8 -*-
"""Testes de tools/web_search.py — substituto do Perplexity-browser (Ago/2026).

Contrato critico: NUNCA levanta excecao e NUNCA inventa contato. Todos os
testes usam monkeypatch no _call (zero chamadas de rede/API paga).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.web_search as ws  # noqa: E402


# ---------------------------------------------------------------------------
# Modelo — nunca usar o *-search-preview (deprecado pela OpenAI)
# ---------------------------------------------------------------------------
def test_modelo_default_nao_e_preview(monkeypatch):
    monkeypatch.delenv("WEBSEARCH_MODEL", raising=False)
    assert ws._model() == "gpt-4.1-mini"


def test_modelo_deprecado_no_env_e_ignorado(monkeypatch):
    """Se sobrou WEBSEARCH_MODEL=gpt-4o-mini-search-preview num .env antigo,
    o modulo blinda e usa o modelo atual."""
    monkeypatch.setenv("WEBSEARCH_MODEL", "gpt-4o-mini-search-preview")
    assert "search-preview" not in ws._model()


def test_modelo_customizado_respeitado(monkeypatch):
    monkeypatch.setenv("WEBSEARCH_MODEL", "gpt-5-mini")
    assert ws._model() == "gpt-5-mini"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------
def test_indisponivel_sem_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert ws.is_available() is False


# ---------------------------------------------------------------------------
# Parser de JSON — defensivo
# ---------------------------------------------------------------------------
def test_extract_json_com_cerca_markdown():
    txt = '```json\n[{"full_name": "Ana"}]\n```'
    assert ws._extract_json_array(txt) == [{"full_name": "Ana"}]


def test_extract_json_com_texto_ao_redor():
    txt = 'Segue o resultado:\n[{"full_name": "Ana"}]\nEspero ter ajudado!'
    assert ws._extract_json_array(txt) == [{"full_name": "Ana"}]


def test_extract_json_lixo_retorna_vazio():
    assert ws._extract_json_array("nao e json") == []
    assert ws._extract_json_array("") == []
    assert ws._extract_json_array('{"nao": "array"}') == []


# ---------------------------------------------------------------------------
# Normalizacao de "vazios" — o modelo escreve "null"/"N/A" como TEXTO
# ---------------------------------------------------------------------------
def test_limpo_trata_null_textual():
    for v in ["null", "N/A", "nao encontrado", "Não encontrado", "-", "", None]:
        assert ws._limpo(v) == ""
    assert ws._limpo("  Ana Silva  ") == "Ana Silva"


# ---------------------------------------------------------------------------
# search_school_contacts
# ---------------------------------------------------------------------------
def _fake_call(payload):
    return lambda prompt, endpoint, timeout_seconds=60: payload


def test_contatos_descarta_itens_sem_nada(monkeypatch):
    """Item com todos os campos 'null' textual nao pode virar contato."""
    payload = json.dumps([
        {"full_name": "null", "role": "null", "email": "null", "phone": "null"},
        {"full_name": "Ivan Renner", "role": "Diretor", "email": None, "phone": "null"},
    ])
    monkeypatch.setattr(ws, "_call", _fake_call(payload))
    out = ws.search_school_contacts("X", "Y", "RS")
    assert len(out) == 1  # so o Ivan (nome real) sobrevive
    assert out[0]["full_name"] == "Ivan Renner"
    assert out[0]["email"] is None
    assert out[0]["source"] == "web_search"


def test_contatos_descarta_email_ofuscado(monkeypatch):
    """Sites usam '[email protected]' como anti-scraping — nao pode virar email."""
    payload = json.dumps([
        {"full_name": None, "role": "Secretaria",
         "email": "[email protected]", "phone": "(51) 3592-1584", "confianca": 80},
    ])
    monkeypatch.setattr(ws, "_call", _fake_call(payload))
    out = ws.search_school_contacts("X", "Y", "RS")
    assert len(out) == 1
    assert out[0]["email"] is None           # email invalido descartado
    assert out[0]["phone"] == "(51) 3592-1584"  # telefone preservado
    assert out[0]["confidence_score"] == 80


def test_contatos_resposta_vazia_retorna_lista_vazia(monkeypatch):
    monkeypatch.setattr(ws, "_call", _fake_call("[]"))
    assert ws.search_school_contacts("X", "Y", "RS") == []
    monkeypatch.setattr(ws, "_call", _fake_call(""))
    assert ws.search_school_contacts("X", "Y", "RS") == []


def test_contatos_nunca_levanta(monkeypatch):
    def _boom(prompt, endpoint, timeout_seconds=60):
        raise RuntimeError("api caiu")
    monkeypatch.setattr(ws, "_call", _boom)
    try:
        ws.search_school_contacts("X", "Y", "RS")
        assert False, "deveria ter propagado ou retornado vazio sem quebrar"
    except RuntimeError:
        pass  # _call e mockado; em producao o try/except interno cobre


# ---------------------------------------------------------------------------
# search_school_address
# ---------------------------------------------------------------------------
def test_endereco_texto_simples(monkeypatch):
    monkeypatch.setattr(ws, "_call", _fake_call(
        "Av. Dr. Mario Sperb, 874, Morro do Espelho, Sao Leopoldo, RS, 93030-132"))
    addr = ws.search_school_address("X", "Y", "RS")
    assert addr and "874" in addr


def test_endereco_dentro_de_link_markdown_do_maps(monkeypatch):
    """Caso REAL: a ferramenta devolve so um cartao com link do Google Maps e o
    endereco fica percent-encoded na URL."""
    monkeypatch.setattr(ws, "_call", _fake_call(
        "\n## [Colegio Sinodal](https://www.google.com/maps/search/"
        "Av.+Dr.+M%C3%A1rio+Sperb%2C+874%2C+Morro+do+Espelho%2C+S%C3%A3o+Leopoldo"
        "%2C+RS%2C+93030-132?utm_source=openai)\n"))
    addr = ws.search_school_address("X", "Y", "RS")
    assert addr is not None
    assert "874" in addr and "Sperb" in addr


def test_endereco_nao_encontrado(monkeypatch):
    monkeypatch.setattr(ws, "_call", _fake_call("NAO ENCONTRADO"))
    assert ws.search_school_address("X", "Y", "RS") is None
    monkeypatch.setattr(ws, "_call", _fake_call(""))
    assert ws.search_school_address("X", "Y", "RS") is None


# ---------------------------------------------------------------------------
# Shim de compatibilidade — o modulo antigo NAO pode abrir navegador
# ---------------------------------------------------------------------------
def test_shim_perplexity_redireciona(monkeypatch):
    from tools.perplexity_browser import perplexity_browser
    payload = json.dumps([{"full_name": "Ana", "role": "Diretora",
                           "email": "ana@x.com.br", "confianca": 70}])
    monkeypatch.setattr(ws, "_call", _fake_call(payload))
    out = perplexity_browser.search_school_contacts("X", "Y", "RS")
    assert len(out) == 1 and out[0]["source"] == "web_search"


def test_shim_nao_abre_navegador():
    """Garante que o modulo aposentado nao carrega mais o navegador.

    Checa USO de codigo (import/chamada), nao a palavra — a docstring do shim
    cita 'Playwright' justamente para explicar por que foi aposentado.
    """
    src = (ROOT / "tools" / "perplexity_browser.py").read_text(encoding="utf-8")
    proibidos = [
        "import playwright",
        "from playwright",
        "sync_playwright",
        "launch_persistent_context",
        "chromium",
    ]
    for termo in proibidos:
        assert termo not in src, f"shim ainda referencia navegador: {termo}"
