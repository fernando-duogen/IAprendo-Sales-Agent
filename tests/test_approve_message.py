# -*- coding: utf-8 -*-
"""approve_message: nao pode quebrar por coluna ausente, nem esconder o motivo.

Contexto (Ago/2026). Um agente reportou "Falha ao aprovar." no painel. A causa
foi uma regressao do commit 4148d0f: o carimbo de identidade passou a preencher
`send_as_username` sempre que ha usuario ativo, e com isso `metadata` entrou em
TODA aprovacao — mas `approval_queue` NUNCA teve essa coluna (confirmado no
banco: `42703: column "metadata" does not exist`). Resultado: PostgREST recusa o
UPDATE, o except externo devolve False e a tela diz "Falha ao aprovar." sem
motivo. Quebrou para TODOS os usuarios, nao so o agente.

POR QUE A SUITE NAO PEGOU — e o que estes testes corrigem:
`tests/test_e2e_v2.py:261` chama queue_manager.approve() contra o banco real e
PASSA, porque nos testes nao ha thread-local nem sessao: o sender ativo cai no
fallback .env, get_email_identity_username() devolve None, `need_metadata` fica
False e `metadata` nunca entra no UPDATE. A suite passava por nao reproduzir a
condicao que dispara o bug. Por isso todo teste aqui roda COM IDENTIDADE ATIVA.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import get_db  # noqa: E402
from utils import sender_profile as sp  # noqa: E402

# `db` do modulo e um proxy (_LazyDB) que delega por __getattr__: um
# monkeypatch nele NAO chega no objeto real, e o teste acabaria batendo no banco
# de PRODUCAO. Peguei isso na primeira execucao — os testes tem que agir sobre a
# instancia real devolvida por get_db().
db = get_db()

QUEUE_ID = "11111111-1111-1111-1111-111111111111"
COMPANY_ID = "22222222-2222-2222-2222-222222222222"

# 'agente' opera; assina como 'chefe'. Mesma forma do users.yaml real.
PERFIS = {
    "chefe": {"username": "chefe", "name": "Chefe", "email": "chefe@x.com",
              "email_sender_name": "Chefe | EMPRESA", "phone": "", "role": "CEO",
              "is_admin": True, "whatsapp_numbers": [], "email_identity_from": ""},
    "agente": {"username": "agente", "name": "Vendedor 1", "email": "ag@x.com",
               "email_sender_name": "Vendedor 1", "phone": "", "role": "Vendedor",
               "is_admin": False, "whatsapp_numbers": [],
               "email_identity_from": "chefe"},
}


# ---------------------------------------------------------------------------
# Cliente Supabase falso: registra os UPDATEs e simula coluna ausente
# ---------------------------------------------------------------------------
class _Resultado:
    def __init__(self, data):
        self.data = data


class _Consulta:
    def __init__(self, cliente):
        self._c = cliente
        self._op = None
        self._payload = None

    def select(self, *a, **k):
        self._op = "select"
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, *a, **k):
        return self

    def single(self):
        return self

    def execute(self):
        if self._op == "select":
            if self._c.tem_metadata:
                return _Resultado({"metadata": dict(self._c.metadata_atual)})
            raise Exception('column approval_queue.metadata does not exist')
        # UPDATE
        self._c.updates.append(dict(self._payload))
        if not self._c.tem_metadata and "metadata" in self._payload:
            # PostgREST: PGRST204 / 42703
            raise Exception(
                "{'code': 'PGRST204', 'message': \"Could not find the "
                "'metadata' column of 'approval_queue' in the schema cache\"}")
        if self._c.cas_vazio:
            return _Resultado([])
        return _Resultado([{"id": QUEUE_ID, "company_id": COMPANY_ID}])


class _ClienteFake:
    def __init__(self, tem_metadata=True, cas_vazio=False):
        self.tem_metadata = tem_metadata
        self.cas_vazio = cas_vazio
        self.metadata_atual = {}
        self.updates = []

    def table(self, _nome):
        return _Consulta(self)


@pytest.fixture
def ambiente(monkeypatch):
    """Identidade ativa ('agente' assinando como 'chefe') + claim capturado."""
    monkeypatch.setattr(sp, "_load_profiles", lambda: PERFIS)
    claims = []

    def _claim(cid, username=None):
        # Fiel ao real (supabase_client.claim_company_if_unowned): quando o
        # chamador passa None, o dono e resolvido do sender ATIVO. Registrar o
        # valor resolvido — nao o argumento — e o que faz o teste medir o
        # resultado (lead do operador) em vez da forma da chamada.
        claims.append(username or sp.get_active_sender_username())

    monkeypatch.setattr(db, "claim_company_if_unowned", _claim)
    sp.set_active_sender_for_thread("agente")
    yield claims
    sp.clear_active_sender_for_thread()


def _ultimo_update(cli):
    return cli.updates[-1]


# ---------------------------------------------------------------------------
# 1) Coluna AUSENTE: aprova mesmo assim (o caminho que destrava producao)
# ---------------------------------------------------------------------------
def test_aprova_mesmo_sem_a_coluna_metadata(monkeypatch, ambiente):
    cli = _ClienteFake(tem_metadata=False)
    monkeypatch.setattr(db, "client", cli)

    erros = []
    assert db.approve_message(QUEUE_ID, error_out=erros) is True, (
        f"aprovacao falhou sem a coluna metadata: {erros}")
    assert erros == []
    assert len(cli.updates) == 2, "esperava 1 tentativa com metadata + 1 retry sem"
    assert "metadata" in cli.updates[0], "a 1a tentativa deveria carregar o carimbo"
    assert "metadata" not in cli.updates[1], "o retry tem que sair SEM metadata"
    assert cli.updates[1]["status"] == "approved", "o status precisa aterrissar"


def test_sem_a_coluna_o_dono_do_lead_continua_o_operador(monkeypatch, ambiente):
    """Mesmo no caminho degradado, o lead nao pode ir para o 'chefe'."""
    monkeypatch.setattr(db, "client", _ClienteFake(tem_metadata=False))
    assert db.approve_message(QUEUE_ID) is True
    assert ambiente == ["agente"]


def test_agendamento_tambem_e_tolerante(monkeypatch, ambiente):
    """scheduled_send_at cai na mesma classe de risco que metadata."""
    cli = _ClienteFake(tem_metadata=False)
    monkeypatch.setattr(db, "client", cli)
    assert db.approve_message(QUEUE_ID, scheduled_send_at="2026-09-01T10:00:00Z") is True
    assert _ultimo_update(cli)["status"] == "approved"


# ---------------------------------------------------------------------------
# 2) Coluna PRESENTE: o carimbo de identidade grava
# ---------------------------------------------------------------------------
def test_com_a_coluna_grava_o_carimbo_da_identidade(monkeypatch, ambiente):
    cli = _ClienteFake(tem_metadata=True)
    monkeypatch.setattr(db, "client", cli)

    assert db.approve_message(QUEUE_ID) is True
    assert len(cli.updates) == 1, "com a coluna presente nao deve haver retry"
    meta = _ultimo_update(cli)["metadata"]
    assert meta["send_as_username"] == "chefe", "assina como a IDENTIDADE"


def test_carimbo_nao_vira_dono_do_lead(monkeypatch, ambiente):
    """O invariante que este bug quase destruiu: quem assina != quem opera."""
    monkeypatch.setattr(db, "client", _ClienteFake(tem_metadata=True))
    db.approve_message(QUEUE_ID)
    assert ambiente == ["agente"], "o lead do agente nao pode ir para o chefe"


def test_override_explicito_de_admin_vence_o_carimbo(monkeypatch, ambiente):
    cli = _ClienteFake(tem_metadata=True)
    monkeypatch.setattr(db, "client", cli)
    db.approve_message(QUEUE_ID, send_as_username="chefe")
    assert _ultimo_update(cli)["metadata"]["send_as_username"] == "chefe"
    # com override explicito, o dono do lead e o alvo do override (comportamento
    # historico do "Enviar como"), nao o carimbo automatico
    assert ambiente == ["chefe"]


def test_override_de_anexos_preservado(monkeypatch, ambiente):
    cli = _ClienteFake(tem_metadata=True)
    monkeypatch.setattr(db, "client", cli)
    db.approve_message(QUEUE_ID, attachment_urls=[])
    assert _ultimo_update(cli)["metadata"]["attachment_urls"] == []


# ---------------------------------------------------------------------------
# 3) O motivo da falha para de ser escondido
# ---------------------------------------------------------------------------
def test_erro_inesperado_devolve_o_motivo(monkeypatch, ambiente):
    """Erro que NAO e coluna ausente nao pode ser mascarado nem re-tentado."""
    class _Explode(_ClienteFake):
        def table(self, _n):
            raise Exception("boom: conexao recusada")

    monkeypatch.setattr(db, "client", _Explode())
    erros = []
    assert db.approve_message(QUEUE_ID, error_out=erros) is False
    assert erros and "boom" in erros[0]


def test_cas_vazio_explica_que_nao_esta_mais_pendente(monkeypatch, ambiente):
    monkeypatch.setattr(db, "client", _ClienteFake(tem_metadata=True, cas_vazio=True))
    erros = []
    assert db.approve_message(QUEUE_ID, error_out=erros) is False
    assert erros and "pendente" in erros[0].lower()


def test_error_out_e_opcional(monkeypatch, ambiente):
    """Os 6 chamadores atuais nao passam error_out — nao podem quebrar."""
    monkeypatch.setattr(db, "client", _ClienteFake(tem_metadata=False))
    assert db.approve_message(QUEUE_ID) is True


def test_queue_manager_repassa_o_motivo(monkeypatch, ambiente):
    from approval_queue.queue_manager import queue_manager
    monkeypatch.setattr(db, "client", _ClienteFake(tem_metadata=True, cas_vazio=True))
    erros = []
    assert queue_manager.approve(QUEUE_ID, error_out=erros) is False
    assert erros, "o wrapper tem que repassar error_out para a tela"
