"""
HubSpot Pull - Sincronizacao reversa (HubSpot -> Supabase).

Puxa mudancas do HubSpot e atualiza o Supabase incrementalmente.
Usa a tabela sync_state para rastrear o timestamp do ultimo pull.

Regras de resolucao de conflitos:
- Mudanca mais recente vence (comparar updated_at)
- Campos protegidos no Supabase: qualification_score, qualification_reasoning (gerados pela IA)
- Atualiza apenas campos mapeados (nao sobrescreve tudo)

Usage:
    from integrations.hubspot_pull import hubspot_pull
    result = hubspot_pull.pull_changes()
    # {"companies": 5, "contacts": 12, "deals": 3, "errors": 0}
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from database.supabase_client import db
from integrations.hubspot_client import hubspot_client
from utils.logger import logger


# Campos do HubSpot que nao devem sobrescrever os do Supabase
# (sao gerados pela IA e sao fonte de verdade interna)
PROTECTED_SUPABASE_FIELDS = {
    "qualification_score",
    "qualification_reasoning",
}


class HubSpotPull:
    """Puxa mudancas do HubSpot e atualiza o Supabase."""

    SOURCE_KEY = "hubspot_pull"

    def get_last_sync(self) -> datetime:
        """Retorna o timestamp do ultimo pull. Se nunca rodou, retorna 24h atras."""
        try:
            result = db.client.table("sync_state").select("*").eq("source", self.SOURCE_KEY).limit(1).execute()
            if result.data:
                last = result.data[0].get("last_sync_at")
                if last:
                    # Parse ISO timestamp
                    if isinstance(last, str):
                        return datetime.fromisoformat(last.replace("Z", "+00:00"))
                    return last
        except Exception as e:
            logger.warning(f"Erro ao buscar sync_state, usando fallback 24h: {e}")
        return datetime.now(timezone.utc) - timedelta(hours=24)

    def update_sync_state(self, status: str, records: int, error: str = "") -> None:
        """Atualiza o timestamp do ultimo pull."""
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            data = {
                "source": self.SOURCE_KEY,
                "last_sync_at": now_iso,
                "last_status": status,
                "last_error": error[:500] if error else None,
                "records_updated": records,
                "updated_at": now_iso,
            }
            # Upsert
            existing = db.client.table("sync_state").select("id").eq("source", self.SOURCE_KEY).execute()
            if existing.data:
                db.client.table("sync_state").update(data).eq("source", self.SOURCE_KEY).execute()
            else:
                data["created_at"] = now_iso
                db.client.table("sync_state").insert(data).execute()
        except Exception as e:
            logger.error(f"Erro ao atualizar sync_state: {e}")

    def _update_company_from_hubspot(self, hs_company: Dict[str, Any]) -> bool:
        """Atualiza uma company no Supabase com dados do HubSpot (se existir)."""
        props = hs_company.get("properties", {})
        hubspot_id = hs_company.get("id")
        if not hubspot_id:
            return False

        # Buscar no Supabase pelo hubspot_company_id (nome correto da coluna
        # em companies — "hubspot_id" nao existe nessa tabela)
        try:
            existing = db.client.table("companies").select("*").eq("hubspot_company_id", str(hubspot_id)).limit(1).execute()
            if not existing.data:
                # Nao existe no Supabase — pular (nao criar retroativamente)
                return False

            company = existing.data[0]
            updates = {}

            # Mapear campos HubSpot -> Supabase (apenas os permitidos)
            # NOTA: `lifecyclestage` do HubSpot (lead/opportunity/customer/...)
            # NAO mapeia diretamente para `commercial_stage` do Supabase
            # (prospectado/contatado/respondeu/reuniao/proposta/cliente/perdido).
            # Traducao requer pensar na semantica de cada valor — deixado como
            # TODO. Se voltar a adicionar aqui, garanta que os valores mapeados
            # batem com companies_commercial_stage_chk.
            field_map = {
                "name": "name",
                "city": "city",
                "state": "state",
                "phone": "phone",
                "website": "website",
            }
            for hs_field, sb_field in field_map.items():
                if sb_field in PROTECTED_SUPABASE_FIELDS:
                    continue
                new_val = props.get(hs_field)
                if new_val is not None and new_val != company.get(sb_field):
                    updates[sb_field] = new_val

            if updates:
                updates["updated_at"] = datetime.now(timezone.utc).isoformat()
                db.client.table("companies").update(updates).eq("id", company["id"]).execute()
                logger.info("Company atualizada via HubSpot pull", extra={"company_id": company["id"], "fields": list(updates.keys())})
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao atualizar company do HubSpot: {e}")
            return False

    def _update_contact_from_hubspot(self, hs_contact: Dict[str, Any]) -> bool:
        """Atualiza um contato no Supabase com dados do HubSpot."""
        props = hs_contact.get("properties", {})
        hubspot_id = hs_contact.get("id")
        if not hubspot_id:
            return False

        try:
            # Nome correto da coluna em contacts eh hubspot_contact_id
            existing = db.client.table("contacts").select("*").eq("hubspot_contact_id", str(hubspot_id)).limit(1).execute()
            if not existing.data:
                return False

            contact = existing.data[0]
            updates = {}

            # Nome completo
            firstname = props.get("firstname", "") or ""
            lastname = props.get("lastname", "") or ""
            full_name = f"{firstname} {lastname}".strip()
            if full_name and full_name != contact.get("full_name"):
                updates["full_name"] = full_name

            # Outros campos
            if props.get("email") and props.get("email") != contact.get("email"):
                updates["email"] = props.get("email")
            if props.get("phone") and props.get("phone") != contact.get("phone"):
                updates["phone"] = props.get("phone")
            if props.get("jobtitle") and props.get("jobtitle") != contact.get("role"):
                updates["role"] = props.get("jobtitle")

            if updates:
                updates["updated_at"] = datetime.now(timezone.utc).isoformat()
                db.client.table("contacts").update(updates).eq("id", contact["id"]).execute()
                logger.info("Contact atualizado via HubSpot pull", extra={"contact_id": contact["id"], "fields": list(updates.keys())})
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao atualizar contact do HubSpot: {e}")
            return False

    def _update_deal_from_hubspot(self, hs_deal: Dict[str, Any]) -> bool:
        """Atualiza deal stage na tabela companies (via notes ou campo proprio)."""
        props = hs_deal.get("properties", {})
        hubspot_deal_id = hs_deal.get("id")
        if not hubspot_deal_id:
            return False

        try:
            existing = db.client.table("companies").select("id,notes").eq("hubspot_deal_id", str(hubspot_deal_id)).limit(1).execute()
            if not existing.data:
                return False

            company = existing.data[0]
            new_stage = props.get("dealstage", "")
            if not new_stage:
                return False

            # Atualizar notas com o novo stage (o Supabase nao tem campo dealstage direto)
            current_notes = company.get("notes") or ""
            # Remover marker antigo
            import re
            cleaned = re.sub(r"\[hubspot_stage:[^\]]*\]", "", current_notes).strip()
            new_notes = f"{cleaned} [hubspot_stage:{new_stage}]".strip()

            db.client.table("companies").update({
                "notes": new_notes,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", company["id"]).execute()
            logger.info("Deal stage atualizado via HubSpot pull", extra={"company_id": company["id"], "stage": new_stage})
            return True
        except Exception as e:
            logger.error(f"Erro ao atualizar deal do HubSpot: {e}")
            return False

    def pull_changes(self) -> Dict[str, Any]:
        """Executa pull completo: companies, contacts, deals.
        Retorna dict com contagens e erros.
        """
        if not hubspot_client._enabled:
            return {"error": "HubSpot nao configurado", "companies": 0, "contacts": 0, "deals": 0}

        since = self.get_last_sync()
        logger.info(f"Iniciando HubSpot pull desde {since.isoformat()}")

        result = {"companies": 0, "contacts": 0, "deals": 0, "errors": 0, "since": since.isoformat()}

        try:
            # Companies
            hs_companies = hubspot_client.list_modified_companies(since, limit=100)
            for hc in hs_companies:
                try:
                    if self._update_company_from_hubspot(hc):
                        result["companies"] += 1
                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Erro ao processar company: {e}")

            # Contacts
            hs_contacts = hubspot_client.list_modified_contacts(since, limit=100)
            for hc in hs_contacts:
                try:
                    if self._update_contact_from_hubspot(hc):
                        result["contacts"] += 1
                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Erro ao processar contact: {e}")

            # Deals
            hs_deals = hubspot_client.list_modified_deals(since, limit=100)
            for hd in hs_deals:
                try:
                    if self._update_deal_from_hubspot(hd):
                        result["deals"] += 1
                except Exception as e:
                    result["errors"] += 1
                    logger.error(f"Erro ao processar deal: {e}")

            total = result["companies"] + result["contacts"] + result["deals"]
            self.update_sync_state("success", total)
            logger.info(f"HubSpot pull concluido: {total} registros atualizados", extra=result)

        except Exception as e:
            logger.error(f"Erro geral no HubSpot pull: {e}", exc_info=True)
            self.update_sync_state("error", 0, str(e))
            result["error"] = str(e)

        return result


hubspot_pull = HubSpotPull()
