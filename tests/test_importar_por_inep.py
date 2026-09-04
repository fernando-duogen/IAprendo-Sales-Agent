# -*- coding: utf-8 -*-
"""Importar um lote pequeno e conhecido: o caminho que custou 65 minutos.

Contexto (03-04/09/2026). Um operador tentou importar EXATAMENTE 3 escolas
particulares com Fundamental Anos Finais, com os codigos INEP em maos, e
terminou com ZERO importadas (confirmado no banco). O que a tela oferecia:

  - "Buscar no Brasil" so aceitava recorte GEOGRAFICO (UF/cidade/tipo/porte).
    Quem ja sabe quais escolas quer tinha que descrever essas 3 por regiao e
    torcer pro recorte conter exatamente elas.
  - o preview mostrava 15 linhas, sem campo de busca e sem o INEP na tabela.
  - existia um "Colar Lista", mas em OUTRA aba (Preparar escolas) e buscando
    apenas no CRM — colar um INEP que ainda nao foi importado responde
    "nao encontrada", sem dizer que o caminho e importar antes.
  - o checkbox "Ensino Fundamental Anos Finais" filtrava por texto contendo
    "Fundamental", que cobre do 1o ao 9o: metade do resultado era escola so de
    anos iniciais.

Os testes abaixo congelam cada uma dessas quatro coisas.
"""
import ast
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.nivel_ensino import (  # noqa: E402
    LABEL_FUND_AF, PG_FUND_AF, mask_fund_af, mask_medio,
)
from dashboard.helpers.importar_mec import _quebrar_linhas  # noqa: E402

IMPORTAR_MEC = ROOT / "dashboard" / "helpers" / "importar_mec.py"
MEC_SOURCE = ROOT / "dashboard" / "_mec_source.py"
PIPELINE = ROOT / "dashboard" / "pages" / "5_📊_Pipeline.py"
FILTERS = ROOT / "dashboard" / "filters.py"
SUPABASE = ROOT / "database" / "supabase_client.py"

# Os 3 codigos reais do relato.
INEPS = ["35106446", "31311723", "42003903"]


# ===========================================================================
# 1) Colar INEPs — parsing do que a gente REALMENTE cola
# ===========================================================================
def test_uma_linha_por_codigo():
    assert _quebrar_linhas("35106446\n31311723\n42003903") == INEPS


def test_aceita_cola_de_planilha_e_de_csv():
    """Tab vem de planilha, virgula de CSV, ponto-e-virgula de export BR."""
    assert _quebrar_linhas("35106446\t31311723") == ["35106446", "31311723"]
    assert _quebrar_linhas("35106446, 31311723") == ["35106446", "31311723"]
    assert _quebrar_linhas("35106446; 31311723") == ["35106446", "31311723"]


def test_texto_em_volta_vira_entrada_e_nao_some():
    """"35106446 Mobile SP" tem que virar UMA entrada, nao desaparecer.

    Sumir calado e o pior resultado: o operador conta 3 linhas coladas e a tela
    responde sobre 2, sem dizer qual foi ignorada.
    """
    linhas = _quebrar_linhas("35106446 Mobile SP\n31311723 Bernoulli BH")
    assert len(linhas) == 2
    assert linhas[0].startswith("35106446")


def test_vazio_e_espacos_nao_viram_entrada():
    assert _quebrar_linhas("") == []
    assert _quebrar_linhas("   \n\n  \n") == []
    assert _quebrar_linhas("35106446\n\n\n31311723") == ["35106446", "31311723"]


# ===========================================================================
# 2) check_ineps_for_import — o destino de CADA linha, antes de importar
# ===========================================================================
class _FakeQuery:
    def __init__(self, tabela, dados):
        self.tabela, self.dados, self._ineps = tabela, dados, []

    def select(self, *a, **k):
        return self

    def in_(self, _col, valores):
        self._ineps = list(valores)
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        linhas = [r for r in self.dados.get(self.tabela, [])
                  if str(r.get("inep_code")) in self._ineps]
        return type("R", (), {"data": linhas})()


class _FakeClient:
    def __init__(self, dados):
        self.dados = dados

    def table(self, nome):
        return _FakeQuery(nome, self.dados)


