"""
Logger - Sistema de logging estruturado em JSON.

Este módulo fornece um logger centralizado que gera logs em formato JSON
para facilitar análise e monitoramento. Todos os módulos do sistema devem
usar este logger ao invés do logging padrão do Python.

Features:
    - Logs em JSON estruturado (fácil de parsear)
    - 3 handlers: arquivo principal, console (dev), arquivo de erros
    - Suporte a campos extras (context metadata)
    - Rotação automática de logs (futuro)

Usage:
    from utils.logger import logger

    # Log simples
    logger.info("Operação concluída")

    # Log com contexto
    logger.info(
        "Escola qualificada",
        extra={'school_id': '123', 'score': 85}
    )

    # Log de erro
    try:
        result = risky_operation()
    except Exception as e:
        logger.error(
            "Operação falhou",
            extra={'operation': 'risky_operation', 'error': str(e)},
            exc_info=True
        )
"""

import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger
from typing import Optional

# Import settings - mas com fallback se não estiver configurado ainda
try:
    from config.settings import settings
    LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    ENVIRONMENT = settings.ENVIRONMENT
except (ImportError, ValueError):
    # Fallback durante setup inicial
    LOG_LEVEL = logging.INFO
    ENVIRONMENT = 'development'


def setup_logger(name: str = "iaprendo") -> logging.Logger:
    """
    Configura logger estruturado com output JSON.

    Cria 3 handlers:
        1. Arquivo principal (logs/application.log) - JSON, nivel DEBUG+
        2. Console (stdout) - Texto simples, nivel INFO+, apenas em dev
        3. Arquivo de erros (logs/errors.log) - JSON, nivel ERROR+

    Args:
        name: Nome do logger (default: "iaprendo").

    Returns:
        Logger configurado e pronto para uso.

    Example:
        >>> logger = setup_logger("meu_modulo")
        >>> logger.info("Teste", extra={'key': 'value'})
    """
    logger = logging.getLogger(name)

    # Evita duplicação de handlers se já inicializado
    if logger.handlers:
        return logger

    logger.setLevel(LOG_LEVEL)

    # Criar diretório de logs se não existir
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # ========================================================================
    # HANDLER 1: Arquivo JSON (PRINCIPAL)
    # ========================================================================
    file_handler = logging.FileHandler(
        log_dir / "application.log",
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # Formatter JSON estruturado
    json_formatter = jsonlogger.JsonFormatter(
        fmt='%(asctime)s %(name)s %(levelname)s %(message)s',
        rename_fields={
            'asctime': 'timestamp',
            'levelname': 'level',
            'name': 'module'
        }
    )
    file_handler.setFormatter(json_formatter)
    logger.addHandler(file_handler)

    # ========================================================================
    # HANDLER 2: Console (DESENVOLVIMENTO)
    # ========================================================================
    if ENVIRONMENT == 'development':
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter texto simples para console
        console_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # ========================================================================
    # HANDLER 3: Arquivo de ERROS
    # ========================================================================
    error_handler = logging.FileHandler(
        log_dir / "errors.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(json_formatter)
    logger.addHandler(error_handler)

    # Log inicial
    logger.info(
        "Logger inicializado",
        extra={
            'log_level': logging.getLevelName(LOG_LEVEL),
            'environment': ENVIRONMENT,
            'log_dir': str(log_dir.absolute())
        }
    )

    return logger


# ============================================================================
# SINGLETON - Instância única para todo o sistema
# ============================================================================
logger = setup_logger("iaprendo")


# ============================================================================
# HELPERS OPCIONAIS
# ============================================================================

def log_function_call(func_name: str, **kwargs) -> None:
    """
    Helper para logar chamadas de função com parâmetros.

    Args:
        func_name: Nome da função sendo chamada.
        **kwargs: Parâmetros da função.

    Example:
        >>> log_function_call("qualify_school", school_id="123", score=85)
    """
    logger.debug(
        f"Função chamada: {func_name}",
        extra={'function': func_name, 'params': kwargs}
    )


def log_api_call(
    api_name: str,
    endpoint: str,
    method: str = "GET",
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    **extra_fields
) -> None:
    """
    Helper para logar chamadas de API com métricas.

    Args:
        api_name: Nome da API (ex: "anthropic", "apollo").
        endpoint: Endpoint chamado.
        method: Método HTTP (default: GET).
        status_code: HTTP status code da resposta.
        duration_ms: Duração da chamada em milissegundos.
        **extra_fields: Campos adicionais.

    Example:
        >>> log_api_call(
        ...     api_name="anthropic",
        ...     endpoint="/v1/messages",
        ...     method="POST",
        ...     status_code=200,
        ...     duration_ms=1234.5,
        ...     tokens_used=150
        ... )
    """
    log_data = {
        'api_name': api_name,
        'endpoint': endpoint,
        'method': method
    }

    if status_code is not None:
        log_data['status_code'] = status_code

    if duration_ms is not None:
        log_data['duration_ms'] = duration_ms

    # Adicionar campos extras
    log_data.update(extra_fields)

    level = logging.INFO if status_code and status_code < 400 else logging.WARNING
    logger.log(
        level,
        f"API call: {api_name} {method} {endpoint}",
        extra=log_data
    )


def log_database_operation(
    operation: str,
    table: str,
    duration_ms: Optional[float] = None,
    rows_affected: Optional[int] = None,
    **extra_fields
) -> None:
    """
    Helper para logar operações de banco de dados.

    Args:
        operation: Tipo de operação (SELECT, INSERT, UPDATE, DELETE).
        table: Nome da tabela.
        duration_ms: Duração da operação em milissegundos.
        rows_affected: Número de linhas afetadas.
        **extra_fields: Campos adicionais.

    Example:
        >>> log_database_operation(
        ...     operation="INSERT",
        ...     table="companies",
        ...     duration_ms=45.2,
        ...     rows_affected=1,
        ...     company_id="abc123"
        ... )
    """
    log_data = {
        'operation': operation,
        'table': table
    }

    if duration_ms is not None:
        log_data['duration_ms'] = duration_ms

    if rows_affected is not None:
        log_data['rows_affected'] = rows_affected

    # Adicionar campos extras
    log_data.update(extra_fields)

    logger.debug(
        f"DB operation: {operation} on {table}",
        extra=log_data
    )
