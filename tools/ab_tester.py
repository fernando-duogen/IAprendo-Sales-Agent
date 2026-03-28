"""
AB Tester - Gera variacoes de assunto de email e mede performance.

Usa Claude Haiku para gerar variantes de subject line e rastreia
qual variante performa melhor (open rate, click rate).

Usage:
    from tools.ab_tester import ab_tester

    # Gerar variantes de assunto
    variants = ab_tester.generate_variants(
        original_subject="IA educacional para sua escola",
        company_name="Colegio Farroupilha"
    )
    # ["IA educacional para sua escola", "Variante A...", "Variante B..."]

    # Atribuir variante a um item da fila
    chosen = ab_tester.assign_variant(queue_id="uuid-123", variants=variants)

    # Consultar resultados dos ultimos 30 dias
    results = ab_tester.get_results(days=30)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


class ABTester:
    """Gerencia testes A/B de subject lines para emails de prospecao.

    Gera variantes de assunto usando Claude Haiku, atribui aleatoriamente
    a cada envio e mede performance para identificar o vencedor.
    """

    def __init__(self) -> None:
        """Inicializa AB tester com cliente Anthropic."""
        self.api_key: str = (
            getattr(settings, "ANTHROPIC_API_KEY", "")
            or os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.model: str = getattr(
            settings, "CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001"
        )
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """Retorna cliente Anthropic (lazy init).

        Returns:
            Cliente Anthropic inicializado.

        Raises:
            RuntimeError: Se ANTHROPIC_API_KEY nao estiver configurada.
        """
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY nao configurada - AB testing requer Claude API"
                )
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    "Pacote 'anthropic' nao instalado. Execute: pip install anthropic"
                )
        return self._client

    # ========================================================================
    # GERACAO DE VARIANTES
    # ========================================================================

    def generate_variants(
        self,
        original_subject: str,
        company_name: str,
    ) -> List[str]:
        """Gera 2 variantes alternativas de assunto de email usando Claude Haiku.

        Retorna o assunto original + 2 variantes para teste A/B.

        Args:
            original_subject: Assunto original do email.
            company_name: Nome da escola/empresa (para contexto).

        Returns:
            Lista com 3 assuntos: [original, variante_A, variante_B].
            Se a geracao falhar, retorna apenas [original].
        """
        try:
            client = self._get_client()

            prompt = (
                f"Gere 2 variacoes curtas deste assunto de email comercial "
                f"para escola: \"{original_subject}\"\n"
                f"Escola: {company_name}\n\n"
                f"Regras:\n"
                f"- Mantenha profissional e curto (max 60 caracteres cada)\n"
                f"- Cada variacao deve ter abordagem diferente "
                f"(curiosidade, beneficio direto, pergunta, etc)\n"
                f"- Nunca use clickbait ou promessas exageradas\n"
                f"- Retorne APENAS JSON valido no formato: "
                f'{{\"variants\": [\"variacao1\", \"variacao2\"]}}'
            )

            response = client.messages.create(
                model=self.model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extrai texto da resposta
            text = response.content[0].text.strip()

            # Tenta parsear JSON (remove possivel markdown)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            data = json.loads(text)
            variants = data.get("variants", [])

            if not variants or len(variants) < 2:
                logger.warning(
                    "AB Tester: Claude retornou menos de 2 variantes",
                    extra={"response": text},
                )
                return [original_subject]

            # Trunca variantes longas
            clean_variants: List[str] = []
            for v in variants[:2]:
                v = v.strip()
                if len(v) > 60:
                    v = v[:57] + "..."
                clean_variants.append(v)

            result = [original_subject] + clean_variants

            logger.info(
                "AB Tester: variantes geradas",
                extra={
                    "original": original_subject,
                    "variant_a": clean_variants[0],
                    "variant_b": clean_variants[1],
                    "company": company_name,
                },
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(
                "AB Tester: falha ao parsear resposta do Claude",
                extra={"error": str(e)},
            )
        except Exception as e:
            logger.error(
                "AB Tester: erro ao gerar variantes",
                extra={"error": str(e), "original": original_subject},
            )

        return [original_subject]

    # ========================================================================
    # ATRIBUICAO DE VARIANTE
    # ========================================================================

    def assign_variant(
        self,
        queue_id: str,
        variants: List[str],
    ) -> str:
        """Atribui aleatoriamente uma variante a um item da fila de aprovacao.

        Sorteia uma das variantes, armazena no campo metadata do
        approval_queue e retorna o assunto escolhido.

        Args:
            queue_id: UUID do item na tabela approval_queue.
            variants: Lista de assuntos (original + variantes).

        Returns:
            O assunto escolhido (variante atribuida).
        """
        if not variants:
            logger.warning("AB Tester: lista de variantes vazia")
            return ""

        # Sorteia indice: 0=original, 1=variant_A, 2=variant_B
        chosen_index = random.randint(0, len(variants) - 1)
        chosen_subject = variants[chosen_index]

        # Nomeia a variante
        variant_labels = ["original", "variant_a", "variant_b"]
        variant_label = (
            variant_labels[chosen_index]
            if chosen_index < len(variant_labels)
            else f"variant_{chosen_index}"
        )

        try:
            # Busca metadata atual do item
            response = (
                db.client.table("approval_queue")
                .select("metadata")
                .eq("id", queue_id)
                .single()
                .execute()
            )

            current_metadata: Dict[str, Any] = {}
            if response.data and response.data.get("metadata"):
                current_metadata = response.data["metadata"]

            # Adiciona dados do AB test
            current_metadata["ab_test"] = {
                "variants": variants,
                "chosen_index": chosen_index,
                "chosen_label": variant_label,
                "chosen_subject": chosen_subject,
                "assigned_at": datetime.now(timezone.utc).isoformat(),
            }

            # Atualiza no Supabase
            db.client.table("approval_queue").update({
                "metadata": current_metadata,
            }).eq("id", queue_id).execute()

            logger.info(
                "AB Tester: variante atribuida",
                extra={
                    "queue_id": queue_id,
                    "variant": variant_label,
                    "subject": chosen_subject,
                },
            )

        except Exception as e:
            logger.error(
                "AB Tester: erro ao salvar variante",
                extra={"queue_id": queue_id, "error": str(e)},
            )

        return chosen_subject

    # ========================================================================
    # RESULTADOS
    # ========================================================================

    def get_results(self, days: int = 30) -> Dict[str, Any]:
        """Calcula resultados do teste A/B nos ultimos N dias.

        Agrupa emails enviados por variante e calcula open rate e click rate
        para determinar o vencedor.

        Args:
            days: Numero de dias para considerar (padrao: 30).

        Returns:
            Dicionario com resultados:
            {
                "period_days": int,
                "total_tested": int,
                "variants": {
                    "original": {"sent": int, "opened": int, "clicked": int, "open_rate": float, "click_rate": float},
                    "variant_a": {...},
                    "variant_b": {...},
                },
                "winner": str (label da variante vencedora),
                "winner_open_rate": float,
                "confidence": str ("low"/"medium"/"high" baseado em volume)
            }
        """
        results: Dict[str, Any] = {
            "period_days": days,
            "total_tested": 0,
            "variants": {},
            "winner": "insufficient_data",
            "winner_open_rate": 0.0,
            "confidence": "low",
        }

        try:
            since = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat()

            # Busca itens enviados com dados de AB test
            response = (
                db.client.table("approval_queue")
                .select("metadata, status, sent_at, opened_at, clicked_at")
                .eq("status", "sent")
                .gte("sent_at", since)
                .execute()
            )

            items = response.data or []

            # Filtra apenas itens com AB test
            ab_items: List[Dict[str, Any]] = []
            for item in items:
                meta = item.get("metadata") or {}
                if "ab_test" in meta:
                    ab_items.append(item)

            results["total_tested"] = len(ab_items)

            if not ab_items:
                logger.info("AB Tester: nenhum dado de teste encontrado no periodo")
                return results

            # Agrupa por variante
            variant_stats: Dict[str, Dict[str, int]] = {}

            for item in ab_items:
                ab_data = item["metadata"]["ab_test"]
                label = ab_data.get("chosen_label", "unknown")

                if label not in variant_stats:
                    variant_stats[label] = {
                        "sent": 0,
                        "opened": 0,
                        "clicked": 0,
                    }

                variant_stats[label]["sent"] += 1

                if item.get("opened_at"):
                    variant_stats[label]["opened"] += 1

                if item.get("clicked_at"):
                    variant_stats[label]["clicked"] += 1

            # Calcula taxas e encontra vencedor
            best_label = ""
            best_open_rate = -1.0

            for label, stats in variant_stats.items():
                sent = stats["sent"]
                open_rate = (stats["opened"] / sent * 100) if sent > 0 else 0.0
                click_rate = (stats["clicked"] / sent * 100) if sent > 0 else 0.0

                results["variants"][label] = {
                    "sent": sent,
                    "opened": stats["opened"],
                    "clicked": stats["clicked"],
                    "open_rate": round(open_rate, 1),
                    "click_rate": round(click_rate, 1),
                }

                if open_rate > best_open_rate:
                    best_open_rate = open_rate
                    best_label = label

            results["winner"] = best_label
            results["winner_open_rate"] = round(best_open_rate, 1)

            # Confianca baseada em volume
            total = results["total_tested"]
            if total >= 100:
                results["confidence"] = "high"
            elif total >= 30:
                results["confidence"] = "medium"
            else:
                results["confidence"] = "low"

            logger.info(
                "AB Tester: resultados calculados",
                extra={
                    "total": total,
                    "winner": best_label,
                    "open_rate": best_open_rate,
                    "confidence": results["confidence"],
                },
            )

        except Exception as e:
            logger.error(
                "AB Tester: erro ao calcular resultados",
                extra={"error": str(e)},
            )

        return results


# Singleton
ab_tester = ABTester()
