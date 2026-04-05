"""
Memory - Memoria persistente do IAlex entre sessoes.

Guarda fatos, preferencias, insights e avisos sobre escolas, contatos e o negocio.
Suporta 3 escopos:
- global: sobre Fernando, o negocio, preferencias gerais
- company: sobre uma escola especifica (scope_id = company.id)
- contact: sobre um contato especifico (scope_id = contact.id)

Categorias:
- fact: fato objetivo ("Escola tem 1200 alunos")
- preference: preferencia do contato ("Prefere WhatsApp")
- insight: insight comercial ("Reagiu bem a case de BNCC")
- warning: alerta ("Diretor esta de licenca ate agosto")
- reminder: lembrete ("Retornar em setembro")

Usage:
    from integrations.memory import memory

    # Gravar fato
    memory.remember("fact", "company", company_id, "Escola tem 1200 alunos", importance=7)

    # Buscar memorias de uma escola
    mems = memory.get_for("company", company_id, limit=10)

    # Buscar memorias globais
    globals_ = memory.get_for("global")

    # Buscar por texto
    results = memory.search("whatsapp", limit=5)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from database.supabase_client import db
from utils.logger import logger


class Memory:
    """Memoria persistente do IAlex."""

    TABLE = "conversation_memory"

    def is_available(self) -> bool:
        """Verifica se a tabela existe no banco."""
        try:
            db.client.table(self.TABLE).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def remember(
        self,
        content: str,
        scope: str = "global",
        scope_id: Optional[str] = None,
        category: str = "fact",
        importance: int = 5,
        source: str = "ialex",
        expires_at: Optional[str] = None,
    ) -> Optional[str]:
        """Grava uma memoria. Retorna o id ou None se falhou."""
        if not self.is_available():
            return None
        if scope not in ("global", "company", "contact"):
            scope = "global"
        if category not in ("fact", "preference", "insight", "warning", "reminder"):
            category = "fact"
        importance = max(1, min(10, int(importance or 5)))

        data = {
            "scope": scope,
            "scope_id": scope_id if scope != "global" else None,
            "category": category,
            "content": content.strip()[:2000],
            "importance": importance,
            "source": source,
        }
        if expires_at:
            data["expires_at"] = expires_at
        try:
            result = db.client.table(self.TABLE).insert(data).execute()
            if result.data:
                mem_id = result.data[0]["id"]
                logger.info("Memoria gravada", extra={"id": mem_id, "scope": scope, "category": category})
                return mem_id
        except Exception as e:
            logger.error(f"Erro ao gravar memoria: {e}")
        return None

    def get_for(
        self,
        scope: str,
        scope_id: Optional[str] = None,
        limit: int = 20,
        include_global: bool = False,
    ) -> List[Dict[str, Any]]:
        """Busca memorias para um escopo especifico.
        Se include_global=True, tambem inclui memorias globais.
        Ordena por importance DESC, created_at DESC.
        """
        if not self.is_available():
            return []
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            results = []
            # Query do escopo especifico
            q = db.client.table(self.TABLE).select("*").eq("scope", scope)
            if scope_id and scope != "global":
                q = q.eq("scope_id", scope_id)
            q = q.order("importance", desc=True).order("created_at", desc=True).limit(limit)
            r = q.execute()
            results.extend(r.data or [])
            # Filtrar expiradas
            results = [m for m in results if not m.get("expires_at") or m["expires_at"] > now_iso]

            # Incluir globais se pedido
            if include_global and scope != "global":
                g = db.client.table(self.TABLE).select("*").eq("scope", "global").order("importance", desc=True).limit(10).execute()
                for m in (g.data or []):
                    if not m.get("expires_at") or m["expires_at"] > now_iso:
                        results.append(m)

            return results
        except Exception as e:
            logger.error(f"Erro ao buscar memorias: {e}")
            return []

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Busca memorias por conteudo (ilike)."""
        if not self.is_available() or not query:
            return []
        try:
            r = db.client.table(self.TABLE).select("*").ilike("content", f"%{query}%").order("importance", desc=True).limit(limit).execute()
            return r.data or []
        except Exception as e:
            logger.error(f"Erro ao buscar memorias por texto: {e}")
            return []

    def forget(self, memory_id: str) -> bool:
        """Remove uma memoria especifica."""
        if not self.is_available():
            return False
        try:
            db.client.table(self.TABLE).delete().eq("id", memory_id).execute()
            logger.info("Memoria removida", extra={"id": memory_id})
            return True
        except Exception as e:
            logger.error(f"Erro ao remover memoria: {e}")
            return False

    def mark_used(self, memory_id: str) -> None:
        """Marca uma memoria como usada (incrementa contador)."""
        if not self.is_available():
            return
        try:
            # Buscar use_count atual
            r = db.client.table(self.TABLE).select("use_count").eq("id", memory_id).limit(1).execute()
            current = (r.data[0].get("use_count", 0) if r.data else 0) + 1
            db.client.table(self.TABLE).update({
                "use_count": current,
                "last_used_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", memory_id).execute()
        except Exception:
            pass

    def format_for_context(self, memories: List[Dict[str, Any]]) -> str:
        """Formata uma lista de memorias como texto para injetar no system prompt."""
        if not memories:
            return ""
        lines = []
        icon_by_cat = {
            "fact": "📌",
            "preference": "⭐",
            "insight": "💡",
            "warning": "⚠️",
            "reminder": "🔔",
        }
        for m in memories:
            icon = icon_by_cat.get(m.get("category", "fact"), "📌")
            content = m.get("content", "")
            lines.append(f"{icon} {content}")
        return "\n".join(lines)


memory = Memory()
