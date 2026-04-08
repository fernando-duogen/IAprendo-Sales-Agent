"""
Reply Handler — Auto-resposta inteligente a replies de escolas.

Quando uma escola responde ao email, este modulo:
1. Analisa o conteudo da resposta (positiva? negativa? pediu info? quer agendar?)
2. Classifica a intencao
3. Gera uma resposta adequada via GPT
4. Coloca na fila de aprovacao (Fernando revisa antes de enviar)
5. Notifica Fernando no WhatsApp com analise + resposta sugerida

Intencoes detectadas:
- POSITIVO_AGENDAR: quer reuniao/demo → resposta com horarios
- POSITIVO_INFO: quer mais informacoes → resposta com detalhes
- POSITIVO_GENERICO: interesse sem acao clara → resposta calorosa + CTA
- NEGATIVO: nao interessado → resposta educada de despedida
- AUSENTE: resposta automatica/fora do escritorio → ignorar
- PERGUNTA: fez pergunta especifica → resposta com a informacao

Usage:
    from tools.reply_handler import reply_handler
    result = reply_handler.process_reply(queue_id)
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from utils.logger import logger


REPLY_INTENTS = {
    "positivo_agendar": {
        "label": "Quer agendar",
        "emoji": "📅",
        "style": "Responda com entusiasmo, proponha 2-3 horarios concretos, inclua link de agendamento.",
    },
    "positivo_info": {
        "label": "Quer mais info",
        "emoji": "📋",
        "style": "Responda com detalhes sobre IAprendo: pricing, funcionalidades, BNCC. Termine com CTA para agendar.",
    },
    "positivo_generico": {
        "label": "Interesse generico",
        "emoji": "👍",
        "style": "Responda de forma calorosa, reforce valor, proponha proximo passo concreto (demo de 15 min).",
    },
    "negativo": {
        "label": "Nao interessado",
        "emoji": "🚫",
        "style": "Responda educadamente, agradeca o retorno, deixe porta aberta para futuro. Maximo 3 linhas.",
    },
    "ausente": {
        "label": "Auto-resposta/ausente",
        "emoji": "🤖",
        "style": None,  # Nao gerar resposta
    },
    "pergunta": {
        "label": "Pergunta especifica",
        "emoji": "❓",
        "style": "Responda a pergunta diretamente com dados concretos. Termine com CTA.",
    },
}

# Markers de auto-resposta (ignorar)
AUTO_REPLY_MARKERS = [
    "fora do escritorio", "out of office", "automatic reply",
    "resposta automatica", "estou ausente", "ferias", "vacation",
    "noreply", "no-reply", "mailer-daemon",
]


class ReplyHandler:
    """Processa respostas de escolas e gera auto-respostas inteligentes."""

    def classify_intent(self, reply_text: str) -> str:
        """Classifica a intencao da resposta (sem GPT — regex/keywords rapido)."""
        if not reply_text:
            return "ausente"

        text_lower = reply_text.lower()

        # Auto-resposta?
        for marker in AUTO_REPLY_MARKERS:
            if marker in text_lower:
                return "ausente"

        # Negativo?
        neg_keywords = ["nao tenho interesse", "nao temos interesse", "no momento nao",
                        "nao e o momento", "cancel", "remover", "descadastrar",
                        "sem interesse", "nao obrigado"]
        for kw in neg_keywords:
            if kw in text_lower:
                return "negativo"

        # Quer agendar?
        agendar_keywords = ["agendar", "reuniao", "horario", "disponibilidade",
                           "conversar", "ligar", "call", "apresentacao", "demo",
                           "segunda", "terca", "quarta", "quinta", "sexta",
                           "semana que vem", "agenda"]
        for kw in agendar_keywords:
            if kw in text_lower:
                return "positivo_agendar"

        # Quer info?
        info_keywords = ["preco", "valor", "custo", "plano", "funciona",
                        "como funciona", "mais informacao", "detalhe",
                        "proposta", "orcamento", "piloto"]
        for kw in info_keywords:
            if kw in text_lower:
                return "positivo_info"

        # Pergunta?
        if "?" in reply_text:
            return "pergunta"

        # Positivo generico (tem texto significativo que nao e negativo)
        if len(text_lower.strip()) > 20:
            return "positivo_generico"

        return "ausente"

    def process_reply(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """Processa uma resposta: analisa, gera auto-resposta e coloca na fila.

        Args:
            queue_id: ID da mensagem original que recebeu reply

        Returns:
            Dict com intent, resposta gerada, novo queue_id. None se ignorar.
        """
        # Buscar email original + dados
        try:
            original = db.client.table("approval_queue").select(
                "id,subject,body,company_id,contact_id,replied_at,follow_up_number"
            ).eq("id", queue_id).single().execute()
            if not original.data:
                return None
            msg = original.data
        except Exception as e:
            logger.error(f"reply_handler: erro ao buscar original: {e}")
            return None

        company_id = msg.get("company_id")
        contact_id = msg.get("contact_id")

        # Buscar conteudo da resposta (interaction com type=email_replied)
        reply_text = ""
        try:
            interaction = db.client.table("interactions").select(
                "message_snippet,metadata"
            ).eq("type", "email_replied").eq("company_id", company_id).order(
                "created_at", desc=True
            ).limit(1).execute()
            if interaction.data:
                reply_text = interaction.data[0].get("message_snippet") or ""
                meta = interaction.data[0].get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                reply_text = reply_text or meta.get("body", "") or meta.get("content", "")
        except Exception:
            pass

        # Classificar intencao
        intent = self.classify_intent(reply_text)
        intent_info = REPLY_INTENTS.get(intent, REPLY_INTENTS["positivo_generico"])

        logger.info(f"Reply classificada: {intent}", extra={
            "queue_id": queue_id, "company_id": company_id,
            "reply_preview": reply_text[:100],
        })

        # Se auto-resposta/ausente, ignorar
        if intent == "ausente" or not intent_info.get("style"):
            return {"intent": intent, "action": "ignorado", "reason": "auto-resposta ou ausente"}

        # Buscar dados da escola e contato
        school_name = "?"
        contact_name = "?"
        contact_email = ""
        city = ""
        try:
            if company_id:
                c = db.client.table("companies").select("name,city,admin_category").eq(
                    "id", company_id
                ).single().execute()
                if c.data:
                    school_name = c.data.get("name", "?")
                    city = c.data.get("city", "")
            if contact_id:
                ct = db.client.table("contacts").select("full_name,email").eq(
                    "id", contact_id
                ).single().execute()
                if ct.data:
                    contact_name = ct.data.get("full_name", "?")
                    contact_email = ct.data.get("email", "")
        except Exception:
            pass

        # Buscar memorias da escola
        memory_ctx = ""
        try:
            from integrations.memory import memory
            mems = memory.get_for("company", company_id, limit=3)
            if mems:
                memory_ctx = memory.format_for_context(mems)
        except Exception:
            pass

        # Gerar auto-resposta via GPT
        meeting_link = os.getenv("HUBSPOT_MEETING_LINK", "")
        sender_name = os.getenv("YOUR_NAME", "Fernando")

        prompt = f"""Voce e {sender_name}, da IAprendo. Uma escola respondeu seu email de prospeccao.
