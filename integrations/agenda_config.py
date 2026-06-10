"""
Agenda Config — configuracao da Agenda/Metas do redesign v2 (F1).

Armazena na conversation_memory (scope='global') com marker, no mesmo padrao do
pipeline_config (evita migration de tabela de config).

Schema do config:
    {
        "ticket_por_aluno": 7.99,        # R$/aluno/mes — base da Receita Potencial (§3.2)
        "teto_em_conversa": 15,          # leads ativos por vendedor (ICP §2.1)
        "limite_email_dia": 50,          # anti-bloqueio por vendedor
        "limite_whatsapp_dia": 30,
        "away": {"felipe": "2026-07-15"} # username -> ausente ate (ISO date) (SPEC §5.2)
    }

Usage:
    from integrations.agenda_config import agenda_config
    cfg = agenda_config.get_config()
    agenda_config.set_away("felipe", "2026-07-15")
"""
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from database.supabase_client import db
from utils.logger import logger

MARKER = "[AGENDA_CONFIG_V1]"


class AgendaConfig:
    """Wrapper para ler/gravar a configuracao da agenda/metas."""

    TABLE = "conversation_memory"

    def default_config(self) -> Dict[str, Any]:
        return {
            "ticket_por_aluno": 7.99,
            "teto_em_conversa": 15,
            "limite_email_dia": 50,
            "limite_whatsapp_dia": 30,
            "away": {},
        }

    def _validate(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {**self.default_config(), **(cfg or {})}
        try:
            out["ticket_por_aluno"] = max(0.1, min(500.0, float(out.get("ticket_por_aluno") or 7.99)))
        except (TypeError, ValueError):
            out["ticket_por_aluno"] = 7.99
        try:
            out["teto_em_conversa"] = max(1, min(100, int(out.get("teto_em_conversa") or 15)))
        except (TypeError, ValueError):
            out["teto_em_conversa"] = 15
        try:
            out["limite_email_dia"] = max(1, min(500, int(out.get("limite_email_dia") or 50)))
        except (TypeError, ValueError):
            out["limite_email_dia"] = 50
        try:
            out["limite_whatsapp_dia"] = max(1, min(200, int(out.get("limite_whatsapp_dia") or 30)))
        except (TypeError, ValueError):
            out["limite_whatsapp_dia"] = 30
        # away: {username: 'YYYY-MM-DD'}; datas invalidas/passadas sao removidas
        away_in = out.get("away") or {}
        away: Dict[str, str] = {}
        if isinstance(away_in, dict):
            for user, until in away_in.items():
                try:
                    d = date.fromisoformat(str(until))
                    if d >= date.today():
                        away[str(user)] = d.isoformat()
                except (TypeError, ValueError):
                    continue
        out["away"] = away
        return out

    def _find_existing(self) -> Optional[Dict[str, Any]]:
        try:
            r = (
                db.client.table(self.TABLE)
                .select("*")
                .eq("scope", "global")
                .ilike("content", f"{MARKER}%")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return (r.data or [None])[0]
        except Exception as e:
            logger.debug(f"agenda_config find_existing: {e}")
            return None

    def get_config(self) -> Dict[str, Any]:
        existing = self._find_existing()
        if not existing:
            return self.default_config()
        try:
            payload = existing.get("content", "")[len(MARKER):].strip()
            return self._validate(json.loads(payload))
        except Exception as e:
            logger.warning(f"agenda_config get_config: parse falhou, defaults: {e}")
            return self.default_config()

    def save_config(self, cfg: Dict[str, Any]) -> bool:
        cfg = self._validate(cfg)
        try:
            db.client.table(self.TABLE).delete().eq("scope", "global").ilike(
                "content", f"{MARKER}%"
            ).execute()
            payload = MARKER + json.dumps(cfg, ensure_ascii=False)
            db.client.table(self.TABLE).insert({
                "scope": "global",
                "scope_id": None,
                "category": "fact",
                "content": payload[:2000],
                "importance": 9,
                "source": "ialex",
            }).execute()
            logger.info("agenda_config salvo", extra={"cfg": cfg})
            return True
        except Exception as e:
            logger.error(f"agenda_config save_config: {e}")
            return False

    # ------------------------------------------------------------------ helpers

    def is_away(self, username: Optional[str]) -> bool:
        """True se o usuario esta marcado como ausente (ferias) hoje (SPEC §5.2)."""
        if not username:
            return False
        until = self.get_config().get("away", {}).get(username)
        if not until:
            return False
        try:
            return date.fromisoformat(until) >= date.today()
        except (TypeError, ValueError):
            return False

    def set_away(self, username: str, until: Optional[str]) -> bool:
        """Marca/desmarca ausencia. until=None remove a flag."""
        cfg = self.get_config()
        away = dict(cfg.get("away") or {})
        if until:
            away[username] = str(until)
        else:
            away.pop(username, None)
        cfg["away"] = away
        return self.save_config(cfg)

    def ticket_por_aluno(self) -> float:
        return float(self.get_config().get("ticket_por_aluno", 7.99))


agenda_config = AgendaConfig()
