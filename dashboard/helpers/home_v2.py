"""home_v2 — logica da Home "Hoje" (F2 do redesign v2), FORA da pagina.

Regra da SPEC §12-B: logica em helpers testaveis; a pagina so renderiza.
A agenda e a fonte da verdade dos numeros do dia (atividades 'responder'
abertas = respostas a tratar; SLA = idade da atividade).
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from workflows.activity_engine import now_utc, parse_ts, to_brt

# Etapas que contam como "em conversa" (disciplina de foco — blueprint §2.1)
IN_CONVERSATION_STAGES = {"contatado", "respondeu", "reuniao", "proposta"}
IN_CONVERSATION_STATUSES = {"contacted", "responded"}


def agenda_groups(owner: str, now: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Agrupa as atividades abertas do dono: atrasadas / hoje / amanha / proximas.
    Ordem dentro do grupo ja vem do db (prioridade, due, criacao — SPEC §1.8)."""
    now = now or now_utc()
    today = to_brt(now).date()
    tomorrow = today + timedelta(days=1)
    groups: Dict[str, List[Dict[str, Any]]] = {
        "atrasadas": [], "hoje": [], "amanha": [], "proximas": []}
    for a in db.list_activities(owner=owner, status=["open"], limit=200):
        due = parse_ts(a.get("due_at"))
        if not due:
            continue
        d = to_brt(due).date()
        if due < now:
            groups["atrasadas"].append(a)
        elif d == today:
            groups["hoje"].append(a)
        elif d == tomorrow:
            groups["amanha"].append(a)
        else:
            groups["proximas"].append(a)
    return groups


