# -*- coding: utf-8 -*-
"""Feedback de acao: "cliquei e nao aconteceu nada".

Contexto (Ago/2026): 21 confirmacoes do dashboard chamavam st.success(...) e
logo em seguida st.rerun(). st.success e um elemento do CORPO da pagina; o
rerun aborta o run atual e reconstroi a pagina, entao a mensagem nunca era
vista. Efeito pratico: aprovar uma mensagem nao dava retorno nenhum — ela
apenas sumia da fila, e o usuario nao sabia se aprovou ou se deu erro.

NAO cobre st.toast: nao foi verificado que o toast se perde no rerun (ele e uma
notificacao em overlay com duracao propria), entao os call sites de toast foram
deixados como estavam de proposito.

Os checks de codigo usam AST — nunca casamento de string, que ja produziu
falso-positivo ao casar o proprio comentario que documentava o bug antigo.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.helpers.flash import (  # noqa: E402
    flash, flash_error, flash_success, flash_warning, pending, render_flash,
)

DASHBOARD = ROOT / "dashboard"
COMUNICACAO = DASHBOARD / "pages" / "6_✉️_Comunicacao.py"


# ---------------------------------------------------------------------------
# flash: a mensagem sobrevive porque vive em session_state, nao na arvore
# ---------------------------------------------------------------------------
def test_mensagem_fica_pendente_ate_ser_renderizada():
    ss = {}
    flash_success("Mensagem aprovada.", state=ss)
    assert pending(ss) == [("success", "Mensagem aprovada.")]


def test_render_consome_a_fila():
    ss = {}
    flash_success("ok", state=ss)
    render_flash(state=ss)
    assert pending(ss) == [], "mensagem nao pode reaparecer no run seguinte"


def test_varias_mensagens_se_acumulam_em_ordem():
    ss = {}
    flash_success("a", state=ss)
    flash_warning("b", state=ss)
    flash_error("c", state=ss)
    assert [k for k, _ in pending(ss)] == ["success", "warning", "error"]


def test_tipo_desconhecido_vira_info_em_vez_de_sumir():
    ss = {}
    flash("bizarro", "texto", state=ss)
    assert pending(ss) == [("info", "texto")]


def test_fila_tem_teto_para_acao_em_lote():
    ss = {}
    for i in range(50):
        flash_success(str(i), state=ss)
    fila = pending(ss)
    assert len(fila) <= 10
    assert fila[-1] == ("success", "49"), "o teto tem que descartar as ANTIGAS"


def test_render_sem_nada_pendente_nao_quebra():
    render_flash(state={})


# ---------------------------------------------------------------------------
# AST: invariantes do codigo do dashboard
# ---------------------------------------------------------------------------
def _st_call(node):
    """Nome do metodo em `st.<nome>(...)` quando o statement e so essa chamada."""
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        f = node.value.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "st":
            return f.attr
    return None


def _blocos(tree):
    for node in ast.walk(tree):
        for attr in ("body", "orelse", "finalbody"):
            seq = getattr(node, attr, None)
            if isinstance(seq, list):
                yield seq


PAGINAS = sorted(DASHBOARD.rglob("*.py"))


@pytest.mark.parametrize("path", PAGINAS, ids=[p.stem for p in PAGINAS])
def test_nenhum_success_e_descartado_pelo_rerun(path):
    """st.success(...) seguido de st.rerun() = mensagem que ninguem ve.

    Use flash_success(...) de dashboard/helpers/flash.py — ele persiste em
    session_state e e renderizado depois do rerun.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    ofensores = []
    for seq in _blocos(tree):
        for i, a in enumerate(seq):
            if _st_call(a) not in ("success", "info", "warning", "error"):
                continue
            # Basta o rerun vir DEPOIS na mesma lista de statements — nao
            # precisa ser adjacente. A versao antiga so olhava pares
            # vizinhos e por isso nao pegou o st.success do 'Aprovar' (com
            # 2 linhas no meio) — o mesmo clique que escondeu a coluna
            # metadata ausente. Sem falso-positivo: se sao irmaos e o
            # feedback vem antes, o rerun descarta sempre.
            if any(_st_call(b) == "rerun" for b in seq[i + 1:]):
                ofensores.append((a.lineno, _st_call(a)))
    assert not ofensores, (
        f"{path.name}: st.<tipo>() descartado pelo rerun nas linhas "
        f"{sorted(ofensores)} — trocar por flash_*()"
    )


def _tem_call(tree, nome):
    return any(
        isinstance(n, ast.Call)
        and ((isinstance(n.func, ast.Name) and n.func.id == nome)
             or (isinstance(n.func, ast.Attribute) and n.func.attr == nome))
        for n in ast.walk(tree)
    )


@pytest.mark.parametrize("path", PAGINAS, ids=[p.stem for p in PAGINAS])
def test_quem_enfileira_flash_tambem_renderiza(path):
    """Enfileirar sem render_flash() = mensagem presa em session_state."""
    if path.name == "flash.py":
        pytest.skip("o proprio modulo")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    enfileira = any(_tem_call(tree, n)
                    for n in ("flash_success", "flash_error",
                              "flash_warning", "flash_info"))
    if not enfileira:
        pytest.skip("nao usa flash")
    assert _tem_call(tree, "render_flash"), (
        f"{path.name} enfileira mensagem mas nunca chama render_flash()"
    )


def test_rotulos_de_aba_nao_dependem_de_contagem():
    """st.tabs nao tem key: a identidade vem dos rotulos.

    Com a contagem embutida ("Aguardando (12)"), qualquer acao mudava o numero,
    mudava o rotulo, e as abas remontavam no indice 0 — aprovar uma mensagem na
    aba "Aprovadas" jogava o usuario de volta para "Aguardando".
    """
    tree = ast.parse(COMUNICACAO.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "tabs"):
            continue
        for arg in node.args:
            if not isinstance(arg, (ast.List, ast.Tuple)):
                continue
            dinamicos = [e.lineno for e in arg.elts if isinstance(e, ast.JoinedStr)]
            assert not dinamicos, (
                f"rotulo de aba dinamico nas linhas {dinamicos}: as abas vao "
                f"remontar no indice 0 a cada acao"
            )
