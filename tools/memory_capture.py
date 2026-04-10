"""
Memory Capture — regras que transformam eventos do sistema em memorias
persistentes que o IAlex pode usar depois para personalizar emails, follow-ups
e recomendar proximas acoes.

Todas as funcoes sao idempotentes: fazem `memory.search()` antes de gravar
para evitar duplicatas. Falhas sao silenciosas (log warning) — nunca derrubam
o fluxo principal que chamou.

Usado em 4 pontos:
- tools/email_tracker.py::_process_brevo_event (opens/clicks/replies)
- agents/qualifier.py::qualify_school (score alto + sinais)
- agent/brain.py::_handle_registrar_reuniao (resultado da reuniao)
- scripts/seed_census_memories.py (batch inicial de dados ricos)
"""
from typing import Any, Dict, Optional
from datetime import datetime

from integrations.memory import memory
from utils.logger import logger


def _already_exists(query: str, scope: str, scope_id: Optional[str]) -> bool:
    """Checa se ja existe memoria parecida (idempotencia)."""
    try:
        if not memory.is_available():
            return False
        # Busca textual + filtra por escopo
        results = memory.search(query, limit=3)
        for r in results:
            if r.get("scope") == scope and (scope == "global" or r.get("scope_id") == scope_id):
                return True
        return False
    except Exception:
        return False


def _safe_remember(
    content: str,
    scope: str,
    scope_id: Optional[str],
    category: str,
    importance: int,
    source: str,
    dedupe_query: Optional[str] = None,
) -> Optional[str]:
    """Wrapper que checa duplicata e chama memory.remember()."""
    try:
        # Checar duplicata usando trecho unico da mensagem
        dedupe_key = dedupe_query or content[:50]
        if _already_exists(dedupe_key, scope, scope_id):
            logger.debug(
                "memory_capture: duplicata ignorada",
                extra={"dedupe_key": dedupe_key, "scope": scope},
            )
            return None

        mem_id = memory.remember(
            content=content,
            scope=scope,
            scope_id=scope_id,
            category=category,
            importance=importance,
            source=source,
        )
        if mem_id:
            logger.info(
                "memory_capture: memoria gravada",
                extra={
                    "id": mem_id,
                    "scope": scope,
                    "category": category,
                    "importance": importance,
                    "source": source,
                },
            )
        return mem_id
    except Exception as e:
        logger.warning(f"memory_capture falhou: {e}")
        return None


# =============================================================================
# CAPTURE: EMAIL EVENTS (tools/email_tracker.py)
# =============================================================================

