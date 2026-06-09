"""Testes de utils/stage_sync.py — coerencia status <-> commercial_stage.

Logica central da consistencia (fonte unica de verdade). Pura, sem DB.
"""
import pytest

from utils.stage_sync import (
    coherent_status_for_stage,
    infer_stage,
    STAGE_MAP,
    LABEL_TO_STAGE,
    COMMERCIAL_STAGE_ORDER,
)

# commercial_stage_rank / should_advance_commercial_stage podem nao existir ainda
# (sincronizacao externa do estagio — ex: pull do HubSpot). Os testes desses
# pulam graciosamente ate as funcoes entrarem no stage_sync.
try:
    from utils.stage_sync import commercial_stage_rank, should_advance_commercial_stage
    _HAS_ADVANCE = True
except ImportError:  # pragma: no cover
    _HAS_ADVANCE = False


class TestCoherentStatusForStage:
    @pytest.mark.parametrize("cur,stage,expected", [
        ("contacted", "cliente", "converted"),   # avanca
        (None, "cliente", "converted"),           # sem status atual -> converted
        ("raw", "proposta", "responded"),         # proposta => responded
        ("contacted", "respondeu", "responded"),
        ("qualified", "contatado", "contacted"),
        ("contacted", "perdido", "rejected"),
        ("converted", "contatado", None),         # NUNCA regride
        ("converted", "proposta", None),
        ("raw", "prospectado", None),             # prospectado nao forca status
        ("responded", "reuniao", None),           # reuniao->responded; ja esta responded
    ])
    def test_cases(self, cur, stage, expected):
        assert coherent_status_for_stage(cur, stage) == expected

    def test_unknown_or_empty_stage_returns_none(self):
        assert coherent_status_for_stage("raw", "xpto") is None
        assert coherent_status_for_stage("raw", None) is None
        assert coherent_status_for_stage("raw", "") is None


class TestInferStage:
    def test_manual_stage_sempre_vence(self):
        assert infer_stage({"commercial_stage": "proposta", "status": "raw"}) == "proposta"

    @pytest.mark.parametrize("status,expected", [
        ("contacted", "contatado"),
        ("responded", "respondeu"),
        ("converted", "cliente"),
        ("rejected", "perdido"),
        ("descartado", "perdido"),
        ("raw", "prospectado"),
        ("qualified", "prospectado"),
        ("enriched", "prospectado"),
        ("filtered", "prospectado"),
    ])
    def test_mapeamento_por_status(self, status, expected):
        assert infer_stage({"status": status}) == expected

    def test_sinais(self):
        assert infer_stage({"status": "raw"}, has_meeting=True) == "reuniao"
        assert infer_stage({"status": "raw"}, has_reply=True) == "respondeu"
        assert infer_stage({"status": "raw"}, has_email=True) == "contatado"

    def test_reuniao_tem_prioridade_sobre_reply_e_email(self):
        assert infer_stage(
            {"status": "raw"}, has_email=True, has_reply=True, has_meeting=True
        ) == "reuniao"

    def test_status_desconhecido_sem_sinais_none(self):
        assert infer_stage({"status": "weird"}) is None
        assert infer_stage({}) is None


@pytest.mark.skipif(not _HAS_ADVANCE, reason="commercial_stage_rank ainda nao no stage_sync (WIP)")
class TestCommercialStageRank:
    @pytest.mark.parametrize("stage,expected", [
        ("prospectado", 0), ("contatado", 1), ("respondeu", 2),
        ("reuniao", 3), ("proposta", 4), ("cliente", 5),
        ("perdido", -1), ("", -1), (None, -1), ("xyz", -1),
    ])
    def test(self, stage, expected):
        assert commercial_stage_rank(stage) == expected


@pytest.mark.skipif(not _HAS_ADVANCE, reason="should_advance_commercial_stage ainda nao no stage_sync (WIP)")
class TestShouldAdvanceCommercialStage:
    @pytest.mark.parametrize("cur,inc,expected", [
        (None, "contatado", True),        # lacuna -> preenche
        ("proposta", "contatado", False), # regrediria
        ("contatado", "proposta", True),  # avanca
        ("cliente", "perdido", False),    # deal ganho nunca regride
        ("reuniao", "perdido", True),     # HubSpot marcou perdido
        ("perdido", "cliente", True),     # perdido -> cliente (recupera)
        ("perdido", "contatado", False),  # perdido so avanca p/ cliente
        ("cliente", "contatado", False),  # cliente nunca regride
        ("contatado", "contatado", False),# igual
        (None, None, False),              # sem incoming
        ("contatado", "", False),         # incoming vazio
    ])
    def test(self, cur, inc, expected):
        assert should_advance_commercial_stage(cur, inc) == expected


class TestStageLabelMaps:
    """STAGE_MAP (push) e LABEL_TO_STAGE (pull) sao a fonte unica do mapeamento
    commercial_stage <-> label do HubSpot. Travam os dois sentidos pra nao
    divergirem (era o risco do espelho manual que existia no hubspot_pull)."""

    # commercial_stage validos: funil linear + terminal 'perdido'.
    CANONICAL = COMMERCIAL_STAGE_ORDER + ["perdido"]

    def test_todo_stage_canonico_tem_label(self):
        for stage in self.CANONICAL:
            assert stage in STAGE_MAP, f"{stage} sem label em STAGE_MAP"

    def test_roundtrip_canonico(self):
        # commercial_stage -> label -> commercial_stage volta no mesmo canonico.
        for stage in self.CANONICAL:
            label = STAGE_MAP[stage]
            assert LABEL_TO_STAGE[label] == stage, (
                f"round-trip quebrou: {stage} -> {label} -> {LABEL_TO_STAGE.get(label)}"
            )

    def test_email_aberto_colapsa_em_contatado(self):
        # 'Email Aberto' nao tem commercial_stage proprio -> 'contatado'.
        assert LABEL_TO_STAGE["Email Aberto"] == "contatado"

    def test_todo_label_do_stage_map_tem_inverso(self):
        for label in set(STAGE_MAP.values()):
            assert label in LABEL_TO_STAGE, f"label '{label}' sem inverso em LABEL_TO_STAGE"

    def test_inverso_so_aponta_pra_stage_valido(self):
        validos = set(self.CANONICAL)
        for label, stage in LABEL_TO_STAGE.items():
            assert stage in validos, f"'{label}' -> '{stage}' fora do dominio valido"
