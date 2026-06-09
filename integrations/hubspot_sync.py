"""
HubSpotSync - Logica de negocio para sincronizar dados IAprendo <-> HubSpot.

Orquestra o hubspot_client.py e decide QUANDO e O QUE sincronizar.
Todos os metodos sao idempotentes: podem ser chamados multiplas vezes sem duplicar.

Fluxo:
  1. sync_company    -> Cria/atualiza Company no HubSpot
  2. sync_contact    -> Cria/atualiza Contact, associa a Company
  3. create_deal     -> Cria Deal no pipeline "IAprendo Sales"
  4. log_email_sent  -> Registra email como nota + atualiza Deal stage
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from integrations.hubspot_client import hubspot_client
from database.supabase_client import db
from utils.logger import logger


# Mapeamento commercial_stage -> stage label do HubSpot.
#
# FONTE UNICA: STAGE_MAP vive em utils/stage_sync.py (compartilhado com o pull
# via LABEL_TO_STAGE, pra os dois sentidos nao divergirem). Re-exportado aqui
# pra nao quebrar `from integrations.hubspot_sync import STAGE_MAP`.
#
# IMPORTANTE: o pipeline de Deals no HubSpot precisa ter EXATAMENTE os 8 stage
# labels do STAGE_MAP. Se algum nao existir, update_deal_stage() loga warning e
# nao faz nada (seguro, mas a sincronia nao acontece). Rode
# scripts/setup_hubspot_properties.py pra criar/reconciliar os stages.
from utils.stage_sync import STAGE_MAP


class HubSpotSync:
    """Sincronizacao unidirecional Supabase -> HubSpot."""

    def __init__(self) -> None:
        self.enabled = hubspot_client._enabled
        self._pipeline_id = None
        self._stage_ids = {}  # label -> stage_id
        self._custom_props_available = True  # Custom properties created via setup_hubspot_properties.py

    # =========================================================================
    # Pipeline discovery (lazy)
    # =========================================================================

    def _ensure_pipeline(self) -> bool:
        """Carrega IDs do pipeline e stages. Retorna True se encontrado.

        Seleciona o pipeline pelo nome configurado (settings.HUBSPOT_PIPELINE_NAME,
        default "IAprendo Sales") — NAO o primeiro da lista, que pode ser o
        pipeline default do HubSpot (labels em ingles: Appointment Scheduled...)
        e quebrar todo o mapeamento de stages. Cai pro primeiro so como ultimo
        recurso, com aviso.
        """
        if self._pipeline_id and self._stage_ids:
            return True
        pipelines = hubspot_client.get_deal_pipelines()
        if not pipelines:
            logger.warning("Nenhum pipeline encontrado no HubSpot")
            return False
        if len(pipelines) == 1:
            # Free tier: existe so 1 pipeline de deals — use-o direto, sem
            # depender de nome/acento.
            p = pipelines[0]
        else:
            from config.settings import settings
            wanted = getattr(settings, "HUBSPOT_PIPELINE_NAME", "IAprendo Sales")
            p = next((x for x in pipelines if x.get("label") == wanted), None)
            if p is None:
                p = pipelines[0]
                logger.warning(
                    "Pipeline configurado nao encontrado no HubSpot; usando o primeiro",
                    extra={"wanted": wanted, "fallback": p.get("label")},
                )
        self._pipeline_id = p["id"]
        self._stage_ids = {s["label"]: s["id"] for s in p["stages"]}
        logger.info(
            "Pipeline carregado",
            extra={"pipeline_id": self._pipeline_id, "pipeline_label": p.get("label"), "stages": len(self._stage_ids)},
        )
        return True

    # =========================================================================
    # Company sync
    # =========================================================================

    def sync_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Cria ou atualiza Company no HubSpot. Salva hubspot_id no Supabase.

        Args:
            company: Dict com dados da escola (do Supabase companies table).

        Returns:
            {"success": bool, "hubspot_id": str|None, "action": "created"|"updated"|"skipped"}
        """
        if not self.enabled:
            return {"success": False, "hubspot_id": None, "action": "disabled"}

        company_id = company.get("id")
        inep = company.get("inep_code", "")
        name = company.get("name", "Escola Desconhecida")

        # Ja tem hubspot_id? -> atualizar
        existing_hs_id = company.get("hubspot_company_id")
        if existing_hs_id:
            props = self._company_to_hubspot_props(company)
            ok = hubspot_client.update_company(existing_hs_id, props)
            return {"success": ok, "hubspot_id": existing_hs_id, "action": "updated"}

        # Buscar no HubSpot por nome (evita duplicata)
        # Tenta variações: original, title case, uppercase
        if name:
            name_variants = list(set([name, name.title(), name.upper()]))
            for variant in name_variants:
                found = hubspot_client.search_company("name", variant)
                if found:
                    hs_id = found["id"]
                    db.update_company(company_id, {"hubspot_company_id": hs_id})
                    hubspot_client.update_company(hs_id, self._company_to_hubspot_props(company))
                    return {"success": True, "hubspot_id": hs_id, "action": "updated"}

        # Criar nova
        props = self._company_to_hubspot_props(company)
        hs_id = hubspot_client.create_company(props)
        if hs_id and company_id:
            db.update_company(company_id, {"hubspot_company_id": hs_id})
        return {"success": bool(hs_id), "hubspot_id": hs_id, "action": "created" if hs_id else "failed"}

    def _company_to_hubspot_props(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Mapeia campos da escola para propriedades HubSpot (apenas campos padrao)."""
        props = {
            "name": company.get("name", ""),
            "city": company.get("city", ""),
            "state": company.get("state", ""),
            "address": company.get("address", ""),
        }
        if company.get("phone"):
            props["phone"] = company["phone"]
        if company.get("website"):
            props["domain"] = company["website"].replace("https://", "").replace("http://", "").rstrip("/")
        # Custom properties (so incluir se existirem no HubSpot)
        if self._custom_props_available:
            if company.get("inep_code"):
                props["inep_code"] = company["inep_code"]
            if company.get("qualification_score") is not None:
                props["iaprendo_score"] = str(company["qualification_score"])
            if company.get("status"):
                props["iaprendo_status"] = company["status"]
        # Incluir score/status na descricao como fallback
        desc_parts = []
        if company.get("qualification_score") is not None:
            desc_parts.append(f"Score: {company['qualification_score']}/100")
        if company.get("status"):
            desc_parts.append(f"Status: {company['status']}")
        if company.get("inep_code"):
            desc_parts.append(f"INEP: {company['inep_code']}")
        if company.get("education_levels"):
            desc_parts.append(f"Niveis: {company['education_levels']}")
        if company.get("school_size"):
            desc_parts.append(f"Porte: {company['school_size']}")
        if desc_parts:
            props["description"] = " | ".join(desc_parts)
        return props

    # =========================================================================
    # Contact sync
    # =========================================================================

    def sync_contact(self, contact: Dict[str, Any], hubspot_company_id: Optional[str] = None) -> Dict[str, Any]:
        """Cria ou atualiza Contact no HubSpot. Associa a Company se fornecido.

        Args:
            contact: Dict com dados do contato (do Supabase contacts table).
            hubspot_company_id: ID da Company no HubSpot para associacao.

        Returns:
            {"success": bool, "hubspot_id": str|None, "action": str}
        """
        if not self.enabled:
            return {"success": False, "hubspot_id": None, "action": "disabled"}

        contact_id = contact.get("id")
        email = contact.get("email")
        if not email:
            return {"success": False, "hubspot_id": None, "action": "no_email"}

        existing_hs_id = contact.get("hubspot_contact_id")
        if existing_hs_id:
            props = self._contact_to_hubspot_props(contact)
            ok = hubspot_client.update_contact(existing_hs_id, props)
            return {"success": ok, "hubspot_id": existing_hs_id, "action": "updated"}

        # Buscar por email
        found = hubspot_client.search_contact("email", email)
        if found:
            hs_id = found["id"]
            if contact_id:
                db.update_contact(contact_id, {"hubspot_contact_id": hs_id})
            return {"success": True, "hubspot_id": hs_id, "action": "found_existing"}

        # Criar novo
        props = self._contact_to_hubspot_props(contact)
        hs_id = hubspot_client.create_contact(props)
        if hs_id and contact_id:
            db.update_contact(contact_id, {"hubspot_contact_id": hs_id})

        # Associar a Company (se temos ambos os IDs)
        if hs_id and hubspot_company_id:
            try:
                self._associate_contact_to_company(hs_id, hubspot_company_id)
            except Exception as e:
                logger.warning("Falha ao associar contact a company",
                    extra={"error": str(e), "contact_hs_id": hs_id, "company_hs_id": hubspot_company_id})

        return {"success": bool(hs_id), "hubspot_id": hs_id, "action": "created" if hs_id else "failed"}

    def _contact_to_hubspot_props(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Mapeia campos do contato para propriedades HubSpot."""
        full_name = contact.get("full_name", "")
        parts = full_name.split(" ", 1)
        firstname = parts[0] if parts else ""
        lastname = parts[1] if len(parts) > 1 else ""
        props = {
            "email": contact.get("email", ""),
            "firstname": firstname,
            "lastname": lastname,
            "jobtitle": contact.get("role", ""),
            "phone": contact.get("phone", ""),
        }
        if contact.get("linkedin_url"):
            props["hs_linkedinid"] = contact["linkedin_url"]
        if contact.get("decision_maker_type"):
            props["decision_maker_type"] = contact["decision_maker_type"]
        if contact.get("outreach_priority") is not None:
            props["outreach_priority"] = str(contact["outreach_priority"])
        return props

    def _associate_contact_to_company(self, contact_hs_id: str, company_hs_id: str) -> None:
        """Associa Contact a Company no HubSpot."""
        try:
            # Usar API v3 (mais estavel)
            from hubspot.crm.associations import BatchInputPublicAssociation, PublicAssociation
            batch = BatchInputPublicAssociation(inputs=[
                PublicAssociation(_from={"id": contact_hs_id}, to={"id": company_hs_id}, type="contact_to_company")
            ])
            hubspot_client._client.crm.associations.batch_api.create(
                from_object_type="contacts", to_object_type="companies",
                batch_input_public_association=batch,
            )
        except Exception:
            # Fallback: tentar sem batch
            try:
                hubspot_client._client.crm.contacts.associations_api.create(
                    contact_id=contact_hs_id,
                    to_object_type="companies",
                    to_object_id=company_hs_id,
                    association_type="contact_to_company",
                )
            except Exception as e2:
                logger.warning("Associacao contact->company falhou (nao-critico)", extra={"error": str(e2)[:100]})

    # =========================================================================
    # Deal (Oportunidade)
    # =========================================================================

    def create_deal(self, company: Dict[str, Any], contact: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Cria Deal no pipeline IAprendo Sales, associado a Company e Contact.

        Returns:
            {"success": bool, "hubspot_deal_id": str|None}
        """
        if not self.enabled or not self._ensure_pipeline():
            return {"success": False, "hubspot_deal_id": None}

        company_id = company.get("id")
        school_name = company.get("name", "Escola")
        hs_company_id = company.get("hubspot_company_id")
        hs_contact_id = contact.get("hubspot_contact_id") if contact else None

        # Verifica se ja tem deal
        existing_deal_id = company.get("hubspot_deal_id")
        if existing_deal_id:
            return {"success": True, "hubspot_deal_id": existing_deal_id}

        # Novo deal entra no 1o stage do funil ("Prospectado"), via STAGE_MAP —
        # NAO "Appointment Scheduled" (label do pipeline default, inexistente aqui).
        first_stage_id = self._stage_ids.get(STAGE_MAP["prospectado"], "")
        props = {
            "dealname": f"IAprendo - {school_name}",
            "pipeline": self._pipeline_id,
            "dealstage": first_stage_id,
            "amount": "0",
        }
        if company.get("qualification_score") is not None:
            props["iaprendo_score"] = str(company["qualification_score"])

        hs_deal_id = hubspot_client.create_deal(props, hs_company_id, hs_contact_id)
        if hs_deal_id and company_id:
            db.update_company(company_id, {"hubspot_deal_id": hs_deal_id})

        return {"success": bool(hs_deal_id), "hubspot_deal_id": hs_deal_id}

    def update_deal_stage(self, company_id: str, stage: str) -> bool:
        """Atualiza o stage de um Deal existente (busca deal_id no Supabase).

        `stage` e a chave de commercial_stage (prospectado..cliente/perdido),
        igual ao db.set_commercial_stage — a label do HubSpot e resolvida via
        STAGE_MAP (fonte unica). Se vier um label do HubSpot direto, passa
        adiante (retrocompat).
        """
        if not self.enabled or not self._ensure_pipeline():
            return False
        try:
            result = db.client.table("companies").select("hubspot_deal_id").eq("id", company_id).single().execute()
            deal_id = result.data.get("hubspot_deal_id") if result.data else None
            if not deal_id:
                logger.warning("Company sem hubspot_deal_id", extra={"company_id": company_id})
                return False
            stage_label = STAGE_MAP.get(stage, stage)
            stage_id = self._stage_ids.get(stage_label)
            if not stage_id:
                logger.warning("Stage nao encontrado", extra={"stage": stage, "stage_label": stage_label})
                return False
            return hubspot_client.update_deal(deal_id, {"dealstage": stage_id})
        except Exception as e:
            logger.error("Erro ao atualizar deal stage", extra={"error": str(e), "company_id": company_id})
            return False

    # =========================================================================
    # Email engagement logging
    # =========================================================================

    def log_email_sent(self, queue_record: Dict[str, Any], brevo_result: Dict[str, Any]) -> Dict[str, Any]:
        """Registra email enviado no HubSpot (nota + atualiza deal stage).

        Args:
            queue_record: Record da approval_queue (tem company_id, contact_id, subject, body).
            brevo_result: Resultado do brevo_sender (tem message_id).

        Returns:
            {"success": bool, "note_id": str|None}
        """
        if not self.enabled:
            return {"success": False, "note_id": None}

        company_id = queue_record.get("company_id")
        contact_id = queue_record.get("contact_id")
        subject = queue_record.get("subject", "")
        brevo_msg_id = brevo_result.get("message_id", "")

        # Buscar HubSpot IDs do Supabase
        hs_company_id = None
        hs_contact_id = None
        hs_deal_id = None
        try:
            if company_id:
                c = db.client.table("companies").select("hubspot_company_id,hubspot_deal_id").eq("id", company_id).single().execute()
                if c.data:
                    hs_company_id = c.data.get("hubspot_company_id")
                    hs_deal_id = c.data.get("hubspot_deal_id")
            if contact_id:
                ct = db.client.table("contacts").select("hubspot_contact_id").eq("id", contact_id).single().execute()
                if ct.data:
                    hs_contact_id = ct.data.get("hubspot_contact_id")
        except Exception as e:
            logger.warning("Erro ao buscar HubSpot IDs para logging", extra={"error": str(e)})

        # Verificar se temos pelo menos um HubSpot ID para associar a nota
        if not hs_company_id and not hs_contact_id and not hs_deal_id:
            logger.warning("Nenhum HubSpot ID encontrado para logar email",
                extra={"company_id": company_id, "contact_id": contact_id})
            return {"success": False, "note_id": None}

        # Criar nota com detalhes do email
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        note_body = f"Email enviado via IAprendo em {now}\nAssunto: {subject}\nBrevo ID: {brevo_msg_id}"
        note_id = hubspot_client.create_note(
            body=note_body,
            company_id=hs_company_id,
            contact_id=hs_contact_id,
            deal_id=hs_deal_id,
        )

        # Atualizar deal stage para "Email Enviado" via STAGE_MAP — antes usava
        # "Qualified To Buy" (label do pipeline default, inexistente aqui).
        if hs_deal_id and self._ensure_pipeline():
            stage_id = self._stage_ids.get(STAGE_MAP["contatado"])
            if stage_id:
                hubspot_client.update_deal(hs_deal_id, {"dealstage": stage_id})

        return {"success": bool(note_id), "note_id": note_id}


# Singleton
hubspot_sync = HubSpotSync()
