"""Smoke test CONTROLADO da Agenda/Metas (F1) contra o banco real.

Roda os criterios de aceitacao da SPEC §10 testaveis sem UI, usando dados
sinteticos prefixados (M-TEST-) com LIMPEZA GARANTIDA (try/finally).
Seguro para o banco unico (prod=dev): nao toca em nenhum dado existente.

Uso (apos aplicar APLICAR-019 no Supabase):
    venv\\Scripts\\python.exe scripts/smoke_agenda.py
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from workflows.activity_engine import run_engine, sweep_auto_resolution

MARK = f"M-TEST-{uuid.uuid4().hex[:6].upper()}"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))


def main():
    print(f"=== SMOKE AGENDA (marcador {MARK}) ===")
    company_id = None
    try:
        # 0) pre-requisito: tabelas existem
        db.client.table("activities").select("id").limit(1).execute()
        db.client.table("goals").select("id").limit(1).execute()
        print("  OK    migration 019 aplicada (activities/goals existem)")

        # escola sintetica
        company_id = db.insert_company({
            "name": f"{MARK} Escola Sintetica", "inep_code": MARK,
            "city": "Porto Alegre", "state": "RS", "status": "raw",
            "fonte_dados": "manual", "owner_username": "fernando",
        })
        check("escola sintetica criada", bool(company_id))

        # 1) dedupe: engine/insercao 2x nao duplica
        base = {
            "owner_username": "fernando", "type": "tarefa",
            "title": f"{MARK} tarefa de teste",
            "due_at": datetime.now(timezone.utc).isoformat(),
            "priority": 2, "source": "auto", "auto_rule": "smoke",
            "dedupe_key": f"smoke:{MARK}", "company_id": company_id,
        }
        a1 = db.create_activity(dict(base))
        a2 = db.create_activity(dict(base))  # mesmo dedupe_key
        check("idempotencia por dedupe_key (2a insercao = None)", bool(a1) and a2 is None)

        # 2) auto-resolucao: atividade 'responder' + outbound posterior -> done
        resp = db.create_activity({
            "owner_username": "fernando", "type": "responder",
            "title": f"{MARK} responder teste",
            "due_at": datetime.now(timezone.utc).isoformat(),
            "priority": 1, "source": "auto", "auto_rule": "reply_received",
            "dedupe_key": f"smoke-resp:{MARK}", "company_id": company_id,
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        })
        db.client.table("interactions").insert({
            "company_id": company_id, "type": "email_sent", "channel": "email",
            "subject": f"{MARK} outbound de teste",
        }).execute()
        sweep_auto_resolution()
        rows = db.client.table("activities").select("status,resolution") \
            .eq("id", resp["id"]).execute().data
        check("varredor auto-resolve 'responder' apos outbound",
              rows and rows[0]["status"] == "done"
              and rows[0]["resolution"] == "auto_trabalho_detectado",
              str(rows[0]) if rows else "sem linha")

        # 3) snooze max 3
        s = db.create_activity({
            "owner_username": "fernando", "type": "tarefa",
            "title": f"{MARK} snooze teste",
            "due_at": datetime.now(timezone.utc).isoformat(),
            "priority": 2, "source": "ialex",
            "dedupe_key": f"smoke-snz:{MARK}",
        })
        until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        oks = [db.snooze_activity(s["id"], until).get("ok") for _ in range(4)]
        check("snooze: 3 ok + 4o bloqueado", oks[:3] == [True, True, True] and oks[3] is False)

        # 4) trigger stage_changed: mudar etapa gera evento imutavel
        db.client.table("companies").update(
            {"commercial_stage": "proposta", "valor_mensal_proposto": 1234}
        ).eq("id", company_id).execute()
        ev = db.client.table("interactions").select("metadata") \
            .eq("company_id", company_id).eq("type", "stage_changed") \
            .execute().data or []
        check("trigger stage_changed gravou evento",
              any((e.get("metadata") or {}).get("to_stage") == "proposta" for e in ev),
              f"{len(ev)} eventos")

        # 5) metas: upsert + revision_log + realizado
        today = datetime.now(timezone.utc).date().replace(day=1).isoformat()
        nxt = (datetime.now(timezone.utc).date().replace(day=1) + timedelta(days=40)).replace(day=1)
        g1 = db.upsert_goal("smoke-test-user", "emails_enviados", today, 40, "smoke")
        g2 = db.upsert_goal("smoke-test-user", "emails_enviados", today, 50, "smoke",
                            reason="ajuste de teste")
        check("meta: upsert + revision_log",
              g1 is not None and g2 is not None and len(g2.get("revision_log") or []) == 2)

        # 6) run_engine roda ponta a ponta sem excecao (2x — idempotente)
        s1 = run_engine()
        s2 = run_engine()
        check("run_engine 2x sem excecao", isinstance(s1, dict) and isinstance(s2, dict),
              f"1a={s1} 2a={s2}")

    except Exception as e:
        check("EXCECAO INESPERADA", False, str(e)[:200])
    finally:
        # LIMPEZA TOTAL (try/finally — banco unico!)
        print("  ...limpando dados de teste")
        try:
            if company_id:
                db.client.table("companies").delete().eq("id", company_id).execute()
                # activities caem por CASCADE; interactions por CASCADE (FK)
            db.client.table("activities").delete().ilike("dedupe_key", f"%{MARK}%").execute()
            db.client.table("goals").delete().eq("username", "smoke-test-user").execute()
        except Exception as e:
            print(f"  AVISO: limpeza parcial: {e}")

    failed = [n for n, ok in results if not ok]
    print(f"\n=== RESULTADO: {len(results) - len(failed)}/{len(results)} PASS ===")
    if failed:
        print("FALHAS:", failed)
        sys.exit(1)


if __name__ == "__main__":
    main()
