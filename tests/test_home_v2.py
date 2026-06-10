"""Testes de dashboard/helpers/home_v2.py (F2) — logica da Home com db mockado."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dashboard.helpers import home_v2 as hv


def make_query(data=None, count=0):
    q = MagicMock()
    q.execute.return_value = SimpleNamespace(data=data or [], count=count)
    for m in ["select", "eq", "in_", "gte", "lte", "lt", "gt", "order",
              "limit", "is_", "update", "insert", "ilike", "neq"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    return q


NOW = datetime(2026, 6, 10, 15, 0, tzinfo=timezone.utc)  # quarta 12h BRT


def act(title, due, type_="tarefa", prio=2, created=None):
    return {"id": title, "title": title, "type": type_, "priority": prio,
            "due_at": due, "status": "open",
            "created_at": created or "2026-06-10T10:00:00+00:00"}


class TestAgendaGroups:
    @patch.object(hv, "db")
    def test_agrupamento(self, mock_db):
        mock_db.list_activities.return_value = [
            act("atrasada", "2026-06-09T12:00:00+00:00"),
            act("hoje-futura", "2026-06-10T20:00:00+00:00"),   # 17h BRT
            act("amanha", "2026-06-11T13:00:00+00:00"),
            act("semana-que-vem", "2026-06-15T13:00:00+00:00"),
        ]
        g = hv.agenda_groups("fernando", NOW)
        assert [a["title"] for a in g["atrasadas"]] == ["atrasada"]
        assert [a["title"] for a in g["hoje"]] == ["hoje-futura"]
        assert [a["title"] for a in g["amanha"]] == ["amanha"]
        assert [a["title"] for a in g["proximas"]] == ["semana-que-vem"]

    @patch.object(hv, "db")
    def test_hoje_vencida_vai_para_atrasadas(self, mock_db):
        mock_db.list_activities.return_value = [
            act("hoje-vencida", "2026-06-10T12:00:00+00:00")]  # 9h BRT < now
        g = hv.agenda_groups("fernando", NOW)
        assert len(g["atrasadas"]) == 1 and not g["hoje"]


class TestDayNumbers:
    @patch.object(hv, "db")
    def test_numeros_e_sla(self, mock_db):
        mock_db.list_activities.return_value = [
            act("responder X", "2026-06-09T12:00:00+00:00", type_="responder",
                prio=1, created="2026-06-09T10:00:00+00:00"),  # 29h esperando
            act("tarefa", "2026-06-10T20:00:00+00:00"),
        ]
        mock_db.client.table.return_value = make_query(count=12)
        n = hv.day_numbers("fernando", NOW)
        assert n["atividades_hoje"] == 2
        assert n["atrasadas"] == 1 and n["prio1"] == 1
        assert n["respostas_novas"] == 1
        assert n["resposta_mais_antiga_h"] == 29.0
        assert n["aprovacoes_pendentes"] == 12
        assert n["sobrecarga"] is False

    @patch.object(hv, "db")
    def test_sobrecarga_acima_de_12(self, mock_db):
        mock_db.list_activities.return_value = [
            act(f"t{i}", "2026-06-10T20:00:00+00:00") for i in range(13)]
        mock_db.client.table.return_value = make_query(count=0)
        assert hv.day_numbers("fernando", NOW)["sobrecarga"] is True


class TestEmConversa:
    @patch.object(hv, "db")
    def test_conta_stages_certos(self, mock_db):
        mock_db.client.table.return_value = make_query(data=[
            {"status": "contacted", "commercial_stage": None},        # conta
            {"status": "responded", "commercial_stage": "respondeu"}, # conta
            {"status": "contacted", "commercial_stage": "cliente"},   # NAO (fechado)
            {"status": "raw", "commercial_stage": None},              # NAO
            {"status": "contacted", "commercial_stage": "proposta"},  # conta
        ])
        assert hv.em_conversa("fernando") == 3


class TestTeamPanel:
    @patch.object(hv, "agenda_groups")
    @patch.object(hv, "db")
    def test_painel_do_gestor(self, mock_db, mock_groups):
        mock_groups.side_effect = lambda u, now: {
            "atrasadas": [act("r", "x", type_="responder")] if u == "felipe" else [],
            "hoje": [act("t", "x")], "amanha": [], "proximas": []}
        mock_db.client.table.return_value = make_query(data=[])
        panel = hv.team_panel(["fernando", "felipe"], NOW)
        assert panel["por_vendedor"]["felipe"]["atrasadas"] == 1
        assert panel["por_vendedor"]["felipe"]["respostas_atrasadas"] == 1
        assert panel["por_vendedor"]["fernando"]["atrasadas"] == 0


class TestBuscaGlobal:
    @patch.object(hv, "db")
    def test_query_curta_nao_busca(self, mock_db):
        out = hv.busca_global("a")
        assert out == {"escolas": [], "contatos": []}
        mock_db.client.table.assert_not_called()

    @patch.object(hv, "db")
    def test_busca_escolas_e_contatos(self, mock_db):
        mock_db.client.table.return_value = make_query(
            data=[{"id": "1", "name": "Colegio Alfa"}])
        out = hv.busca_global("alfa")
        assert out["escolas"] and out["contatos"]  # mesmo mock pros 2
