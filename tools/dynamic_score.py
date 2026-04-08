"""
Score Dinamico - Ajusta score das escolas baseado em interacoes REAIS.

Score VIVO que sobe quando escola abre/clica/responde e desce quando ignora.
Roda automaticamente a cada 30 min pelo scheduler.

Fontes de dados:
- approval_queue: opened_at, clicked_at, replied_at, bounced_at (direto)
- interactions: meeting_scheduled, meeting_completed, etc
- meetings: outcome (fechou?)

Decay temporal: engajamento recente vale mais (ultimos 7 dias = 100%,
8-30 dias = 50%, 31+ dias = 25%).

Usage:
    from tools.dynamic_score import dynamic_scorer
    new_score = dynamic_scorer.update_score("company-uuid")
    results = dynamic_scorer.update_all_scores()
    breakdown = dynamic_scorer.get_score_breakdown("company-uuid")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

from database.supabase_client import db
from utils.logger import logger


# ============================================================================
# SCORE ADJUSTMENTS
# ============================================================================

SCORE_RULES: Dict[str, int] = {
    "email_opened": 5,          # por email aberto
    "email_clicked": 10,        # por link clicado (sinal mais forte)
    "email_replied": 25,        # por resposta (sinal fortissimo)
    "meeting_scheduled": 35,    # reuniao agendada
    "meeting_completed": 20,    # reuniao realizada (bonus extra)
    "meeting_closed": 50,       # fechou negocio!
    "no_response_3": -15,       # 3+ emails sem resposta
    "no_open_3": -10,           # 3+ emails sem abertura
    "email_bounced": -25,       # bounce = contato ruim
    "days_inactive_30": -10,    # inativo ha 30+ dias
}

MIN_SCORE: int = 0
MAX_SCORE: int = 100


# ============================================================================
# DYNAMIC SCORER
# ============================================================================

class DynamicScorer:
    """Recalcula scores de empresas com base em interacoes registradas."""

    def __init__(self) -> None:
        """Inicializa o scorer."""
        self.rules: Dict[str, int] = SCORE_RULES.copy()

    # ========================================================================
    # PUBLIC METHODS
    # ========================================================================

    def update_score(self, company_id: str) -> int:
        """
        Recalcula o score de uma empresa baseado em todas as interacoes.

        Args:
            company_id: UUID da empresa na tabela companies.

        Returns:
            Novo score (0-100) ja salvo no banco.
        """
        try:
            breakdown = self.get_score_breakdown(company_id)
            new_score: int = breakdown["final_score"]

            db.update_company(company_id, {"qualification_score": new_score})

            logger.info(
                "Score atualizado",
                extra={
                    "company_id": company_id,
                    "base_score": breakdown["base_score"],
                    "adjustment": breakdown["total_adjustment"],
                    "final_score": new_score,
                },
            )
            return new_score

        except Exception as e:
            logger.error(
                f"Erro ao atualizar score: {e}",
                extra={"company_id": company_id},
            )
            return -1

    def update_all_scores(self) -> Dict[str, Any]:
        """
        Recalcula scores de todas as empresas que possuem interacoes.

        Returns:
            Dict com total processado, sucessos e falhas.
        """
        updated: int = 0
        failed: int = 0
        company_ids: List[str] = []

        try:
            seen = set()
            # Buscar empresas com emails enviados (fonte primaria)
            queue_result = db.client.table("approval_queue").select(
                "company_id"
            ).eq("status", "sent").execute()
            for row in (queue_result.data or []):
                cid = row.get("company_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    company_ids.append(cid)

            # Tambem empresas com interacoes
            int_result = db.client.table("interactions").select(
                "company_id"
            ).execute()
            for row in (int_result.data or []):
                cid = row.get("company_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    company_ids.append(cid)

        except Exception as e:
            logger.error(f"Erro ao listar empresas para score: {e}")
            return {"total": 0, "updated": 0, "failed": 0}

        for cid in company_ids:
            score = self.update_score(cid)
            if score >= 0:
                updated += 1
            else:
                failed += 1

        summary = {
            "total": len(company_ids),
            "updated": updated,
            "failed": failed,
        }
        logger.info("Atualizacao em lote concluida", extra=summary)
        return summary

    def _decay_multiplier(self, iso_str: Optional[str]) -> float:
        """Retorna multiplicador de decay temporal (recente vale mais).
        Ultimos 7 dias: 1.0 | 8-30 dias: 0.5 | 31+ dias: 0.25
        """
        if not iso_str:
            return 0.25
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days
            if days <= 7:
                return 1.0
            elif days <= 30:
                return 0.5
            else:
                return 0.25
        except Exception:
            return 0.25

    def get_score_breakdown(self, company_id: str) -> Dict[str, Any]:
        """
        Retorna detalhamento do score: base + ajustes de engajamento REAL.
        Usa dados diretos da approval_queue (opened_at, clicked_at, etc)
        + tabela interactions + meetings. Com decay temporal.
        """
        # -- score base (qualificacao IA original) --
        base_score: int = 0
        try:
            result = (
                db.client.table("companies")
                .select("qualification_score")
                .eq("id", company_id)
                .single()
                .execute()
            )
            if result.data:
                base_score = int(result.data.get("qualification_score") or 0)
        except Exception:
            pass

        adjustments: List[Dict[str, Any]] = []
        total_adjustment: float = 0

        # -- DADOS DA APPROVAL_QUEUE (fonte primaria de engajamento) --
        emails_sent = 0
        emails_opened = 0
        emails_clicked = 0
        emails_replied = 0
        emails_bounced = 0
        last_activity = None

        try:
            queue_items = db.client.table("approval_queue").select(
                "sent_at,opened_at,clicked_at,replied_at,bounced_at"
            ).eq("company_id", company_id).eq("status", "sent").execute().data or []

            for q in queue_items:
                emails_sent += 1
                if q.get("opened_at"):
                    decay = self._decay_multiplier(q["opened_at"])
                    emails_opened += 1
                    total_adjustment += self.rules["email_opened"] * decay
                if q.get("clicked_at"):
                    decay = self._decay_multiplier(q["clicked_at"])
                    emails_clicked += 1
                    total_adjustment += self.rules["email_clicked"] * decay
                if q.get("replied_at"):
                    decay = self._decay_multiplier(q["replied_at"])
                    emails_replied += 1
                    total_adjustment += self.rules["email_replied"] * decay
                    last_activity = q["replied_at"]
                if q.get("bounced_at"):
                    emails_bounced += 1
                    total_adjustment += self.rules["email_bounced"]

                # Track ultima atividade
                for field in ("replied_at", "clicked_at", "opened_at", "sent_at"):
                    val = q.get(field)
                    if val and (not last_activity or val > last_activity):
                        last_activity = val

        except Exception:
            pass

        # Registrar ajustes detalhados
        if emails_opened > 0:
            adjustments.append({"rule": "email_opened", "count": emails_opened, "points": round(self.rules["email_opened"] * emails_opened * 0.5, 1)})
        if emails_clicked > 0:
            adjustments.append({"rule": "email_clicked", "count": emails_clicked, "points": round(self.rules["email_clicked"] * emails_clicked * 0.5, 1)})
        if emails_replied > 0:
            adjustments.append({"rule": "email_replied", "count": emails_replied, "points": round(self.rules["email_replied"] * emails_replied * 0.5, 1)})
        if emails_bounced > 0:
            adjustments.append({"rule": "email_bounced", "count": emails_bounced, "points": self.rules["email_bounced"] * emails_bounced})

        # -- MEETINGS --
        try:
            meets = db.client.table("meetings").select(
                "status,outcome,scheduled_at"
            ).eq("company_id", company_id).execute().data or []
            for m in meets:
                if m.get("status") in ("scheduled", "completed"):
                    decay = self._decay_multiplier(m.get("scheduled_at"))
                    total_adjustment += self.rules["meeting_scheduled"] * decay
                    adjustments.append({"rule": "meeting_scheduled", "count": 1, "points": round(self.rules["meeting_scheduled"] * decay, 1)})
                if m.get("outcome") == "fechado":
                    total_adjustment += self.rules["meeting_closed"]
                    adjustments.append({"rule": "meeting_closed", "count": 1, "points": self.rules["meeting_closed"]})
                elif m.get("status") == "completed":
                    total_adjustment += self.rules["meeting_completed"]
                    adjustments.append({"rule": "meeting_completed", "count": 1, "points": self.rules["meeting_completed"]})
        except Exception:
            pass

        # -- PENALIDADES --
        # Sem resposta apos 3+ emails
        if emails_sent >= 3 and emails_replied == 0:
            total_adjustment += self.rules["no_response_3"]
            adjustments.append({"rule": "no_response_3", "count": emails_sent, "points": self.rules["no_response_3"]})

        # Sem abertura apos 3+ emails
        if emails_sent >= 3 and emails_opened == 0:
            total_adjustment += self.rules["no_open_3"]
            adjustments.append({"rule": "no_open_3", "count": emails_sent, "points": self.rules["no_open_3"]})

        # Inativo ha 30+ dias
        if last_activity:
            try:
                last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                days_inactive = (datetime.now(timezone.utc) - last_dt).days
                if days_inactive >= 30:
                    total_adjustment += self.rules["days_inactive_30"]
                    adjustments.append({"rule": "days_inactive_30", "count": days_inactive, "points": self.rules["days_inactive_30"]})
            except Exception:
                pass

        # Clamp
        final_score: int = max(MIN_SCORE, min(MAX_SCORE, base_score + int(total_adjustment)))

        return {
            "company_id": company_id,
            "base_score": base_score,
            "adjustments": adjustments,
            "total_adjustment": int(total_adjustment),
            "final_score": final_score,
            "emails_sent": emails_sent,
            "emails_opened": emails_opened,
            "emails_clicked": emails_clicked,
            "emails_replied": emails_replied,
        }


# ============================================================================
# SINGLETON
# ============================================================================

dynamic_scorer = DynamicScorer()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import json

    if len(sys.argv) > 1:
        cid = sys.argv[1]
        breakdown = dynamic_scorer.get_score_breakdown(cid)
        print(json.dumps(breakdown, indent=2, default=str))
    else:
        result = dynamic_scorer.update_all_scores()
        print(json.dumps(result, indent=2))
