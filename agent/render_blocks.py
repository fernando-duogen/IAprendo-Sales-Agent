"""Deriva blocos de renderizacao ricos a partir dos RESULTADOS das tools.

Canal lateral do conversa-primeiro (operador v1): os handlers de tool ja
retornam JSON estruturado (listas de escolas, URLs de graficos, itens da fila),
mas o LLM achata tudo em texto. Este modulo recupera essa estrutura SEM tocar
nas tools nem no conversation_history — o Brain chama blocks_from_tool() apos
cada handler e acumula os blocos; o chat web renderiza; o WhatsApp ignora.

REGRA DE OURO: blocks_from_tool NUNCA levanta excecao. Qualquer input
malformado/inesperado retorna [] — um bug de mapeamento jamais pode derrubar
o process_message (WhatsApp e chat dependem dele).

Tipos de bloco (contrato com dashboard/helpers/chat_blocks_view.py):
  school_list   {escolas: [..], total, fonte}
  download      {url, filename, label, detalhe}
  chart_ref     {charts: [{url, alt, chart_type}], escola}
  report_link   {url, escola, inep}
  approval_list {items: [..], total}
  email_preview {queue_id, escola, contato, email_destino, assunto, corpo,
                 canal, status, follow_up_numero}
  metric_summary{tool, data}
"""
from typing import Any, Dict, List, Optional

import json

# Tools cujo resultado e uma lista de escolas/leads (chave varia por tool).
_SCHOOL_LIST_TOOLS = {
    "consultar_escolas",
    "escolas_proximas",
    "meus_leads",
    "leads_sem_dono",
    "leads_parados",
    "buscar_escola_brasil",
    "buscar_escolas_por_enem",
    "priorizar_leads_enem",
    "ranking_evolucao_enem",
}
_LIST_KEYS = ("escolas", "leads", "ranking", "resultados", "resultado", "items")

# Tools cujo resultado e um resumo numerico (renderer mostra metric cards).
_METRIC_TOOLS = {
    "estatisticas_gerais",
    "relatorio_pipeline",
    "funil_vendas",
    "agregar_estatisticas_escolas",
    "kpi_periodo",
}

_MAX_LIST_ITEMS = 50


def _parse(result: Any) -> Optional[Dict[str, Any]]:
    """JSON string -> dict. None se nao for dict valido."""
    if isinstance(result, dict):
        return result
    if not isinstance(result, str):
        return None
    try:
        data = json.loads(result)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _first_list(data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Primeira lista-de-dicts encontrada nas chaves conhecidas."""
    for key in _LIST_KEYS:
        val = data.get(key)
        if isinstance(val, list) and val and all(isinstance(x, dict) for x in val):
            return val
    return None


def blocks_from_tool(tool_name: str, args: Dict[str, Any], result: Any) -> List[Dict[str, Any]]:
    """Mapeia (tool, resultado) -> lista de blocos de render. Nunca levanta."""
    try:
        return _blocks_from_tool_inner(tool_name, args, result)
    except Exception:
        return []


def _blocks_from_tool_inner(tool_name: str, args: Dict[str, Any], result: Any) -> List[Dict[str, Any]]:
    data = _parse(result)
    if not data or data.get("erro"):
        return []

    # --- Export XLSX -> botao de download -------------------------------
    if tool_name == "exportar_escolas_xlsx":
        url = data.get("url")
        if data.get("ok") and isinstance(url, str) and url.startswith("http"):
            return [{
                "type": "download",
                "url": url,
                "filename": str(data.get("filename") or "escolas.xlsx"),
                "label": "Baixar XLSX",
                "detalhe": (
                    f"{data.get('total_escolas', '?')} escola(s) + "
                    f"{data.get('total_contatos', '?')} contato(s) — link valido "
                    f"{data.get('validade_horas', 24)}h"
                ),
            }]
        return []

    # --- Graficos de insight -> imagens inline --------------------------
    if tool_name == "gerar_graficos_escola":
        charts = data.get("graficos")
        if isinstance(charts, list) and charts:
            clean = [
                {
                    "url": c.get("url"),
                    "alt": c.get("alt") or c.get("type") or "grafico",
                    "chart_type": c.get("type"),
                }
                for c in charts
                if isinstance(c, dict) and isinstance(c.get("url"), str)
            ]
            if clean:
                return [{
                    "type": "chart_ref",
                    "charts": clean,
                    "escola": data.get("escola"),
                }]
        return []

    # --- One Page Report -> link destacado ------------------------------
    if tool_name == "gerar_relatorio_escola":
        url = data.get("html_url")
        if isinstance(url, str) and url.startswith("http"):
            return [{
                "type": "report_link",
                "url": url,
                "escola": data.get("escola"),
                "inep": data.get("inep"),
            }]
        return []

    # --- Fila de aprovacao -> lista com acoes ---------------------------
    if tool_name == "fila_aprovacao":
        items = data.get("items")
        if isinstance(items, list) and items:
            return [{
                "type": "approval_list",
                "items": items[:_MAX_LIST_ITEMS],
                "total": data.get("total", len(items)),
            }]
        return []

    # --- Email completo -> preview com acoes (gate de aprovacao) --------
    if tool_name == "ver_email_completo":
        if data.get("queue_id") and data.get("corpo") is not None:
            return [{
                "type": "email_preview",
                "queue_id": data.get("queue_id"),
                "escola": data.get("escola", ""),
                "contato": data.get("contato", ""),
                "email_destino": data.get("email_destino", ""),
                "assunto": data.get("assunto", ""),
                "corpo": data.get("corpo", ""),
                "canal": data.get("canal", "email"),
                "status": data.get("status", ""),
                "follow_up_numero": data.get("follow_up_numero", 0),
            }]
        return []

    # --- Listas de escolas/leads -> cards/tabela ------------------------
    if tool_name in _SCHOOL_LIST_TOOLS:
        rows = _first_list(data)
        if rows:
            # buscar_escola_brasil usa "total_encontradas" (total real do
            # recorte); "total" e o tamanho da pagina em algumas tools.
            total = data.get("total_encontradas") or data.get("total") or len(rows)
            return [{
                "type": "school_list",
                "escolas": rows[:_MAX_LIST_ITEMS],
                "total": total,
                "fonte": data.get("fonte"),
                "tool": tool_name,
            }]
        return []

    # --- Resumos numericos -> metric cards ------------------------------
    if tool_name in _METRIC_TOOLS:
        return [{"type": "metric_summary", "tool": tool_name, "data": data}]

    return []
