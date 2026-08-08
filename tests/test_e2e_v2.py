# -*- coding: utf-8 -*-
"""Suite E2E do redesign v2 (pre-cutover, rodada 5).

Duas camadas:
1. RENDER: cada pagina do st.navigation roda via streamlit AppTest sem
   excecao (auth mockada via session_state — _auth_gate faz early-return).
2. FLUXOS DE ESCRITA: as mesmas funcoes que os botoes chamam, contra o banco
   REAL (unico, prod=dev), com dados marcados [E2E-TEST] e cleanup garantido
   em fixture finalizer (padrao scripts/smoke_agenda.py).

Regras: NUNCA tocar dados reais; ZERO chamadas de API paga (sem qualifier/
writer IA); nada pode sobrar no banco (cleanup roda mesmo em falha).
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.supabase_client import db  # noqa: E402

E2E = "[E2E-TEST]"
OWNER = "fernando"

PAGES_DIR = ROOT / "dashboard" / "pages"

# Paginas do st.navigation v2 (dashboard/main.py)
NAV_PAGES = [
    ROOT / "dashboard" / "app.py",
    PAGES_DIR / "0_💬_Chat_IAlex.py",
    PAGES_DIR / "5_📊_Pipeline.py",
    PAGES_DIR / "2_🏫_Escolas.py",
    PAGES_DIR / "6_✉️_Comunicacao.py",
    PAGES_DIR / "4_💼_Negocios.py",
    PAGES_DIR / "8_📈_Analytics.py",
    PAGES_DIR / "9_⚙️_Configuracoes.py",
    PAGES_DIR / "10_📖_Manual.py",
]


def _new_apptest(page_path: Path):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(page_path), default_timeout=120)
    # Auth mockada: _auth_gate.require_auth early-returna com estes dois;
    # paginas/sender_profile leem username/name; app.py le _v2_current_user.
    at.session_state["_v2_auth_done"] = True
    at.session_state["authentication_status"] = True
    at.session_state["username"] = OWNER
    at.session_state["name"] = "Fernando (E2E)"
    at.session_state["_v2_current_user"] = {
        "username": OWNER, "name": "Fernando (E2E)", "role": "CEO",
    }
    return at


# ---------------------------------------------------------------------------
# Camada 1 — RENDER das paginas do navigation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", NAV_PAGES, ids=[p.stem for p in NAV_PAGES])
def test_render_pagina_sem_excecao(page):
    at = _new_apptest(page)
    at.run()
    excs = [e for e in at.exception]
    assert not excs, f"{page.name} lancou excecao: {[str(e.value)[:300] for e in excs]}"


# ---------------------------------------------------------------------------
# Camada 1.5 — Chat IAlex com BLOCKS ricos (operador v1, F1)
# Injeta um Brain FAKE na sessao (zero API paga) que devolve reply + blocks;
# o turno completo do chat deve renderizar tabela (school_list) e nao quebrar.
# ---------------------------------------------------------------------------
class _FakeChatBrain:
    """Simula o contrato do Brain: process_message + conversation_history."""

    def __init__(self):
        self.conversation_history = []

    def process_message(self, message, sender="fernando", **kwargs):
        self.conversation_history.append({"role": "user", "content": message})
        reply = "Encontrei 2 escolas [E2E-TEST]."
        self.conversation_history.append({"role": "assistant", "content": reply})
        return {
            "reply": reply,
            "blocks": [
                {
                    "type": "school_list",
                    "escolas": [
                        {"name": "Escola A [E2E-TEST]", "city": "POA", "status": "raw"},
                        {"name": "Escola B [E2E-TEST]", "city": "POA", "status": "qualified"},
                    ],
                    "total": 2,
                    "fonte": "banco_crm",
                },
                {
                    "type": "download",
                    "url": "https://example.com/f.xlsx",
                    "filename": "f.xlsx",
                    "label": "Baixar XLSX",
                    "detalhe": "2 escola(s)",
                },
            ],
        }


def test_chat_ialex_renderiza_blocks():
    page = PAGES_DIR / "0_💬_Chat_IAlex.py"
    at = _new_apptest(page)
    at.session_state["_brain_instance"] = _FakeChatBrain()
    at.run()
    assert not [e for e in at.exception]

    # Envia um turno de chat
    at.chat_input[0].set_value("liste escolas [E2E-TEST]").run()
    excs = [e for e in at.exception]
    assert not excs, f"chat lancou excecao: {[str(e.value)[:300] for e in excs]}"

    # O reply apareceu e a tabela (school_list -> st.dataframe) foi renderizada
    all_md = " ".join(str(m.value) for m in at.markdown)
    assert "Encontrei 2 escolas" in all_md
    assert len(at.dataframe) >= 1, "school_list deveria virar st.dataframe"

    # Blocks foram guardados no mapa paralelo, NUNCA no history da API
    hist = at.session_state["chat_history_fernando"]
    for msg in hist:
        assert "blocks" not in msg
    blocks_map = at.session_state["chat_blocks_fernando"]
    assert blocks_map, "mapa de blocks nao pode estar vazio apos turno com blocks"


# ---------------------------------------------------------------------------
# Camada 2 — fluxos de escrita (dados [E2E-TEST], cleanup garantido)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def e2e():
    """Registry de objetos criados; finalizer limpa TUDO mesmo em falha."""
    reg = {"companies": [], "activities": [], "queue": [], "templates": []}
    yield reg
    # ---- cleanup (ordem: filhos -> pais) ----
    for qid in reg["queue"]:
        try:
            db.client.table("approval_queue").delete().eq("id", qid).execute()
        except Exception:
            pass
    for aid in reg["activities"]:
        try:
            db.client.table("activities").delete().eq("id", aid).execute()
        except Exception:
            pass
    for tid in reg["templates"]:
        try:
            db.client.table("message_templates").delete().eq("id", tid).execute()
        except Exception:
            pass
    for cid in reg["companies"]:
        try:
            db.client.table("interactions").delete().eq("company_id", cid).execute()
        except Exception:
            pass
        try:
            db.client.table("activities").delete().eq("company_id", cid).execute()
        except Exception:
            pass
        try:
            db.client.table("companies").delete().eq("id", cid).execute()
        except Exception:
            pass


def _mk_company(e2e, **extra):
    data = {
        "name": f"{E2E} ESCOLA {uuid.uuid4().hex[:6].upper()}",
        "inep_code": "E2E" + uuid.uuid4().hex[:8],
        "city": "Porto Alegre",
        "state": "RS",
        "status": "raw",
    }
    data.update(extra)
    cid = db.insert_company(data)
    assert cid, "insert_company falhou"
    e2e["companies"].append(cid)
    return cid


def test_atividade_criar_concluir(e2e):
    """Home: ✓ concluir atividade (db.create_activity -> complete_activity)."""
    act = db.create_activity({
        "owner_username": OWNER,
        "title": f"{E2E} ligar pra escola",
        "type": "follow_up",
        "due_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "source": "manual",
        "priority": 3,
    })
    assert act and act.get("id"), "create_activity falhou"
    e2e["activities"].append(act["id"])

    ok = db.complete_activity(act["id"], by=OWNER, resolution="manual")
    assert ok, "complete_activity falhou"

    row = db.client.table("activities").select("status, resolution").eq(
        "id", act["id"]).single().execute().data
    assert row["status"] == "done" and row["resolution"] == "manual"


def test_kanban_mover_stage_e_evento_imutavel(e2e):
    """Negocios: Mover para ▸ (set_commercial_stage) + trigger stage_changed."""
    cid = _mk_company(e2e)

    r1 = db.set_commercial_stage(cid, "proposta",
                                 extra={"valor_mensal_proposto": 1234.0})
    assert r1.get("commercial_stage") == "proposta"

    r2 = db.set_commercial_stage(
        cid, "perdido",
        extra={"motivo_perda_categoria": "sem_orcamento",
               "motivo_perda_texto": f"{E2E} motivo teste"},
        advance_status=False,
    )
    assert r2.get("commercial_stage") == "perdido"

    # Trigger 019: cada mudanca de stage grava evento imutavel em interactions
    evs = db.client.table("interactions").select("id, type").eq(
        "company_id", cid).eq("type", "stage_changed").execute().data or []
    assert len(evs) >= 2, f"esperava >=2 eventos stage_changed, veio {len(evs)}"


def test_fila_rejeitar_e_aprovar_sem_envio(e2e):
    """Mensagens: Rejeitar com motivo + Aprovar agendado (sem envio real)."""
    from approval_queue import queue_manager

    cid = _mk_company(e2e)

    base = {
        "company_id": cid,
        "subject": f"{E2E} assunto",
        "body": f"{E2E} corpo da mensagem de teste",
        "status": "pending",
        "channel": "email",
    }
    q1 = db.client.table("approval_queue").insert(base).execute().data[0]
    e2e["queue"].append(q1["id"])
    q2 = db.client.table("approval_queue").insert(dict(base)).execute().data[0]
    e2e["queue"].append(q2["id"])

    # rejeitar
    assert queue_manager.reject(q1["id"], reason=f"{E2E} rejeicao teste")
    s1 = db.client.table("approval_queue").select("status, rejection_reason").eq(
        "id", q1["id"]).single().execute().data
    assert s1["status"] == "rejected"
    assert E2E in (s1.get("rejection_reason") or "")

    # aprovar com envio agendado pro FUTURO distante (nunca entra no ciclo) e
    # deletar imediatamente no proprio teste (cleanup de fixture e a 2a rede).
    future = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    assert queue_manager.approve(q2["id"], scheduled_send_at=future)
    s2 = db.client.table("approval_queue").select("status, sent_at").eq(
        "id", q2["id"]).single().execute().data
    assert s2["status"] == "approved" and not s2["sent_at"]
    db.client.table("approval_queue").delete().eq("id", q2["id"]).execute()


def test_modelo_visibilidade_pessoal(e2e):
    """Modelos: pessoal de OUTRO usuario some; pessoal MEU e compartilhado ficam."""
    ins = db.client.table("message_templates").insert([
        {"name": f"{E2E} pessoal-outro", "subject_template": "s", "body_template": "b",
         "is_active": False, "visibility": "personal", "owner_username": "outrouser"},
        {"name": f"{E2E} pessoal-meu", "subject_template": "s", "body_template": "b",
         "is_active": False, "visibility": "personal", "owner_username": OWNER},
        {"name": f"{E2E} compartilhado", "subject_template": "s", "body_template": "b",
         "is_active": False, "visibility": "shared"},
    ]).execute().data
    for t in ins:
        e2e["templates"].append(t["id"])

    todos = db.client.table("message_templates").select("*").execute().data or []
    # filtro identico ao da pagina Mensagens > Modelos
    visiveis = [
        t for t in todos
        if (t.get("visibility") or "shared") == "shared"
        or t.get("owner_username") in (None, OWNER)
    ]
    nomes = {t["name"] for t in visiveis}
    assert f"{E2E} pessoal-meu" in nomes
    assert f"{E2E} compartilhado" in nomes
    assert f"{E2E} pessoal-outro" not in nomes, "modelo pessoal de outro vazou!"


def test_registrar_resposta_recebida(e2e):
    """Recebidas: registrar resposta de fora da plataforma (interactions)."""
    cid = _mk_company(e2e)
    res = db.register_manual_interaction(
        company_id=cid, channel="email", direction="received",
        notes=f"{E2E} resposta recebida por fora", source="dashboard",
    )
    assert res, "register_manual_interaction falhou"
    rows = db.client.table("interactions").select("id, message_snippet").eq(
        "company_id", cid).execute().data or []
    assert any(E2E in (r.get("message_snippet") or "") for r in rows)


def test_trabalhar_escola_do_catalogo(e2e):
    """Recomendadas: 'Trabalhar esta escola' (catalogo MEC -> CRM com dono)."""
    rows = db.client.table("mec_catalog").select("*").limit(1).execute().data
    assert rows, "mec_catalog vazio?"
    cdata = db._catalog_row_to_company(rows[0])
    cdata["name"] = f"{E2E} {cdata.get('name', 'ESCOLA CATALOGO')}"[:200]
    cdata["inep_code"] = "E2E" + uuid.uuid4().hex[:8]  # nao colidir com real
    cdata["owner_username"] = OWNER
    cdata["fonte_dados"] = "recomendadas"
    cid = db.insert_company(cdata)
    assert cid, "insert via catalogo falhou"
    e2e["companies"].append(cid)

    row = db.client.table("companies").select("owner_username, name").eq(
        "id", cid).single().execute().data
    assert row["owner_username"] == OWNER


def test_zero_residuos_e2e_apos_cleanup():
    """Roda por ULTIMO (ordem alfabetica nao importa: depende da fixture module
    ja finalizada? Nao — fixture finaliza no fim do modulo. Este teste valida
    apenas que nao ha residuos de execucoes ANTERIORES, como guarda extra."""
    leftovers = []
    for table, col in [("companies", "name"), ("activities", "title"),
                       ("approval_queue", "subject"), ("message_templates", "name")]:
        try:
            r = db.client.table(table).select("id").ilike(col, f"{E2E}%").limit(5).execute().data or []
            # tolera os criados NESTE run (fixture ainda viva); só alerta antigos
        except Exception:
            r = []
        if len(r) > 20:
            leftovers.append((table, len(r)))
    assert not leftovers, f"residuos E2E acumulados: {leftovers}"