def capture_email_event(
    company_id: str,
    event_type: str,
    metadata: Optional[Dict[str, Any]] = None,
    contact_id: Optional[str] = None,  # noqa: ARG001 (aceito para forward compat)
    channel: str = "email",
) -> Optional[str]:
    """Captura eventos de tracking de email/WhatsApp e gera memoria quando relevante.

    Args:
        company_id: ID da escola.
        event_type: opened, clicked, replied, delivered, hardBounce, softBounce.
        metadata: {event_date, subject, reply_text, ...}.
        contact_id: aceito para compat com callers futuros (nao usado ainda).
        channel: "email" (default) ou "whatsapp". Altera textos e filtra
            eventos nao aplicaveis (opened/clicked nao existem em WhatsApp).

    Regras email:
    - delivered: NAO gera (ruido)
    - opened: insight "Abriu email em DATA (assunto SUBJECT)", imp=5
    - clicked: insight "Clicou em link do email em DATA", imp=7
    - replied: insight "RESPONDEU ao email em DATA — quente!", imp=9
    - hardBounce/softBounce: warning "Email bounce (TIPO)", imp=6

    Regras WhatsApp:
    - replied: insight "RESPONDEU ao WhatsApp em DATA — lead quente", imp=9
    - hardBounce/softBounce: warning "WhatsApp bounce", imp=6
    - opened/clicked/delivered: ignorados (nao existem)
    """
    if not company_id:
        return None

    metadata = metadata or {}
    event_date = metadata.get("event_date") or datetime.utcnow().isoformat()
    subject = (metadata.get("subject") or "").strip()[:60]

    # Normalizar data para formato curto
    try:
        if "T" in str(event_date):
            data_curta = str(event_date).split("T")[0]
        else:
            data_curta = str(event_date)[:10]
    except Exception:
        data_curta = "data desconhecida"

    subject_suffix = f' (assunto: "{subject}")' if subject else ""
    is_whatsapp = channel == "whatsapp"

    if event_type == "delivered":
        return None  # ruido

    # WhatsApp: opened/clicked nao existem — ignora silenciosamente
    if is_whatsapp and event_type in ("opened", "clicked"):
        return None

    if event_type == "opened":
        return _safe_remember(
            content=f"Abriu email em {data_curta}{subject_suffix}",
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=5,
            source="auto",
            dedupe_query=f"Abriu email em {data_curta}",
        )

    if event_type == "clicked":
        return _safe_remember(
            content=f"CLICOU em link do email em {data_curta}{subject_suffix} — interesse demonstrado.",
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=7,
            source="auto",
            dedupe_query=f"CLICOU em link do email em {data_curta}",
        )

    if event_type == "replied":
        if is_whatsapp:
            reply_preview = (metadata.get("reply_text") or "").strip()[:100]
            preview_suffix = f' — "{reply_preview}..."' if reply_preview else ""
            return _safe_remember(
                content=f"RESPONDEU ao WhatsApp em {data_curta}{preview_suffix} — lead quente, acionar manual.",
                scope="company",
                scope_id=company_id,
                category="insight",
                importance=9,
                source="auto",
                dedupe_query=f"RESPONDEU ao WhatsApp em {data_curta}",
            )
        return _safe_remember(
            content=f"RESPONDEU ao email em {data_curta}{subject_suffix} — lead quente, acionar manual.",
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=9,
            source="auto",
            dedupe_query=f"RESPONDEU ao email em {data_curta}",
        )

    if event_type in ("hardBounce", "softBounce"):
        tipo = "hard" if event_type == "hardBounce" else "soft"
        canal_label = "WhatsApp" if is_whatsapp else "Email"
        obs = "Verificar numero do contato." if is_whatsapp else "Verificar endereco do contato."
        return _safe_remember(
            content=f"{canal_label} teve bounce ({tipo}) em {data_curta}. {obs}",
            scope="company",
            scope_id=company_id,
            category="warning",
            importance=6,
            source="auto",
            dedupe_query=f"{canal_label} bounce ({tipo}) em {data_curta}",
        )

    return None


# =============================================================================
# CAPTURE: QUALIFIER RESULT (agents/qualifier.py)
# =============================================================================

def capture_qualifier_result(
    company: Dict[str, Any],
    qualify_result: Dict[str, Any],
) -> int:
    """Captura resultado do qualifier e gera memorias uteis.

    Regras:
    - score >= 85: insight com score + reasoning curto, imp=7
    - innovation_signals: cada sinal vira fact individual, imp=5
    - recommended_approach: preference com abordagem, imp=6

    Retorna quantas memorias foram criadas.
    """
    company_id = company.get("id")
    if not company_id:
        return 0

    criadas = 0
    score = qualify_result.get("score") or 0
    reasoning = (qualify_result.get("reasoning") or "").strip()[:200]

    # Score alto
    if score >= 85 and reasoning:
        if _safe_remember(
            content=f"Score alto ({score}/100): {reasoning}",
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=7,
            source="auto",
            dedupe_query=f"Score alto ({score}/100)",
        ):
            criadas += 1

    # Innovation signals — ate 3
    signals = qualify_result.get("innovation_signals") or []
    for signal in signals[:3]:
        if not signal or not isinstance(signal, str):
            continue
        signal_clean = signal.strip()[:150]
        if len(signal_clean) < 5:
            continue
        if _safe_remember(
            content=f"Sinal de inovacao: {signal_clean}",
            scope="company",
            scope_id=company_id,
            category="fact",
            importance=5,
            source="auto",
            dedupe_query=f"Sinal de inovacao: {signal_clean[:30]}",
        ):
            criadas += 1

    # Recommended approach
    approach = (qualify_result.get("recommended_approach") or "").strip()
    if approach and len(approach) > 15:
        if _safe_remember(
            content=f"Abordagem recomendada: {approach[:200]}",
            scope="company",
            scope_id=company_id,
            category="preference",
            importance=6,
            source="auto",
            dedupe_query=f"Abordagem recomendada: {approach[:30]}",
        ):
            criadas += 1

    return criadas


