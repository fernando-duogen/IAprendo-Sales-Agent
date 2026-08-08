# -*- coding: utf-8 -*-
"""Contrato do Brain.process_message (operador v1, F0).

Garante:
1. Retorno SEMPRE tem "reply" (WhatsApp le so isso) e "blocks" (chat web).
2. Sem kwargs novos = caminho legado (max_tokens=2048, ate 5 iteracoes).
3. Caps opcionais sao respeitados quando passados.
4. Blocks derivados de tool ficam FORA do conversation_history (que vai a API).
5. on_event e best-effort — callback que levanta nao quebra o turno.

Usa um cliente OpenAI FAKE (zero chamadas de rede/API paga).
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent.brain as brain_mod  # noqa: E402
from agent.brain import Brain  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes do cliente OpenAI
# ---------------------------------------------------------------------------
class _FakeFunc:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, tc_id, name, arguments="{}"):
        self.id = tc_id
        self.type = "function"
        self.function = _FakeFunc(name, arguments)


class _FakeMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, finish_reason, message):
        self.finish_reason = finish_reason
        self.message = message


class _FakeResponse:
    def __init__(self, choice):
        self.choices = [choice]
        self.usage = None  # pula o logging de tokens


class _FakeCompletions:
    """Devolve as respostas na ordem; grava kwargs de cada create()."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _fake_client(responses):
    return SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions(responses)))


def _final(text="Tudo certo!"):
    return _FakeResponse(_FakeChoice("stop", _FakeMsg(content=text)))


def _tool_call(name, args="{}"):
    return _FakeResponse(_FakeChoice(
        "tool_calls", _FakeMsg(content=None, tool_calls=[_FakeToolCall("tc1", name, args)])
    ))


@pytest.fixture()
def brain():
    b = Brain()
    return b


# ---------------------------------------------------------------------------
# 1-2. Caminho legado: reply sempre presente; defaults intactos
# ---------------------------------------------------------------------------
def test_reply_e_blocks_sempre_presentes(brain):
    brain.client = _fake_client([_final("oi")])
    result = brain.process_message("teste [BRAIN-CONTRACT]")
    assert result["reply"] == "oi"
    assert isinstance(result["blocks"], list)


def test_defaults_legados_sem_kwargs(brain):
    fake = _fake_client([_final()])
    brain.client = fake
    brain.process_message("teste [BRAIN-CONTRACT]")
    call = fake.chat.completions.calls[0]
    assert call["max_tokens"] == 2048  # default historico (WhatsApp intacto)
    assert call["tool_choice"] == "auto"


def test_caps_opcionais_respeitados(brain):
    fake = _fake_client([_final()])
    brain.client = fake
    brain.process_message("teste [BRAIN-CONTRACT]", max_tokens=4096, max_iterations=8)
    assert fake.chat.completions.calls[0]["max_tokens"] == 4096


def test_teto_de_iteracoes_default(brain):
    # 5 respostas de tool_calls seguidas -> para em 5 e devolve fallback amigavel
    fake = _fake_client([_tool_call("tool_que_nao_existe") for _ in range(5)])
    brain.client = fake
    result = brain.process_message("teste [BRAIN-CONTRACT]")
    assert len(fake.chat.completions.calls) == 5
    assert "reply" in result and "blocks" in result


# ---------------------------------------------------------------------------
# 3-4. Blocks: derivados da tool, fora do history
# ---------------------------------------------------------------------------
def test_blocks_derivados_e_fora_do_history(brain, monkeypatch):
    export_json = json.dumps({
        "ok": True, "url": "https://x/f.xlsx", "filename": "f.xlsx",
        "total_escolas": 1, "total_contatos": 2, "validade_horas": 24,
    })
    monkeypatch.setitem(
        brain_mod.TOOL_HANDLERS, "exportar_escolas_xlsx", lambda args: export_json
    )
    brain.client = _fake_client([_tool_call("exportar_escolas_xlsx"), _final("exportado")])
    result = brain.process_message("exporta [BRAIN-CONTRACT]")

    assert result["reply"] == "exportado"
    assert len(result["blocks"]) == 1
    assert result["blocks"][0]["type"] == "download"

    # blocks NUNCA podem vazar pro conversation_history (vai pra API OpenAI)
    for msg in brain.conversation_history:
        assert "blocks" not in msg
        assert set(msg.keys()) <= {"role", "content", "tool_calls", "tool_call_id"}


def test_tool_desconhecida_gera_erro_amigavel_sem_blocks(brain):
    brain.client = _fake_client([_tool_call("nao_existe"), _final("ok")])
    result = brain.process_message("teste [BRAIN-CONTRACT]")
    assert result["reply"] == "ok"
    assert result["blocks"] == []
    # o resultado de erro foi pro history como tool msg
    tool_msgs = [m for m in brain.conversation_history if m.get("role") == "tool"]
    assert tool_msgs and "nao encontrada" in tool_msgs[0]["content"]


# ---------------------------------------------------------------------------
# 5. on_event best-effort
# ---------------------------------------------------------------------------
def test_on_event_recebe_tool_start_end(brain, monkeypatch):
    monkeypatch.setitem(
        brain_mod.TOOL_HANDLERS, "estatisticas_gerais", lambda args: json.dumps({"total_escolas": 1})
    )
    events = []
    brain.client = _fake_client([_tool_call("estatisticas_gerais"), _final()])
    brain.process_message("teste [BRAIN-CONTRACT]", on_event=events.append)
    types = [e["type"] for e in events]
    assert "tool_start" in types and "tool_end" in types
    assert events[0]["tool"] == "estatisticas_gerais"


# ---------------------------------------------------------------------------
# F2 — cobertura total: novas tools registradas e defensivas
# ---------------------------------------------------------------------------
_NOVAS_TOOLS_F2 = [
    "reagendar_envio", "editar_template", "arquivar_template",
    "ver_config_vendas", "atualizar_config_vendas",
]


def test_novas_tools_f2_registradas():
    tool_names = {t["name"] for t in brain_mod.TOOLS}
    for name in _NOVAS_TOOLS_F2:
        assert name in tool_names, f"schema de {name} ausente em TOOLS"
        assert name in brain_mod.TOOL_HANDLERS, f"handler de {name} ausente"


def test_reagendar_envio_id_invalido_erro_amigavel():
    out = json.loads(brain_mod._handle_reagendar_envio({"queue_id": "00000000-0000-0000-0000-000000000000"}))
    assert "erro" in out  # nao levanta, nao escreve


def test_editar_template_sem_identificacao():
    out = json.loads(brain_mod._handle_editar_template({}))
    assert "erro" in out and "template_id" in out["erro"]


def test_arquivar_template_inexistente():
    out = json.loads(brain_mod._handle_arquivar_template({"nome": "zzz-inexistente-[BRAIN-CONTRACT]"}))
    assert "erro" in out


def test_on_event_que_levanta_nao_quebra(brain, monkeypatch):
    monkeypatch.setitem(
        brain_mod.TOOL_HANDLERS, "estatisticas_gerais", lambda args: json.dumps({"x": 1})
    )

    def _boom(evt):
        raise RuntimeError("callback quebrado")

    brain.client = _fake_client([_tool_call("estatisticas_gerais"), _final("sobrevivi")])
    result = brain.process_message("teste [BRAIN-CONTRACT]", on_event=_boom)
    assert result["reply"] == "sobrevivi"
