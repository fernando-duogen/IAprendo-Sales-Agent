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
MIN_COMPANY_DATA_POINTS: int = 3  # para analise individual da escola

# Feriados nacionais BR 2026 (mes, dia)
FERIADOS_BR: List[tuple] = [
    (1, 1),    # Ano Novo
    (2, 16),   # Carnaval (segunda)
    (2, 17),   # Carnaval (terca)
    (4, 3),    # Sexta-feira Santa
    (4, 21),   # Tiradentes
    (5, 1),    # Dia do Trabalho
    (6, 4),    # Corpus Christi
    (9, 7),    # Independencia
    (10, 12),  # N.S. Aparecida
    (11, 2),   # Finados
    (11, 15),  # Proclamacao Republica
    (12, 25),  # Natal
]

# Fase do ano letivo — peso de receptividade (0.0 a 1.0)
FASE_LETIVA: Dict[int, float] = {
    1: 0.3,   # Janeiro: ferias — evitar
    2: 0.5,   # Fevereiro: volta as aulas, escola ocupada
    3: 0.9,   # Marco: alta — orcamentos, planejamento
    4: 0.9,   # Abril: alta — rotina estabelecida
    5: 0.8,   # Maio: boa receptividade
    6: 0.7,   # Junho: pre-ferias, ainda receptivos
    7: 0.2,   # Julho: ferias — evitar
    8: 0.8,   # Agosto: volta 2o semestre
    9: 0.8,   # Setembro: boa receptividade
    10: 0.7,  # Outubro: medio
    11: 0.5,  # Novembro: fim de ano, correria
    12: 0.2,  # Dezembro: recesso — evitar
}

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


    # ================================================================
    # METODOS NOVOS — Calendario inteligente
    # ================================================================

    def _is_feriado(self, dt: datetime) -> bool:
        """Verifica se uma data e feriado nacional."""
        return (dt.month, dt.day) in FERIADOS_BR

    def _is_dia_util(self, dt: datetime) -> bool:
        """Verifica se e dia util (seg-sex, nao feriado)."""
        return dt.weekday() < 5 and not self._is_feriado(dt)

    def _fase_letiva_peso(self, dt: datetime) -> float:
        """Retorna peso de receptividade do mes (0.0-1.0)."""
        return FASE_LETIVA.get(dt.month, 0.5)

    def _fetch_company_open_data(self, company_id: str) -> List[datetime]:
        """Busca timestamps de abertura especificos de uma escola."""
        try:
            r = db.client.table("approval_queue").select(
                "opened_at"
            ).eq("company_id", company_id).not_.is_(
                "opened_at", "null"
            ).execute()
            opens = []
            for row in (r.data or []):
                try:
                    dt = datetime.fromisoformat(row["opened_at"].replace("Z", "+00:00"))
                    opens.append(dt)
                except Exception:
                    pass
            return opens
        except Exception:
            return []

    def suggest_send_time_for_company(
        self, company_id: Optional[str] = None
    ) -> datetime:
        """Sugere melhor horario de envio considerando:
        1. Padrao individual da escola (se tem tracking)
        2. Padrao geral (todos os emails)
        3. Feriados nacionais
        4. Fase do ano letivo
        5. Dias uteis

        Args:
            company_id: UUID da escola (opcional — se None, usa padrao geral)

        Returns:
            datetime com timezone -03:00 do proximo slot otimo
        """
        from datetime import timezone as _tz

        # 1. Tentar padrao individual da escola
        optimal_hours = DEFAULT_OPTIMAL_HOURS
        best_days = DEFAULT_BEST_DAYS

        if company_id:
            company_opens = self._fetch_company_open_data(company_id)
            if len(company_opens) >= MIN_COMPANY_DATA_POINTS:
                hour_counter = Counter(dt.hour for dt in company_opens)
                optimal_hours = sorted([h for h, _ in hour_counter.most_common(TOP_N_HOURS)])
                day_counter = Counter(dt.weekday() for dt in company_opens)
                best_days = sorted([d for d, _ in day_counter.most_common(TOP_N_DAYS)])
                logger.info(f"Usando padrao individual da escola ({len(company_opens)} opens)")
            else:
                # Fallback: padrao geral
                optimal_hours = self.get_optimal_hours()
                best_days = self.get_best_days()
        else:
            optimal_hours = self.get_optimal_hours()
            best_days = self.get_best_days()

        # 2. Encontrar proximo slot que seja dia util + nao feriado + fase letiva ok
        brt = _tz(timedelta(hours=-3))
        now = datetime.now(brt)
        candidate = now.replace(minute=0, second=0, microsecond=0)

        for day_offset in range(60):  # buscar ate 60 dias no futuro
            check_date = candidate + timedelta(days=day_offset)

            # Pular feriados e finais de semana
            if not self._is_dia_util(check_date):
                continue

            # Pular dias da semana que nao sao otimos (se tiver dados)
            if check_date.weekday() not in best_days:
                continue

            # Verificar fase letiva — se peso < 0.3, pular (ferias/recesso)
            peso = self._fase_letiva_peso(check_date)
            if peso < 0.3:
                continue

            for hour in optimal_hours:
                potential = check_date.replace(hour=hour, tzinfo=brt)
                if potential > now:
                    logger.info(
                        f"Slot otimo para escola: {potential.strftime('%d/%m %H:%M')}",
                        extra={
                            "company_id": company_id,
                            "hour": hour,
                            "day": check_date.weekday(),
                            "fase_peso": peso,
                        },
                    )
                    return potential

        # Fallback: amanha 8h (BRT)
        fallback = (now + timedelta(days=1)).replace(
            hour=8, minute=0, second=0, microsecond=0, tzinfo=brt,
        )
        return fallback


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
