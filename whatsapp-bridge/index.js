const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, makeCacheableSignalKeyStore, Browsers } = require('@whiskeysockets/baileys');
const pino = require('pino');
const express = require('express');
const http = require('http');
const QRCode = require('qrcode');

const OWNER_NUMBER = process.env.IALEX_OWNER_NUMBER || '5551996422564';
const IALEX_NUMBER = process.env.IALEX_PHONE_NUMBER || '5551999213905';
const WEBHOOK_URL = 'http://localhost:5001/webhook';
const PORT = 8090;

const logger = pino({ level: 'warn' });

let sock = null;
let currentQR = null;
let connected = false;

async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('./auth_info');

    sock = makeWASocket({
        auth: {
            creds: state.creds,
            keys: makeCacheableSignalKeyStore(state.keys, logger),
        },
        logger,
        browser: Browsers.macOS('Chrome'),
        version: [2, 3000, 1033893291],
        generateHighQualityLinkPreview: false,
        markOnlineOnConnect: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            currentQR = qr;
            console.log('\n=== QR CODE DISPONIVEL ===');
            console.log(`Acesse http://localhost:${PORT}/pair para escanear\n`);
        }

        if (connection === 'close') {
            connected = false;
            currentQR = null;
            const reason = lastDisconnect?.error?.output?.statusCode;
            console.log('Desconectado. Razao:', reason);
            if (reason !== DisconnectReason.loggedOut) {
                console.log('Reconectando em 5s...');
                setTimeout(connectToWhatsApp, 5000);
            } else {
                console.log('Deslogado. Limpe auth_info e reinicie.');
            }
        } else if (connection === 'open') {
            connected = true;
            currentQR = null;
            console.log('\n=== CONECTADO AO WHATSAPP! ===');
            console.log('IAlex esta online.\n');
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        const msg = m.messages[0];
        if (!msg.key.fromMe && m.type === 'notify') {
            const sender = msg.key.remoteJid;
            const text = msg.message?.conversation ||
                        msg.message?.extendedTextMessage?.text || '';

            // Detectar tipo de mensagem
            let messageType = 'text';
            let locationData = null;
            let audioData = null;

            if (msg.message?.locationMessage) {
                messageType = 'location';
                locationData = {
                    latitude: msg.message.locationMessage.degreesLatitude,
                    longitude: msg.message.locationMessage.degreesLongitude,
                    name: msg.message.locationMessage.name || null,
                    address: msg.message.locationMessage.address || null,
                };
                console.log(`Localizacao de ${sender}: ${locationData.latitude}, ${locationData.longitude}`);
            } else if (msg.message?.audioMessage) {
                messageType = 'audio';
                // Baixar o áudio via Baileys
                try {
                    const { downloadMediaMessage } = require('@whiskeysockets/baileys');
                    const buffer = await downloadMediaMessage(msg, 'buffer', {}, { logger, reuploadRequest: sock.updateMediaMessage });
                    audioData = {
                        mimetype: msg.message.audioMessage.mimetype,
                        seconds: msg.message.audioMessage.seconds,
                        buffer: buffer.toString('base64'),
                    };
                    console.log(`Audio de ${sender}: ${audioData.seconds}s, ${audioData.mimetype}`);
                } catch (audioErr) {
                    console.error('Erro ao baixar audio:', audioErr.message);
                    messageType = 'text'; // fallback
                }
            } else {
                console.log(`Mensagem de ${sender}: ${text}`);
            }

            // Ignorar mensagens sem conteúdo útil
            if (messageType === 'text' && !text) return;

            try {
                const payload = JSON.stringify({
                    event: 'messages.upsert',
                    instance: 'ialex',
                    data: {
                        key: msg.key,
                        message: msg.message,
                        pushName: msg.pushName,
                        sender: sender,
                        text: text,
                        messageType: messageType,
                        location: locationData,
                        audio: audioData,
                    }
                });

                const url = new URL(WEBHOOK_URL);
                const req = http.request({
                    hostname: url.hostname,
                    port: url.port,
                    path: url.pathname,
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(payload) }
                }, (res) => {
                    let body = '';
                    res.on('data', (chunk) => body += chunk);
                    res.on('end', () => {
                        try {
                            const response = JSON.parse(body);
                            if (response.reply) {
                                sock.sendMessage(sender, { text: response.reply });
                            }
                        } catch (e) {}
                    });
                });
                req.on('error', () => {
                    sock.sendMessage(sender, { text: 'IAlex esta inicializando. Tente novamente.' });
                });
                req.write(payload);
                req.end();
            } catch (e) {
                console.error('Erro:', e.message);
            }
        }
    });
}

// HTTP server
const app = express();
app.use(express.json());

