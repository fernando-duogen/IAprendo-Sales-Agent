# -*- coding: utf-8 -*-
"""Identidade de saida do e-mail: quem OPERA != quem ASSINA.

Contexto (Ago/2026): o dono roda um agente que opera a plataforma logado como
`vendedor1`. O trabalho tem que ficar vinculado a ELE (leads, metas,
created_by), mas os e-mails saem como o Fernando — mesmo remetente, mesmo nome
no corpo, mesma assinatura, mesmos anexos.

A identidade de e-mail morava em tres lugares independentes indexados por
username, nenhum com heranca:
  - `config/users.yaml` (email, email_sender_name)
  - assinatura: marcador [EMAIL_SIGNATURE_USER:<user>] em conversation_memory
  - anexos:     marcador [EMAIL_ATTACHMENTS:<user>]

`email_identity_from` resolve os tres num ponto so, sem copiar dado: editar a
assinatura do fernando muda a de quem herda dele no mesmo instante.

O TESTE QUE MAIS IMPORTA e test_heranca_nao_vaza_para_atribuicao: se a heranca
escapar para owner_username/created_by, o agente deixa de ser distinguivel do
dono — que e exatamente o motivo de ele existir.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import sender_profile as sp  # noqa: E402
from utils.sender_profile import _resolve_identity_username  # noqa: E402


# ---------------------------------------------------------------------------
# Resolucao da cadeia (funcao pura — nao depende do users.yaml real)
# ---------------------------------------------------------------------------
def _perfis(**pares):
    """{'a': 'b'} => perfil 'a' herda identidade de 'b'. '' = nao herda."""
    return {u: {"username": u, "email_identity_from": alvo}
            for u, alvo in pares.items()}


def test_sem_heranca_assina_como_ele_mesmo():
    p = _perfis(fernando="", charles="")
    assert _resolve_identity_username("fernando", p) == "fernando"
    assert _resolve_identity_username("charles", p) == "charles"


def test_heranca_simples():
    p = _perfis(vendedor1="fernando", fernando="")
    assert _resolve_identity_username("vendedor1", p) == "fernando"


def test_heranca_em_cadeia():
    p = _perfis(a="b", b="c", c="")
    assert _resolve_identity_username("a", p) == "c"


def test_ciclo_nao_trava_e_volta_pro_proprio():
    """a->b->a. Identidade errada e pior que heranca perdida."""
    p = _perfis(a="b", b="a")
    assert _resolve_identity_username("a", p) == "a"
    assert _resolve_identity_username("b", p) == "b"


def test_auto_referencia_nao_trava():
    p = _perfis(a="a")
    assert _resolve_identity_username("a", p) == "a"


def test_alvo_inexistente_assina_como_ele_mesmo():
    p = _perfis(vendedor1="fantasma")
    assert _resolve_identity_username("vendedor1", p) == "vendedor1"


def test_usuario_desconhecido_nao_quebra():
    assert _resolve_identity_username("ninguem", _perfis(a="")) == "ninguem"


# ---------------------------------------------------------------------------
# get_email_identity com perfis injetados
# ---------------------------------------------------------------------------
FIXTURE = {
    "chefe": {
        "username": "chefe", "name": "Chefe Real", "email": "chefe@x.com",
        "email_sender_name": "Chefe Real | EMPRESA", "phone": "+5551999",
        "role": "CEO", "is_admin": True, "whatsapp_numbers": [],
        "email_identity_from": "",
    },
    "agente": {
        "username": "agente", "name": "Vendedor 1", "email": "agente@x.com",
        "email_sender_name": "Vendedor 1", "phone": "", "role": "Vendedor",
        "is_admin": False, "whatsapp_numbers": [],
        "email_identity_from": "chefe",
    },
}


@pytest.fixture
def perfis(monkeypatch):
    monkeypatch.setattr(sp, "_load_profiles", lambda: FIXTURE)
    return FIXTURE


def test_agente_assina_com_todos_os_campos_do_chefe(perfis):
    ident = sp.get_email_identity("agente")
    assert ident["email"] == "chefe@x.com", "o De: tem que ser o do chefe"
    assert ident["email_sender_name"] == "Chefe Real | EMPRESA"
    assert ident["name"] == "Chefe Real", "o corpo do e-mail assina como o chefe"
    assert ident["phone"] == "+5551999"


def test_assinatura_e_anexos_indexam_pelo_chefe(perfis):
    """signature_username do brevo_sender sai daqui."""
    assert sp.get_email_identity_username("agente") == "chefe"


def test_quem_nao_herda_segue_igual(perfis):
    assert sp.get_email_identity("chefe")["username"] == "chefe"
    assert sp.get_email_identity_username("chefe") == "chefe"


def test_perfil_do_operador_nao_e_alterado(perfis):
    """A heranca e so na SAIDA — o cadastro dele continua o dele."""
    op = sp.get_profile_by_username("agente")
    assert op["name"] == "Vendedor 1"
    assert op["is_admin"] is False


def test_heranca_nao_vaza_para_atribuicao(perfis):
    """O teste central: owner_username/created_by continuam do OPERADOR.

    Se isto quebrar, o agente vira indistinguivel do dono no CRM — e some a
    unica razao de ele existir como usuario separado.
    """
    sp.set_active_sender_for_thread("agente")
    try:
        assert sp.get_active_sender_username() == "agente"
        assert sp.get_active_sender()["username"] == "agente"
        assert sp.get_email_identity()["username"] == "chefe"
        assert sp.get_email_identity_username() == "chefe"
    finally:
        sp.clear_active_sender_for_thread()


def test_usuario_fora_do_cadastro_nao_explode(perfis):
    ident = sp.get_email_identity("nao_existe")
    assert ident.get("username") is not None


# ---------------------------------------------------------------------------
# Cadastro real (users.yaml e gitignored — pula quando ausente)
# ---------------------------------------------------------------------------
def test_vendedor1_configurado_no_ambiente():
    perfil = sp.get_profile_by_username("vendedor1")
    if perfil is None:
        pytest.skip("vendedor1 nao cadastrado aqui (users.yaml e gitignored)")
    assert sp.get_email_identity_username("vendedor1") == "fernando"
    assert perfil["is_admin"] is False
    # numero repetido trocaria identidades em silencio no IAlex
    assert perfil["whatsapp_numbers"] == []


# ---------------------------------------------------------------------------
# AST: os consumidores de SAIDA nao podem voltar a usar o sender ativo
# ---------------------------------------------------------------------------
CONSUMIDORES = [
    ROOT / "tools" / "brevo_sender.py",
    ROOT / "agents" / "writer.py",
    ROOT / "workflows" / "follow_up_manager.py",
]


PROIBIDOS = {"get_active_sender", "get_active_sender_username"}


def _chamadas_resolvendo_alias(tree) -> set:
    """Nomes de sender_profile realmente chamados, seguindo `import ... as`.

    Sem resolver o alias esta guarda seria decorativa: o follow_up_manager
    importava exatamente assim (`get_active_sender as _get_active_sender_fu`) e
    passaria batido.
    """
    alias = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("sender_profile"):
            for a in n.names:
                alias[a.asname or a.name] = a.name
    usados = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            usados.add(alias.get(n.func.id, n.func.id))
    return usados


@pytest.mark.parametrize("path", CONSUMIDORES, ids=lambda p: p.stem)
def test_consumidor_de_saida_usa_a_identidade(path):
    """get_active_sender() aqui faria o e-mail sair assinado 'Vendedor 1'."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    chamadas = _chamadas_resolvendo_alias(tree)
    assert "get_active_sender" not in chamadas, (
        f"{path.name} voltou a montar o remetente com o sender ativo; "
        f"use get_email_identity()"
    )
    assert "get_active_sender_username" not in chamadas, (
        f"{path.name}: assinatura/anexos devem indexar por "
        f"get_email_identity_username()"
    )


def test_auto_claim_usa_o_operador_nao_a_identidade():
    """approve_message carimba a identidade em send_as_username; o dono do lead
    NAO pode sair desse mesmo valor, senao o lead do agente vira do fernando."""
    src = (ROOT / "database" / "supabase_client.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    alvo = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "claim_company_if_unowned":
            alvo = n
    assert alvo is not None, "claim_company_if_unowned sumiu"
    nomes = {x.id for x in ast.walk(alvo) if isinstance(x, ast.Name)}
    assert "send_as_username" not in nomes, (
        "o auto-claim voltou a usar send_as_username (a IDENTIDADE) como dono "
        "do lead — tem que usar quem opera"
    )
