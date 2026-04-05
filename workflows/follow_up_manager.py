"""
follow_up_manager.py - Gerencia sequencias automaticas e COMPORTAMENTAIS de follow-up.

Item 6 do roadmap: classifica cada mensagem enviada baseado no comportamento
do lead (abriu? clicou? respondeu? ficou em silencio?) e escolhe o estilo de
follow-up certo para cada caso, em vez de seguir uma sequencia fixa dia 3/7/14.

REGRA ABSOLUTA: Follow-ups SEMPRE passam pela approval_queue.
NUNCA envia sem aprovacao humana.

Tipos comportamentais (FOLLOW_UP_TYPES):
  - hot_click     → lead CLICOU em link → tom comercial direto, agenda agora
  - curious_open  → abriu 2+ vezes sem responder → valor adicional (curiosidade)
  - silent_open   → abriu 1x ha 3+ dias → lembrete gentil
  - revival       → silencio total 7+ dias (nem abriu) → angulo totalmente novo

Maximo de 3 follow-ups por empresa (exceto hot_click que sempre vale).
Integra com email_rag, memory e intent_detector (itens 1-4 do roadmap).
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
# Configuracao comportamental (Item 6 do roadmap)
# ===========================================================================

# Cada tipo de follow-up responde a um padrao comportamental observado no tracking.
# priority = 1 (maior) a 4 (menor) — hot_click sempre vence
FOLLOW_UP_TYPES: Dict[str, Dict[str, Any]] = {
    "hot_click": {
        "style": "commercial_direct",
        "label": "Lead clicou no link",
        "priority": 1,
        "min_days": 1,          # ja pode mandar no dia seguinte
        "emoji": "🔥",
    },
    "curious_open": {
        "style": "additional_value",
        "label": "Abriu 2+ vezes",
        "priority": 2,
        "min_days": 2,
        "emoji": "👀",
    },
    "silent_open": {
        "style": "gentle_reminder",
        "label": "Abriu 1x e sumiu",
        "priority": 3,
        "min_days": 3,
        "emoji": "📬",
    },
    "revival": {
        "style": "fresh_angle",
        "label": "Silencio total (nao abriu)",
        "priority": 4,
        "min_days": 7,
        "emoji": "🧊",
    },
}

MAX_FOLLOW_UPS: int = 3

# Backcompat: mantem estrutura antiga para qualquer codigo legado (nao e usado
# mais na logica nova, mas evita ImportError se alguem importou).
FOLLOW_UP_STEPS: List[Dict[str, Any]] = [
    {"number": 1, "days_after": 3, "style": "gentle_reminder", "label": "Lembrete gentil"},
    {"number": 2, "days_after": 7, "style": "additional_value", "label": "Valor adicional"},
    {"number": 3, "days_after": 14, "style": "last_attempt", "label": "Ultima tentativa"},
]


# ===========================================================================
# Funcoes auxiliares
# ===========================================================================

def _days_since(iso_str: Optional[str]) -> Optional[float]:
    """Retorna dias (float) desde um timestamp ISO. None se invalido."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        return None


