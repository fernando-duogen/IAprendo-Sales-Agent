# -*- coding: utf-8 -*-
"""Testes de agent/render_blocks.py — funcao PURA e DEFENSIVA.

Contrato critico: blocks_from_tool NUNCA levanta excecao (um bug de mapeamento
jamais pode derrubar o process_message que atende WhatsApp e chat web).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.render_blocks import blocks_from_tool  # noqa: E402


# ---------------------------------------------------------------------------
# Defensividade — nunca levanta, lixo vira []
# ---------------------------------------------------------------------------
def test_json_malformado_retorna_vazio():
    assert blocks_from_tool("consultar_escolas", {}, "{nao e json") == []


def test_result_nao_string_retorna_vazio():
    assert blocks_from_tool("consultar_escolas", {}, None) == []
    assert blocks_from_tool("consultar_escolas", {}, 42) == []
    assert blocks_from_tool("consultar_escolas", {}, ["lista"]) == []
    assert blocks_from_tool("consultar_escolas", {}, object()) == []


def test_json_valido_mas_lista_nao_dict_retorna_vazio():
    assert blocks_from_tool("consultar_escolas", {}, json.dumps([1, 2])) == []


def test_erro_no_resultado_retorna_vazio():
    assert blocks_from_tool("exportar_escolas_xlsx", {}, json.dumps({"erro": "x"})) == []


def test_tool_desconhecida_retorna_vazio():
    assert blocks_from_tool("tool_inexistente", {}, json.dumps({"total": 1})) == []


def test_nunca_levanta_com_args_lixo():
    # args de tipos errados nao podem derrubar
    assert blocks_from_tool(None, None, None) == []
    assert blocks_from_tool(123, "x", b"bytes") == []


# ---------------------------------------------------------------------------
# school_list — chaves de lista e total (auditoria)
# ---------------------------------------------------------------------------
def test_ranking_evolucao_usa_chave_resultado():
    """ranking_evolucao_enem retorna 'resultado' (singular) — deve gerar bloco."""
    result = json.dumps({
        "resultado": [{"nome": "Escola A", "delta": 42.0}],
        "total_no_ranking": 1,
    })
    blocks = blocks_from_tool("ranking_evolucao_enem", {}, result)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "school_list"


def test_total_encontradas_prevalece_sobre_tamanho_da_pagina():
    """buscar_escola_brasil: total do RECORTE (3000), nao o tamanho da pagina (2)."""
    result = json.dumps({
        "total_encontradas": 3000,
        "escolas": [{"nome": "A"}, {"nome": "B"}],
    })
    blocks = blocks_from_tool("buscar_escola_brasil", {}, result)
    assert len(blocks) == 1
    assert blocks[0]["total"] == 3000


# ---------------------------------------------------------------------------
# download (exportar_escolas_xlsx)
# ---------------------------------------------------------------------------
def test_exportar_ok_vira_download():
    result = json.dumps({
        "ok": True, "url": "https://x.supabase.co/f.xlsx", "filename": "escolas_f.xlsx",
        "total_escolas": 5, "total_contatos": 9, "validade_horas": 24,
    })
    blocks = blocks_from_tool("exportar_escolas_xlsx", {}, result)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "download"
    assert b["url"].startswith("https://")
    assert b["filename"] == "escolas_f.xlsx"
    assert "5" in b["detalhe"] and "9" in b["detalhe"]


def test_exportar_falha_sem_bloco():
    assert blocks_from_tool("exportar_escolas_xlsx", {}, json.dumps({"ok": False})) == []
    # ok=True mas url invalida
    assert blocks_from_tool(
        "exportar_escolas_xlsx", {}, json.dumps({"ok": True, "url": "nao-url"})
    ) == []


# ---------------------------------------------------------------------------
# chart_ref (gerar_graficos_escola)
# ---------------------------------------------------------------------------
def test_graficos_viram_chart_ref():
    result = json.dumps({
        "sucesso": True, "escola": "Col X",
        "graficos": [
            {"url": "https://a/radar.png", "type": "radar", "alt": "Radar ENEM"},
            {"url": "https://a/gap.png", "type": "gap"},
            {"sem_url": True},  # entrada invalida deve ser filtrada
        ],
    })
    blocks = blocks_from_tool("gerar_graficos_escola", {}, result)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "chart_ref"
    assert b["escola"] == "Col X"
    assert len(b["charts"]) == 2
    assert b["charts"][0]["alt"] == "Radar ENEM"
    assert b["charts"][1]["alt"] == "gap"  # fallback pro type


def test_graficos_vazios_sem_bloco():
    assert blocks_from_tool("gerar_graficos_escola", {}, json.dumps({"graficos": []})) == []


# ---------------------------------------------------------------------------
# report_link (gerar_relatorio_escola)
# ---------------------------------------------------------------------------
def test_relatorio_vira_report_link():
    result = json.dumps({
        "sucesso": True, "escola": "Col Y", "inep": "43000001",
        "html_url": "https://dados.iaprendo.com.br/reports/43000001.html",
    })
    blocks = blocks_from_tool("gerar_relatorio_escola", {}, result)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "report_link"
    assert blocks[0]["inep"] == "43000001"


# ---------------------------------------------------------------------------
# approval_list (fila_aprovacao)
# ---------------------------------------------------------------------------
def test_fila_vira_approval_list():
    items = [{"id": f"q{i}", "escola": f"E{i}", "assunto": "A", "status": "pending"}
             for i in range(3)]
    blocks = blocks_from_tool("fila_aprovacao", {}, json.dumps({"total": 3, "items": items}))
    assert len(blocks) == 1
    assert blocks[0]["type"] == "approval_list"
    assert blocks[0]["total"] == 3
    assert len(blocks[0]["items"]) == 3


def test_fila_vazia_sem_bloco():
    assert blocks_from_tool("fila_aprovacao", {}, json.dumps({"total": 0, "items": []})) == []


# ---------------------------------------------------------------------------
# email_preview (ver_email_completo) — corpo COMPLETO preservado (gate!)
# ---------------------------------------------------------------------------
def test_email_completo_vira_preview_com_corpo_integral():
    corpo = "Linha 1\n" * 200  # corpo longo NAO pode ser truncado (regra zero)
    result = json.dumps({
        "queue_id": "q1", "escola": "Col Z", "contato": "Maria",
        "email_destino": "m@x.br", "assunto": "Oi", "corpo": corpo,
        "canal": "email", "status": "pending", "follow_up_numero": 0,
    })
    blocks = blocks_from_tool("ver_email_completo", {}, result)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "email_preview"
    assert b["queue_id"] == "q1"
    assert b["corpo"] == corpo  # integral


# ---------------------------------------------------------------------------
# school_list (tools de lista) — cap de 50
# ---------------------------------------------------------------------------
def test_consultar_escolas_vira_school_list():
    escolas = [{"id": str(i), "name": f"Escola {i}"} for i in range(80)]
    result = json.dumps({"total": 80, "fonte": "banco_crm", "escolas": escolas})
    blocks = blocks_from_tool("consultar_escolas", {}, result)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["type"] == "school_list"
    assert b["total"] == 80
    assert len(b["escolas"]) == 50  # cap
    assert b["fonte"] == "banco_crm"


def test_leads_key_alternativa():
    result = json.dumps({"total": 2, "leads": [{"id": "1"}, {"id": "2"}]})
    blocks = blocks_from_tool("meus_leads", {}, result)
    assert len(blocks) == 1 and blocks[0]["type"] == "school_list"


# ---------------------------------------------------------------------------
# metric_summary
# ---------------------------------------------------------------------------
def test_estatisticas_vira_metric_summary():
    result = json.dumps({"total_escolas": 121, "contatadas": 30})
    blocks = blocks_from_tool("estatisticas_gerais", {}, result)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "metric_summary"
    assert blocks[0]["data"]["total_escolas"] == 121
