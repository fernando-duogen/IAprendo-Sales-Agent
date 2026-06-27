"""
IAlex Agenda/Metas tools (F1 do redesign v2 "Dia de Venda").

14 tools: agenda (5) · metas (3) · gestao (2) · inteligencia (2) · registro (2).
Funcionam IDENTICAS no WhatsApp e no chat web (mesmo Brain).

Import pattern (brain.py, igual ao das ENEM tools):
    try:
        from agent.tools.agenda_tools import AGENDA_TOOLS, AGENDA_TOOL_HANDLERS
    except Exception:
        AGENDA_TOOLS = []
        AGENDA_TOOL_HANDLERS = {}

Regras de negocio: docs/SPEC_AGENDA_METAS.md. Vocabulario: dashboard/labels.py.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from utils.logger import logger
from utils.sender_profile import get_active_sender_username, is_admin
from workflows.activity_engine import (
    BRT, add_business_hours, business_day_at, now_utc, parse_ts, to_brt,
)
from dashboard.labels import (
    GOAL_METRICS, activity_label, goal_metric_label, priority_label,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _me() -> str:
    return get_active_sender_username() or "fernando"


def _err(msg: str) -> str:
    return json.dumps({"erro": msg}, ensure_ascii=False)


def _ok(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _fmt_dt(iso_str: Optional[str]) -> str:
    dt = parse_ts(iso_str)
    if not dt:
        return "?"
    local = to_brt(dt)
    return local.strftime("%d/%m %Hh%M") if (local.minute or local.hour) else local.strftime("%d/%m")


def _parse_when(when: Optional[str], default_hour: int = 9) -> datetime:
    """'2026-06-12' | '2026-06-12T14:00' -> datetime UTC (data pura vira HHh BRT).
    Sem valor: amanha as 9h (dia util)."""
    if when:
        try:
            raw = str(when).strip()
            if len(raw) == 10:  # YYYY-MM-DD
                local = datetime.fromisoformat(raw).replace(
                    hour=default_hour, minute=0, tzinfo=BRT)
            else:
                local = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                if local.tzinfo is None:
                    local = local.replace(tzinfo=BRT)
            return local.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return business_day_at(now_utc() + timedelta(days=1), default_hour)


def _find_company(nome_ou_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Resolve escola por UUID, codigo MEC ou nome (fuzzy)."""
    if not nome_ou_id:
        return None
    ref = str(nome_ou_id).strip()
    try:
        if len(ref) == 36 and ref.count("-") == 4:
            rows = db.client.table("companies").select("*").eq("id", ref).limit(1).execute().data
            if rows:
                return rows[0]
        if ref.isdigit():
            rows = db.client.table("companies").select("*").eq("inep_code", ref).limit(1).execute().data
            if rows:
                return rows[0]
        for w in [ref] + ref.split():
            rows = db.client.table("companies").select("*") \
                .ilike("name", f"%{w}%").limit(3).execute().data or []
            if len(rows) == 1:
                return rows[0]
            if rows and w == ref:
                return rows[0]  # melhor match do nome completo
    except Exception as e:
        logger.debug("agenda_tools _find_company: %s", e)
    return None


def _resolve_activity(ref: str, owner: str) -> Any:
    """id exato OU texto aproximado no titulo das abertas do dono.
    Retorna dict (1 match), list (ambiguo) ou None."""
    ref = str(ref or "").strip()
    if len(ref) == 36 and ref.count("-") == 4:
        rows = db.client.table("activities").select("*").eq("id", ref).limit(1).execute().data
        return rows[0] if rows else None
    open_acts = db.list_activities(owner=owner, status=["open", "snoozed"], limit=100)
    matches = [a for a in open_acts if ref.lower() in (a.get("title") or "").lower()]
    if len(matches) == 1:
        return matches[0]
    return matches or None


def _activity_line(a: Dict[str, Any]) -> str:
    flag = "⚠️ " if (parse_ts(a.get("due_at")) or now_utc()) < now_utc() else ""
    pr = "🔴 " if a.get("priority") == 1 else ""
    return (f"{flag}{pr}{activity_label(a.get('type'))}: {a.get('title')} "
            f"(vence {_fmt_dt(a.get('due_at'))})")


