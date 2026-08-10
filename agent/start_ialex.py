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
import socket
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import logger


def _check_port_in_use(port: int) -> bool:
    """Verifica se a porta ja esta em uso (outra instancia rodando)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return False  # porta livre
        except OSError:
            return True  # porta em uso


def check_evolution_api():
    """Verifica se Evolution API esta rodando."""
    from agent.whatsapp_bridge import WhatsAppBridge
    bridge = WhatsAppBridge()

    # Verificar conexao
    state = bridge.check_connection()
    if state.get("error"):
        logger.warning(f"Evolution API nao acessivel: {state.get('error')}")
        print("\n[AVISO] Evolution API nao esta rodando!")
        print("   Execute primeiro: docker compose up -d")
        print(f"   URL esperada: {bridge.base_url}")
        return False, bridge

    print(f"[OK] Evolution API conectada ({bridge.base_url})")
    instance_state = state.get("state", state.get("instance", {}).get("state", "unknown"))
    print(f"   Estado da instancia: {instance_state}")
    return True, bridge


def setup_instance(bridge):
    """Cria instancia e conecta WhatsApp se necessario."""
    state = bridge.check_connection()
    instance_state = state.get("state", state.get("instance", {}).get("state", ""))

    if instance_state == "open":
        print("[OK] WhatsApp ja conectado!")
        return True

    # Se state == "connecting", a instancia existe e esta estabilizando (container
    # recem-iniciado). Aguardar ate 30s antes de tentar criar — evita o ERROR 403
    # "instance already exists" quando so precisavamos esperar.
    if instance_state == "connecting":
        print("   Instancia existente em conexao, aguardando estabilizar...")
        for _ in range(6):  # 6 x 5s = 30s
            time.sleep(5)
            state = bridge.check_connection()
            instance_state = state.get("state", state.get("instance", {}).get("state", ""))
            if instance_state == "open":
                print("[OK] WhatsApp conectado (instancia preexistente)!")
                return True
            if instance_state not in ("connecting", ""):
                break  # estado terminal diferente de connecting, seguir fluxo normal

    # Criar instancia se nao existe
    print("\n[INFO] Configurando instancia WhatsApp...")
    create_result = bridge.create_instance()
    if create_result.get("error"):
        print(f"   Criando nova instancia... {create_result}")

    # Obter QR Code
    print("\n[INFO] Gerando QR Code para conectar WhatsApp...")
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
    print("\n[AGUARDANDO] Escanear o QR Code...")
    for i in range(60):  # 5 minutos de timeout
        time.sleep(5)
        state = bridge.check_connection()
        instance_state = state.get("state", state.get("instance", {}).get("state", ""))
        if instance_state == "open":
            print("\n[OK] WhatsApp conectado com sucesso!")
            return True
        if i % 6 == 0:
            print(f"   Ainda aguardando... ({i * 5}s)")

    print("\n[ERRO] Timeout: QR Code expirou. Reinicie o processo.")
    return False


def main():
    parser = argparse.ArgumentParser(description="IAlex - Agente Vendedor WhatsApp")
    parser.add_argument("--port", type=int, default=5001, help="Porta do webhook server")
    parser.add_argument("--no-scheduler", action="store_true", help="Nao iniciar scheduler")
    parser.add_argument("--debug", action="store_true", help="Modo debug")
    args = parser.parse_args()

    # Guard: impedir duas instancias rodando ao mesmo tempo
    if _check_port_in_use(args.port):
        print(f"[ERRO] Porta {args.port} ja esta em uso!")
        print("   Outra instancia do IAlex ja esta rodando.")
        print("   Encerre-a antes de iniciar novamente.")
        logger.error(f"IAlex start abortado: porta {args.port} ja em uso (instancia duplicada)")
        return

    print("=" * 50)
    print("  IAlex - Agente Vendedor IAprendo")
    print("=" * 50)
    print()

    # 1. Verificar Evolution API
    print("[1/6] Verificando Evolution API...")
    api_ok, bridge = check_evolution_api()

    if not api_ok:
        print("\nPara iniciar a Evolution API:")
        print("   cd agente-de-vendas")
        print("   docker compose up -d")
        print("   (aguarde ~30 segundos)")
        print("   Depois execute este script novamente.")
        return

    # 2. Setup instancia
    print("\n[2/6] Verificando instancia WhatsApp...")
    wa_ok = setup_instance(bridge)

    if not wa_ok:
        return

    # 2.5. Health-check REAL da sessao Baileys + auto-restart
    # A Evolution as vezes retorna state="open" mesmo com sessao Baileys morta
    # (Connection Closed silencioso). Esse check detecta e reinicia automatico.
    # Isso EVITA o cenario de "IAlex iniciado, mas nao responde nem manda boot".
    print("\n[2.5/6] Health-check da sessao Baileys (deteccao de 'Connection Closed' fantasma)...")
    for attempt in range(3):
        ping = bridge.ping_real()
        if ping.get("ok"):
            print("   [OK] Sessao Baileys saudavel — envio de mensagens vai funcionar.")
            break
        print(f"   [AVISO] Health-check falhou: {ping.get('error')}")
        if ping.get("needs_restart"):
            print(f"   [INFO] Reiniciando instancia (tentativa {attempt + 1}/3)...")
            if bridge.restart_instance():
                print("   [INFO] Aguardando 8s pra Baileys reconectar...")
                time.sleep(8)
                continue
            print("   [ERRO] Restart falhou.")
        if attempt == 2:
            print("   [AVISO] Health-check NAO recuperou apos 3 tentativas.")
            print("   Mensagens podem falhar com 'Connection Closed'.")
            print("   Tente: reiniciar docker compose ou re-escanear QR Code.")

    # 3. Webhook — ja configurado globalmente via docker-compose.yml
    # (WEBHOOK_GLOBAL_URL + WEBHOOK_GLOBAL_ENABLED). A chamada POST /webhook/set/{instance}
    # e redundante e retornava 400 no schema v2 da Evolution API, entao foi removida.
    print("\n[3/6] Webhook (configurado via compose env)")
    webhook_url = f"http://host.docker.internal:{args.port}/webhook"
    print(f"   Webhook: {webhook_url}")

    # 4. Iniciar scheduler
    if not args.no_scheduler:
        print("\n[4/6] Iniciando scheduler de mensagens proativas...")
        from agent.scheduler import ialex_scheduler
        ialex_scheduler.start()
        print("   Scheduler ativo (briefing 8h, check 13h, resumo 17h)")

    # 5. Enviar mensagem de teste
    owner = os.getenv("IALEX_OWNER_NUMBER", "")
    if owner:
        print(f"\n[5/6] Enviando mensagem de teste para {owner}...")
        bridge.send_message(owner, "*IAlex ativo!*\n\nEstou online e pronto para ajudar. Mande uma mensagem para comecar!\n\nComandos rapidos:\n- _'status'_ - resumo geral\n- _'pendentes'_ - emails para aprovar\n- _'pipeline 5'_ - rodar para 5 escolas\n- _'follow-ups'_ - verificar follow-ups")
        print("   Mensagem de teste enviada!")
    else:
        print("\n[AVISO] IALEX_OWNER_NUMBER nao configurado no .env")
        print("   Adicione: IALEX_OWNER_NUMBER=5551999999999")

    # 6. Iniciar webhook server
    print(f"\n[6/6] Iniciando webhook server na porta {args.port}...")
    print("=" * 50)
    print(f"  IAlex ONLINE - Webhook em http://localhost:{args.port}")
    print("  Mande uma mensagem no WhatsApp para testar!")
    print("  Pressione Ctrl+C para encerrar")
    print("=" * 50)

    from agent.webhook_server import start_server
    start_server(port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
