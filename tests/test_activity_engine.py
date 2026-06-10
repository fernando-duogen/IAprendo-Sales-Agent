"""Testes do workflows/activity_engine.py (F1) — SPEC_AGENDA_METAS.

Helpers de tempo sao testados puros; fluxos (varredor, anti-colisao, expiracao,
rollover) com db mockado — nunca tocam o banco real.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from workflows import activity_engine as eng


# ---------------------------------------------------------------------------
# Helpers de mock
# ---------------------------------------------------------------------------
def make_query(data=None, count=0):
    """MagicMock encadeavel: qualquer filtro retorna o proprio mock; execute()
    retorna um objeto com .data/.count."""
    q = MagicMock()
    result = SimpleNamespace(data=data or [], count=count)
    q.execute.return_value = result
    for m in ["select", "eq", "in_", "gte", "lte", "lt", "gt", "order",
              "limit", "is_", "update", "insert", "ilike"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    return q


def utc(y, mo, d, h=12, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def brt_naive_as_utc(y, mo, d, h, mi=0):
    """Constroi um instante cujo horario BRT e o dado (BRT = UTC-3)."""
    return datetime(y, mo, d, h, mi, tzinfo=eng.BRT).astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Tempo util (BRT)
# ---------------------------------------------------------------------------
class TestBusinessTime:
    def test_sexta_apos_18h_rola_para_segunda_9h(self):
        # 2026-06-12 e sexta
        dt = brt_naive_as_utc(2026, 6, 12, 19, 0)
        nxt = eng.to_brt(eng.next_business_time(dt))
        assert nxt.weekday() == 0 and nxt.hour == 9  # segunda 9h

    def test_sabado_rola_para_segunda(self):
        dt = brt_naive_as_utc(2026, 6, 13, 10, 0)  # sabado
        nxt = eng.to_brt(eng.next_business_time(dt))
        assert nxt.weekday() == 0 and nxt.hour == 9

    def test_horario_comercial_nao_muda(self):
        dt = brt_naive_as_utc(2026, 6, 10, 14, 30)  # quarta 14h30
        nxt = eng.to_brt(eng.next_business_time(dt))
        assert (nxt.weekday(), nxt.hour, nxt.minute) == (2, 14, 30)

    def test_sla_4h_uteis_atravessa_o_dia(self):
        # criada quarta 16h BRT: 2h hoje + 2h amanha a partir das 9h -> 11h
        dt = brt_naive_as_utc(2026, 6, 10, 16, 0)
        due = eng.to_brt(eng.add_business_hours(dt, 4))
        assert (due.weekday(), due.hour) == (3, 11)  # quinta 11h

    def test_sla_4h_dentro_do_dia(self):
        dt = brt_naive_as_utc(2026, 6, 10, 9, 0)
        due = eng.to_brt(eng.add_business_hours(dt, 4))
        assert (due.weekday(), due.hour) == (2, 13)

    def test_business_day_at_rola_fim_de_semana(self):
        dt = brt_naive_as_utc(2026, 6, 13, 8, 0)  # sabado
        due = eng.to_brt(eng.business_day_at(dt, 14))
        assert due.weekday() == 0 and due.hour == 14


# ---------------------------------------------------------------------------
# Varredor (auto-resolucao) — SPEC §1.4
# ---------------------------------------------------------------------------
class TestSweep:
    def _act(self, **kw):
        base = {"id": "a1", "type": "responder", "company_id": "c1",
                "source": "auto", "status": "open",
                "created_at": "2026-06-09T12:00:00+00:00",
                "owner_username": "fernando", "auto_rule": "reply_received"}
        base.update(kw)
        return base

    @patch.object(eng, "db")
    def test_responder_resolve_quando_ha_outbound_posterior(self, mock_db):
        mock_db.client.table.return_value = make_query(
            data=[{"created_at": "2026-06-10T10:00:00+00:00"}])
        mock_db.complete_activity.return_value = True
        assert eng._sweep_one(self._act(), utc(2026, 6, 10)) is True
        mock_db.complete_activity.assert_called_once_with(
            "a1", "system", "auto_trabalho_detectado")

    @patch.object(eng, "db")
    def test_responder_nao_resolve_sem_outbound(self, mock_db):
        mock_db.client.table.return_value = make_query(data=[])
        assert eng._sweep_one(self._act(), utc(2026, 6, 10)) is False
        mock_db.complete_activity.assert_not_called()

    @patch.object(eng, "db")
    def test_followup_morre_quando_etapa_avancou(self, mock_db):
        def table(name):
            if name == "interactions":
                return make_query(data=[])  # sem outbound, sem reply
            if name == "companies":
                return make_query(data=[{"id": "c1", "commercial_stage": "reuniao"}])
            return make_query()
        mock_db.client.table.side_effect = table
        mock_db.dismiss_activity.return_value = True
        act = self._act(type="follow_up", auto_rule="sequencia_toques")
        assert eng._sweep_one(act, utc(2026, 6, 10)) is True
        mock_db.dismiss_activity.assert_called_once_with(
            "a1", "system", "auto_gatilho_morto")

    @patch.object(eng, "db")
    def test_registrar_resultado_resolve_com_outcome(self, mock_db):
        mock_db.client.table.return_value = make_query(
            data=[{"id": "m1", "outcome": "interested", "status": "completed"}])
        mock_db.complete_activity.return_value = True
        act = self._act(type="registrar_resultado", meeting_id="m1",
                        auto_rule="meeting_outcome")
        assert eng._sweep_one(act, utc(2026, 6, 10)) is True

    @patch.object(eng, "db")
    def test_prep_dismissa_reuniao_cancelada(self, mock_db):
        mock_db.client.table.return_value = make_query(
            data=[{"id": "m1", "status": "cancelled", "scheduled_at": None}])
        mock_db.dismiss_activity.return_value = True
        act = self._act(type="preparar_reuniao", meeting_id="m1",
                        auto_rule="meeting_prep", dedupe_key="prep:m1:2026-06-11")
        assert eng._sweep_one(act, utc(2026, 6, 10)) is True

    @patch.object(eng, "db")
    def test_prep_dismissa_reuniao_remarcada(self, mock_db):
        # chave diz 2026-06-11; reuniao agora e 2026-06-20 -> gatilho morto
        mock_db.client.table.return_value = make_query(
            data=[{"id": "m1", "status": "scheduled",
                   "scheduled_at": "2026-06-20T12:00:00+00:00"}])
        mock_db.dismiss_activity.return_value = True
        act = self._act(type="preparar_reuniao", meeting_id="m1",
                        auto_rule="meeting_prep", dedupe_key="prep:m1:2026-06-11")
        assert eng._sweep_one(act, utc(2026, 6, 10)) is True

    @patch.object(eng, "db")
    def test_manual_nunca_auto_resolve(self, mock_db):
        act = self._act(type="tarefa", source="manual", auto_rule=None)
        assert eng._sweep_one(act, utc(2026, 6, 10)) is False
        mock_db.complete_activity.assert_not_called()
        mock_db.dismiss_activity.assert_not_called()

    @patch.object(eng, "db")
    def test_aprovar_mensagens_resolve_com_fila_zerada(self, mock_db):
        mock_db.client.table.return_value = make_query(data=[], count=0)
        mock_db.complete_activity.return_value = True
        act = self._act(type="aprovar_mensagens", company_id=None,
                        auto_rule="approvals_aging")
        assert eng._sweep_one(act, utc(2026, 6, 10)) is True


# ---------------------------------------------------------------------------
# Anti-colisao e tetos — SPEC §1.7
# ---------------------------------------------------------------------------
class TestAntiColisao:
    @patch.object(eng, "_is_away", return_value=False)
    @patch.object(eng, "db")
    def test_nao_nasce_followup_se_ha_responder_aberto(self, mock_db, _away):
        mock_db.count_open_activities.return_value = 3
        mock_db.client.table.return_value = make_query(
            data=[{"id": "x", "type": "responder", "auto_rule": "reply_received"}])
        assert eng._can_create("fernando", 2, "c1", "follow_up") is False

    @patch.object(eng, "_is_away", return_value=False)
    @patch.object(eng, "db")
    def test_responder_nasce_mesmo_com_followup_aberto(self, mock_db, _away):
        mock_db.count_open_activities.return_value = 3
        mock_db.client.table.return_value = make_query(
            data=[{"id": "x", "type": "follow_up", "auto_rule": "sequencia_toques"}])
        assert eng._can_create("fernando", 1, "c1", "responder") is True

    @patch.object(eng, "_is_away", return_value=False)
    @patch.object(eng, "db")
    def test_teto_soft_bloqueia_prio2_mas_nao_prio1(self, mock_db, _away):
        mock_db.count_open_activities.return_value = 25
        mock_db.client.table.return_value = make_query(data=[])
        assert eng._can_create("fernando", 2, None, "tarefa") is False
        assert eng._can_create("fernando", 1, None, "responder") is True

    @patch.object(eng, "db")
    def test_trava_absoluta_bloqueia_tudo(self, mock_db):
        mock_db.count_open_activities.return_value = 40
        assert eng._can_create("fernando", 1, None, "responder") is False

    @patch.object(eng, "_is_away", return_value=True)
    @patch.object(eng, "db")
    def test_ausente_nao_recebe_prio2_mas_recebe_prio1(self, mock_db, _away):
        mock_db.count_open_activities.return_value = 0
        mock_db.client.table.return_value = make_query(data=[])
        assert eng._can_create("felipe", 2, None, "tarefa") is False
        assert eng._can_create("felipe", 1, "c1", "responder") is True


# ---------------------------------------------------------------------------
# Expiracao — SPEC §1.6
# ---------------------------------------------------------------------------
class TestExpiracao:
    @patch.object(eng, "db")
    def test_followup_expira_apos_7d_e_responder_nunca(self, mock_db):
        now = utc(2026, 6, 20)
        autos = [
            {"id": "f1", "auto_rule": "sequencia_toques", "type": "follow_up",
             "due_at": "2026-06-10T12:00:00+00:00", "owner_username": "f"},
            {"id": "r1", "auto_rule": "reply_received", "type": "responder",
             "due_at": "2026-06-01T12:00:00+00:00", "owner_username": "f"},
        ]
        mock_db.client.table.return_value = make_query(data=autos)
        mock_db.dismiss_activity.return_value = True
        n = eng.expire_overdue(now)
        assert n == 1
        mock_db.dismiss_activity.assert_called_once_with("f1", "system", "expirada")

    @patch.object(eng, "db")
    def test_aprovar_mensagens_expira_no_dia_seguinte(self, mock_db):
        now = brt_naive_as_utc(2026, 6, 11, 10, 0)
        autos = [{"id": "a1", "auto_rule": "approvals_aging",
                  "type": "aprovar_mensagens",
                  "due_at": brt_naive_as_utc(2026, 6, 10, 9, 0).isoformat(),
                  "owner_username": "f"}]
        mock_db.client.table.return_value = make_query(data=autos)
        mock_db.dismiss_activity.return_value = True
        assert eng.expire_overdue(now) == 1


# ---------------------------------------------------------------------------
# Regras de criacao (amostra) + dedupe
# ---------------------------------------------------------------------------
class TestRegras:
    @patch.object(eng, "_can_create", return_value=True)
    @patch.object(eng, "db")
    def test_reply_received_cria_para_o_dono(self, mock_db, _can):
        def table(name):
            if name == "interactions":
                q = make_query(data=[{"id": "i9", "company_id": "c1",
                                      "created_at": "2026-06-10T11:00:00+00:00"}])
                return q
            if name == "companies":
                return make_query(data=[{"id": "c1", "name": "Colegio X",
                                         "owner_username": "lizianne"}])
            return make_query()
        mock_db.client.table.side_effect = table
        mock_db.create_activity.return_value = {"id": "novo"}
        # _last_outbound_at usa interactions com gt(after) — devolve a mesma
        # lista nao-vazia, o que marcaria "ja tratada". Neutralizamos:
        with patch.object(eng, "_last_outbound_at", return_value=None):
            n = eng._rule_reply_received(utc(2026, 6, 10, 12))
        assert n == 1
        payload = mock_db.create_activity.call_args[0][0]
        assert payload["owner_username"] == "lizianne"
        assert payload["priority"] == 1
        assert payload["dedupe_key"] == "responder:c1:i9"

    @patch.object(eng, "_can_create", return_value=True)
    @patch.object(eng, "db")
    def test_reply_sem_dono_vai_para_admin(self, mock_db, _can):
        def table(name):
            if name == "interactions":
                return make_query(data=[{"id": "i9", "company_id": "c1",
                                         "created_at": "2026-06-10T11:00:00+00:00"}])
            if name == "companies":
                return make_query(data=[{"id": "c1", "name": "Colegio X",
                                         "owner_username": None}])
            return make_query()
        mock_db.client.table.side_effect = table
        mock_db.create_activity.return_value = {"id": "novo"}
        with patch.object(eng, "_last_outbound_at", return_value=None), \
             patch.object(eng, "admin_username", return_value="fernando"):
            eng._rule_reply_received(utc(2026, 6, 10, 12))
        payload = mock_db.create_activity.call_args[0][0]
        assert payload["owner_username"] == "fernando"
        assert payload["title"].startswith("(lead sem dono)")

    @patch.object(eng, "_can_create", return_value=True)
    @patch.object(eng, "db")
    def test_sequencia_toque2_canal_alternado(self, mock_db, _can):
        last_out = utc(2026, 6, 6, 12)  # 4 dias atras
        def table(name):
            if name == "companies":
                return make_query(data=[{"id": "c1", "name": "Colegio X",
                                         "owner_username": "fernando",
                                         "commercial_stage": "contatado",
                                         "status": "contacted",
                                         "last_contacted_at": last_out.isoformat()}])
            return make_query()
        mock_db.client.table.side_effect = table
        mock_db.create_activity.return_value = {"id": "novo"}
        with patch.object(eng, "_last_outbound_at", return_value=last_out), \
             patch.object(eng, "_has_reply_after", return_value=False), \
             patch.object(eng, "_has_pending_message", return_value=False), \
             patch.object(eng, "_last_outbound_channel", return_value="email"):
            n = eng._rule_sequencia_toques(utc(2026, 6, 10, 12))
        assert n == 1
        payload = mock_db.create_activity.call_args[0][0]
        assert payload["sequence_step"] == 2
        assert "WhatsApp" in payload["title"]
        assert payload["dedupe_key"] == "seq:c1:2"

    @patch.object(eng, "_can_create", return_value=True)
    @patch.object(eng, "db")
    def test_sequencia_breakup_apos_10d(self, mock_db, _can):
        last_out = utc(2026, 5, 29, 12)
        def table(name):
            if name == "companies":
                return make_query(data=[{"id": "c1", "name": "Colegio X",
                                         "owner_username": "fernando",
                                         "commercial_stage": None,
                                         "status": "contacted",
                                         "last_contacted_at": last_out.isoformat()}])
            return make_query()
        mock_db.client.table.side_effect = table
        mock_db.create_activity.return_value = {"id": "novo"}
        with patch.object(eng, "_last_outbound_at", return_value=last_out), \
             patch.object(eng, "_has_reply_after", return_value=False), \
             patch.object(eng, "_has_pending_message", return_value=False), \
             patch.object(eng, "_last_outbound_channel", return_value="email"):
            eng._rule_sequencia_toques(utc(2026, 6, 10, 12))
        payload = mock_db.create_activity.call_args[0][0]
        assert payload["type"] == "tarefa"
        assert payload["title"].startswith("Decidir: arquivar")

    @patch.object(eng, "db")
    def test_dedupe_create_activity_none_nao_conta(self, mock_db):
        mock_db.count_open_activities.return_value = 0
        mock_db.client.table.return_value = make_query(data=[])
        mock_db.create_activity.return_value = None  # dedupe hit
        with patch.object(eng, "_is_away", return_value=False):
            ok = eng._create("fernando", "tarefa", "t", utc(2026, 6, 10), 2,
                             "goal_reminder", "k1")
        assert ok is False


# ---------------------------------------------------------------------------
# Metas: rollover e lembrete — SPEC §4.1
# ---------------------------------------------------------------------------
class TestMetas:
    @patch.object(eng, "db")
    def test_rollover_so_no_dia_1(self, mock_db):
        assert eng.rollover_goals(brt_naive_as_utc(2026, 6, 15, 10)) == 0
        mock_db.list_goals.assert_not_called()

    @patch.object(eng, "db")
    def test_rollover_herda_apenas_o_que_falta(self, mock_db):
        prev = [{"username": "fernando", "metric": "emails_enviados", "target": 40},
                {"username": "lizianne", "metric": "emails_enviados", "target": 40}]
        cur = [{"username": "fernando", "metric": "emails_enviados", "target": 50}]
        mock_db.list_goals.side_effect = [prev, cur]
        mock_db.upsert_goal.return_value = {"id": "g"}
        n = eng.rollover_goals(brt_naive_as_utc(2026, 7, 1, 1))
        assert n == 1
        args = mock_db.upsert_goal.call_args
        assert args[0][0] == "lizianne"
        assert args[1]["reason"] == "herdada"

    @patch.object(eng, "_create", return_value=True)
    @patch.object(eng, "db")
    def test_goal_reminder_dia_25(self, mock_db, mock_create):
        mock_db.list_goals.return_value = []
        assert eng._rule_goal_reminder(brt_naive_as_utc(2026, 6, 25, 10)) == 1
        assert eng._rule_goal_reminder(brt_naive_as_utc(2026, 6, 20, 10)) == 0


# ---------------------------------------------------------------------------
# run_engine integra as fases na ordem
# ---------------------------------------------------------------------------
class TestRunEngine:
    @patch.object(eng, "rollover_goals", return_value=0)
    @patch.object(eng, "create_from_rules", return_value=2)
    @patch.object(eng, "expire_overdue", return_value=1)
    @patch.object(eng, "reopen_snoozed", return_value=1)
    @patch.object(eng, "sweep_auto_resolution", return_value=3)
    def test_resumo(self, *_mocks):
        s = eng.run_engine(utc(2026, 6, 10))
        assert s == {"swept": 3, "reopened": 1, "expired": 1,
                     "created": 2, "goals_rolled": 0}
