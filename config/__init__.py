"""
Config Package - Sistema de configuração centralizado.

Este pacote fornece acesso centralizado a todas as configurações do sistema
através do módulo settings.py (fonte única de verdade).
"""

from .settings import settings

__all__ = ['settings']
