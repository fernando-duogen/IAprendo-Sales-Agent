"""
diagnose_email.py - Diagnostico completo do envio de email via Brevo.

Verifica configuracao, API key, sender, quota, mensagens pendentes,
e tenta enviar email de teste.

Uso: python scripts/diagnose_email.py [--send-test]
"""
import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import settings
from database.supabase_client import db
from tools.brevo_sender import brevo_sender
from utils.logger import logger


def diagnose(send_test: bool = False) -> None:
    """Executa todas as verificacoes de diagnostico."""
    print("=" * 60)
    print("DIAGNOSTICO DE ENVIO DE EMAIL (Brevo)")
    print("=" * 60)

    errors = []

    # 1. BREVO_API_KEY
    print("\n[1/6] Verificando BREVO_API_KEY...")
    api_key = getattr(settings, "BREVO_API_KEY", "")
    if api_key:
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"   OK: Configurada ({masked})")
    else:
        print("   ERRO: BREVO_API_KEY nao configurada no .env")
        errors.append("BREVO_API_KEY vazia")

    # 2. Sender email
    print("\n[2/6] Verificando sender email...")
    import os
    brevo_sender_email = os.getenv("BREVO_SENDER_EMAIL", "")
    your_email = settings.YOUR_EMAIL
    from_email = brevo_sender_email or your_email
    print(f"   BREVO_SENDER_EMAIL: {brevo_sender_email or '(nao configurado)'}")
    print(f"   YOUR_EMAIL: {your_email or '(nao configurado)'}")
    print(f"   Sera usado: {from_email}")
    if not from_email:
        errors.append("Nenhum email de remetente configurado")
    else:
        print(f"   IMPORTANTE: '{from_email}' deve estar verificado no Brevo!")
        print(f"   Verifique em: https://app.brevo.com/senders/list")

    # 3. brevo_sender habilitado
    print("\n[3/6] Verificando brevo_sender._enabled...")
    if brevo_sender._enabled:
        print("   OK: Brevo habilitado")
    else:
        print("   ERRO: Brevo desabilitado (API key ausente ou invalida)")
        errors.append("brevo_sender._enabled = False")

    # 4. Quota Brevo (valida API key)
    print("\n[4/6] Verificando quota Brevo (valida API key)...")
    if brevo_sender._enabled:
        quota = brevo_sender.check_quota()
        if quota.get("available"):
            plan_info = quota.get("plan", [])
            print(f"   OK: API key valida. Plano: {plan_info}")
        else:
            error = quota.get("error", quota.get("status_code", "desconhecido"))
            print(f"   ERRO: API key invalida ou problema de rede: {error}")
            errors.append(f"check_quota falhou: {error}")
    else:
        print("   PULADO (Brevo desabilitado)")

    # 5. Mensagens no banco
    print("\n[5/6] Verificando mensagens na approval_queue...")
    try:
        # Pendentes
        pending = db.client.table("approval_queue").select(
            "id", count="exact"
        ).eq("status", "pending").execute()
        pending_count = pending.count if pending.count is not None else len(pending.data or [])

        # Aprovadas nao enviadas
        approved = db.client.table("approval_queue").select(
            "id,contact_id", count="exact"
        ).eq("status", "approved").is_("sent_at", "null").execute()
        approved_count = approved.count if approved.count is not None else len(approved.data or [])

        # Enviadas
        sent = db.client.table("approval_queue").select(
            "id", count="exact"
        ).eq("status", "sent").execute()
        sent_count = sent.count if sent.count is not None else len(sent.data or [])

        print(f"   Pendentes (aguardando aprovacao): {pending_count}")
        print(f"   Aprovadas (aguardando envio):     {approved_count}")
        print(f"   Enviadas:                         {sent_count}")

        if approved_count == 0 and sent_count > 0:
            print("\n   ATENCAO: Todas as mensagens ja foram marcadas como 'sent'.")
            print("   Isso pode ter ocorrido por envio simulado (simulated=True).")
            print("   Verifique se os emails foram realmente enviados.")

        # Verificar aprovadas sem email
        if approved.data:
            sem_email = 0
            for msg in approved.data:
                cid = msg.get("contact_id")
                if cid:
                    try:
                        c = db.client.table("contacts").select("email").eq("id", cid).single().execute()
                        if not c.data or not c.data.get("email"):
                            sem_email += 1
                    except Exception:
                        sem_email += 1
                else:
                    sem_email += 1
            if sem_email > 0:
                print(f"\n   ATENCAO: {sem_email} mensagem(ns) aprovada(s) SEM email no contato.")
                print("   Essas serao puladas no envio. Adicione emails no dashboard.")

        # Verificar sent sem interaction (possivelmente simuladas)
        if sent_count > 0:
            try:
                interactions = db.client.table("interactions").select(
                    "id", count="exact"
                ).eq("type", "email_sent").execute()
                interaction_count = interactions.count if interactions.count is not None else len(interactions.data or [])
                if interaction_count < sent_count:
                    diff = sent_count - interaction_count
                    print(f"\n   ALERTA: {diff} mensagem(ns) 'sent' sem interaction registrada.")
                    print("   Possivel envio simulado (Brevo desabilitado).")
                    errors.append(f"{diff} mensagem(ns) possivelmente simuladas")
            except Exception:
                pass

    except Exception as e:
        print(f"   ERRO ao consultar banco: {e}")
        errors.append(f"Erro banco: {e}")

    # 6. Envio de teste
    print("\n[6/6] Envio de email de teste...")
    if send_test:
        if not brevo_sender._enabled:
            print("   ERRO: Nao e possivel enviar teste (Brevo desabilitado)")
        elif not your_email:
            print("   ERRO: YOUR_EMAIL nao configurado para receber teste")
        else:
            print(f"   Enviando para: {your_email}")
            result = brevo_sender.send_email(
                to_email=your_email,
                to_name=settings.YOUR_NAME,
                subject="[IAprendo] Teste de Diagnostico de Email",
                body="Este e um email de teste do sistema IAprendo.\n\nSe voce esta recebendo este email, o envio via Brevo esta funcionando corretamente.\n\nData do teste: " + __import__("datetime").datetime.now().isoformat(),
                queue_id=None,
            )
            if result.get("success"):
                print(f"   OK: Email enviado! Message ID: {result.get('message_id')}")
                print(f"   Verifique sua caixa de entrada (e spam) em: {your_email}")
            elif result.get("simulated"):
                print(f"   SIMULADO: Email NAO foi enviado (Brevo desabilitado)")
                errors.append("Envio teste simulado")
            else:
                print(f"   ERRO: {result.get('error', 'desconhecido')}")
                if result.get("status_code"):
                    print(f"   HTTP Status: {result.get('status_code')}")
                errors.append(f"Envio teste falhou: {result.get('error')}")
    else:
        print("   PULADO (use --send-test para enviar email de teste)")

    # Resumo
    print("\n" + "=" * 60)
    if errors:
        print(f"RESULTADO: {len(errors)} PROBLEMA(S) ENCONTRADO(S)")
        for i, err in enumerate(errors, 1):
            print(f"   {i}. {err}")
        print("\nAcoes sugeridas:")
        if any("API_KEY" in e for e in errors):
            print("   - Configure BREVO_API_KEY no arquivo .env")
        if any("simulad" in e.lower() for e in errors):
            print("   - Execute o fix em send_approved.py (remover simulated como sucesso)")
            print("   - Resete mensagens simuladas: UPDATE approval_queue SET status='approved', sent_at=NULL WHERE status='sent'")
        if any("check_quota" in e for e in errors):
            print("   - Verifique sua API key no dashboard Brevo: https://app.brevo.com/settings/keys/api")
    else:
        print("RESULTADO: TUDO OK!")
        if not send_test:
            print("   Execute com --send-test para confirmar envio real.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Diagnostico de envio de email via Brevo")
    parser.add_argument("--send-test", action="store_true", help="Envia email de teste para YOUR_EMAIL")
    args = parser.parse_args()
    diagnose(send_test=args.send_test)
