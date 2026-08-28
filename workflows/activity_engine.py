"""
Activity Engine — motor da Agenda do redesign v2 (F1).

Contrato (docs/SPEC_AGENDA_METAS.md): *a agenda NUNCA mente*. A cada execucao,
NESTA ordem (criar antes de varrer geraria atividade ja morta):
    1. sweep_auto_resolution()  — varredor: resolve auto-atividades cujo gatilho morreu
    2. reopen_snoozed()         — snoozed_until chegou -> open
    3. expire_overdue()         — TTL por regra (SPEC §1.6)
    4. create_from_rules()      — 8 regras (SPEC §1.3/§1.7), idempotentes por dedupe_key
    5. rollover_goals()         — dia 1: metas herdadas do mes anterior (SPEC §4.1)

Quem chama: agent/scheduler.py (30min + apos check_replies) e o load da Home (F2).
Idempotente por construcao (dedupe_key UNIQUE + varredor) — rodar 2x = rodar 1x.
"""
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger

try:
    from zoneinfo import ZoneInfo
    BRT = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover
    BRT = timezone(timedelta(hours=-3))

# ---------------------------------------------------------------------------
# Constantes operacionais (SPEC §0/§1)
# ---------------------------------------------------------------------------
BUSINESS_START, BUSINESS_END = 8, 18   # seg-sex, BRT

# Precedencia anti-colisao (menor = mais importante) — SPEC §1.7.
# Grupo "de contato": max 1 aberta por (escola, dono).
CONTACT_GROUP_PRECEDENCE = {"responder": 1, "hot_no_contact": 4, "follow_up": 5}

# TTL de expiracao por regra, em dias apos o due (SPEC §1.6). Ausente = nunca.
EXPIRE_TTL_DAYS = {"followup_due": 7, "sequencia_toques": 7, "hot_no_contact": 5}

AUTO_CAP_SOFT = 25   # teto de auto-atividades abertas/dono (prio 2-3)
AUTO_CAP_HARD = 40   # trava absoluta (acima: bug — para de criar e loga erro)

OUTBOUND_TYPES = ["email_sent", "whatsapp_sent", "linkedin_sent", "call_made"]
REPLY_TYPES = ["email_replied", "whatsapp_replied", "linkedin_replied"]
ADVANCED_STAGES = {"reuniao", "proposta", "cliente", "perdido"}

# Ultimo recurso, so se o YAML E o sender_profile falharem. Manter uma lista
# literal aqui envelhece em silencio (ficou sem o `charles` por meses e um
# usuario ausente daqui some dos seletores e das metas quando o fallback roda).
DEFAULT_USERS = ["fernando", "lizianne", "felipe", "charles"]


def _usernames_from_profiles() -> List[str]:
    """Usuarios via sender_profile (mesma fonte do YAML, com cache por mtime)."""
    try:
        from utils.sender_profile import list_profiles
        return [p.get("username") for p in list_profiles() if p.get("username")]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Helpers de tempo (BRT, horas uteis) — SPEC §0/§5.12
# ---------------------------------------------------------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_brt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT)


