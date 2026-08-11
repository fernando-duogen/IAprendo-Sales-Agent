# -*- coding: utf-8 -*-
"""Cache, filtros e contexto de navegacao.

Contexto (Ago/2026), terceiro bloco do relato do dono: acoes que funcionavam mas
"nao apareciam", filtros que se resetavam sozinhos e botoes que abriam a escola
errada.

- 22 funcoes cacheadas no dashboard e `.clear()` em apenas 5 lugares. A pior era
  get_crm_schools (TTL 300, le `companies`): NADA a invalidava, e ha 8 pontos de
  escrita. Importava uma escola e ela nao aparecia no buscador por 5 minutos;
  excluia e continuava listada.
- Widget sem `key=` tem a identidade derivada dos proprios parametros —
  inclusive da lista de `options`. Nos filtros cujas opcoes vem dos dados,
  bastava o dado mudar para o filtro virar outro widget e voltar ao default.
- morning_panel descartava o company_id no switch_page (e `action_params`, que
  ele montava em 3 lugares, nunca era lido por ninguem: codigo morto).

Checks de codigo em AST — nunca casamento de string.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DASHBOARD = ROOT / "dashboard"
PIPELINE = DASHBOARD / "pages" / "5_📊_Pipeline.py"
ESCOLAS = DASHBOARD / "pages" / "2_🏫_Escolas.py"
MORNING = DASHBOARD / "helpers" / "morning_panel.py"
IMPORTAR = DASHBOARD / "helpers" / "importar_mec.py"

# Escritas que mudam QUAIS escolas existem no CRM.
ESCRITAS_COMPANIES = {"insert_company", "delete_company", "bulk_delete_companies"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _chamadas(tree: ast.AST, nome: str) -> list:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == nome) or \
               (isinstance(f, ast.Attribute) and f.attr == nome):
                out.append(n)
    return out


# ---------------------------------------------------------------------------
# invalidacao do cache de escolas
# ---------------------------------------------------------------------------
def test_helper_de_invalidacao_existe():
    from dashboard.helpers.school_lookup import invalidate_crm_schools
    assert callable(invalidate_crm_schools)


ARQUIVOS_QUE_ESCREVEM = [ESCOLAS, PIPELINE]


@pytest.mark.parametrize("path", ARQUIVOS_QUE_ESCREVEM, ids=lambda p: p.stem)
def test_escrita_em_companies_invalida_o_buscador(path):
    """Quem cria/apaga escola tem que limpar get_crm_schools.

    Sem isso o seletor "Buscar escola" fica ate 5 min mostrando o mundo antigo —
    e o usuario conclui que a acao nao funcionou.
    """
    tree = _tree(path)
    escritas = sum(len(_chamadas(tree, nome)) for nome in ESCRITAS_COMPANIES)
    invalidacoes = len(_chamadas(tree, "invalidate_crm_schools"))
    assert escritas > 0, f"{path.name}: nenhuma escrita encontrada (teste desatualizado?)"
    assert invalidacoes >= escritas, (
        f"{path.name}: {escritas} escrita(s) em companies mas so "
        f"{invalidacoes} invalidate_crm_schools()"
    )


def test_importacao_mec_invalida_o_buscador():
    assert _chamadas(_tree(IMPORTAR), "invalidate_crm_schools"), (
        "a importacao cria escolas e precisa invalidar get_crm_schools"
    )


# ---------------------------------------------------------------------------
# cache que nao chaveia pelo que le
# ---------------------------------------------------------------------------
def _funcao(tree: ast.AST, nome: str):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == nome:
            return n
    return None


def test_contact_stats_nao_le_global_de_fora_dos_argumentos():
    """A funcao lia a global `all_companies` sem recebe-la como argumento.

    O cache nao chaveava por ela, e o botao "Atualizar dados" — que limpa os
    outros dois caches — nao limpava este: os contadores "Sem nenhum contato
    (N)" seguiam errados mesmo apos o refresh explicito.
    """
    fn = _funcao(_tree(PIPELINE), "_load_contact_stats")
    assert fn is not None, "_load_contact_stats sumiu do Pipeline"
    params = {a.arg for a in fn.args.args}
    nomes = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "all_companies" not in nomes, (
        "_load_contact_stats voltou a ler a global all_companies; "
        "receba as escolas por argumento (com _ para o Streamlit nao hashear)"
    )
    assert params, "a funcao precisa receber as escolas por argumento"


def test_pipeline_invalida_os_tres_caches_apos_rodar():
    """Rodar o pipeline muda status/contatos/fila; o stepper do topo ja foi
    renderizado com dados de ate 30s atras."""
    fn = _funcao(_tree(PIPELINE), "_cascade")
    assert fn is not None, "_cascade sumiu do Pipeline"
    limpos = {
        n.func.value.id
        for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "clear" and isinstance(n.func.value, ast.Name)
    }
    # o for-loop referencia os caches numa tupla; aceitar as duas formas
    nomes = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    esperados = {"_load_all_companies_cached", "_load_queue_counts_cached",
                 "_load_contact_stats"}
    assert esperados <= (limpos | nomes), (
        f"_cascade nao invalida {esperados - (limpos | nomes)}"
    )


# ---------------------------------------------------------------------------
# filtros cujas opcoes vem dos dados precisam de key=
# ---------------------------------------------------------------------------
WIDGETS_DE_FILTRO = {"multiselect", "selectbox", "radio", "select_slider"}


def _widgets_sem_key(tree: ast.AST):
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr not in WIDGETS_DE_FILTRO:
            continue
        if not (isinstance(n.func.value, ast.Name) and n.func.value.id == "st"):
            continue
        if any(k.arg == "key" for k in n.keywords):
            continue
        yield n


def _opcoes_vem_de_chamada(node: ast.Call) -> bool:
    """options e o 2o argumento posicional; se for uma CHAMADA, veio de dado.

    Excecao: `range(...)` e um seletor POSICIONAL (o valor e o indice da linha).
    Ali a ausencia de key e o comportamento correto — com key, o indice antigo
    sobreviveria a mudanca da lista e passaria a apontar para outra escola,
    exatamente a classe de bug corrigida em dashboard/helpers/table_select.py.
    """
    if len(node.args) < 2:
        return False
    opts = node.args[1]
    if not isinstance(opts, ast.Call):
        return False
    if isinstance(opts.func, ast.Name) and opts.func.id == "range":
        return False
    return True


@pytest.mark.parametrize("path", [ESCOLAS, IMPORTAR], ids=lambda p: p.stem)
def test_filtro_com_opcoes_dinamicas_tem_key(path):
    """Sem key, mudar o dado troca a identidade do widget e o filtro zera.

    Filtros com opcoes LITERAIS sao estaveis e nao precisam de key — o teste so
    exige key quando as opcoes vem de uma chamada (source.ufs(), etc).
    """
    ofensores = [
        (n.lineno, n.args[0].value if n.args and isinstance(n.args[0], ast.Constant) else "?")
        for n in _widgets_sem_key(_tree(path))
        if _opcoes_vem_de_chamada(n)
    ]
    assert not ofensores, (
        f"{path.name}: filtro com opcoes dinamicas e sem key= em {ofensores}"
    )


# ---------------------------------------------------------------------------
# navegacao carrega o alvo
# ---------------------------------------------------------------------------
def test_painel_diario_leva_a_escola_junto():
    """"Ver escola" num lead CRITICO abria a ULTIMA ficha vista.

    action_params era montado em 3 pontos e nunca lido — codigo morto.
    """
    tree = _tree(MORNING)
    assert _chamadas(tree, "_carregar_contexto"), (
        "morning_panel voltou a navegar sem levar o company_id"
    )
    assert _funcao(tree, "_carregar_contexto") is not None
    # O mapeamento param -> chave de destino vive no modulo (_DEST_STATE).
    consts = {c.value for c in ast.walk(tree) if isinstance(c, ast.Constant)}
    assert "escola_detail_id" in consts, (
        "o contexto precisa setar escola_detail_id, que e o que a pagina Escolas le"
    )


def test_action_params_deixou_de_ser_codigo_morto():
    fn = _funcao(_tree(MORNING), "_carregar_contexto")
    assert fn is not None, "_carregar_contexto nao existe: action_params segue morto"
    nomes = {c.value for c in ast.walk(fn) if isinstance(c, ast.Constant)}
    assert "action_params" in nomes, "action_params continua sem ser lido por ninguem"


# ---------------------------------------------------------------------------
# formularios de criacao limpam apos enviar
# ---------------------------------------------------------------------------
FORMS_DE_CRIACAO = {"add_contact_form"}


def test_form_de_criacao_limpa_apos_enviar():
    """Campos preenchidos apos o submit pareciam "nao enviou" -> duplicata."""
    for n in ast.walk(_tree(ESCOLAS)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "form"):
            continue
        nome = n.args[0].value if n.args and isinstance(n.args[0], ast.Constant) else None
        if nome not in FORMS_DE_CRIACAO:
            continue
        limpa = any(k.arg == "clear_on_submit"
                    and isinstance(k.value, ast.Constant) and k.value.value is True
                    for k in n.keywords)
        assert limpa, f"linha {n.lineno}: form '{nome}' precisa de clear_on_submit=True"
