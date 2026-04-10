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
        channel = msg.get("channel", "email")

        # Buscar dados do contato
        to_email = None
        to_name = "Diretor(a)"
        to_phone = None
        to_phone_whatsapp = None
        if contact_id:
            try:
                c = db.client.table("contacts").select("full_name,email,phone,phone_whatsapp").eq("id", contact_id).single().execute()
                if c.data:
                    to_email = c.data.get("email")
                    to_name = c.data.get("full_name") or "Diretor(a)"
                    to_phone = c.data.get("phone")
                    to_phone_whatsapp = c.data.get("phone_whatsapp")
            except Exception:
                pass

        # Se eh canal WhatsApp, priorizar phone_whatsapp (celular com 9 dig)
        # Fallback para qualquer contato da escola com phone_whatsapp
        if channel == "whatsapp" and not to_phone_whatsapp and company_id:
            try:
                cts = db.client.table("contacts").select("id,full_name,phone_whatsapp").eq(
                    "company_id", company_id
                ).not_.is_("phone_whatsapp", "null").limit(1).execute().data or []
                if cts:
                    to_phone_whatsapp = cts[0].get("phone_whatsapp")
                    if not to_name or to_name == "Diretor(a)":
                        to_name = cts[0].get("full_name") or to_name
            except Exception:
                pass

        # Se nao tem telefone do contato, buscar da escola (fallback para email)
        if not to_phone and company_id:
            try:
                comp = db.client.table("companies").select("phone").eq("id", company_id).single().execute()
                to_phone = (comp.data or {}).get("phone")
            except Exception:
                pass

        # ====== DISPATCH POR CANAL ======

        result = {}

        if channel == "whatsapp":
            # --- WHATSAPP ---
            # Escolher melhor telefone: phone_whatsapp > phone (fallback)
            wpp_number = to_phone_whatsapp or to_phone

            if not wpp_number:
                logger.warning("Sem telefone WhatsApp - bloqueando", extra={"queue_id": queue_id})
                try:
                    db.client.table("approval_queue").update({
                        "status": "blocked",
                        "rejection_reason": "Sem phone_whatsapp cadastrado. Rode seed_whatsapp_numbers.",
                    }).eq("id", queue_id).execute()
                except Exception:
                    pass
                skipped += 1
                details.append({"queue_id": queue_id, "status": "blocked", "reason": "sem_phone_whatsapp"})
                continue

            try:
                from agent.whatsapp_bridge import WhatsAppBridge
                bridge = WhatsAppBridge()

                # Validar se numero eh registrado no WhatsApp antes de enviar
                try:
                    check = bridge.check_number(wpp_number)
                    if check.get("exists") is False:
                        logger.warning("Numero nao registrado no WhatsApp", extra={
                            "queue_id": queue_id, "number": wpp_number,
                        })
                        db.client.table("approval_queue").update({
                            "status": "blocked",
                            "rejection_reason": f"Numero {wpp_number} nao registrado no WhatsApp.",
                        }).eq("id", queue_id).execute()
                        skipped += 1
                        details.append({"queue_id": queue_id, "status": "blocked", "reason": "numero_nao_whatsapp"})
                        continue
                    # Se exists is None (erro/timeout), continua — evita bloquear tudo por falha do check
                except Exception as _e:
                    logger.debug(f"check_number skip: {_e}")

                send_result = bridge.send_message(wpp_number, body)
                result = {"success": bool(send_result.get("success") or send_result.get("key"))}
            except Exception as e:
                logger.error(f"WhatsApp send erro: {e}")
                result = {"success": False, "error": str(e)}

        elif channel == "linkedin":
            # --- LINKEDIN (manual — notificar Fernando) ---
            try:
                import os
                from agent.whatsapp_bridge import WhatsAppBridge
                bridge = WhatsAppBridge()
                owner = os.getenv("IALEX_OWNER_NUMBER", "")
                if owner:
                    bridge.send_message(owner, (
                        f"📩 *Acao manual LinkedIn*\n\n"
                        f"🏫 Escola: procurar no banco\n"
                        f"👤 Contato: {to_name}\n\n"
                        f"📝 *Mensagem para enviar:*\n{body[:500]}\n\n"
                        f"_Envie manualmente no LinkedIn e depois me diga 'feito'._"
                    ))
                # Marcar como manual_action (nao como sent)
                db.client.table("approval_queue").update({
                    "status": "manual_action",
                }).eq("id", queue_id).execute()
                sent += 1
                details.append({"queue_id": queue_id, "status": "manual_action", "channel": "linkedin"})
                logger.info("LinkedIn: notificacao manual enviada", extra={"queue_id": queue_id})
                continue
            except Exception as e:
                logger.error(f"LinkedIn notify erro: {e}")
                result = {"success": False}

        else:
            # --- EMAIL (default) ---
            if not to_email:
                logger.warning("Sem email - bloqueando", extra={"queue_id": queue_id})
                try:
                    db.client.table("approval_queue").update({
                        "status": "blocked",
                        "rejection_reason": "Contato sem email cadastrado. Adicione o email e reprocesse.",
                    }).eq("id", queue_id).execute()
                except Exception:
                    pass
                skipped += 1
                details.append({"queue_id": queue_id, "status": "blocked", "reason": "sem_email"})
                continue
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
                # Atualizar status da escola para 'contacted' (se ainda nao estiver)
                if company_id:
                    try:
                        comp = db.client.table("companies").select("status").eq(
                            "id", company_id
                        ).single().execute()
                        if comp.data and comp.data.get("status") in ("raw", "qualified", "enriched"):
                            db.client.table("companies").update({
                                "status": "contacted",
                                "last_contacted_at": now,
                            }).eq("id", company_id).execute()
                    except Exception:
                        pass
                # Registrar interacao
                interaction_type = f"{channel}_sent" if channel != "email" else "email_sent"
                db.insert_interaction({
                    "company_id": company_id,
                    "contact_id": contact_id,
                    "type": interaction_type,
                    "channel": channel,
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