# =============================================================================
# CAPTURE: MEETING (brain._handle_registrar_reuniao)
# =============================================================================

def capture_meeting(
    company_id: str,
    meeting_data: Dict[str, Any],
) -> int:
    """Captura reunioes registradas e gera memorias.

    Regras:
    - outcome='interessado' ou 'fechado': insight "Reuniao POSITIVA", imp=9
    - outcome='follow_up': fact "Reuniao com follow-up pendente", imp=7
    - outcome='nao_interessado': warning "Reuniao: nao interessado (motivo)", imp=7
    - notes > 20 chars: fact "Nota da reuniao: ...", imp=6

    Retorna quantas memorias foram criadas.
    """
    if not company_id:
        return 0

    criadas = 0
    outcome = (meeting_data.get("outcome") or "").lower()
    notes = (meeting_data.get("notes") or "").strip()
    data_reuniao = meeting_data.get("scheduled_at", "")
    try:
        data_curta = str(data_reuniao).split("T")[0] if data_reuniao else datetime.now().strftime("%Y-%m-%d")
    except Exception:
        data_curta = "data desconhecida"

    if outcome in ("interessado", "fechado"):
        if _safe_remember(
            content=f"Reuniao POSITIVA em {data_curta} (resultado: {outcome}). Lead quente, priorizar.",
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=9,
            source="auto",
            dedupe_query=f"Reuniao POSITIVA em {data_curta}",
        ):
            criadas += 1

    elif outcome == "follow_up":
        if _safe_remember(
            content=f"Reuniao em {data_curta} — solicitou follow-up. Retomar contato.",
            scope="company",
            scope_id=company_id,
            category="fact",
            importance=7,
            source="auto",
            dedupe_query=f"Reuniao em {data_curta} — solicitou follow-up",
        ):
            criadas += 1

    elif outcome in ("nao_interessado", "perdido"):
        if _safe_remember(
            content=f"Reuniao em {data_curta}: escola NAO INTERESSADA. {notes[:100]}",
            scope="company",
            scope_id=company_id,
            category="warning",
            importance=7,
            source="auto",
            dedupe_query=f"Reuniao em {data_curta}: escola NAO INTERESSADA",
        ):
            criadas += 1

    # Notas relevantes — independente do outcome
    if notes and len(notes) > 20:
        if _safe_remember(
            content=f"Nota da reuniao {data_curta}: {notes[:300]}",
            scope="company",
            scope_id=company_id,
            category="fact",
            importance=6,
            source="auto",
            dedupe_query=f"Nota da reuniao {data_curta}",
        ):
            criadas += 1

    return criadas


# =============================================================================
# CAPTURE: CENSO (batch inicial)
# =============================================================================

