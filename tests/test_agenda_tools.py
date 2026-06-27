"""Testes de agent/tools/agenda_tools.py (F1) — handlers com db mockado."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import agenda_tools as at


def make_query(data=None, count=0):
    q = MagicMock()
    q.execute.return_value = SimpleNamespace(data=data or [], count=count)
    for m in ["select", "eq", "in_", "gte", "lte", "lt", "gt", "order",
              "limit", "is_", "update", "insert", "ilike", "neq"]:
        getattr(q, m).return_value = q
    q.not_.is_.return_value = q
    return q


def parse(result: str) -> dict:
    return json.loads(result)


class TestRegistroBrainCompleto:
    def test_brain_carrega_as_14_tools(self):
        assert len(at.AGENDA_TOOLS) == 14
        assert set(at.AGENDA_TOOL_HANDLERS) == {t["name"] for t in at.AGENDA_TOOLS}

    def test_schemas_validos(self):
        for t in at.AGENDA_TOOLS:
            assert t["name"] and t["description"]
            assert t["input_schema"]["type"] == "object"


class TestPermissoes:
    @patch.object(at, "is_admin", return_value=False)
    @patch.object(at, "get_active_sender_username", return_value="lizianne")
    def test_definir_meta_negada_para_nao_admin(self, *_):
        out = parse(at._handle_definir_meta(
            {"usuario": "felipe", "metrica": "clientes", "alvo": 2}))
        assert "erro" in out and "admin" in out["erro"]

    @patch.object(at, "is_admin", return_value=False)
    @patch.object(at, "get_active_sender_username", return_value="lizianne")
    def test_metas_time_negada_para_nao_admin(self, *_):
        out = parse(at._handle_metas_time({}))
        assert "erro" in out

    @patch.object(at, "is_admin", return_value=False)
    @patch.object(at, "get_active_sender_username", return_value="lizianne")
    def test_reatribuir_lote_negada_para_nao_admin(self, *_):
        out = parse(at._handle_reatribuir_leads_lote(
            {"de_usuario": "felipe", "para_usuario": "lizianne"}))
        assert "erro" in out

    @patch.object(at, "is_admin", return_value=True)
    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "db")
    def test_reatribuir_sem_confirmar_so_preve(self, mock_db, *_):
        mock_db.client.table.return_value = make_query(count=12)
        out = parse(at._handle_reatribuir_leads_lote(
            {"de_usuario": "felipe", "para_usuario": "lizianne"}))
        assert out.get("confirmacao_necessaria") is True
        mock_db.reassign_company_activities.assert_not_called()


class TestAgenda:
    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "db")
    def test_criar_atividade_basica(self, mock_db, _me):
        mock_db.create_activity.return_value = {
            "id": "a1", "due_at": "2026-06-12T12:00:00+00:00"}
        out = parse(at._handle_criar_atividade(
            {"titulo": "Ligar pro Colegio Alfa", "quando": "2026-06-12"}))
        assert out["ok"] is True
        payload = mock_db.create_activity.call_args[0][0]
        assert payload["source"] == "ialex"
        assert payload["type"] == "ligar"  # inferido do titulo
        assert payload["owner_username"] == "fernando"

    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "is_admin", return_value=False)
    def test_criar_para_outro_exige_admin(self, *_):
        out = parse(at._handle_criar_atividade(
            {"titulo": "x", "para_usuario": "lizianne"}))
        assert "erro" in out

    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "db")
    def test_concluir_por_texto_aproximado(self, mock_db, _me):
        mock_db.list_activities.return_value = [
            {"id": "a1", "title": "Follow-up com Colegio Alfa", "status": "open"}]
        mock_db.complete_activity.return_value = True
        out = parse(at._handle_concluir_atividade({"ref": "alfa"}))
        assert out["ok"] is True
        mock_db.complete_activity.assert_called_once_with("a1", "fernando", "manual")

    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "db")
    def test_concluir_ambiguo_lista_opcoes(self, mock_db, _me):
        mock_db.list_activities.return_value = [
            {"id": "a1", "title": "Ligar Colegio Alfa", "status": "open"},
            {"id": "a2", "title": "Follow-up Colegio Alfa", "status": "open"}]
        out = parse(at._handle_concluir_atividade({"ref": "alfa"}))
        assert out.get("ambiguo") is True and len(out["opcoes"]) == 2

    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "db")
    def test_adiar_respeita_limite(self, mock_db, _me):
        mock_db.list_activities.return_value = [
            {"id": "a1", "title": "Ligar Alfa", "status": "open"}]
        mock_db.snooze_activity.return_value = {
            "ok": False, "erro": "limite de 3 adiamentos atingido — conclua ou dispense com motivo"}
        out = parse(at._handle_adiar_atividade({"ref": "alfa", "quando": "2026-06-15"}))
        assert "limite" in out["erro"]


class TestMetasEArgumentos:
    @patch.object(at, "get_active_sender_username", return_value="lizianne")
    @patch.object(at, "db")
    def test_minha_meta_sem_metas(self, mock_db, _me):
        mock_db.list_goals.return_value = []
        out = parse(at._handle_minha_meta({}))
        assert "msg" in out and "metas" not in out

    @patch.object(at, "get_active_sender_username", return_value="lizianne")
    @patch.object(at, "db")
    def test_minha_meta_com_realizado(self, mock_db, _me):
        mock_db.list_goals.return_value = [
            {"username": "lizianne", "metric": "emails_enviados", "target": 40}]
        mock_db.goal_realized.return_value = 28.0
        out = parse(at._handle_minha_meta({"mes": "2026-06"}))
        m = out["metas"][0]
        assert m["realizado"] == 28.0 and m["meta"] == 40.0 and m["pct"] == 70.0

    @patch.object(at, "db")
    def test_argumentos_gap_enem(self, mock_db):
        company = {"id": "c1", "name": "Colegio X", "inep_code": "43000001",
                   "matriculas_fund_af": 300, "matriculas_medio": 300,
                   "qt_coordenadores": 0, "nivel_tecnologico": "Baixo"}
        mock_db.client.table.return_value = make_query(data=[{
            "enem_gap_vs_peer_2025": -23, "enem_area_mais_fraca": "Matematica",
            "enem_amostra_confiavel": True, "peer_trajetoria_6y": "crescendo",
            "enem_media_geral": 512, "enem_potencial_melhoria": 80}])
        with patch("integrations.agenda_config.agenda_config.ticket_por_aluno",
                   return_value=7.99):
            args = at._build_argumentos(company)
        joined = " ".join(args)
        assert "Matematica" in joined and "23 pontos" in joined
        assert any("R$" in a for a in args)        # receita potencial
        assert any("direcao" in a for a in args)   # sem coordenador

    @patch.object(at, "db")
    def test_argumentos_respeitam_amostra_nao_confiavel(self, mock_db):
        company = {"id": "c1", "name": "X", "inep_code": "43000002",
                   "matriculas_fund_af": 100, "matriculas_medio": 0,
                   "qt_coordenadores": 1, "nivel_tecnologico": "Medio"}
        mock_db.client.table.return_value = make_query(data=[{
            "enem_gap_vs_peer_2025": -30, "enem_area_mais_fraca": "Redacao",
            "enem_amostra_confiavel": False}])
        with patch("integrations.agenda_config.agenda_config.ticket_por_aluno",
                   return_value=7.99):
            args = at._build_argumentos(company)
        assert not any("30 pontos" in a for a in args)  # nao cita numero
        assert any("indicativ" in a for a in args)       # aviso presente


class TestRegistrarEncontro:
    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "_find_company", return_value=None)
    def test_escola_inexistente_pede_confirmacao(self, *_):
        out = parse(at._handle_registrar_encontro({"escola": "Colegio Novo"}))
        assert out.get("escola_nao_encontrada") is True

    @patch.object(at, "get_active_sender_username", return_value="fernando")
    @patch.object(at, "_find_company", return_value=None)
    @patch.object(at, "db")
    def test_cria_escola_manual_com_inep_sintetico(self, mock_db, *_):
        mock_db.insert_company.return_value = "novo-id"
        mock_db.client.table.return_value = make_query()
        mock_db.create_activity.return_value = {
            "id": "a1", "due_at": "2026-06-12T12:00:00+00:00"}
        out = parse(at._handle_registrar_encontro({
            "escola": "Colegio Novo", "criar_escola": True, "cidade": "Porto Alegre",
            "uf": "rs", "proximo_passo": "Ligar", "proximo_quando": "2026-06-12"}))
        assert out["ok"] is True
        payload = mock_db.insert_company.call_args[0][0]
        assert payload["inep_code"].startswith("M-")
        assert payload["fonte_dados"] == "manual"
        assert payload["state"] == "RS"