def _month_bounds(mes: Optional[str]) -> (str, str, str):
    """'2026-07' -> (period_start, period_end, label). Default: mes corrente BRT."""
    local = to_brt(now_utc())
    if mes:
        try:
            y, m = str(mes).strip()[:7].split("-")
            local = local.replace(year=int(y), month=int(m))
        except (TypeError, ValueError):
            pass
    start = local.date().replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start.isoformat(), end.isoformat(), f"{start.year}-{start.month:02d}"


# ===========================================================================
# AGENDA (5)
# ===========================================================================

def _handle_minha_agenda(params: Dict) -> str:
    try:
        me = params.get("usuario") if (params.get("usuario") and is_admin(_me())) else _me()
        now = now_utc()
        local_today = to_brt(now).date()
        acts = db.list_activities(owner=me, status=["open"], limit=100)
        atrasadas, hoje, proximas = [], [], []
        for a in acts:
            due = parse_ts(a.get("due_at"))
            if not due:
                continue
            d = to_brt(due).date()
            if due < now and d < local_today:
                atrasadas.append(a)
            elif d == local_today:
                (atrasadas if due < now else hoje).append(a)
            else:
                proximas.append(a)
        return _ok({
            "usuario": me,
            "atrasadas": [_activity_line(a) for a in atrasadas],
            "hoje": [_activity_line(a) for a in hoje],
            "proximas": [_activity_line(a) for a in proximas[:10]],
            "resumo": f"{len(atrasadas)} atrasadas · {len(hoje)} para hoje · "
                      f"{len(proximas)} proximas",
            "ids": {a["title"][:40]: a["id"] for a in (atrasadas + hoje)[:15]},
        })
    except Exception as e:
        logger.error("minha_agenda: %s", e)
        return _err(str(e)[:200])


def _handle_criar_atividade(params: Dict) -> str:
    try:
        titulo = (params.get("titulo") or "").strip()
        if not titulo:
            return _err("Informe o titulo da atividade.")
        me = _me()
        owner = me
        if params.get("para_usuario") and params["para_usuario"] != me:
            if not is_admin(me):
                return _err("So o admin cria atividades para outra pessoa.")
            owner = params["para_usuario"]
        company = _find_company(params.get("escola_nome"))
        tipo = params.get("tipo") or ("ligar" if "ligar" in titulo.lower() else "tarefa")
        if tipo not in ("ligar", "tarefa", "follow_up"):
            tipo = "tarefa"
        due = _parse_when(params.get("quando"))
        created = db.create_activity({
            "owner_username": owner, "type": tipo, "title": titulo[:300],
            "details": (params.get("detalhes") or None),
            "due_at": due.isoformat(),
            "priority": int(params.get("prioridade") or 2),
            "source": "ialex", "created_by": me,
            "company_id": company.get("id") if company else None,
        })
        if not created:
            return _err("Falha ao criar a atividade.")
        return _ok({"ok": True, "id": created["id"],
                    "msg": f"Anotado: '{titulo}' para {_fmt_dt(created['due_at'])}"
                           + (f" (escola: {company['name']})" if company else "")})
    except Exception as e:
        logger.error("criar_atividade: %s", e)
        return _err(str(e)[:200])


def _handle_concluir_atividade(params: Dict) -> str:
    try:
        me = _me()
        found = _resolve_activity(params.get("ref") or params.get("titulo") or "", me)
        if not found:
            return _err("Nao achei essa atividade aberta na sua agenda.")
        if isinstance(found, list):
            return _ok({"ambiguo": True,
                        "opcoes": [{"id": a["id"], "titulo": a["title"]} for a in found[:5]],
                        "msg": "Achei mais de uma — qual delas?"})
        if db.complete_activity(found["id"], me, "manual"):
            return _ok({"ok": True, "msg": f"✓ Concluida: {found['title']}"})
        return _err("Falha ao concluir.")
    except Exception as e:
        logger.error("concluir_atividade: %s", e)
        return _err(str(e)[:200])


