"""
send_approved.py - Envia APENAS mensagens aprovadas pelo humano.

REGRA ABSOLUTA: Nunca envia sem aprovacao. Status must be approved.
Este modulo e o ultimo guardiao antes do envio real.
"""
from typing import Dict, Any, List
from datetime import datetime, timezone
from database.supabase_client import db
from tools.brevo_sender import brevo_sender
from utils.logger import logger


def send_approved_messages(limit: int = 50) -> Dict[str, Any]:
    """
    Envia APENAS mensagens com status approved na approval_queue.
    NUNCA envia sem aprovacao humana previa.
    
    Returns:
        Dict com: sent, failed, skipped, details
    """
    logger.info("Iniciando envio de mensagens aprovadas", extra={"limit": limit})
    # Buscar apenas approved que ainda nao foram enviadas
    # Respeita agendamento: se scheduled_send_at existe, so envia quando hora chegar
    try:
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

        result = db.client.table("approval_queue")
        q = result.select(
            "id, company_id, contact_id, subject, body, channel, scheduled_send_at"
        ).eq("status", "approved").is_("sent_at", "null").or_(
            f"scheduled_send_at.is.null,scheduled_send_at.lte.{now_iso}"
        ).limit(limit).execute()
        approved_msgs = q.data
    except Exception as e:
        logger.error("Erro ao buscar aprovadas", extra={"error": str(e)})
        return {"sent": 0, "failed": 0, "skipped": 0, "error": str(e)}

    if not approved_msgs:
        logger.info("Nenhuma mensagem aprovada aguardando envio")
        return {"sent": 0, "failed": 0, "skipped": 0}

    sent = failed = skipped = 0
    details = []

    for msg in approved_msgs:
        queue_id = msg["id"]
        company_id = msg.get("company_id")
        contact_id = msg.get("contact_id")
        subject = msg.get("subject", "")
        body = msg.get("body", "")

        # Buscar email do contato
        to_email = None
        to_name = "Diretor(a)"
        if contact_id:
            try:
                c = db.client.table("contacts").select("full_name,email").eq("id", contact_id).single().execute()
                to_email = c.data.get("email") if c.data else None
                to_name = c.data.get("full_name") or "Diretor(a)" if c.data else "Diretor(a)"
            except Exception:
                pass

        if not to_email:
            logger.warning("Sem email - pulando", extra={"queue_id": queue_id, "company_id": company_id})
            skipped += 1
            details.append({"queue_id": queue_id, "status": "skipped", "reason": "sem_email"})
            continue        # Enviar via Brevo
        result = brevo_sender.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body=body,
            queue_id=queue_id,
        )
        if result.get("success"):
            # Marcar como enviada
            try:
                now = datetime.now(timezone.utc).isoformat()
                db.client.table("approval_queue").update({
                    "status": "sent",
                    "sent_at": now,
                }).eq("id", queue_id).execute()
                # Registrar interacao
                db.insert_interaction({
                    "company_id": company_id,
                    "contact_id": contact_id,
                    "type": "email_sent",
                    "channel": "email",
                    "subject": subject,
                    "metadata": {"queue_id": queue_id, "message_id": result.get("message_id", "")},
                })
                sent += 1
                details.append({"queue_id": queue_id, "status": "sent", "to": to_email})
                logger.info("Email enviado", extra={"queue_id": queue_id, "to": to_email})
                # Sync com HubSpot (nao-critico: falha nao impede envio)
                try:
                    from integrations.hubspot_sync import hubspot_sync
                    if hubspot_sync.enabled and company_id:
                        import time as _time
                        # 1. Garantir empresa no HubSpot
                        company_data = db.get_company_detail(company_id)
                        if not company_data:
                            raise ValueError(f"Company {company_id} nao encontrada")
                        if not company_data.get("hubspot_company_id"):
                            hubspot_sync.sync_company(company_data)
                            _time.sleep(1)
                            company_data = db.get_company_detail(company_id)
                        hs_company_id = company_data.get("hubspot_company_id") if company_data else None

                        # 2. Sincronizar APENAS o contato que recebeu o email
                        ct_data_for_hs = None
                        if contact_id:
                            try:
                                ct_query = db.client.table("contacts").select("*").eq("id", contact_id).single().execute()
                                ct_data_for_hs = ct_query.data
                            except Exception:
                                pass
                            if ct_data_for_hs and not ct_data_for_hs.get("hubspot_contact_id"):
                                hubspot_sync.sync_contact(ct_data_for_hs, hs_company_id)
                                _time.sleep(1)
                                # Recarregar para pegar hubspot_contact_id
                                try:
                                    ct_data_for_hs = db.client.table("contacts").select("*").eq("id", contact_id).single().execute().data
                                except Exception:
                                    pass

                        # 3. Criar deal se nao existe
                        company_data = db.get_company_detail(company_id)  # recarregar
                        if company_data and not company_data.get("hubspot_deal_id"):
                            hubspot_sync.create_deal(company_data, ct_data_for_hs)
                            _time.sleep(1)

                        # 4. Registrar email enviado
                        hubspot_sync.log_email_sent(msg, result)
                except Exception as hs_err:
                    logger.warning("HubSpot sync falhou", extra={"error": str(hs_err), "queue_id": queue_id})
            except Exception as e:
                logger.error("Erro ao atualizar status apos envio",
                    extra={"queue_id": queue_id, "error": str(e)})
        else:
            failed += 1
            details.append({"queue_id": queue_id, "status": "failed", "error": result.get("error", "")})
            logger.error("Falha ao enviar", extra={"queue_id": queue_id, "error": result.get("error", "")})

    summary = {"sent": sent, "failed": failed, "skipped": skipped, "details": details}
    logger.info("Envio concluido", extra=summary)
    return summary


if __name__ == "__main__":
    result = send_approved_messages()
    r = result
    print("Enviados:", r["sent"], "Falhas:", r["failed"], "Pulados:", r["skipped"])