def day_numbers(owner: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Os 3 numeros do dia (calculados AO VIVO) + alertas de SLA."""
    now = now or now_utc()
    g = agenda_groups(owner, now)
    today_acts = g["atrasadas"] + g["hoje"]

    # respostas a tratar = atividades 'responder' abertas (a agenda e a verdade)
    respostas = [a for a in today_acts if a.get("type") == "responder"]
    oldest_hours = 0.0
    for a in respostas:
        created = parse_ts(a.get("created_at"))
        if created:
            oldest_hours = max(oldest_hours, (now - created).total_seconds() / 3600)

    pendentes, aging = 0, 0
    try:
        pendentes = int(db.client.table("approval_queue").select("id", count="exact")
                        .eq("status", "pending").execute().count or 0)
        aging = int(db.client.table("approval_queue").select("id", count="exact")
                    .eq("status", "pending")
                    .lt("created_at", (now - timedelta(hours=24)).isoformat())
                    .execute().count or 0)
    except Exception:
        pass

    return {
        "atividades_hoje": len(today_acts),
        "atrasadas": len(g["atrasadas"]),
        "prio1": sum(1 for a in today_acts if a.get("priority") == 1),
        "aprovacoes_pendentes": pendentes,
        "aprovacoes_aging": aging,
        "respostas_novas": len(respostas),
        "resposta_mais_antiga_h": round(oldest_hours, 1),
        "sobrecarga": len(g["hoje"]) + len(g["atrasadas"]) > 12,
    }


def em_conversa(owner: str) -> int:
    """Leads ativos do vendedor (teto de foco — blueprint §2.1)."""
    try:
        rows = db.client.table("companies").select("status,commercial_stage") \
            .eq("owner_username", owner).limit(1000).execute().data or []
        n = 0
        for r in rows:
            cs = (r.get("commercial_stage") or "").lower()
            st_ = (r.get("status") or "").lower()
            if cs in IN_CONVERSATION_STAGES or (not cs and st_ in IN_CONVERSATION_STATUSES):
                n += 1
        return n
    except Exception:
        return 0


def hot_leads(limit: int = 3) -> List[Dict[str, Any]]:
    """Leads 'Agir agora'/Quente pro card lateral."""
    try:
        return db.client.table("companies").select(
            "id,name,urgency_tier,urgency_score,owner_username,last_contacted_at"
        ).in_("urgency_tier", ["CRITICAL", "HOT"]) \
         .order("urgency_score", desc=True).limit(limit).execute().data or []
    except Exception:
        return []


def reunioes_24h(owner: Optional[str] = None,
                 now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = now or now_utc()
    try:
        q = db.client.table("meetings").select(
            "id,company_id,scheduled_at,title,meeting_type,owner_username") \
            .eq("status", "scheduled") \
            .gte("scheduled_at", now.isoformat()) \
            .lte("scheduled_at", (now + timedelta(hours=24)).isoformat()) \
            .order("scheduled_at")
        if owner:
            q = q.eq("owner_username", owner)
        return q.limit(5).execute().data or []
    except Exception:
        return []


def minhas_metas(owner: str, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Metas do mes com realizado AO VIVO (pro anel da Home e Resultados)."""
    now = now or now_utc()
    start = to_brt(now).date().replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    out = []
    for g in db.list_goals(period_start=start.isoformat(), username=owner):
        realized = db.goal_realized(owner, g["metric"], start.isoformat(), end.isoformat())
        out.append({"metric": g["metric"], "target": float(g.get("target") or 0),
                    "realized": realized})
    return out


def team_panel(usernames: List[str], now: Optional[datetime] = None) -> Dict[str, Any]:
    """Painel Equipe do gestor (toggle da Home): atrasadas/hoje por vendedor,
    leads sem dono, parados >7d por dono, fila envelhecendo por dono."""
    now = now or now_utc()
    por_vendedor = {}
    for u in usernames:
        g = agenda_groups(u, now)
        respostas_atrasadas = sum(
            1 for a in g["atrasadas"] if a.get("type") == "responder")
        por_vendedor[u] = {
            "atrasadas": len(g["atrasadas"]),
            "hoje": len(g["hoje"]),
            "respostas_atrasadas": respostas_atrasadas,
        }
    sem_dono, parados = [], []
    try:
        sem_dono = db.client.table("companies").select("id,name,city,urgency_tier") \
            .is_("owner_username", "null") \
            .in_("status", ["contacted", "responded", "qualified", "enriched"]) \
            .limit(20).execute().data or []
    except Exception:
        pass
    try:
        cutoff = (now - timedelta(days=7)).isoformat()
        parados = db.client.table("companies").select(
            "id,name,owner_username,last_contacted_at,commercial_stage") \
            .lt("last_contacted_at", cutoff) \
            .in_("status", ["contacted", "responded"]) \
            .order("last_contacted_at").limit(20).execute().data or []
        parados = [p for p in parados
                   if (p.get("commercial_stage") or "").lower() not in ("cliente", "perdido")]
    except Exception:
        pass
    aging_por_dono: Dict[str, int] = {}
    try:
        rows = db.client.table("approval_queue").select("created_by") \
            .eq("status", "pending") \
            .lt("created_at", (now - timedelta(hours=24)).isoformat()) \
            .limit(500).execute().data or []
        for r in rows:
            o = r.get("created_by") or "—"
            aging_por_dono[o] = aging_por_dono.get(o, 0) + 1
    except Exception:
        pass
    return {"por_vendedor": por_vendedor, "sem_dono": sem_dono,
            "parados_7d": parados, "fila_aging": aging_por_dono}


def busca_global(q: str, limit: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """Busca acionavel: escolas e pessoas (cada resultado leva a acao)."""
    out: Dict[str, List[Dict[str, Any]]] = {"escolas": [], "contatos": []}
    q = (q or "").strip()
    if len(q) < 2:
        return out
    try:
        out["escolas"] = db.client.table("companies").select(
            "id,name,city,state,status,commercial_stage,inep_code") \
            .ilike("name", f"%{q}%").limit(limit).execute().data or []
    except Exception:
        pass
    try:
        out["contatos"] = db.client.table("contacts").select(
            "id,full_name,role,email,company_id") \
            .ilike("full_name", f"%{q}%").limit(limit).execute().data or []
    except Exception:
        pass
    return out
