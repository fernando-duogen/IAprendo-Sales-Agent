"""
Pipeline Config - Configuracao do pipeline automatico do IAlex.

Armazena as preferencias do Fernando (horario, dias, etapas, limites) na tabela
conversation_memory (scope='global', category='fact') usando um marker no
conteudo para evitar nova migration.

Schema do config:
    {
        "enabled": True,
        "schedule_time": "08:00",          # HH:MM 24h
        "days": ["mon","tue","wed","thu","fri"],
        "steps": ["qualify","enrich","contacts","write"],
        "limits": {
            "qualify_limit": 20,
            "enrich_limit": 10,
            "write_limit": 10,
        },
        "write_mode": "ai",                # "ai" ou "template"
        "send_approved": False,
        "dry_run": False,
    }

Usage:
    from integrations.pipeline_config import pipeline_config
    cfg = pipeline_config.get_config()
    pipeline_config.save_config({**cfg, "schedule_time": "07:30"})
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from database.supabase_client import db
from utils.logger import logger


MARKER = "[PIPELINE_CONFIG_V1]"
VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
VALID_STEPS = {"qualify", "enrich", "contacts", "write", "send"}

# Modo de Autonomia — controla o quanto o IAlex pode agir sozinho
#   manual:     ZERO automacao. Scheduler nao dispara nada para contatos.
#               Fernando opera 100% manualmente no dashboard/WhatsApp.
#   semi_auto:  IAlex gera emails/follow-ups e poe na fila de aprovacao.
#               NUNCA envia sem Fernando aprovar 1 a 1. (DEFAULT — mais seguro)
#   full_auto:  IAlex tambem envia automaticamente o que Fernando ja aprovou.
#               Requer opt-in EXPLICITO com confirmacao dupla.
VALID_AUTONOMY_LEVELS = {"manual", "semi_auto", "full_auto"}
DEFAULT_AUTONOMY_LEVEL = "semi_auto"


class PipelineConfig:
    """Wrapper para ler/gravar a configuracao do pipeline automatico."""

    TABLE = "conversation_memory"

    # =========================================================================
    # Defaults
    # =========================================================================

    def default_config(self) -> Dict[str, Any]:
        """Retorna a configuracao padrao (usada quando nao ha nada salvo)."""
        return {
            # Modo de autonomia global (DEFAULT: semi_auto — nunca envia sem aprovacao)
            "autonomy_level": DEFAULT_AUTONOMY_LEVEL,
            "autonomy_authorized_at": None,  # timestamp de quando Fernando autorizou full_auto
            "enabled": False,
            "schedule_time": "08:00",
            "days": ["mon", "tue", "wed", "thu", "fri"],
            "steps": ["qualify", "enrich", "contacts", "write"],
            "limits": {
                "qualify_limit": 20,
                "enrich_limit": 10,
                "write_limit": 10,
            },
            "write_mode": "ai",
            "send_approved": False,
            "dry_run": False,
            "last_run_at": None,
            "last_run_status": None,
            # Follow-ups comportamentais (Item 6)
            "followup_enabled": False,
            "followup_time": "09:30",
            "followup_limit": 20,
            "followup_types": ["hot_click", "curious_open", "silent_open", "revival"],
        }

    # =========================================================================
    # Validacao
    # =========================================================================

    def _validate(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Limpa e valida a configuracao, preenchendo campos ausentes com defaults."""
        defaults = self.default_config()
        out: Dict[str, Any] = {**defaults, **(cfg or {})}

        # === Autonomy level (safety-first) ===
        lvl = str(out.get("autonomy_level", DEFAULT_AUTONOMY_LEVEL)).lower()
        if lvl not in VALID_AUTONOMY_LEVELS:
            lvl = DEFAULT_AUTONOMY_LEVEL
        out["autonomy_level"] = lvl

        # Se nao for full_auto, forcar send_approved=False e remover "send" dos steps
        # (garantia defensiva: mesmo que alguem tenha salvo send=True num nivel inferior)
        if lvl != "full_auto":
            out["send_approved"] = False

        # enabled
        out["enabled"] = bool(out.get("enabled", False))

        # schedule_time: HH:MM
        st = str(out.get("schedule_time", "08:00"))
        try:
            hh, mm = st.split(":")
            h, m = int(hh), int(mm)
            assert 0 <= h <= 23 and 0 <= m <= 59
            out["schedule_time"] = f"{h:02d}:{m:02d}"
        except Exception:
            out["schedule_time"] = "08:00"

        # days
        days = out.get("days") or []
        days = [d for d in days if d in VALID_DAYS]
        if not days:
            days = ["mon", "tue", "wed", "thu", "fri"]
        out["days"] = days

        # steps
        steps = out.get("steps") or []
        steps = [s for s in steps if s in VALID_STEPS]
        if not steps:
            steps = ["qualify", "enrich", "contacts", "write"]
        # Gate: fora de full_auto, NUNCA permitir step "send" (trava de seguranca)
        if out["autonomy_level"] != "full_auto" and "send" in steps:
            steps = [s for s in steps if s != "send"]
        out["steps"] = steps

        # limits
        limits = out.get("limits") or {}
        out["limits"] = {
            "qualify_limit": max(1, min(500, int(limits.get("qualify_limit", 20) or 20))),
            "enrich_limit": max(1, min(500, int(limits.get("enrich_limit", 10) or 10))),
            "write_limit": max(1, min(500, int(limits.get("write_limit", 10) or 10))),
        }

        # write_mode
        wm = str(out.get("write_mode", "ai")).lower()
        out["write_mode"] = wm if wm in ("ai", "template") else "ai"

        # send_approved / dry_run
        out["send_approved"] = bool(out.get("send_approved", False))
        out["dry_run"] = bool(out.get("dry_run", False))

        # === Follow-ups (Item 6) ===
        out["followup_enabled"] = bool(out.get("followup_enabled", False))

        fu_time = str(out.get("followup_time", "09:30"))
        try:
            hh, mm = fu_time.split(":")
            h, m = int(hh), int(mm)
            assert 0 <= h <= 23 and 0 <= m <= 59
            out["followup_time"] = f"{h:02d}:{m:02d}"
        except Exception:
            out["followup_time"] = "09:30"

        out["followup_limit"] = max(1, min(100, int(out.get("followup_limit", 20) or 20)))

        valid_fu_types = {"hot_click", "curious_open", "silent_open", "revival"}
        fu_types = out.get("followup_types") or []
        fu_types = [t for t in fu_types if t in valid_fu_types]
        if not fu_types:
            fu_types = list(valid_fu_types)
        out["followup_types"] = fu_types

        return out

    # =========================================================================
    # Persistencia (via conversation_memory)
    # =========================================================================

    def _is_available(self) -> bool:
        try:
            db.client.table(self.TABLE).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def _find_existing(self) -> Optional[Dict[str, Any]]:
        """Retorna o registro mais recente com o marker de pipeline_config."""
        if not self._is_available():
            return None
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
            logger.debug(f"pipeline_config find_existing: {e}")
            return None

    def get_config(self) -> Dict[str, Any]:
        """Carrega configuracao do banco (com defaults se nao existir)."""
        existing = self._find_existing()
        if not existing:
            return self.default_config()
        try:
            content = existing.get("content", "")
            payload = content[len(MARKER):].strip()
            data = json.loads(payload)
            return self._validate(data)
        except Exception as e:
            logger.warning(f"pipeline_config get_config: falha ao parsear, usando defaults: {e}")
            return self.default_config()

    def save_config(self, cfg: Dict[str, Any]) -> bool:
        """Salva configuracao (remove antigas antes de inserir nova)."""
        if not self._is_available():
            logger.error("pipeline_config save: conversation_memory indisponivel")
            return False
        cfg = self._validate(cfg)
        try:
            # Remover configs antigas
            db.client.table(self.TABLE).delete().eq("scope", "global").ilike(
                "content", f"{MARKER}%"
            ).execute()
            # Inserir nova
            payload = MARKER + json.dumps(cfg, ensure_ascii=False)
            data = {
                "scope": "global",
                "scope_id": None,
                "category": "fact",
                "content": payload[:2000],
                "importance": 9,
                "source": "ialex",
            }
            db.client.table(self.TABLE).insert(data).execute()
            logger.info(
                "pipeline_config salvo",
                extra={
                    "enabled": cfg["enabled"],
                    "time": cfg["schedule_time"],
                    "days": cfg["days"],
                    "steps": cfg["steps"],
                },
            )
            return True
        except Exception as e:
            logger.error(f"pipeline_config save_config: {e}")
            return False

    # =========================================================================
    # Autonomy helpers
    # =========================================================================

    def get_autonomy_level(self) -> str:
        """Retorna o nivel atual (manual, semi_auto, full_auto)."""
        return self.get_config().get("autonomy_level", DEFAULT_AUTONOMY_LEVEL)

    def can_automate(self) -> bool:
        """True se o scheduler pode disparar geracao automatica (semi_auto ou full_auto)."""
        return self.get_autonomy_level() in ("semi_auto", "full_auto")

    def can_send_automatically(self) -> bool:
        """True SOMENTE se o nivel e full_auto. Todas as outras camadas DEVEM checar isto
        antes de chamar send_approved_messages em contexto automatico."""
        return self.get_autonomy_level() == "full_auto"

    def set_autonomy_level(self, level: str) -> Dict[str, Any]:
        """Altera o nivel de autonomia. Se descer para manual/semi_auto, limpa
        send_approved e remove 'send' dos steps automaticamente.
        Retorna dict com o que mudou.
        """
        if level not in VALID_AUTONOMY_LEVELS:
            return {"ok": False, "error": f"nivel invalido: {level}"}
        cfg = self.get_config()
        old_level = cfg.get("autonomy_level", DEFAULT_AUTONOMY_LEVEL)
        cfg["autonomy_level"] = level
        if level == "full_auto":
            cfg["autonomy_authorized_at"] = datetime.now(timezone.utc).isoformat()
        else:
            cfg["autonomy_authorized_at"] = None
            cfg["send_approved"] = False
            cfg["steps"] = [s for s in cfg.get("steps", []) if s != "send"]
        ok = self.save_config(cfg)
        logger.info(
            "autonomy_level alterado",
            extra={"from": old_level, "to": level, "ok": ok},
        )
        return {"ok": ok, "from": old_level, "to": level}

    def update_last_run(self, status: str, summary: Optional[Dict[str, Any]] = None) -> None:
        """Marca no config a data/hora do ultimo run (para exibir no dashboard)."""
        try:
            cfg = self.get_config()
            cfg["last_run_at"] = datetime.now(timezone.utc).isoformat()
            cfg["last_run_status"] = status
            if summary:
                cfg["last_run_summary"] = summary
            self.save_config(cfg)
        except Exception as e:
            logger.debug(f"pipeline_config update_last_run: {e}")

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def weekday_short_from_date(dt: datetime) -> str:
        """Retorna mon/tue/... para um datetime."""
        return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][dt.weekday()]

    @staticmethod
    def day_label(day: str) -> str:
        """Traduz mon -> Seg, etc."""
        return {
            "mon": "Seg", "tue": "Ter", "wed": "Qua",
            "thu": "Qui", "fri": "Sex", "sat": "Sab", "sun": "Dom",
        }.get(day, day)

    @staticmethod
    def step_label(step: str) -> str:
        """Traduz step -> Nome amigavel."""
        return {
            "qualify": "Qualificar",
            "enrich": "Enriquecer",
            "contacts": "Buscar contatos",
            "write": "Gerar emails",
            "send": "Enviar aprovados",
        }.get(step, step)


pipeline_config = PipelineConfig()
