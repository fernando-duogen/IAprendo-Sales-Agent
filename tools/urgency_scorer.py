"""
Urgency Scorer (F2) - Score de urgencia unificado (0-100).

Combina 4 sub-scores independentes num unico valor que determina
a prioridade de atencao para cada lead:

  urgency = W_eng * engagement + W_pred * predictive + W_int * intent + W_enem * enem

Sub-scores (0-100 cada):
  - Engagement: dynamic_score.py (opens/clicks/replies com decay temporal)
  - Predictive: predictive_scorer.py (probabilidade ML de fechamento)
  - Intent: intent_detector.py (sinais de compra em tempo real)
  - ENEM: enem_tools.py P1/P2/P3 (oportunidade estrategica)

Tiers (thresholds configuraveis via settings):
  - CRITICAL (80-100): Alerta WhatsApp imediato + auto-draft follow-up
  - HOT (60-79): Destaque no briefing matinal
  - WARM (40-59): Notificacao dashboard
  - COLD (0-39): Background tracking

Usage:
    from tools.urgency_scorer import urgency_scorer

    # Score de uma escola
    result = urgency_scorer.compute_urgency("company-uuid")
    # {"urgency_score": 82, "urgency_tier": "CRITICAL", "sub_scores": {...}, "reasons": [...]}

    # Batch update
    summary = urgency_scorer.compute_all()

    # Leads por tier
    critical = urgency_scorer.get_by_tier("CRITICAL")

    # Mudancas de tier nas ultimas 72h
    changes = urgency_scorer.detect_tier_changes(hours=72)
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


# ============================================================================
# ENEM PRIORITY MAPPING
# ============================================================================

ENEM_PRIORITY_SCORES: Dict[str, int] = {
    "P1": 90,   # Alta oportunidade
    "P2": 70,   # Media
    "P3": 60,   # Urgencia defensiva
}
ENEM_DEFAULT_SCORE: int = 30  # Sem dados ENEM


# ============================================================================
# URGENCY SCORER
# ============================================================================

class UrgencyScorer:
    """Motor de score de urgencia unificado.

    Combina engagement, preditivo, intent e ENEM num unico score 0-100,
    com tiers configuraveis e historico para deteccao de tendencias.
    """

    def __init__(self) -> None:
        """Inicializa com pesos e thresholds de settings."""
        self.w_engagement: float = settings.URGENCY_W_ENGAGEMENT
        self.w_predictive: float = settings.URGENCY_W_PREDICTIVE
        self.w_intent: float = settings.URGENCY_W_INTENT
        self.w_enem: float = settings.URGENCY_W_ENEM

        self.tier_critical: int = settings.URGENCY_TIER_CRITICAL
        self.tier_hot: int = settings.URGENCY_TIER_HOT
        self.tier_warm: int = settings.URGENCY_TIER_WARM

    # ========================================================================
    # PUBLIC: Score individual
    # ========================================================================

    def compute_urgency(self, company_id: str) -> Dict[str, Any]:
        """Calcula score de urgencia unificado para uma empresa.

        Args:
            company_id: UUID da empresa.

        Returns:
            Dict com urgency_score (0-100), urgency_tier, sub_scores e reasons.
        """
        sub_eng = self._get_engagement_score(company_id)
        sub_pred = self._get_predictive_score(company_id)
        sub_int = self._get_intent_score(company_id)
        sub_enem = self._get_enem_priority_score(company_id)

        raw = (
            self.w_engagement * sub_eng
            + self.w_predictive * sub_pred
            + self.w_intent * sub_int
            + self.w_enem * sub_enem
        )
        urgency_score: int = max(0, min(100, round(raw)))
        urgency_tier: str = self._determine_tier(urgency_score)

        reasons: List[str] = []
        if sub_int >= 70:
            reasons.append(f"Sinal de compra forte ({sub_int})")
        if sub_eng >= 60:
            reasons.append(f"Engajamento alto ({sub_eng})")
        if sub_pred >= 60:
            reasons.append(f"Alta probabilidade preditiva ({sub_pred})")
        if sub_enem >= 80:
            reasons.append("Prioridade ENEM P1")
        elif sub_enem >= 60:
            reasons.append("Prioridade ENEM P2/P3")

        result: Dict[str, Any] = {
            "company_id": company_id,
            "urgency_score": urgency_score,
            "urgency_tier": urgency_tier,
            "sub_scores": {
                "engagement": sub_eng,
                "predictive": sub_pred,
                "intent": sub_int,
                "enem": sub_enem,
            },
            "reasons": reasons,
        }

        self._save_urgency(company_id, urgency_score, urgency_tier, result["sub_scores"])
        return result

    # ========================================================================
    # PUBLIC: Batch update
    # ========================================================================

    def compute_all(self) -> Dict[str, Any]:
        """Recalcula urgency para todas as empresas com engajamento.

        Returns:
            Dict com total, updated, failed, by_tier, tier_changes.
        """
        updated: int = 0
        failed: int = 0
        by_tier: Dict[str, int] = {"CRITICAL": 0, "HOT": 0, "WARM": 0, "COLD": 0}
        tier_changes: List[Dict[str, Any]] = []

        company_ids = self._get_active_company_ids()
        if not company_ids:
            return {"total": 0, "updated": 0, "failed": 0, "by_tier": by_tier, "tier_changes": []}

        # Buscar tiers anteriores para detectar mudancas
        old_tiers: Dict[str, str] = {}
        try:
            rows = db.client.table("companies").select(
                "id,urgency_tier"
            ).in_("id", company_ids).execute().data or []
            for r in rows:
                old_tiers[r["id"]] = r.get("urgency_tier", "COLD") or "COLD"
        except Exception:
            pass

        for cid in company_ids:
            try:
                result = self.compute_urgency(cid)
                tier = result["urgency_tier"]
                by_tier[tier] = by_tier.get(tier, 0) + 1
                updated += 1

                old = old_tiers.get(cid, "COLD")
                if old != tier:
                    tier_changes.append({
                        "company_id": cid,
                        "old_tier": old,
                        "new_tier": tier,
                        "urgency_score": result["urgency_score"],
                    })
            except Exception as e:
                logger.debug(f"Urgency compute failed for {cid}: {e}")
                failed += 1

        summary: Dict[str, Any] = {
            "total": len(company_ids),
            "updated": updated,
            "failed": failed,
            "by_tier": by_tier,
            "tier_changes": tier_changes,
        }
        logger.info("Urgency batch update concluido", extra=summary)
        return summary

    # ========================================================================
    # PUBLIC: Queries
    # ========================================================================

    def get_by_tier(self, tier: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna empresas de um tier especifico, ordenadas por score DESC.

        Args:
            tier: CRITICAL, HOT, WARM ou COLD.
            limit: Max resultados.

        Returns:
            Lista de dicts com id, name, city, urgency_score, urgency_tier.
        """
        try:
            result = db.client.table("companies").select(
                "id,name,city,state,urgency_score,urgency_tier,qualification_score,status"
            ).eq("urgency_tier", tier).order(
                "urgency_score", desc=True
            ).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Erro ao buscar tier {tier}: {e}")
            return []

    def get_critical_leads(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Atalho para leads CRITICAL."""
        return self.get_by_tier("CRITICAL", limit)

    def get_score_breakdown(self, company_id: str) -> Dict[str, Any]:
        """Retorna breakdown detalhado sem recalcular (ultimo snapshot do historico).

        Args:
            company_id: UUID da empresa.

        Returns:
            Dict com score, tier, sub_scores e computed_at.
        """
        try:
            result = db.client.table("urgency_score_history").select(
                "urgency_score,urgency_tier,sub_engagement,sub_predictive,sub_intent,sub_enem,weights_used,computed_at"
            ).eq("company_id", company_id).order(
                "computed_at", desc=True
            ).limit(1).execute()
            if result.data:
                row = result.data[0]
                return {
                    "urgency_score": row["urgency_score"],
                    "urgency_tier": row["urgency_tier"],
                    "sub_scores": {
                        "engagement": row["sub_engagement"],
                        "predictive": row["sub_predictive"],
                        "intent": row["sub_intent"],
                        "enem": row["sub_enem"],
                    },
                    "weights": row.get("weights_used"),
                    "computed_at": row["computed_at"],
                }
            return {"urgency_score": 0, "urgency_tier": "COLD", "sub_scores": {}, "computed_at": None}
        except Exception as e:
            logger.error(f"Erro ao buscar breakdown: {e}")
            return {"urgency_score": 0, "urgency_tier": "COLD", "sub_scores": {}, "computed_at": None}

    # ========================================================================
    # PUBLIC: Trends
    # ========================================================================

    def detect_tier_changes(self, hours: int = 72) -> List[Dict[str, Any]]:
        """Detecta empresas que mudaram de tier nas ultimas N horas.

        Args:
            hours: Janela de busca (default 72h).

        Returns:
            Lista de mudancas: company_id, name, old_tier, new_tier, old_score, new_score.
        """
        changes: List[Dict[str, Any]] = []
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

            # Buscar empresas com historico recente
            recent = db.client.table("urgency_score_history").select(
                "company_id"
            ).gte("computed_at", cutoff).execute().data or []

            company_ids = list({r["company_id"] for r in recent})
            if not company_ids:
                return []

            for cid in company_ids[:100]:  # cap para performance
                try:
                    history = db.client.table("urgency_score_history").select(
                        "urgency_score,urgency_tier,computed_at"
                    ).eq("company_id", cid).order(
                        "computed_at", desc=True
                    ).limit(10).execute().data or []

                    if len(history) < 2:
                        continue

                    newest = history[0]
                    # Encontrar o snapshot mais antigo na janela
                    oldest_in_window = history[-1]
                    for h in reversed(history):
                        try:
                            ct = datetime.fromisoformat(h["computed_at"].replace("Z", "+00:00"))
                            if ct >= datetime.fromisoformat(cutoff.replace("Z", "+00:00")):
                                oldest_in_window = h
                                break
                        except Exception:
                            continue

                    if newest["urgency_tier"] != oldest_in_window["urgency_tier"]:
                        # Buscar nome da escola
                        name = "?"
                        try:
                            c = db.client.table("companies").select("name").eq("id", cid).limit(1).execute()
                            if c.data:
                                name = c.data[0].get("name", "?")
                        except Exception:
                            pass

                        changes.append({
                            "company_id": cid,
                            "name": name,
                            "old_tier": oldest_in_window["urgency_tier"],
                            "new_tier": newest["urgency_tier"],
                            "old_score": oldest_in_window["urgency_score"],
                            "new_score": newest["urgency_score"],
                        })
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Erro ao detectar tier changes: {e}")

        return changes

    def get_score_history(self, company_id: str, limit: int = 14) -> List[int]:
        """Retorna historico de scores para sparkline.

        Args:
            company_id: UUID da empresa.
            limit: Max snapshots (default 14).

        Returns:
            Lista de scores (mais antigo primeiro).
        """
        try:
            result = db.client.table("urgency_score_history").select(
                "urgency_score"
            ).eq("company_id", company_id).order(
                "computed_at", desc=True
            ).limit(limit).execute()
            scores = [r["urgency_score"] for r in (result.data or [])]
            return list(reversed(scores))  # mais antigo primeiro
        except Exception:
            return []

    # ========================================================================
    # PRIVATE: Sub-score extractors
    # ========================================================================

    def _get_engagement_score(self, company_id: str) -> int:
        """Extrai sub-score de engajamento do DynamicScorer.

        Delega para dynamic_scorer.get_score_breakdown() e usa o final_score.
        Fallback: qualification_score da empresa.
        """
        try:
            from tools.dynamic_score import dynamic_scorer
            breakdown = dynamic_scorer.get_score_breakdown(company_id)
            return max(0, min(100, breakdown.get("final_score", 0)))
        except Exception:
            # Fallback: qualification_score direto da tabela
            try:
                r = db.client.table("companies").select(
                    "qualification_score"
                ).eq("id", company_id).limit(1).execute()
                if r.data:
                    return r.data[0].get("qualification_score", 0) or 0
            except Exception:
                pass
            return 0

    def _get_predictive_score(self, company_id: str) -> int:
        """Extrai sub-score preditivo do PredictiveScorer.

        Delega para predictive_scorer.predict_company(). Fallback: 50 (neutro).
        """
        try:
            from tools.predictive_scorer import predictive_scorer
            result = predictive_scorer.predict_company(company_id)
            return max(0, min(100, result.get("score", 50)))
        except Exception:
            return 50  # Neutro quando modelo indisponivel

    def _get_intent_score(self, company_id: str) -> int:
        """Extrai sub-score de intent do IntentDetector.

        Busca o max signal score para esta empresa nos ultimos 7 dias.
        """
        try:
            from tools.intent_detector import intent_detector
            signals = intent_detector.detect_all_signals(days=7)
            max_score: int = 0
            for s in signals:
                if s.get("company_id") == company_id:
                    max_score = max(max_score, s.get("score", 0))
            return max_score
        except Exception:
            return 0

    def _get_enem_priority_score(self, company_id: str) -> int:
        """Extrai sub-score de prioridade ENEM.

        Busca inep_code da empresa, depois school_analytics para dados ENEM.
        Classifica como P1/P2/P3 usando logica simplificada do enem_tools.
        """
        try:
            # Buscar inep_code
            comp = db.client.table("companies").select(
                "inep_code"
            ).eq("id", company_id).limit(1).execute()
            if not comp.data:
                return ENEM_DEFAULT_SCORE
            inep = comp.data[0].get("inep_code")
            if not inep:
                return ENEM_DEFAULT_SCORE

            # Buscar dados ENEM
            sa = db.client.table("school_analytics").select(
                "enem_media_geral,enem_percentil_br,enem_delta_2020_2024,amostra_confiavel"
            ).eq("inep_code", str(inep)).limit(1).execute()
            if not sa.data:
                return ENEM_DEFAULT_SCORE

            row = sa.data[0]
            if not row.get("amostra_confiavel"):
                return ENEM_DEFAULT_SCORE

            # Classificacao simplificada P1/P2/P3
            percentil = row.get("enem_percentil_br") or 0
            delta = row.get("enem_delta_2020_2024") or 0

            if percentil >= 70 and delta >= 0:
                priority = "P1"  # Alta performance + melhorando
            elif percentil <= 40 or delta < -10:
                priority = "P3"  # Urgencia defensiva
            else:
                priority = "P2"  # Media

            return ENEM_PRIORITY_SCORES.get(priority, ENEM_DEFAULT_SCORE)
        except Exception:
            return ENEM_DEFAULT_SCORE

    # ========================================================================
    # PRIVATE: Persistence
    # ========================================================================

    def _save_urgency(
        self,
        company_id: str,
        score: int,
        tier: str,
        sub_scores: Dict[str, int],
    ) -> None:
        """Salva score em companies e insere snapshot no historico."""
        now = datetime.now(timezone.utc).isoformat()
        weights = {
            "engagement": self.w_engagement,
            "predictive": self.w_predictive,
            "intent": self.w_intent,
            "enem": self.w_enem,
        }

        try:
            db.client.table("companies").update({
                "urgency_score": score,
                "urgency_tier": tier,
                "urgency_updated_at": now,
            }).eq("id", company_id).execute()
        except Exception as e:
            logger.debug(f"Urgency save to companies failed: {e}")

        try:
            db.client.table("urgency_score_history").insert({
                "company_id": company_id,
                "urgency_score": score,
                "urgency_tier": tier,
                "sub_engagement": sub_scores.get("engagement", 0),
                "sub_predictive": sub_scores.get("predictive", 0),
                "sub_intent": sub_scores.get("intent", 0),
                "sub_enem": sub_scores.get("enem", 0),
                "weights_used": json.dumps(weights),
                "computed_at": now,
            }).execute()
        except Exception as e:
            logger.debug(f"Urgency history insert failed: {e}")

    def _determine_tier(self, score: int) -> str:
        """Determina tier com base nos thresholds configuraveis."""
        if score >= self.tier_critical:
            return "CRITICAL"
        elif score >= self.tier_hot:
            return "HOT"
        elif score >= self.tier_warm:
            return "WARM"
        else:
            return "COLD"

    def _get_active_company_ids(self) -> List[str]:
        """Retorna IDs de empresas com algum engajamento (emails enviados ou interacoes)."""
        seen: set = set()
        ids: List[str] = []
        try:
            # Empresas com emails enviados
            q = db.client.table("approval_queue").select(
                "company_id"
            ).eq("status", "sent").execute()
            for row in (q.data or []):
                cid = row.get("company_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    ids.append(cid)

            # Empresas com interacoes
            i = db.client.table("interactions").select(
                "company_id"
            ).execute()
            for row in (i.data or []):
                cid = row.get("company_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    ids.append(cid)
        except Exception as e:
            logger.error(f"Erro ao listar empresas ativas: {e}")
        return ids


# Singleton
urgency_scorer = UrgencyScorer()


# ============================================================================
# CLI para testes
# ============================================================================

if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) > 1 and _sys.argv[1] == "--all":
        print("Rodando compute_all()...")
        result = urgency_scorer.compute_all()
        print(f"Total: {result['total']} | Updated: {result['updated']} | Failed: {result['failed']}")
        print(f"By tier: {result['by_tier']}")
        if result["tier_changes"]:
            print(f"Tier changes: {len(result['tier_changes'])}")
            for ch in result["tier_changes"][:5]:
                print(f"  {ch['old_tier']} -> {ch['new_tier']} (score {ch['urgency_score']})")
    elif len(_sys.argv) > 1:
        cid = _sys.argv[1]
        print(f"Computing urgency for {cid}...")
        result = urgency_scorer.compute_urgency(cid)
        print(f"Score: {result['urgency_score']} | Tier: {result['urgency_tier']}")
        print(f"Sub-scores: {result['sub_scores']}")
        print(f"Reasons: {result['reasons']}")
    else:
        print("Usage: python tools/urgency_scorer.py <company_id>")
        print("       python tools/urgency_scorer.py --all")
