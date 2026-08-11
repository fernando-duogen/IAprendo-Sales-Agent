# -*- coding: utf-8 -*-
"""Selecao em tabelas: nao agir no registro errado, nao perder cliques.

Contexto (Ago/2026): o dono relatou "as vezes nao seleciona, as vezes da bug, as
vezes desmarca tudo". A varredura mostrou que sao bugs, e nao preferencia de UX.

Dois fundamentos do Streamlit 1.56 que o codigo assumia ao contrario:

  F1  st.data_editor  -> os DADOS entram na identidade do widget
      (elements/widgets/data_editor.py:1109-1123, key_as_main_identity=False).
      Mudou uma celula do df => widget novo => checkboxes zeram.

  F2  st.dataframe(on_select=) -> os dados NAO entram na identidade
      (elements/arrow.py:992-1012) e o serde nao faz clamp dos indices
      (arrow.py:201-249). A selecao POSICIONAL sobrevive a mudanca de filtro e
      passa a apontar para outros registros — ou estoura IndexError.

A suite de 347 testes nao pegava nada disto porque o AppTest nao clica. Estes
testes exercitam a logica real (helper extraido) e, para o que so existe dentro
da pagina, usam AST — nunca casamento de string, que ja deu falso-positivo tres
vezes ao casar o proprio comentario que documenta o bug antigo.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.helpers.table_select import (  # noqa: E402
    build_label_map, reset_if_rows_changed, rows_signature,
    selected_ids, selected_positions,
)

PIPELINE = ROOT / "dashboard" / "pages" / "5_📊_Pipeline.py"
ESCOLAS = ROOT / "dashboard" / "pages" / "2_🏫_Escolas.py"
CONTATOS = ROOT / "dashboard" / "helpers" / "contatos_view.py"


# ---------------------------------------------------------------------------
# Fakes: o objeto que o st.dataframe devolve aparece nas duas formas no repo
# ---------------------------------------------------------------------------
class _AttrEvent:
    """Forma usada em 2_Escolas.py: event.selection.rows"""

    def __init__(self, rows):
        self.selection = type("S", (), {"rows": rows})()


def _dict_event(rows):
    """Forma usada em contatos_view.py: event["selection"]["rows"]"""
    return {"selection": {"rows": rows}}


# ---------------------------------------------------------------------------
# selected_positions / selected_ids — o clamp que evita IndexError e alvo errado
# ---------------------------------------------------------------------------
def test_clamp_descarta_indice_fora_do_range():
    """O caso real: 300 escolas, marca a linha 12, filtra para 5 escolas."""
    assert selected_positions(_AttrEvent([0, 5, 12]), 5) == [0]


def test_clamp_nas_duas_formas_de_evento():
    assert selected_positions(_AttrEvent([0, 2]), 10) == [0, 2]
    assert selected_positions(_dict_event([0, 2]), 10) == [0, 2]


def test_selected_ids_nunca_levanta_index_error():
    """Antes: `[df.iloc[i]["id"] for i in rows]` fora de try -> pagina morria."""
    ids = ["a", "b", "c"]
    assert selected_ids(_AttrEvent([0, 1, 2]), ids) == ["a", "b", "c"]
    # lista encolheu entre runs
    assert selected_ids(_AttrEvent([0, 7, 99]), ids) == ["a"]
    # nada selecionado
    assert selected_ids(_AttrEvent([]), ids) == []


def test_defensivo_com_evento_invalido():
    for ev in (None, {}, {"selection": None}, "lixo", object()):
        assert selected_positions(ev, 5) == []
    assert selected_positions(_AttrEvent([None, "x", 1.0, -1, 2]), 5) == [1, 2]


# ---------------------------------------------------------------------------
# reset_if_rows_changed — descarta a selecao quando as linhas mudam
# ---------------------------------------------------------------------------
def test_primeiro_render_nao_descarta_nada():
    ss = {}
    assert reset_if_rows_changed("t", ["a", "b"], state=ss) is False


def test_mesmas_linhas_preservam_a_selecao():
    ss = {}
    reset_if_rows_changed("t", ["a", "b"], state=ss)
    ss["t"] = {"selection": {"rows": [1]}}
    assert reset_if_rows_changed("t", ["a", "b"], state=ss) is False
    assert "t" in ss, "selecao nao pode ser descartada sem mudanca de linhas"


def test_filtro_mudou_descarta_a_selecao_orfa():
    ss = {}
    reset_if_rows_changed("t", ["a", "b", "c"], state=ss)
    ss["t"] = {"selection": {"rows": [2]}}
    assert reset_if_rows_changed("t", ["a"], state=ss) is True
    assert "t" not in ss, "selecao orfa tem que sumir, senao a acao vai no alvo errado"


def test_reordenacao_tambem_descarta():
    """A selecao e posicional: mesma lista em outra ordem = outros registros."""
    ss = {}
    reset_if_rows_changed("t", ["a", "b"], state=ss)
    assert reset_if_rows_changed("t", ["b", "a"], state=ss) is True


def test_assinatura_e_sensivel_a_ordem():
    assert rows_signature(["a", "b"]) != rows_signature(["b", "a"])
    assert rows_signature(["a", "b"]) == rows_signature(["a", "b"])


# ---------------------------------------------------------------------------
# build_label_map — rotulo duplicado nao pode engolir registro
# ---------------------------------------------------------------------------
def test_rotulos_colididos_preservam_os_dois_ids():
    """Caso real do MEC: nome truncado igual, mesma cidade, Score 0, Fit 0."""
    itens = [
        {"id": "id-primeira", "nome": "ESCOLA MUNICIPAL PROFESSORA MARIA"},
        {"id": "id-segunda", "nome": "ESCOLA MUNICIPAL PROFESSORA MARIA"},
    ]
    m = build_label_map(itens, lambda c: c["nome"][:20])
    assert len(m) == 2, "o dict guardava so o ULTIMO id — a outra escola sumia"
    assert set(m.values()) == {"id-primeira", "id-segunda"}


def test_tres_colisoes_continuam_unicas():
    itens = [{"id": f"id{i}", "nome": "IGUAL"} for i in range(3)]
    m = build_label_map(itens, lambda c: c["nome"])
    assert len(m) == 3
    assert set(m.values()) == {"id0", "id1", "id2"}


def test_sem_colisao_o_rotulo_fica_limpo():
    itens = [{"id": "1", "nome": "Colegio A"}, {"id": "2", "nome": "Colegio B"}]
    m = build_label_map(itens, lambda c: c["nome"])
    assert set(m.keys()) == {"Colegio A", "Colegio B"}


def test_todo_id_e_recuperavel_pelo_rotulo():
    """Invariante que a rotina de sync do multiselect depende: id -> rotulo -> id."""
    itens = [{"id": f"id{i}", "nome": "X" if i % 2 else "Y"} for i in range(6)]
    m = build_label_map(itens, lambda c: c["nome"])
    for it in itens:
        assert it["id"] in m.values()


# ---------------------------------------------------------------------------
# AST: invariantes do codigo das paginas (imune a comentario/docstring)
# ---------------------------------------------------------------------------
def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _names_in(node: ast.AST) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _assigned_value(tree: ast.AST, target_name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == target_name:
                    return node.value
    return None


def test_filter_signature_nao_depende_da_selecao():
    """BUG do '1 clique em cada 2'.

    Com a selecao dentro da assinatura, cada clique invalidava o df e executava
    `del tbl_editor_v3`, apagando o clique que o frontend acabava de mandar.
    A assinatura descreve o FILTRO; a selecao externa e refletida por
    _reset_ckbox_keys().
    """
    val = _assigned_value(_tree(PIPELINE), "filter_signature")
    assert val is not None, "filter_signature sumiu do Pipeline"
    assert "current_sel_set" not in _names_in(val), (
        "a selecao voltou para dentro da filter_signature — isso faz o widget "
        "ser destruido a cada clique e perde 1 clique em cada 2"
    )
    assert "pipeline_selected_ids" not in {
        c.value for c in ast.walk(val) if isinstance(c, ast.Constant)
    }, "filter_signature nao pode ler pipeline_selected_ids"


def _selectable_tables(tree: ast.AST) -> list:
    """Chamadas st.dataframe(...) com on_select — as que guardam selecao."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "dataframe":
            kw = {k.arg for k in node.keywords}
            if "on_select" in kw:
                out.append(node)
    return out


