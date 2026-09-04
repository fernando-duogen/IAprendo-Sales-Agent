# -*- coding: utf-8 -*-
"""BCC no envio de producao: o operador ve o e-mail como o cliente recebeu.

Contexto (04/09/2026). O disparo real ia so para a escola. Nao havia copia pra
ninguem — nao dava pra conferir o que efetivamente saiu (assinatura, anexos,
graficos, HTML final). O "Enviar teste" da fila resolve o PREVIEW, mas manda
outro e-mail, com "[TESTE]" no assunto e sem queue_id: nao e o mesmo artefato.

Estes testes inspecionam o PAYLOAD que vai pro Brevo — coisa que
tests/test_brevo_retry.py nunca fez (ele so olha o dict de retorno e o
call_count). Sem olhar o payload, "adicionei o bcc" e uma afirmacao sem prova.

Tres invariantes valem mais que os outros:
  - o e-mail do CLIENTE nao muda em nada por causa do BCC (assunto e corpo
    identicos com e sem copia) — o BCC recebe o mesmo conteudo, entao qualquer
    alteracao pra "marcar a copia" vazaria pra escola;
  - BCC invalido NAO derruba o envio: o Brevo responde 400 e 400 nao tem retry,
    ou seja um typo no .env faria a escola ficar sem o e-mail;
  - "Enviar teste" nunca copia ninguem.
"""
import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.brevo_sender import BrevoSender, _resolver_bcc  # noqa: E402

SEND_APPROVED = ROOT / "workflows" / "send_approved.py"
BREVO = ROOT / "tools" / "brevo_sender.py"


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("time.sleep", lambda *a, **k: None):
        yield


@pytest.fixture
def bcc_env(monkeypatch):
    """Define BREVO_BCC_EMAIL (settings le do ambiente a cada acesso)."""
    def _set(valor):
        monkeypatch.setenv("BREVO_BCC_EMAIL", valor)
    yield _set


def _resp(status=201, json_data=None, text=""):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data or {"messageId": "<id>"}
    m.text = text
    return m


def _sender():
    s = BrevoSender()
    s.api_key = "test-key"
    s._enabled = True
    return s


def _enviar(mpost, *, with_bcc=True, to="escola@colegio.com.br", subject="Assunto"):
    """Envia e devolve o JSON que teria ido pro Brevo."""
    mpost.return_value = _resp()
    _sender().send_email(
        to_email=to, to_name="Diretor", subject=subject, body="corpo",
        from_email="a@b.com", from_name="A", attachments=[], with_bcc=with_bcc,
    )
    return mpost.call_args.kwargs["json"]


# ---------------------------------------------------------------------------
# O payload
# ---------------------------------------------------------------------------
@patch("tools.brevo_sender.requests.post")
def test_bcc_entra_no_payload(mpost, bcc_env):
    bcc_env("fernando@duogen.com.br")
    assert _enviar(mpost)["bcc"] == [{"email": "fernando@duogen.com.br"}]


@patch("tools.brevo_sender.requests.post")
def test_sem_with_bcc_a_chave_nem_existe(mpost, bcc_env):
    """Default False: chave ausente, nao lista vazia (o Brevo recusaria [])."""
    bcc_env("fernando@duogen.com.br")
    assert "bcc" not in _enviar(mpost, with_bcc=False)


@patch("tools.brevo_sender.requests.post")
def test_env_vazio_nao_cria_a_chave(mpost, bcc_env):
    bcc_env("")
    assert "bcc" not in _enviar(mpost)


@patch("tools.brevo_sender.requests.post")
def test_lista_com_varios_preserva_ordem(mpost, bcc_env):
    bcc_env("a@x.com, b@y.com , c@z.com")
    assert _enviar(mpost)["bcc"] == [
        {"email": "a@x.com"}, {"email": "b@y.com"}, {"email": "c@z.com"}]


@patch("tools.brevo_sender.requests.post")
def test_bcc_nao_vaza_para_o_to(mpost, bcc_env):
    """O destinatario visivel continua sendo so a escola."""
    bcc_env("fernando@duogen.com.br")
    p = _enviar(mpost)
    assert p["to"] == [{"email": "escola@colegio.com.br", "name": "Diretor"}]


