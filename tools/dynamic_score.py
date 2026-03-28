"""
Score Dinamico - Ajusta score das escolas baseado em interacoes.

Recalcula o qualification_score de cada empresa somando o score base
(qualificacao IA) com bonus/penalidades de interacoes reais.

Regras de ajuste:
    - Email aberto:          +10
    - Link clicado:          +15
    - Resposta recebida:     +30
    - Reuniao agendada:      +50
    - Sem resposta a 3 emails: -20
    - Email bounced:         -30

Usage:
    from tools.dynamic_score import dynamic_scorer

    # Recalcular score de uma empresa
    new_score = dynamic_scorer.update_score("company-uuid")

    # Recalcular todas
    results = dynamic_scorer.update_all_scores()

    # Ver detalhamento
    breakdown = dynamic_scorer.get_score_breakdown("company-uuid")
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List, Optional
from datetime import datetime

from database.supabase_client import db
from utils.logger import logger


# ============================================================================
# SCORE ADJUSTMENTS
# ============================================================================

SCORE_RULES: Dict[str, int] = {
    "email_opened": 10,
    "link_clicked": 15,
    "reply_received": 30,
    "meeting_scheduled": 50,
    "no_response_3": -20,
    "email_bounced": -30,
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
            # Buscar empresas que tem pelo menos uma interacao
            result = (
                db.client.table("interactions")
                .select("company_id")
                .execute()
            )
            if result.data:
                seen = set()
                for row in result.data:
                    cid = row.get("company_id")
                    if cid and cid not in seen:
                        seen.add(cid)
                        company_ids.append(cid)

        except Exception as e:
            logger.error(f"Erro ao listar empresas com interacoes: {e}")
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

    def get_score_breakdown(self, company_id: str) -> Dict[str, Any]:
        """
        Retorna detalhamento do score: base + cada ajuste individual.

        Args:
            company_id: UUID da empresa.

        Returns:
            Dict com base_score, adjustments (lista), total_adjustment,
            final_score.
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
        except Exception as e:
            logger.warning(f"Nao encontrou score base: {e}")

        # -- interacoes --
        interactions: List[Dict[str, Any]] = []
        try:
            result = (
                db.client.table("interactions")
                .select("*")
                .eq("company_id", company_id)
                .order("created_at", desc=False)
                .execute()
            )
            if result.data:
                interactions = result.data
        except Exception as e:
            logger.warning(f"Nao encontrou interacoes: {e}")

        # -- calcular ajustes --
        adjustments: List[Dict[str, Any]] = []
        total_adjustment: int = 0

        # Contar eventos relevantes
        emails_sent: int = 0
        emails_opened: int = 0
        links_clicked: int = 0
        replies: int = 0
        meetings: int = 0
        bounces: int = 0

        for interaction in interactions:
            itype = (interaction.get("type") or "").lower()
            status = (interaction.get("status") or "").lower()

            if itype == "email_sent":
                emails_sent += 1
            elif itype in ("email_opened", "opened"):
                emails_opened += 1
            elif itype in ("link_clicked", "clicked"):
                links_clicked += 1
            elif itype in ("reply_received", "reply", "responded"):
                replies += 1
            elif itype in ("meeting_scheduled", "meeting"):
                meetings += 1
            elif itype in ("email_bounced", "bounced", "bounce"):
                bounces += 1

            # Tambem checa status do approval_queue
            if status == "bounced":
                bounces += 1

        # Aplicar regras
        if emails_opened > 0:
            adj = self.rules["email_opened"] * emails_opened
            adjustments.append({"rule": "email_opened", "count": emails_opened, "points": adj})
            total_adjustment += adj

        if links_clicked > 0:
            adj = self.rules["link_clicked"] * links_clicked
            adjustments.append({"rule": "link_clicked", "count": links_clicked, "points": adj})
            total_adjustment += adj

        if replies > 0:
            adj = self.rules["reply_received"] * replies
            adjustments.append({"rule": "reply_received", "count": replies, "points": adj})
            total_adjustment += adj

        if meetings > 0:
            adj = self.rules["meeting_scheduled"] * meetings
            adjustments.append({"rule": "meeting_scheduled", "count": meetings, "points": adj})
            total_adjustment += adj

        if bounces > 0:
            adj = self.rules["email_bounced"] * bounces
            adjustments.append({"rule": "email_bounced", "count": bounces, "points": adj})
            total_adjustment += adj

        # Sem resposta apos 3+ emails
        if emails_sent >= 3 and replies == 0 and meetings == 0:
            adj = self.rules["no_response_3"]
            adjustments.append({"rule": "no_response_3", "count": 1, "points": adj})
            total_adjustment += adj

        # Clamp
        final_score: int = max(MIN_SCORE, min(MAX_SCORE, base_score + total_adjustment))

        return {
            "company_id": company_id,
            "base_score": base_score,
            "adjustments": adjustments,
            "total_adjustment": total_adjustment,
            "final_score": final_score,
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