def _calls_named(tree: ast.AST, name: str) -> list:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == name:
                out.append(node)
            elif isinstance(f, ast.Attribute) and f.attr == name:
                out.append(node)
    return out


@pytest.mark.parametrize("path", [ESCOLAS, CONTATOS])
def test_toda_tabela_com_selecao_tem_guarda_de_reset(path):
    """Qualquer tabela nova com on_select precisa do reset — senao volta o bug."""
    tree = _tree(path)
    tabelas = _selectable_tables(tree)
    guardas = _calls_named(tree, "reset_if_rows_changed")
    assert tabelas, f"nenhuma tabela com on_select em {path.name}"
    assert len(guardas) >= len(tabelas), (
        f"{path.name}: {len(tabelas)} tabela(s) com selecao mas so "
        f"{len(guardas)} chamada(s) a reset_if_rows_changed"
    )


@pytest.mark.parametrize("path", [ESCOLAS, CONTATOS])
def test_tabela_com_selecao_usa_key_estavel(path):
    """key= derivada de dado (f-string) destroi o widget quando o dado muda."""
    for node in _selectable_tables(_tree(path)):
        for kw in node.keywords:
            if kw.arg == "key":
                assert not isinstance(kw.value, ast.JoinedStr), (
                    f"{path.name}: key= de tabela com selecao nao pode ser "
                    f"f-string derivada do dado (linha {kw.value.lineno})"
                )


