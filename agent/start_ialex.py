"""
IAlex - Starter principal.
Inicia todos os componentes:
1. Webhook server (recebe mensagens do WhatsApp)
2. Scheduler (mensagens proativas)
3. Verifica conexao com Evolution API
"""
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


def check_evolution_api():
    """Verifica se Evolution API esta rodando."""
    from agent.whatsapp_bridge import WhatsAppBridge
    bridge = WhatsAppBridge()

    # Verificar conexao
    state = bridge.check_connection()
    if state.get("error"):
        logger.warning(f"Evolution API nao acessivel: {state.get('error')}")
        print("\n⚠️  Evolution API nao esta rodando!")
        print("   Execute primeiro: docker compose up -d")
        print(f"   URL esperada: {bridge.base_url}")
        return False, bridge

    print(f"✅ Evolution API conectada ({bridge.base_url})")
    instance_state = state.get("state", state.get("instance", {}).get("state", "unknown"))
    print(f"   Estado da instancia: {instance_state}")
    return True, bridge


def setup_instance(bridge):
    """Cria instancia e conecta WhatsApp se necessario."""
    state = bridge.check_connection()
    instance_state = state.get("state", state.get("instance", {}).get("state", ""))

    if instance_state == "open":
        print("✅ WhatsApp ja conectado!")
        return True

    # Criar instancia se nao existe
    print("\n📱 Configurando instancia WhatsApp...")
    create_result = bridge.create_instance()
    if create_result.get("error"):
        print(f"   Criando nova instancia... {create_result}")

    # Obter QR Code
    print("\n📷 Gerando QR Code para conectar WhatsApp...")
    print("   Abra o WhatsApp no celular > Aparelhos conectados > Conectar aparelho")
    print("   Escaneie o QR Code que aparecera no terminal ou acesse:")
    print(f"   {bridge.base_url}/instance/connect/{bridge.instance_name}")
    print()

    qr = bridge.get_qr_code()
    if qr and isinstance(qr, dict) and qr.get("base64"):
        print("   QR Code disponivel! Acesse o link acima no navegador para escanear.")
    else:
        print(f"   Acesse: {bridge.base_url}/instance/connect/{bridge.instance_name}")

    # Aguardar conexao
    print("\n⏳ Aguardando voce escanear o QR Code...")
    for i in range(60):  # 5 minutos de timeout
        time.sleep(5)
        state = bridge.check_connection()
        instance_state = state.get("state", state.get("instance", {}).get("state", ""))
        if instance_state == "open":
            print("\n✅ WhatsApp conectado com sucesso!")
            return True
        if i % 6 == 0:
            print(f"   Ainda aguardando... ({i * 5}s)")

    print("\n❌ Timeout: QR Code expirou. Reinicie o processo.")
    return False


def main():
    parser = argparse.ArgumentParser(description="IAlex - Agente Vendedor WhatsApp")
    parser.add_argument("--port", type=int, default=5001, help="Porta do webhook server")
    parser.add_argument("--no-scheduler", action="store_true", help="Nao iniciar scheduler")
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    args = parser.parse_args()

    print("=" * 50)
    print("  🤖 IAlex - Agente Vendedor IAprendo")
    print("=" * 50)
    print()

    # 1. Verificar Evolution API
    print("1️⃣  Verificando Evolution API...")
    api_ok, bridge = check_evolution_api()

    if not api_ok:
        print("\n💡 Para iniciar a Evolution API:")
        print("   cd agente-de-vendas")
        print("   docker compose up -d")
        print("   (aguarde ~30 segundos)")
        print("   Depois execute este script novamente.")
        return

    # 2. Setup instancia
    print("\n2️⃣  Verificando instancia WhatsApp...")
    wa_ok = setup_instance(bridge)

    if not wa_ok:
        return

    # 3. Configurar webhook
    print("\n3️⃣  Configurando webhook...")
    webhook_url = f"http://host.docker.internal:{args.port}/webhook"
    bridge.set_webhook(webhook_url)
    print(f"   Webhook: {webhook_url}")

    # 4. Iniciar scheduler
    if not args.no_scheduler:
        print("\n4️⃣  Iniciando scheduler de mensagens proativas...")
        from agent.scheduler import ialex_scheduler
        ialex_scheduler.start()
        print("   ✅ Scheduler ativo (briefing 8h, check 12h, resumo 17h)")

    # 5. Enviar mensagem de teste
    owner = os.getenv("IALEX_OWNER_NUMBER", "")
    if owner:
        print(f"\n5️⃣  Enviando mensagem de teste para {owner}...")
        bridge.send_message(owner, "🤖 *IAlex ativo!*\n\nEstou online e pronto para ajudar. Mande uma mensagem para comecar!\n\nComandos rapidos:\n• _'status'_ - resumo geral\n• _'pendentes'_ - emails para aprovar\n• _'pipeline 5'_ - rodar para 5 escolas\n• _'follow-ups'_ - verificar follow-ups")
        print("   ✅ Mensagem de teste enviada!")
    else:
        print("\n⚠️  IALEX_OWNER_NUMBER nao configurado no .env")
        print("   Adicione: IALEX_OWNER_NUMBER=5551999999999")

    # 6. Iniciar webhook server
    print(f"\n6️⃣  Iniciando webhook server na porta {args.port}...")
    print("=" * 50)
    print(f"  🤖 IAlex ONLINE - Webhook em http://localhost:{args.port}")
    print("  📱 Mande uma mensagem no WhatsApp para testar!")
    print("  🛑 Pressione Ctrl+C para encerrar")
    print("=" * 50)

    from agent.webhook_server import start_server
    start_server(port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
