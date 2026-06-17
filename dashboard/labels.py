"""labels.py — FONTE UNICA do vocabulario da UI (redesign v2 "Dia de Venda").

Regra de ouro do blueprint (§6): NENHUMA pagina escreve string de status na mao.
Todo mapeamento banco -> texto do usuario vive aqui. O IAlex recebe este
dicionario no system prompt — UI e WhatsApp falam a MESMA lingua.

Modulo PURO (sem streamlit) para ser testavel e importavel pelo brain/engine.
Render HTML (pills/badges/chips) fica em dashboard/theme.py, que importa daqui.

Referencias: docs/BLUEPRINT_V2.md §5/§6 · docs/SPEC_AGENDA_METAS.md
"""
from typing import Any, Dict, Optional, Tuple

# =============================================================================
# ETAPA DA ESCOLA (pill preenchida) — colapsa status tecnico + commercial_stage
# numa UNICA trilha visivel (blueprint §6). commercial_stage tem precedencia
# quando existe (e mais especifico/comercial que o status tecnico).
# =============================================================================

# status tecnico (companies.status) -> (label, cor hex)
_STATUS_TO_STAGE_LABEL: Dict[str, Tuple[str, str]] = {
    "raw":        ("Nova", "#90A4AE"),
    "filtered":   ("Avaliada", "#7E57C2"),
    "qualified":  ("Avaliada", "#7E57C2"),
    "enriched":   ("Pronta para contato", "#26A69A"),
    "contacted":  ("Contatada", "#1E88E5"),
    "responded":  ("Respondeu", "#F9A825"),
    "converted":  ("Cliente", "#2E7D32"),
    "rejected":   ("Perdida", "#B0BEC5"),
}

# commercial_stage (companies.commercial_stage) -> (label, cor hex)
_COMMERCIAL_TO_STAGE_LABEL: Dict[str, Tuple[str, str]] = {
    "prospectado": ("Pronta para contato", "#26A69A"),
    "contatado":   ("Contatada", "#1E88E5"),
    "respondeu":   ("Respondeu", "#F9A825"),
    "reuniao":     ("Em reuniao", "#FB8C00"),
    "proposta":    ("Proposta enviada", "#8E24AA"),
    "cliente":     ("Cliente", "#2E7D32"),
    "perdido":     ("Perdida", "#B0BEC5"),
}

# Etapas em ordem do funil (para kanban/funil da v2)
STAGE_ORDER = [
    "Nova", "Avaliada", "Pronta para contato", "Contatada",
    "Respondeu", "Em reuniao", "Proposta enviada", "Cliente", "Perdida",
]


def _clean(v: Any) -> str:
    """Normaliza qualquer valor para string limpa em minusculas.

    Trata None E NaN (float) como vazio: colunas de DataFrame vem como NaN
    quando nulas, e `NaN or ""` retorna o proprio NaN (truthy), quebrando
    `.strip()` com "'float' object has no attribute 'strip'".
    """
    if v is None or (isinstance(v, float) and v != v):  # v != v capta NaN
        return ""
    return str(v).strip().lower()


def school_stage(status: Optional[str], commercial_stage: Optional[str] = None) -> Tuple[str, str]:
    """(label, cor) da etapa VISIVEL da escola. commercial_stage > status."""
    cs = _clean(commercial_stage)
    if cs in _COMMERCIAL_TO_STAGE_LABEL:
        return _COMMERCIAL_TO_STAGE_LABEL[cs]
    st_ = _clean(status) or "raw"
    return _STATUS_TO_STAGE_LABEL.get(st_, ("Nova", "#90A4AE"))


def school_stage_label(status: Optional[str], commercial_stage: Optional[str] = None) -> str:
    return school_stage(status, commercial_stage)[0]


# =============================================================================
# PRIORIDADE (urgency) — UNICA nocao de prioridade em listas (blueprint §5).
# Thresholds documentados (v1.3): Agir agora 80+ · Quente 60-79 · Morno 40-59 ·
# Frio 0-39. SLA de resposta: 4h uteis (fixo — SPEC §8 item 13).
# =============================================================================