def classify_follow_up_type(msg: Dict[str, Any]) -> Optional[str]:
    """Classifica comportamentalmente uma mensagem enviada e retorna o tipo
    de follow-up adequado — ou None se deve pular.

    Sinais usados (tracking do email):
        - replied_at: se houver → pula (intent_detector cuida)
        - bounced_at: se houver → pula (email quebrado)
        - clicked_at: sinal mais forte → hot_click
        - opened_at + tempo de abertura > 24h do envio → curious_open (reabriu)
        - opened_at unico → silent_open
        - sem abertura e >= 7 dias → revival
        - follow_up_number >= MAX (exceto hot_click) → pula

    Args:
        msg: dict com campos id, sent_at, opened_at, clicked_at, replied_at,
             bounced_at, follow_up_number

    Returns:
        Nome do tipo (chave de FOLLOW_UP_TYPES) ou None.
    """
    if msg.get("replied_at"):
        return None  # Intent detector assume
    if msg.get("bounced_at"):
        return None  # Email quebrado

    sent_at = msg.get("sent_at")
    days_sent = _days_since(sent_at) or 0
    current_fu = msg.get("follow_up_number", 0) or 0

    clicked = msg.get("clicked_at")
    opened = msg.get("opened_at")

    # --- hot_click: clicou, ainda pode manda mesmo se ja foi FU3 ---
    if clicked:
        days_click = _days_since(clicked) or 0
        if days_click >= FOLLOW_UP_TYPES["hot_click"]["min_days"]:
            return "hot_click"
        return None  # ainda quente demais, espera mais 1 dia

    # Se ja atingiu MAX e nao clicou → para
    if current_fu >= MAX_FOLLOW_UPS:
        return None

    # --- curious_open: reabriu depois de 24h (sinal de curiosidade latente) ---
    if opened and sent_at:
        days_open_after_sent = (_days_since(sent_at) or 0) - 0  # dias desde envio
        # Heuristica: se opened_at > sent_at por 24h, provavelmente reabriu
        try:
            sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
            open_dt = datetime.fromisoformat(opened.replace("Z", "+00:00"))
            hours_between = (open_dt - sent_dt).total_seconds() / 3600
            if hours_between > 24 and days_sent >= FOLLOW_UP_TYPES["curious_open"]["min_days"]:
                return "curious_open"
        except (ValueError, TypeError):
            pass

    # --- silent_open: abriu 1x (ha >= 3 dias) e sumiu ---
    if opened and days_sent >= FOLLOW_UP_TYPES["silent_open"]["min_days"]:
        return "silent_open"

    # --- revival: nunca abriu, silencio total >= 7 dias ---
    if not opened and days_sent >= FOLLOW_UP_TYPES["revival"]["min_days"]:
        return "revival"

    return None


def _get_style_for_type(fu_type: str) -> str:
    """Retorna o estilo de prompt para um tipo comportamental."""
    return FOLLOW_UP_TYPES.get(fu_type, {}).get("style", "gentle_reminder")


def _get_days_for_follow_up(follow_up_number: int) -> int:
    """Legacy: mantido para backcompat do dry-run. Nao usado na logica nova."""
    legacy = {1: 3, 2: 7, 3: 14}
    return legacy.get(follow_up_number, 999)


def _get_style_for_follow_up(follow_up_number: int) -> str:
    """Legacy: mantido para backcompat."""
    legacy = {1: "gentle_reminder", 2: "additional_value", 3: "last_attempt"}
    return legacy.get(follow_up_number, "gentle_reminder")


# ===========================================================================
# get_due_follow_ups: Encontra empresas que precisam de follow-up
# ===========================================================================