Gere uma RESPOSTA adequada ao email da escola.

ESCOLA: {school_name} ({city})
CONTATO: {contact_name}

EMAIL ORIGINAL QUE VOCE ENVIOU:
Assunto: {msg.get('subject', '')}
---
{(msg.get('body', ''))[:500]}
---

RESPOSTA DA ESCOLA:
---
{reply_text[:800]}
---

INTENCAO DETECTADA: {intent} — {intent_info['label']}

INSTRUCOES DE ESTILO:
{intent_info['style']}

{f'MEMORIAS SOBRE ESTA ESCOLA:{chr(10)}{memory_ctx}' if memory_ctx else ''}

INFORMACOES UTEIS:
- Link de agendamento: {meeting_link}
- Preco IAprendo: a partir de R$ 9,90/mes por aluno (plano anual)
- Piloto gratuito: sim, 1-2 turmas por 30 dias
- 100% alinhado a BNCC
- Resultados: 30% melhor desempenho, 70% maior retencao

REGRAS:
1. Responda em PORTUGUES BRASILEIRO
2. Tom humano, como {sender_name} escreveria
3. Maximo 80 palavras
4. Se intent=negativo, maximo 30 palavras (agradeca e encerre)
5. Se intent=positivo_agendar, inclua link de agendamento
6. NUNCA invente dados