def _handle_adiar_atividade(params: Dict) -> str:
    try:
        me = _me()
        found = _resolve_activity(params.get("ref") or params.get("titulo") or "", me)
        if not found:
            return _err("Nao achei essa atividade aberta na sua agenda.")
        if isinstance(found, list):
            return _ok({"ambiguo": True,
                        "opcoes": [{"id": a["id"], "titulo": a["title"]} for a in found[:5]],
                        "msg": "Achei mais de uma — qual delas?"})
        until = _parse_when(params.get("quando"))
        res = db.snooze_activity(found["id"], until.isoformat())
        if res.get("ok"):
            return _ok({"ok": True,
                        "msg": f"⏰ Adiada para {_fmt_dt(until.isoformat())} "
                               f"({res['snooze_count']}/3 adiamentos)"})
        return _err(res.get("erro") or "Falha ao adiar.")
    except Exception as e:
        logger.error("adiar_atividade: %s", e)
        return _err(str(e)[:200])


def _handle_atividades_atrasadas(params: Dict) -> str:
    try:
        me = _me()
        target = params.get("usuario")
        if target and target != me and not is_admin(me):
            return _err("So o admin ve a agenda de outra pessoa.")
        owner = target or me
        now = now_utc()
        acts = db.list_activities(owner=owner, status=["open"],
                                  due_before=now.isoformat(), limit=50)
        return _ok({
            "usuario": owner, "total": len(acts),
            "atividades": [_activity_line(a) for a in acts],
        })
    except Exception as e:
        logger.error("atividades_atrasadas: %s", e)
        return _err(str(e)[:200])


# ===========================================================================
# METAS (3)
# ===========================================================================

def _goal_status_line(g: Dict[str, Any], period_start: str, period_end: str) -> Dict[str, Any]:
    realized = db.goal_realized(g["username"], g["metric"], period_start, period_end)
    target = float(g.get("target") or 0)
    pct = round(100.0 * realized / target, 1) if target else 0.0
    return {
        "metrica": goal_metric_label(g["metric"]),
        "meta": target, "realizado": realized, "pct": pct,
        "ritmo": "no ritmo" if _on_pace(realized, target, period_start, period_end) else "atencao",
    }


def _on_pace(realized: float, target: float, period_start: str, period_end: str) -> bool:
    """Pro-rata por dias corridos x0.9 (SPEC §4.2 — simplificacao F1)."""
    if not target:
        return True
    try:
        start = date.fromisoformat(period_start)
        end = date.fromisoformat(period_end)
        today = to_brt(now_utc()).date()
        total = max(1, (end - start).days)
        gone = min(total, max(0, (today - start).days + 1))
        return realized >= target * (gone / total) * 0.9
    except Exception:
        return True


def _handle_minha_meta(params: Dict) -> str:
    try:
        me = _me()
        start, end, label = _month_bounds(params.get("mes"))
        goals = db.list_goals(period_start=start, username=me)
        if not goals:
            return _ok({"mes": label, "msg": f"Ainda nao ha metas definidas para "
                        f"{label}. Fale com o gestor (ou use definir_meta, se admin)."})
        return _ok({"mes": label, "usuario": me,
                    "metas": [_goal_status_line(g, start, end) for g in goals]})
    except Exception as e:
        logger.error("minha_meta: %s", e)
        return _err(str(e)[:200])


def _handle_metas_time(params: Dict) -> str:
    try:
        if not is_admin(_me()):
            return _err("Visao do time e so para o admin. Use minha_meta.")
        start, end, label = _month_bounds(params.get("mes"))
        goals = db.list_goals(period_start=start)
        if not goals:
            return _ok({"mes": label, "msg": f"Nenhuma meta definida para {label}."})
        por_pessoa: Dict[str, List[Dict[str, Any]]] = {}
        for g in goals:
            por_pessoa.setdefault(g["username"], []).append(
                _goal_status_line(g, start, end))
        return _ok({"mes": label, "time": por_pessoa})
    except Exception as e:
        logger.error("metas_time: %s", e)
        return _err(str(e)[:200])


