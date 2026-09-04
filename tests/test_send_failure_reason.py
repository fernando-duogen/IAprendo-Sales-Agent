# -*- coding: utf-8 -*-
""""Enviar agora": a tela tem que dizer POR QUE o envio falhou.

Contexto (28/08/2026). O botao "Enviar agora" mostrava so
"1 falha(s) no envio. Verifique os logs." — e quem opera o painel nao tem
acesso ao log da VM.

O motivo real ja voltava: o brevo_sender devolve
`{"success": False, "error": <body 4xx>, "status_code": <int>}` no ramo
"Erro Brevo (cliente, sem retry)" e o send_approved carregava o body em
`details[i]["error"]` — mas descartava o status_code, e o dashboard nao lia
nenhum dos dois.

Sem o status nao da para distinguir 400 de payload, 401 de credencial e 402 de
cota — que exigem acoes completamente diferentes. Por isso o teste do formato
exige os DOIS pedacos.

Nada aqui muda o envio: 4xx continua sem retry.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.send_approved import resumo_falhas  # noqa: E402

SEND_APPROVED = ROOT / "workflows" / "send_approved.py"
COMUNICACAO = ROOT / "dashboard" / "pages" / "6_✉️_Comunicacao.py"

# Body real de um 4xx do Brevo (formato da API v3).
BODY_400 = '{"code":"invalid_parameter","message":"to[0].email is invalid"}'
BODY_401 = '{"code":"unauthorized","message":"Key not found"}'


def _falha(erro=BODY_400, status=400, qid="q1"):
    return {"queue_id": qid, "status": "failed", "error": erro, "status_code": status}


# ---------------------------------------------------------------------------
# Formato: "{status} {body}"
# ---------------------------------------------------------------------------
def test_traz_status_e_body():
    out = resumo_falhas([_falha()])
    assert "400" in out, "sem o status nao da pra saber se e payload, credencial ou cota"
    assert "to[0].email is invalid" in out, "o body do Brevo tem que aparecer"


def test_401_de_credencial_aparece_distinguivel_de_400():
    assert "401" in resumo_falhas([_falha(BODY_401, 401)])
    assert "400" not in resumo_falhas([_falha(BODY_401, 401)])


def test_sem_status_code_mostra_so_o_body():
    """Falha por excecao (nao-HTTP) nao tem status — nao pode virar 'None ...'."""
    out = resumo_falhas([{"queue_id": "q", "status": "failed",
                          "error": "timeout na conexao"}])
    assert out == "timeout na conexao"
    assert "None" not in out


def test_erro_vazio_com_status_ainda_informa_algo():
    out = resumo_falhas([{"queue_id": "q", "status": "failed",
                          "error": "", "status_code": 502}])
    assert "502" in out and out.strip() != "502"


# ---------------------------------------------------------------------------
# Ruido: so 'failed' entra, e o resumo nao explode em lote
# ---------------------------------------------------------------------------
def test_ignora_bloqueadas_e_enviadas():
    details = [
        {"queue_id": "a", "status": "sent", "to": "x@y.com"},
        {"queue_id": "b", "status": "blocked", "reason": "sem_email"},
        {"queue_id": "c", "status": "manual_action", "channel": "linkedin"},
    ]
    assert resumo_falhas(details) == "", "bloqueada nao e falha de envio"


def test_sem_falhas_devolve_string_vazia():
    assert resumo_falhas([]) == ""
    assert resumo_falhas(None) == ""


def test_varias_falhas_sao_agregadas_com_teto():
    out = resumo_falhas([_falha(qid=f"q{i}") for i in range(10)])
    assert "+7 outra(s)" in out, "envio em lote nao pode virar um paredao de texto"
    assert out.count("400") == 3


def test_resumo_tem_tamanho_limitado():
    gigante = [_falha("x" * 5000, 400, f"q{i}") for i in range(5)]
    assert len(resumo_falhas(gigante)) <= 500


# ---------------------------------------------------------------------------
# AST: o status_code precisa chegar ate o details, e o envio nao pode mudar
# ---------------------------------------------------------------------------
def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def test_details_da_falha_carrega_error_e_status_code():
    """Se alguem remover status_code daqui, resumo_falhas perde metade da info."""
    achou = False
    for n in ast.walk(_tree(SEND_APPROVED)):
        if not (isinstance(n, ast.Dict) and n.keys):
            continue
        chaves = {k.value for k in n.keys if isinstance(k, ast.Constant)}
        valores = {v.value for v in n.values if isinstance(v, ast.Constant)}
        if "status" in chaves and "failed" in valores and "error" in chaves:
            achou = True
            assert "status_code" in chaves, (
                "o details da falha voltou a descartar o status_code do Brevo")
    assert achou, "nao encontrei o details.append da falha de envio"


def test_4xx_continua_sem_retry():
    """Guarda explicita do pedido: mostrar o motivo nao pode virar re-tentativa."""
    src = (ROOT / "tools" / "brevo_sender.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # o ramo `if 400 <= status < 500` tem que continuar terminando em `return`
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        if not isinstance(n.test, ast.Compare):
            continue
        consts = {c.value for c in ast.walk(n.test) if isinstance(c, ast.Constant)}
        if {400, 500} <= consts:
            assert any(isinstance(x, ast.Return) for x in n.body), (
                "o ramo 4xx tem que retornar imediatamente — sem retry")
            return
    raise AssertionError("nao encontrei o ramo 4xx do brevo_sender")


def test_a_tela_usa_o_resumo_do_modulo():
    """A pagina nao pode reimplementar o formato (foi o que gerou a divergencia)."""
    tree = _tree(COMUNICACAO)
    chamou = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "resumo_falhas"
        for n in ast.walk(tree)
    )
    assert chamou, "a tela precisa usar send_approved.resumo_falhas"


# ---------------------------------------------------------------------------
# AppTest: a fiacao inteira, do session_state ate a tela
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_a_tela_mostra_o_motivo_da_falha():
    """Congela o caminho completo: o que _do_send_now grava vira st.error.

    As guardas AST acima provam as pecas; so o render prova que elas estao
    ligadas — e foi exatamente uma ligacao faltando (o status_code que morria no
    send_approved) que gerou este trabalho.
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(COMUNICACAO), default_timeout=300)
    at.session_state["_v2_auth_done"] = True
    at.session_state["authentication_status"] = True
    at.session_state["username"] = "vendedor1"
    at.session_state["name"] = "Vendedor 1"
    at.session_state["_v2_current_user"] = {
        "username": "vendedor1", "name": "Vendedor 1", "role": "Vendedor (agente)",
    }
    # exatamente o que _do_send_now deixa apos um 4xx do Brevo
    at.session_state["_approved_send_result"] = (0, 0, 1)
    at.session_state["_approved_send_error"] = f"400 {BODY_400}"
    at.run()

    assert not at.exception, [str(e.value) for e in at.exception]
    erros = [e.value for e in at.error]
    assert any("Motivo:" in e and "400" in e for e in erros), erros
    assert "_approved_send_error" not in at.session_state, (
        "o motivo tem que ser consumido — senao reaparece no proximo run")
