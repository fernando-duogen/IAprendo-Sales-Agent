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
# Ex: IALEX_AUTHORIZED_LIDS=59824700190908,12345678901234
OWNER_NUMBER = os.getenv("IALEX_OWNER_NUMBER", "")
OWNER_LID = os.getenv("IALEX_OWNER_LID", "")
AUTHORIZED_NUMBERS = os.getenv("IALEX_AUTHORIZED_NUMBERS", "")
AUTHORIZED_LIDS = os.getenv("IALEX_AUTHORIZED_LIDS", "")

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


def _get_authorized_lids() -> list:
    """Retorna lista de LIDs (WhatsApp Linked ID) autorizados."""
    lids = []
    if OWNER_LID:
        lids.append(OWNER_LID.strip())
    if AUTHORIZED_LIDS:
        for lid in AUTHORIZED_LIDS.split(","):
            lid_clean = lid.strip()
            if lid_clean:
                lids.append(lid_clean)
    return lids


def _try_match_school_reply(sender: str, sender_jid: str, text: str) -> dict:
    """Tenta identificar se uma mensagem recebida eh reply de uma escola.

    Criterios:
    1. Extrai os ultimos 9 digitos do sender
    2. Busca contacts com phone_whatsapp terminando nesses digitos
    3. Exige approval_queue.sent_at do canal whatsapp <= 7 dias atras
       para o mesmo company_id (mitigacao de spoofing)

    Returns:
        Dict com {company_id, contact_id, contact_name, school_name, queue_id}
        se for reply valida, ou {} se nao for.
    """
    from database.supabase_client import db
    from datetime import datetime, timezone, timedelta

    clean_sender = sender_jid.replace("@s.whatsapp.net", "").replace("@lid", "")
    digits = "".join(c for c in clean_sender if c.isdigit())
    if len(digits) < 9:
        return {}
    tail = digits[-9:]

    try:
        contacts = db.client.table("contacts").select(
            "id,full_name,phone_whatsapp,company_id"
        ).not_.is_("phone_whatsapp", "null").execute().data or []
    except Exception as e:
        logger.debug(f"school_reply contacts query erro: {e}")
        return {}

    match_contact = None
    for c in contacts:
        wpp = "".join(ch for ch in (c.get("phone_whatsapp") or "") if ch.isdigit())
        if wpp and wpp.endswith(tail):
            match_contact = c
            break

    if not match_contact:
        return {}

    company_id = match_contact.get("company_id")
    if not company_id:
        return {}

    # Mitigacao de spoofing: exige whatsapp enviado <= 7 dias
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        recent = db.client.table("approval_queue").select(
            "id,sent_at,subject"
        ).eq("company_id", company_id).eq("channel", "whatsapp").eq(
            "status", "sent"
        ).gte("sent_at", cutoff).order("sent_at", desc=True).limit(1).execute().data or []
    except Exception as e:
        logger.debug(f"school_reply approval_queue query erro: {e}")
        return {}

    if not recent:
        logger.info(
            "Possivel reply de escola sem sent recente — ignorando",
            extra={"sender": clean_sender, "company_id": company_id}
        )
        return {}

    queue_id = recent[0].get("id")

    # Buscar nome da escola
    school_name = ""
    try:
        comp = db.client.table("companies").select("name").eq(
            "id", company_id
        ).single().execute()
        school_name = (comp.data or {}).get("name", "")
    except Exception:
        pass

    return {
        "company_id": company_id,
        "contact_id": match_contact.get("id"),
        "contact_name": match_contact.get("full_name") or "",
        "school_name": school_name,
        "queue_id": queue_id,
    }


