"""
follow_up_manager.py - Gerencia sequencias automaticas de follow-up por email.

Verifica quais empresas precisam de follow-up (dias 3, 7, 14 apos ultimo contato),
gera mensagem contextual via Claude Sonnet e coloca na approval_queue.

REGRA ABSOLUTA: Follow-ups SEMPRE passam pela approval_queue.
NUNCA envia sem aprovacao humana.

Sequencia:
  Follow-up 1 (dia 3):  Lembrete gentil
  Follow-up 2 (dia 7):  Compartilhar valor adicional
  Follow-up 3 (dia 14): Ultima tentativa, angulo diferente

Maximo de 3 follow-ups por empresa. Apos isso, para automaticamente.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings

from anthropic import Anthropic

# ===========================================================================
# Configuracao da sequencia de follow-up
# ===========================================================================

FOLLOW_UP_STEPS: List[Dict[str, Any]] = [
    {"number": 1, "days_after": 3, "style": "gentle_reminder",
     "label": "Lembrete gentil"},
    {"number": 2, "days_after": 7, "style": "additional_value",
     "label": "Valor adicional"},
    {"number": 3, "days_after": 14, "style": "last_attempt",
     "label": "Ultima tentativa"},
]

MAX_FOLLOW_UPS: int = 3


# ===========================================================================
# Funcoes auxiliares
# ===========================================================================

def _get_days_for_follow_up(follow_up_number: int) -> int:
    """Retorna quantos dias devem ter passado para o follow-up N.

    Args:
        follow_up_number: Numero do follow-up (1, 2 ou 3).

    Returns:
        Numero de dias apos ultimo contato.
    """
    for step in FOLLOW_UP_STEPS:
        if step["number"] == follow_up_number:
            return step["days_after"]
    return 999


def _get_style_for_follow_up(follow_up_number: int) -> str:
    """Retorna o estilo/tom para o follow-up N.

    Args:
        follow_up_number: Numero do follow-up (1, 2 ou 3).

    Returns:
        String com o estilo (gentle_reminder, additional_value, last_attempt).
    """
    for step in FOLLOW_UP_STEPS:
        if step["number"] == follow_up_number:
            return step["style"]
    return "gentle_reminder"


# ===========================================================================
# get_due_follow_ups: Encontra empresas que precisam de follow-up
# ===========================================================================

def get_due_follow_ups(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Encontra empresas que precisam de follow-up.

    Criterios:
        - Email foi ENVIADO (status='sent' E sent_at nao nulo)
        - Dias suficientes passaram desde o ultimo contato
        - Nenhuma resposta recebida (sem interacao 'email_replied')
        - Email nao voltou (sem bounced_at)
        - follow_up_number < 3 (maximo 3 follow-ups)
        - Nao tem mensagem pendente/aprovada para a mesma empresa

    Args:
        limit: Numero maximo de follow-ups para gerar.

    Returns:
        Lista de dicts com: company_id, contact_id, queue_id,
        next_follow_up_number, original_subject, original_body, sent_at.
    """
    logger.info("Buscando follow-ups devidos", extra={"limit": limit})

    try:
        # Buscar mensagens enviadas que podem precisar de follow-up
        result = db.client.table("approval_queue").select(
            "id, company_id, contact_id, subject, body, "
            "follow_up_number, sent_at, bounced_at, parent_id"
        ).eq("status", "sent").not_.is_("sent_at", "null").is_(
            "bounced_at", "null"
        ).lt("follow_up_number", MAX_FOLLOW_UPS).order(
            "sent_at", desc=False
        ).limit(200).execute()

        sent_messages = result.data or []
    except Exception as e:
        logger.error("Erro ao buscar mensagens enviadas", extra={"error": str(e)})
        return []

    if not sent_messages:
        logger.info("Nenhuma mensagem enviada encontrada para follow-up")
        return []

    now = datetime.now(timezone.utc)
    due_follow_ups: List[Dict[str, Any]] = []

    for msg in sent_messages:
        if len(due_follow_ups) >= limit:
            break

        company_id = msg.get("company_id")
        contact_id = msg.get("contact_id")
        queue_id = msg.get("id")
        current_follow_up = msg.get("follow_up_number", 0)
        sent_at_str = msg.get("sent_at")

        if not company_id or not sent_at_str:
            continue

        next_follow_up = current_follow_up + 1
        if next_follow_up > MAX_FOLLOW_UPS:
            continue

        # Calcular dias desde envio
        try:
            sent_at = datetime.fromisoformat(sent_at_str.replace("Z", "+00:00"))
            days_since_sent = (now - sent_at).days
        except (ValueError, TypeError):
            logger.warning("Data de envio invalida", extra={
                "queue_id": queue_id, "sent_at": sent_at_str})
            continue

        required_days = _get_days_for_follow_up(next_follow_up)
        if days_since_sent < required_days:
            continue

        # Verificar se ja tem resposta (interacao email_replied)
        try:
            reply_check = db.client.table("interactions").select("id").eq(
                "company_id", company_id
            ).eq("type", "email_replied").limit(1).execute()

            if reply_check.data:
                logger.debug("Empresa ja respondeu - pulando", extra={
                    "company_id": company_id})
                continue
        except Exception as e:
            logger.warning("Erro ao verificar resposta", extra={
                "company_id": company_id, "error": str(e)})
            continue

        # Verificar se ja existe follow-up com esse numero na fila
        # (pendente, aprovado ou ja enviado com follow_up_number >= next)
        try:
            existing_check = db.client.table("approval_queue").select("id").eq(
                "company_id", company_id
            ).gte("follow_up_number", next_follow_up).limit(1).execute()

            if existing_check.data:
                logger.debug("Follow-up ja existe na fila", extra={
                    "company_id": company_id,
                    "follow_up_number": next_follow_up})
                continue
        except Exception as e:
            logger.warning("Erro ao verificar fila existente", extra={
                "company_id": company_id, "error": str(e)})
            continue

        # Verificar se tem mensagem pendente/aprovada para essa empresa
        try:
            pending_check = db.client.table("approval_queue").select("id").eq(
                "company_id", company_id
            ).in_("status", ["pending", "approved"]).limit(1).execute()

            if pending_check.data:
                logger.debug("Empresa tem mensagem pendente - pulando", extra={
                    "company_id": company_id})
                continue
        except Exception as e:
            logger.warning("Erro ao verificar pendentes", extra={
                "company_id": company_id, "error": str(e)})
            continue

        # Encontrar a mensagem original (raiz da cadeia)
        original_subject = msg.get("subject", "")
        original_body = msg.get("body", "")

        # Se este msg ja e follow-up, buscar o original via parent_id
        if msg.get("parent_id"):
            try:
                parent = db.client.table("approval_queue").select(
                    "subject, body, parent_id"
                ).eq("id", msg["parent_id"]).single().execute()

                if parent.data:
                    # Se o parent tambem tem parent, buscar a raiz
                    root = parent.data
                    while root.get("parent_id"):
                        try:
                            grandparent = db.client.table("approval_queue").select(
                                "subject, body, parent_id"
                            ).eq("id", root["parent_id"]).single().execute()
                            if grandparent.data:
                                root = grandparent.data
                            else:
                                break
                        except Exception:
                            break
                    original_subject = root.get("subject", original_subject)
                    original_body = root.get("body", original_body)
            except Exception:
                pass

        due_follow_ups.append({
            "company_id": company_id,
            "contact_id": contact_id,
            "queue_id": queue_id,
            "next_follow_up_number": next_follow_up,
            "original_subject": original_subject,
            "original_body": original_body,
            "sent_at": sent_at_str,
            "days_since_sent": days_since_sent,
        })

    logger.info("Follow-ups devidos encontrados", extra={
        "total_sent_checked": len(sent_messages),
        "due_count": len(due_follow_ups)})

    return due_follow_ups


