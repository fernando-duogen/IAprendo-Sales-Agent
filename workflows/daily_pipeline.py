"""
daily_pipeline.py - Pipeline diario de prospeccao B2B.

Executa as etapas do pipeline na ordem correta:
1. Qualifica escolas (Claude Haiku)
2. Enriquece dados (web scraping)
3. Encontra decisores
4. Gera mensagens personalizadas (Claude Sonnet)
5. Coloca na approval_queue para aprovacao humana
6. Envia mensagens JA aprovadas

NUNCA envia sem aprovacao humana.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from database.supabase_client import db
from agents.qualifier import QualifierAgent
from agents.enricher import EnricherAgent
from agents.contact_finder import ContactFinderAgent
from agents.writer import WriterAgent
from workflows.send_approved import send_approved_messages
from utils.logger import logger


def _get_schools(
    status: str,
    limit: int,
    company_ids: Optional[List[str]] = None,
    force: bool = False,
):
    """Busca escolas por status, opcionalmente filtradas por IDs.

    Args:
        force: Se True E company_ids dado, ignora filtro de status e retorna
               todas as escolas nos IDs (modo "forcar reprocessar"). Util
               quando usuario quer rodar enrich numa escola ja enriched, ou
               re-qualify numa qualified, etc.
    """
    if company_ids:
        # force=True: ignora status, retorna todas dos IDs
        effective_status = None if force else status
        return db.get_companies_by_ids_and_status(company_ids, effective_status)[:limit]
    return db.get_companies_by_status(status, limit=limit)


def run_pipeline(
    qualify_limit: int = 20,
    enrich_limit: int = 10,
    write_limit: int = 10,
    send_approved: bool = True,
    dry_run: bool = False,
    write_mode: str = "ai",
    company_ids: Optional[List[str]] = None,
    steps: Optional[List[str]] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Executa o pipeline diario completo.

    Args:
        qualify_limit: Qtd de escolas para qualificar
        enrich_limit: Qtd para enriquecer
        write_limit: Qtd de mensagens para gerar
        send_approved: Se deve enviar as ja aprovadas
        dry_run: Se True, nao executa acoes reais
        write_mode: "ai" ou "template"
        company_ids: Lista de IDs de escolas para processar (None = todas)
        steps: Lista de etapas a executar (None = todas).
               Opcoes: "qualify", "enrich", "contacts", "write", "send"
    """
    all_steps = ["qualify", "enrich", "contacts", "write", "send"]
    active_steps = set(steps) if steps else set(all_steps)

    started_at = datetime.now().isoformat()
    logger.info("Pipeline iniciado", extra={
        "qualify_limit": qualify_limit,
        "enrich_limit": enrich_limit,
        "write_limit": write_limit,
        "dry_run": dry_run,
        "company_ids_count": len(company_ids) if company_ids else "all",
        "steps": list(active_steps),
    })
    report: Dict[str, Any] = {
        "started_at": started_at,
        "dry_run": dry_run,
        "steps": {},
    }

    # === ETAPA 1: QUALIFICAR ===
    if "qualify" in active_steps:
        logger.info("[1/5] Qualificando escolas...")
        to_qualify = _get_schools("raw", qualify_limit, company_ids, force=force)
        if not dry_run and to_qualify:
            qualifier = QualifierAgent()
            qualified = qualifier.execute(to_qualify, force=force)
            report["steps"]["qualify"] = {"input": len(to_qualify), "output": len(qualified)}
        else:
            report["steps"]["qualify"] = {"input": len(to_qualify), "output": 0, "skipped": dry_run}
        logger.info("[1/5] Qualificacao concluida", extra=report["steps"]["qualify"])

    # === ETAPA 2: ENRIQUECER ===
    if "enrich" in active_steps:
        logger.info("[2/5] Enriquecendo dados...")
        to_enrich = _get_schools("qualified", enrich_limit, company_ids, force=force)
        if not dry_run and to_enrich:
            enricher = EnricherAgent()
            enriched = enricher.execute(to_enrich, force=force)
            report["steps"]["enrich"] = {"input": len(to_enrich), "output": len(enriched)}
        else:
            report["steps"]["enrich"] = {"input": len(to_enrich), "output": 0, "skipped": dry_run}
        logger.info("[2/5] Enriquecimento concluido", extra=report["steps"]["enrich"])

    # === ETAPA 3: ENCONTRAR DECISORES ===
    if "contacts" in active_steps:
        logger.info("[3/5] Buscando decisores...")
        to_find_contact = _get_schools("enriched", enrich_limit, company_ids, force=force)
        if not dry_run and to_find_contact:
            contact_finder = ContactFinderAgent()
            contacts_found = contact_finder.execute(to_find_contact, force=force)
            report["steps"]["contacts"] = {"input": len(to_find_contact), "output": len(contacts_found)}
        else:
            report["steps"]["contacts"] = {"input": len(to_find_contact), "output": 0, "skipped": dry_run}
        logger.info("[3/5] Busca de decisores concluida", extra=report["steps"]["contacts"])

    # === ETAPA 4: GERAR MENSAGENS ===
    if "write" in active_steps:
        logger.info("[4/5] Gerando mensagens...")
        to_write: list = []
        if force and company_ids:
            # Em modo forcar, busca todas selecionadas sem filtrar status
            to_write = _get_schools("enriched", write_limit, company_ids, force=True)
        else:
            for status in ("enriched", "qualified", "contacted"):
                if len(to_write) < write_limit:
                    batch = _get_schools(status, write_limit - len(to_write), company_ids)
                    to_write.extend(batch)
        to_write = to_write[:write_limit]
        if not dry_run and to_write:
            writer = WriterAgent()
            messages = writer.execute(to_write, mode=write_mode, force=force)
            report["steps"]["write"] = {"input": len(to_write), "output": len(messages)}
        else:
            report["steps"]["write"] = {"input": len(to_write), "output": 0, "skipped": dry_run}
        logger.info("[4/5] Geracao de mensagens concluida", extra=report["steps"]["write"])

    # === ETAPA 5: ENVIAR APROVADAS ===
    if "send" in active_steps:
        if send_approved and not dry_run:
            logger.info("[5/5] Enviando mensagens aprovadas...")
            send_result = send_approved_messages(limit=50)
            report["steps"]["send"] = send_result
            logger.info("[5/5] Envio concluido", extra=send_result)
        else:
            report["steps"]["send"] = {"skipped": True}

    # === RELATORIO FINAL ===
    report["finished_at"] = datetime.now().isoformat()
    steps_data = report["steps"]
    total_qualified = steps_data.get("qualify", {}).get("output", 0)
    total_written = steps_data.get("write", {}).get("output", 0)
    total_sent = steps_data.get("send", {}).get("sent", 0)
    logger.info("Pipeline concluido", extra={
        "qualified": total_qualified,
        "written": total_written,
        "sent": total_sent,
    })
    report["summary"] = {
        "qualified": total_qualified,
        "messages_generated": total_written,
        "messages_sent": total_sent,
    }
    return report


if __name__ == "__main__":
    import json
    result = run_pipeline(qualify_limit=5, enrich_limit=3, write_limit=3)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