def _handle_school_reply(match: dict, text: str, sender_jid: str) -> None:
    """Processa reply de escola SEM responder automaticamente.

    1. Atualiza approval_queue.replied_at
    2. Insere interaction (type=whatsapp_replied)
    3. Captura memoria (memory_capture com channel=whatsapp)
    4. Notifica Fernando (NAO responde pra escola)

    IAlex NUNCA responde automaticamente a escola. Fernando decide
    se quer gerar uma sugestao manualmente.
    """
    from database.supabase_client import db
    from datetime import datetime, timezone

    company_id = match["company_id"]
    contact_id = match.get("contact_id")
    queue_id = match.get("queue_id")
    school_name = match.get("school_name") or "escola"
    contact_name = match.get("contact_name") or "contato"

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Marcar replied_at na fila
    try:
        db.client.table("approval_queue").update({
            "replied_at": now_iso,
        }).eq("id", queue_id).execute()
    except Exception as e:
        logger.error(f"Erro ao marcar replied_at: {e}")

    # 2. Registrar interacao
    try:
        db.insert_interaction({
            "company_id": company_id,
            "contact_id": contact_id,
            "type": "whatsapp_replied",
            "channel": "whatsapp",
            "subject": f"Reply via WhatsApp de {contact_name}",
            "content": text[:2000],
            "metadata": {"queue_id": queue_id, "sender_jid": sender_jid},
        })
    except Exception as e:
        logger.error(f"Erro ao inserir interaction: {e}")

    # 3. Capturar memoria (lead quente)
    try:
        from tools.memory_capture import memory_capture
        memory_capture.capture_email_event(
            company_id=company_id,
            contact_id=contact_id,
            event_type="replied",
            metadata={"reply_text": text[:500]},
            channel="whatsapp",
        )
    except Exception as e:
        logger.debug(f"memory_capture skip: {e}")

    # 4. Notificar Fernando — NUNCA responde a escola
    try:
        bridge = get_bridge()
        owner_num = os.getenv("IALEX_OWNER_NUMBER", "")
        owner_lid = os.getenv("IALEX_OWNER_LID", "")
        dest = owner_num
        if owner_lid and not owner_num:
            dest = f"{owner_lid}@lid"

        if dest:
            first = contact_name.split()[0] if contact_name else "contato"
            preview = text[:500] + ("..." if len(text) > 500 else "")
            notify = (
                f"🔥 *Lead quente* — resposta no WhatsApp\n\n"
                f"🏫 {school_name}\n"
                f"👤 {first}\n\n"
                f"💬 _\"{preview}\"_\n\n"
                f"_Quer que eu sugira uma resposta? (diga 'sugerir resposta WhatsApp pro {school_name}')_"
            )
            bridge.send_message(dest, notify)
    except Exception as e:
        logger.error(f"Erro ao notificar Fernando sobre reply: {e}")

    logger.info(
        "Reply de escola processado (sem resposta automatica)",
        extra={"company_id": company_id, "queue_id": queue_id}
    )


def _is_from_owner(sender: str) -> bool:
    """Verifica se a mensagem e de um numero/LID autorizado.
    Whatsapp moderno envia LIDs opacos (ex: 59824700190908@lid) em vez de
    numero direto. Aceita tanto numeros quanto LIDs explicitamente na lista.
    """
    authorized_numbers = _get_authorized_numbers()
    authorized_lids = _get_authorized_lids()

    # Se nada esta configurado, permite tudo (modo dev — nao recomendado)
    if not authorized_numbers and not authorized_lids:
        logger.warning("Nenhum numero/LID autorizado configurado — aceitando todos")
        return True

    clean_sender = sender.replace("@s.whatsapp.net", "").replace("@lid", "")

    # Checar LIDs autorizados (match exato)
    if clean_sender in authorized_lids:
        return True

    # Checar numeros autorizados — comparar ultimos 8 digitos (numero local)
    # para aceitar tanto formato com nono digito (5551996422564)
    # quanto sem nono digito (555196422564) que o WhatsApp pode retornar
    digits_sender = "".join(c for c in clean_sender if c.isdigit())
    sender_tail = digits_sender[-8:] if len(digits_sender) >= 8 else digits_sender
    for auth_num in authorized_numbers:
        auth_digits = "".join(c for c in auth_num if c.isdigit())
        auth_tail = auth_digits[-8:] if len(auth_digits) >= 8 else auth_digits
        if sender_tail == auth_tail:
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
    nearby = [s for s in schools[:10] if s["_dist"] <= 1.0]  # apenas ate 1km
    if not nearby:
        return ""  # nenhuma escola proxima — nao ativar modo campo

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
                # Antes de rejeitar, tentar detectar se eh reply de escola
                # (precisa extrair text primeiro — pode ser text ou extendedText)
                try:
                    _reply_text = msg.get("text", "") or ""
                    if not _reply_text:
                        _mc = msg.get("message", {}) or {}
                        _reply_text = (
                            _mc.get("conversation", "")
                            or _mc.get("extendedTextMessage", {}).get("text", "")
                            or ""
                        )
                    if _reply_text:
                        _match = _try_match_school_reply(sender, sender_jid, _reply_text)
                        if _match:
                            _handle_school_reply(_match, _reply_text, sender_jid)
                            return jsonify({"status": "school_reply_processed"}), 200
                except Exception as _e:
                    logger.debug(f"school_reply detection skip: {_e}")

                # Log detalhado para facilitar adicao de LIDs novos autorizados
                is_lid = "@lid" in sender_jid
                logger.warning(
                    "Mensagem REJEITADA — numero/LID nao autorizado",
                    extra={
                        "sender_jid": sender_jid,
                        "sender_clean": sender,
                        "is_lid": is_lid,
                        "push_name": msg.get("pushName", ""),
                        "hint": (
                            f"Para autorizar, adicione este LID ao .env: IALEX_AUTHORIZED_LIDS={sender}"
                            if is_lid else
                            f"Para autorizar, adicione este numero ao .env: IALEX_AUTHORIZED_NUMBERS=...,{sender}"
                        ),
                    }
                )
                return jsonify({"status": "ok"}), 200

            # Determinar tipo de mensagem
            msg_type = msg.get("messageType", "text")

            # === LOCATION MESSAGE ===
            if msg_type == "location" and msg.get("location"):
                loc = msg["location"]
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                loc_name = loc.get("name", "")
                logger.info("Localizacao recebida", extra={"lat": lat, "lng": lng})

                # Tentar buscar escola proxima (< 1km) para contexto
                campo_context = ""
                try:
                    campo_context = _build_field_mode_briefing(lat, lng)
                except Exception:
                    pass

                loc_desc = f"{loc_name}, " if loc_name else ""

                if campo_context:
                    # Tem escola proxima — passar briefing como contexto pro brain
                    # O brain inclui na resposta (uma mensagem so, confiavel)
                    text = (
                        f"[LOCALIZACAO RECEBIDA] {loc_desc}coordenadas {lat}, {lng}. "
                        f"Fernando esta proximo de uma escola do banco (< 1km). "
                        f"INCLUA este briefing na sua resposta e pergunte o que ele quer fazer:\n\n"
                        f"{campo_context}"
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


# ============================================================================
# OPR TRACKING (F7 Fase 3)
# ============================================================================

def _cors_headers():
    """Headers CORS abertos para tracking do OPR (servido em dominio diferente)."""
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "3600",
    }


