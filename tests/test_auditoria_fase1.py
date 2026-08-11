# -*- coding: utf-8 -*-
"""Regressao dos achados CRITICOS da auditoria completa (Ago/2026).

Cada teste aqui existe porque um bug REAL passou pela suite anterior:
- import errado so estourava no CLIQUE (import lazy) -> AppTest nao pegava;
- chave de cor inexistente so estourava com dado especifico no banco;
- divergencia de ordenacao so aparecia com >1 item na fila.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent.brain as brain_mod  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Acoes inline do chat: o queue manager tem que INSTANCIAR de verdade
# ---------------------------------------------------------------------------
def test_chat_queue_manager_instancia():
    """Bug: importava ApprovalQueueManager (inexistente) -> toda acao do chat
    falhava com ImportError engolido pelo except do render_block."""
    from dashboard.helpers.chat_blocks_view import _get_queue_manager
    qm = _get_queue_manager()
    assert qm is not None
    for metodo in ("approve", "reject"):
        assert callable(getattr(qm, metodo, None)), f"queue manager sem {metodo}()"


# ---------------------------------------------------------------------------
# 2. Cores usadas no dashboard precisam existir no tema
# ---------------------------------------------------------------------------
def test_cores_usadas_existem_no_tema():
    """Bug: COLORS['danger'] nao existe -> KeyError derrubava a ficha da escola
    de qualquer escola com nota Google < 3.5."""
    import re
    from dashboard.theme import COLORS

    alvos = [
        ROOT / "dashboard" / "pages" / "2_🏫_Escolas.py",
        ROOT / "dashboard" / "app.py",
        ROOT / "dashboard" / "helpers" / "chat_blocks_view.py",
        ROOT / "dashboard" / "helpers" / "urgency_widgets.py",
    ]
    faltando = []
    for p in alvos:
        if not p.exists():
            continue
        for chave in re.findall(r'COLORS\[\s*["\'](\w+)["\']\s*\]',
                                p.read_text(encoding="utf-8")):
            if chave not in COLORS:
                faltando.append(f"{p.name}: COLORS[{chave!r}]")
    assert not faltando, f"chaves de cor inexistentes: {faltando}"


# ---------------------------------------------------------------------------
# 3. Posicao na fila tem que casar com o que fila_aprovacao EXIBE
# ---------------------------------------------------------------------------
def test_resolve_queue_id_usa_mesma_ordem_da_fila(monkeypatch):
    """Bug: resolver ordenava ASC + so 'pending'; a fila exibe DESC sem filtro
    -> "aprova o 2" atingia OUTRO email, que era enviado de verdade."""
    capturado = {}

    class _Q:
        def select(self, *a, **k):
            return self

        def eq(self, col, val):
            capturado["eq"] = (col, val)
            return self

        def order(self, col, desc=False):
            capturado["order"] = (col, desc)
            return self

        def limit(self, n):
            capturado["limit"] = n
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": f"id{i}"} for i in range(1, 6)]})()

    monkeypatch.setattr(brain_mod.db, "client",
                        type("C", (), {"table": lambda self, t: _Q()})())

    qid = brain_mod._resolve_queue_id({"posicao": 2})
    assert capturado["order"] == ("created_at", True), "tem que ser DESC como a fila"
    assert "eq" not in capturado, "sem filtro de status quando o usuario nao pediu"
    assert qid == "id2"


def test_resolve_queue_id_respeita_status_pedido(monkeypatch):
    capturado = {}

    class _Q:
        def select(self, *a, **k):
            return self

        def eq(self, col, val):
            capturado["eq"] = (col, val)
            return self

        def order(self, col, desc=False):
            return self

        def limit(self, n):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "a"}, {"id": "b"}]})()

    monkeypatch.setattr(brain_mod.db, "client",
                        type("C", (), {"table": lambda self, t: _Q()})())
    brain_mod._resolve_queue_id({"posicao": 2, "status": "pending"})
    assert capturado["eq"] == ("status", "pending")


def test_resolve_queue_id_posicao_invalida():
    assert brain_mod._resolve_queue_id({}) is None
    assert brain_mod._resolve_queue_id({"posicao": 0}) is None
    assert brain_mod._resolve_queue_id({"posicao": "abc"}) is None
    assert brain_mod._resolve_queue_id({"posicao": None}) is None
    assert brain_mod._resolve_queue_id({"queue_id": "xyz"}) == "xyz"


# ---------------------------------------------------------------------------
# 4. Agendamento: horario sem fuso e BRT, nao UTC
# ---------------------------------------------------------------------------
def test_iso_sem_fuso_vira_brasilia():
    """Bug: '2026-08-12T16:00' ia cru pro timestamptz -> lido como UTC ->
    envio 3h ADIANTADO (13h de Brasilia)."""
    out = brain_mod._parse_agendar_para("2026-08-12T16:00")
    assert out is not None
    dt = datetime.fromisoformat(out)
    assert dt.utcoffset() is not None, "precisa carregar fuso"
    assert dt.utcoffset().total_seconds() == -3 * 3600
    assert dt.hour == 16  # a hora que o usuario pediu se mantem


def test_iso_com_fuso_preservado():
    assert brain_mod._parse_agendar_para("2026-08-12T16:00-03:00") == "2026-08-12T16:00-03:00"


def test_formato_nao_entendido_vira_none():
    """Bug: retornava a string crua ('amanha 9h') -> estourava no Postgres."""
    assert brain_mod._parse_agendar_para("amanha 9h") is None
    assert brain_mod._parse_agendar_para("segunda que vem") is None
    assert brain_mod._parse_agendar_para("") is None
    assert brain_mod._parse_agendar_para(None) is None


def test_aprovar_com_agendamento_invalido_nao_aprova(monkeypatch):
    """Sem isso, a mensagem seria aprovada SEM agendamento e sairia no proximo
    lote (minutos) em vez da data pedida."""
    chamou = []
    monkeypatch.setattr(brain_mod.db, "client", type("C", (), {
        "table": lambda self, t: chamou.append(t) or (_ for _ in ()).throw(
            AssertionError("nao deveria tocar no banco"))
    })())
    out = json.loads(brain_mod._handle_aprovar_mensagem({
        "queue_id": "abc", "agendar_para": "amanha de tarde",
    }))
    assert "erro" in out
    assert "NADA foi aprovado" in out["erro"]


# ---------------------------------------------------------------------------
# 5. Geocoder: endereco achado pela busca web precisa ser salvo
# ---------------------------------------------------------------------------
def test_geocoder_aceita_method_novo_e_antigo():
    src = (ROOT / "tools" / "geocoder.py").read_text(encoding="utf-8")
    assert 'web_search_fallback' in src
    # o consumidor tem que aceitar os DOIS nomes
    idx = src.find('result.get("method") in')
    assert idx != -1, "consumidor ainda compara com == (perde o endereco novo)"
    trecho = src[idx:idx + 200]
    assert "web_search_fallback" in trecho and "perplexity_fallback" in trecho


# ---------------------------------------------------------------------------
# 6. Urgencia: coluna ENEM correta (15% do score dependia disso)
# ---------------------------------------------------------------------------
def test_urgency_usa_coluna_enem_correta():
    """Bug: lia 'amostra_confiavel' (inexistente) -> 400 engolido -> score ENEM
    constante -> nenhuma escola chegava a HOT/CRITICAL."""
    import re
    src = (ROOT / "tools" / "urgency_scorer.py").read_text(encoding="utf-8")
    assert "enem_amostra_confiavel" in src
    # Ignora COMENTARIOS (o fix documenta o nome antigo de proposito) e checa
    # so o codigo executavel.
    codigo = "\n".join(
        re.sub(r"#.*$", "", linha) for linha in src.splitlines()
    )
    assert not re.search(r'(?<!enem_)\bamostra_confiavel\b', codigo), \
        "codigo ainda referencia a coluna inexistente 'amostra_confiavel'"