Responda APENAS em JSON: {{"subject": "Re: ...", "body": "...", "reasoning": "..."}}"""

        try:
            from dotenv import load_dotenv
            load_dotenv()
            from openai import OpenAI

            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return {"intent": intent, "action": "erro", "reason": "OPENAI_API_KEY nao configurada"}

            client = OpenAI(api_key=api_key)
            model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")

            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )
            raw_text = resp.choices[0].message.content or ""

            # Parse JSON
            import re
            cleaned = raw_text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            match = re.search(r'\{[\s\S]*\}', cleaned)
            if match:
                data = json.loads(match.group(0))
            else:
                data = {"subject": f"Re: {msg.get('subject', '')}", "body": raw_text[:500]}

            subject = data.get("subject", f"Re: {msg.get('subject', '')}")
            body = data.get("body", "")
            reasoning = data.get("reasoning", "")

        except Exception as e:
            logger.error(f"reply_handler GPT erro: {e}")
            return {"intent": intent, "action": "erro", "reason": str(e)[:200]}

        # Inserir na fila de aprovacao
        try:
            from tools.smart_scheduler import smart_scheduler
            scheduled_at = smart_scheduler.suggest_send_time_for_company(company_id).isoformat()
        except Exception:
            scheduled_at = None

        queue_data = {
            "company_id": company_id,
            "subject": subject[:500],
            "body": body,
            "original_subject": subject[:500],
            "original_body": body,
            "channel": "email",
            "status": "pending",
            "follow_up_number": (msg.get("follow_up_number") or 0) + 1,
            "parent_id": queue_id,
        }
        if scheduled_at:
            queue_data["scheduled_send_at"] = scheduled_at
        if contact_id:
            queue_data["contact_id"] = contact_id

        try:
            result = db.client.table("approval_queue").insert(queue_data).execute()
            new_queue_id = result.data[0]["id"] if result.data else None
        except Exception as e:
            logger.error(f"reply_handler insert erro: {e}")
            return {"intent": intent, "action": "erro", "reason": str(e)[:200]}

        # Salvar na memoria
        try:
            from integrations.memory import memory
            memory.remember(
                content=f"Escola respondeu ({intent_info['label']}): {reply_text[:200]}",
                scope="company",
                scope_id=company_id,
                category="insight",
                importance=9,
                source="ialex",
            )
        except Exception:
            pass

        logger.info(f"Auto-resposta gerada: {intent}", extra={
            "queue_id": queue_id, "new_queue_id": new_queue_id,
            "school": school_name,
        })

        return {
            "intent": intent,
            "intent_label": intent_info["label"],
            "intent_emoji": intent_info["emoji"],
            "escola": school_name,
            "contato": contact_name,
            "reply_preview": reply_text[:200],
            "resposta_subject": subject,
            "resposta_body": body,
            "resposta_reasoning": reasoning,
            "new_queue_id": new_queue_id,
            "action": "resposta_gerada",
        }

    def process_new_replies(self, limit: int = 10) -> Dict[str, Any]:
        """Processa todas as replies recentes que ainda nao foram respondidas.

        Busca emails com replied_at preenchido que nao tem resposta na fila.
        """
        try:
            # Buscar emails respondidos
            replied = db.client.table("approval_queue").select(
                "id,company_id,replied_at,follow_up_number"
            ).eq("status", "sent").not_.is_(
                "replied_at", "null"
            ).order("replied_at", desc=True).limit(50).execute().data or []

            if not replied:
                return {"processed": 0, "generated": 0, "ignored": 0, "details": []}

            processed = 0
            generated = 0
            ignored = 0
            details = []

            for msg in replied[:limit]:
                qid = msg["id"]
                company_id = msg.get("company_id")

                # Checar se ja tem resposta gerada para este reply
                try:
                    existing = db.client.table("approval_queue").select("id").eq(
                        "parent_id", qid
                    ).in_("status", ["pending", "approved", "sent"]).limit(1).execute()
                    if existing.data:
                        continue  # Ja tem resposta
                except Exception:
                    pass

                # Checar se ja processamos via memoria
                try:
                    from integrations.memory import memory
                    mems = memory.search(f"[AUTO_REPLY_PROCESSED:{qid}]")
                    if mems:
                        continue
                except Exception:
                    pass

                # Processar
                result = self.process_reply(qid)
                processed += 1

                if result and result.get("action") == "resposta_gerada":
                    generated += 1
                    details.append(result)
                    # Marcar como processado
                    try:
                        memory.remember(
                            content=f"[AUTO_REPLY_PROCESSED:{qid}] {result.get('intent', '?')}",
                            scope="company",
                            scope_id=company_id,
                            category="fact",
                            importance=5,
                            source="ialex",
                        )
                    except Exception:
                        pass
                else:
                    ignored += 1

            return {
                "processed": processed,
                "generated": generated,
                "ignored": ignored,
                "details": details,
            }
        except Exception as e:
            logger.error(f"process_new_replies erro: {e}")
            return {"processed": 0, "generated": 0, "ignored": 0, "error": str(e)[:200]}


# Singleton
reply_handler = ReplyHandler()