def _hash_ip(ip: str) -> str:
    """SHA256 do IP (LGPD-compliant)."""
    import hashlib
    if not ip:
        return ""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]


@app.route("/track-opr", methods=["POST", "OPTIONS"])
def track_opr():
    """Recebe evento de tracking do OPR HTML.

    CORS aberto porque o OPR e servido em dados.iaprendo.com.br (dominio diferente).
    Eventos suportados: page_load, tab_click, cta_click.
    """
    # CORS preflight
    if request.method == "OPTIONS":
        return ("", 204, _cors_headers())

    data = request.json or {}
    inep = str(data.get("inep", "")).strip()
    event = (data.get("event") or "page_load").strip()
    benchmark = (data.get("benchmark") or "").strip() or None
    session_id = (data.get("session_id") or "").strip()[:64]

    if not inep:
        return jsonify({"error": "inep required"}), 400, _cors_headers()

    try:
        from database.supabase_client import db

        # Tentar linkar com company_id (se a escola existe no CRM)
        company_id = None
        try:
            comp = db.client.table("companies").select("id").eq(
                "inep_code", inep
            ).limit(1).execute()
            if comp.data:
                company_id = comp.data[0].get("id")
        except Exception:
            pass

        db.client.table("opr_pageviews").insert({
            "inep": inep,
            "company_id": company_id,
            "event_type": event[:30],
            "benchmark_viewed": benchmark,
            "session_id": session_id,
            "user_agent": (request.headers.get("User-Agent") or "")[:500],
            "referer": (request.headers.get("Referer") or "")[:500],
            "ip_hash": _hash_ip(request.remote_addr or ""),
        }).execute()

        logger.info("OPR tracked", extra={
            "inep": inep, "event": event, "benchmark": benchmark,
        })
    except Exception as e:
        logger.debug(f"OPR track failed: {e}")

    return jsonify({"ok": True}), 200, _cors_headers()


def _start_scheduler():
    """Inicia o scheduler de briefings proativos em background."""
    try:
        from agent.scheduler import ialex_scheduler
        ialex_scheduler.start()
        logger.info("Scheduler de briefings proativos iniciado")
    except Exception as e:
        logger.warning(f"Scheduler nao iniciou (nao critico): {e}")


def start_server(port: int = 5001, debug: bool = False):
    """Inicia o servidor webhook + scheduler.

    Quando debug=True, o Flask monitora mudancas nos arquivos .py e
    reinicia automaticamente o servidor. O scheduler so inicia no
    processo principal (nao no reloader) para evitar duplicatas.
    """
    logger.info(f"IAlex webhook server starting on port {port}")

    # Com reloader, o Flask spawna 2 processos. O scheduler so deve
    # rodar no filho (WERKZEUG_RUN_MAIN='true'), nao no pai.
    import os
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if not debug or is_reloader_child:
        _start_scheduler()

    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=debug)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IAlex Webhook Server")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true",
                        help="Ativa auto-reload quando arquivos mudam")
    args = parser.parse_args()
    start_server(port=args.port, debug=args.debug)