def _handle_definir_meta(params: Dict) -> str:
    try:
        me = _me()
        if not is_admin(me):
            return _err("So o admin define metas.")
        username = (params.get("usuario") or "").strip().lower()
        metric = (params.get("metrica") or "").strip().lower()
        if metric not in GOAL_METRICS:
            return _err(f"Metrica invalida. Use uma de: {', '.join(GOAL_METRICS)}")
        try:
            target = float(params.get("alvo"))
        except (TypeError, ValueError):
            return _err("Informe o alvo numerico da meta.")
        start, end, label = _month_bounds(params.get("mes"))
        # Calibracao historica (SPEC §4.1): ultimos 30 dias como contexto
        hist_end = to_brt(now_utc()).date().isoformat()
        hist_start = (to_brt(now_utc()).date() - timedelta(days=30)).isoformat()
        hist = db.goal_realized(username, metric, hist_start, hist_end)
        saved = db.upsert_goal(username, metric, start, target, me,
                               reason=params.get("motivo"))
        if not saved:
            return _err("Falha ao salvar a meta.")
        return _ok({"ok": True, "mes": label, "usuario": username,
                    "metrica": goal_metric_label(metric), "alvo": target,
                    "contexto": f"Ultimos 30 dias: {hist:g} de {goal_metric_label(metric)}. "
                                f"Benchmark: {GOAL_METRICS[metric]['benchmark']}."})
    except Exception as e:
        logger.error("definir_meta: %s", e)
        return _err(str(e)[:200])


# ===========================================================================
# GESTAO (2)
# ===========================================================================

def _handle_reatribuir_leads_lote(params: Dict) -> str:
    try:
        me = _me()
        if not is_admin(me):
            return _err("So o admin reatribui leads em lote.")
        origem = (params.get("de_usuario") or "").strip().lower()
        destino = (params.get("para_usuario") or "").strip().lower()
        if not origem or not destino:
            return _err("Informe de_usuario e para_usuario.")
        if not params.get("confirmar"):
            n = db.client.table("companies").select("id", count="exact") \
                .eq("owner_username", origem).execute().count or 0
            return _ok({"confirmacao_necessaria": True,
                        "msg": f"{n} leads de {origem} seriam transferidos para "
                               f"{destino}. Confirme para executar (confirmar=true)."})
        limite = int(params.get("limite") or 999)
        rows = db.client.table("companies").select("id,name") \
            .eq("owner_username", origem).limit(limite).execute().data or []
        moved, acts_moved = 0, 0
        for c in rows:
            db.client.table("companies").update(
                {"owner_username": destino}).eq("id", c["id"]).execute()
            acts_moved += db.reassign_company_activities(
                c["id"], destino, note=f"transferida de {origem} por {me}")
            moved += 1
        logger.info("reatribuir_leads_lote: %s->%s leads=%s acts=%s by=%s",
                    origem, destino, moved, acts_moved, me)
        return _ok({"ok": True, "leads_transferidos": moved,
                    "atividades_transferidas": acts_moved,
                    "msg": f"{moved} leads (e {acts_moved} atividades abertas) "
                           f"de {origem} agora sao de {destino}."})
    except Exception as e:
        logger.error("reatribuir_leads_lote: %s", e)
        return _err(str(e)[:200])


def _handle_kpi_periodo(params: Dict) -> str:
    try:
        me = _me()
        vendedor = (params.get("vendedor") or "").strip().lower() or None
        if vendedor and vendedor not in ("team",) and vendedor != me and not is_admin(me):
            return _err("KPIs de outro vendedor sao so para o admin.")
        target = vendedor or "team"
        inicio = params.get("inicio")
        fim = params.get("fim")
        if not inicio or not fim:
            start, end, label = _month_bounds(params.get("mes"))
            inicio, fim = start, end
        out = {}
        for metric in GOAL_METRICS:
            out[goal_metric_label(metric)] = db.goal_realized(target, metric, inicio, fim)
        return _ok({"de": inicio, "ate": fim, "vendedor": target, "kpis": out})
    except Exception as e:
        logger.error("kpi_periodo: %s", e)
        return _err(str(e)[:200])


# ===========================================================================
# INTELIGENCIA (2)
# ===========================================================================