# ---------------------------------------------------------------------------
# AppTest: o sintoma do dono, ponta a ponta
# ---------------------------------------------------------------------------
def _pipeline_apptest():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(PIPELINE), default_timeout=240)
    # Auth mockada (mesmo padrao de tests/test_e2e_v2.py:_new_apptest)
    at.session_state["_v2_auth_done"] = True
    at.session_state["authentication_status"] = True
    at.session_state["username"] = "fernando"
    at.session_state["name"] = "Fernando (test)"
    at.session_state["_v2_current_user"] = {
        "username": "fernando", "name": "Fernando (test)", "role": "CEO",
    }
    return at


def _marcar(at, *linhas):
    """Simula o que o frontend do st.data_editor manda ao marcar checkboxes.

    {"edited_rows": {pos: {col: valor}}, ...} e a shape publica documentada do
    valor que o data_editor guarda em session_state.
    """
    at.session_state["tbl_editor_v3"] = {
        "edited_rows": {i: {"Sel": True} for i in linhas},
        "added_rows": [], "deleted_rows": [],
    }
    at.run()
    sel = at.session_state["pipeline_selected_ids"] \
        if "pipeline_selected_ids" in at.session_state else []
    return list(sel or [])


@pytest.mark.slow
def test_cliques_consecutivos_no_checkbox_nao_se_perdem():
    """O sintoma relatado: "as vezes nao seleciona".

    Contra o codigo antigo este roteiro devolvia 1, 1, 3, 3 — marcar a 2a e a 4a
    escola nao tinha efeito nenhum, porque a selecao entrava na filter_signature
    e cada clique invalidava o widget (`del tbl_editor_v3`) antes do sync ler o
    que o frontend acabara de mandar. O esperado e 1, 2, 3, 4.
    """
    at = _pipeline_apptest()
    at.run()
    if not at.exception and "_tbl_df_cached" not in at.session_state:
        pytest.skip("tabela do Pipeline nao renderizou (sem dados/banco)")
    assert not at.exception, [str(e.value)[:300] for e in at.exception]

    obtido = [len(_marcar(at, *range(n + 1))) for n in range(4)]
    assert obtido == [1, 2, 3, 4], (
        f"cliques perdidos: esperado [1,2,3,4], veio {obtido}"
    )

    # desmarcar tambem tem que valer no mesmo run
    assert len(_marcar(at, 0)) == 1


CONFIRM_KEYS_SEM_SNAPSHOT = {
    "confirm_sel_delete",   # Escolas: selecionadas
    "confirm_bulk_delete",  # Escolas: todas as filtradas
}


def test_confirmacao_de_exclusao_nao_congela_lista_de_ids():
    """Snapshot no 1o clique + confirmacao depois = apaga a lista ANTIGA.

    A flag tem que ser booleana; a lista e relida no momento de confirmar, para
    que o que o banner diz seja o que e apagado.
    """
    tree = _tree(ESCOLAS)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if not isinstance(t, ast.Subscript):
                continue
            sl = t.slice
            if not (isinstance(sl, ast.Constant) and sl.value in CONFIRM_KEYS_SEM_SNAPSHOT):
                continue
            assert isinstance(node.value, ast.Constant) and node.value.value is True, (
                f"linha {node.lineno}: '{sl.value}' precisa ser flag booleana, "
                f"nao snapshot de ids"
            )
