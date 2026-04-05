"""
HubSpotClient - Client de baixo nivel para a API do HubSpot.

Segue o padrao do BrevoSender: singleton, feature flag, graceful degradation.
Usa o SDK oficial hubspot-api-client.

IMPORTANTE: Este client NAO decide quando sincronizar.
A logica de negocio fica em hubspot_sync.py.
"""
import time
from typing import Dict, Any, Optional, List
from config.settings import settings
from utils.logger import logger


class HubSpotClient:
    """Client para API v3 do HubSpot via SDK oficial."""

    def __init__(self) -> None:
        self.api_key = settings.HUBSPOT_API_KEY
        self._enabled = bool(self.api_key)
        self._client = None
        if self._enabled:
            try:
                from hubspot import HubSpot
                self._client = HubSpot(access_token=self.api_key)
                logger.info("HubSpot client inicializado")
            except Exception as e:
                logger.error("Falha ao inicializar HubSpot client", extra={"error": str(e)})
                self._enabled = False
        else:
            logger.warning("HUBSPOT_API_KEY nao configurada - HubSpot desabilitado")

    # =========================================================================
    # Helpers
    # =========================================================================

    def _retry(self, func, *args, max_retries: int = 3, **kwargs) -> Any:
        """Executa funcao com retry e backoff exponencial."""
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)
                # Rate limit (429) - esperar e tentar de novo
                if "429" in error_str and attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.warning("HubSpot rate limit, aguardando",
                        extra={"wait_seconds": wait, "attempt": attempt + 1})
                    time.sleep(wait)
                    continue
                # Ultimo attempt ou erro nao-retentavel
                if attempt == max_retries - 1:
                    logger.error("HubSpot API falhou apos retries",
                        extra={"error": error_str, "attempts": max_retries})
                    raise
                time.sleep(1)
        return None

    def _props_to_simple_object(self, properties: Dict[str, Any]):
        """Converte dict de propriedades para SimplePublicObjectInputForCreate."""
        from hubspot.crm.companies import SimplePublicObjectInputForCreate
        clean = {k: str(v) if v is not None else "" for k, v in properties.items()}
        return SimplePublicObjectInputForCreate(properties=clean)

    # =========================================================================
    # Companies (Escolas)
    # =========================================================================

    def create_company(self, properties: Dict[str, Any]) -> Optional[str]:
        """Cria Company no HubSpot. Retorna hubspot_id ou None."""
        if not self._enabled:
            return None
        try:
            obj = self._props_to_simple_object(properties)
            result = self._retry(self._client.crm.companies.basic_api.create, simple_public_object_input_for_create=obj)
            hubspot_id = result.id
            logger.info("HubSpot Company criada", extra={"hubspot_id": hubspot_id, "obj_name": properties.get("name", "")})
            return hubspot_id
        except Exception as e:
            logger.error("Erro ao criar HubSpot Company", extra={"error": str(e), "obj_name": properties.get("name", "")})
            return None

    def update_company(self, hubspot_id: str, properties: Dict[str, Any]) -> bool:
        """Atualiza Company existente no HubSpot."""
        if not self._enabled:
            return False
        try:
            from hubspot.crm.companies import SimplePublicObjectInput
            obj = SimplePublicObjectInput(properties={k: str(v) if v is not None else "" for k, v in properties.items()})
            self._retry(self._client.crm.companies.basic_api.update, company_id=hubspot_id, simple_public_object_input=obj)
            logger.info("HubSpot Company atualizada", extra={"hubspot_id": hubspot_id})
            return True
        except Exception as e:
            logger.error("Erro ao atualizar HubSpot Company", extra={"error": str(e), "hubspot_id": hubspot_id})
            return False

    def search_company(self, field: str, value: str) -> Optional[Dict[str, Any]]:
        """Busca Company por campo (ex: inep_code, domain)."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.companies import PublicObjectSearchRequest, Filter, FilterGroup
            f = Filter(property_name=field, operator="EQ", value=value)
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(filter_groups=[fg], limit=1)
            result = self._retry(self._client.crm.companies.search_api.do_search, public_object_search_request=req)
            if result.results:
                r = result.results[0]
                return {"id": r.id, "properties": r.properties}
            return None
        except Exception as e:
            logger.error("Erro ao buscar HubSpot Company", extra={"error": str(e), "field": field, "value": value})
            return None

    # =========================================================================
    # Contacts (Decisores)
    # =========================================================================

    def create_contact(self, properties: Dict[str, Any]) -> Optional[str]:
        """Cria Contact no HubSpot. Retorna hubspot_id ou None."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.contacts import SimplePublicObjectInputForCreate
            clean = {k: str(v) if v is not None else "" for k, v in properties.items()}
            obj = SimplePublicObjectInputForCreate(properties=clean)
            result = self._retry(self._client.crm.contacts.basic_api.create, simple_public_object_input_for_create=obj)
            hubspot_id = result.id
            logger.info("HubSpot Contact criado", extra={"hubspot_id": hubspot_id, "email": properties.get("email", "")})
            return hubspot_id
        except Exception as e:
            error_str = str(e)
            # Contato ja existe (409 Conflict) - buscar e retornar ID existente
            if "409" in error_str or "CONFLICT" in error_str:
                email = properties.get("email", "")
                if email:
                    existing = self.search_contact("email", email)
                    if existing:
                        logger.info("HubSpot Contact ja existe, retornando ID", extra={"hubspot_id": existing["id"]})
                        return existing["id"]
            logger.error("Erro ao criar HubSpot Contact", extra={"error": error_str})
            return None

    def update_contact(self, hubspot_id: str, properties: Dict[str, Any]) -> bool:
        """Atualiza Contact existente."""
        if not self._enabled:
            return False
        try:
            from hubspot.crm.contacts import SimplePublicObjectInput
            obj = SimplePublicObjectInput(properties={k: str(v) if v is not None else "" for k, v in properties.items()})
            self._retry(self._client.crm.contacts.basic_api.update, contact_id=hubspot_id, simple_public_object_input=obj)
            return True
        except Exception as e:
            logger.error("Erro ao atualizar HubSpot Contact", extra={"error": str(e), "hubspot_id": hubspot_id})
            return False

    def search_contact(self, field: str, value: str) -> Optional[Dict[str, Any]]:
        """Busca Contact por campo (ex: email)."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
            f = Filter(property_name=field, operator="EQ", value=value)
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(filter_groups=[fg], limit=1)
            result = self._retry(self._client.crm.contacts.search_api.do_search, public_object_search_request=req)
            if result.results:
                r = result.results[0]
                return {"id": r.id, "properties": r.properties}
            return None
        except Exception as e:
            logger.error("Erro ao buscar HubSpot Contact", extra={"error": str(e), "field": field, "value": value})
            return None

    # =========================================================================
    # PULL METHODS — Sincronização reversa (HubSpot → Agente)
    # =========================================================================

    def list_modified_companies(self, since, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista companies modificadas no HubSpot desde `since` (datetime).
        Retorna lista de dicts com id, properties, updatedAt.
        """
        if not self._enabled:
            return []
        try:
            from hubspot.crm.companies import PublicObjectSearchRequest, Filter, FilterGroup
            since_ts = int(since.timestamp() * 1000)  # HubSpot usa epoch em ms
            f = Filter(property_name="hs_lastmodifieddate", operator="GTE", value=str(since_ts))
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(
                filter_groups=[fg],
                limit=limit,
                properties=["name", "domain", "inep_code", "city", "state", "phone", "website", "hs_lastmodifieddate", "lifecyclestage"],
            )
            result = self._retry(self._client.crm.companies.search_api.do_search, public_object_search_request=req)
            return [{"id": r.id, "properties": r.properties, "updated_at": r.updated_at} for r in (result.results or [])]
        except Exception as e:
            logger.error("Erro ao listar companies modificadas", extra={"error": str(e)})
            return []

    def list_modified_contacts(self, since, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista contacts modificados no HubSpot desde `since` (datetime)."""
        if not self._enabled:
            return []
        try:
            from hubspot.crm.contacts import PublicObjectSearchRequest, Filter, FilterGroup
            since_ts = int(since.timestamp() * 1000)
            f = Filter(property_name="lastmodifieddate", operator="GTE", value=str(since_ts))
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(
                filter_groups=[fg],
                limit=limit,
                properties=["firstname", "lastname", "email", "phone", "jobtitle", "lastmodifieddate", "lifecyclestage"],
            )
            result = self._retry(self._client.crm.contacts.search_api.do_search, public_object_search_request=req)
            return [{"id": r.id, "properties": r.properties, "updated_at": r.updated_at} for r in (result.results or [])]
        except Exception as e:
            logger.error("Erro ao listar contacts modificados", extra={"error": str(e)})
            return []

    def list_modified_deals(self, since, limit: int = 100) -> List[Dict[str, Any]]:
        """Lista deals modificados no HubSpot desde `since` (datetime)."""
        if not self._enabled:
            return []
        try:
            from hubspot.crm.deals import PublicObjectSearchRequest, Filter, FilterGroup
            since_ts = int(since.timestamp() * 1000)
            f = Filter(property_name="hs_lastmodifieddate", operator="GTE", value=str(since_ts))
            fg = FilterGroup(filters=[f])
            req = PublicObjectSearchRequest(
                filter_groups=[fg],
                limit=limit,
                properties=["dealname", "dealstage", "amount", "closedate", "hs_lastmodifieddate", "pipeline"],
            )
            result = self._retry(self._client.crm.deals.search_api.do_search, public_object_search_request=req)
            return [{"id": r.id, "properties": r.properties, "updated_at": r.updated_at} for r in (result.results or [])]
        except Exception as e:
            logger.error("Erro ao listar deals modificados", extra={"error": str(e)})
            return []

    def get_company(self, hubspot_id: str) -> Optional[Dict[str, Any]]:
        """Busca detalhes de uma company pelo ID do HubSpot."""
        if not self._enabled:
            return None
        try:
            result = self._retry(
                self._client.crm.companies.basic_api.get_by_id,
                company_id=hubspot_id,
                properties=["name", "domain", "inep_code", "city", "state", "phone", "website", "lifecyclestage"],
            )
            return {"id": result.id, "properties": result.properties}
        except Exception as e:
            logger.error("Erro ao buscar company por ID", extra={"error": str(e), "id": hubspot_id})
            return None

    # =========================================================================
    # Deals (Oportunidades)
    # =========================================================================

    def create_deal(self, properties: Dict[str, Any],
                    company_hubspot_id: Optional[str] = None,
                    contact_hubspot_id: Optional[str] = None) -> Optional[str]:
        """Cria Deal no HubSpot com associacoes opcionais. Retorna hubspot_id."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.deals import SimplePublicObjectInputForCreate
            from hubspot.crm.deals import PublicAssociationsForObject, AssociationSpec
            associations = []
            if company_hubspot_id:
                assoc = PublicAssociationsForObject(
                    types=[AssociationSpec(association_category="HUBSPOT_DEFINED", association_type_id=5)],
                    to={"id": company_hubspot_id},
                )
                associations.append(assoc)
            if contact_hubspot_id:
                assoc = PublicAssociationsForObject(
                    types=[AssociationSpec(association_category="HUBSPOT_DEFINED", association_type_id=3)],
                    to={"id": contact_hubspot_id},
                )
                associations.append(assoc)
            clean = {k: str(v) if v is not None else "" for k, v in properties.items()}
            obj = SimplePublicObjectInputForCreate(properties=clean, associations=associations if associations else None)
            result = self._retry(self._client.crm.deals.basic_api.create, simple_public_object_input_for_create=obj)
            hubspot_id = result.id
            logger.info("HubSpot Deal criado", extra={"hubspot_id": hubspot_id, "dealname": properties.get("dealname", "")})
            return hubspot_id
        except Exception as e:
            logger.error("Erro ao criar HubSpot Deal", extra={"error": str(e)})
            return None

    def update_deal(self, hubspot_id: str, properties: Dict[str, Any]) -> bool:
        """Atualiza Deal existente (ex: mudar stage)."""
        if not self._enabled:
            return False
        try:
            from hubspot.crm.deals import SimplePublicObjectInput
            obj = SimplePublicObjectInput(properties={k: str(v) if v is not None else "" for k, v in properties.items()})
            self._retry(self._client.crm.deals.basic_api.update, deal_id=hubspot_id, simple_public_object_input=obj)
            logger.info("HubSpot Deal atualizado", extra={"hubspot_id": hubspot_id})
            return True
        except Exception as e:
            logger.error("Erro ao atualizar HubSpot Deal", extra={"error": str(e), "hubspot_id": hubspot_id})
            return False

    # =========================================================================
    # Pipelines
    # =========================================================================

    def get_deal_pipelines(self) -> List[Dict[str, Any]]:
        """Lista pipelines de deals existentes."""
        if not self._enabled:
            return []
        try:
            result = self._retry(self._client.crm.pipelines.pipelines_api.get_all, object_type="deals")
            return [{"id": p.id, "label": p.label, "stages": [
                {"id": s.id, "label": s.label, "display_order": s.display_order}
                for s in p.stages
            ]} for p in result.results]
        except Exception as e:
            logger.error("Erro ao listar pipelines", extra={"error": str(e)})
            return []

    def create_deal_pipeline(self, label: str, stages: List[Dict[str, Any]]) -> Optional[str]:
        """Cria pipeline de deals com stages. Retorna pipeline_id."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.pipelines import PipelineInput, PipelineStageInput
            stage_inputs = [
                PipelineStageInput(
                    label=s["label"],
                    display_order=s["display_order"],
                    metadata={"probability": str(s.get("probability", "0.0"))},
                )
                for s in stages
            ]
            pipeline_input = PipelineInput(label=label, stages=stage_inputs, display_order=0)
            result = self._retry(
                self._client.crm.pipelines.pipelines_api.create,
                object_type="deals",
                pipeline_input=pipeline_input,
            )
            logger.info("HubSpot Pipeline criado", extra={"pipeline_id": result.id, "label": label})
            return result.id
        except Exception as e:
            logger.error("Erro ao criar pipeline", extra={"error": str(e), "label": label})
            return None

    # =========================================================================
    # Properties (Custom Fields)
    # =========================================================================

    def create_property(self, object_type: str, name: str, label: str,
                        prop_type: str = "string", field_type: str = "text",
                        group_name: str = "iaprendo",
                        options: Optional[List[Dict[str, str]]] = None) -> bool:
        """Cria custom property em Companies, Contacts ou Deals."""
        if not self._enabled:
            return False
        try:
            from hubspot.crm.properties import PropertyCreate
            kwargs = {
                "name": name, "label": label, "type": prop_type,
                "field_type": field_type, "group_name": group_name,
            }
            if options:
                kwargs["options"] = [{"label": o["label"], "value": o["value"]} for o in options]
            prop = PropertyCreate(**kwargs)
            self._retry(
                self._client.crm.properties.core_api.create,
                object_type=object_type,
                property_create=prop,
            )
            logger.info("HubSpot Property criada", extra={"object_type": object_type, "prop_name": name})
            return True
        except Exception as e:
            if "PROPERTY_EXISTS" in str(e) or "already exists" in str(e).lower():
                logger.info("HubSpot Property ja existe", extra={"object_type": object_type, "prop_name": name})
                return True
            logger.error("Erro ao criar property", extra={"error": str(e), "prop_name": name})
            return False

    def create_property_group(self, object_type: str, group_name: str, group_label: str) -> bool:
        """Cria grupo de propriedades customizadas."""
        if not self._enabled:
            return False
        try:
            from hubspot.crm.properties import PropertyGroupCreate
            group = PropertyGroupCreate(name=group_name, label=group_label)
            self._retry(
                self._client.crm.properties.groups_api.create,
                object_type=object_type,
                property_group_create=group,
            )
            logger.info("HubSpot Property Group criado", extra={"object_type": object_type, "group_name": group_name})
            return True
        except Exception as e:
            if "already exists" in str(e).lower() or "GROUP_EXISTS" in str(e):
                return True
            logger.error("Erro ao criar property group", extra={"error": str(e), "group_name": group_name})
            return False

    # =========================================================================
    # Engagements (Timeline/Notes)
    # =========================================================================

    def create_note(self, body: str, company_id: Optional[str] = None,
                    contact_id: Optional[str] = None, deal_id: Optional[str] = None) -> Optional[str]:
        """Cria nota (engagement) associada a objetos."""
        if not self._enabled:
            return None
        try:
            from hubspot.crm.objects.notes import SimplePublicObjectInputForCreate, PublicAssociationsForObject, AssociationSpec
            associations = []
            if company_id:
                associations.append(PublicAssociationsForObject(
                    types=[AssociationSpec(association_category="HUBSPOT_DEFINED", association_type_id=190)],
                    to={"id": company_id},
                ))
            if contact_id:
                associations.append(PublicAssociationsForObject(
                    types=[AssociationSpec(association_category="HUBSPOT_DEFINED", association_type_id=202)],
                    to={"id": contact_id},
                ))
            if deal_id:
                associations.append(PublicAssociationsForObject(
                    types=[AssociationSpec(association_category="HUBSPOT_DEFINED", association_type_id=214)],
                    to={"id": deal_id},
                ))
            obj = SimplePublicObjectInputForCreate(
                properties={"hs_note_body": body, "hs_timestamp": str(int(time.time() * 1000))},
                associations=associations if associations else None,
            )
            result = self._retry(self._client.crm.objects.notes.basic_api.create, simple_public_object_input_for_create=obj)
            return result.id
        except Exception as e:
            logger.error("Erro ao criar nota HubSpot", extra={"error": str(e)})
            return None


# Singleton
hubspot_client = HubSpotClient()