def _analytics(inep: Optional[str]) -> Dict[str, Any]:
    if not inep:
        return {}
    try:
        rows = db.client.table("school_analytics").select(
            "enem_media_geral,enem_gap_vs_peer_2025,enem_area_mais_fraca,"
            "enem_amostra_confiavel,peer_trajetoria_6y,enem_potencial_melhoria"
        ).eq("inep_code", str(inep).strip()).limit(1).execute().data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def _build_argumentos(company: Dict[str, Any]) -> List[str]:
    """Top 3-5 argumentos em linguagem de vendedor (blueprint §4 Escolas)."""
    args: List[str] = []
    ana = _analytics(company.get("inep_code"))
    confiavel = bool(ana.get("enem_amostra_confiavel"))
    gap = ana.get("enem_gap_vs_peer_2025")
    area = ana.get("enem_area_mais_fraca")
    if confiavel and gap is not None and float(gap) <= -15:
        args.append(f"📉 {area or 'Uma area'} esta {abs(float(gap)):.0f} pontos abaixo "
                    f"de escolas semelhantes no ENEM — dor clara que o IAprendo ataca.")
    elif confiavel and area:
        args.append(f"📊 {area} e a area mais fraca da escola no ENEM — bom gancho de conversa.")
    traj = (ana.get("peer_trajetoria_6y") or "").lower()
    fund = int(company.get("matriculas_fund_af") or 0)
    medio = int(company.get("matriculas_medio") or 0)
    alvo = fund + medio
    if "cresc" in traj or "subiu" in traj:
        args.append("📈 Matriculas em crescimento — orcamento em expansao, momento certo.")
    if alvo:
        try:
            from integrations.agenda_config import agenda_config
            ticket = agenda_config.ticket_por_aluno()
        except Exception:
            ticket = 7.99
        args.append(f"💰 {alvo} alunos-alvo → potencial de R$ {alvo * ticket:,.0f}/mes."
                    .replace(",", "."))
    if not int(company.get("qt_coordenadores") or 0):
        args.append("👩‍💼 Sem coordenador pedagogico mapeado — decisao tende a estar "
                    "centralizada na direcao (ciclo de venda mais curto).")
    tech = (company.get("nivel_tecnologico") or "").lower()
    if tech == "alto":
        args.append("💻 Nivel tecnologico alto — perfil pronto para adotar plataforma.")
    elif tech == "baixo":
        args.append("🌱 Nivel tecnologico baixo — IAprendo como porta de entrada digital.")
    if not confiavel and ana:
        args.append("⚠️ Poucos alunos fizeram ENEM — use dados como indicativos, nao cite numeros.")
    return args[:5]


def _handle_argumentos_venda(params: Dict) -> str:
    try:
        company = _find_company(params.get("escola") or params.get("escola_nome"))
        if not company:
            return _err("Nao achei essa escola no CRM. Importe-a primeiro (importar_escola).")
        args = _build_argumentos(company)
        return _ok({"escola": company.get("name"),
                    "argumentos": args or ["Sem dados suficientes — gere o Relatorio da "
                                           "escola (gerar_relatorio_escola) para mais contexto."]})
    except Exception as e:
        logger.error("argumentos_venda: %s", e)
        return _err(str(e)[:200])


def _handle_preparar_reuniao(params: Dict) -> str:
    """Briefing de reuniao: dados + argumentos + ultimas interacoes + relatorio."""
    try:
        company = _find_company(params.get("escola") or params.get("escola_nome"))
        if not company:
            return _err("Nao achei essa escola no CRM.")
        cid = company["id"]
        meetings = db.client.table("meetings").select("scheduled_at,title,meeting_type,location") \
            .eq("company_id", cid).eq("status", "scheduled") \
            .gte("scheduled_at", now_utc().isoformat()) \
            .order("scheduled_at").limit(1).execute().data or []
        inters = db.client.table("interactions").select("type,subject,message_snippet,created_at") \
            .eq("company_id", cid).neq("type", "stage_changed") \
            .order("created_at", desc=True).limit(3).execute().data or []
        inep = company.get("inep_code") or ""
        report_url = (f"https://fernando-duogen.github.io/IAprendo-Sales-Agent/reports/{inep}.html"
                      if inep and not str(inep).startswith("M-") else None)
        return _ok({
            "escola": company.get("name"),
            "reuniao": (f"{_fmt_dt(meetings[0]['scheduled_at'])} · "
                        f"{meetings[0].get('meeting_type') or ''} "
                        f"{meetings[0].get('location') or ''}".strip()
                        if meetings else "nenhuma reuniao futura agendada"),
            "argumentos_de_venda": _build_argumentos(company),
            "ultimas_interacoes": [
                f"{_fmt_dt(i.get('created_at'))} · {i.get('type')}: "
                f"{(i.get('subject') or i.get('message_snippet') or '')[:80]}"
                for i in inters],
            "relatorio_da_escola": report_url or "gere com gerar_relatorio_escola",
            "dica": "Abra o relatorio antes; comece pela dor (argumento 1).",
        })
    except Exception as e:
        logger.error("preparar_reuniao: %s", e)
        return _err(str(e)[:200])


