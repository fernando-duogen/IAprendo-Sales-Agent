"""
IAlex Webhook Server - Recebe mensagens do WhatsApp via Evolution API.
Roda como servidor Flask na porta 5001.
Processa mensagens recebidas e responde via IAlex brain + executor.
"""
import sys
import os
import json
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify
from utils.logger import logger

app = Flask(__name__)

# Componentes do IAlex (inicializados sob demanda)
_brain = None
_executor = None
_bridge = None


def get_brain():
    global _brain
    if _brain is None:
        from agent.brain import Brain
        _brain = Brain()
    return _brain


def get_executor():
    global _executor
    if _executor is None:
        from agent.executor import Executor
        _executor = Executor()
    return _executor


def get_bridge():
    global _bridge
    if _bridge is None:
        from agent.whatsapp_bridge import WhatsAppBridge
        _bridge = WhatsAppBridge()
    return _bridge


# Numero do dono (Fernando) - aceita numero ou LID
OWNER_NUMBER = os.getenv("IALEX_OWNER_NUMBER", "")
OWNER_LID = os.getenv("IALEX_OWNER_LID", "59824700190908")

# Controle de mensagens processadas (evitar duplicatas)
_processed_ids = set()
_MAX_PROCESSED = 1000


def _is_from_owner(sender: str) -> bool:
    """Verifica se a mensagem e do Fernando.
    Aceita numero de telefone (5551...) ou LID especifico do Fernando.
    """
    if not OWNER_NUMBER and not OWNER_LID:
        return True
    clean_sender = sender.replace("@s.whatsapp.net", "").replace("@lid", "")
    # Checar LID
    if OWNER_LID and clean_sender == OWNER_LID:
        return True
    # Checar numero
    if OWNER_NUMBER:
        digits_sender = "".join(c for c in clean_sender if c.isdigit())
        digits_owner = "".join(c for c in OWNER_NUMBER if c.isdigit())
        if digits_sender.endswith(digits_owner[-10:]):
            return True
    return False


def _extract_buttons(reply: str):
    """Extrai botoes de resposta rapida do texto.
    Formato: [BOTOES: Sim | Nao | Talvez] no final da mensagem.
    Retorna (texto_limpo, lista_botoes).
    """
    import re
    match = re.search(r'\[BOTOES:\s*(.+?)\]\s*$', reply)
    if match:
        buttons = [b.strip() for b in match.group(1).split("|") if b.strip()][:3]
        clean = reply[:match.start()].rstrip()
        return clean, buttons
    return reply, []


def _process_message_async(sender: str, text: str, msg_id: str):
    """Processa mensagem em thread separada para nao bloquear webhook."""
    try:
        logger.info("IAlex processando mensagem", extra={"sender": sender, "text": text[:100]})

        brain = get_brain()
        bridge = get_bridge()

        # Brain processa com tool use (consulta banco direto)
        result = brain.process_message(text, sender="fernando")
        full_reply = result.get("reply", "Desculpe, nao entendi. Pode reformular?")

        # Converter Markdown para formatacao WhatsApp
        import re
        full_reply = re.sub(r'\*\*(.+?)\*\*', r'*\1*', full_reply)  # **bold** → *bold*
        full_reply = re.sub(r'(?<!\[)#{1,3}\s+', '', full_reply)     # ## headers → remove

        # Extrair botoes de resposta rapida (se o Brain incluiu)
        full_reply, buttons = _extract_buttons(full_reply)

        # Enviar resposta via WhatsApp
        MAX_MSG_LEN = 4000
        if len(full_reply) > MAX_MSG_LEN:
            parts = []
            current = ""
            for line in full_reply.split("\n"):
                if len(current) + len(line) + 1 > MAX_MSG_LEN:
                    parts.append(current)
                    current = line
                else:
                    current += "\n" + line if current else line
            if current:
                parts.append(current)

            for i, part in enumerate(parts):
                if i == len(parts) - 1 and buttons:
                    bridge.send_buttons(sender, part.strip(), buttons)
                else:
                    bridge.send_message(sender, part.strip())
        elif buttons:
            bridge.send_buttons(sender, full_reply, buttons)
        else:
            bridge.send_message(sender, full_reply)

        logger.info("IAlex respondeu", extra={"reply_len": len(full_reply), "buttons": len(buttons)})

    except Exception as e:
        logger.error("Erro ao processar mensagem IAlex", extra={"error": str(e)})
        try:
            bridge = get_bridge()
            bridge.send_message(sender, f"Ops, tive um erro interno. Tente novamente. ({str(e)[:50]})")
        except Exception:
            pass