def _db_falso(no_catalogo=(), no_crm=()):
    """Database real com um client falso — exercita a logica de verdade."""
    from database.supabase_client import Database
    d = Database.__new__(Database)
    d.client = _FakeClient({
        "mec_catalog": [{"inep_code": i, "name": f"ESCOLA {i}", "city": "São Paulo",
                         "state": "SP", "admin_dependency": "Privada",
                         "matriculas_fund_af": 800, "matriculas_medio": 100,
                         "education_levels": "Fundamental + Médio"}
                        for i in no_catalogo],
        "companies": [{"inep_code": i} for i in no_crm],
    })
    return d


def test_tres_codigos_novos_ficam_prontos_para_importar():
    res = _db_falso(no_catalogo=INEPS).check_ineps_for_import(INEPS)
    assert [r["situacao"] for r in res] == ["nova"] * 3
    assert all(r["nome"] for r in res), "a tela precisa do nome pra confirmar a escola"


def test_ja_no_crm_nao_e_erro():
    """O objetivo era ter a escola no CRM. Ela esta la. Isso e sucesso."""
    res = _db_falso(no_catalogo=INEPS, no_crm=[INEPS[0]]).check_ineps_for_import(INEPS)
    assert res[0]["situacao"] == "ja_no_crm"
    assert [r["situacao"] for r in res[1:]] == ["nova", "nova"]


def test_codigo_inexistente_e_digitacao_errada_sao_erros_DIFERENTES():
    """"nao existe no MEC" e "isso nao e um INEP" pedem acoes diferentes.

    Era tudo "nao encontrada" — a mensagem que travou o operador, porque nao
    dizia se o problema era o codigo, a base, ou a tela.
    """
    res = _db_falso(no_catalogo=INEPS).check_ineps_for_import(["99999999", "abc", "123"])
    assert [r["situacao"] for r in res] == ["nao_existe", "invalido", "invalido"]
    assert res[0]["motivo"] != res[1]["motivo"]


def test_toda_linha_colada_aparece_na_resposta():
    """Quantidade e ordem preservadas: 5 coladas -> 5 respostas, na ordem."""
    entrada = ["35106446", "xx", "31311723", "99999999", "42003903"]
    res = _db_falso(no_catalogo=INEPS).check_ineps_for_import(entrada)
    assert len(res) == len(entrada)
    assert [r["entrada"] for r in res] == entrada


def test_espacos_em_volta_nao_quebram_o_codigo():
    res = _db_falso(no_catalogo=INEPS).check_ineps_for_import([" 35106446 "])
    assert res[0]["situacao"] == "nova"


def test_lista_vazia_nao_consulta_o_banco():
    assert _db_falso().check_ineps_for_import([]) == []


# ===========================================================================
# 3) Anos Finais: o filtro tem que dizer a verdade
# ===========================================================================
def _df_niveis():
    """Os 4 casos reais da base, com os numeros medidos em 04/09/2026."""
    return pd.DataFrame([
        # so anos iniciais: diz "Fundamental" mas tem ZERO no 6o-9o (60.921 assim)
        {"escola": "SO ANOS INICIAIS", "af": 0, "niveis": "Infantil + Fundamental"},
        # anos finais de verdade (61.354 assim)
        {"escola": "TEM ANOS FINAIS", "af": 865, "niveis": "Fundamental + Médio"},
        # sem dado de Censo — desconhecido, nao zero (4.739 assim)
        {"escola": "SEM DADO CENSO", "af": None, "niveis": "Fundamental"},
        {"escola": "SO MEDIO", "af": 0, "niveis": "Médio"},
    ])


def test_escola_so_de_anos_iniciais_fica_de_fora():
    """O bug inteiro em uma linha: 1o-5o nao e nosso alvo."""
    df = _df_niveis()
    assert not mask_fund_af(df, "af", "niveis")[0], (
        "escola de 1o ao 5o voltou a passar pelo filtro de Anos Finais")


def test_escola_com_anos_finais_entra():
    assert mask_fund_af(_df_niveis(), "af", "niveis")[1]


