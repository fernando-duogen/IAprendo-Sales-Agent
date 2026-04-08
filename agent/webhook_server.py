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


# Numeros autorizados — separados por virgula no .env
# Ex: IALEX_AUTHORIZED_NUMBERS=5551996422564,5551981081786
OWNER_NUMBER = os.getenv("IALEX_OWNER_NUMBER", "")
OWNER_LID = os.getenv("IALEX_OWNER_LID", "59824700190908")
AUTHORIZED_NUMBERS = os.getenv("IALEX_AUTHORIZED_NUMBERS", "")

# Controle de mensagens processadas (evitar duplicatas)
_processed_ids = set()
_MAX_PROCESSED = 1000


def _get_authorized_numbers() -> list:
    """Retorna lista de numeros autorizados (ultimos 10 digitos de cada)."""
    numbers = []
    if OWNER_NUMBER:
        numbers.append("".join(c for c in OWNER_NUMBER if c.isdigit())[-10:])
    if AUTHORIZED_NUMBERS:
        for n in AUTHORIZED_NUMBERS.split(","):
            digits = "".join(c for c in n.strip() if c.isdigit())
            if len(digits) >= 8:
                numbers.append(digits[-10:])
    return numbers


def _is_from_owner(sender: str) -> bool:
    """Verifica se a mensagem e de um numero autorizado.
    Aceita numero de telefone (5551...) ou LID.
    """
    authorized = _get_authorized_numbers()
    if not authorized and not OWNER_LID:
        return True
    clean_sender = sender.replace("@s.whatsapp.net", "").replace("@lid", "")
    # Checar LID
    if OWNER_LID and clean_sender == OWNER_LID:
        return True
    # Checar numeros autorizados
    digits_sender = "".join(c for c in clean_sender if c.isdigit())
    for auth_num in authorized:
        if digits_sender.endswith(auth_num):
            return True
    return False


def _build_field_mode_briefing(lat: float, lng: float) -> str:
    """Modo campo: busca escola mais proxima no banco e monta briefing
    instantaneo com diretor, score, ultimo contato e pitch de 30 segundos.
    Retorna string formatada para WhatsApp ou '' se nada encontrado."""
    import math
    from database.supabase_client import db

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    try:
        schools = db.client.table("companies").select(
            "id,name,city,state,admin_category,school_size,qualification_score,"
            "qualification_reasoning,education_levels,phone,latitude,longitude,status"
        ).not_.is_("latitude", "null").not_.is_("longitude", "null").execute().data or []
    except Exception:
        return ""

    if not schools:
        return ""

    for s in schools:
        try:
            s["_dist"] = _haversine(lat, lng, float(s["latitude"]), float(s["longitude"]))
        except Exception:
            s["_dist"] = 99999

    schools.sort(key=lambda x: x["_dist"])
    nearby = [s for s in schools[:10] if s["_dist"] <= 2.0]  # apenas ate 2km
    if not nearby:
        return ""  # nenhuma escola proxima — nao enviar briefing

    closest = nearby[0]
    company_id = closest["id"]
    dist_m = int(closest["_dist"] * 1000)

    # Contatos (diretor primeiro)
    contacts = []
    try:
        contacts = db.client.table("contacts").select(
            "full_name,role,email,decision_maker_type,phone"
        ).eq("company_id", company_id).order("outreach_priority").limit(5).execute().data or []
    except Exception:
        pass

    diretor = None
    for c in contacts:
        if c.get("decision_maker_type") == "diretor":
            diretor = c
            break
    if not diretor and contacts:
        diretor = contacts[0]

    # Ultimo contato
    ultimo_contato = "Nenhum email enviado"
    try:
        last = db.client.table("approval_queue").select(
            "sent_at,opened_at,clicked_at,replied_at"
        ).eq("company_id", company_id).eq("status", "sent").order(
            "sent_at", desc=True
        ).limit(1).execute().data or []
        if last:
            e = last[0]
            sent_date = (e.get("sent_at") or "")[:10]
            t = "respondeu" if e.get("replied_at") else ("clicou" if e.get("clicked_at") else ("abriu" if e.get("opened_at") else "enviado"))
            ultimo_contato = f"{sent_date} — {t}"
    except Exception:
        pass

    # Insights
    insights = []
    try:
        from integrations.memory import memory
        mems = memory.get_for("company", company_id, limit=3)
        insights = [m.get("content", "")[:80] for m in mems if m.get("content")]
    except Exception:
        pass

    # Montar briefing
    school_name = closest.get("name", "?")
    score = closest.get("qualification_score") or "?"
    porte = closest.get("school_size") or "?"
    tipo = closest.get("admin_category") or "?"
    phone = closest.get("phone") or ""

    lines = [
        f"📍 *MODO CAMPO — Escola a {dist_m}m*",
        "",
        f"🏫 *{school_name}*",
        f"📍 {closest.get('city', '')} | 🎯 Score: {score} | 📊 {porte}",
        f"📋 {tipo}",
    ]
    if phone:
        lines.append(f"📞 {phone}")

    lines.append("")
    if diretor:
        lines.append(f"👤 *{diretor.get('full_name', '?')}* — {diretor.get('role', '?')}")
        if diretor.get("email"):
            lines.append(f"📧 {diretor['email']}")
    else:
        lines.append("👤 _Diretor(a) nao identificado(a)_")

    lines.append("")
    lines.append(f"📧 *Ultimo contato:* {ultimo_contato}")

    if insights:
        lines.append("")
        lines.append("💡 *Insights:*")
        for ins in insights[:3]:
            lines.append(f"• {ins}")

    # Pitch
    pitch_foco = "ROI e diferencial" if "privada" in tipo.lower() else "BNCC e impacto"
    lines.append("")
    lines.append(f"🎯 *Pitch 30s:* _foque em {pitch_foco}_")
    dir_nome = diretor.get("full_name", "").split()[0] if diretor else "Diretor(a)"
    lines.append(
        f'_"Oi {dir_nome}, sou Fernando da IAprendo. '
        f'Temos uma plataforma 100% BNCC que melhora desempenho em 30%. '
        f'Posso mostrar em 2 minutos?"_'
    )

    # Outras proximas
    if len(nearby) > 1:
        lines.append("")
        lines.append(f"📍 *+{len(nearby)-1} escola(s) proxima(s):*")
        for s in nearby[1:5]:
            d = int(s["_dist"] * 1000)
            lines.append(f"• {s.get('name', '?')} ({d}m)")

    lines.append("")
    lines.append("1️⃣ Gerar email")
    lines.append("2️⃣ Registrar visita")
    lines.append("3️⃣ Ver detalhes")
    lines.append("4️⃣ Mais escolas no raio")
    lines.append("📋 _\"menu\" para mais_")

    return "\n".join(lines)