# ---------------------------------------------------------------------------
# O e-mail do cliente nao pode mudar
# ---------------------------------------------------------------------------
@patch("tools.brevo_sender.requests.post")
def test_assunto_e_corpo_identicos_com_e_sem_bcc(mpost, bcc_env):
    """O BCC recebe o MESMO conteudo do cliente (confirmado na API do Brevo).

    Logo, qualquer tentativa de "marcar" a copia (ex: prefixo [COPIA]) mudaria
    o e-mail da escola. Este teste existe pra que isso nao seja adicionado sem
    alguem perceber.
    """
    bcc_env("fernando@duogen.com.br")
    com = _enviar(mpost, with_bcc=True)
    mpost.reset_mock()
    sem = _enviar(mpost, with_bcc=False)
    for campo in ("subject", "htmlContent", "textContent", "sender", "to"):
        assert com[campo] == sem[campo], f"{campo} mudou por causa do BCC"


# ---------------------------------------------------------------------------
# Dedup contra o destinatario (requisito 4)
# ---------------------------------------------------------------------------
def test_to_igual_ao_bcc_pula_a_copia(bcc_env):
    bcc_env("fernando@duogen.com.br")
    assert _resolver_bcc("fernando@duogen.com.br") == []


def test_comparacao_ignora_caixa_e_espacos(bcc_env):
    bcc_env("  Fernando@Duogen.com.BR  ")
    assert _resolver_bcc("fernando@duogen.com.br") == []


def test_na_lista_so_o_duplicado_sai(bcc_env):
    bcc_env("fernando@duogen.com.br, socio@duogen.com.br")
    assert _resolver_bcc("fernando@duogen.com.br") == [{"email": "socio@duogen.com.br"}]


def test_duplicata_dentro_da_lista(bcc_env):
    bcc_env("a@x.com, A@X.com")
    assert _resolver_bcc("escola@z.com") == [{"email": "a@x.com"}]


# ---------------------------------------------------------------------------
# Robustez: a copia nunca pode custar o e-mail do cliente
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ruim", ["fernando", "@duogen.com.br", "a@b", "a b@c.com", "a@@b.com"])
def test_endereco_invalido_e_descartado(ruim, bcc_env):
    bcc_env(ruim)
    assert _resolver_bcc("escola@z.com") == []


@patch("tools.brevo_sender.requests.post")
def test_invalido_na_lista_nao_impede_o_envio(mpost, bcc_env):
    """O caso que motivou a validacao: 400 do Brevo nao tem retry.

    Um typo no .env mandaria o payload inteiro pro lixo — e a ESCOLA ficaria
    sem o e-mail por causa de uma conveniencia do operador.
    """
    bcc_env("valido@duogen.com.br, tYpo-sem-arroba")
    p = _enviar(mpost)
    assert p["bcc"] == [{"email": "valido@duogen.com.br"}]
    assert p["subject"] == "Assunto", "o envio ao cliente seguiu normal"


@patch("tools.brevo_sender.requests.post")
def test_config_quebrada_nao_derruba_o_envio(mpost, monkeypatch):
    """Se ler a config explodir, envia sem BCC em vez de nao enviar."""
    import tools.brevo_sender as bs

    class _Explode:
        @property
        def BREVO_BCC_EMAIL(self):
            raise RuntimeError("config corrompida")
        def __getattr__(self, _n):
            return ""

    monkeypatch.setattr(bs, "settings", _Explode())
    p = _enviar(mpost)
    assert "bcc" not in p
    assert p["subject"] == "Assunto"


# ---------------------------------------------------------------------------
# Quem liga o BCC (requisito 3) e quem nunca liga (requisito: nao no teste)
# ---------------------------------------------------------------------------
def _chamadas_send_email(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "send_email"]


def test_o_envio_de_producao_liga_o_bcc():
    """send_approved e o unico caminho pra lead real — "Enviar agora", ciclo
    IAlex, agendador e follow-ups todos passam por ele."""
    chamadas = _chamadas_send_email(SEND_APPROVED)
    assert len(chamadas) == 1, "apareceu outro envio de producao — revisar o BCC nele"
    kw = {k.arg: k.value for k in chamadas[0].keywords}
    assert isinstance(kw.get("with_bcc"), ast.Constant) and kw["with_bcc"].value is True, (
        "o envio de producao parou de mandar copia pro operador")


TELAS_DE_TESTE = [
    ROOT / "dashboard" / "pages" / "6_✉️_Comunicacao.py",
    ROOT / "dashboard" / "pages" / "5_📊_Pipeline.py",
    ROOT / "agent" / "brain.py",
]