# ===========================================================================
# REGISTRO (2) — "encontrei alguem na rua" (blueprint v1.4)
# ===========================================================================

def _handle_criar_contato(params: Dict) -> str:
    try:
        company = _find_company(params.get("escola") or params.get("escola_nome"))
        if not company:
            return _err("Nao achei essa escola no CRM — use registrar_encontro, que "
                        "tambem cria a escola se preciso.")
        nome = (params.get("nome") or "").strip()
        if not nome:
            return _err("Informe o nome da pessoa.")
        data = {
            "company_id": company["id"], "full_name": nome[:200],
            "role": (params.get("cargo") or "")[:200], "source": "manual",
            "confidence_score": 90,
        }
        try:
            from utils.role_classifier import classify_role
            dm, prio = classify_role(data["role"])
            data["decision_maker_type"] = dm
            data["outreach_priority"] = prio
        except Exception:
            pass
        for k_src, k_dst in (("email", "email"), ("whatsapp", "phone_whatsapp"),
                             ("telefone", "phone")):
            if params.get(k_src):
                data[k_dst] = str(params[k_src]).strip()
        cid = db.insert_contact(data)
        if not cid:
            return _err("Falha ao criar o contato.")
        return _ok({"ok": True, "msg": f"Contato {nome} criado em {company['name']}."})
    except Exception as e:
        logger.error("criar_contato: %s", e)
        return _err(str(e)[:200])


def _handle_registrar_encontro(params: Dict) -> str:
    """Orquestra: escola (CRM -> criar manual) + pessoa (opcional) + interacao +
    proximo passo (atividade). Ex.: 'conheci a diretora Maria do Colegio X na
    feira, registra e me lembra de ligar quinta'."""
    try:
        me = _me()
        escola_ref = params.get("escola") or params.get("escola_nome")
        if not escola_ref:
            return _err("Informe a escola.")
        company = _find_company(escola_ref)
        created_school = False
        if not company:
            if not params.get("criar_escola"):
                return _ok({"escola_nao_encontrada": True,
                            "msg": f"'{escola_ref}' nao esta no CRM. Posso tentar "
                                   "importar da base MEC (importar_escola) ou criar "
                                   "manualmente — confirme com criar_escola=true "
                                   "(informe cidade/UF se souber)."})
            data = {
                "name": str(escola_ref).strip()[:500],
                "inep_code": f"M-{uuid.uuid4().hex[:8].upper()}",
                "city": (params.get("cidade") or "")[:200] or None,
                "state": (params.get("uf") or "")[:2].upper() or None,
                "fonte_dados": "manual", "status": "contacted",
                "owner_username": me,
            }
            cid_new = db.insert_company({k: v for k, v in data.items() if v is not None})
            if not cid_new:
                return _err("Falha ao criar a escola manual.")
            company = {"id": cid_new, "name": data["name"], "inep_code": data["inep_code"]}
            created_school = True
        cid = company["id"]

        # pessoa (opcional)
        contato_msg = ""
        if params.get("pessoa"):
            _handle_criar_contato({"escola": company.get("name") or cid,
                                   "nome": params["pessoa"],
                                   "cargo": params.get("cargo"),
                                   "email": params.get("email"),
                                   "whatsapp": params.get("whatsapp")})
            contato_msg = f" Contato {params['pessoa']} registrado."

        # interacao (conta como contato real -> alimenta auto-resolucao e metas)
        when = _parse_when(params.get("quando"), default_hour=to_brt(now_utc()).hour) \
            if params.get("quando") else now_utc()
        db.client.table("interactions").insert({
            "company_id": cid, "type": "call_made", "channel": "phone",
            "subject": "Encontro/contato registrado manualmente",
            "message_snippet": (params.get("resumo") or "")[:500] or None,
            "created_at": when.isoformat(),
        }).execute()
        try:
            db.client.table("companies").update(
                {"last_contacted_at": when.isoformat(), "status": "contacted"}
            ).eq("id", cid).execute()
        except Exception:
            pass

        # proximo passo (atividade)
        prox_msg = ""
        if params.get("proximo_passo"):
            due = _parse_when(params.get("proximo_quando"))
            act = db.create_activity({
                "owner_username": me, "type": "ligar",
                "title": f"{params['proximo_passo']} — {company.get('name')}"[:300],
                "due_at": due.isoformat(), "priority": 2,
                "source": "ialex", "created_by": me, "company_id": cid,
            })
            if act:
                prox_msg = f" Proximo passo agendado para {_fmt_dt(act['due_at'])}."

        return _ok({"ok": True,
                    "msg": f"Encontro registrado em {company.get('name')}."
                           + (" (escola criada manualmente)" if created_school else "")
                           + contato_msg + prox_msg})
    except Exception as e:
        logger.error("registrar_encontro: %s", e)
        return _err(str(e)[:200])