app.get('/pair', async (req, res) => {
    if (connected) {
        res.send('<html><body style="text-align:center;padding:40px;font-family:Arial"><h1>IAlex</h1><p style="color:green;font-size:24px">Conectado ao WhatsApp!</p></body></html>');
    } else if (currentQR) {
        try {
            const qrDataUrl = await QRCode.toDataURL(currentQR, { width: 300 });
            res.send(`<html><body style="text-align:center;padding:40px;font-family:Arial">
                <h1>IAlex - Escanear QR Code</h1>
                <img src="${qrDataUrl}" style="margin:20px" />
                <p style="font-size:18px">No celular do IAlex (${IALEX_NUMBER}):</p>
                <ol style="text-align:left;max-width:400px;margin:0 auto;font-size:16px">
                    <li>Abra o WhatsApp</li>
                    <li>Toque nos 3 pontinhos > <b>Aparelhos conectados</b></li>
                    <li>Toque em <b>Conectar aparelho</b></li>
                    <li>Aponte a camera para o QR Code acima</li>
                </ol>
                <p><small>Recarregue a pagina se o QR expirar</small></p>
                <script>setTimeout(() => location.reload(), 30000)</script>
            </body></html>`);
        } catch (e) {
            res.send('<html><body style="text-align:center;padding:40px;font-family:Arial"><h1>IAlex</h1><p>Erro ao gerar QR. Recarregue.</p></body></html>');
        }
    } else {
        res.send('<html><body style="text-align:center;padding:40px;font-family:Arial"><h1>IAlex</h1><p>Aguardando QR Code... Recarregue em 5s.</p><script>setTimeout(() => location.reload(), 5000)</script></body></html>');
    }
});

app.get('/status', (req, res) => {
    res.json({ connected, hasQR: !!currentQR });
});

app.post('/send', async (req, res) => {
    const { number, message } = req.body;
    if (!sock || !connected) return res.json({ error: 'Not connected' });
    try {
        const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
        await sock.sendMessage(jid, { text: message });
        res.json({ success: true });
    } catch (e) {
        res.json({ error: e.message });
    }
});

// Verifica se um numero existe no WhatsApp (antes de enviar)
// POST /check-number { number: "5551999999999" } -> { exists: true, jid: "..." }
app.post('/check-number', async (req, res) => {
    const { number } = req.body;
    if (!sock || !connected) return res.json({ error: 'Not connected' });
    try {
        const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
        const results = await sock.onWhatsApp(jid);
        if (results && results.length > 0 && results[0].exists) {
            res.json({ exists: true, jid: results[0].jid });
        } else {
            res.json({ exists: false });
        }
    } catch (e) {
        res.json({ exists: null, error: e.message });
    }
});

// Enviar mensagem com botoes de resposta rapida (max 3 botoes)
app.post('/send-buttons', async (req, res) => {
    const { number, text, buttons, footer } = req.body;
    if (!sock || !connected) return res.json({ error: 'Not connected' });
    try {
        const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
        const buttonRows = (buttons || []).slice(0, 3).map((btn, i) => ({
            buttonId: `btn_${i}`,
            buttonText: { displayText: btn },
            type: 1,
        }));
        await sock.sendMessage(jid, {
            text: text,
            footer: footer || 'IAlex',
            buttons: buttonRows,
            headerType: 1,
        });
        res.json({ success: true });
    } catch (e) {
        // Fallback: enviar como texto com opcoes numeradas
        try {
            const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
            const numEmojis = ['1️⃣', '2️⃣', '3️⃣'];
            const opts = (buttons || []).slice(0, 3).map((b, i) => `${numEmojis[i]} ${b}`).join('\n');
            await sock.sendMessage(jid, { text: `${text}\n\n${opts}\n\n_Responda com o numero ou texto da opcao_` });
            res.json({ success: true, fallback: true });
        } catch (e2) {
            res.json({ error: e2.message });
        }
    }
});

// Enviar mensagem com lista de opcoes (max 10 itens)
app.post('/send-list', async (req, res) => {
    const { number, text, buttonText, sections, footer } = req.body;
    if (!sock || !connected) return res.json({ error: 'Not connected' });
    try {
        const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
        await sock.sendMessage(jid, {
            text: text,
            footer: footer || 'IAlex',
            title: '',
            buttonText: buttonText || 'Ver opcoes',
            sections: sections || [],
        });
        res.json({ success: true });
    } catch (e) {
        // Fallback: enviar como texto com opcoes numeradas
        try {
            const jid = number.includes('@') ? number : `${number}@s.whatsapp.net`;
            const numEmojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'];
            const items = (sections || []).flatMap(s => (s.rows || []).map(r => r.title));
            const opts = items.slice(0, 10).map((t, i) => `${numEmojis[i]} ${t}`).join('\n');
            await sock.sendMessage(jid, { text: `${text}\n\n${opts}\n\n_Responda com o numero ou texto da opcao_` });
            res.json({ success: true, fallback: true });
        } catch (e2) {
            res.json({ error: e2.message });
        }
    }
});

app.listen(PORT, () => {
    console.log(`IAlex bridge em http://localhost:${PORT}`);
    console.log(`QR Code page em http://localhost:${PORT}/pair`);
});

connectToWhatsApp();
