"""
Smart Scheduler - Agenda envios para horarios com melhor taxa de abertura.
Escolas tendem a abrir emails em horarios especificos.

Analisa dados historicos de abertura de emails para determinar
os melhores horarios e dias da semana para envio. Quando nao ha
dados suficientes, usa defaults baseados em padroes B2B educacionais.

Classes:
    SmartScheduler: Agendador inteligente baseado em dados

Usage:
    from tools.smart_scheduler import smart_scheduler

    # Proximo melhor horario para envio
    best_time = smart_scheduler.suggest_send_time()

    # Analise completa
    analysis = smart_scheduler.get_schedule_analysis()
"""

import sys
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger


# ============================================================================
# CONSTANTS
# ============================================================================

# Horarios padrao para escolas (quando nao ha dados historicos)
DEFAULT_OPTIMAL_HOURS: List[int] = [7, 8, 10, 13, 14]

# Dias padrao B2B (0=Segunda, 1=Terca, 2=Quarta, 3=Quinta)
DEFAULT_BEST_DAYS: List[int] = [1, 2, 3]

# Minimo de data points para considerar dados historicos confiaveis
MIN_DATA_POINTS: int = 10

# Quantidade de melhores horarios/dias a retornar
TOP_N_HOURS: int = 5
TOP_N_DAYS: int = 3


# ============================================================================
# SMART SCHEDULER
# ============================================================================