def get_due_follow_ups(
    limit: int = 20,
    allowed_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Encontra empresas prontas para follow-up usando classificacao COMPORTAMENTAL.

    Em vez da sequencia fixa dia 3/7/14, analisa o tracking de cada email
    enviado (opened_at, clicked_at, replied_at, bounced_at) e escolhe o tipo
    de follow-up adequado (hot_click, curious_open, silent_open, revival).

    Ordena por prioridade (hot_click primeiro, depois curious_open, etc).

    Args:
        limit: Numero maximo de follow-ups para gerar.
        allowed_types: Lista de tipos permitidos (None = todos).

    Returns:
        Lista de dicts com: company_id, contact_id, queue_id,
        next_follow_up_number, follow_up_type, tracking_signal,
        original_subject, original_body, sent_at, days_since_sent.
    """
    logger.info("Buscando follow-ups devidos (comportamental)", extra={
        "limit": limit, "allowed_types": allowed_types})

    try:
        # Buscar mensagens enviadas com qualquer tracking
        result = db.client.table("approval_queue").select(
            "id, company_id, contact_id, subject, body, "
            "follow_up_number, sent_at, opened_at, clicked_at, replied_at, "
            "bounced_at, parent_id"
        ).eq("status", "sent").not_.is_("sent_at", "null").order(
            "sent_at", desc=False
        ).limit(500).execute()

        sent_messages = result.data or []
    except Exception as e:
        logger.error("Erro ao buscar mensagens enviadas", extra={"error": str(e)})
        return []

    if not sent_messages:
        logger.info("Nenhuma mensagem enviada encontrada para follow-up")
        return []

    due_follow_ups: List[Dict[str, Any]] = []
    classification_stats: Dict[str, int] = {t: 0 for t in FOLLOW_UP_TYPES}
    classification_stats["skip"] = 0

    # Cache de empresas com mensagem pendente (evita N queries)
    pending_company_ids: set = set()
    try:
        pend = db.client.table("approval_queue").select("company_id").in_(
            "status", ["pending", "approved"]
        ).execute().data or []
        pending_company_ids = {p["company_id"] for p in pend if p.get("company_id")}
    except Exception as e:
        logger.debug(f"cache pendentes: {e}")

    for msg in sent_messages:
        if len(due_follow_ups) >= limit:
            break

        company_id = msg.get("company_id")
        contact_id = msg.get("contact_id")
        queue_id = msg.get("id")
        current_fu = msg.get("follow_up_number", 0) or 0
        sent_at_str = msg.get("sent_at")

        if not company_id or not sent_at_str:
            continue

        # 1) Classificacao comportamental
        fu_type = classify_follow_up_type(msg)
        if not fu_type:
            classification_stats["skip"] += 1
            continue

        # 2) Filtro por tipos permitidos (config)
        if allowed_types and fu_type not in allowed_types:
            classification_stats["skip"] += 1
            continue

        classification_stats[fu_type] += 1

        # 3) Escola com mensagem pendente/aprovada: pula (anti-duplicacao)
        if company_id in pending_company_ids:
            continue

        # 4) Verifica se ja existe follow-up para essa escola com numero >= proximo
        next_fu = current_fu + 1
        try:
            existing = db.client.table("approval_queue").select("id").eq(
                "company_id", company_id
            ).gte("follow_up_number", next_fu).limit(1).execute()
            if existing.data:
                continue
        except Exception:
            pass

        # 5) Calcular dias desde envio
        try:
            days_since_sent = int((_days_since(sent_at_str) or 0))
        except Exception:
            continue

        # 6) Encontrar mensagem raiz (se msg ja e follow-up, subir cadeia)
        original_subject = msg.get("subject", "")
        original_body = msg.get("body", "")
        if msg.get("parent_id"):
            try:
                root = msg
                visited = set()
                while root.get("parent_id") and root["parent_id"] not in visited:
                    visited.add(root["parent_id"])
                    parent = db.client.table("approval_queue").select(
                        "subject, body, parent_id"
                    ).eq("id", root["parent_id"]).single().execute()
                    if parent.data:
                        root = parent.data
                    else:
                        break
                original_subject = root.get("subject", original_subject)
                original_body = root.get("body", original_body)
            except Exception:
                pass

        # 7) Montar sinal de tracking (contexto para o prompt)
        tracking_signal = {
            "opened": bool(msg.get("opened_at")),
            "clicked": bool(msg.get("clicked_at")),
            "days_silent": days_since_sent,
            "current_fu_number": current_fu,
        }

        due_follow_ups.append({
            "company_id": company_id,
            "contact_id": contact_id,
            "queue_id": queue_id,
            "next_follow_up_number": next_fu,
            "follow_up_type": fu_type,
            "tracking_signal": tracking_signal,
            "original_subject": original_subject,
            "original_body": original_body,
            "sent_at": sent_at_str,
            "days_since_sent": days_since_sent,
        })

    # Ordenar por prioridade (hot_click primeiro)
    due_follow_ups.sort(key=lambda d: FOLLOW_UP_TYPES.get(
        d["follow_up_type"], {}).get("priority", 99))

    logger.info("Follow-ups devidos encontrados (comportamental)", extra={
        "total_sent_checked": len(sent_messages),
        "due_count": len(due_follow_ups),
        "stats": classification_stats,
    })

    return due_follow_ups


# ===========================================================================
# generate_follow_up: Gera mensagem de follow-up via Claude
# ===========================================================================

def _load_followup_prompt_template() -> Optional[str]:
    """Carrega o template de prompt para follow-ups."""
    from pathlib import Path
    path = Path(__file__).parent.parent / "prompts" / "followup_writer_prompt.txt"
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Template de follow-up nao encontrado: {e}")
        return None


# Instrucoes de estilo por tipo comportamental (injetadas no prompt)
STYLE_INSTRUCTIONS: Dict[str, str] = {
    "commercial_direct": (
        "LEAD CLICOU EM LINK DO EMAIL ANTERIOR — tem interesse real, esta quente.\n"
        "- Assunto: curto, direto, ex 'Horario para conversarmos?' ou 'Sobre o link que voce viu'\n"
        "- Abra reconhecendo discretamente ('Vi que teve a chance de dar uma olhada no material')\n"
        "- NAO pressione — proponha 2 horarios concretos proximos (ex: 'terca 14h ou quarta 10h')\n"
        "- Inclua o link de agendamento no final\n"
        "- Maximo 4 linhas. Foco em CONVERSAO imediata.\n"
        "- Tom comercial mas humano, como fala um consultor confiante."
    ),
    "additional_value": (
        "LEAD ABRIU VARIAS VEZES SEM RESPONDER — ha curiosidade, mas ainda ha duvida.\n"
        "- Assunto: comecar com 'Re: ' + assunto original (mantem o thread)\n"
        "- NAO mencione falta de resposta ou pressione\n"
        "- Compartilhe UM dado novo e especifico: case de escola similar, estatistica concreta ou beneficio pouco obvio\n"
        "- Conecte o dado com a realidade da escola (porte, niveis de ensino)\n"
        "- Tom consultivo, como quem quer ajudar a entender valor\n"
        "- Termine com pergunta leve ('Faz sentido conversarmos 15 minutos?') + link"
    ),
    "gentle_reminder": (
        "LEAD ABRIU 1 VEZ E SUMIU — pode ser que nao viu, pode estar ocupado.\n"
        "- Assunto: 'Re: ' + assunto original\n"
        "- Lembrete curto e gentil, 3 linhas no MAXIMO\n"
        "- 'Fernando aqui, so queria garantir que meu email chegou'\n"
        "- Reforce em UMA frase o beneficio principal\n"
        "- Pergunta simples: 'Tem 10 minutos essa semana para bater um papo?'\n"
        "- NAO repita argumentos do original, apenas uma linha de reforco"
    ),
    "fresh_angle": (
        "LEAD NAO ABRIU NENHUMA VEZ — o email original foi ignorado. Precisa angulo NOVO.\n"
        "- Assunto NOVO (NAO usar 'Re:') — criativo, provocativo, curioso\n"
        "- Exemplos: 'Um numero que me surpreendeu sobre [cidade]' ou 'Sobre seus alunos de 8o e 9o ano'\n"
        "- Mudanca completa de angulo: pergunta provocativa OU dado chocante sobre educacao\n"
        "- NAO mencione que tentou antes\n"
        "- Maximo 4 linhas, direto ao ponto\n"
        "- CTA suave: 'Se fizer sentido, posso enviar um resumo de 1 pagina?'"
    ),
    # Legacy (mantido para backcompat)
    "last_attempt": (
        "ULTIMA TENTATIVA — muda o angulo completamente, pergunta provocativa, maximo 4 linhas."
    ),
}


def _build_tracking_context(signal: Dict[str, Any]) -> str:
    """Formata o sinal de tracking como texto legivel para o prompt."""
    if not signal:
        return "- Sem dados de tracking disponiveis"
    lines = []
    if signal.get("clicked"):
        lines.append("- ✅ CLICOU no link do email anterior (sinal de interesse forte)")
    if signal.get("opened"):
        lines.append(f"- 👀 Abriu o email (possivelmente mais de uma vez)")
    else:
        lines.append("- 🧊 NAO abriu o email (silencio total)")
    days = signal.get("days_silent", 0)
    lines.append(f"- ⏱️  {days} dia(s) desde o envio original")
    current_fu = signal.get("current_fu_number", 0)
    if current_fu > 0:
        lines.append(f"- 🔄 Ja recebeu {current_fu} follow-up(s) anterior(es)")
    return "\n".join(lines)


def generate_follow_up(
    company_id: str,
    contact_id: Optional[str],
    original_queue_id: str,
    follow_up_number: int = 1,
    original_subject: str = "",
    original_body: str = "",
    follow_up_type: str = "silent_open",
    tracking_signal: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Gera follow-up COMPORTAMENTAL personalizado via Claude Sonnet.

    Usa o novo prompt unificado (prompts/followup_writer_prompt.txt) + RAG
    (exemplos de follow-ups bem-sucedidos) + memory (contexto persistente
    da escola) + o tipo comportamental classificado por classify_follow_up_type.

    A mensagem gerada vai para approval_queue com status='pending'.
    NUNCA envia sem aprovacao humana.

    Args:
        company_id: UUID da empresa.
        contact_id: UUID do contato (pode ser None).
        original_queue_id: UUID da mensagem na cadeia (pai imediato).
        follow_up_number: Numero do follow-up (1, 2 ou 3).
        original_subject: Assunto do email original (raiz da cadeia).
        original_body: Corpo do email original (raiz da cadeia).
        follow_up_type: tipo comportamental (hot_click, curious_open, silent_open, revival).
        tracking_signal: dict com opened, clicked, days_silent, current_fu_number.

    Returns:
        Dict com queue_id, subject, body, follow_up_type ou None se falhar.
    """
    logger.info("Gerando follow-up comportamental", extra={
        "company_id": company_id,
        "follow_up_number": follow_up_number,
        "follow_up_type": follow_up_type,
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

    # === Estilo comportamental ===
    style_key = _get_style_for_type(follow_up_type)
    style_instruction_text = STYLE_INSTRUCTIONS.get(
        style_key, STYLE_INSTRUCTIONS["gentle_reminder"]
    )
    fu_label = FOLLOW_UP_TYPES.get(follow_up_type, {}).get("label", follow_up_type)

    # === Tracking context ===
    tracking_context_text = _build_tracking_context(tracking_signal or {})

    # === RAG: exemplos de follow-ups bem-sucedidos ===
    rag_text = ""
    try:
        from integrations.email_rag import email_rag
        examples = email_rag.get_successful_followups(
            follow_up_type=follow_up_type,
            company_context={
                "school_size": company.get("school_size"),
                "admin_category": company.get("admin_category"),
                "city": company.get("city"),
                "state": company.get("state"),
            },
            limit=2,
        )
        if examples:
            rag_text = email_rag.format_for_prompt(examples)
            logger.info(f"RAG follow-up: {len(examples)} exemplos injetados")
    except Exception as e:
        logger.debug(f"RAG follow-up skip: {e}")
    if not rag_text:
        rag_text = "(Sem exemplos passados disponiveis — gere baseado apenas nas instrucoes de estilo)"

    # === Memory: contexto persistente da escola ===
    memory_text = ""
    try:
        from integrations.memory import memory
        mems = memory.get_for("company", company_id, limit=5)
        if mems:
            memory_text = memory.format_for_context(mems)
            logger.debug(f"Memory follow-up: {len(mems)} memorias injetadas")
    except Exception as e:
        logger.debug(f"Memory follow-up skip: {e}")
    if not memory_text:
        memory_text = "(Sem memorias registradas para esta escola)"

    # === Montar dados formatados ===
    school_data_text = (
        f"- Nome: {school_name}\n"
        f"- Cidade/UF: {city}/{state}\n"
        f"- Niveis de ensino: {education_levels}\n"
        f"- Score de qualificacao: {qualification_score}/100"
    )
    contact_data_text = (
        f"- Nome: {contact_name}\n"
        f"- Cargo: {contact_role}"
    )

    # === Carregar template ===
    template = _load_followup_prompt_template()
    if not template:
        logger.error("Template de follow-up indisponivel, abortando")
        return None

    # Truncar body original para nao estourar contexto
    original_body_trimmed = (original_body or "")[:800]

    prompt = (
        template
        .replace("{sender_name}", settings.YOUR_NAME)
        .replace("{sender_email}", settings.YOUR_EMAIL)
        .replace("{company_name}", getattr(settings, "COMPANY_NAME", "IAprendo"))
        .replace("{school_data}", school_data_text)
        .replace("{contact_data}", contact_data_text)
        .replace("{original_subject}", original_subject or "(sem assunto)")
        .replace("{original_body}", original_body_trimmed)
        .replace("{tracking_context}", tracking_context_text)
        .replace("{memory_context}", memory_text)
        .replace("{rag_examples}", rag_text)
        .replace("{follow_up_type}", follow_up_type)
        .replace("{follow_up_label}", fu_label)
        .replace("{style_instructions}", style_instruction_text)
        .replace("{meeting_link}", meeting_link)
    )

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

        # Assunto: "Re:" so para tipos que mantem o thread
        # (revival usa assunto NOVO; hot_click pode ir com ou sem Re:)
        keep_thread = follow_up_type in ("curious_open", "silent_open")
        if keep_thread and not subject.lower().startswith("re:"):
            subject = f"Re: {original_subject}"
        elif follow_up_type == "revival" and subject.lower().startswith("re:"):
            # Para revival, tirar o Re: se o LLM inseriu errado
            subject = subject[3:].strip(" :")

        # Limitar tamanho do assunto
        if len(subject) > 60:
            subject = subject[:57] + "..."

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Falha ao parsear resposta do follow-up", extra={
            "company_id": company_id, "error": str(e),
            "response_preview": response_text[:200]})
        return None

    # Anotacao do tipo comportamental no reasoning (sem precisar de migration)
    reasoning_tagged = f"[FU:{follow_up_type}] {reasoning}"

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
            logger.info("Follow-up comportamental na approval_queue", extra={
                "queue_id": new_queue_id,
                "company_id": company_id,
                "follow_up_number": follow_up_number,
                "follow_up_type": follow_up_type,
                "school_name": school_name})

            # Gravar tipo na memoria (substituto leve de nova coluna)
            try:
                from integrations.memory import memory
                memory.remember(
                    content=f"[FOLLOWUP_TYPE:{new_queue_id}:{follow_up_type}] {reasoning[:200]}",
                    scope="company",
                    scope_id=company_id,
                    category="insight",
                    importance=5,
                    source="follow_up_manager",
                )
            except Exception:
                pass

            return {
                "queue_id": new_queue_id,
                "company_id": company_id,
                "company_name": school_name,
                "contact_name": contact_name,
                "follow_up_number": follow_up_number,
                "follow_up_type": follow_up_type,
                "subject": subject,
                "body_preview": body[:150] + "..." if len(body) > 150 else body,
                "reasoning": reasoning_tagged,
                "style": style_key,
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

def run_follow_up_check(
    limit: int = 20,
    allowed_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Verifica e gera follow-ups COMPORTAMENTAIS devidos.

    Funcao principal chamada pelo scheduler ou pipeline diario.
    Classifica cada mensagem enviada por comportamento (hot_click, curious_open,
    silent_open, revival) e gera o follow-up adequado via Claude Sonnet.

    NUNCA envia sem aprovacao humana.

    Args:
        limit: Numero maximo de follow-ups para gerar nesta execucao.
        allowed_types: Tipos permitidos (None = todos).

    Returns:
        Dict com: generated, errors, by_type (contagem por tipo), details, etc.
    """
    logger.info("Iniciando verificacao de follow-ups comportamentais", extra={
        "limit": limit, "allowed_types": allowed_types})
    started_at = datetime.now(timezone.utc).isoformat()

    # 1. Buscar follow-ups devidos
    due = get_due_follow_ups(limit=limit, allowed_types=allowed_types)

    if not due:
        logger.info("Nenhum follow-up devido no momento")
        return {
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "generated": 0,
            "errors": 0,
            "skipped": 0,
            "due_found": 0,
            "by_type": {t: 0 for t in FOLLOW_UP_TYPES},
            "details": [],
        }

    generated = 0
    errors = 0
    skipped = 0
    by_type: Dict[str, int] = {t: 0 for t in FOLLOW_UP_TYPES}
    details: List[Dict[str, Any]] = []

    # 2. Gerar follow-ups (com tipo comportamental)
    for item in due:
        try:
            result = generate_follow_up(
                company_id=item["company_id"],
                contact_id=item.get("contact_id"),
                original_queue_id=item["queue_id"],
                follow_up_number=item["next_follow_up_number"],
                original_subject=item.get("original_subject", ""),
                original_body=item.get("original_body", ""),
                follow_up_type=item.get("follow_up_type", "silent_open"),
                tracking_signal=item.get("tracking_signal"),
            )

            if result:
                generated += 1
                fu_type = result.get("follow_up_type", "unknown")
                by_type[fu_type] = by_type.get(fu_type, 0) + 1
                details.append({
                    "status": "generated",
                    "company_id": item["company_id"],
                    "queue_id": result["queue_id"],
                    "follow_up_number": item["next_follow_up_number"],
                    "follow_up_type": fu_type,
                    "company_name": result.get("company_name", ""),
                    "subject": result.get("subject", ""),
                })
                logger.info("Follow-up comportamental gerado", extra={
                    "company_id": item["company_id"],
                    "follow_up_type": fu_type,
                    "queue_id": result["queue_id"]})
            else:
                errors += 1
                details.append({
                    "status": "error",
                    "company_id": item["company_id"],
                    "follow_up_number": item["next_follow_up_number"],
                    "follow_up_type": item.get("follow_up_type"),
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
                "follow_up_type": item.get("follow_up_type"),
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
        "by_type": by_type,
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

    # CLI output: ASCII safe (Windows terminal nao suporta emojis)
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.dry_run:
        due = get_due_follow_ups(limit=args.limit)
        print(f"\nFollow-ups devidos: {len(due)}")
        by_type: Dict[str, int] = {}
        for item in due:
            t = item.get("follow_up_type", "?")
            by_type[t] = by_type.get(t, 0) + 1
            print(f"  [{t}] Empresa: {item['company_id'][:8]}... | "
                  f"Dias: {item['days_since_sent']} | "
                  f"Assunto: {item['original_subject'][:40]}")
        print("\nPor tipo:")
        for t, n in by_type.items():
            print(f"  {t}: {n}")
    else:
        result = run_follow_up_check(limit=args.limit)
        print(f"\nFollow-ups gerados: {result['generated']}")
        print(f"Erros: {result['errors']}")
        print(f"Total devidos: {result.get('due_found', 0)}")
        print("\nPor tipo:")
        for t, n in result.get("by_type", {}).items():
            print(f"  {t}: {n}")
        for d in result["details"]:
            status = d["status"]
            cid = str(d.get("company_id", "?"))[:8]
            fu_type = d.get("follow_up_type", "?")
            print(f"  [{status}] Empresa {cid}... Tipo: {fu_type}")
