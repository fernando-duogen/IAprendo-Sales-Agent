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
from datetime import datetime, timedelta, timezone
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

    # ------------------------------------------------------------------
    # CATALOGO MEC ONLINE (tabela leve mec_catalog) — busca/import sem CSV
    # ------------------------------------------------------------------
    def catalog_available(self) -> bool:
        """True se a tabela mec_catalog existe E tem linhas (base carregada).

        Usa checagem de EXISTENCIA (1 linha), NAO count exato: contar 185k linhas
        estoura o statement_timeout no Cloud, o que fazia retornar False mesmo com
        a base carregada (sintoma "catalogo nao carregado" no Importar online).
        """
        try:
            r = self.client.table('mec_catalog').select('inep_code').limit(1).execute()
            return bool(r.data)
        except Exception:
            return False

    # Colunas numericas pelas quais o catalogo pode ser ordenado (ranking).
    _CATALOG_SORTABLE = {
        "total_matriculas", "matriculas_medio", "matriculas_fund_af",
        "total_docentes", "qt_coordenadores",
    }

    def search_mec_catalog(
        self,
        filters: Dict[str, Any],
        limit: int = 200,
        order_by: Optional[str] = None,
        desc: bool = True,
    ) -> Dict[str, Any]:
        """Busca escolas no catalogo MEC (Supabase) via SQL com filtros.

        Funciona ONLINE sem o CSV. Filtros suportados (todos opcionais):
            nome, cidade, uf, dependencia, tipo, niveis_ensino, porte,
            localizacao (strings; nome/cidade/niveis usam forma normalizada).

        Args:
            filters: dicionario de filtros (chaves acima).
            limit: maximo de linhas retornadas (cap 1000).

        Returns:
            {'rows': [...], 'total': int, 'limit': int} — total e a contagem
            real no banco (pode ser > len(rows) se truncado pelo limit).
        """
        import unicodedata

        def _norm(s: str) -> str:
            return (unicodedata.normalize('NFKD', str(s)).encode('ASCII', 'ignore')
                    .decode('ASCII').lower().strip())

        limit = max(1, min(int(limit or 200), 1000))
        try:
            # count='estimated' (nao 'exact'): em buscas amplas (ex: so UF) o filtro
            # pode bater dezenas de milhares de linhas e o COUNT exato estoura o
            # statement_timeout no Cloud. O total e so informativo ("~N resultados").
            q = self.client.table('mec_catalog').select('*', count='estimated')
            if filters.get('nome'):
                for w in [p for p in _norm(filters['nome']).split() if len(p) >= 2]:
                    q = q.ilike('name_norm', f'%{w}%')
            if filters.get('cidade'):
                q = q.ilike('city_norm', f'%{_norm(filters["cidade"])}%')
            if filters.get('uf'):
                q = q.eq('state', str(filters['uf']).upper()[:2])
            if filters.get('dependencia'):
                q = q.ilike('admin_dependency', f'%{filters["dependencia"]}%')
            if filters.get('tipo'):
                q = q.ilike('admin_category', f'%{filters["tipo"]}%')
            if filters.get('niveis_ensino'):
                q = q.ilike('levels_norm', f'%{_norm(filters["niveis_ensino"])}%')
            if filters.get('porte'):
                q = q.ilike('school_size', f'%{filters["porte"]}%')
            if filters.get('localizacao'):
                q = q.ilike('localizacao', f'%{filters["localizacao"]}%')
            # Ordenacao opcional (ranking/superlativo: "maior escola", "top N").
            # Exclui NULLs na coluna ordenada pra o topo do ranking ser real.
            if order_by in self._CATALOG_SORTABLE:
                q = q.not_.is_(order_by, "null").order(order_by, desc=bool(desc))
            res = q.limit(limit).execute()
            rows = res.data or []
            total = res.count if getattr(res, 'count', None) is not None else len(rows)
            return {'rows': rows, 'total': total, 'limit': limit}
        except Exception as e:
            logger.warning("Falha na busca do catalogo MEC", extra={'error': str(e)})
            return {'rows': [], 'total': 0, 'limit': limit, 'error': str(e)[:200]}

    @staticmethod
    def _catalog_row_to_company(row: Dict[str, Any]) -> Dict[str, Any]:
        """Converte uma linha do mec_catalog em company_data pronto pra insert."""
        inep_code = str(row.get('inep_code') or '').strip()
        data = {
            'name': row.get('name'), 'inep_code': inep_code,
            'city': row.get('city'), 'state': row.get('state'),
            'address': row.get('address'), 'phone': row.get('phone'),
            'latitude': row.get('latitude'), 'longitude': row.get('longitude'),
            'admin_category': row.get('admin_category'),
            'admin_dependency': row.get('admin_dependency'),
            'categoria_privada': row.get('categoria_privada'),
            'education_levels': row.get('education_levels'),
            'school_size': row.get('school_size'),
            'fonte_dados': row.get('fonte_dados'),
            'total_matriculas': row.get('total_matriculas'),
            'matriculas_fund_af': row.get('matriculas_fund_af'),
            'matriculas_medio': row.get('matriculas_medio'),
            'total_docentes': row.get('total_docentes'),
            'qt_coordenadores': row.get('qt_coordenadores'),
            'nivel_tecnologico': row.get('nivel_tecnologico'),
            'status': 'raw',
        }
        return {k: v for k, v in data.items() if v is not None}

    def import_company_from_catalog(
        self,
        inep_code: str,
        source: str = 'catalogo_online'
    ) -> Dict[str, Any]:
        """Importa 1 escola do catalogo MEC pro CRM (sem depender do CSV).

        Returns: {'ok': bool, 'id': str|None, 'inep': str, 'already': bool,
                  'name': str|None, 'message': str}
        """
        inep_code = str(inep_code or '').strip()
        if not inep_code:
            return {'ok': False, 'id': None, 'inep': inep_code, 'already': False,
                    'name': None, 'message': 'INEP vazio.'}
        try:
            existing = self.get_company_by_inep(inep_code)
            if existing:
                return {'ok': True, 'id': existing['id'], 'inep': inep_code,
                        'already': True, 'name': existing.get('name'),
                        'message': 'Ja estava no CRM.'}
            r = self.client.table('mec_catalog').select('*').eq(
                'inep_code', inep_code).limit(1).execute()
            row = (r.data or [None])[0]
            if not row:
                return {'ok': False, 'id': None, 'inep': inep_code, 'already': False,
                        'name': None, 'message': 'Nao encontrada no catalogo.'}
            company_data = self._catalog_row_to_company(row)
            company_data['source'] = source
            company_id = self.insert_company(company_data)
            return {'ok': bool(company_id), 'id': company_id, 'inep': inep_code,
                    'already': False, 'name': company_data.get('name'),
                    'message': 'Importada.' if company_id else 'Falha ao inserir.'}
        except Exception as e:
            logger.error("Erro ao importar do catalogo", extra={'inep': inep_code, 'error': str(e)})
            return {'ok': False, 'id': None, 'inep': inep_code, 'already': False,
                    'name': None, 'message': f'Erro: {str(e)[:150]}'}

    # ------------------------------------------------------------------
    # CATALOGO MEC — queries com filtros-LISTA (paridade com a UI local do
    # Importar/Mapa, que usa multiselects). filters = {
    #   ufs:[], cities:[], deps:[], portes:[], inc_fund:bool, inc_medio:bool }
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_catalog_filters(q, filters: Optional[Dict[str, Any]]):
        """Aplica os filtros-lista numa query do mec_catalog (espelha a UI local)."""
        f = filters or {}
        ufs = f.get("ufs") or []
        cities = f.get("cities") or []
        deps = f.get("deps") or []
        portes = f.get("portes") or []
        if ufs:
            q = q.in_("state", [str(u).upper()[:2] for u in ufs])
        if cities:
            q = q.in_("city", list(cities))
        if deps:
            q = q.in_("admin_dependency", list(deps))
        if portes:
            q = q.in_("school_size", list(portes))
        inc_fund = bool(f.get("inc_fund"))
        inc_medio = bool(f.get("inc_medio"))
        if inc_fund and inc_medio:
            q = q.or_("levels_norm.ilike.%fundamental%,levels_norm.ilike.%medio%")
        elif inc_fund:
            q = q.ilike("levels_norm", "%fundamental%")
        elif inc_medio:
            q = q.ilike("levels_norm", "%medio%")
        return q

    def count_mec_catalog(self, filters: Optional[Dict[str, Any]]) -> int:
        """Conta escolas do catalogo que casam os filtros. count='exact' quando
        ha filtro geografico (subconjunto pequeno, preciso); 'estimated' quando
        amplo (so niveis), pra nao estourar o statement_timeout no Cloud."""
        try:
            f = filters or {}
            narrow = any(f.get(k) for k in ("ufs", "cities", "deps", "portes"))
            mode = "exact" if narrow else "estimated"
            q = self.client.table("mec_catalog").select("inep_code", count=mode)
            q = self._apply_catalog_filters(q, f)
            r = q.limit(1).execute()
            return int(r.count or 0)
        except Exception as e:
            logger.warning("count_mec_catalog falhou", extra={"error": str(e)})
            return 0

    def query_mec_catalog(self, filters: Optional[Dict[str, Any]],
                          limit: int = 15, columns: str = "*") -> list:
        """Linhas do catalogo que casam os filtros (preview / pontos do mapa / import)."""
        try:
            q = self.client.table("mec_catalog").select(columns)
            q = self._apply_catalog_filters(q, filters)
            return q.limit(max(1, int(limit))).execute().data or []
        except Exception as e:
            logger.warning("query_mec_catalog falhou", extra={"error": str(e)})
            return []

    def catalog_cities(self, ufs: Optional[list]) -> list:
        """Distinct de cidades das UFs dadas (cascata) — via RPC mec_catalog_cities.
        Requer a migration add_mec_facet_rpcs.sql; sem ela, retorna [] (a UI cai
        num fallback)."""
        try:
            states = [str(u).upper()[:2] for u in (ufs or [])]
            r = self.client.rpc("mec_catalog_cities", {"p_states": states}).execute()
            out = []
            for row in (r.data or []):
                out.append(row.get("city") if isinstance(row, dict) else row)
            return [c for c in out if c]
        except Exception as e:
            logger.warning("catalog_cities RPC indisponivel", extra={"error": str(e)})
            return []

    def catalog_facets(self) -> Dict[str, list]:
        """Distinct de states/deps/portes. Tenta a RPC mec_catalog_facets; se nao
        existir, faz fallback por amostra (deps/portes sao poucos distintos)."""
        try:
            r = self.client.rpc("mec_catalog_facets").execute()
            d = r.data or {}
            if d and (d.get("states") or d.get("dependencias")):
                return {
                    "states": d.get("states") or [],
                    "deps": d.get("dependencias") or [],
                    "portes": d.get("portes") or [],
                }
        except Exception:
            pass
        deps, portes = set(), set()
        try:
            sample = (self.client.table("mec_catalog")
                      .select("admin_dependency,school_size").limit(3000).execute().data or [])
            for s in sample:
                if s.get("admin_dependency"):
                    deps.add(s["admin_dependency"])
                if s.get("school_size"):
                    portes.add(s["school_size"])
        except Exception as e:
            logger.warning("catalog_facets fallback falhou", extra={"error": str(e)})
        return {"states": [], "deps": sorted(deps), "portes": sorted(portes)}

    def import_mec_filtered(self, filters: Optional[Dict[str, Any]], limit: int = 0,
                            source: str = "dashboard_online") -> Dict[str, Any]:
        """Importa pro CRM TODAS as escolas do catalogo que casam os filtros (ate
        `limit`; 0 = teto de seguranca). Pre-checa INEP existente (idempotente) e
        insere em lote. Espelha o 'Confirmar e Importar' do modo local."""
        CAP = 5000  # teto por clique (evita inserir 185k de uma vez)
        eff = CAP if (not limit or int(limit) <= 0) else min(int(limit), CAP)
        try:
            rows = self.query_mec_catalog(filters, limit=eff, columns="*")
            if not rows:
                return {"inseridas": 0, "duplicatas": 0, "no_match": True, "ok": True}
            ineps = [str(r.get("inep_code")).strip() for r in rows if r.get("inep_code")]
            existing = set()
            for i in range(0, len(ineps), 200):
                chunk = ineps[i:i + 200]
                ex = (self.client.table("companies").select("inep_code")
                      .in_("inep_code", chunk).execute().data or [])
                existing.update(str(e.get("inep_code")).strip() for e in ex)
            novos = [r for r in rows if str(r.get("inep_code")).strip() not in existing]
            inseridas = 0
            for i in range(0, len(novos), 100):
                batch = []
                for r in novos[i:i + 100]:
                    cd = self._catalog_row_to_company(r)
                    cd["source"] = source
                    batch.append(cd)
                if not batch:
                    continue
                try:
                    res = self.client.table("companies").insert(batch).execute()
                    inseridas += len(res.data or [])
                except Exception as e_batch:
                    logger.warning("import_mec_filtered: lote falhou",
                                   extra={"error": str(e_batch)[:150]})
            return {
                "inseridas": inseridas,
                "duplicatas": len(existing),
                "ok": True,
                "capped": (not limit or int(limit) <= 0) and len(rows) >= CAP,
            }
        except Exception as e:
            logger.error("import_mec_filtered falhou", extra={"error": str(e)})
            return {"inseridas": 0, "duplicatas": 0, "ok": False, "error": str(e)[:200]}

    def fetch_in_chunks(self, table: str, columns: str, column: str,
                        values: List[Any], *, chunk: int = 150,
                        order_by: Optional[str] = None,
                        order_desc: bool = False) -> List[Dict[str, Any]]:
        """SELECT `columns` FROM `table` WHERE `column` IN (`values`), com a lista
        quebrada em lotes de `chunk`.

        Por que: uma lista grande de INEPs num unico .in_() estoura o tamanho da
        URL do PostgREST (erro 400 do Cloudflare) quando a base de leads cresce
        (centenas/milhares). Cada item cai em EXATAMENTE um lote, entao um
        `order_by` por-lote preserva a ordenacao por-item (ex.: pegar o registro
        mais recente por INEP). Retorna a concatenacao dos r.data — mesma forma
        de um `.execute().data` unico. Falha de um lote nao derruba os demais.
        """
        out: List[Dict[str, Any]] = []
        vals = [v for v in (values or []) if v not in (None, "")]
        for i in range(0, len(vals), max(1, chunk)):
            part = vals[i:i + chunk]
            try:
                q = self.client.table(table).select(columns).in_(column, part)
                if order_by:
                    q = q.order(order_by, desc=bool(order_desc))
                out.extend(q.execute().data or [])
            except Exception as e:
                logger.warning("fetch_in_chunks: lote falhou",
                               extra={"table": table, "error": str(e)[:150]})
        return out

    # =========================================================================
    # AGENDA (activities) — F1 do redesign v2 · regras: docs/SPEC_AGENDA_METAS.md
    # =========================================================================

    def create_activity(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Cria atividade. Se dedupe_key ja existe (unique violation), retorna
        None silenciosamente — e o contrato de idempotencia do engine (SPEC §1.3)."""
        try:
            if not data.get('owner_username') or not data.get('title') or not data.get('due_at'):
                raise ValueError("Campos obrigatorios: owner_username, title, due_at")
            res = self.client.table('activities').insert(data).execute()
            return (res.data or [None])[0]
        except Exception as e:
            msg = str(e)
            if '23505' in msg or 'duplicate' in msg.lower() or 'idx_activities_dedupe' in msg:
                return None  # dedupe hit — comportamento esperado
            logger.error("Erro ao criar atividade", extra={'error': msg[:200]})
            return None

    def list_activities(self, owner: Optional[str] = None, status: Optional[Any] = None,
                        company_id: Optional[str] = None, due_before: Optional[str] = None,
                        auto_only: bool = False, limit: int = 300) -> List[Dict[str, Any]]:
        """Lista atividades (ordem da agenda: prioridade, due, criacao — SPEC §1.8)."""
        try:
            q = self.client.table('activities').select('*')
            if owner:
                q = q.eq('owner_username', owner)
            if status:
                q = q.in_('status', status if isinstance(status, list) else [status])
            if company_id:
                q = q.eq('company_id', company_id)
            if due_before:
                q = q.lte('due_at', due_before)
            if auto_only:
                q = q.eq('source', 'auto')
            r = q.order('priority').order('due_at').order('created_at').limit(limit).execute()
            return r.data or []
        except Exception as e:
            logger.error("Erro ao listar atividades", extra={'error': str(e)[:200]})
            return []

    def complete_activity(self, activity_id: str, by: str,
                          resolution: str = 'manual') -> bool:
        """Conclui (done). `by='system'` + resolution distinguem auto-resolucao."""
        try:
            self.client.table('activities').update({
                'status': 'done',
                'resolution': resolution,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'completed_by': by,
            }).eq('id', activity_id).in_('status', ['open', 'snoozed']).execute()
            return True
        except Exception as e:
            logger.error("Erro ao concluir atividade", extra={'id': activity_id, 'error': str(e)[:200]})
            return False

    def dismiss_activity(self, activity_id: str, by: str, resolution: str) -> bool:
        """Dispensa (dismissed) com resolution obrigatoria (auditoria — SPEC §1.1)."""
        try:
            self.client.table('activities').update({
                'status': 'dismissed',
                'resolution': resolution,
                'completed_at': datetime.now(timezone.utc).isoformat(),
                'completed_by': by,
            }).eq('id', activity_id).in_('status', ['open', 'snoozed']).execute()
            return True
        except Exception as e:
            logger.error("Erro ao dispensar atividade", extra={'id': activity_id, 'error': str(e)[:200]})
            return False

    def snooze_activity(self, activity_id: str, until: str) -> Dict[str, Any]:
        """Adia (snoozed). Limite de 3 adiamentos (SPEC §1.5) — no 4o, retorna
        erro orientando a dispensar com motivo."""
        try:
            r = self.client.table('activities').select('snooze_count,status') \
                .eq('id', activity_id).limit(1).execute()
            row = (r.data or [None])[0]
            if not row:
                return {'ok': False, 'erro': 'atividade nao encontrada'}
            if row.get('status') not in ('open', 'snoozed'):
                return {'ok': False, 'erro': 'atividade ja resolvida'}
            count = int(row.get('snooze_count') or 0)
            if count >= 3:
                return {'ok': False, 'erro': 'limite de 3 adiamentos atingido — conclua ou dispense com motivo'}
            self.client.table('activities').update({
                'status': 'snoozed',
                'snoozed_until': until,
                'snooze_count': count + 1,
            }).eq('id', activity_id).execute()
            return {'ok': True, 'snooze_count': count + 1}
        except Exception as e:
            logger.error("Erro ao adiar atividade", extra={'id': activity_id, 'error': str(e)[:200]})
            return {'ok': False, 'erro': str(e)[:150]}

    def reassign_company_activities(self, company_id: str, new_owner: str,
                                    note: str = '') -> int:
        """Transfere as atividades ABERTAS da escola junto com o lead (SPEC §5.1)."""
        try:
            r = self.client.table('activities').select('id,details') \
                .eq('company_id', company_id).in_('status', ['open', 'snoozed']).execute()
            rows = r.data or []
            for row in rows:
                details = (row.get('details') or '')
                if note:
                    details = (details + f"\n[{note}]").strip()
                self.client.table('activities').update({
                    'owner_username': new_owner, 'details': details,
                }).eq('id', row['id']).execute()
            return len(rows)
        except Exception as e:
            logger.error("Erro ao reatribuir atividades", extra={'company_id': company_id, 'error': str(e)[:200]})
            return 0

    def count_open_activities(self, owner: str, auto_only: bool = False,
                              min_priority: Optional[int] = None) -> int:
        """Conta abertas do dono (teto anti-spam do engine — SPEC §1.7)."""
        try:
            q = self.client.table('activities').select('id', count='exact') \
                .eq('owner_username', owner).eq('status', 'open')
            if auto_only:
                q = q.eq('source', 'auto')
            if min_priority is not None:
                q = q.gte('priority', min_priority)
            r = q.execute()
            return int(r.count or 0)
        except Exception as e:
            logger.error("Erro ao contar atividades", extra={'error': str(e)[:200]})
            return 0

    # =========================================================================
    # METAS (goals) — SPEC §4
    # =========================================================================

    def upsert_goal(self, username: str, metric: str, period_start: str,
                    target: float, by: str, reason: Optional[str] = None,
                    period_type: str = 'month') -> Optional[Dict[str, Any]]:
        """Cria/atualiza meta com trilha em revision_log (mudanca nunca e
        silenciosa — SPEC §4.1). reason='herdada' marca o rollover automatico."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            r = self.client.table('goals').select('*') \
                .eq('username', username).eq('metric', metric) \
                .eq('period_type', period_type).eq('period_start', period_start) \
                .limit(1).execute()
            existing = (r.data or [None])[0]
            if existing:
                log = list(existing.get('revision_log') or [])
                log.append({'at': now, 'by': by,
                            'old_target': float(existing.get('target') or 0),
                            'new_target': float(target),
                            'reason': reason or ''})
                res = self.client.table('goals').update({
                    'target': target, 'revision_log': log,
                }).eq('id', existing['id']).execute()
                return (res.data or [None])[0]
            res = self.client.table('goals').insert({
                'username': username, 'metric': metric,
                'period_type': period_type, 'period_start': period_start,
                'target': target, 'created_by': by,
                'revision_log': [{'at': now, 'by': by, 'new_target': float(target),
                                  'reason': reason or 'criada'}],
            }).execute()
            return (res.data or [None])[0]
        except Exception as e:
            logger.error("Erro no upsert de meta", extra={'username': username, 'metric': metric,
                                                          'error': str(e)[:200]})
            return None

    def list_goals(self, period_start: Optional[str] = None,
                   username: Optional[str] = None,
                   period_type: str = 'month') -> List[Dict[str, Any]]:
        try:
            q = self.client.table('goals').select('*').eq('period_type', period_type)
            if period_start:
                q = q.eq('period_start', period_start)
            if username:
                q = q.eq('username', username)
            return q.order('username').order('metric').execute().data or []
        except Exception as e:
            logger.error("Erro ao listar metas", extra={'error': str(e)[:200]})
            return []

    def _owner_company_ids(self, username: str) -> List[str]:
        try:
            r = self.client.table('companies').select('id') \
                .eq('owner_username', username).limit(5000).execute()
            return [row['id'] for row in (r.data or [])]
        except Exception:
            return []

    def goal_realized(self, username: str, metric: str,
                      period_start: str, period_end: str) -> float:
        """Realizado AO VIVO de eventos timestamped imutaveis (SPEC §4.3).
        username='team' = sem filtro de vendedor. Fontes por metrica:
        interactions (e-mails/respostas), meetings (reunioes), eventos
        stage_changed do trigger (propostas/clientes/valor), activities (done)."""
        try:
            team = (username == 'team')

            def _count_interactions(types: List[str]) -> float:
                q = self.client.table('interactions').select('id', count='exact') \
                    .in_('type', types) \
                    .gte('created_at', period_start).lt('created_at', period_end)
                if not team:
                    ids = self._owner_company_ids(username)
                    if not ids:
                        return 0.0
                    q = q.in_('company_id', ids[:200])
                return float(q.execute().count or 0)

            if metric == 'emails_enviados':
                return _count_interactions(['email_sent'])
            if metric == 'respostas':
                return _count_interactions(['email_replied', 'whatsapp_replied'])

            if metric == 'reunioes_realizadas':
                q = self.client.table('meetings').select('id', count='exact') \
                    .eq('status', 'completed') \
                    .gte('scheduled_at', period_start).lt('scheduled_at', period_end)
                if not team:
                    q = q.eq('owner_username', username)
                return float(q.execute().count or 0)

            if metric in ('propostas', 'clientes', 'valor_fechado'):
                to_stage = 'proposta' if metric == 'propostas' else 'cliente'
                q = self.client.table('interactions').select('metadata') \
                    .eq('type', 'stage_changed') \
                    .eq('metadata->>to_stage', to_stage) \
                    .gte('created_at', period_start).lt('created_at', period_end) \
                    .limit(2000)
                if not team:
                    q = q.eq('metadata->>owner_username', username)
                rows = q.execute().data or []
                if metric == 'valor_fechado':
                    total = 0.0
                    for row in rows:
                        try:
                            total += float((row.get('metadata') or {}).get('valor_mensal_fechado') or 0)
                        except (TypeError, ValueError):
                            pass
                    return total
                return float(len(rows))

            if metric == 'atividades_concluidas':
                q = self.client.table('activities').select('id', count='exact') \
                    .eq('status', 'done') \
                    .in_('resolution', ['manual', 'auto_trabalho_detectado']) \
                    .gte('completed_at', period_start).lt('completed_at', period_end)
                if not team:
                    q = q.eq('owner_username', username)
                return float(q.execute().count or 0)

            return 0.0
        except Exception as e:
            logger.error("Erro no realizado da meta", extra={'metric': metric, 'error': str(e)[:200]})
            return 0.0

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

        # DEDUP (app-level): evita criar contato duplicado na MESMA escola.
        # Chave: email (se houver) OU nome normalizado. Se ja existe, atualiza
        # campos vazios e retorna o id existente (em vez de duplicar).
        try:
            _cid = contact_data['company_id']
            _email = (contact_data.get('email') or '').strip().lower()
            _name = (contact_data.get('full_name') or '').strip().lower()
            _existing = self.client.table('contacts').select(
                'id,full_name,email,phone,phone_whatsapp,linkedin_url'
            ).eq('company_id', _cid).execute().data or []
            _match = None
            for _c in _existing:
                _ce = (_c.get('email') or '').strip().lower()
                _cn = (_c.get('full_name') or '').strip().lower()
                if (_email and _ce == _email) or (not _email and _cn and _cn == _name):
                    _match = _c
                    break
            if _match:
                # Preencher campos vazios do existente com os novos (merge leve)
                _fill = {}
                for _f in ('email', 'phone', 'phone_whatsapp', 'linkedin_url', 'role'):
                    if contact_data.get(_f) and not _match.get(_f):
                        _fill[_f] = contact_data[_f]
                if _fill:
                    try:
                        self.client.table('contacts').update(_fill).eq('id', _match['id']).execute()
                    except Exception:
                        pass
                logger.info("Contato duplicado evitado (merge no existente)",
                            extra={'company_id': _cid, 'contact_id': _match['id']})
                return _match['id']
        except Exception as _e_dedup:
            logger.debug(f"dedup contato skip: {_e_dedup}")

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

    def set_commercial_stage(
        self,
        company_id: str,
        stage: str,
        extra: Optional[Dict[str, Any]] = None,
        advance_status: bool = True,
    ) -> Dict[str, Any]:
        """Seta companies.commercial_stage E avanca o status tecnico junto
        (advance-only) numa unica escrita — mantendo os 2 modelos coerentes.

        Usado pelas tools comerciais do IAlex (proposta/cliente/perdido) e por
        qualquer fluxo que mova o estagio comercial. Sem isto, gravar so o
        commercial_stage deixa o status defasado (ex: cliente aparecendo como
        'contacted' em Escolas/Analytics/HubSpot).

        Args:
            company_id: UUID da escola.
            stage: novo commercial_stage (prospectado..cliente/perdido).
            extra: campos adicionais a gravar junto (ex: valor_mensal_fechado,
                data_fechamento, motivo_perda_texto).
            advance_status: se True (padrao), avanca companies.status pro minimo
                coerente com o stage (nunca regride).

        Returns:
            Dict com os campos efetivamente atualizados (inclui 'status' se mudou).
        """
        from utils.stage_sync import coherent_status_for_stage

        updates: Dict[str, Any] = dict(extra or {})
        updates["commercial_stage"] = stage

        if advance_status:
            try:
                cur = (
                    self.client.table("companies")
                    .select("status")
                    .eq("id", company_id)
                    .single()
                    .execute()
                )
                cur_status = (cur.data or {}).get("status")
                new_status = coherent_status_for_stage(cur_status, stage)
                if new_status:
                    updates["status"] = new_status
            except Exception as e:
                logger.warning(
                    "set_commercial_stage: falha ao resolver status coerente",
                    extra={"company_id": company_id, "error": str(e)},
                )

        self.update_company(company_id, updates)
        logger.info(
            "commercial_stage atualizado",
            extra={
                "company_id": company_id,
                "stage": stage,
                "status_sincronizado": updates.get("status"),
            },
        )
        return updates

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

    def find_similar_company(
        self, name: str, city: str = "", state: str = ""
    ) -> List[Dict[str, Any]]:
        """Busca escolas com nome parecido na mesma cidade/UF (dedup de cadastro manual).

        Usado pra AVISAR antes de criar uma escola manualmente que pode ja existir.
        Match por nome (contains, case-insensitive) + cidade/UF se informados.
        """
        if not name or len(name.strip()) < 4:
            return []
        try:
            q = self.client.table("companies").select(
                "id,name,city,state,inep_code,status,owner_username"
            ).ilike("name", f"%{name.strip()}%")
            if city:
                q = q.ilike("city", f"%{city.strip()}%")
            if state:
                q = q.eq("state", state.strip().upper())
            return q.limit(10).execute().data or []
        except Exception as e:
            logger.debug(f"find_similar_company falhou: {e}")
            return []

    def count_companies_by_owner(self) -> Dict[str, int]:
        """Conta escolas por dono (owner_username). Chave '(sem dono)' agrega os nulos.
        Usado nas metricas por vendedor (Analytics)."""
        try:
            rows = self.client.table("companies").select("owner_username").execute().data or []
        except Exception as e:
            logger.debug(f"count_companies_by_owner falhou: {e}")
            return {}
        counts: Dict[str, int] = {}
        for r in rows:
            k = r.get("owner_username") or "(sem dono)"
            counts[k] = counts.get(k, 0) + 1
        return counts

    def get_stale_owned_leads(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """Leads COM dono parados ha >= `days` dias (last_contacted_at antigo ou nulo)
        e ainda nao convertidos/perdidos. Para alertas de SLA."""
        try:
            from datetime import datetime, timezone, timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            rows = (self.client.table("companies")
                    .select("id,name,city,state,owner_username,last_contacted_at,status,commercial_stage")
                    .not_.is_("owner_username", "null")
                    .execute().data or [])
            stale = []
            for r in rows:
                stage = (r.get("commercial_stage") or "").lower()
                if stage in ("cliente", "perdido"):
                    continue
                lc = r.get("last_contacted_at")
                if (lc is None) or (str(lc) < cutoff):
                    stale.append(r)
            stale.sort(key=lambda x: (x.get("last_contacted_at") or ""))
            return stale[:limit]
        except Exception as e:
            logger.debug(f"get_stale_owned_leads falhou: {e}")
            return []

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
