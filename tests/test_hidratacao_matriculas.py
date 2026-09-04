# -*- coding: utf-8 -*-
"""Escola com dado no sistema tem que receber template com numeros.

Contexto (04/09/2026). `template_selector.detectar_dados` decide se a escola
tem "dados ricos" olhando os campos de matricula do dict de company. Escola com
esses campos zerados caia no template pobre mesmo com o Censo cheio.

## A causa raiz (que nao era a suposta)

A hipotese inicial era "falta chamar o sync antes de escolher o template".
Medindo o banco: das 125 escolas com INEP, **8 estavam zeradas — e todas as 8
tinham censo**. Mas chamar o sync nao consertaria nenhuma:

    censo 2025 -> linha EXISTE com qt_mat_bas = NULL
    censo 2024 -> qt_mat_bas = 315, qt_mat_fund_af = 98

`sync_company_matriculas_from_censo` pegava **so o vintage mais recente**
(`order desc, limit 1`), encontrava vazio e devolvia "censo sem matriculas". A
safra nova e criada antes de o INEP publicar os numeros, entao o topo da lista
vem em branco por meses.

Ou seja: sem consertar o sync, a hidratacao seria um no-op caro. Os dois
precisam existir, e o teste que importa e o do lookback.

## O que NAO muda

ENEM nao se inventa: sem linha em school_enem_yearly, tem_enem=False e a escola
recebe template de matriculas (ou pobre). Nunca se preenche ENEM por analogia.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import Database  # noqa: E402
from utils.template_selector import (  # noqa: E402
    detectar_dados, limpar_cache_enem, selecionar_template,
)


# ===========================================================================
# Banco falso — reproduz o formato real das tabelas envolvidas
# ===========================================================================
class _Q:
    def __init__(self, tabela, dados, updates):
        self.t, self.d, self.up = tabela, dados, updates
        self.filtros, self._desc, self._lim, self._payload = {}, False, None, None

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self.filtros[col] = val
        return self

    def order(self, col, desc=False):
        self._desc = desc
        self._ordem = col
        return self

    def limit(self, n):
        self._lim = n
        return self

    def not_(self):  # pragma: no cover - compat
        return self

    def update(self, payload):
        self._payload = payload
        return self

    def execute(self):
        linhas = [r for r in self.d.get(self.t, [])
                  if all(str(r.get(k)) == str(v) for k, v in self.filtros.items())]
        if self._payload is not None:
            for r in linhas:
                r.update(self._payload)
            self.up.append((self.t, dict(self._payload)))
            return type("R", (), {"data": linhas})()
        if getattr(self, "_ordem", None):
            linhas = sorted(linhas, key=lambda r: r.get(self._ordem) or 0,
                            reverse=self._desc)
        if self._lim:
            linhas = linhas[:self._lim]
        return type("R", (), {"data": linhas})()


class _Client:
    def __init__(self, dados):
        self.dados, self.updates = dados, []

    def table(self, nome):
        return _Q(nome, self.dados, self.updates)


def _db(companies=(), censo=(), catalogo=()):
    d = Database.__new__(Database)
    d.client = _Client({
        "companies": [dict(c) for c in companies],
        "school_censo_yearly": [dict(c) for c in censo],
        "mec_catalog": [dict(c) for c in catalogo],
    })
    return d


def _company(inep="43105114", **extra):
    base = {"id": "c1", "inep_code": inep, "name": "COLEGIO SAO JUDAS TADEU",
            "total_matriculas": 0, "matriculas_fund_af": 0, "matriculas_medio": 0}
    base.update(extra)
    return base


def _censo(inep="43105114", vintage=2024, bas=315, af=98, med=89):
    return {"inep_code": inep, "vintage_censo": vintage, "qt_mat_bas": bas,
            "qt_mat_fund_af": af, "qt_mat_med": med, "qt_doc_bas": 36}


# ===========================================================================
# (a) sem matriculas + censo disponivel -> hidrata
# ===========================================================================
def test_hidrata_do_censo_quando_a_company_esta_zerada():
    db = _db(companies=[_company()], censo=[_censo()])
    out = db.hydrate_company_matriculas(_company())
    assert out["total_matriculas"] == 315
    assert out["matriculas_fund_af"] == 98


def test_o_dict_devolvido_e_o_atualizado_nao_o_de_entrada():
    """O bug classico deste caminho: banco muda, seletor le a copia velha."""
    db = _db(companies=[_company()], censo=[_censo()])
    entrada = _company()
    out = db.hydrate_company_matriculas(entrada)
    assert out["total_matriculas"] == 315
    assert entrada["total_matriculas"] == 0, "o dict de entrada nao deve ser mutado"
    assert out is not entrada


def test_safra_mais_nova_vazia_cai_na_anterior():
    """A CAUSA RAIZ: censo 2025 existe com tudo NULL, 2024 tem o numero.

    Eram 8 de 8 escolas zeradas do CRM exatamente assim. Sem o lookback, o
    sync devolve "censo sem matriculas" e a hidratacao vira no-op caro.
    """
    db = _db(companies=[_company()],
             censo=[_censo(vintage=2025, bas=None, af=None, med=None),
                    _censo(vintage=2024, bas=315, af=98)])
    r = db.sync_company_matriculas_from_censo("43105114")
    assert r["updated"] is True
    assert r["vintage"] == 2024, "usou a safra vazia em vez de voltar uma"
    assert r["fields"]["total_matriculas"] == 315


def test_prefere_a_safra_mais_recente_que_tem_dado():
    db = _db(companies=[_company()],
             censo=[_censo(vintage=2023, bas=393), _censo(vintage=2024, bas=315),
                    _censo(vintage=2025, bas=None, af=None, med=None)])
    r = db.sync_company_matriculas_from_censo("43105114")
    assert r["vintage"] == 2024 and r["fields"]["total_matriculas"] == 315


def test_todas_as_safras_vazias_nao_atualiza():
    db = _db(companies=[_company()],
             censo=[_censo(vintage=v, bas=None, af=None, med=None)
                    for v in (2023, 2024, 2025)])
    r = db.sync_company_matriculas_from_censo("43105114")
    assert r["updated"] is False and "matricula" in r["reason"]


# ===========================================================================
# (c) escola que ja tem numero NAO pode ser sobrescrita
# ===========================================================================
def test_company_com_matriculas_nao_e_clobbered():
    ja = _company(total_matriculas=2179, matriculas_fund_af=709)
    db = _db(companies=[ja], censo=[_censo(bas=315, af=98)])
    out = db.hydrate_company_matriculas(ja)
    assert out["total_matriculas"] == 2179, "numero do CRM foi sobrescrito pelo censo"
    assert db.client.updates == [], "nao deveria ter escrito nada"


def test_so_matriculas_medio_preenchido_ja_conta_como_tem_dado():
    ja = _company(total_matriculas=0, matriculas_fund_af=0, matriculas_medio=443)
    db = _db(companies=[ja], censo=[_censo(bas=315)])
    assert db.hydrate_company_matriculas(ja)["matriculas_medio"] == 443
    assert db.client.updates == []


# ===========================================================================
# (d) sem censo e sem catalogo -> nao quebra, segue pobre
# ===========================================================================
def test_sem_nenhuma_fonte_nao_quebra():
    db = _db(companies=[_company()])
    out = db.hydrate_company_matriculas(_company())
    assert out["total_matriculas"] == 0
    assert detectar_dados(out)["matriculas"] is False


def test_company_sem_inep_sai_na_hora():
    db = _db(companies=[])
    out = db.hydrate_company_matriculas({"id": "x", "name": "Sem INEP"})
    assert out["name"] == "Sem INEP"
    assert db.client.updates == []


def test_fallback_do_catalogo_quando_nao_ha_censo():
    db = _db(companies=[_company()],
             catalogo=[{"inep_code": "43105114", "total_matriculas": 1831,
                        "matriculas_fund_af": 865, "matriculas_medio": 667}])
    out = db.hydrate_company_matriculas(_company())
    assert out["total_matriculas"] == 1831


def test_catalogo_zerado_nao_conta_como_dado():
    db = _db(companies=[_company()],
             catalogo=[{"inep_code": "43105114", "total_matriculas": 0,
                        "matriculas_fund_af": 0, "matriculas_medio": 0}])
    out = db.hydrate_company_matriculas(_company())
    assert out["total_matriculas"] == 0
    assert db.client.updates == []


# ===========================================================================
# (b) "ja no CRM" tem que sincronizar, nao ser no-op silencioso
# ===========================================================================
def test_ja_no_crm_zerada_e_hidratada_no_reimport():
    db = _db(companies=[_company()], censo=[_censo()])
    r = db.import_company_from_catalog("43105114")
    assert r["already"] is True and r["ok"] is True
    assert db.client.dados["companies"][0]["total_matriculas"] == 315


def test_ja_no_crm_com_numero_nao_escreve_nada():
    db = _db(companies=[_company(total_matriculas=2179)], censo=[_censo()])
    db.import_company_from_catalog("43105114")
    assert db.client.updates == []


# ===========================================================================
# Efeito no que motivou tudo: o template escolhido
# ===========================================================================
TEMPLATES = [
    {"id": "t_pobre", "name": "Sem dados", "is_active": True,
     "audience_type": "nominal", "data_profile": "nenhum"},
    {"id": "t_mat", "name": "Com matriculas", "is_active": True,
     "audience_type": "nominal", "data_profile": "matriculas"},
    {"id": "t_ambos", "name": "Matriculas + ENEM", "is_active": True,
     "audience_type": "nominal", "data_profile": "ambos"},
]
CONTATO = {"full_name": "Maria Silva", "email": "maria.silva@colegio.com.br",
           "source": "apollo"}


@pytest.fixture(autouse=True)
def _cache_limpo():
    limpar_cache_enem()
    yield
    limpar_cache_enem()


def test_apos_hidratar_a_escola_ganha_template_com_numeros(monkeypatch):
    """O criterio de sucesso do pedido, ponta a ponta (sem ENEM)."""
    import utils.template_selector as ts
    monkeypatch.setattr(ts, "_tem_enem", lambda _i: False)

    db = _db(companies=[_company()], censo=[_censo()])
    antes = selecionar_template(_company(), CONTATO, TEMPLATES)
    assert antes["id"] == "t_pobre", "sem hidratar, template pobre (o bug)"

    depois = selecionar_template(db.hydrate_company_matriculas(_company()),
                                 CONTATO, TEMPLATES)
    assert depois["id"] == "t_mat"


def test_enem_nao_se_inventa(monkeypatch):
    """Com matriculas mas SEM linha de ENEM, nao pode escolher 'ambos'."""
    import utils.template_selector as ts
    monkeypatch.setattr(ts, "_tem_enem", lambda _i: False)

    db = _db(companies=[_company()], censo=[_censo()])
    escolhido = selecionar_template(db.hydrate_company_matriculas(_company()),
                                    CONTATO, TEMPLATES)
    assert escolhido["id"] != "t_ambos"


def test_com_enem_real_sobe_para_ambos(monkeypatch):
    import utils.template_selector as ts
    monkeypatch.setattr(ts, "_tem_enem", lambda _i: True)

    db = _db(companies=[_company()], censo=[_censo()])
    escolhido = selecionar_template(db.hydrate_company_matriculas(_company()),
                                    CONTATO, TEMPLATES)
    assert escolhido["id"] == "t_ambos"


def test_enem_sozinho_sem_matricula_nao_vira_ambos(monkeypatch):
    import utils.template_selector as ts
    monkeypatch.setattr(ts, "_tem_enem", lambda _i: True)

    tpls = TEMPLATES + [{"id": "t_enem", "name": "So ENEM", "is_active": True,
                         "audience_type": "nominal", "data_profile": "enem"}]
    escolhido = selecionar_template(_company(), CONTATO, tpls)
    assert escolhido["id"] == "t_enem"


# ===========================================================================
# Guardas de codigo: a hidratacao tem que acontecer ANTES da escolha
# ===========================================================================
def test_writer_hidrata_antes_de_selecionar_template():
    import ast
    src = (ROOT / "agents" / "writer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    hidrata = sel = None
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        if n.func.attr == "hydrate_company_matriculas" and hidrata is None:
            hidrata = n.lineno
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "selecionar_template"):
            sel = n.lineno
    assert hidrata, "o writer parou de hidratar a escola"
    assert sel and hidrata < sel, (
        "hidratacao caiu DEPOIS da escolha do template — o seletor volta a "
        "decidir com o dict velho")


def test_hidratacao_e_reatribuida():
    """`db.hydrate_company_matriculas(company)` sem `company =` nao faz nada."""
    import ast
    tree = ast.parse((ROOT / "agents" / "writer.py").read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)):
            continue
        f = n.value.func
        if isinstance(f, ast.Attribute) and f.attr == "hydrate_company_matriculas":
            raise AssertionError(
                f"writer.py:{n.lineno} chama hydrate sem usar o retorno — "
                f"o dict novo e descartado e a escolha segue com o antigo")