PRIORITY_TIERS: Dict[str, Dict[str, Any]] = {
    "CRITICAL": {"min": 80, "emoji": "🔴", "label": "Agir agora", "color": "#C62828"},
    "HOT":      {"min": 60, "emoji": "🟠", "label": "Quente",     "color": "#E65100"},
    "WARM":     {"min": 40, "emoji": "🟡", "label": "Morno",      "color": "#F9A825"},
    "COLD":     {"min": 0,  "emoji": "⚪", "label": "Frio",       "color": "#90A4AE"},
}

SLA_RESPOSTA_HORAS_UTEIS = 4


def priority_of(score: Optional[float]) -> str:
    """Tier ('CRITICAL'...'COLD') a partir do urgency_score 0-100."""
    s = float(score or 0)
    if s >= 80:
        return "CRITICAL"
    if s >= 60:
        return "HOT"
    if s >= 40:
        return "WARM"
    return "COLD"


def priority_label(tier_or_score) -> str:
    """'🔴 Agir agora' a partir do tier (str) ou do score (num)."""
    tier = tier_or_score if isinstance(tier_or_score, str) else priority_of(tier_or_score)
    t = PRIORITY_TIERS.get((tier or "COLD").upper(), PRIORITY_TIERS["COLD"])
    return f"{t['emoji']} {t['label']}"


# =============================================================================
# STATUS DE MENSAGEM (chip contornado — familia visual DISTINTA da pill de
# escola; blueprint §6). approval_queue.status (+ tracking).
# =============================================================================

MESSAGE_STATUS: Dict[str, Dict[str, str]] = {
    "pending":   {"icon": "⏳", "label": "Aguardando sua aprovacao", "color": "#F57F17"},
    "approved":  {"icon": "✅", "label": "Aprovada",                 "color": "#2E7D32"},
    "rejected":  {"icon": "✖",  "label": "Descartada",               "color": "#90A4AE"},
    "sent":      {"icon": "📤", "label": "Enviada",                  "color": "#1E88E5"},
    "delivered": {"icon": "📬", "label": "Entregue",                 "color": "#1E88E5"},
    "opened":    {"icon": "👁",  "label": "Aberta",                   "color": "#7E57C2"},
    "clicked":   {"icon": "🔗", "label": "Clicou no link",           "color": "#8E24AA"},
    "replied":   {"icon": "💬", "label": "Respondida",               "color": "#2E7D32"},
    "bounced":   {"icon": "⚠️", "label": "Nao entregue",             "color": "#C62828"},
}


def message_status_label(status: Optional[str], scheduled_hint: Optional[str] = None) -> str:
    """'⏳ Aguardando sua aprovacao' (com hora opcional p/ aprovadas agendadas)."""
    m = MESSAGE_STATUS.get(_clean(status) or "pending")
    if not m:
        return str(status or "?")
    label = f"{m['icon']} {m['label']}"
    if status == "approved" and scheduled_hint:
        label += f" — sai {scheduled_hint}"
    return label


# =============================================================================
# TERMOS canonicos (jargao tecnico -> linguagem de vendedor; blueprint §6)
# =============================================================================

TERMS: Dict[str, str] = {
    "enriquecer": "Buscar contatos",
    "qualificar": "Avaliar potencial",
    "approval_queue": "Caixa de saida",
    "template": "Modelo de mensagem",
    "peer_group": "Escolas semelhantes",
    "inep": "Codigo da escola (MEC)",
    "power_map": "Quem decide",
    "one_page_report": "Relatorio da escola",
    "descoberta": "Buscar escolas novas",
    "pipeline": "Preparar mensagens",
    "forcar": "Refazer mesmo se ja feito",
    "email_deduzido": "E-mail provavel (nao confirmado)",
    "amostra_nao_confiavel": "Poucos alunos fizeram ENEM — dado apenas indicativo",
}

# Potencial (P1/P2/P3 do ENEM -> estrelas; SO em Prospectar — blueprint §5)
POTENTIAL_STARS: Dict[str, str] = {"P1": "★★★", "P2": "★★☆", "P3": "★☆☆"}


# =============================================================================
# ATIVIDADES (agenda v2 — SPEC §1)
# =============================================================================