class SmartScheduler:
    """
    Agendador inteligente que sugere horarios otimos para envio de emails.

    Analisa dados historicos de abertura para identificar padroes.
    Quando nao ha dados suficientes, usa defaults baseados em
    comportamento tipico de escolas brasileiras.
    """

    def __init__(self) -> None:
        """Inicializa o SmartScheduler."""
        pass

    def _fetch_open_data(self) -> List[datetime]:
        """
        Busca timestamps de abertura de emails do banco.

        Returns:
            Lista de datetimes quando emails foram abertos.
        """
        try:
            response = (
                db.client.table("approval_queue")
                .select("opened_at")
                .not_.is_("opened_at", "null")
                .execute()
            )

            opens: List[datetime] = []
            if response.data:
                for row in response.data:
                    opened_at: Optional[str] = row.get("opened_at")
                    if opened_at:
                        try:
                            dt: datetime = datetime.fromisoformat(
                                opened_at.replace("Z", "+00:00")
                            )
                            opens.append(dt)
                        except (ValueError, TypeError):
                            continue

            logger.info(
                f"Dados de abertura carregados: {len(opens)} registros",
                extra={"count": len(opens)},
            )
            return opens

        except Exception as e:
            logger.warning(
                f"Erro ao buscar dados de abertura: {e}",
                extra={"error": str(e)},
            )
            return []

    def get_optimal_hours(self) -> List[int]:
        """
        Retorna as melhores horas do dia para envio de email.

        Analisa aberturas passadas para encontrar horarios com maior
        taxa de abertura. Se nao ha dados suficientes, retorna defaults
        baseados em horarios escolares.

        Returns:
            Lista ordenada de horas (0-23) com melhor performance.
        """
        opens: List[datetime] = self._fetch_open_data()

        if len(opens) < MIN_DATA_POINTS:
            logger.info(
                f"Dados insuficientes ({len(opens)}/{MIN_DATA_POINTS}), "
                f"usando horarios padrao",
            )
            return DEFAULT_OPTIMAL_HOURS

        hour_counter: Counter = Counter(dt.hour for dt in opens)
        best_hours: List[int] = [
            hour for hour, _ in hour_counter.most_common(TOP_N_HOURS)
        ]

        logger.info(
            f"Melhores horarios (baseado em {len(opens)} aberturas): {best_hours}",
            extra={"hours": best_hours, "data_points": len(opens)},
        )
        return sorted(best_hours)

    def get_best_days(self) -> List[int]:
        """
        Retorna os melhores dias da semana para envio.

        Analisa aberturas passadas por dia da semana (0=Segunda).
        Se nao ha dados suficientes, retorna Terca/Quarta/Quinta.

        Returns:
            Lista ordenada de dias da semana (0=Seg, 6=Dom).
        """
        opens: List[datetime] = self._fetch_open_data()

        if len(opens) < MIN_DATA_POINTS:
            logger.info(
                f"Dados insuficientes ({len(opens)}/{MIN_DATA_POINTS}), "
                f"usando dias padrao",
            )
            return DEFAULT_BEST_DAYS

        day_counter: Counter = Counter(dt.weekday() for dt in opens)
        best_days: List[int] = [
            day for day, _ in day_counter.most_common(TOP_N_DAYS)
        ]

        day_names: List[str] = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]
        logger.info(
            f"Melhores dias (baseado em {len(opens)} aberturas): "
            f"{[day_names[d] for d in sorted(best_days)]}",
            extra={"days": best_days, "data_points": len(opens)},
        )
        return sorted(best_days)

    def suggest_send_time(self) -> datetime:
        """
        Sugere o proximo melhor momento para enviar emails.

        Se o momento atual esta em uma janela boa (dia e hora otimos),
        retorna agora. Caso contrario, calcula o proximo slot otimo.

        Returns:
            Datetime sugerido para o proximo envio.
        """
        now: datetime = datetime.now()
        optimal_hours: List[int] = self.get_optimal_hours()
        best_days: List[int] = self.get_best_days()

        # Check if now is a good time
        if now.weekday() in best_days and now.hour in optimal_hours:
            logger.info(
                "Momento atual e otimo para envio",
                extra={"hour": now.hour, "day": now.weekday()},
            )
            return now

        # Find next optimal slot
        candidate: datetime = now.replace(minute=0, second=0, microsecond=0)

        # Try up to 7 days ahead
        for day_offset in range(8):
            check_date: datetime = candidate + timedelta(days=day_offset)

            if check_date.weekday() not in best_days:
                continue

            for hour in optimal_hours:
                potential: datetime = check_date.replace(hour=hour)

                if potential > now:
                    day_names: List[str] = [
                        "Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"
                    ]
                    logger.info(
                        f"Proximo slot otimo: {day_names[potential.weekday()]} "
                        f"as {potential.strftime('%H:%M')}",
                        extra={
                            "suggested": potential.isoformat(),
                            "day": potential.weekday(),
                            "hour": potential.hour,
                        },
                    )
                    return potential

        # Fallback: next business day at first optimal hour
        fallback: datetime = now + timedelta(days=1)
        fallback = fallback.replace(
            hour=optimal_hours[0], minute=0, second=0, microsecond=0
        )
        logger.info(
            f"Usando fallback: {fallback.strftime('%d/%m %H:%M')}",
            extra={"suggested": fallback.isoformat()},
        )
        return fallback

    def get_schedule_analysis(self) -> Dict[str, Any]:
        """
        Retorna analise completa de agendamento para exibicao no dashboard.

        Returns:
            Dict com:
                - best_hours (List[int]): Melhores horarios
                - best_days (List[str]): Melhores dias (nomes)
                - data_points (int): Quantidade de dados analisados
                - using_defaults (bool): Se esta usando valores padrao
                - next_suggested (str): Proximo horario sugerido
                - hourly_distribution (Dict[int, int]): Aberturas por hora
                - daily_distribution (Dict[str, int]): Aberturas por dia
        """
        opens: List[datetime] = self._fetch_open_data()
        using_defaults: bool = len(opens) < MIN_DATA_POINTS

        day_names: List[str] = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab", "Dom"]

        best_hours: List[int] = self.get_optimal_hours()
        best_days: List[int] = self.get_best_days()
        next_time: datetime = self.suggest_send_time()

        # Build distributions
        hourly_distribution: Dict[int, int] = {}
        daily_distribution: Dict[str, int] = {}

        if not using_defaults:
            hour_counter: Counter = Counter(dt.hour for dt in opens)
            hourly_distribution = dict(hour_counter)

            day_counter: Counter = Counter(dt.weekday() for dt in opens)
            daily_distribution = {
                day_names[day]: count for day, count in day_counter.items()
            }

        analysis: Dict[str, Any] = {
            "best_hours": best_hours,
            "best_days": [day_names[d] for d in best_days],
            "data_points": len(opens),
            "using_defaults": using_defaults,
            "next_suggested": next_time.strftime("%d/%m/%Y %H:%M"),
            "hourly_distribution": hourly_distribution,
            "daily_distribution": daily_distribution,
        }

        logger.info(
            f"Analise de agendamento gerada "
            f"({'defaults' if using_defaults else f'{len(opens)} data points'})",
            extra=analysis,
        )
        return analysis


# ============================================================================
# SINGLETON
# ============================================================================

smart_scheduler: SmartScheduler = SmartScheduler()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    print("=== Smart Scheduler - IAprendo ===\n")

    analysis: Dict[str, Any] = smart_scheduler.get_schedule_analysis()

    if analysis["using_defaults"]:
        print(f"[INFO] Usando valores padrao (dados insuficientes: {analysis['data_points']}/{MIN_DATA_POINTS})")
    else:
        print(f"[INFO] Baseado em {analysis['data_points']} aberturas de email")

    print(f"\nMelhores horarios: {analysis['best_hours']}")
    print(f"Melhores dias:     {analysis['best_days']}")
    print(f"Proximo envio:     {analysis['next_suggested']}")

    if analysis["hourly_distribution"]:
        print("\nDistribuicao por hora:")
        for hour in sorted(analysis["hourly_distribution"]):
            count: int = analysis["hourly_distribution"][hour]
            bar: str = "#" * count
            print(f"  {hour:02d}h: {bar} ({count})")

    if analysis["daily_distribution"]:
        print("\nDistribuicao por dia:")
        for day, count in analysis["daily_distribution"].items():
            bar = "#" * count
            print(f"  {day}: {bar} ({count})")