def _send_with_buttons(bridge, sender: str, text: str, buttons: list):
    """Tenta enviar com botoes nativos. Se falhar, envia texto com opcoes numeradas."""
    result = bridge.send_buttons(sender, text, buttons)
    if result.get("success"):
        return
    # Fallback: texto com opcoes numeradas
    num_emojis = ["1️⃣", "2️⃣", "3️⃣"]
    opts = "\n".join(f"{num_emojis[i]} {b}" for i, b in enumerate(buttons[:3]))
    fallback_text = f"{text}\n\n{opts}\n\n_Responda com o numero ou texto da opcao_"
    bridge.send_message(sender, fallback_text)


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
                    _send_with_buttons(bridge, sender, part.strip(), buttons)
                else:
                    bridge.send_message(sender, part.strip())
        elif buttons:
            _send_with_buttons(bridge, sender, full_reply, buttons)
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

            # === LOCATION MESSAGE — MODO CAMPO + OPCOES ===
            if msg_type == "location" and msg.get("location"):
                loc = msg["location"]
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                loc_name = loc.get("name", "")
                logger.info("Localizacao recebida", extra={"lat": lat, "lng": lng})

                # Tentar briefing modo campo (escola proxima no banco)
                campo_reply = ""
                try:
                    campo_reply = _build_field_mode_briefing(lat, lng)
                except Exception as e:
                    logger.debug(f"Modo campo skip: {e}")

                # Montar mensagem completa: briefing (se houver) + opcoes
                loc_desc = f"{loc_name}, " if loc_name else ""
                text = (
                    f"[LOCALIZACAO RECEBIDA] {loc_desc}coordenadas {lat}, {lng}. "
                    f"Fernando compartilhou sua localizacao."
                )

                briefing_sent = False
                if campo_reply:
                    try:
                        bridge = get_bridge()
                        result = bridge.send_message(sender, campo_reply)
                        if result.get("success") or result.get("key"):
                            briefing_sent = True
                            logger.info("Modo campo: briefing enviado")
                    except Exception as e:
                        logger.error(f"Modo campo send erro: {e}")

                if briefing_sent:
                    text += (
                        " Ja enviei o briefing da escola mais proxima acima. "
                        "Agora pergunte se Fernando quer algo mais com essa escola ou "
                        "se quer buscar outras escolas proximas."
                    )
                else:
                    # Sem escola proxima no banco — perguntar o que quer
                    text += (
                        " Pergunte o que ele quer fazer: "
                        "buscar escolas proximas (e em qual raio), buscar no banco ou na base "
                        "completa do MEC, filtrar por tipo (privada/publica), ou outra coisa."
                    )

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