# ===========================================================================
# Schemas (formato Anthropic/OpenAI tools do brain)
# ===========================================================================

AGENDA_TOOLS: List[Dict[str, Any]] = [
    {"name": "minha_agenda",
     "description": "Agenda de atividades do usuario (atrasadas/hoje/proximas). Use quando perguntarem 'o que tenho pra hoje?', 'minha agenda', 'minhas tarefas'. Admin pode passar usuario para ver a agenda de outro.",
     "input_schema": {"type": "object", "properties": {
         "usuario": {"type": "string", "description": "(admin) ver agenda de outro vendedor"}}}},
    {"name": "criar_atividade",
     "description": "Cria atividade/lembrete na agenda ('me lembra de ligar pro Colegio X sexta'). quando aceita YYYY-MM-DD ou ISO com hora; sem hora = 9h.",
     "input_schema": {"type": "object", "properties": {
         "titulo": {"type": "string"},
         "quando": {"type": "string", "description": "YYYY-MM-DD ou ISO"},
         "escola_nome": {"type": "string"},
         "tipo": {"type": "string", "enum": ["tarefa", "ligar", "follow_up"]},
         "prioridade": {"type": "integer", "description": "1 alta, 2 normal, 3 baixa"},
         "detalhes": {"type": "string"},
         "para_usuario": {"type": "string", "description": "(admin) criar para outro"}},
         "required": ["titulo"]}},
    {"name": "concluir_atividade",
     "description": "Marca atividade como concluida. ref aceita o id OU parte do titulo ('conclui a do follow-up da Alfa').",
     "input_schema": {"type": "object", "properties": {
         "ref": {"type": "string"}}, "required": ["ref"]}},
    {"name": "adiar_atividade",
     "description": "Adia (snooze) uma atividade. Limite de 3 adiamentos. ref = id ou parte do titulo.",
     "input_schema": {"type": "object", "properties": {
         "ref": {"type": "string"}, "quando": {"type": "string"}},
         "required": ["ref"]}},
    {"name": "atividades_atrasadas",
     "description": "Lista atividades atrasadas (vencidas e abertas). Admin pode passar usuario.",
     "input_schema": {"type": "object", "properties": {
         "usuario": {"type": "string"}}}},
    {"name": "minha_meta",
     "description": "Minhas metas do mes com realizado AO VIVO e ritmo ('como estou na meta?', 'quanto falta?'). mes = YYYY-MM (default: atual).",
     "input_schema": {"type": "object", "properties": {
         "mes": {"type": "string"}}}},
    {"name": "metas_time",
     "description": "(admin) Grade de metas do time inteiro com realizado e ritmo ('como esta o time?', 'quem esta atras da meta?').",
     "input_schema": {"type": "object", "properties": {
         "mes": {"type": "string"}}}},
    {"name": "definir_meta",
     "description": "(admin) Define/atualiza meta de um vendedor. Metricas: emails_enviados, respostas, reunioes_realizadas, propostas, clientes, valor_fechado, atividades_concluidas. Retorna contexto historico de calibracao.",
     "input_schema": {"type": "object", "properties": {
         "usuario": {"type": "string"},
         "metrica": {"type": "string"},
         "alvo": {"type": "number"},
         "mes": {"type": "string", "description": "YYYY-MM (default: atual)"},
         "motivo": {"type": "string", "description": "obrigatorio ao mudar meta apos o dia 5"}},
         "required": ["usuario", "metrica", "alvo"]}},
    {"name": "reatribuir_leads_lote",
     "description": "(admin) Transfere TODOS os leads de um vendedor para outro (ferias/redistribuicao), levando as atividades abertas junto. Sem confirmar=true, so mostra a previa.",
     "input_schema": {"type": "object", "properties": {
         "de_usuario": {"type": "string"}, "para_usuario": {"type": "string"},
         "limite": {"type": "integer"}, "confirmar": {"type": "boolean"}},
         "required": ["de_usuario", "para_usuario"]}},
    {"name": "kpi_periodo",
     "description": "KPIs consolidados de um periodo (e-mails, respostas, reunioes, propostas, clientes, receita, atividades). vendedor='team' (default) ou username (proprio; admin ve qualquer um). Use mes=YYYY-MM OU inicio/fim ISO.",
     "input_schema": {"type": "object", "properties": {
         "mes": {"type": "string"}, "inicio": {"type": "string"},
         "fim": {"type": "string"}, "vendedor": {"type": "string"}}}},
    {"name": "argumentos_venda",
     "description": "Top 3-5 argumentos de venda da escola em linguagem de vendedor, gerados dos dados ENEM/Censo ('me da os argumentos pro Atlantico'). Respeita o gate de amostra confiavel.",
     "input_schema": {"type": "object", "properties": {
         "escola": {"type": "string"}}, "required": ["escola"]}},
    {"name": "preparar_reuniao",
     "description": "Briefing completo para reuniao com uma escola: data da reuniao, argumentos de venda, ultimas interacoes e link do Relatorio da escola ('o que preciso saber pra reuniao de amanha?').",
     "input_schema": {"type": "object", "properties": {
         "escola": {"type": "string"}}, "required": ["escola"]}},
    {"name": "criar_contato",
     "description": "Cria uma PESSOA (contato) manualmente numa escola do CRM (nome, cargo, email, whatsapp, telefone).",
     "input_schema": {"type": "object", "properties": {
         "escola": {"type": "string"}, "nome": {"type": "string"},
         "cargo": {"type": "string"}, "email": {"type": "string"},
         "whatsapp": {"type": "string"}, "telefone": {"type": "string"}},
         "required": ["escola", "nome"]}},
    {"name": "registrar_encontro",
     "description": "Registra um encontro/contato feito FORA da plataforma ('conheci a diretora Maria do Colegio X na feira; me lembra de ligar quinta'). Cria a escola manualmente se nao existir (criar_escola=true), cria a pessoa, registra a interacao e agenda o proximo passo.",
     "input_schema": {"type": "object", "properties": {
         "escola": {"type": "string"},
         "pessoa": {"type": "string"}, "cargo": {"type": "string"},
         "email": {"type": "string"}, "whatsapp": {"type": "string"},
         "resumo": {"type": "string"},
         "quando": {"type": "string", "description": "quando aconteceu (default: agora)"},
         "proximo_passo": {"type": "string"},
         "proximo_quando": {"type": "string"},
         "criar_escola": {"type": "boolean"},
         "cidade": {"type": "string"}, "uf": {"type": "string"}},
         "required": ["escola"]}},
]

AGENDA_TOOL_HANDLERS: Dict[str, Any] = {
    "minha_agenda": _handle_minha_agenda,
    "criar_atividade": _handle_criar_atividade,
    "concluir_atividade": _handle_concluir_atividade,
    "adiar_atividade": _handle_adiar_atividade,
    "atividades_atrasadas": _handle_atividades_atrasadas,
    "minha_meta": _handle_minha_meta,
    "metas_time": _handle_metas_time,
    "definir_meta": _handle_definir_meta,
    "reatribuir_leads_lote": _handle_reatribuir_leads_lote,
    "kpi_periodo": _handle_kpi_periodo,
    "argumentos_venda": _handle_argumentos_venda,
    "preparar_reuniao": _handle_preparar_reuniao,
    "criar_contato": _handle_criar_contato,
    "registrar_encontro": _handle_registrar_encontro,
}
