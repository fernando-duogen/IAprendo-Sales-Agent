"""
ContactFinderAgent - Encontra decisores nas escolas.

Cascata de busca:
  1. Web scraping no site da escola  (gratis, ~20% sucesso)
  2. Apollo People Search             (60 creditos/mes, melhor qualidade)
  3. Hunter Domain Search             (25 buscas/mes, bom para emails genericos)
  4. Snov Domain Search               (50 creditos/mes, boa cobertura)
  5. Email patterns por dominio       (gratis, nao verificado)
  6. Placeholder                      (ultimo recurso)

Salva MULTIPLOS contatos por escola com classificacao de papel (Mapa de Poder).
"""
import re
import time
import requests
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup
from agents.base_agent import BaseAgent
from database.supabase_client import db
from config.settings import settings
from utils.logger import logger
from utils.role_classifier import classify_role, classify_email_prefix
from tools.apollo_client import apollo_client
from tools.hunter_client import hunter_client
from tools.snov_client import snov_client
from tools.perplexity_browser import perplexity_browser

TARGET_ROLES = [
    "Diretor", "Diretora", "Diretor(a)",
    "Vice-Diretor", "Vice-Diretora",
    "Coordenador Pedagogico", "Coordenadora Pedagogica",
    "Gestor de Tecnologia", "Gestora de Tecnologia",
    "Secretario", "Secretaria",
]