@pytest.mark.parametrize("path", TELAS_DE_TESTE, ids=lambda p: p.stem)
def test_enviar_teste_nunca_copia_ninguem(path):
    """"Enviar teste" ja vai pro endereco de teste — copiar seria ruido."""
    for c in _chamadas_send_email(path):
        kw = {k.arg for k in c.keywords}
        assert "with_bcc" not in kw, (
            f"{path.name}:{c.lineno} — envio de teste passou a mandar BCC")


def test_default_do_parametro_e_false():
    """A protecao real: caminho novo nasce SEM copiar, e opta por copiar.

    Se o default fosse True, qualquer envio de teste futuro copiaria o
    operador sem ninguem decidir isso.
    """
    fn = next(n for n in ast.walk(ast.parse(BREVO.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "send_email")
    nomes = [a.arg for a in fn.args.args]
    assert "with_bcc" in nomes, "send_email perdeu o parametro with_bcc"
    idx = nomes.index("with_bcc") - (len(nomes) - len(fn.args.defaults))
    assert idx >= 0, "with_bcc virou parametro obrigatorio"
    assert fn.args.defaults[idx].value is False, (
        "o default do with_bcc deixou de ser False — envio de teste passaria "
        "a copiar o operador sem ninguem decidir isso")


def test_log_registra_o_bcc_e_nao_a_chave():
    """Requisito: logar bcc sem expor a API key.

    A key nunca entrou em log (vai so no header do request); este teste trava
    isso junto com a presenca do bcc no log de sucesso.
    """
    src = BREVO.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("info", "warning", "error", "debug")):
            continue
        for kw in n.keywords:
            if kw.arg != "extra" or not isinstance(kw.value, ast.Dict):
                continue
            for v in ast.walk(kw.value):
                if isinstance(v, ast.Attribute) and v.attr == "api_key":
                    raise AssertionError(f"api_key em log na linha {n.lineno}")
    assert '"bcc": ",".join' in src, "o log de sucesso parou de registrar o bcc"


# ---------------------------------------------------------------------------
# O status precisa CHEGAR na tela (Ajustes -> Diagnostico)
# ---------------------------------------------------------------------------
HEALTH = ROOT / "tools" / "health_check.py"
CONFIGS = ROOT / "dashboard" / "pages" / "9_⚙️_Configuracoes.py"


def _lista_de_nomes(path, nome_var):
    """Strings literais dentro da atribuicao `nome_var = [...]` ou `{...}`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        alvos = [t.id for t in n.targets if isinstance(t, ast.Name)]
        if nome_var not in alvos:
            continue
        if isinstance(n.value, ast.Dict):
            return {k.value for k in n.value.keys if isinstance(k, ast.Constant)}
        if isinstance(n.value, (ast.List, ast.Tuple)):
            out = set()
            for el in n.value.elts:
                if isinstance(el, ast.Tuple) and el.elts and isinstance(el.elts[0], ast.Constant):
                    out.add(el.elts[0].value)
            return out
    raise AssertionError(f"nao achei `{nome_var}` em {path.name}")


def test_todo_check_tem_rotulo_na_tela():
    """Um check sem rotulo aparecia com o nome cru — ou nem aparecia.

    A grade era `for row_start in (0, 5)`: fixa em 10 checks. O check de e-mail
    rodava no health_check e ficava INVISIVEL, sem erro nenhum. Este teste trava
    a correspondencia entre o que o health_check produz e o que a tela nomeia.
    """
    executados = _lista_de_nomes(HEALTH, "checks_order")
    rotulados = _lista_de_nomes(CONFIGS, "check_labels")
    assert "email_config" in executados, "o check de config de e-mail sumiu"
    faltando = executados - rotulados
    assert not faltando, f"check(s) sem rotulo na tela de Diagnostico: {sorted(faltando)}"


def test_grade_do_diagnostico_nao_tem_numero_fixo_de_linhas():
    """A grade tem que acompanhar a quantidade de checks, nao um literal."""
    tree = ast.parse(CONFIGS.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if not (isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                and n.target.id == "row_start"):
            continue
        assert isinstance(n.iter, ast.Call), (
            "a grade do Diagnostico voltou a iterar linhas fixas — "
            "check novo fica invisivel")
        return
    raise AssertionError("nao encontrei a grade de checks do Diagnostico")
