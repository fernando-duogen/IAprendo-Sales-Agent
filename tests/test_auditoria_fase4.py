# -*- coding: utf-8 -*-
"""Regressao de ROBUSTEZ e limpeza (auditoria Ago/2026, fase 4).

Classe de bug: nada quebra na cara do usuario, mas o sistema para de fazer o
que promete — silenciosamente (numero truncado, feature que deixa de rodar,
guard que nunca dispara, config que nao configura).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _codigo(path: Path) -> str:
    return "\n".join(
        re.sub(r"#.*$", "", l) for l in path.read_text(encoding="utf-8").splitlines()
    )


# ---------------------------------------------------------------------------
# Paginacao: PostgREST clampa .limit() em 1000
# ---------------------------------------------------------------------------
def test_priorizar_leads_pagina():
    """Bug: .limit(25000) devolvia no maximo 1000 -> ranking e totais de um
    recorte grande (ex.: Estadual/Brasil = 15.828) saiam de 1/16 dos dados."""
    src = _codigo(ROOT / "agent" / "tools" / "enem_tools.py")
    i = src.find("def _handle_priorizar_leads_enem")
    assert i != -1
    trecho = src[i:i + 3000]
    assert ".range(" in trecho, "priorizar_leads_enem ainda nao pagina"
    assert "_POSTGREST_PAGE_SIZE" in trecho


def test_agregar_estatisticas_pagina():
    """Bug: alem de truncar, o flag `truncado` NUNCA disparava (len < _CAP),
    entao a resposta afirmava cobertura total de 185k escolas."""
    src = _codigo(ROOT / "agent" / "brain.py")
    i = src.find("def _handle_agregar_estatisticas_escolas")
    assert i != -1
    trecho = src[i:i + 4000]
    assert ".range(" in trecho, "agregacao ainda nao pagina"


def test_priorizar_leads_considera_as_duas_safras():
    """Linhas em enem_ano=2024 so tem as colunas _2024/_5y."""
    src = _codigo(ROOT / "agent" / "tools" / "enem_tools.py")
    i = src.find("def _handle_priorizar_leads_enem")
    trecho = src[i:i + 1500]
    assert "enem_gap_vs_peer_2024" in trecho
    assert "peer_trajetoria_5y" in trecho


# ---------------------------------------------------------------------------
# Follow-ups: a feature parava de rodar apos 500 envios
# ---------------------------------------------------------------------------
def test_followups_olham_os_mais_recentes():
    """Bug: order(sent_at, desc=False).limit(500) = os 500 MAIS ANTIGOS.
    Passado o 500o envio, email novo NUNCA gerava follow-up."""
    src = _codigo(ROOT / "workflows" / "follow_up_manager.py")
    i = src.find('.eq("status", "sent")')
    assert i != -1
    trecho = src[i:i + 300]
    assert "desc=True" in trecho, "follow-ups ainda varrem os envios mais antigos"


# ---------------------------------------------------------------------------
# Guard de duplicata usava status inexistente
# ---------------------------------------------------------------------------
def test_proactive_usa_status_canonico():
    """Bug: 'pending_approval' nao existe no CHECK -> contagem sempre 0 ->
    o guard nunca disparava e cada rodada empilhava um draft novo."""
    src = _codigo(ROOT / "tools" / "proactive_actions.py")
    assert "pending_approval" not in src
    assert '"status", "pending"' in src


# ---------------------------------------------------------------------------
# st.stop() dentro de aba apaga as abas seguintes
# ---------------------------------------------------------------------------
def test_helpers_de_aba_nao_usam_st_stop():
    """Streamlit renderiza TODAS as abas no mesmo run: st.stop() num helper
    matava as abas seguintes (ex.: 'Preparar escolas' e 'Sinais' sumiam)."""
    for nome in ("importar_mec.py", "inteligencia_view.py"):
        src = _codigo(ROOT / "dashboard" / "helpers" / nome)
        assert "st.stop()" not in src, f"{nome} ainda usa st.stop() dentro de aba"


# ---------------------------------------------------------------------------
# Rede de protecao da migration precisa olhar o __cause__
# ---------------------------------------------------------------------------
def test_update_company_inspeciona_cause():
    """Bug: o texto do PostgREST fica no __cause__ (raise ... from e), entao
    str(e) sozinho nunca casava e a protecao era inoperante — o enricher
    perdia o update INTEIRO (inclusive status)."""
    src = _codigo(ROOT / "agents" / "base_agent.py")
    assert "__cause__" in src


# ---------------------------------------------------------------------------
# Google: flag que nao desligava nada + CLI documentado inexistente
# ---------------------------------------------------------------------------
def test_enable_geocoding_desliga_de_verdade(monkeypatch):
    import importlib
    import integrations.google_places as gp

    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key")
    monkeypatch.setenv("ENABLE_GEOCODING", "false")
    importlib.reload(gp)
    assert gp.GooglePlacesClient().is_available() is False

    monkeypatch.setenv("ENABLE_GEOCODING", "true")
    importlib.reload(gp)
    assert gp.GooglePlacesClient().is_available() is True


def test_geocoder_tem_cli():
    """`python -m tools.geocoder` era citado em 5 docs e NAO FAZIA NADA
    (o arquivo nao tinha bloco __main__)."""
    src = (ROOT / "tools" / "geocoder.py").read_text(encoding="utf-8")
    arvore = ast.parse(src)
    assert any(isinstance(n, ast.FunctionDef) and n.name == "main"
               for n in arvore.body), "geocoder sem funcao main()"
    assert '__main__' in src


def test_google_maps_tem_alerta_de_quota():
    src = _codigo(ROOT / "tools" / "health_check.py")
    i = src.find("limits = {")
    trecho = src[i:i + 400]
    assert "google_maps" in trecho, "google_maps segue fora do alerta de cota"


# ---------------------------------------------------------------------------
# Consistencia visual/numerica
# ---------------------------------------------------------------------------
def test_cor_do_tier_cold_bate_entre_modulos():
    """COLD verde (urgency_widgets) x cinza (labels) — verde num lead FRIO
    lia-se como 'esta tudo bem'."""
    from dashboard.helpers.urgency_widgets import TIER_CONFIG
    from dashboard.labels import PRIORITY_TIERS
    cor_widget = TIER_CONFIG["COLD"]["color"].lower()
    cor_label = (PRIORITY_TIERS["COLD"].get("color") or "").lower()
    assert cor_widget == cor_label, \
        f"COLD com cores diferentes: widget={cor_widget} labels={cor_label}"


def test_chat_usa_cotacao_ao_vivo():
    """Bug: USD_BRL fixo em 5.50 no chat (com comentario de 'fallback' mas sem
    nenhuma tentativa) enquanto o painel usava cotacao ao vivo -> valores em R$
    divergentes para o mesmo gasto."""
    src = _codigo(ROOT / "agent" / "brain.py")
    i = src.find("USD_BRL = 5.50")
    assert i != -1
    trecho = src[i:i + 600]
    assert "economia.awesomeapi" in trecho, "chat ainda nao busca cotacao real"


def test_build_stamp_atualizado():
    """O carimbo servia p/ detectar deploy velho; 8 commits atrasado virou
    ruido permanente."""
    from dashboard._build import BUILD
    assert BUILD.startswith("2026-08"), f"build stamp desatualizado: {BUILD}"