class ContactFinderAgent(BaseAgent):
    """Encontra decisores nas escolas em cascata com fallbacks.

    Salva MULTIPLOS contatos por escola e classifica cada um
    pelo tipo de decisor (diretor, vice, coordenador, etc).
    A cascata para quando encontra pelo menos um email real.
    Economiza creditos de APIs pagas usando scraping gratis primeiro.
    """

    def __init__(self) -> None:
        super().__init__(agent_name="contact_finder")

    def execute(self, companies: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """Encontra decisores para lista de escolas."""
        results: List[Dict[str, Any]] = []
        for company in companies:
            try:
                found = self.find_contacts(company)
                if found:
                    results.extend(found)
            except Exception as e:
                logger.error(
                    "Erro ao buscar contatos",
                    extra={"company_id": company.get("id"), "error": str(e)},
                )
        logger.info(
            "Busca de contatos concluida",
            extra={"total_companies": len(companies), "contacts_found": len(results)},
        )
        return results

    def _has_director_with_real_email(self, contacts: List[Dict[str, Any]]) -> bool:
        """Verifica se existe diretor com email real (nao pattern/placeholder)."""
        return any(
            c.get("email") and c.get("decision_maker_type") == "diretor"
            and c.get("source") not in ("email_pattern", "placeholder")
            for c in contacts
        )

    def find_contacts(self, company: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Encontra contatos/decisores de uma empresa em cascata.

        Prioriza encontrar Diretor com email real.
        Scraping sempre roda (gratis). APIs pagas so se nao tem Diretor.
        Salva multiplos contatos (ate 5) com classificacao de papel.
        """
        company_id = company.get("id")
        school_name = company.get("name", "Desconhecida")
        logger.info("Buscando contatos", extra={"company_id": company_id, "school_name": school_name})

        # Retornar cedo se ja tem DIRETOR com email real (nao pattern)
        existing = db.get_contacts_by_company(company_id)
        if existing and self._has_director_with_real_email(existing):
            logger.debug(
                "Diretor com email real ja existe - pulando",
                extra={"company_id": company_id},
            )
            return existing  # Retorna TODOS os contatos existentes

        website = company.get("website", "")
        domain = self._extract_domain(website) if website else None
        contacts_found: List[Dict[str, Any]] = []

        # Estrategia 1: Web scraping no site da escola (SEMPRE - gratis)
        if website:
            scraped = self._scrape_website_contacts(website, company_id)
            contacts_found.extend(scraped)

        # Verificar se ja tem diretor com email real (scraping + existentes)
        all_known = (existing or []) + contacts_found

        # Estrategia 2: Apollo People Search (60 creditos/mes)
        # So gasta creditos se NAO tem diretor com email real
        if not self._has_director_with_real_email(all_known):
            if domain and apollo_client.is_available() and self._check_rate_limit("apollo"):
                api_contacts = apollo_client.search_contacts(domain, school_name)
                if api_contacts:
                    saved = self._save_api_contacts(api_contacts, company_id)
                    contacts_found.extend(saved)
                    try:
                        db.insert_api_usage({"api_name": "apollo", "endpoint": "people/search", "credits_used": 1})
                    except Exception:
                        pass

        # Reavaliar antes de gastar Hunter/Snov
        all_known = (existing or []) + contacts_found

        # Estrategia 3: Hunter Domain Search (25 buscas/mes)
        if not self._has_director_with_real_email(all_known):
            if domain and hunter_client.is_available() and self._check_rate_limit("hunter"):
                api_contacts = hunter_client.search_domain(domain, school_name)
                if api_contacts:
                    saved = self._save_api_contacts(api_contacts, company_id)
                    contacts_found.extend(saved)
                    try:
                        db.insert_api_usage({"api_name": "hunter", "endpoint": "domain-search", "credits_used": 1})
                    except Exception:
                        pass

        # Reavaliar antes de gastar Snov
        all_known = (existing or []) + contacts_found

        # Estrategia 4: Snov Domain Search (50 creditos/mes)
        if not self._has_director_with_real_email(all_known):
            if domain and snov_client.is_available() and self._check_rate_limit("snov"):
                api_contacts = snov_client.search_domain(domain, school_name)
                if api_contacts:
                    saved = self._save_api_contacts(api_contacts, company_id)
                    contacts_found.extend(saved)
                    try:
                        db.insert_api_usage({"api_name": "snov", "endpoint": "domain-emails", "credits_used": 1})
                    except Exception:
                        pass

        # Estrategia 5: Perplexity via navegador (gratis - usa assinatura Pro)
        all_known = (existing or []) + contacts_found
        if not self._has_director_with_real_email(all_known):
            if perplexity_browser.is_available():
                city = company.get("city", "")
                state = company.get("state", "")
                api_contacts = perplexity_browser.search_school_contacts(school_name, city, state)
                if api_contacts:
                    saved = self._save_api_contacts(api_contacts, company_id)
                    contacts_found.extend(saved)
                    try:
                        db.insert_api_usage({"api_name": "perplexity", "endpoint": "browser-search", "credits_used": 1})
                    except Exception:
                        pass

        # Estrategia 6: Email patterns por dominio (gratis, nao verificado)
        # So gera se nao encontrou NENHUM email real
        has_any_real_email = any(
            c.get("email") and c.get("source") not in ("email_pattern", "placeholder")
            for c in contacts_found
        )
        if not has_any_real_email and not contacts_found and domain:
            pattern_contacts = self._generate_pattern_contacts(domain)
            if pattern_contacts:
                saved = self._save_api_contacts(pattern_contacts, company_id)
                contacts_found.extend(saved)

        # Estrategia 6: Placeholder (ultimo recurso - sem email)
        if not contacts_found:
            placeholders = [c for c in (existing or []) if not c.get("email")]
            if placeholders:
                contacts_found.append(placeholders[0])
            else:
                placeholder = self._create_placeholder_contact(company)
                if placeholder:
                    contacts_found.append(placeholder)

        return contacts_found

    # =========================================================================
    # Metodos auxiliares
    # =========================================================================

    def _extract_domain(self, website: str) -> Optional[str]:
        """Extrai apenas o dominio limpo de uma URL."""
        try:
            url = website if website.startswith("http") else "https://" + website
            parsed = urlparse(url)
            domain = (parsed.netloc or parsed.path).replace("www.", "").strip("/").split("/")[0]
            return domain if domain and "." in domain else None
        except Exception:
            return None

    def _classify_contact(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Adiciona decision_maker_type e outreach_priority ao contato."""
        role_text = contact_data.get("role") or ""
        email = contact_data.get("email") or ""

        # Classificar pelo cargo primeiro
        dm_type, priority = classify_role(role_text)

        # Se cargo generico, tentar pelo prefixo do email
        if dm_type == "outro" and email and "@" in email:
            dm_type2, priority2 = classify_email_prefix(email)
            if dm_type2 != "outro":
                dm_type, priority = dm_type2, priority2

        contact_data["decision_maker_type"] = dm_type
        contact_data["outreach_priority"] = priority
        return contact_data

    def _save_api_contacts(
        self,
        api_contacts: List[Dict[str, Any]],
        company_id: str,
    ) -> List[Dict[str, Any]]:
        """Salva multiplos contatos de API com classificacao de papel.

        Salva ate 5 contatos. Atualiza placeholder existente se for diretor.
        Deduplica por email (mesmo email nao e inserido 2x).
        """
        existing = db.get_contacts_by_company(company_id)
        placeholders = [c for c in (existing or []) if not c.get("email")]
        existing_emails = {c.get("email").lower() for c in (existing or []) if c.get("email")}
        saved: List[Dict[str, Any]] = []
        placeholder_updated = False

        for api_contact in api_contacts[:5]:  # Ate 5 decisores
            email = api_contact.get("email") or ""

            # Deduplicar por email
            if email and email.lower() in existing_emails:
                logger.debug("Email ja existe - pulando", extra={"email": email})
                continue

            contact_data: Dict[str, Any] = {
                "company_id": company_id,
                "full_name": api_contact.get("full_name") or "Responsavel",
                "role": api_contact.get("role") or "Responsavel",
                "email": email if email else None,
                "source": api_contact.get("source"),
            }

            # Campos opcionais das APIs
            if api_contact.get("phone"):
                contact_data["phone"] = api_contact["phone"]
            if api_contact.get("phone_whatsapp"):
                contact_data["phone_whatsapp"] = api_contact["phone_whatsapp"]
            if api_contact.get("linkedin_url"):
                contact_data["linkedin_url"] = api_contact["linkedin_url"]
            if api_contact.get("confidence_score"):
                contact_data["confidence_score"] = api_contact["confidence_score"]

            # Classificar papel (Mapa de Poder)
            contact_data = self._classify_contact(contact_data)

            try:
                # Atualizar placeholder se e diretor e ainda nao atualizou
                if (placeholders and not placeholder_updated
                        and contact_data.get("decision_maker_type") == "diretor"):
                    placeholder_id = placeholders[0]["id"]
                    update_fields = {
                        k: v for k, v in contact_data.items()
                        if v is not None and k != "company_id"
                    }
                    db.update_contact(placeholder_id, update_fields)
                    contact_data["id"] = placeholder_id
                    placeholder_updated = True
                    logger.info(
                        "Placeholder atualizado via API",
                        extra={"company_id": company_id, "email": email, "dm_type": contact_data.get("decision_maker_type")},
                    )
                else:
                    # Inserir como novo contato
                    contact_id = db.insert_contact(contact_data)
                    contact_data["id"] = contact_id
                    logger.info(
                        "Contato inserido via API",
                        extra={"company_id": company_id, "email": email, "dm_type": contact_data.get("decision_maker_type")},
                    )

                saved.append(contact_data)
                if email:
                    existing_emails.add(email.lower())

            except Exception as e:
                logger.error("Falha ao salvar contato", extra={"company_id": company_id, "error": str(e)})

        return saved

    def _generate_pattern_contacts(self, domain: str) -> List[Dict[str, Any]]:
        """Gera emails por padrao para multiplos papeis."""
        if not domain or "." not in domain:
            return []
        return [
            {"full_name": "Contato", "role": "Contato", "email": f"contato@{domain}", "source": "email_pattern"},
            {"full_name": "Direcao", "role": "Direcao", "email": f"direcao@{domain}", "source": "email_pattern"},
            {"full_name": "Coordenacao", "role": "Coordenacao Pedagogica", "email": f"coordenacao@{domain}", "source": "email_pattern"},
        ]

    def _scrape_website_contacts(self, website: str, company_id: str) -> List[Dict[str, Any]]:
        """Tenta encontrar contatos no website da escola."""
        contacts: List[Dict[str, Any]] = []
        pages_to_try = ["/contato", "/equipe", "/sobre", "/quem-somos", ""]
        for page in pages_to_try:
            try:
                url = website.rstrip("/") + page
                headers = {"User-Agent": "Mozilla/5.0 (compatible; SchoolResearch/1.0)"}
                resp = requests.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    found = self._extract_contacts_from_html(resp.text, company_id)
                    contacts.extend(found)
                    if contacts:
                        break
                time.sleep(1)
            except Exception as e:
                logger.debug("Falha ao scrape pagina", extra={"url": url, "error": str(e)})
        return contacts

    def _extract_contacts_from_html(self, html: str, company_id: str) -> List[Dict[str, Any]]:
        """Extrai emails do HTML e classifica por prefixo."""
        contacts: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        email_pattern = r"[a-zA-Z0-9._%+" + chr(45) + r"]+@[a-zA-Z0-9." + chr(45) + r"]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, text)
        for email in emails[:5]:  # Ate 5 emails do site
            if not any(skip in email.lower() for skip in ["noreply", "no-reply", "donotreply"]):
                # Classificar pelo prefixo do email
                dm_type, priority = classify_email_prefix(email)
                contact_data: Dict[str, Any] = {
                    "company_id": company_id,
                    "full_name": "Responsavel",
                    "email": email,
                    "source": "web_scraping",
                    "decision_maker_type": dm_type,
                    "outreach_priority": priority,
                }
                try:
                    contact_id = db.insert_contact(contact_data)
                    contact_data["id"] = contact_id
                    contacts.append(contact_data)
                    logger.info("Contato via scraping", extra={"company_id": company_id, "email": email, "dm_type": dm_type})
                except Exception as e:
                    logger.warning("Falha ao inserir contato", extra={"error": str(e)})
        return contacts

    def _try_email_patterns(self, website: str, company_id: str) -> List[Dict[str, Any]]:
        """Mantido para compatibilidade. Nova logica usa _generate_pattern_contacts."""
        return []

    def _create_placeholder_contact(self, company: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cria contato placeholder para papel diretor."""
        company_id = company.get("id")
        phone = company.get("phone", "")
        contact_data: Dict[str, Any] = {
            "company_id": company_id,
            "full_name": "Diretor(a)",
            "role": "Diretor(a)",
            "source": "placeholder",
            "decision_maker_type": "diretor",
            "outreach_priority": 1,
        }
        if phone:
            contact_data["phone"] = phone
        try:
            contact_id = db.insert_contact(contact_data)
            contact_data["id"] = contact_id
            logger.info("Placeholder criado", extra={"company_id": company_id})
            return contact_data
        except Exception as e:
            logger.warning("Falha ao criar placeholder", extra={"error": str(e)})
            return None
