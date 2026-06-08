"""
Supabase Client - Cliente de banco de dados com rate limiting persistente.

Este módulo fornece uma camada de abstração sobre o Supabase (PostgreSQL)
com métodos CRUD completos e controle de uso de APIs (rate limiting).

Classes:
    DatabaseError: Exception customizada para erros de banco
    Database: Cliente principal com métodos CRUD

Usage:
    from database.supabase_client import db

    # Buscar escola por INEP (evita duplicatas)
    school = db.get_company_by_inep("43000001")

    # Inserir nova escola
    company_id = db.insert_company({
        'name': 'Escola Teste',
        'inep_code': '43000001',
        'city': 'Porto Alegre',
        'state': 'RS'
    })

    # Rate limiting (CRÍTICO)
    cutoff = datetime.now() - timedelta(days=30)
    apollo_used = db.count_api_usage_since('apollo', cutoff)
    if apollo_used < 60:
        # OK para usar Apollo
        pass
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from supabase import create_client, Client
from config.settings import settings
from utils.logger import logger, log_database_operation


# ============================================================================
# EXCEPTIONS
# ============================================================================

class DatabaseError(Exception):
    """Exception base para erros de banco de dados."""
    pass


class DuplicateRecordError(DatabaseError):
    """Tentativa de inserir registro duplicado."""
    pass


class RecordNotFoundError(DatabaseError):
    """Registro não encontrado."""
    pass


# ============================================================================
# DATABASE CLIENT
# ============================================================================

class Database:
    """
    Cliente de banco de dados Supabase com rate limiting persistente.

    Attributes:
        client: Cliente Supabase configurado.

    Methods:
        Companies (Escolas):
            - get_company_by_inep: Busca escola por código INEP único
            - insert_company: Insere nova escola (detecta duplicatas)
            - update_company: Atualiza dados da escola
            - get_companies_by_status: Lista escolas por status

        Contacts (Decisores):
            - insert_contact: Insere contato (decisor)
            - get_contacts_by_company: Lista contatos de uma escola

        Approval Queue:
            - get_pending_approvals: Lista mensagens aguardando aprovação
            - approve_message: Aprova mensagem para envio
            - reject_message: Rejeita mensagem

        Interactions (Histórico):
            - insert_interaction: Registra interação

        API Usage (Rate Limiting): ⭐ CRÍTICO
            - count_api_usage_since: Conta usos desde data específica
            - count_api_usage_this_month: Atalho para mês atual
            - insert_api_usage: Registra uso de API
    """

    def __init__(self):
        """Inicializa cliente Supabase."""
        try:
            self.client: Client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            logger.info(
                "Cliente Supabase inicializado",
                extra={'url': settings.SUPABASE_URL[:30] + '...'}
            )
        except Exception as e:
            logger.critical(
                "Falha ao inicializar Supabase",
                extra={'error': str(e)},
                exc_info=True
            )
            raise DatabaseError("Não foi possível conectar ao Supabase") from e

    # ========================================================================
    # COMPANIES (Escolas/Leads)
    # ========================================================================

    def get_company_by_inep(self, inep_code: str) -> Optional[Dict[str, Any]]:
        """
        Busca escola por código INEP único.

        ⭐ CRÍTICO - Sempre use este método antes de inserir para evitar duplicatas.

        Args:
            inep_code: Código INEP da escola (chave única).

        Returns:
            Dicionário com dados da escola ou None se não encontrada.

        Raises:
            DatabaseError: Se houver erro na consulta.

        Example:
            >>> company = db.get_company_by_inep("43000001")
            >>> if company:
            >>>     print(company['name'])
            >>> else:
            >>>     print("Escola não encontrada")
        """
        try:
            result = self.client.table('companies')\
                .select('*')\
                .eq('inep_code', inep_code)\
                .execute()

            if result.data:
                logger.debug(
                    "Escola encontrada por INEP",
                    extra={
                        'inep_code': inep_code,
                        'company_id': result.data[0]['id']
                    }
                )
                return result.data[0]

            return None

        except Exception as e:
            logger.error(
                "Erro ao buscar empresa por INEP",
                extra={'inep_code': inep_code, 'error': str(e)},
                exc_info=True
            )
            raise DatabaseError(f"Falha ao buscar INEP {inep_code}") from e

    def insert_company(self, company_data: Dict[str, Any]) -> Optional[str]:
        """
        Insere nova escola no banco.

        ⚠️ ATENÇÃO: Verifica duplicata por INEP antes de inserir.
        Se já existir, retorna o ID do registro existente.

        Args:
            company_data: Dicionário com dados da escola.
                Campos obrigatórios: name, inep_code
                Campos opcionais: city, state, address, phone, etc.

        Returns:
            UUID da empresa (str) ou None se falhar.

        Raises:
            DatabaseError: Se houver erro na inserção.
            ValueError: Se faltar campo obrigatório.

        Example:
            >>> company_id = db.insert_company({
            >>>     'name': 'Escola Exemplo',
            >>>     'inep_code': '43000001',
            >>>     'city': 'Porto Alegre',
            >>>     'state': 'RS',
            >>>     'status': 'raw'
            >>> })
        """
        # Validação
        if 'name' not in company_data or 'inep_code' not in company_data:
            raise ValueError("Campos obrigatórios: name, inep_code")

        inep_code = company_data['inep_code']

        try:
            # Verificar duplicata
            existing = self.get_company_by_inep(inep_code)
            if existing:
                logger.warning(
                    "Escola já existe (duplicata detectada)",
                    extra={
                        'inep_code': inep_code,
                        'existing_id': existing['id']
                    }
                )
                return existing['id']

            # Inserir
            result = self.client.table('companies')\
                .insert(company_data)\
                .execute()

            if result.data:
                company_id = result.data[0]['id']
                logger.info(
                    "Escola inserida",
                    extra={
                        'company_id': company_id,
                        'inep_code': inep_code,
                        'school_name': company_data.get('name')
                    }
                )
                log_database_operation(
                    operation='INSERT',
                    table='companies',
                    rows_affected=1,
                    company_id=company_id
                )
                return company_id

            return None

        except Exception as e:
            logger.error(
                "Erro ao inserir empresa",
                extra={
                    'inep_code': inep_code,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DatabaseError(f"Falha ao inserir empresa {inep_code}") from e

    def update_company(
        self,
        company_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Atualiza dados de uma escola.

        Args:
            company_id: UUID da empresa.
            updates: Dicionário com campos a atualizar.

        Returns:
            Dicionário com dados atualizados ou None se falhar.

        Raises:
            DatabaseError: Se houver erro na atualização.

        Example:
            >>> updated = db.update_company(
            >>>     company_id="abc-123",
            >>>     updates={
            >>>         'status': 'qualified',
            >>>         'qualification_score': 85
            >>>     }
            >>> )
        """
        try:
            result = self.client.table('companies')\
                .update(updates)\
                .eq('id', company_id)\
                .execute()

            if result.data:
                logger.info(
                    "Empresa atualizada",
                    extra={
                        'company_id': company_id,
                        'fields_updated': list(updates.keys())
                    }
                )
                log_database_operation(
                    operation='UPDATE',
                    table='companies',
                    rows_affected=1,
                    company_id=company_id
                )
                return result.data[0]

            return None

        except Exception as e:
            logger.error(
                "Erro ao atualizar empresa",
                extra={
                    'company_id': company_id,
                    'error': str(e)
                },
                exc_info=True
            )
            raise DatabaseError(f"Falha ao atualizar empresa {company_id}") from e

    def get_companies_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Lista escolas por status.

        Args:
            status: Status desejado (raw, filtered, qualified, enriched, contacted).
            limit: Número máximo de resultados (default: 100).

        Returns:
            Lista de dicionários com dados das escolas.

        Raises:
            DatabaseError: Se houver erro na consulta.

        Example:
            >>> qualified = db.get_companies_by_status('qualified', limit=50)
            >>> for company in qualified:
            >>>     print(company['name'], company['qualification_score'])
        """
        try:
            result = self.client.table('companies')\
                .select('*')\
                .eq('status', status)\
                .order('qualification_score', desc=True)\
                .limit(limit)\
                .execute()

            logger.debug(
                "Empresas listadas por status",
                extra={
                    'status': status,
                    'count': len(result.data),
                    'limit': limit
                }
            )

            return result.data

        except Exception as e:
            logger.error(
                "Erro ao listar empresas por status",
                extra={'status': status, 'error': str(e)},
                exc_info=True
            )
            raise DatabaseError(f"Falha ao listar empresas com status {status}") from e

    def get_companies_by_ids(
        self,
        company_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Retorna empresas por lista de IDs."""
        if not company_ids:
            return []
        try:
            result = self.client.table('companies')\
                .select('*')\
                .in_('id', company_ids)\
                .order('qualification_score', desc=True)\
                .execute()
            return result.data or []
        except Exception as e:
            logger.error("Erro ao buscar empresas por IDs", extra={'error': str(e)})
            return []

    def get_companies_by_ids_and_status(
        self,
        company_ids: List[str],
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retorna empresas filtradas por IDs (e opcionalmente status).

        Args:
            company_ids: Lista de UUIDs a buscar.
            status: Status para filtrar. Se None, retorna TODAS as escolas
                    nos IDs sem filtro de status (modo "forcar reprocessar").
        """
        if not company_ids:
            return []
        try:
            q = self.client.table('companies').select('*').in_('id', company_ids)
            if status is not None:
                q = q.eq('status', status)
            result = q.order('qualification_score', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error("Erro ao buscar empresas por IDs e status",
                         extra={'error': str(e), 'status': status})
            return []

    # ========================================================================
    # CONTACTS (Decisores)
    # ========================================================================

    def insert_contact(self, contact_data: Dict[str, Any]) -> Optional[str]:
        """
        Insere contato (decisor) de uma escola.

        Args:
            contact_data: Dicionário com dados do contato.
                Campos obrigatórios: company_id, full_name
                Campos opcionais: role, email, phone, linkedin_url, source

        Returns:
            UUID do contato (str) ou None se falhar.

        Raises:
            DatabaseError: Se houver erro na inserção.
            ValueError: Se faltar campo obrigatório.

        Example:
            >>> contact_id = db.insert_contact({
            >>>     'company_id': 'abc-123',
            >>>     'full_name': 'Maria Silva',
            >>>     'role': 'Diretora',
            >>>     'email': 'maria@escola.com',
            >>>     'source': 'apollo'
            >>> })
        """
        # Validação
        if 'company_id' not in contact_data or 'full_name' not in contact_data:
            raise ValueError("Campos obrigatórios: company_id, full_name")

        try:
            result = self.client.table('contacts')\
                .insert(contact_data)\
                .execute()

            if result.data:
                contact_id = result.data[0]['id']
                logger.info(
                    "Contato inserido",
                    extra={
                        'contact_id': contact_id,
                        'company_id': contact_data['company_id'],
                        'contact_name': contact_data['full_name']
                    }
                )
                return contact_id

            return None

        except Exception as e:
            logger.error(
                "Erro ao inserir contato",
                extra={
                    'company_id': contact_data.get('company_id'),
                    'error': str(e)
                },
                exc_info=True
            )
            raise DatabaseError("Falha ao inserir contato") from e

    def get_contacts_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        """
        Lista contatos de uma escola.

        Args:
            company_id: UUID da empresa.

        Returns:
            Lista de dicionários com dados dos contatos.

        Raises:
            DatabaseError: Se houver erro na consulta.

        Example:
            >>> contacts = db.get_contacts_by_company("abc-123")
            >>> for contact in contacts:
            >>>     print(contact['full_name'], contact['email'])
        """
        try:
            result = self.client.table('contacts')\
                .select('*')\
                .eq('company_id', company_id)\
                .execute()

            logger.debug(
                "Contatos listados",
                extra={
                    'company_id': company_id,
                    'count': len(result.data)
                }
            )

            return result.data

        except Exception as e:
            logger.error(
                "Erro ao listar contatos",
                extra={'company_id': company_id, 'error': str(e)},
                exc_info=True
            )
            raise DatabaseError(f"Falha ao listar contatos da empresa {company_id}") from e

    # ========================================================================
    # APPROVAL QUEUE (Fila de Aprovação)
    # ========================================================================

    def get_pending_approvals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista mensagens aguardando aprovação humana.

        Args:
            limit: Número máximo de resultados (default: 50).

        Returns:
            Lista de mensagens pendentes com dados completos.

        Raises:
            DatabaseError: Se houver erro na consulta.

        Example:
            >>> pending = db.get_pending_approvals(limit=10)
            >>> for msg in pending:
            >>>     print(msg['subject'], msg['company_id'])
        """
        try:
            result = self.client.table('approval_queue')\
                .select('*, companies(name, city), contacts(full_name, email)')\
                .eq('status', 'pending')\
                .order('created_at', desc=False)\
                .limit(limit)\
                .execute()

            logger.debug(
                "Aprovações pendentes listadas",
                extra={'count': len(result.data), 'limit': limit}
            )

            return result.data

        except Exception as e:
            logger.error(
                "Erro ao listar aprovações pendentes",
                extra={'error': str(e)},
                exc_info=True
            )
            raise DatabaseError("Falha ao listar aprovações pendentes") from e


    def insert_approval_queue(self, queue_data: Dict[str, Any]) -> Optional[str]:
        """Insere mensagem na approval_queue gravando created_by (autor).

        Resolve o sender ativo automaticamente se 'created_by' nao vier no dict.
        Tolerante: se a coluna created_by ainda nao existe (migration nao rodou),
        reinsere sem ela. Retorna o queue_id ou None.
        """
        try:
            if 'created_by' not in queue_data:
                _author = self._active_username()
                if _author:
                    queue_data['created_by'] = _author
            try:
                result = self.client.table('approval_queue').insert(queue_data).execute()
            except Exception as _e_ins:
                if 'created_by' in queue_data and (
                    'created_by' in str(_e_ins) or 'column' in str(_e_ins).lower()
                ):
                    queue_data.pop('created_by', None)
                    result = self.client.table('approval_queue').insert(queue_data).execute()
                else:
                    raise
            return result.data[0]['id'] if result.data else None
        except Exception as e:
            logger.error('Erro ao inserir na approval_queue',
                         extra={'company_id': queue_data.get('company_id'), 'error': str(e)})
            return None

    def approve_message(
        self,
        queue_id: str,
        edited_subject: str = None,
        edited_body: str = None,
        scheduled_send_at: str = None,
        send_as_username: str = None,
        attachment_urls: list = None,
    ) -> bool:
        """Aprova mensagem para envio. Se scheduled_send_at fornecido, agenda
        o envio para o horario especificado (ISO 8601). Se None, envia imediatamente.

        Args:
            send_as_username: Override admin para enviar como outro usuario.
                Salvo em metadata.send_as_username e lido por send_approved.py.
                None = usa o sender ativo no momento do envio (padrao).
            attachment_urls: Override de anexos para esta mensagem especifica.
                Lista de dicts [{"name", "url"}]. Salvo em metadata.attachment_urls.
                Se None = sticky default (anexos ativos do user resolvidos no envio).
                Se [] (lista vazia explicita) = enviar SEM anexos.
        """
        try:
            from datetime import datetime
            update = {'status': 'approved', 'approved_at': datetime.utcnow().isoformat()}
            if edited_subject:
                update['subject'] = edited_subject
            if edited_body:
                update['body'] = edited_body
            if scheduled_send_at:
                update['scheduled_send_at'] = scheduled_send_at
            # Merge metadata (envia ambos os overrides quando aplicavel)
            need_metadata = send_as_username is not None or attachment_urls is not None
            if need_metadata:
                try:
                    cur = (self.client.table('approval_queue').select('metadata')
                           .eq('id', queue_id).single().execute().data or {})
                    cur_meta = cur.get('metadata') or {}
                    if isinstance(cur_meta, str):
                        import json as _json
                        try:
                            cur_meta = _json.loads(cur_meta)
                        except Exception:
                            cur_meta = {}
                except Exception:
                    cur_meta = {}
                if send_as_username:
                    cur_meta['send_as_username'] = send_as_username
                if attachment_urls is not None:
                    # Aceita lista vazia (override pra "sem anexos")
                    cur_meta['attachment_urls'] = list(attachment_urls)
                update['metadata'] = cur_meta
            # GUARD DE CONCORRENCIA (compare-and-swap atomico): so atualiza se
            # ainda estiver 'pending'. Se outro user ja aprovou/rejeitou, o
            # WHERE nao casa, result.data vem vazio e retornamos False — evita
            # 2 usuarios aprovarem a mesma mensagem.
            result = (self.client.table('approval_queue').update(update)
                      .eq('id', queue_id).eq('status', 'pending').execute())
            success = bool(result.data)
            if success:
                extra = {'queue_id': queue_id}
                if scheduled_send_at:
                    extra['scheduled_send_at'] = scheduled_send_at
                if send_as_username:
                    extra['send_as'] = send_as_username
                logger.info('Mensagem aprovada', extra=extra)
                # AUTO-CLAIM: aprovar = comprometer-se com o envio -> vira dono
                # do lead (se sem dono). Dono = quem envia (send_as override ou
                # usuario ativo). Tolerante a falha.
                try:
                    _company_id = (result.data[0] or {}).get('company_id')
                    if _company_id:
                        self.claim_company_if_unowned(_company_id, send_as_username or None)
                except Exception:
                    pass
            else:
                logger.warning('Aprovacao ignorada: mensagem nao esta mais pending '
                               '(ja tratada por outro usuario?)', extra={'queue_id': queue_id})
            return success
        except Exception as e:
            logger.error('Erro ao aprovar mensagem', extra={'queue_id': queue_id, 'error': str(e)})
            return False

    def reject_message(self, queue_id: str, reason: str = '') -> bool:
        """Rejeita mensagem (so se ainda estiver pending — guard de concorrencia)."""
        try:
            update = {'status': 'rejected', 'rejection_reason': reason}
            # CAS atomico: so rejeita se ainda pending (ver approve_message)
            result = (self.client.table('approval_queue').update(update)
                      .eq('id', queue_id).eq('status', 'pending').execute())
            success = bool(result.data)
            if success:
                logger.info('Mensagem rejeitada', extra={'queue_id': queue_id, 'reason': reason})
            else:
                logger.warning('Rejeicao ignorada: mensagem nao esta mais pending '
                               '(ja tratada por outro usuario?)', extra={'queue_id': queue_id})
            return success
        except Exception as e:
            logger.error('Erro ao rejeitar mensagem', extra={'queue_id': queue_id, 'error': str(e)})
            return False


    def update_contact(self, contact_id: str, updates: dict) -> bool:
        """Atualiza dados de um contato existente."""
        try:
            result = self.client.table('contacts').update(updates).eq('id', contact_id).execute()
            success = bool(result.data)
            if success:
                logger.info('Contato atualizado', extra={'contact_id': contact_id, 'fields': list(updates.keys())})
            return success
        except Exception as e:
            logger.error('Erro ao atualizar contato', extra={'contact_id': contact_id, 'error': str(e)})
            return False

    def set_contact_on_queue(self, queue_id: str, contact_id: str) -> bool:
        """Associa um contato a uma mensagem na approval_queue."""
        try:
            result = self.client.table('approval_queue').update({'contact_id': contact_id}).eq('id', queue_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error('Erro ao associar contato na fila', extra={'queue_id': queue_id, 'error': str(e)})
            return False

    # ======================================================================
    # INTERACTIONS (Histórico)
    # ========================================================================

    # Mapeamento canal+direcao -> type (ver constraint valid_interaction_type)
    _MANUAL_INTERACTION_TYPE_MAP = {
        ("whatsapp", "sent"): "whatsapp_sent",
        ("whatsapp", "received"): "whatsapp_replied",
        ("email", "sent"): "email_sent",
        ("email", "received"): "email_replied",
        ("phone", "sent"): "call_made",
        ("phone", "received"): "call_received",
        ("linkedin", "sent"): "linkedin_sent",
        ("linkedin", "received"): "linkedin_replied",
    }

    # Status que avancam para "contacted" quando registramos contato manual.
    # Os demais (contacted, responded, converted, rejected) preservam o estado
    # atual — nao queremos regredir leads que ja avancaram alem.
    _STATUS_ADVANCEABLE = {"raw", "filtered", "qualified", "enriched"}

    def register_manual_interaction(
        self,
        company_id: str,
        channel: str,
        direction: str = "sent",
        contact_id: Optional[str] = None,
        notes: str = "",
        interaction_date: Optional[str] = None,
        advance_status: bool = True,
        advance_commercial_stage: bool = False,
        source: str = "dashboard",
    ) -> Dict[str, Any]:
        """Registra contato manual feito pelo Fernando fora da plataforma.

        Operacao atomica do ponto de vista do usuario:
        1. Insere linha em `interactions` com type apropriado para canal+direcao
        2. Atualiza `companies.last_contacted_at` = interaction_date (ou NOW())
        3. Se advance_status=True e status atual eh inicial, move para 'contacted'
        4. Se advance_commercial_stage=True e stage atual eh nulo/'prospectado',
           move para 'contatado' (Kanban comercial)

        Args:
            company_id: UUID da escola.
            channel: 'whatsapp' | 'email' | 'phone' | 'linkedin'.
            direction: 'sent' (Fernando contatou) | 'received' (escola contatou).
            contact_id: UUID do contato/decisor (opcional).
            notes: Observacao livre (vai para `message_snippet`, max 500 chars).
            interaction_date: ISO 8601 (ex '2026-04-25T15:30:00-03:00'). None=NOW().
            advance_status: Move companies.status -> 'contacted' se aplicavel.
            advance_commercial_stage: Move companies.commercial_stage -> 'contatado' se aplicavel.
            source: Origem do registro ('dashboard' | 'ialex' | 'api'). Vai para metadata.

        Returns:
            Dict com:
                - interaction_id: UUID da interacao criada
                - type: type derivado (ex 'whatsapp_sent')
                - status_changed: novo status se mudou, None senao
                - commercial_stage_changed: nova stage se mudou, None senao

        Raises:
            ValueError: canal/direction invalidos ou company_id nao encontrado.
            DatabaseError: falha ao escrever no Supabase.
        """
        # Validacao
        channel = (channel or "").strip().lower()
        direction = (direction or "sent").strip().lower()
        key = (channel, direction)
        if key not in self._MANUAL_INTERACTION_TYPE_MAP:
            raise ValueError(
                f"Combinacao canal/direction invalida: {key}. "
                f"Validos: {list(self._MANUAL_INTERACTION_TYPE_MAP.keys())}"
            )
        if not company_id:
            raise ValueError("company_id obrigatorio")

        interaction_type = self._MANUAL_INTERACTION_TYPE_MAP[key]
        when = interaction_date or datetime.utcnow().isoformat()

        # 1) Inserir interacao
        payload: Dict[str, Any] = {
            "company_id": company_id,
            "type": interaction_type,
            "channel": channel,
            "created_at": when,
            "metadata": {"source": source, "manual": True, "direction": direction},
        }
        if contact_id:
            payload["contact_id"] = contact_id
        if notes:
            payload["message_snippet"] = notes[:500]

        interaction_id = self.insert_interaction(payload)

        # 2) Atualizar last_contacted_at + (opcional) status / commercial_stage
        company_update: Dict[str, Any] = {"last_contacted_at": when}
        status_changed: Optional[str] = None
        commercial_stage_changed: Optional[str] = None

        # Buscar estado atual para decidir avanco
        current = (
            self.client.table("companies")
            .select("status,commercial_stage")
            .eq("id", company_id)
            .single()
            .execute()
        )
        if not current.data:
            raise ValueError(f"Escola {company_id} nao encontrada")

        cur_status = (current.data.get("status") or "raw").lower()
        cur_stage = (current.data.get("commercial_stage") or "").lower()

        if advance_status and cur_status in self._STATUS_ADVANCEABLE:
            company_update["status"] = "contacted"
            status_changed = "contacted"

        if advance_commercial_stage and cur_stage in ("", "prospectado"):
            company_update["commercial_stage"] = "contatado"
            commercial_stage_changed = "contatado"

        # Update sempre acontece (last_contacted_at no minimo)
        try:
            self.client.table("companies").update(company_update).eq(
                "id", company_id
            ).execute()
        except Exception as e:
            logger.warning(
                "Interacao registrada mas falhou update da company",
                extra={"company_id": company_id, "error": str(e)},
            )

        # AUTO-CLAIM: registrar contato manual = trabalhar o lead -> vira dono
        # (se ainda nao tiver). Tolerante a falha (nunca quebra o registro).
        owner = None
        try:
            owner = self.claim_company_if_unowned(company_id)
        except Exception:
            pass

        return {
            "interaction_id": interaction_id,
            "type": interaction_type,
            "status_changed": status_changed,
            "commercial_stage_changed": commercial_stage_changed,
            "when": when,
            "owner": owner,
        }

    def insert_interaction(self, interaction_data: Dict[str, Any]) -> Optional[str]:
        """
        Registra interação com lead.

        Args:
            interaction_data: Dicionário com dados da interação.
                Campos obrigatórios: company_id, type, channel
                Campos opcionais: contact_id, subject, metadata

        Returns:
            UUID da interação (str) ou None se falhar.

        Raises:
            DatabaseError: Se houver erro na inserção.
            ValueError: Se faltar campo obrigatório.

        Example:
            >>> interaction_id = db.insert_interaction({
            >>>     'company_id': 'abc-123',
            >>>     'type': 'email_sent',
            >>>     'channel': 'email',
            >>>     'subject': 'Proposta IAprendo',
            >>>     'metadata': {'tracking_id': 'xyz-789'}
            >>> })
        """
        # Validação
        required = ['company_id', 'type', 'channel']
        if not all(field in interaction_data for field in required):
            raise ValueError(f"Campos obrigatórios: {', '.join(required)}")

        # Autoria: grava QUEM registrou (se nao informado, resolve sender ativo).
        # Tolerante: se a coluna created_by ainda nao existe (migration nao rodou),
        # o insert ignora chaves extras? Nao — Postgrest rejeita. Por isso so
        # adicionamos se houver valor, e o except abaixo ja captura falhas.
        if 'created_by' not in interaction_data:
            _author = self._active_username()
            if _author:
                interaction_data['created_by'] = _author

        try:
            try:
                result = self.client.table('interactions')\
                    .insert(interaction_data)\
                    .execute()
            except Exception as _e_ins:
                # Guard: se a coluna created_by ainda nao existe (migration
                # add_lead_ownership nao rodou), reinsere sem ela.
                if 'created_by' in interaction_data and (
                    'created_by' in str(_e_ins) or 'column' in str(_e_ins).lower()
                ):
                    interaction_data.pop('created_by', None)
                    result = self.client.table('interactions')\
                        .insert(interaction_data).execute()
                else:
                    raise

            if result.data:
                interaction_id = result.data[0]['id']
                logger.info(
                    "Interação registrada",
                    extra={
                        'interaction_id': interaction_id,
                        'company_id': interaction_data['company_id'],
                        'type': interaction_data['type']
                    }
                )
                return interaction_id

            return None

        except Exception as e:
            logger.error(
                "Erro ao inserir interação",
                extra={
                    'company_id': interaction_data.get('company_id'),
                    'error': str(e)
                },
                exc_info=True
            )
            raise DatabaseError("Falha ao inserir interação") from e

    # ========================================================================
    # API USAGE (Rate Limiting Persistente) ⭐ CRÍTICO
    # ========================================================================

    def count_api_usage_since(
        self,
        api_name: str,
        since_date: datetime
    ) -> int:
        """
        Conta usos de uma API desde data específica.

        ⭐ CRÍTICO - Rate limiting persistente que sobrevive a restarts.
        Use antes de TODA chamada de API paga para evitar estouro de créditos.

        Args:
            api_name: Nome da API (anthropic, apollo, snov, hunter, google_maps).
            since_date: Data de início (timezone-aware).

        Returns:
            Número de usos registrados desde a data.

        Raises:
            DatabaseError: Se houver erro na consulta.

        Example:
            >>> cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            >>> apollo_used = db.count_api_usage_since('apollo', cutoff)
            >>> if apollo_used < settings.APOLLO_MONTHLY_LIMIT:
            >>>     # OK para usar Apollo
            >>>     result = apollo_api.search()
        """
        try:
            result = self.client.table('api_usage')\
                .select('credits_used', count='exact')\
                .eq('api_name', api_name)\
                .gte('created_at', since_date.isoformat())\
                .execute()

            # Somar créditos usados
            total_credits = sum(row.get('credits_used', 1) for row in result.data)

            logger.debug(
                "API usage contado",
                extra={
                    'api_name': api_name,
                    'since_date': since_date.isoformat(),
                    'total_calls': len(result.data),
                    'total_credits': total_credits
                }
            )

            return total_credits

        except Exception as e:
            logger.error(
                "Erro ao contar uso de API",
                extra={
                    'api_name': api_name,
                    'since_date': since_date.isoformat(),
                    'error': str(e)
                },
                exc_info=True
            )
            raise DatabaseError(f"Falha ao contar uso da API {api_name}") from e

    def count_api_usage_this_month(self, api_name: str) -> int:
        """
        Conta usos de uma API no mês atual.

        Atalho para count_api_usage_since() com período de 30 dias.

        Args:
            api_name: Nome da API.

        Returns:
            Número de usos no mês atual.

        Example:
            >>> apollo_used_this_month = db.count_api_usage_this_month('apollo')
            >>> remaining = 60 - apollo_used_this_month
            >>> print(f"Apollo: {remaining} créditos restantes este mês")
        """
        cutoff = datetime.now() - timedelta(days=30)
        return self.count_api_usage_since(api_name, cutoff)

    def insert_api_usage(self, usage_data: Dict[str, Any]) -> Optional[str]:
        """
        Registra uso de API.

        ⚠️ ATENÇÃO: SEMPRE registre uso de API logo após a chamada.
        Isso permite rate limiting persistente.

        Args:
            usage_data: Dicionário com dados do uso.
                Campos obrigatórios: api_name
                Campos opcionais: endpoint, credits_used, success, status_code,
                                 response_time_ms, error_message, context

        Returns:
            UUID do registro (str) ou None se falhar.

        Raises:
            DatabaseError: Se houver erro na inserção.
            ValueError: Se faltar api_name.

        Example:
            >>> db.insert_api_usage({
            >>>     'api_name': 'apollo',
            >>>     'endpoint': '/people/search',
            >>>     'credits_used': 1,
            >>>     'success': True,
            >>>     'status_code': 200,
            >>>     'response_time_ms': 1234.5,
            >>>     'context': {'company_id': 'abc-123'}
            >>> })
        """
        if 'api_name' not in usage_data:
            raise ValueError("Campo obrigatório: api_name")

        # Defaults
        usage_data.setdefault('credits_used', 1)
        usage_data.setdefault('success', True)

        try:
            result = self.client.table('api_usage')\
                .insert(usage_data)\
                .execute()

            if result.data:
                usage_id = result.data[0]['id']
                logger.debug(
                    "Uso de API registrado",
                    extra={
                        'usage_id': usage_id,
                        'api_name': usage_data['api_name'],
                        'credits_used': usage_data.get('credits_used', 1)
                    }
                )
                return usage_id

            return None

        except Exception as e:
            logger.error(
                "Erro ao registrar uso de API",
                extra={
                    'api_name': usage_data.get('api_name'),
                    'error': str(e)
                },
                exc_info=True
            )
            # Não fazer raise aqui - registro de uso não deve quebrar o fluxo
            logger.warning("Continuando sem registrar uso de API")
            return None


    # ========================================================================
    # GESTAO DE ESCOLAS (Delete, Detail, Bulk)
    # ========================================================================

    def get_company_detail(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retorna empresa com todos os campos."""
        try:
            result = self.client.table('companies').select('*').eq('id', company_id).single().execute()
            return result.data
        except Exception as e:
            logger.error("Erro ao buscar detalhe da empresa", extra={"company_id": company_id, "error": str(e)})
            return None

    def get_queue_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        """Retorna itens da fila de aprovacao de uma empresa."""
        try:
            result = self.client.table('approval_queue').select('*').eq('company_id', company_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error("Erro ao buscar fila por empresa", extra={"company_id": company_id, "error": str(e)})
            return []

    def get_interactions_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        """Retorna interacoes/atividades de uma empresa."""
        try:
            result = self.client.table('interactions').select('*').eq('company_id', company_id).order('created_at', desc=True).execute()
            return result.data or []
        except Exception as e:
            logger.error("Erro ao buscar interacoes", extra={"company_id": company_id, "error": str(e)})
            return []

    def delete_company(self, company_id: str) -> bool:
        """Exclui empresa e todos os dados relacionados (contatos, fila, interacoes)."""
        try:
            self.client.table('interactions').delete().eq('company_id', company_id).execute()
            self.client.table('approval_queue').delete().eq('company_id', company_id).execute()
            self.client.table('contacts').delete().eq('company_id', company_id).execute()
            self.client.table('companies').delete().eq('id', company_id).execute()
            logger.info("Empresa excluida com dados relacionados", extra={"company_id": company_id})
            return True
        except Exception as e:
            logger.error("Erro ao excluir empresa", extra={"company_id": company_id, "error": str(e)})
            return False

    def delete_queue_items(self, company_id: str) -> int:
        """Exclui todos os itens da fila de uma empresa. Retorna qtd removida."""
        try:
            result = self.client.table('approval_queue').delete().eq('company_id', company_id).execute()
            count = len(result.data) if result.data else 0
            logger.info("Itens da fila excluidos", extra={"company_id": company_id, "count": count})
            return count
        except Exception as e:
            logger.error("Erro ao excluir fila", extra={"company_id": company_id, "error": str(e)})
            return 0

    def bulk_delete_companies(self, company_ids: List[str]) -> int:
        """Exclui multiplas empresas e dados relacionados. Retorna qtd removida."""
        deleted = 0
        for cid in company_ids:
            if self.delete_company(cid):
                deleted += 1
        return deleted

    def reset_company_status(self, company_id: str, new_status: str) -> bool:
        """Reseta status da empresa."""
        return self.update_company(company_id, {"status": new_status}) is not None

    # ========================================================================
    # LEAD OWNERSHIP + AUTORIA (Fase 2 da auditoria)
    # ========================================================================

    @staticmethod
    def _active_username() -> Optional[str]:
        """Resolve o username ativo (dashboard logado OU IAlex thread-local).
        None se nao houver (ex: cron). Import lazy evita ciclo de import."""
        try:
            from utils.sender_profile import get_active_sender_username
            return get_active_sender_username()
        except Exception:
            return None

    def claim_company_if_unowned(
        self, company_id: str, username: Optional[str] = None
    ) -> Optional[str]:
        """Auto-claim: se a escola NAO tem dono, define `username` como dono.

        Atomico (UPDATE ... WHERE owner_username IS NULL) — 2 users agindo ao
        mesmo tempo nao geram donos conflitantes; o primeiro vence. Idempotente:
        se ja tem dono, nao muda nada.

        Args:
            company_id: UUID da escola.
            username: quem reivindica. Se None, resolve o sender ativo.

        Returns:
            O username do dono atual (existente ou recem-atribuido), ou None.
        """
        if not company_id:
            return None
        user = username or self._active_username()
        if not user:
            return self.get_company_owner(company_id)  # sem user pra reivindicar
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            # CAS: so define dono se ainda nao houver
            self.client.table("companies").update(
                {"owner_username": user, "owner_assigned_at": now}
            ).eq("id", company_id).is_("owner_username", "null").execute()
            # Ler de volta o dono efetivo (pode ser outro se houve corrida)
            owner = self.get_company_owner(company_id)
            if owner == user:
                logger.info("Lead auto-atribuido", extra={"company_id": company_id, "owner": user})
            return owner
        except Exception as e:
            logger.warning("Falha no auto-claim de lead", extra={"company_id": company_id, "error": str(e)})
            return None

    def get_company_owner(self, company_id: str) -> Optional[str]:
        """Retorna o owner_username da escola (ou None se sem dono)."""
        if not company_id:
            return None
        try:
            r = (self.client.table("companies").select("owner_username")
                 .eq("id", company_id).single().execute())
            return (r.data or {}).get("owner_username")
        except Exception:
            return None

    def set_company_owner(self, company_id: str, username: Optional[str]) -> bool:
        """Define/reatribui/limpa o dono (uso ADMIN — correcao, nao claim).

        username=None limpa o dono (volta pro pool). Caso contrario reatribui.
        """
        if not company_id:
            return False
        try:
            from datetime import datetime, timezone
            if username:
                update = {
                    "owner_username": username,
                    "owner_assigned_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                update = {"owner_username": None, "owner_assigned_at": None}
            result = self.client.table("companies").update(update).eq("id", company_id).execute()
            ok = bool(result.data)
            if ok:
                logger.info("Owner do lead alterado (admin)",
                            extra={"company_id": company_id, "owner": username})
            return ok
        except Exception as e:
            logger.error("Erro ao definir owner", extra={"company_id": company_id, "error": str(e)})
            return False

    def delete_contact(self, contact_id: str) -> bool:
        """Exclui um contato individual."""
        try:
            self.client.table('contacts').delete().eq('id', contact_id).execute()
            logger.info("Contato excluido", extra={"contact_id": contact_id})
            return True
        except Exception as e:
            logger.error("Erro ao excluir contato", extra={"contact_id": contact_id, "error": str(e)})
            return False

    # ========================================================================
    # SUPABASE STORAGE — Upload de graficos para emails
    # ========================================================================

    _CHART_BUCKET = "insight-charts"
    _bucket_verified = False

    def _ensure_chart_bucket(self) -> None:
        """Cria o bucket de charts se nao existir (1x por sessao)."""
        if self._bucket_verified:
            return
        try:
            buckets = self.client.storage.list_buckets()
            exists = any(b.name == self._CHART_BUCKET for b in buckets)
            if not exists:
                self.client.storage.create_bucket(
                    self._CHART_BUCKET,
                    options={"public": True},
                )
                logger.info(f"Bucket '{self._CHART_BUCKET}' criado (publico)")
            self._bucket_verified = True
        except Exception as e:
            logger.warning(f"Erro verificando/criando bucket: {e}")
            self._bucket_verified = True  # nao travar em loop

    def upload_chart(self, path: str, png_bytes: bytes) -> Optional[str]:
        """Upload de PNG para Supabase Storage. Retorna URL publica.

        Args:
            path: Caminho relativo dentro do bucket. Ex: '43238203/radar_20260412.png'
            png_bytes: Conteudo do PNG em bytes.

        Returns:
            URL publica do arquivo, ou None se falhar.
        """
        self._ensure_chart_bucket()
        try:
            # Tentar upload (se ja existir, remove e re-faz)
            bucket = self.client.storage.from_(self._CHART_BUCKET)
            try:
                bucket.upload(
                    path,
                    png_bytes,
                    file_options={"content-type": "image/png", "upsert": "true"},
                )
            except Exception:
                # Fallback: remover e re-upload
                try:
                    bucket.remove([path])
                except Exception:
                    pass
                bucket.upload(
                    path,
                    png_bytes,
                    file_options={"content-type": "image/png"},
                )
            url = bucket.get_public_url(path)
            logger.info("Chart uploaded", extra={"path": path, "url": url[:80]})
            return url
        except Exception as e:
            logger.error(f"Erro upload chart: {e}", extra={"path": path})
            return None

    def upload_attachment(
        self,
        path: str,
        file_bytes: bytes,
        content_type: str = "application/pdf",
    ) -> Optional[str]:
        """Upload de arquivo arbitrario (PDF, etc) para Supabase Storage.

        Reusa o bucket `insight-charts` (publico) e segue o mesmo padrao de
        upload_chart/upload_report (delete+reupload em fallback).

        Args:
            path: Caminho relativo dentro do bucket. Ex: 'attachments/fernando/1234_proposta.pdf'
            file_bytes: Conteudo do arquivo em bytes.
            content_type: MIME type. Default 'application/pdf'.

        Returns:
            URL publica do arquivo, ou None se falhar.
        """
        self._ensure_chart_bucket()
        try:
            bucket = self.client.storage.from_(self._CHART_BUCKET)
            try:
                bucket.upload(
                    path,
                    file_bytes,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
            except Exception:
                try:
                    bucket.remove([path])
                except Exception:
                    pass
                bucket.upload(
                    path,
                    file_bytes,
                    file_options={"content-type": content_type},
                )
            url = bucket.get_public_url(path)
            logger.info("Attachment uploaded", extra={"path": path, "url": url[:80], "size": len(file_bytes)})
            return url
        except Exception as e:
            logger.error(f"Erro upload attachment: {e}", extra={"path": path})
            return None

    def remove_attachment(self, path: str) -> bool:
        """Remove arquivo do Supabase Storage. Retorna True se OK."""
        try:
            self.client.storage.from_(self._CHART_BUCKET).remove([path])
            return True
        except Exception as e:
            logger.error(f"Erro remove attachment: {e}", extra={"path": path})
            return False

    def upload_report(self, path: str, html_content: str) -> Optional[str]:
        """Upload de HTML report para Supabase Storage. Retorna URL publica.

        Args:
            path: Caminho relativo dentro do bucket. Ex: 'reports/43105114.html'
            html_content: Conteudo HTML como string.

        Returns:
            URL publica do arquivo, ou None se falhar.
        """
        self._ensure_chart_bucket()
        try:
            html_bytes = html_content.encode("utf-8")
            bucket = self.client.storage.from_(self._CHART_BUCKET)
            # Remover versao anterior se existir (upsert nem sempre funciona)
            try:
                bucket.remove([path])
            except Exception:
                pass
            # Upload com content-type explícito (ambos formatos para compatibilidade)
            bucket.upload(
                path,
                html_bytes,
                file_options={
                    "content-type": "text/html; charset=utf-8",
                    "contentType": "text/html; charset=utf-8",
                    "x-upsert": "true",
                },
            )
            url = bucket.get_public_url(path)
            logger.info("Report uploaded", extra={"path": path, "url": url[:80]})
            return url
        except Exception as e:
            logger.error(f"Erro upload report: {e}", extra={"path": path})
            return None


# ============================================================================
# SINGLETON - Instância única para todo o sistema (lazy initialization)
# ============================================================================
_db_instance: Optional[Database] = None


def get_db() -> Database:
    """
    Retorna instância singleton do Database (lazy initialization).

    Cria a conexão apenas na primeira chamada, evitando crash no import
    quando as credenciais ainda não estão configuradas.

    Returns:
        Instância do Database conectada ao Supabase.

    Example:
        >>> from database.supabase_client import get_db
        >>> db = get_db()
        >>> school = db.get_company_by_inep("43000001")
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance


class _LazyDB:
    """Proxy que inicializa Database apenas no primeiro acesso a um atributo."""

    def __getattr__(self, name: str) -> Any:
        return getattr(get_db(), name)


# Mantém compatibilidade: from database.supabase_client import db
db = _LazyDB()
