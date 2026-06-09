"""
preflight_check.py — Checklist de PRONTIDAO PRA VENDER (pre-voo de lancamento).

Roda verificacoes READ-ONLY (nao envia email, nao escreve no banco) e imprime
um relatorio OK/FALHA/AVISO dos itens criticos pra operar com os 3 usuarios:

  1. Chaves/env (LLMs, Brevo, Supabase, HubSpot, Google)
  2. Brevo: conta + quota + senders verificados pros 3 emails (BLOQUEADOR)
  3. Usuarios: 3 perfis carregam com email/assinatura/whatsapp
  4. Templates: existem + cobertura da matriz (auto por alvo)
  5. Schema: colunas criticas das migrations aplicadas

Uso:  venv\\Scripts\\python.exe scripts\\preflight_check.py
Segredos sao mascarados. Nada e enviado/alterado.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

OK, FAIL, WARN = "[ OK ]", "[FALHA]", "[AVISO]"
_results = {"ok": 0, "fail": 0, "warn": 0}


def line(tag, msg):
    _results["ok" if tag == OK else "fail" if tag == FAIL else "warn"] += 1
    print(f"  {tag}  {msg}")


def section(title):
    print(f"\n=== {title} ===")


def mask(v):
    if not v:
        return "(vazio)"
    s = str(v)
    return f"SET (...{s[-4:]})" if len(s) > 4 else "SET"


def main():
    print("=" * 64)
    print("  PRE-VOO DE LANCAMENTO - IAprendo Sales Agent")
    print("=" * 64)

    from config.settings import settings

    # ----------------------------------------------------------------- 1) ENV
    section("1) Chaves / ambiente")
    # OpenAI eh o backend LLM ATIVO (base_agent escolhe OpenAI se a chave existir;
    # Anthropic eh so fallback). Por isso OPENAI eh required e ANTHROPIC opcional.
    required = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL") or getattr(settings, "SUPABASE_URL", ""),
        "SUPABASE_KEY": os.getenv("SUPABASE_KEY") or getattr(settings, "SUPABASE_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),   # LLM ativo (brain + writer + qualifier)
        "BREVO_API_KEY": getattr(settings, "BREVO_API_KEY", ""),
    }
    for k, v in required.items():
        line(OK if v else FAIL, f"{k}: {mask(v)}")

    optional = {
        "ANTHROPIC_API_KEY": getattr(settings, "ANTHROPIC_API_KEY", ""),  # fallback do OpenAI (nao usado se OpenAI setado)
        "BREVO_SENDER_EMAIL": os.getenv("BREVO_SENDER_EMAIL", ""),
        "HUBSPOT_API_KEY": getattr(settings, "HUBSPOT_API_KEY", ""),
        "HUBSPOT_MEETING_LINK": getattr(settings, "HUBSPOT_MEETING_LINK", ""),
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    }
    for k, v in optional.items():
        line(OK if v else WARN, f"{k} (opcional): {mask(v) if v else '(nao setado)'}")

    # ------------------------------------------------------------- 2) USUARIOS
    section("2) Usuarios (multi-user)")
    from utils.sender_profile import list_profiles
    profiles = list_profiles()
    user_emails = []
    if len(profiles) < 1:
        line(FAIL, "Nenhum perfil carregado de config/users.yaml")
    else:
        line(OK if len(profiles) >= 3 else WARN, f"{len(profiles)} perfis carregados")
        for p in profiles:
            faltando = [f for f in ("email", "email_sender_name", "phone") if not p.get(f)]
            wa = len(p.get("whatsapp_numbers") or [])
            if p.get("email"):
                user_emails.append(p["email"])
            tag = OK if (not faltando and wa) else WARN
            line(tag, f"{p.get('username')}: email={p.get('email') or '?'} | "
                      f"sender_name={'ok' if p.get('email_sender_name') else 'FALTA'} | "
                      f"wa={wa} num(s)"
                      + (f" | FALTA: {faltando}" if faltando else ""))

    # ---------------------------------------------------------------- 3) BREVO
    section("3) Brevo (conta, quota, senders verificados)")
    try:
        from tools.brevo_sender import brevo_sender
        if not brevo_sender._enabled:
            line(FAIL, "BREVO_API_KEY ausente — envio desabilitado")
        else:
            q = brevo_sender.check_quota()
            if q.get("available"):
                line(OK, "Conta Brevo acessivel")
                for plan in (q.get("plan") or []):
                    if isinstance(plan, dict) and "credits" in plan:
                        line(OK, f"   plano={plan.get('type')} credits={plan.get('credits')}")
            else:
                line(FAIL, f"Conta Brevo inacessivel: {q.get('error') or q.get('status_code')}")

            # Senders verificados — checar os 3 emails dos usuarios (BLOQUEADOR)
            import requests
            resp = requests.get(f"{brevo_sender.BASE_URL}/senders",
                                headers={"api-key": brevo_sender.api_key}, timeout=15)
            if resp.status_code == 200:
                senders = resp.json().get("senders", [])
                verified = {s["email"].lower() for s in senders if s.get("active")}
                line(OK, f"Senders verificados no Brevo: {sorted(verified)}")
                for em in user_emails:
                    ok = em.lower() in verified
                    line(OK if ok else FAIL,
                         f"   sender '{em}' {'VERIFICADO' if ok else 'NAO verificado -> emails desse usuario VAO FALHAR'}")
            else:
                line(WARN, f"Nao consegui listar senders (HTTP {resp.status_code})")
    except Exception as e:
        line(FAIL, f"Erro no check Brevo: {str(e)[:160]}")

    # ------------------------------------------------------------ 4) TEMPLATES
    section("4) Templates de email (matriz auto por alvo)")
    try:
        from database.supabase_client import db
        tpls = db.client.table("message_templates").select(
            "id,name,audience_type,data_profile,is_default").execute().data or []
        # tabela nao tem coluna channel — tratar todos como email
        email_tpls = tpls
        line(OK if email_tpls else FAIL, f"{len(email_tpls)} template(s) cadastrados")
        has_default = any(t.get("is_default") for t in email_tpls)
        line(OK if has_default else WARN, f"template padrao definido: {has_default}")
        classed = [t for t in email_tpls if t.get("audience_type") and t.get("data_profile")]
        line(OK if classed else WARN,
             f"{len(classed)} template(s) com alvo classificado (audience+dados) p/ selecao automatica")
        combos = {(t["audience_type"], t["data_profile"]) for t in classed}
        if ("nominal", "ambos") in combos:
            line(OK, "   combo IDEAL presente: nominal + ambos (matriculas+ENEM)")
        else:
            line(WARN, "   combo IDEAL ausente: nominal + ambos")
        if any(a == "generico" for a, _ in combos):
            line(OK, "   fallback generico presente")
        else:
            line(WARN, "   fallback generico ausente (recomendado p/ escolas sem dados)")
    except Exception as e:
        line(WARN, f"Nao consegui checar templates: {str(e)[:160]}")

    # --------------------------------------------------------------- 5) SCHEMA
    section("5) Schema (colunas das migrations)")
    from database.supabase_client import db
    checks = [
        ("companies", "owner_username,owner_assigned_at,phone_whatsapp,commercial_stage,valor_mensal_fechado"),
        ("interactions", "created_by"),
        ("approval_queue", "created_by,chart_urls"),
        ("message_templates", "audience_type,data_profile"),
        ("mec_catalog", "inep_code,name_norm"),
    ]
    for table, cols in checks:
        try:
            db.client.table(table).select(cols).limit(1).execute()
            line(OK, f"{table}: colunas OK ({cols})")
        except Exception as e:
            line(FAIL, f"{table}: FALTA coluna -> {str(e)[:120]}")

    # ---------------------------------------------------------------- RESUMO
    print("\n" + "=" * 64)
    print(f"  RESUMO: {_results['ok']} OK | {_results['warn']} avisos | {_results['fail']} falhas")
    print("=" * 64)
    if _results["fail"]:
        print("  -> Ha FALHAS que bloqueiam o lancamento. Veja [FALHA] acima.")
    elif _results["warn"]:
        print("  -> Sem bloqueadores. Avisos sao melhorias recomendadas.")
    else:
        print("  -> Tudo pronto pra vender. 🚀")


if __name__ == "__main__":
    main()