# ===========================================================================
# generate_follow_up: Gera mensagem de follow-up via Claude
# ===========================================================================

def generate_follow_up(
    company_id: str,
    contact_id: Optional[str],
    original_queue_id: str,
    follow_up_number: int = 1,
    original_subject: str = "",
    original_body: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Gera mensagem de follow-up personalizada via Claude Sonnet.

    A mensagem gerada vai para approval_queue com status='pending'.
    NUNCA envia sem aprovacao humana.

    Args:
        company_id: UUID da empresa.
        contact_id: UUID do contato (pode ser None).
        original_queue_id: UUID da mensagem original na approval_queue.
        follow_up_number: Numero do follow-up (1, 2 ou 3).
        original_subject: Assunto do email original enviado.
        original_body: Corpo do email original enviado.

    Returns:
        Dict com queue_id, subject, body ou None se falhar.
    """
    logger.info("Gerando follow-up", extra={
        "company_id": company_id,
        "follow_up_number": follow_up_number,
        "original_queue_id": original_queue_id})

    # Buscar dados da empresa
    try:
        company = db.get_company_detail(company_id)
        if not company:
            logger.error("Empresa nao encontrada", extra={
                "company_id": company_id})
            return None
    except Exception as e:
        logger.error("Erro ao buscar empresa", extra={
            "company_id": company_id, "error": str(e)})
        return None

    # Buscar dados do contato
    contact_name = "Diretor(a)"
    contact_role = "Diretor(a)"
    contact_email = None
    if contact_id:
        try:
            contact_result = db.client.table("contacts").select(
                "full_name, role, email"
            ).eq("id", contact_id).single().execute()

            if contact_result.data:
                contact_name = contact_result.data.get("full_name") or "Diretor(a)"
                contact_role = contact_result.data.get("role") or "Diretor(a)"
                contact_email = contact_result.data.get("email")
        except Exception as e:
            logger.warning("Erro ao buscar contato", extra={
                "contact_id": contact_id, "error": str(e)})

    # Montar contexto para o prompt
    school_name = company.get("name", "Escola")
    city = company.get("city", "")
    state = company.get("state", "")
    education_levels = company.get("education_levels", "")
    qualification_score = company.get("qualification_score", "N/A")

    meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "")
    meeting_link_text = os.getenv("HUBSPOT_MEETING_LINK_TEXT", "Agendar conversa")

    style = _get_style_for_follow_up(follow_up_number)

    # Instrucoes por estilo de follow-up
    style_instructions = {
        "gentle_reminder": (
            "Este e o PRIMEIRO follow-up (dia 3). Tom: lembrete gentil e amigavel.\n"
            "- Mencione brevemente o email anterior\n"
            "- Pergunte se recebeu/teve chance de ver\n"
            "- Reforce o beneficio principal em UMA frase\n"
            "- Seja breve (3-5 linhas no maximo)\n"
            "- NAO repita todo o conteudo do email original"
        ),
        "additional_value": (
            "Este e o SEGUNDO follow-up (dia 7). Tom: compartilhar valor adicional.\n"
            "- NAO mencione que nao recebeu resposta (evite pressao)\n"
            "- Compartilhe um dado novo, caso de sucesso ou insight relevante\n"
            "- Foque em como a plataforma resolve um problema especifico da escola\n"
            "- Inclua o link para agendar conversa\n"
            "- Tom consultivo, como quem quer ajudar"
        ),
        "last_attempt": (
            "Este e o TERCEIRO e ULTIMO follow-up (dia 14). Tom: abordagem final.\n"
            "- Mude o angulo completamente (nao repita argumentos anteriores)\n"
            "- Use uma pergunta provocativa ou dado impactante\n"
            "- Deixe claro que e a ultima mensagem (sem ser agressivo)\n"
            "- Ofereça alternativa simples (responder com 'sim' para agendar)\n"
            "- Maximo 4-5 linhas, direto ao ponto"
        ),
    }

    prompt = f"""Voce e um especialista em vendas B2B para escolas. Gere um email de follow-up.

CONTEXTO DA ESCOLA:
- Nome: {school_name}
- Cidade/UF: {city}/{state}
- Niveis de ensino: {education_levels}
- Score de qualificacao: {qualification_score}/100

CONTATO:
- Nome: {contact_name}
- Cargo: {contact_role}

EMAIL ORIGINAL ENVIADO:
Assunto: {original_subject}
---
{original_body[:500]}
---

FOLLOW-UP #{follow_up_number} de {MAX_FOLLOW_UPS}

INSTRUCOES DE ESTILO:
{style_instructions.get(style, style_instructions["gentle_reminder"])}

INFORMACOES DO REMETENTE:
- Nome: {settings.YOUR_NAME}
- Email: {settings.YOUR_EMAIL}
- Empresa: {getattr(settings, 'COMPANY_NAME', 'IAprendo')}
{f'- Link para agendar: {meeting_link}' if meeting_link else ''}
{f'  Texto do link: {meeting_link_text}' if meeting_link else ''}

REGRAS OBRIGATORIAS:
1. Assunto DEVE comecar com "Re: " seguido do assunto original (como resposta)
2. Maximo 60 caracteres no assunto
3. Tom profissional mas humano, NUNCA robotico
4. NUNCA mencione que e um email automatizado
5. NUNCA use template generico - personalize para a escola
6. Escreva em portugues brasileiro
7. Inclua assinatura com nome e empresa

Responda APENAS em JSON valido (sem markdown):
{{"subject": "Re: assunto original", "body": "corpo do email", "reasoning": "por que este approach"}}
"""

    # Chamar Claude Sonnet
    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        model_id = settings.CLAUDE_MODEL_QUALITY

        start_time = time.time()
        response = client.messages.create(
            model=model_id,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed_ms = (time.time() - start_time) * 1000

        response_text = response.content[0].text

        # Registrar uso de API
        try:
            db.insert_api_usage({
                "api_name": "anthropic",
                "endpoint": model_id,
                "credits_used": 1,
                "success": True,
                "response_time_ms": elapsed_ms,
                "context": {
                    "agent": "follow_up_manager",
                    "company_id": company_id,
                    "follow_up_number": follow_up_number,
                },
            })
        except Exception:
            pass

    except Exception as e:
        logger.error("Erro ao chamar Claude para follow-up", extra={
            "company_id": company_id, "error": str(e)})
        return None

    # Parsear resposta JSON
    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        data = json.loads(cleaned)
        subject = data.get("subject", "").strip()
        body = data.get("body", "").strip()
        reasoning = data.get("reasoning", "")

        if not subject or not body:
            logger.warning("Resposta do Claude sem subject ou body", extra={
                "company_id": company_id, "response_preview": response_text[:200]})
            return None

        # Garantir prefixo Re:
        if not subject.lower().startswith("re:"):
            subject = f"Re: {original_subject}"

        # Limitar tamanho do assunto
        if len(subject) > 60:
            subject = subject[:57] + "..."

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Falha ao parsear resposta do follow-up", extra={
            "company_id": company_id, "error": str(e),
            "response_preview": response_text[:200]})
        return None

    # Inserir na approval_queue com status='pending'
    # NUNCA envia sem aprovacao humana
    try:
        queue_data = {
            "company_id": company_id,
            "subject": subject,
            "body": body,
            "original_subject": subject,
            "original_body": body,
            "channel": "email",
            "status": "pending",
            "follow_up_number": follow_up_number,
            "parent_id": original_queue_id,
        }
        if contact_id:
            queue_data["contact_id"] = contact_id

        result = db.client.table("approval_queue").insert(queue_data).execute()

        if result.data:
            new_queue_id = result.data[0]["id"]
            logger.info("Follow-up na approval_queue (aguardando aprovacao)", extra={
                "queue_id": new_queue_id,
                "company_id": company_id,
                "follow_up_number": follow_up_number,
                "school_name": school_name})

            return {
                "queue_id": new_queue_id,
                "company_id": company_id,
                "company_name": school_name,
                "contact_name": contact_name,
                "follow_up_number": follow_up_number,
                "subject": subject,
                "body_preview": body[:150] + "..." if len(body) > 150 else body,
                "reasoning": reasoning,
                "style": style,
            }
        else:
            logger.error("Insercao na approval_queue retornou vazio", extra={
                "company_id": company_id})
            return None

    except Exception as e:
        logger.error("Erro ao inserir follow-up na approval_queue", extra={
            "company_id": company_id, "error": str(e)}, exc_info=True)
        return None


# ===========================================================================
# run_follow_up_check: Funcao principal chamada periodicamente
# ===========================================================================

def run_follow_up_check(limit: int = 20) -> Dict[str, Any]:
    """
    Verifica e gera follow-ups devidos.

    Funcao principal chamada pelo scheduler ou pipeline diario.
    Busca empresas que precisam de follow-up, gera mensagens via Claude
    e coloca na approval_queue com status='pending'.

    NUNCA envia sem aprovacao humana.

    Args:
        limit: Numero maximo de follow-ups para gerar nesta execucao.

    Returns:
        Dict com: generated (int), errors (int), skipped (int), details (list).
    """
    logger.info("Iniciando verificacao de follow-ups", extra={"limit": limit})
    started_at = datetime.now(timezone.utc).isoformat()

    # 1. Buscar follow-ups devidos
    due = get_due_follow_ups(limit=limit)

    if not due:
        logger.info("Nenhum follow-up devido no momento")
        return {
            "started_at": started_at,
            "generated": 0,
            "errors": 0,
            "skipped": 0,
            "details": [],
        }

    generated = 0
    errors = 0
    skipped = 0
    details: List[Dict[str, Any]] = []

    # 2. Gerar follow-ups
    for item in due:
        try:
            result = generate_follow_up(
                company_id=item["company_id"],
                contact_id=item.get("contact_id"),
                original_queue_id=item["queue_id"],
                follow_up_number=item["next_follow_up_number"],
                original_subject=item.get("original_subject", ""),
                original_body=item.get("original_body", ""),
            )

            if result:
                generated += 1
                details.append({
                    "status": "generated",
                    "company_id": item["company_id"],
                    "queue_id": result["queue_id"],
                    "follow_up_number": item["next_follow_up_number"],
                    "company_name": result.get("company_name", ""),
                    "subject": result.get("subject", ""),
                })
                logger.info("Follow-up gerado", extra={
                    "company_id": item["company_id"],
                    "follow_up_number": item["next_follow_up_number"],
                    "queue_id": result["queue_id"]})
            else:
                errors += 1
                details.append({
                    "status": "error",
                    "company_id": item["company_id"],
                    "follow_up_number": item["next_follow_up_number"],
                    "reason": "geracao_falhou",
                })

            # Rate limiting: pequena pausa entre chamadas Claude
            if generated < len(due):
                time.sleep(1)

        except Exception as e:
            errors += 1
            details.append({
                "status": "error",
                "company_id": item.get("company_id", "?"),
                "follow_up_number": item.get("next_follow_up_number", "?"),
                "reason": str(e)[:200],
            })
            logger.error("Erro ao gerar follow-up", extra={
                "company_id": item.get("company_id"),
                "error": str(e)}, exc_info=True)

    summary = {
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "generated": generated,
        "errors": errors,
        "skipped": skipped,
        "due_found": len(due),
        "details": details,
    }

    logger.info("Verificacao de follow-ups concluida", extra={
        "generated": generated,
        "errors": errors,
        "due_found": len(due)})

    return summary


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerenciador de follow-ups")
    parser.add_argument("--limit", type=int, default=20,
                        help="Maximo de follow-ups para gerar (default: 20)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas mostra follow-ups devidos sem gerar")
    args = parser.parse_args()

    if args.dry_run:
        due = get_due_follow_ups(limit=args.limit)
        print(f"\nFollow-ups devidos: {len(due)}")
        for item in due:
            print(f"  - Empresa: {item['company_id'][:8]}... | "
                  f"Follow-up #{item['next_follow_up_number']} | "
                  f"Dias desde envio: {item['days_since_sent']} | "
                  f"Assunto original: {item['original_subject'][:40]}")
    else:
        result = run_follow_up_check(limit=args.limit)
        print(f"\nFollow-ups gerados: {result['generated']}")
        print(f"Erros: {result['errors']}")
        print(f"Total devidos: {result.get('due_found', 0)}")
        for d in result["details"]:
            status = d["status"]
            cid = str(d.get("company_id", "?"))[:8]
            fu = d.get("follow_up_number", "?")
            print(f"  [{status}] Empresa {cid}... Follow-up #{fu}")
