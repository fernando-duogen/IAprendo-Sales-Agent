"""
Database Migrations - Scripts de setup e importação do banco de dados.

Este módulo contém migrations que devem ser executadas em ordem numérica:

    001_setup_database.py    - Cria estrutura do banco (7 tabelas, índices, triggers)
    002_import_schools.py    - Importa CSV do MEC com filtros ICP

Usage:
    # Executar em ordem
    python database/migrations/001_setup_database.py
    python database/migrations/002_import_schools.py --sample 100

Importante:
    - 001 DEVE ser executado antes de 002
    - Sempre teste 002 com --sample primeiro
    - Migrations são idempotentes (podem ser re-executadas)
"""

__version__ = "1.0.0"
__all__ = []
