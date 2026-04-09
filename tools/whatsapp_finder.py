"""
WhatsApp Finder — Busca numeros de WhatsApp Business de escolas.

Escolas privadas frequentemente divulgam WhatsApp Business no site,
Google My Business, Instagram e Facebook. Este modulo busca esses
numeros via DuckDuckGo e salva em contacts.phone_whatsapp.

Foco em numeros CELULAR (9 digitos) que sao mais provaveis de ser
WhatsApp. Numeros fixos (8 digitos) sao salvos em companies.phone.

Usage:
    from tools.whatsapp_finder import whatsapp_finder
    result = whatsapp_finder.find_whatsapp("Colegio Marista", "Porto Alegre", "RS")
    results = whatsapp_finder.process_batch(companies, max_per_run=20)
"""
import re
import time
import requests
from typing import Any, Dict, List, Optional

from database.supabase_client import db
from utils.logger import logger


# Regex para celular brasileiro (9 digitos — provavel WhatsApp)
CELULAR_PATTERNS = [
    r"\(\d{2}\)\s*9\d{4}[-\s]?\d{4}",       # (51) 99999-4444
    r"\d{2}\s*9\d{4}[-\s]?\d{4}",            # 51 99999-4444
    r"\+55\s*\d{2}\s*9\d{4}[-\s]?\d{4}",     # +55 51 99999-4444
    r"55\d{2}9\d{8}",                         # 5551999994444
]

# Keywords que indicam WhatsApp Business
WHATSAPP_KEYWORDS = [
    "whatsapp", "whats", "wpp", "zap", "zapzap",
    "fale conosco", "contato", "atendimento",
    "wa.me", "api.whatsapp", "chat.whatsapp",
]

# Headers para requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


