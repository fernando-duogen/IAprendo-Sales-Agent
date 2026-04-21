"""
WhatsApp Bridge - Conexao com Evolution API para envio/recepcao de mensagens.
Evolution API roda em Docker na porta 8080.
"""

import os
import re
import sys
from typing import Any, Dict, List

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import logger


class WhatsAppBridge:
    """Bridge para comunicacao com WhatsApp via Baileys bridge (porta 8090)."""

    def __init__(self) -> None:
        self.bridge_url: str = os.getenv("BAILEYS_BRIDGE_URL", "http://localhost:8090")
        # Legacy Evolution API config (kept for reference)
        self.base_url: str = os.getenv("EVOLUTION_URL", "http://localhost:8080").rstrip("/")
        self.api_key: str = os.getenv("EVOLUTION_API_KEY", "iaprendo-evolution-2026")
        self.instance_name: str = "ialex"
        self.owner_number: str = os.getenv("IALEX_OWNER_NUMBER", "")
        self._headers: Dict[str, str] = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Instance management
    # ------------------------------------------------------------------

    def create_instance(self) -> Dict[str, Any]:
        """Cria instancia 'ialex' na Evolution API.

        Returns:
            Dict com dados da instancia criada ou {} em caso de falha.
        """
        url = f"{self.base_url}/instance/create"
        body = {
            "instanceName": self.instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        }
        try:
            resp = requests.post(url, json=body, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            logger.info(f"Instancia '{self.instance_name}' criada com sucesso.")
            return data
        except requests.RequestException as exc:
            logger.error(f"Erro ao criar instancia: {exc}")
            return {}

    def get_qr_code(self) -> str:
        """Obtem QR code base64 para conectar o WhatsApp.

        Returns:
            String base64 do QR code ou string vazia em caso de falha.
        """
        url = f"{self.base_url}/instance/connect/{self.instance_name}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            qr: str = data.get("base64", data.get("qrcode", ""))
            if qr:
                logger.info("QR code obtido com sucesso.")
            else:
                logger.warning("Resposta sem QR code.")
            return qr
        except requests.RequestException as exc:
            logger.error(f"Erro ao obter QR code: {exc}")
            return ""

    def check_connection(self) -> Dict[str, Any]:
        """Verifica estado da conexao da instancia.

        Returns:
            Dict com estado da conexao ou {} em caso de falha.
        """
        url = f"{self.base_url}/instance/connectionState/{self.instance_name}"
        try:
            resp = requests.get(url, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            state = data.get("instance", {}).get("state", "unknown")
            logger.info(f"Estado da conexao: {state}")
            return data
        except requests.RequestException as exc:
            logger.error(f"Erro ao verificar conexao: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def check_number(self, number: str) -> Dict[str, Any]:
        """Valida se um numero esta registrado no WhatsApp.

        Args:
            number: Numero (ex: '5551999999999') ou JID completo.

        Returns:
            {"exists": True, "jid": "..."} se o numero existe
            {"exists": False} se nao existe
            {"exists": None, "error": "..."} em caso de erro/timeout
        """
        url = f"{self.bridge_url}/check-number"
        if "@" in number:
            formatted = number
        else:
            formatted = self.format_number(number)
        try:
            resp = requests.post(url, json={"number": formatted}, timeout=10)
            data: Dict[str, Any] = resp.json()
            return data
        except requests.RequestException as exc:
            logger.debug(f"check_number erro para {formatted}: {exc}")
            return {"exists": None, "error": str(exc)}

    def send_message(self, number: str, text: str) -> Dict[str, Any]:
        """Envia mensagem de texto via WhatsApp (Evolution API ou Baileys bridge fallback).

        Args:
            number: Numero do destinatario (ex: '5551999999999') ou JID completo (ex: '123@lid').
            text: Texto da mensagem.

        Returns:
            Dict com resposta da API ou {} em caso de falha.
        """
        # Se ja e um JID completo (@lid ou @s.whatsapp.net), enviar direto
        if "@" in number:
            formatted = number
        else:
            formatted = self.format_number(number)

        # Tentar via Evolution API (porta 8080) — metodo primario
        evo_url = f"{self.base_url}/message/sendText/{self.instance_name}"
        body_evo = {"number": formatted, "text": text}
        try:
            resp = requests.post(evo_url, json=body_evo, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            logger.info(f"Mensagem enviada via Evolution API para {formatted}.")
            return {"success": True, **data}
        except requests.RequestException as exc_evo:
            logger.warning(f"Evolution API falhou para {formatted}: {exc_evo}")

        # Fallback: Baileys bridge (porta 8090)
        url = f"{self.bridge_url}/send"
        body = {"number": formatted, "message": text}
        try:
            resp = requests.post(url, json=body, timeout=15)
            data = resp.json()
            if data.get("success"):
                logger.info(f"Mensagem enviada via bridge para {formatted}.")
            elif data.get("error"):
                logger.error(f"Erro do bridge: {data['error']}")
            return data
        except requests.RequestException as exc:
            logger.error(f"Erro ao enviar mensagem para {formatted}: {exc}")
            return {}

    def send_buttons(self, number: str, text: str, buttons: List[str], footer: str = "IAlex") -> Dict[str, Any]:
        """Envia mensagem com botoes de resposta rapida (max 3).

        Args:
            number: Numero ou JID do destinatario.
            text: Texto principal da mensagem.
            buttons: Lista de textos dos botoes (max 3).
            footer: Texto de rodape.
        """
        url = f"{self.bridge_url}/send-buttons"
        formatted = number if "@" in number else self.format_number(number)
        body = {"number": formatted, "text": text, "buttons": buttons[:3], "footer": footer}
        try:
            resp = requests.post(url, json=body, timeout=15)
            return resp.json()
        except requests.RequestException as exc:
            logger.error(f"Erro ao enviar botoes: {exc}")
            return {}

    def send_list(self, number: str, text: str, button_text: str, sections: List[Dict], footer: str = "IAlex") -> Dict[str, Any]:
        """Envia mensagem com lista de opcoes (max 10 itens).

        Args:
            number: Numero ou JID do destinatario.
            text: Texto principal.
            button_text: Texto do botao que abre a lista.
            sections: Lista de secoes com rows [{title, description, rowId}].
            footer: Texto de rodape.
        """
        url = f"{self.bridge_url}/send-list"
        formatted = number if "@" in number else self.format_number(number)
        body = {"number": formatted, "text": text, "buttonText": button_text, "sections": sections, "footer": footer}
        try:
            resp = requests.post(url, json=body, timeout=15)
            return resp.json()
        except requests.RequestException as exc:
            logger.error(f"Erro ao enviar lista: {exc}")
            return {}

    def send_image(self, number: str, image_url: str, caption: str = "") -> Dict[str, Any]:
        """Envia imagem via WhatsApp (Baileys bridge).

        Usa o endpoint /send-image do Baileys bridge (porta 8090) que aceita
        URLs publicas de imagem. O Baileys baixa a imagem e envia via
        WhatsApp Web.

        Args:
            number: Numero do destinatario (ex: '5551999999999') ou JID.
            image_url: URL publica da imagem (HTTPS).
            caption: Legenda opcional da imagem.

        Returns:
            Dict com {"success": True} ou {"success": False, "error": str}.
        """
        url = f"{self.bridge_url}/send-image"
        if "@" in number:
            formatted = number
        else:
            formatted = self.format_number(number)
        body = {
            "number": formatted,
            "url": image_url,
            "caption": caption,
        }
        try:
            resp = requests.post(url, json=body, timeout=20)
            data: Dict[str, Any] = resp.json()
            if data.get("success"):
                logger.info(f"Imagem enviada para {formatted}.")
                return data
            else:
                error_msg = data.get("error", "desconhecido")
                logger.error(f"Erro bridge send-image: {error_msg}")
                return {"success": False, "error": error_msg}
        except requests.RequestException as exc:
            logger.error(f"Erro ao enviar imagem para {formatted}: {exc}")
            return {"success": False, "error": str(exc)}

    def send_buttons(self, number: str, text: str, buttons: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Envia mensagem com botoes de resposta rapida.

        Args:
            number: Numero do destinatario.
            text: Texto da mensagem.
            buttons: Lista de dicts com botoes (ex: [{"buttonText": "Sim"}, ...]).

        Returns:
            Dict com resposta da API ou {} em caso de falha.
        """
        url = f"{self.base_url}/message/sendButtons/{self.instance_name}"
        formatted = self.format_number(number)
        body = {
            "number": formatted,
            "text": text,
            "buttons": buttons,
        }
        try:
            resp = requests.post(url, json=body, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            logger.info(f"Botoes enviados para {formatted}.")
            return data
        except requests.RequestException as exc:
            logger.error(f"Erro ao enviar botoes para {formatted}: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    def set_webhook(self, url: str) -> Dict[str, Any]:
        """Configura webhook para receber eventos da instancia.

        Args:
            url: URL publica do webhook (ex: ngrok).

        Returns:
            Dict com resposta da API ou {} em caso de falha.
        """
        endpoint = f"{self.base_url}/webhook/set/{self.instance_name}"
        body = {
            "url": url,
            "webhook_by_events": True,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
        }
        try:
            resp = requests.post(endpoint, json=body, headers=self._headers, timeout=15)
            resp.raise_for_status()
            data: Dict[str, Any] = resp.json()
            logger.info(f"Webhook configurado: {url}")
            return data
        except requests.RequestException as exc:
            logger.error(f"Erro ao configurar webhook: {exc}")
            return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def format_number(phone: str) -> str:
        """Formata numero de telefone para padrao Evolution API (5551999999999).

        Aceita formatos variados:
            (51) 99999-9999 -> 5551999999999
            51999999999    -> 5551999999999
            +5551999999999 -> 5551999999999
            5551999999999  -> 5551999999999

        Args:
            phone: Numero em qualquer formato brasileiro.

        Returns:
            Numero limpo no formato 55XXXXXXXXXXX.
        """
        digits = re.sub(r"\D", "", phone)

        # Remove leading + already handled by re.sub
        # If starts with 0, remove it (local format)
        if digits.startswith("0"):
            digits = digits[1:]

        # Add country code if missing
        if not digits.startswith("55"):
            digits = "55" + digits

        return digits