def capture_census_insights(company: Dict[str, Any]) -> int:
    """Gera 1-3 memorias com insights do Censo 2025.

    Chamado 1x por escola (via scripts/seed_census_memories.py ou atualizacoes
    futuras). Idempotente.

    Regras:
    - Escala: se alvo >= 100, insight "X alunos em Fund AF+Medio (Y total)"
    - Nivel tec Alto: fact "Nivel tecnologico Alto: INFRA_LIST"
    - Rede: insight "Pertence a rede X (N unidades, M alunos alvo total)"
      (so se cnpj_mantenedora com 2+ unidades — requer query adicional)

    Retorna quantas memorias foram criadas.
    """
    company_id = company.get("id")
    if not company_id:
        return 0

    fonte = company.get("fonte_dados") or ""
    if fonte != "censo_2025":
        return 0

    criadas = 0

    fund_af = int(company.get("matriculas_fund_af") or 0)
    medio = int(company.get("matriculas_medio") or 0)
    alvo = fund_af + medio
    total_mat = int(company.get("total_matriculas") or 0)

    # 1. Escala
    if alvo >= 100:
        content = f"{alvo} alunos em Fund AF+Medio (segmento IAprendo). Total {total_mat} matriculas."
        if _safe_remember(
            content=content,
            scope="company",
            scope_id=company_id,
            category="insight",
            importance=7,
            source="auto",
            dedupe_query=f"{alvo} alunos em Fund AF+Medio",
        ):
            criadas += 1

    # 2. Nivel tecnologico Alto
    if (company.get("nivel_tecnologico") or "") == "Alto":
        infra = []
        if company.get("banda_larga"):
            infra.append("banda larga")
        if company.get("lab_informatica"):
            infra.append("lab de informatica")
        if company.get("internet_alunos"):
            infra.append("internet p/ alunos")
        if company.get("internet_aprendizagem"):
            infra.append("internet p/ aprendizagem")
        infra_str = ", ".join(infra) if infra else "infraestrutura completa"
        content = f"Nivel tecnologico Alto: {infra_str}. Readiness otima para IAprendo."
        if _safe_remember(
            content=content,
            scope="company",
            scope_id=company_id,
            category="fact",
            importance=6,
            source="auto",
            dedupe_query=f"Nivel tecnologico Alto: {infra_str[:30]}",
        ):
            criadas += 1

    # 3. Coordenacao pedagogica forte
    qt_coord = int(company.get("qt_coordenadores") or 0)
    if qt_coord >= 3:
        content = f"Escola tem {qt_coord} coordenadores pedagogicos — decisores tecnicos claros."
        if _safe_remember(
            content=content,
            scope="company",
            scope_id=company_id,
            category="fact",
            importance=6,
            source="auto",
            dedupe_query=f"{qt_coord} coordenadores pedagogicos",
        ):
            criadas += 1

    # 4. Rede educacional (requer query extra — deferida para o script seed
    # que ja carrega todas as escolas em memoria e pode agrupar por CNPJ)

    return criadas


def capture_network_insight(company_id: str, nome_rede: str, n_unidades: int, alvo_total: int) -> Optional[str]:
    """Gera memoria sobre rede educacional. Chamado pelo seed script."""
    if n_unidades < 2:
        return None
    content = f"Pertence a rede {nome_rede} ({n_unidades} unidades, {alvo_total} alunos alvo totais). Potencial de venda institucional."
    return _safe_remember(
        content=content,
        scope="company",
        scope_id=company_id,
        category="insight",
        importance=8,
        source="auto",
        dedupe_query=f"Pertence a rede {nome_rede}",
    )


# =============================================================================
# CAPTURE: CONTACT ENRICHMENT (contact_finder)
# =============================================================================

def capture_contact_enrichment(
    company_id: str,
    contact: Dict[str, Any],
) -> Optional[str]:
    """Gera memoria quando um diretor novo e descoberto via enrichment.

    Regras:
    - decision_maker_type='diretor' com email real: fact "Diretor identificado: NOME"
    """
    if not company_id or not contact:
        return None

    dm_type = contact.get("decision_maker_type") or ""
    if dm_type != "diretor":
        return None

    nome = (contact.get("full_name") or "").strip()
    if not nome:
        return None

    email = (contact.get("email") or "").strip()
    source = contact.get("source") or "enrichment"

    content = f"Diretor(a) identificado(a): {nome}"
    if email and "placeholder" not in email.lower() and "example" not in email.lower():
        content += f" ({email})"
    content += f" [fonte: {source}]"

    return _safe_remember(
        content=content,
        scope="company",
        scope_id=company_id,
        category="fact",
        importance=7,
        source="auto",
        dedupe_query=f"Diretor identificado: {nome}",
    )