def parse_ts(iso_str: Optional[str]) -> Optional[datetime]:
    """ISO -> datetime aware (UTC). None se invalido."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def next_business_time(dt: datetime) -> datetime:
    """Rola para o proximo momento util (seg-sex 8-18 BRT). Fim de semana ->
    segunda 9h; depois das 18h -> proximo dia util 9h; antes das 8h -> 9h."""
    local = to_brt(dt)
    while True:
        if local.weekday() >= 5:  # sab/dom
            local = (local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        if local.hour >= BUSINESS_END:
            local = (local + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
            continue
        if local.hour < BUSINESS_START:
            local = local.replace(hour=9, minute=0, second=0, microsecond=0)
        return local.astimezone(timezone.utc)


def add_business_hours(dt: datetime, hours: float) -> datetime:
    """Soma horas UTEIS (SLA +4h: criada 16h -> due amanha 10h) — SPEC §1.3."""
    local = to_brt(next_business_time(dt))
    remaining = float(hours)
    while remaining > 0:
        end_of_day = local.replace(hour=BUSINESS_END, minute=0, second=0, microsecond=0)
        available = (end_of_day - local).total_seconds() / 3600.0
        if remaining <= available:
            local = local + timedelta(hours=remaining)
            remaining = 0
        else:
            remaining -= available
            local = to_brt(next_business_time(end_of_day + timedelta(minutes=1)))
    return local.astimezone(timezone.utc)


def business_day_at(dt: datetime, hour: int) -> datetime:
    """O dia (util) de dt as HH:00 BRT; rola fim de semana pra frente."""
    local = to_brt(dt).replace(hour=hour, minute=0, second=0, microsecond=0)
    while local.weekday() >= 5:
        local = local + timedelta(days=1)
    return local.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------
def all_usernames() -> List[str]:
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "users.yaml")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        users = list((data.get("credentials", {}) or {}).get("usernames", {}) or {})
        return users or _usernames_from_profiles() or list(DEFAULT_USERS)
    except Exception:
        return _usernames_from_profiles() or list(DEFAULT_USERS)


def admin_username() -> str:
    try:
        from utils.sender_profile import is_admin
        for u in all_usernames():
            if is_admin(u):
                return u
    except Exception:
        pass
    return "fernando"


def _is_away(username: str) -> bool:
    try:
        from integrations.agenda_config import agenda_config
        return agenda_config.is_away(username)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Consultas de apoio
# ---------------------------------------------------------------------------
def _last_outbound_at(company_id: str, after: Optional[datetime] = None) -> Optional[datetime]:
    """Timestamp do ultimo OUTBOUND da escola (qualquer socio — SPEC §1.4)."""
    try:
        q = db.client.table("interactions").select("created_at") \
            .eq("company_id", company_id).in_("type", OUTBOUND_TYPES) \
            .order("created_at", desc=True).limit(1)
        if after:
            q = q.gt("created_at", after.isoformat())
        rows = q.execute().data or []
        return parse_ts(rows[0]["created_at"]) if rows else None
    except Exception:
        return None


def _has_reply_after(company_id: str, after: datetime) -> bool:
    try:
        rows = db.client.table("interactions").select("id") \
            .eq("company_id", company_id).in_("type", REPLY_TYPES) \
            .gt("created_at", after.isoformat()).limit(1).execute().data or []
        return bool(rows)
    except Exception:
        return False


def _company(company_id: str) -> Dict[str, Any]:
    try:
        rows = db.client.table("companies").select(
            "id,name,owner_username,commercial_stage,status,urgency_tier,last_contacted_at"
        ).eq("id", company_id).limit(1).execute().data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def _open_contact_activities(company_id: str, owner: str) -> List[Dict[str, Any]]:
    """Atividades abertas do GRUPO DE CONTATO da (escola, dono) — SPEC §1.7."""
    try:
        return db.client.table("activities").select("id,type,auto_rule") \
            .eq("company_id", company_id).eq("owner_username", owner) \
            .in_("status", ["open", "snoozed"]) \
            .in_("type", list(CONTACT_GROUP_PRECEDENCE)).execute().data or []
    except Exception:
        return []


def _can_create(owner: str, priority: int, company_id: Optional[str],
                act_type: str) -> bool:
    """Tetos (25/40) + anti-colisao + away — SPEC §1.7/§5.2. Prio 1 fura o teto
    soft e nasce mesmo para ausente (resposta de lead nunca e silenciada)."""
    open_autos = db.count_open_activities(owner, auto_only=True)
    if open_autos >= AUTO_CAP_HARD:
        logger.error("activity_engine: trava absoluta de %s autos abertas atingida (%s)",
                     AUTO_CAP_HARD, owner)
        return False
    if priority > 1:
        if open_autos >= AUTO_CAP_SOFT:
            return False
        if _is_away(owner):
            return False
    if company_id and act_type in CONTACT_GROUP_PRECEDENCE:
        mine = CONTACT_GROUP_PRECEDENCE[act_type]
        for a in _open_contact_activities(company_id, owner):
            if CONTACT_GROUP_PRECEDENCE.get(a.get("type"), 99) <= mine:
                return False  # ja existe cobranca de precedencia >= : nao nasce
    return True


def _resolve_lower_precedence(company_id: str, owner: str, new_type: str) -> None:
    """Nasceu cobranca mais importante -> dismissa as menos importantes (§1.7)."""
    mine = CONTACT_GROUP_PRECEDENCE.get(new_type, 99)
    for a in _open_contact_activities(company_id, owner):
        if CONTACT_GROUP_PRECEDENCE.get(a.get("type"), 99) > mine:
            db.dismiss_activity(a["id"], "system", "auto_gatilho_morto")


# ---------------------------------------------------------------------------
# 1) VARREDOR de auto-resolucao (SPEC §1.4) — a regra mais importante
# ---------------------------------------------------------------------------
def sweep_auto_resolution(now: Optional[datetime] = None) -> int:
    now = now or now_utc()
    resolved = 0
    try:
        autos = db.client.table("activities").select("*") \
            .eq("source", "auto").in_("status", ["open", "snoozed"]) \
            .limit(500).execute().data or []
    except Exception as e:
        logger.error("sweep: falha ao listar autos: %s", str(e)[:150])
        return 0

    for act in autos:
        try:
            if _sweep_one(act, now):
                resolved += 1
        except Exception as e:
            logger.warning("sweep: falha em %s: %s", act.get("id"), str(e)[:120])
    return resolved


def _sweep_one(act: Dict[str, Any], now: datetime) -> bool:
    a_id = act["id"]
    a_type = act.get("type")
    company_id = act.get("company_id")
    created = parse_ts(act.get("created_at")) or now

    if a_type == "responder":
        if company_id and _last_outbound_at(company_id, after=created):
            return db.complete_activity(a_id, "system", "auto_trabalho_detectado")
        return False

    if a_type == "follow_up":
        if not company_id:
            return False
        if _last_outbound_at(company_id, after=created):
            return db.complete_activity(a_id, "system", "auto_trabalho_detectado")
        if _has_reply_after(company_id, created):
            return db.dismiss_activity(a_id, "system", "auto_gatilho_morto")
        comp = _company(company_id)
        if (comp.get("commercial_stage") or "").lower() in ADVANCED_STAGES:
            return db.dismiss_activity(a_id, "system", "auto_gatilho_morto")
        return False

    if a_type == "preparar_reuniao":
        meeting = _meeting(act.get("meeting_id"))
        if not meeting:
            return db.dismiss_activity(a_id, "system", "auto_gatilho_morto")
        if meeting.get("status") in ("cancelled", "no_show"):
            return db.dismiss_activity(a_id, "system", "auto_gatilho_morto")
        sched = parse_ts(meeting.get("scheduled_at"))
        # remarcada: a chave da prep inclui a data — se divergiu, esta morta
        if sched and act.get("dedupe_key") and sched.date().isoformat() not in act["dedupe_key"]:
            return db.dismiss_activity(a_id, "system", "auto_gatilho_morto")
        if sched and sched < now:  # reuniao ja passou com prep aberta
            return db.dismiss_activity(a_id, "system", "expirada")
        return False

    if a_type == "registrar_resultado":
        meeting = _meeting(act.get("meeting_id"))
        if meeting and meeting.get("outcome"):
            return db.complete_activity(a_id, "system", "auto_trabalho_detectado")
        return False

    if a_type == "aprovar_mensagens":
        owner = act.get("owner_username")
        n = _pending_count(owner)
        if n == 0:
            return db.complete_activity(a_id, "system", "auto_trabalho_detectado")
        # atualiza o titulo in-place (nunca cria outra no dia) — SPEC §1.4
        title = f"Aprovar {n} mensagens paradas"
        if act.get("title") != title:
            try:
                db.client.table("activities").update({"title": title}).eq("id", a_id).execute()
            except Exception:
                pass
        return False

    if a_type == "ligar" or a_type == "tarefa":
        if act.get("source") in ("manual", "ialex"):
            return False  # NUNCA auto-resolve manuais (SPEC §1.4)
        # hot_no_contact usa type 'ligar'? nao — usa auto_rule; tratar abaixo
        return False

    return False


def _meeting(meeting_id: Optional[str]) -> Dict[str, Any]:
    if not meeting_id:
        return {}
    try:
        rows = db.client.table("meetings").select("id,status,outcome,scheduled_at") \
            .eq("id", meeting_id).limit(1).execute().data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def _pending_count(owner: Optional[str]) -> int:
    try:
        q = db.client.table("approval_queue").select("id", count="exact").eq("status", "pending")
        if owner:
            q = q.eq("created_by", owner)
        return int(q.execute().count or 0)
    except Exception:
        return 0


# hot_no_contact e do grupo de contato mas usa type proprio na criacao; o
# varredor o trata via follow_up-like:
def _sweep_hot(act: Dict[str, Any], now: datetime) -> bool:  # pragma: no cover
    return False


# ---------------------------------------------------------------------------
# 2) Reabrir snoozed vencidos
# ---------------------------------------------------------------------------
def reopen_snoozed(now: Optional[datetime] = None) -> int:
    now = now or now_utc()
    try:
        rows = db.client.table("activities").select("id") \
            .eq("status", "snoozed").lte("snoozed_until", now.isoformat()) \
            .limit(200).execute().data or []
        for r in rows:
            db.client.table("activities").update(
                {"status": "open", "snoozed_until": None}
            ).eq("id", r["id"]).execute()
        return len(rows)
    except Exception as e:
        logger.error("reopen_snoozed: %s", str(e)[:150])
        return 0


# ---------------------------------------------------------------------------
# 3) Expiracao por TTL (SPEC §1.6) — so auto; manuais NUNCA expiram
# ---------------------------------------------------------------------------
def expire_overdue(now: Optional[datetime] = None) -> int:
    now = now or now_utc()
    expired = 0
    try:
        autos = db.client.table("activities").select("id,auto_rule,due_at,type,owner_username") \
            .eq("source", "auto").eq("status", "open") \
            .lt("due_at", now.isoformat()).limit(300).execute().data or []
    except Exception:
        return 0
    today_brt = to_brt(now).date()
    for act in autos:
        rule = act.get("auto_rule") or ""
        due = parse_ts(act.get("due_at"))
        if not due:
            continue
        if act.get("type") == "aprovar_mensagens":
            # diaria por construcao: expira no fim do dia BRT do due
            if to_brt(due).date() < today_brt:
                if db.dismiss_activity(act["id"], "system", "expirada"):
                    expired += 1
            continue
        ttl = EXPIRE_TTL_DAYS.get(rule)
        if ttl and (now - due) > timedelta(days=ttl):
            if db.dismiss_activity(act["id"], "system", "expirada"):
                expired += 1
    return expired


# ---------------------------------------------------------------------------
# 4) Criacao por regras (SPEC §1.3) — idempotente por dedupe_key
# ---------------------------------------------------------------------------
def _create(owner: str, act_type: str, title: str, due_at: datetime,
            priority: int, rule: str, dedupe_key: str,
            company_id: Optional[str] = None, details: str = "",
            meeting_id: Optional[str] = None,
            sequence_step: Optional[int] = None) -> bool:
    if not _can_create(owner, priority, company_id, act_type):
        return False
    created = db.create_activity({
        "owner_username": owner, "type": act_type, "title": title[:300],
        "details": details or None, "due_at": due_at.isoformat(),
        "priority": priority, "source": "auto", "auto_rule": rule,
        "dedupe_key": dedupe_key[:200], "company_id": company_id,
        "meeting_id": meeting_id, "sequence_step": sequence_step,
        "created_by": "system",
    })
    if created and company_id and act_type in CONTACT_GROUP_PRECEDENCE:
        _resolve_lower_precedence(company_id, owner, act_type)
    return bool(created)


def create_from_rules(now: Optional[datetime] = None) -> int:
    now = now or now_utc()
    total = 0
    for fn in (_rule_reply_received, _rule_meeting_prep, _rule_meeting_outcome,
               _rule_hot_no_contact, _rule_approvals_aging,
               _rule_sequencia_toques, _rule_goal_reminder):
        try:
            total += fn(now)
        except Exception as e:
            logger.error("create_from_rules %s: %s", fn.__name__, str(e)[:150])
    return total


def _rule_reply_received(now: datetime) -> int:
    """R1: resposta sem tratamento -> 'Responder {escola}' prio 1, +4h uteis.
    Lead sem dono -> nasce pro admin (SPEC §5.13)."""
    created = 0
    since = (now - timedelta(days=7)).isoformat()
    try:
        replies = db.client.table("interactions").select("id,company_id,created_at") \
            .in_("type", REPLY_TYPES).gte("created_at", since) \
            .order("created_at", desc=True).limit(200).execute().data or []
    except Exception:
        return 0
    seen = set()
    for rep in replies:
        cid = rep.get("company_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        rep_at = parse_ts(rep.get("created_at")) or now
        if _last_outbound_at(cid, after=rep_at):
            continue  # ja tratada (outbound depois da resposta)
        comp = _company(cid)
        owner = comp.get("owner_username")
        title = f"Responder {comp.get('name', 'escola')}"
        if not owner:
            owner = admin_username()
            title = f"(lead sem dono) {title}"
        if _create(owner, "responder", title,
                   add_business_hours(rep_at, 4), 1, "reply_received",
                   f"responder:{cid}:{rep['id']}", company_id=cid,
                   details="Respondeu sua mensagem — SLA de 4h uteis."):
            created += 1
    return created


def _rule_meeting_prep(now: datetime) -> int:
    """R3: reuniao nas proximas 24h -> 'Preparar reuniao' (due = inicio - 24h,
    min agora+1h)."""
    created = 0
    until = (now + timedelta(hours=24)).isoformat()
    try:
        meets = db.client.table("meetings").select("id,company_id,scheduled_at,title,owner_username") \
            .eq("status", "scheduled").gte("scheduled_at", now.isoformat()) \
            .lte("scheduled_at", until).limit(50).execute().data or []
    except Exception:
        return 0
    for m in meets:
        sched = parse_ts(m.get("scheduled_at"))
        if not sched:
            continue
        comp = _company(m.get("company_id")) if m.get("company_id") else {}
        owner = m.get("owner_username") or comp.get("owner_username") or admin_username()
        due = max(sched - timedelta(hours=24), now + timedelta(hours=1))
        if _create(owner, "preparar_reuniao",
                   f"Preparar reuniao com {comp.get('name') or m.get('title') or 'lead'}",
                   due, 2, "meeting_prep",
                   f"prep:{m['id']}:{sched.date().isoformat()}",
                   company_id=m.get("company_id"), meeting_id=m["id"],
                   details="Abra o Relatorio da escola + ultimas interacoes."):
            created += 1
    return created


def _rule_meeting_outcome(now: datetime) -> int:
    """R4: reuniao passada sem resultado -> 'Registrar resultado' (+2h uteis)."""
    created = 0
    try:
        meets = db.client.table("meetings").select("id,company_id,scheduled_at,owner_username") \
            .in_("status", ["scheduled", "completed"]).is_("outcome", "null") \
            .lt("scheduled_at", (now - timedelta(hours=1)).isoformat()) \
            .gte("scheduled_at", (now - timedelta(days=30)).isoformat()) \
            .limit(50).execute().data or []
    except Exception:
        return 0
    for m in meets:
        comp = _company(m.get("company_id")) if m.get("company_id") else {}
        owner = m.get("owner_username") or comp.get("owner_username") or admin_username()
        sched = parse_ts(m.get("scheduled_at")) or now
        if _create(owner, "registrar_resultado",
                   f"Registrar resultado da reuniao — {comp.get('name', 'lead')}",
                   add_business_hours(sched, 2), 2, "meeting_outcome",
                   f"outcome:{m['id']}", company_id=m.get("company_id"),
                   meeting_id=m["id"]):
            created += 1
    return created


def _rule_hot_no_contact(now: datetime) -> int:
    """R5: lead Quente/Agir-agora sem contato ha >5d -> 'Retomar X — esfriando'."""
    created = 0
    cutoff = (now - timedelta(days=5)).isoformat()
    try:
        comps = db.client.table("companies").select(
            "id,name,owner_username,last_contacted_at,urgency_tier"
        ).in_("urgency_tier", ["CRITICAL", "HOT"]) \
         .lt("last_contacted_at", cutoff).limit(50).execute().data or []
    except Exception:
        return 0
    for c in comps:
        owner = c.get("owner_username") or admin_username()
        last = parse_ts(c.get("last_contacted_at"))
        key_date = last.date().isoformat() if last else to_brt(now).date().isoformat()
        if _create(owner, "follow_up",
                   f"Retomar {c.get('name', 'escola')} — esfriando",
                   business_day_at(now, 14), 1, "hot_no_contact",
                   f"hot:{c['id']}:{key_date}", company_id=c["id"],
                   details="Lead quente sem contato ha 5+ dias."):
            created += 1
    return created


def _rule_approvals_aging(now: datetime) -> int:
    """R6: fila pendente >24h -> 1 atividade agregada/dono/dia."""
    created = 0
    cutoff = (now - timedelta(hours=24)).isoformat()
    try:
        rows = db.client.table("approval_queue").select("id,created_by") \
            .eq("status", "pending").lt("created_at", cutoff).limit(500).execute().data or []
    except Exception:
        return 0
    if not rows:
        return 0
    by_owner: Dict[str, int] = {}
    for r in rows:
        owner = r.get("created_by") or admin_username()
        by_owner[owner] = by_owner.get(owner, 0) + 1
    day = to_brt(now).date().isoformat()
    for owner, n in by_owner.items():
        if _create(owner, "aprovar_mensagens",
                   f"Aprovar {n} mensagens paradas",
                   business_day_at(now, 9), 2, "approvals_aging",
                   f"approvals:{owner}:{day}",
                   details="Mensagens aguardando aprovacao ha mais de 24h."):
            created += 1
    return created


def _rule_sequencia_toques(now: datetime) -> int:
    """R7 (v1.3): cadencia estruturada com break-up. Toque N+1 so nasce apos o
    envio REAL do toque N (relogio conta de interactions, nao do plano):
        ultimo outbound ha >=3d sem resposta -> toque 2 (canal ALTERNADO)
        ha >=7d -> toque 3 · ha >=10d apos toque 3 -> 'Decidir: arquivar?'
    Nao nasce se ja ha mensagem pendente na fila para a escola (a cobranca
    certa nesse caso e aprovar, nao gerar)."""
    created = 0
    try:
        comps = db.client.table("companies").select(
            "id,name,owner_username,commercial_stage,status,last_contacted_at"
        ).eq("status", "contacted").not_.is_("last_contacted_at", "null") \
         .limit(300).execute().data or []
    except Exception:
        return 0
    for c in comps:
        if (c.get("commercial_stage") or "").lower() in ADVANCED_STAGES:
            continue
        cid = c["id"]
        last_out = _last_outbound_at(cid)
        if not last_out:
            continue
        if _has_reply_after(cid, last_out):
            continue  # respondeu: a cadencia morre (R1 cuida)
        if _has_pending_message(cid):
            continue
        days = (now - last_out).days
        owner = c.get("owner_username") or admin_username()
        name = c.get("name", "escola")
        last_channel = _last_outbound_channel(cid)
        alt = "WhatsApp" if last_channel == "email" else "e-mail"
        if days >= 10:
            step, title, atype = 4, f"Decidir: arquivar {name}?", "tarefa"
            details = "3 toques sem resposta — retomar ou arquivar com motivo (break-up)."
        elif days >= 7:
            step, title, atype = 3, f"Toque 3 — {name} (ultima tentativa, {alt})", "follow_up"
            details = f"2 toques sem resposta; alterne o canal ({alt})."
        elif days >= 3:
            step, title, atype = 2, f"Toque 2 — {name} (canal alternado: {alt})", "follow_up"
            details = f"Sem resposta ha {days}d; tente por {alt}."
        else:
            continue
        if _create(owner, atype, title, business_day_at(now, 10), 2,
                   "sequencia_toques", f"seq:{cid}:{step}", company_id=cid,
                   details=details, sequence_step=step):
            created += 1
    return created


def _last_outbound_channel(company_id: str) -> str:
    try:
        rows = db.client.table("interactions").select("channel") \
            .eq("company_id", company_id).in_("type", OUTBOUND_TYPES) \
            .order("created_at", desc=True).limit(1).execute().data or []
        return (rows[0].get("channel") or "email") if rows else "email"
    except Exception:
        return "email"


def _has_pending_message(company_id: str) -> bool:
    try:
        rows = db.client.table("approval_queue").select("id") \
            .eq("company_id", company_id).eq("status", "pending") \
            .limit(1).execute().data or []
        return bool(rows)
    except Exception:
        return False


def _rule_goal_reminder(now: datetime) -> int:
    """R8: dia >=25 e mes seguinte sem metas -> lembrete pro admin (SPEC §4.1)."""
    local = to_brt(now)
    if local.day < 25:
        return 0
    nxt = (local.replace(day=1) + timedelta(days=32)).replace(day=1)
    if db.list_goals(period_start=nxt.date().isoformat()):
        return 0
    month_label = f"{nxt.year}-{nxt.month:02d}"
    if _create(admin_username(), "tarefa",
               f"🎯 Definir metas de {month_label}",
               business_day_at(now, 9), 2, "goal_reminder",
               f"goalrem:{month_label}",
               details="O dialog de metas mostra a calibracao historica; sem acao, "
                       "as metas atuais serao herdadas no dia 1."):
        return 1
    return 0


# ---------------------------------------------------------------------------
# 5) Rollover de metas (dia 1 — SPEC §4.1)
# ---------------------------------------------------------------------------
def rollover_goals(now: Optional[datetime] = None) -> int:
    now = now or now_utc()
    local = to_brt(now)
    if local.day != 1:
        return 0
    this_start = local.date().replace(day=1)
    prev_start = (this_start - timedelta(days=1)).replace(day=1)
    prev_goals = db.list_goals(period_start=prev_start.isoformat())
    if not prev_goals:
        return 0
    current = {(g["username"], g["metric"])
               for g in db.list_goals(period_start=this_start.isoformat())}
    rolled = 0
    for g in prev_goals:
        key = (g["username"], g["metric"])
        if key in current:
            continue
        if db.upsert_goal(g["username"], g["metric"], this_start.isoformat(),
                          float(g.get("target") or 0), "system", reason="herdada"):
            rolled += 1
    if rolled:
        logger.info("rollover_goals: %s metas herdadas para %s", rolled, this_start)
    return rolled


# ---------------------------------------------------------------------------
# Entrada unica
# ---------------------------------------------------------------------------
def run_engine(now: Optional[datetime] = None) -> Dict[str, int]:
    """Executa o ciclo completo (ordem da SPEC §0). Idempotente."""
    now = now or now_utc()
    summary = {
        "swept": sweep_auto_resolution(now),
        "reopened": reopen_snoozed(now),
        "expired": expire_overdue(now),
        "created": create_from_rules(now),
        "goals_rolled": rollover_goals(now),
    }
    logger.info("activity_engine: %s", summary)
    return summary


if __name__ == "__main__":  # execucao manual: python -m workflows.activity_engine
    print(run_engine())
