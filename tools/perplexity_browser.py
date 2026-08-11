# -*- coding: utf-8 -*-
"""APOSENTADO (Ago/2026) — shim de compatibilidade que redireciona p/ web_search.

O modulo original automatizava o Chrome (Playwright, headless=False) contra
perplexity.ai usando a assinatura Pro logada. Foi aposentado porque:

  1. NAO rodava na VM Oracle (producao): sem Chrome e sem ambiente grafico.
  2. Custava a mensalidade do Perplexity Pro (~US$20/mes) para 4 usos em
     4 meses — a assinatura foi CANCELADA pelo dono em Ago/2026.
  3. Levava 45-75s por consulta (a busca web via API leva ~4s).

Como a assinatura nao existe mais, chamar o navegador agora pararia na tela de
login e travaria ate 2 minutos. Por isso este shim: qualquer caminho legado
continua funcionando, mas atendido por `tools/web_search.py` (OpenAI Responses
API + ferramenta web_search) — que e API pura, roda em qualquer ambiente e
custa ~US$0.004 por escola.

O codigo original esta no historico do git (commit anterior a este).
"""
from typing import Any, Dict, List, Optional

from utils.logger import logger

_AVISADO = False


def _avisar_uma_vez() -> None:
    global _AVISADO
    if not _AVISADO:
        logger.info(
            "perplexity_browser esta APOSENTADO — redirecionando para "
            "tools/web_search (OpenAI web_search). Atualize a chamada."
        )
        _AVISADO = True


class _PerplexityBrowserShim:
    """Mantem a interface publica antiga, atendida pela busca web via API."""

    def is_available(self) -> bool:
        _avisar_uma_vez()
        from tools import web_search
        return web_search.is_available()

    def _query_perplexity_text(self, prompt: str, timeout_seconds: int = 60) -> str:
        _avisar_uma_vez()
        from tools import web_search
        return web_search.search_text(prompt, timeout_seconds=timeout_seconds)

    def search_school_contacts(
        self, name: str, city: str, state: str, timeout_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        _avisar_uma_vez()
        from tools import web_search
        return web_search.search_school_contacts(
            name, city, state, timeout_seconds=timeout_seconds
        )

    def search_school_address(
        self, name: str, city: str, state: str
    ) -> Optional[str]:
        _avisar_uma_vez()
        from tools import web_search
        return web_search.search_school_address(name, city, state)

    def _close(self) -> None:
        return None


perplexity_browser = _PerplexityBrowserShim()