class WhatsAppFinder:
    """Busca numeros de WhatsApp Business de escolas via web."""

    def _clean_number(self, raw: str) -> Optional[str]:
        """Limpa e normaliza numero para formato 55DDXXXXXXXXX (13 digitos)."""
        digits = re.sub(r"[^\d]", "", raw)
        # Remover prefixo 55 se ja tem
        if digits.startswith("55") and len(digits) >= 12:
            digits = digits[2:]
        # Deve ter 11 digitos (DDD + 9 + 8 digitos)
        if len(digits) == 11 and digits[2] == "9":
            return f"55{digits}"
        # 10 digitos (fixo) — nao e WhatsApp
        if len(digits) == 10:
            return None
        return None

    def _search_duckduckgo(self, query: str) -> str:
        """Busca no DuckDuckGo e retorna texto concatenado dos resultados."""
        try:
            url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return ""

    def _extract_whatsapp_numbers(self, text: str) -> List[str]:
        """Extrai numeros de celular do texto (provaveis WhatsApp)."""
        numbers = []
        seen = set()
        for pattern in CELULAR_PATTERNS:
            for match in re.finditer(pattern, text):
                clean = self._clean_number(match.group())
                if clean and clean not in seen:
                    seen.add(clean)
                    numbers.append(clean)
        return numbers

    def _has_whatsapp_indicator(self, text: str) -> bool:
        """Verifica se o texto contem indicadores de WhatsApp."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in WHATSAPP_KEYWORDS)

    def find_whatsapp(
        self,
        school_name: str,
        city: str = "",
        state: str = "",
    ) -> Dict[str, Any]:
        """Busca WhatsApp Business de uma escola.
        Google Places (primary) → DuckDuckGo (fallback).

        Args:
            school_name: nome da escola
            city: cidade
            state: UF

        Returns:
            dict com found (bool), number (str ou None), source (str), confidence (str)
        """
        location = f"{city} {state}".strip()

        # === Google Places (primary — telefone estruturado) ===
        google_number = None
        try:
            from integrations.google_places import google_places
            if google_places.is_available():
                result = google_places.search_school_single(school_name, city, state)
                if result and result.get("telefone"):
                    clean = self._clean_number(result["telefone"])
                    if clean:
                        google_number = clean
                        logger.info(f"WhatsApp via Google Places: {clean}", extra={"school": school_name})
        except Exception:
            pass

        if google_number:
            return {
                "found": True,
                "number": google_number,
                "all_numbers": [google_number],
                "source": "google_places",
                "confidence": "alta",
                "has_whatsapp_keyword": False,
            }

        # === DuckDuckGo (fallback) ===
        query1 = f"{school_name} {location} whatsapp"
        html1 = self._search_duckduckgo(query1)
        time.sleep(1)

        query2 = f"{school_name} {location} contato telefone celular"
        html2 = self._search_duckduckgo(query2)

        combined = html1 + " " + html2

        numbers = self._extract_whatsapp_numbers(combined)

        if not numbers:
            return {"found": False, "number": None, "source": "duckduckgo", "confidence": "none"}

        # Priorizar numeros que aparecem perto de keywords de WhatsApp
        best_number = numbers[0]
        confidence = "media"

        if self._has_whatsapp_indicator(html1):
            confidence = "alta"
        elif len(numbers) > 1:
            confidence = "media"

        logger.info(f"WhatsApp encontrado: {best_number} ({confidence})", extra={
            "school": school_name, "total_numbers": len(numbers),
        })

        return {
            "found": True,
            "number": best_number,
            "all_numbers": numbers[:3],
            "source": "duckduckgo",
            "confidence": confidence,
            "has_whatsapp_keyword": self._has_whatsapp_indicator(html1),
        }

    def process_batch(
        self,
        companies: List[Dict[str, Any]],
        max_per_run: int = 20,
    ) -> Dict[str, Any]:
        """Busca WhatsApp Business em lote para escolas que nao tem.

        Args:
            companies: lista de dicts com id, name, city, state
            max_per_run: maximo por rodada

        Returns:
            dict com processed, found, skipped
        """
        processed = 0
        found = 0
        skipped = 0

        for comp in companies[:max_per_run]:
            cid = comp.get("id")
            name = comp.get("name", "")

            if not cid or not name:
                skipped += 1
                continue

            # Checar se ja tem WhatsApp salvo
            try:
                existing = db.client.table("contacts").select("phone_whatsapp").eq(
                    "company_id", cid
                ).not_.is_("phone_whatsapp", "null").limit(1).execute()
                if existing.data:
                    skipped += 1
                    continue
            except Exception:
                pass

            # Buscar
            result = self.find_whatsapp(
                school_name=name,
                city=comp.get("city", ""),
                state=comp.get("state", ""),
            )
            processed += 1

            if result.get("found") and result.get("number"):
                number = result["number"]
                # Salvar no primeiro contato da escola (ou na empresa)
                try:
                    contacts = db.client.table("contacts").select("id").eq(
                        "company_id", cid
                    ).order("outreach_priority").limit(1).execute().data or []

                    if contacts:
                        db.client.table("contacts").update({
                            "phone_whatsapp": number,
                        }).eq("id", contacts[0]["id"]).execute()
                    else:
                        # Sem contato — salvar na empresa
                        db.client.table("companies").update({
                            "phone": number,
                        }).eq("id", cid).execute()

                    found += 1
                    logger.info(f"WhatsApp salvo: {name} → {number}")
                except Exception as e:
                    logger.debug(f"Erro ao salvar WhatsApp: {e}")

            # Rate limit
            time.sleep(1.5)

        return {
            "processed": processed,
            "found": found,
            "skipped": skipped,
        }

    def find_for_enriched_schools(self, limit: int = 20) -> Dict[str, Any]:
        """Busca WhatsApp para escolas enriquecidas que nao tem numero de celular.

        Ideal para rodar no scheduler ou via tool do brain.
        """
        try:
            # Escolas enriquecidas
            schools = db.client.table("companies").select(
                "id,name,city,state,phone"
            ).eq("status", "enriched").order(
                "qualification_score", desc=True
            ).limit(limit * 2).execute().data or []

            # Filtrar as que nao tem celular
            candidates = []
            for s in schools:
                phone = s.get("phone") or ""
                # Se ja tem celular (9 digitos), pula
                digits = re.sub(r"[^\d]", "", phone)
                if len(digits) >= 11 and "9" in digits[2:4]:
                    continue
                candidates.append(s)

            if not candidates:
                return {"processed": 0, "found": 0, "skipped": 0, "message": "Todas as escolas ja tem celular"}

            return self.process_batch(candidates[:limit])

        except Exception as e:
            logger.error(f"find_for_enriched_schools: {e}")
            return {"processed": 0, "found": 0, "error": str(e)[:200]}


# Singleton
whatsapp_finder = WhatsAppFinder()