@app.route("/webhook", methods=["POST"])
def webhook():
    """Recebe eventos do Baileys bridge ou Evolution API."""
    try:
        data = request.json or {}
        event = data.get("event", "")

        # Processar apenas mensagens recebidas
        if event == "messages.upsert":
            msg = data.get("data", {})

            # Ignorar mensagens enviadas por nos
            if msg.get("key", {}).get("fromMe", False):
                return jsonify({"status": "ok"}), 200

            msg_id = msg.get("key", {}).get("id", "")

            # Evitar duplicatas
            if msg_id in _processed_ids:
                return jsonify({"status": "ok"}), 200
            _processed_ids.add(msg_id)
            if len(_processed_ids) > _MAX_PROCESSED:
                _processed_ids.clear()

            # Extrair remetente (preservar JID completo para reply)
            sender_jid = msg.get("sender", msg.get("key", {}).get("remoteJid", ""))
            sender = sender_jid.replace("@s.whatsapp.net", "").replace("@lid", "")

            # Verificar se e do dono
            if not _is_from_owner(sender):
                logger.warning("Mensagem de numero nao autorizado", extra={"sender": sender})
                return jsonify({"status": "ok"}), 200

            # Determinar tipo de mensagem
            msg_type = msg.get("messageType", "text")

            # === LOCATION MESSAGE ===
            if msg_type == "location" and msg.get("location"):
                loc = msg["location"]
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                loc_name = loc.get("name", "")
                text = f"Estou em {loc_name + ', ' if loc_name else ''}coordenadas {lat}, {lng}. Quais escolas tem perto de mim num raio de 2km?"
                logger.info("Localizacao recebida", extra={"lat": lat, "lng": lng})

            # === AUDIO MESSAGE ===
            elif msg_type == "audio" and msg.get("audio"):
                audio_data = msg["audio"]
                try:
                    import base64
                    import tempfile
                    from openai import OpenAI

                    audio_bytes = base64.b64decode(audio_data["buffer"])
                    ext = "ogg" if "ogg" in audio_data.get("mimetype", "") else "mp3"

                    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as f:
                        f.write(audio_bytes)
                        temp_path = f.name

                    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    with open(temp_path, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="pt",
                        )
                    text = transcription.text
                    logger.info("Audio transcrito", extra={"text": text[:100], "seconds": audio_data.get("seconds")})

                    # Limpar arquivo temporário
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

                except Exception as e:
                    logger.error(f"Erro ao transcrever audio: {e}")
                    bridge = get_bridge()
                    bridge.send_message(sender_jid, "Nao consegui transcrever o audio. Pode digitar?")
                    return jsonify({"status": "ok"}), 200

            # === TEXT MESSAGE ===
            else:
                text = msg.get("text", "")
                if not text:
                    message_content = msg.get("message", {})
                    if message_content.get("conversation"):
                        text = message_content["conversation"]
                    elif message_content.get("extendedTextMessage", {}).get("text"):
                        text = message_content["extendedTextMessage"]["text"]

            if not text:
                return jsonify({"status": "ok"}), 200

            # Processar em thread separada — usar JID completo para reply
            thread = threading.Thread(
                target=_process_message_async,
                args=(sender_jid, text, msg_id),
                daemon=True,
            )
            thread.start()

        elif event == "connection.update":
            state = data.get("data", {}).get("state", "")
            logger.info(f"WhatsApp connection: {state}")

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        logger.error("Erro no webhook", extra={"error": str(e)})
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    return jsonify({
        "status": "ok",
        "agent": "IAlex",
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/send", methods=["POST"])
def send_manual():
    """Endpoint para enviar mensagem manualmente (debug)."""
    data = request.json or {}
    number = data.get("number", OWNER_NUMBER)
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "text required"}), 400

    bridge = get_bridge()
    result = bridge.send_message(number, text)
    return jsonify(result)


def _start_scheduler():
    """Inicia o scheduler de briefings proativos em background."""
    try:
        from agent.scheduler import ialex_scheduler
        ialex_scheduler.start()
        logger.info("Scheduler de briefings proativos iniciado")
    except Exception as e:
        logger.warning(f"Scheduler nao iniciou (nao critico): {e}")


def start_server(port: int = 5001, debug: bool = False):
    """Inicia o servidor webhook + scheduler."""
    logger.info(f"IAlex webhook server starting on port {port}")
    _start_scheduler()
    app.run(host="0.0.0.0", port=port, debug=debug)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IAlex Webhook Server")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    start_server(port=args.port, debug=args.debug)