ACTIVITY_TYPES: Dict[str, Dict[str, str]] = {
    "responder":           {"emoji": "💬", "label": "Responder"},
    "follow_up":           {"emoji": "🔁", "label": "Follow-up"},
    "ligar":               {"emoji": "📞", "label": "Ligar"},
    "preparar_reuniao":    {"emoji": "📋", "label": "Preparar reuniao"},
    "registrar_resultado": {"emoji": "📝", "label": "Registrar resultado"},
    "aprovar_mensagens":   {"emoji": "✅", "label": "Aprovar mensagens"},
    "tarefa":              {"emoji": "✍️", "label": "Tarefa"},
}

ACTIVITY_SOURCE_BADGE: Dict[str, str] = {
    "auto": "🤖 auto", "ialex": "💬 IAlex", "manual": "✍️ manual",
}

ACTIVITY_RESOLUTIONS = (
    "manual", "auto_trabalho_detectado", "auto_gatilho_morto",
    "expirada", "lead_transferido",
)


def activity_label(type_: Optional[str]) -> str:
    t = ACTIVITY_TYPES.get(_clean(type_) or "tarefa")
    return f"{t['emoji']} {t['label']}" if t else str(type_ or "Tarefa")


# =============================================================================
# METAS — as 7 metricas oficiais com benchmark (blueprint §4 Resultados)
# =============================================================================

GOAL_METRICS: Dict[str, Dict[str, str]] = {
    "emails_enviados":       {"label": "E-mails enviados",     "benchmark": "40-60/vendedor/semana"},
    "respostas":             {"label": "Respostas",            "benchmark": "5-15% dos enviados"},
    "reunioes_realizadas":   {"label": "Reunioes realizadas",  "benchmark": "0,5-1/vendedor/semana"},
    "propostas":             {"label": "Propostas enviadas",   "benchmark": "1-2/vendedor/semana"},
    "clientes":              {"label": "Clientes novos",       "benchmark": "1-2/vendedor/mes"},
    "valor_fechado":         {"label": "Receita (MRR fechado)","benchmark": "R$ 2-8k por contrato"},
    "atividades_concluidas": {"label": "Atividades concluidas","benchmark": "6-10/dia saudavel"},
}


def goal_metric_label(metric: Optional[str]) -> str:
    g = GOAL_METRICS.get(_clean(metric))
    return g["label"] if g else str(metric or "?")


# =============================================================================
# MOTIVOS DE PERDA padronizados (higiene de pipeline — blueprint §4 Negocios)
# =============================================================================

LOSS_REASONS: Dict[str, str] = {
    "sem_orcamento": "Sem orcamento",
    "momento_errado": "Momento errado",
    "concorrente": "Concorrente",
    "sem_resposta": "Sem resposta (ghosting)",
    "inatividade": "Inatividade",
    "outro": "Outro",
}

# =============================================================================
# Resumo p/ o system prompt do IAlex (UI e WhatsApp falam a mesma lingua)
# =============================================================================

IALEX_VOCAB_PROMPT = (
    "VOCABULARIO DA PLATAFORMA (use SEMPRE estes nomes com o time): "
    "Prioridade = quem atender primeiro HOJE (🔴 Agir agora 80+ · 🟠 Quente 60-79 · "
    "🟡 Morno 40-59 · ⚪ Frio 0-39; e o urgency_tier). Potencial (★★★/★★/★) = quem "
    "prospectar primeiro, ANTES do contato (ENEM/P1-P3); nunca misture os dois. "
    "Etapas da escola: Nova → Avaliada → Pronta para contato → Contatada → Respondeu "
    "→ Em reuniao → Proposta enviada → Cliente (ou Perdida). Diga 'Buscar contatos' "
    "(nao 'enriquecer'), 'Avaliar potencial' (nao 'qualificar'), 'Modelo de mensagem' "
    "(nao 'template'), 'Caixa de saida' (nao 'fila de aprovacao'), 'Codigo da escola "
    "(MEC)' (nao 'INEP'), 'Escolas semelhantes' (nao 'peer group'). E-mails deduzidos "
    "sao 'provaveis (nao confirmados)'. SLA de resposta a lead: 4 horas uteis."
)
