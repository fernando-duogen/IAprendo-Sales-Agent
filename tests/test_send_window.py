# -*- coding: utf-8 -*-
"""Janela do envio AUTOMATICO de e-mail: dias uteis, e na sexta so as 8h.

Contexto (28/08/2026). O dono perguntou se o envio automatico respeitava dias
uteis. NAO respeitava: `_send_scheduled_messages` roda a cada 5 minutos e a
unica trava era a HORA (8h-18h) — nenhuma verificacao de dia. Na pratica, o que
fosse aprovado numa sexta a tarde saia no SABADO as 8h.

Regra pedida: enviar so em dia util e, na sexta, apenas no horario das 8h
(e-mail de prospeccao mandado sexta a tarde morre no fim de semana).

Estes testes existem porque a regra e de CALENDARIO: sem congelar o
comportamento por dia da semana, uma mudanca futura no gate passaria batida ate
alguem notar um e-mail saindo num domingo — e ninguem olha log de domingo.
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.scheduler import (  # noqa: E402
    BRT, BUSINESS_SEND_END, BUSINESS_SEND_START, FRIDAY_SEND_HOUR,
    send_window_check,
)

# Semana de referencia: 24/08/2026 e uma SEGUNDA.
SEG, TER, QUA, QUI, SEX, SAB, DOM = range(24, 31)


def _quando(dia_do_mes: int, hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 8, dia_do_mes, hora, minuto, tzinfo=BRT)


def _pode(dia_do_mes: int, hora: int, minuto: int = 0) -> bool:
    return send_window_check(_quando(dia_do_mes, hora, minuto))[0]


def test_a_semana_de_referencia_esta_certa():
    """Se esta ancora estiver errada, todo o resto do arquivo mente."""
    assert _quando(SEG, 9).weekday() == 0
    assert _quando(SEX, 9).weekday() == 4
    assert _quando(SAB, 9).weekday() == 5
    assert _quando(DOM, 9).weekday() == 6


# ---------------------------------------------------------------------------
# Fim de semana: nunca
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dia", [SAB, DOM], ids=["sabado", "domingo"])
@pytest.mark.parametrize("hora", [0, 8, 12, 17, 23])
def test_fim_de_semana_nunca_envia(dia, hora):
    assert _pode(dia, hora) is False


def test_fim_de_semana_explica_quando_volta():
    ok, motivo = send_window_check(_quando(SAB, 10))
    assert ok is False
    assert "segunda" in motivo.lower()


# ---------------------------------------------------------------------------
# Segunda a quinta: a janela comercial de sempre
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("dia", [SEG, TER, QUA, QUI],
                         ids=["seg", "ter", "qua", "qui"])
def test_dia_util_envia_na_janela_comercial(dia):
    assert _pode(dia, BUSINESS_SEND_START) is True
    assert _pode(dia, 12) is True
    assert _pode(dia, BUSINESS_SEND_END - 1, 59) is True


@pytest.mark.parametrize("dia", [SEG, TER, QUA, QUI],
                         ids=["seg", "ter", "qua", "qui"])
def test_dia_util_nao_envia_fora_da_janela(dia):
    assert _pode(dia, BUSINESS_SEND_START - 1, 59) is False
    assert _pode(dia, BUSINESS_SEND_END) is False, "18h em ponto ja esta fora"
    assert _pode(dia, 23) is False
    assert _pode(dia, 3) is False


# ---------------------------------------------------------------------------
# Sexta: SO o horario das 8h
# ---------------------------------------------------------------------------
def test_sexta_envia_as_8h():
    assert _pode(SEX, FRIDAY_SEND_HOUR) is True
    # o job roda a cada 5 min: a hora inteira das 8h e a janela
    assert _pode(SEX, FRIDAY_SEND_HOUR, 5) is True
    assert _pode(SEX, FRIDAY_SEND_HOUR, 55) is True


@pytest.mark.parametrize("hora", [7, 9, 10, 12, 15, 17, 18, 22])
def test_sexta_nao_envia_em_nenhuma_outra_hora(hora):
    """Inclui 9h-17h, que num dia util comum seria horario valido."""
    assert _pode(SEX, hora) is False


def test_sexta_a_tarde_explica_que_so_volta_na_segunda():
    ok, motivo = send_window_check(_quando(SEX, 15))
    assert ok is False
    assert "sexta" in motivo.lower() and "segunda" in motivo.lower()


def test_sexta_e_mais_restrita_que_os_outros_dias_uteis():
    """O invariante da regra: o que passa na quinta as 15h NAO passa na sexta."""
    assert _pode(QUI, 15) is True
    assert _pode(SEX, 15) is False


# ---------------------------------------------------------------------------
# Contrato com quem chama
# ---------------------------------------------------------------------------
def test_bloqueio_sempre_traz_motivo_e_liberacao_nunca_traz():
    for dia in (SEG, TER, QUA, QUI, SEX, SAB, DOM):
        for hora in range(24):
            ok, motivo = send_window_check(_quando(dia, hora))
            if ok:
                assert motivo == "", f"dia {dia} {hora}h liberado com motivo"
            else:
                assert motivo, f"dia {dia} {hora}h bloqueado sem motivo pro log"


def test_total_de_horas_liberadas_na_semana():
    """Fecha o numero: 4 dias x 10h + 1h na sexta = 41 janelas de hora."""
    liberadas = [(d, h) for d in (SEG, TER, QUA, QUI, SEX, SAB, DOM)
                 for h in range(24) if _pode(d, h)]
    assert len(liberadas) == 41, sorted(liberadas)


# ---------------------------------------------------------------------------
# next_send_slot: a tela nao pode prometer horario que nao acontece
# ---------------------------------------------------------------------------
from agent.scheduler import next_send_slot  # noqa: E402


def test_agendamento_dentro_da_janela_sai_na_hora_pedida():
    q = _quando(QUA, 14, 30)
    assert next_send_slot(q) == q


@pytest.mark.parametrize("dia,hora,rotulo", [
    (SEX, 15, "sexta a tarde"),
    (SAB, 10, "sabado"),
    (DOM, 20, "domingo"),
])
def test_agendamento_fora_da_janela_cai_na_segunda_as_8h(dia, hora, rotulo):
    saida = next_send_slot(_quando(dia, hora))
    assert saida.weekday() == 0, rotulo
    assert saida.hour == BUSINESS_SEND_START
    assert saida.day == 31, "segunda seguinte (31/08)"


def test_madrugada_de_dia_util_sai_as_8h_do_mesmo_dia():
    saida = next_send_slot(_quando(TER, 3))
    assert (saida.day, saida.hour) == (TER, BUSINESS_SEND_START)


def test_quinta_a_noite_cai_na_sexta_as_8h():
    saida = next_send_slot(_quando(QUI, 19))
    assert (saida.day, saida.hour) == (SEX, FRIDAY_SEND_HOUR)


def test_resultado_sempre_e_uma_janela_valida_e_nao_retrocede():
    for dia in (SEG, TER, QUA, QUI, SEX, SAB, DOM):
        for hora in range(24):
            pedido = _quando(dia, hora)
            saida = next_send_slot(pedido)
            assert send_window_check(saida)[0], f"{dia} {hora}h -> janela invalida"
            assert saida >= pedido, "nunca pode antecipar o envio"
