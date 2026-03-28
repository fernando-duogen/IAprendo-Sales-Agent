"""
Database Package - Camada de acesso a dados.

Este pacote fornece acesso ao banco de dados Supabase (PostgreSQL):
- schemas.sql: DDL das 7 tabelas
- supabase_client: Cliente CRUD com rate limiting
"""

from .supabase_client import Database, db

__all__ = ['Database', 'db']
