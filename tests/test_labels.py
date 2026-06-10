"""Testes de dashboard/labels.py — fonte unica do vocabulario da v2."""
import pytest

from dashboard.labels import (
    ACTIVITY_TYPES, GOAL_METRICS, LOSS_REASONS, MESSAGE_STATUS,
    POTENTIAL_STARS, PRIORITY_TIERS, STAGE_ORDER,
    activity_label, goal_metric_label, message_status_label,
    priority_label, priority_of, school_stage, school_stage_label,
)


class TestSchoolStage:
    @pytest.mark.parametrize("status,expected", [
        ("raw", "Nova"), ("filtered", "Avaliada"), ("qualified", "Avaliada"),
        ("enriched", "Pronta para contato"), ("contacted", "Contatada"),
        ("responded", "Respondeu"), ("converted", "Cliente"), ("rejected", "Perdida"),
    ])
    def test_status_tecnico(self, status, expected):
        assert school_stage_label(status) == expected

    @pytest.mark.parametrize("cs,expected", [
        ("prospectado", "Pronta para contato"), ("contatado", "Contatada"),
        ("respondeu", "Respondeu"), ("reuniao", "Em reuniao"),
        ("proposta", "Proposta enviada"), ("cliente", "Cliente"), ("perdido", "Perdida"),
    ])
    def test_commercial_stage(self, cs, expected):
        assert school_stage_label("contacted", cs) == expected

    def test_commercial_tem_precedencia(self):
        assert school_stage_label("raw", "proposta") == "Proposta enviada"

    def test_desconhecido_e_none_viram_nova(self):
        assert school_stage_label(None) == "Nova"
        assert school_stage_label("xyz") == "Nova"

    def test_toda_etapa_tem_cor_hex(self):
        for status in ["raw", "qualified", "enriched", "contacted", "responded"]:
            label, cor = school_stage(status)
            assert cor.startswith("#") and len(cor) == 7
        assert all(s in STAGE_ORDER for s in
                   ["Nova", "Cliente", "Perdida", "Em reuniao"])


class TestPriority:
    @pytest.mark.parametrize("score,tier", [
        (100, "CRITICAL"), (80, "CRITICAL"), (79, "HOT"), (60, "HOT"),
        (59, "WARM"), (40, "WARM"), (39, "COLD"), (0, "COLD"), (None, "COLD"),
    ])
    def test_thresholds_nas_bordas(self, score, tier):
        assert priority_of(score) == tier

    def test_label_por_tier_e_por_score(self):
        assert priority_label("CRITICAL") == "🔴 Agir agora"
        assert priority_label(65) == "🟠 Quente"
        assert priority_label(None) == "⚪ Frio"

    def test_tiers_completos(self):
        assert set(PRIORITY_TIERS) == {"CRITICAL", "HOT", "WARM", "COLD"}


class TestMessageStatus:
    def test_todos_os_status_mapeados(self):
        for s in ["pending", "approved", "rejected", "sent", "delivered",
                  "opened", "clicked", "replied", "bounced"]:
            assert s in MESSAGE_STATUS
            assert "label" in MESSAGE_STATUS[s]

    def test_labels(self):
        assert message_status_label("pending") == "⏳ Aguardando sua aprovacao"
        assert message_status_label("approved", "as 14h") == "✅ Aprovada — sai as 14h"
        assert message_status_label(None).startswith("⏳")


class TestActivityAndGoals:
    def test_activity_types_cobrem_o_schema(self):
        # Tem de bater com a CHECK constraint da migration 019
        assert set(ACTIVITY_TYPES) == {
            "follow_up", "responder", "ligar", "preparar_reuniao",
            "registrar_resultado", "aprovar_mensagens", "tarefa",
        }
        assert activity_label("responder") == "💬 Responder"
        assert activity_label(None) == "✍️ Tarefa"

    def test_goal_metrics_cobrem_o_schema(self):
        assert set(GOAL_METRICS) == {
            "emails_enviados", "respostas", "reunioes_realizadas",
            "propostas", "clientes", "valor_fechado", "atividades_concluidas",
        }
        assert goal_metric_label("clientes") == "Clientes novos"

    def test_loss_reasons_e_potencial(self):
        assert "sem_resposta" in LOSS_REASONS and "outro" in LOSS_REASONS
        assert POTENTIAL_STARS["P1"] == "★★★"
