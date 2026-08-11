"""
Health check consolidado do sistema IAprendo.

Ponto unico de verificacao de saude. Usado por:
- Tool do IAlex `diagnostico_sistema` (on-demand via WhatsApp)
- Dashboard Configuracoes > aba Diagnostico (visual)
- Dashboard Painel > tile Diagnostico (at-a-glance com cor)

Design:
- Cada check e isolado em _check_X() -> Dict[status, detail, meta]
- Se um check crasha, ele captura e retorna status=unknown
- Overall = pior status entre todos
- Safe pra chamar em qualquer contexto (dashboard, IAlex, script)

Status codes:
- healthy  : tudo normal
- degraded : anomalia menor, sistema funcional
- critical : problema que bloqueia uso normal
- unknown  : check nao conseguiu determinar
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import requests

from utils.logger import logger


# ============================================================================
# Helpers
# ============================================================================

STATUS_ORDER = {"healthy": 0, "unknown": 1, "degraded": 2, "critical": 3}


def _worst(statuses: List[str]) -> str:
    """Retorna o pior status de uma lista."""
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda s: STATUS_ORDER.get(s, 1))


def _safe_check(name: str, fn) -> Dict[str, Any]:
    """Wrap um check pra nunca crashar — retorna unknown em qualquer erro."""
    try:
        r = fn()
        if not isinstance(r, dict) or "status" not in r:
            return {"status": "unknown", "detail": "check retornou formato invalido"}
        return r
    except Exception as e:
        logger.debug(f"Health check '{name}' crashou: {e}")
        return {"status": "unknown", "detail": f"check crashou: {type(e).__name__}: {str(e)[:100]}"}


def _on_streamlit_cloud() -> bool:
    """True se rodando no Streamlit Community Cloud (monta o repo em /mount/src).

    Os checks que batem em localhost (webhook :5001, Evolution :8080) so fazem
    sentido onde o IAlex roda (PC/Oracle). No Cloud sao falso-vermelho garantido —
    entao la viram 'N/A' em vez de critico. Mesmo sinal usado em insight_charts.
    """
    try:
        return os.path.isdir("/mount/src")
    except Exception:
        return False


# Status neutro p/ checks locais quando vistos do Cloud (nao conta como problema)
_NA_CLOUD = {"status": "unknown", "detail": "N/A no Cloud (IAlex roda no PC/Oracle)"}


# ============================================================================
# Checks individuais
# ============================================================================

def _check_database() -> Dict[str, Any]:
    """Ping Supabase e mede latencia."""
    from database.supabase_client import db
    start = time.time()
    r = db.client.table("companies").select("id").limit(1).execute()
    elapsed_ms = int((time.time() - start) * 1000)
    if not hasattr(r, "data"):
        return {"status": "critical", "detail": "Supabase nao retornou objeto valido"}
    if elapsed_ms > 2000:
        return {"status": "degraded", "detail": f"latencia alta: {elapsed_ms}ms"}
    return {"status": "healthy", "detail": f"Supabase respondeu em {elapsed_ms}ms", "meta": {"latency_ms": elapsed_ms}}


def _check_schema_migrations() -> Dict[str, Any]:
    """Verifica se colunas criticas das ultimas migrations estao presentes."""
    from database.supabase_client import db
    critical = [
        ("companies", "commercial_stage"),        # 013
        ("companies", "valor_mensal_proposto"),    # 013
        ("companies", "cnpj_mantenedora"),         # 010
        ("companies", "matriculas_fund_af"),       # 010
        ("contacts", "phone_whatsapp"),            # power_map
        ("approval_queue", "delivered_at"),        # 012
        ("approval_queue", "channel"),             # channels
        ("rede_overrides", "nome_oficial"),        # 014
        ("conversation_memory", "content"),
    ]
    missing = []
    for table, col in critical:
        try:
            db.client.table(table).select(col).limit(1).execute()
        except Exception as e:
            err = str(e)
            if "42703" in err or "42P01" in err or "does not exist" in err.lower():
                missing.append(f"{table}.{col}")
    if missing:
        return {
            "status": "critical",
            "detail": f"{len(missing)} coluna(s)/tabela(s) faltando",
            "meta": {"missing": missing},
        }
    return {"status": "healthy", "detail": f"{len(critical)}/{len(critical)} colunas criticas presentes"}


def _check_bridge_whatsapp() -> Dict[str, Any]:
    """Checa Evolution API (porta 8080) + status da instancia ialex.

    Arquitetura atual: Docker Compose roda Evolution API (Baileys + Postgres + Redis).
    A 'bridge' Node.js antiga (porta 8090) foi descontinuada — checagem agora
    eh feita via WhatsAppBridge.check_connection() que bate em /instance/connectionState.
    """
    if _on_streamlit_cloud():
        return dict(_NA_CLOUD)
    try:
        from agent.whatsapp_bridge import WhatsAppBridge
        bridge = WhatsAppBridge()
        state = bridge.check_connection()
        if not state:
            return {
                "status": "critical",
                "detail": "Evolution API nao responde (porta 8080). Verifique 'docker compose up -d'.",
            }
        instance_state = state.get("state", state.get("instance", {}).get("state", "unknown"))
        if instance_state == "open":
            return {"status": "healthy", "detail": "WhatsApp conectado (Evolution API)"}
        elif instance_state == "connecting":
            return {
                "status": "degraded",
                "detail": "WhatsApp em conexao — aguarde alguns segundos e recarregue.",
            }
        elif instance_state in ("close", "closed"):
            return {
                "status": "critical",
                "detail": "WhatsApp desconectado. Acesse Evolution Manager (8080) e re-pareie a instancia 'ialex'.",
            }
        else:
            return {
                "status": "degraded",
                "detail": f"WhatsApp em estado desconhecido: {instance_state}",
            }
    except requests.exceptions.ConnectionError:
        return {
            "status": "critical",
            "detail": "Evolution API nao esta rodando (porta 8080). Rode 'docker compose up -d'.",
        }
    except Exception as e:
        return {"status": "unknown", "detail": f"erro ao checar Evolution API: {str(e)[:100]}"}


def _check_webhook_flask() -> Dict[str, Any]:
    """Checa webhook Flask do IAlex (porta 5001)."""
    if _on_streamlit_cloud():
        return dict(_NA_CLOUD)
    try:
        r = requests.get("http://localhost:5001/health", timeout=3)
        if r.status_code != 200:
            return {"status": "critical", "detail": f"webhook HTTP {r.status_code}"}
        return {"status": "healthy", "detail": "webhook respondendo"}
    except requests.exceptions.ConnectionError:
        return {"status": "critical", "detail": "webhook nao esta rodando (porta 5001)"}
    except Exception as e:
        return {"status": "unknown", "detail": f"erro ao checar webhook: {e}"}


def _check_brain_tools() -> Dict[str, Any]:
    """Verifica consistencia TOOLS vs TOOL_HANDLERS."""
    from agent import brain
    schemas = {t["name"] for t in brain.TOOLS if isinstance(t, dict) and "name" in t}
    handlers = set(brain.TOOL_HANDLERS.keys())
    missing_handlers = schemas - handlers
    missing_schemas = handlers - schemas
    if missing_handlers or missing_schemas:
        return {
            "status": "critical",
            "detail": f"inconsistencia: {len(missing_handlers)} sem handler, {len(missing_schemas)} sem schema",
            "meta": {
                "missing_handlers": list(missing_handlers),
                "missing_schemas": list(missing_schemas),
            },
        }
    return {"status": "healthy", "detail": f"{len(handlers)} tools consistentes"}


def _check_queue_state() -> Dict[str, Any]:
    """Fila de aprovacao: pending count + stuck items."""
    from database.supabase_client import db
    from datetime import timedelta

    pending = db.client.table("approval_queue").select("id", count="exact").eq("status", "pending").execute()
    pending_count = pending.count or 0

    # Stuck: em pending ha mais de 7 dias
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    stuck = db.client.table("approval_queue").select("id", count="exact").eq("status", "pending").lt("created_at", cutoff).execute()
    stuck_count = stuck.count or 0

    if stuck_count > 0:
        return {
            "status": "degraded",
            "detail": f"{pending_count} pendente(s), {stuck_count} stuck (>7 dias)",
            "meta": {"pending": pending_count, "stuck": stuck_count},
        }
    if pending_count > 100:
        return {
            "status": "degraded",
            "detail": f"fila grande: {pending_count} pendente(s)",
            "meta": {"pending": pending_count},
        }
    return {
        "status": "healthy",
        "detail": f"{pending_count} pendente(s), sem stuck",
        "meta": {"pending": pending_count, "stuck": 0},
    }


def _check_error_rate_1h() -> Dict[str, Any]:
    """Verifica tipos distintos de erros na ultima hora.
    Conta GRUPOS (mensagens normalizadas), nao ocorrencias brutas — porque
    um erro recorrente e 1 problema, nao 200.
    """
    from tools.log_parser import parse_recent_errors
    r = parse_recent_errors(hours=1, top_n=5)
    if "error" in r:
        return {"status": "unknown", "detail": r["error"]}
    total = r.get("in_window", 0)
    groups = len(r.get("top_errors", []))
    if total == 0:
        return {"status": "healthy", "detail": "0 erros na ultima 1h", "meta": r}
    if groups >= 5 or total > 100:
        return {
            "status": "critical",
            "detail": f"{total} erros ({groups} tipo(s) distintos) na ultima 1h",
            "meta": r,
        }
    if groups >= 3 or total > 20:
        return {
            "status": "degraded",
            "detail": f"{total} erros ({groups} tipo(s)) na ultima 1h",
            "meta": r,
        }
    return {
        "status": "healthy",
        "detail": f"{total} erro(s) ({groups} tipo(s)) na ultima 1h",
        "meta": r,
    }


def _check_error_rate_24h() -> Dict[str, Any]:
    """Verifica tipos distintos de erros nas ultimas 24h.
    Mesma logica do 1h: conta tipos agrupados pra evitar que um unico
    bug recorrente gere ruido de 'N erros' inflacionado.
    """
    from tools.log_parser import parse_recent_errors
    r = parse_recent_errors(hours=24, top_n=5)
    if "error" in r:
        return {"status": "unknown", "detail": r["error"]}
    total = r.get("in_window", 0)
    groups = len(r.get("top_errors", []))
    if total == 0:
        return {"status": "healthy", "detail": "0 erros em 24h", "meta": r}
    if groups >= 8 or total > 500:
        return {
            "status": "critical",
            "detail": f"{total} erros ({groups} tipo(s) distintos) em 24h",
            "meta": r,
        }
    if groups >= 5 or total > 100:
        return {
            "status": "degraded",
            "detail": f"{total} erros ({groups} tipo(s)) em 24h",
            "meta": r,
        }
    return {
        "status": "healthy",
        "detail": f"{total} erro(s) ({groups} tipo(s)) em 24h",
        "meta": r,
    }


def _check_api_quotas() -> Dict[str, Any]:
    """Verifica uso de APIs pagas vs limites."""
    from database.supabase_client import db
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    # Limites estimados (planos gratuitos)
    limits = {
        "apollo": 60,
        "hunter": 25,
        "snov": 50,
        "brevo": 300,
        # google_maps estava FORA de qualquer alerta de cota. O tier gratuito
        # da Google (~US$200/mes) da folga enorme, mas sem teto um loop podia
        # queimar credito sem ninguem ver. 200/dia = ~6.000/mes.
        "google_maps": 200,
    }
    usage = {}
    alerts: List[str] = []
    status = "healthy"
    for api_name, limit in limits.items():
        try:
            used = db.count_api_usage_since(api_name, cutoff) or 0
        except Exception:
            used = 0
        pct = (used / limit * 100) if limit > 0 else 0
        usage[api_name] = {"used": used, "limit": limit, "pct": round(pct, 1)}
        if pct >= 100:
            alerts.append(f"{api_name} 100% ({used}/{limit})")
            status = "critical"
        elif pct >= 80:
            alerts.append(f"{api_name} {pct:.0f}% ({used}/{limit})")
            if status == "healthy":
                status = "degraded"

    if status == "healthy":
        detail = "todas APIs abaixo de 80% do limite"
    else:
        detail = "; ".join(alerts)
    return {"status": status, "detail": detail, "meta": {"usage": usage}}


def _check_pipeline_config() -> Dict[str, Any]:
    """Verifica config de autonomia e pipeline automatico."""
    try:
        from integrations.pipeline_config import pipeline_config
        cfg = pipeline_config.get_config()
        level = cfg.get("autonomy_level", "semi_auto")
        if level == "full_auto":
            return {
                "status": "degraded",
                "detail": "modo full_auto — supervisao recomendada",
                "meta": {"autonomy_level": level},
            }
        return {
            "status": "healthy",
            "detail": f"autonomia: {level}",
            "meta": {"autonomy_level": level},
        }
    except Exception as e:
        return {"status": "unknown", "detail": f"pipeline_config indisponivel: {e}"}


# ============================================================================
# Orchestration
# ============================================================================

def run_health_check() -> Dict[str, Any]:
    """Executa todos os checks e retorna relatorio consolidado.

    Returns:
        Dict com campos overall, timestamp, checks (dict de resultados),
        summary (string curta), alerts (lista achatada dos problemas).
    """
    checks_order = [
        ("database", _check_database),
        ("schema_migrations", _check_schema_migrations),
        ("bridge_whatsapp", _check_bridge_whatsapp),
        ("webhook_flask", _check_webhook_flask),
        ("brain_tools", _check_brain_tools),
        ("queue_state", _check_queue_state),
        ("error_rate_1h", _check_error_rate_1h),
        ("error_rate_24h", _check_error_rate_24h),
        ("api_quotas", _check_api_quotas),
        ("pipeline_config", _check_pipeline_config),
    ]

    results: Dict[str, Any] = {}
    statuses: List[str] = []
    alerts: List[Dict[str, str]] = []

    for name, fn in checks_order:
        r = _safe_check(name, fn)
        results[name] = r
        statuses.append(r.get("status", "unknown"))
        if r.get("status") in ("degraded", "critical"):
            alerts.append({
                "check": name,
                "status": r["status"],
                "detail": r.get("detail", ""),
            })

    overall = _worst(statuses)

    # Summary curta pra UI
    n_crit = sum(1 for s in statuses if s == "critical")
    n_deg = sum(1 for s in statuses if s == "degraded")
    n_unk = sum(1 for s in statuses if s == "unknown")
    n_ok = sum(1 for s in statuses if s == "healthy")
    if overall == "healthy":
        summary = "sistema saudavel"
    elif overall == "critical":
        summary = f"{n_crit} critico(s), {n_deg} degradado(s)"
    elif overall == "degraded":
        summary = f"{n_deg} alerta(s) menor(es)"
    else:
        summary = f"{n_unk} check(s) indeterminado(s)"

    return {
        "overall": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": results,
        "summary": summary,
        "alerts": alerts,
        "stats": {
            "healthy": n_ok,
            "degraded": n_deg,
            "critical": n_crit,
            "unknown": n_unk,
            "total": len(statuses),
        },
    }


# ============================================================================
# Auto-healing (F6 Fase 3A)
# ============================================================================

def auto_heal(check_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Tenta remediar problemas detectados automaticamente.

    Estrategia conservadora: so age em casos de falha conhecida e com fix seguro.
    Para casos ambiguos, apenas notifica Fernando (nao mexe no sistema).

    Args:
        check_result: resultado de run_health_check(). Se None, executa o check.

    Returns:
        Dict com: healed (list), notified (list), skipped (list), overall_after (str)
    """
    import os

    if check_result is None:
        check_result = run_health_check()

    healed: List[Dict[str, str]] = []
    notified: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []

    checks = check_result.get("checks", {})

    # 1) Bridge WhatsApp critical → tenta restart via Evolution API
    bridge_check = checks.get("bridge_whatsapp", {})
    if bridge_check.get("status") == "critical":
        try:
            evo_url = os.getenv("EVOLUTION_URL", "http://localhost:8080").rstrip("/")
            api_key = os.getenv("EVOLUTION_API_KEY", "iaprendo-evolution-2026")
            resp = requests.post(
                f"{evo_url}/instance/restart/ialex",
                headers={"apikey": api_key},
                timeout=10,
            )
            if resp.status_code in (200, 201):
                healed.append({
                    "check": "bridge_whatsapp",
                    "action": "restart_ialex_instance",
                    "detail": "Instancia ialex restartada via Evolution API",
                })
                logger.info("Auto-heal: instancia ialex restartada")
            else:
                skipped.append({
                    "check": "bridge_whatsapp",
                    "reason": f"restart endpoint retornou HTTP {resp.status_code}",
                })
        except Exception as e:
            skipped.append({
                "check": "bridge_whatsapp",
                "reason": f"erro ao tentar restart: {str(e)[:100]}",
            })

    # 2) Webhook Flask critical → apenas notifica (nao pode auto-restart o proprio processo)
    webhook_check = checks.get("webhook_flask", {})
    if webhook_check.get("status") == "critical":
        notified.append({
            "check": "webhook_flask",
            "action": "notify_owner",
            "detail": "Webhook Flask caiu. Precisa restart manual do IAlex.",
        })

    # 3) Fila parada (>7 dias) → notifica Fernando
    queue_check = checks.get("queue_state", {})
    if queue_check.get("status") in ("degraded", "critical"):
        meta = queue_check.get("meta", {}) or {}
        stuck = meta.get("stuck_count", 0) if isinstance(meta, dict) else 0
        if stuck > 0:
            notified.append({
                "check": "queue_state",
                "action": "notify_stuck_queue",
                "detail": f"{stuck} emails na fila ha mais de 7 dias.",
            })

    # 4) Error rate 1h critical → notifica (nao mexe, precisa investigacao)
    err_1h = checks.get("error_rate_1h", {})
    if err_1h.get("status") == "critical":
        notified.append({
            "check": "error_rate_1h",
            "action": "notify_error_spike",
            "detail": err_1h.get("detail", "Pico de erros na ultima hora"),
        })

    # 5) API quota >90% → notifica (fallback ja existe no enricher)
    quota_check = checks.get("api_quotas", {})
    if quota_check.get("status") == "degraded":
        notified.append({
            "check": "api_quotas",
            "action": "notify_quota_warning",
            "detail": quota_check.get("detail", "Alguma API perto do limite"),
        })

    # Enviar notificacoes agregadas via WhatsApp (se houver)
    if notified:
        try:
            from agent.whatsapp_bridge import WhatsAppBridge
            owner = os.getenv("IALEX_OWNER_NUMBER", "")
            if owner:
                lines = ["🛡️ Auto-healing report:"]
                if healed:
                    lines.append("\n✅ Remediado automaticamente:")
                    for h in healed:
                        lines.append(f"  • {h['check']}: {h['detail']}")
                lines.append("\n⚠️ Precisa da sua atencao:")
                for n in notified:
                    lines.append(f"  • {n['check']}: {n['detail']}")
                if skipped:
                    lines.append("\n⏭️ Tentei remediar mas falhou:")
                    for s in skipped:
                        lines.append(f"  • {s['check']}: {s['reason']}")
                bridge = WhatsAppBridge()
                bridge.send_message(owner, "\n".join(lines))
        except Exception as e:
            logger.warning(f"Auto-heal: falha ao notificar owner: {e}")

    # Re-run health check se algo foi remediado, pra ver o estado apos fix
    overall_after = check_result.get("overall", "unknown")
    if healed:
        try:
            time.sleep(3)  # dar tempo do restart propagar
            new_result = run_health_check()
            overall_after = new_result.get("overall", overall_after)
        except Exception:
            pass

    return {
        "healed": healed,
        "notified": notified,
        "skipped": skipped,
        "overall_before": check_result.get("overall", "unknown"),
        "overall_after": overall_after,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import json as _json
    result = run_health_check()
    print(_json.dumps(result, indent=2, default=str))
    if result.get("overall") in ("degraded", "critical"):
        print("\n--- Triggering auto-heal ---")
        heal_result = auto_heal(result)
        print(_json.dumps(heal_result, indent=2, default=str))