def test_escola_sem_dado_de_censo_nao_e_descartada():
    """NULL e "nao sei", nao "nao tem".

    Tratar NULL como zero sumiria com 3.031 escolas que declaram Fundamental —
    perder escola boa em silencio e pior que trazer escola ruim.
    """
    assert mask_fund_af(_df_niveis(), "af", "niveis")[2]


def test_filtro_novo_e_mais_restrito_que_o_texto():
    df = _df_niveis()
    por_texto = df["niveis"].str.contains("Fundamental")
    real = mask_fund_af(df, "af", "niveis")
    assert int(real.sum()) < int(por_texto.sum())
    assert (real & ~por_texto).sum() == 0, "o filtro real nao pode INVENTAR escola"


def test_coluna_de_matricula_ausente_cai_no_texto_sem_quebrar():
    """CSV antigo/parcial nao pode zerar a tela."""
    df = pd.DataFrame([{"escola": "X", "niveis": "Fundamental"}])
    assert mask_fund_af(df, "af_inexistente", "niveis").tolist() == [True]


def test_medio_continua_pelo_texto():
    """Medido: das 30.614 que dizem "medio", ZERO tem matricula 0.

    O texto e confiavel aqui — mexer seria risco sem ganho.
    """
    assert mask_medio(_df_niveis(), "niveis").tolist() == [False, True, False, True]


def test_clausula_sql_cobre_os_dois_ramos():
    """A regra do PostgREST tem que ser a MESMA do pandas."""
    assert "matriculas_fund_af.gt.0" in PG_FUND_AF
    assert "matriculas_fund_af.is.null" in PG_FUND_AF, (
        "sem o ramo do NULL, 3.031 escolas somem da base online")
    assert "fundamental" in PG_FUND_AF


# ===========================================================================
# 4) Guardas de codigo: o que nao pode voltar atras
# ===========================================================================
def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _constantes(path):
    return {n.value for n in ast.walk(_tree(path)) if isinstance(n, ast.Constant)}


# Os arquivos que REALMENTE aplicam o filtro. A primeira versao desta guarda
# apontava para importar_mec.py — onde o filtro nunca morou — e por isso passava
# limpa contra o codigo bugado. Rodar a guarda contra o codigo antigo e o que
# revela guarda decorativa.
@pytest.mark.parametrize("path", [MEC_SOURCE, FILTERS, SUPABASE],
                         ids=["mec_source", "filters", "supabase_client"])
def test_nenhuma_tela_promete_anos_finais_filtrando_por_texto(path):
    """Um checkbox que diz "Anos Finais" e filtra "Fundamental" mente.

    Guarda por AST: procura qualquer chamada .contains("Fundamental") ou
    ilike com "%fundamental%" nestes arquivos — a forma antiga do bug.
    """
    ofensores = []
    for n in ast.walk(_tree(path)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr not in ("contains", "ilike"):
            continue
        for arg in n.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "fundamental" in arg.value.lower():
                    ofensores.append(n.lineno)
    assert not ofensores, (
        f"{path.name}:{ofensores} voltou a filtrar Anos Finais pelo texto "
        f"'Fundamental' (que cobre 1o-9o). Use utils/nivel_ensino.")


def test_rotulo_do_checkbox_diz_a_faixa():
    """Se o rotulo nao diz "6º ao 9º", o operador nao tem como saber o que pediu."""
    assert "6º ao 9º" in LABEL_FUND_AF
    # A tela tem que USAR a constante compartilhada, nao repetir um texto solto
    # que depois diverge do filtro (foi assim que o rotulo antigo mentiu).
    usa = any(isinstance(n, ast.Name) and n.id == "LABEL_FUND_AF"
              for n in ast.walk(_tree(IMPORTAR_MEC)))
    assert usa, "importar_mec nao usa LABEL_FUND_AF de utils/nivel_ensino"
    antigo = "Ensino Fundamental Anos Finais"
    assert antigo not in _constantes(IMPORTAR_MEC), (
        "o rotulo antigo (que nao diz a faixa) voltou pra tela")


def test_preview_traz_inep_e_matricula_de_anos_finais():
    """Sem INEP na tabela nao da pra copiar pro fluxo de colar; sem a matricula
    nao da pra CONFERIR na tela que o filtro fez o que prometeu."""
    from dashboard._mec_source import PREVIEW_COLS
    assert "inep" in PREVIEW_COLS
    assert "mat_fund_af" in PREVIEW_COLS


def test_os_dois_backends_devolvem_o_MESMO_preview():
    """Producao usa o catalogo Supabase e o dev usa o CSV. Preview divergente
    entre eles so aparece trocando de ambiente — tarde demais."""
    def _e_stub(fn):
        """A classe-interface declara `def preview(...): ...` sem corpo."""
        return (len(fn.body) == 1 and isinstance(fn.body[0], ast.Expr)
                and isinstance(fn.body[0].value, ast.Constant)
                and fn.body[0].value.value is Ellipsis)

    fontes = [n for n in ast.walk(_tree(MEC_SOURCE))
              if isinstance(n, ast.FunctionDef) and n.name == "preview"
              and not _e_stub(n)]
    assert len(fontes) >= 2, "esperava um preview por backend (CSV e catalogo)"
    for fn in fontes:
        usa = any(isinstance(x, ast.Name) and x.id == "PREVIEW_COLS"
                  for x in ast.walk(fn))
        assert usa, f"preview na linha {fn.lineno} montou a propria lista de colunas"


def test_a_busca_por_texto_chega_nos_dois_backends():
    for path in (MEC_SOURCE, SUPABASE):
        achou = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get"
            and any(isinstance(a, ast.Constant) and a.value == "q" for a in n.args)
            for n in ast.walk(_tree(path))
        )
        assert achou, f"{path.name} nao le o filtro de busca 'q'"


# ===========================================================================
# 5) Preparar: teto baixo e progresso visivel
# ===========================================================================
def test_preparar_tem_teto_com_padrao_baixo():
    """Sem teto, "selecionar tudo + Preparar" dispara IA e APIs pagas em
    milhares de escolas num clique, sem volta."""
    for n in ast.walk(_tree(PIPELINE)):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "number_input"):
            continue
        kw = {k.arg: k.value for k in n.keywords}
        chave = kw.get("key")
        if isinstance(chave, ast.Constant) and chave.value == "pipe_max_rodada":
            valor = kw.get("value")
            assert isinstance(valor, ast.Constant) and valor.value <= 10, (
                "o padrao do teto subiu — a protecao existe pro clique distraido")
            return
    raise AssertionError("o teto de escolas por rodada sumiu da tela Preparar")


def test_limites_do_pipeline_usam_o_teto_e_nao_a_selecao_inteira():
    """Guarda o elo: teto na tela sem teto no kwargs nao protege nada."""
    src = PIPELINE.read_text(encoding="utf-8")
    for chave in ("qualify_limit", "enrich_limit", "write_limit"):
        assert f'"{chave}": _n,' in src, (
            f"{chave} voltou a receber a selecao inteira em vez do teto")


def test_run_pipeline_repassa_progresso_para_todo_agente():
    """Um agente sem on_progress = barra que congela no meio da rodada."""
    tree = _tree(ROOT / "workflows" / "daily_pipeline.py")
    chamadas = [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "execute"]
    assert len(chamadas) >= 4, "esperava as 4 etapas chamando execute()"
    for c in chamadas:
        assert any(k.arg == "on_progress" for k in c.keywords), (
            f"execute() na linha {c.lineno} nao repassa on_progress")


def test_progresso_nunca_derruba_o_pipeline():
    """Uma rodada que ja gastou chamadas de API nao pode morrer por causa da
    barra de progresso."""
    from agents.qualifier import QualifierAgent
    QualifierAgent._tick(lambda _ev: 1 / 0, "qualify", 1, 3, {"name": "X"})
    QualifierAgent._tick(None, "qualify", 1, 3, {"name": "X"})


def test_progresso_diz_etapa_escola_e_posicao():
    from agents.qualifier import QualifierAgent
    vistos = []
    QualifierAgent._tick(vistos.append, "enrich", 2, 3, {"name": "COLEGIO X", "id": "c1"})
    assert vistos == [{"etapa": "enrich", "i": 2, "total": 3,
                       "escola": "COLEGIO X", "company_id": "c1"}]
