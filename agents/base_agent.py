"""
BaseAgent - Classe abstrata base para todos os agentes do sistema.

Fornece interface padronizada, logging, rate limiting e error handling.

Usage:
    class QualifierAgent(BaseAgent):
        def execute(self, companies, **kwargs):
            for company in companies:
                result = self._call_claude(prompt, model='fast')
                self._update_company(company['id'], result)
"""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from anthropic import Anthropic

from config.settings import settings
from database.supabase_client import db
from utils.logger import logger, log_api_call


class BaseAgent(ABC):
    """
    Classe base abstrata para agentes de IA.

    Attributes:
        agent_name: Nome do agente para logging.
        client: Cliente Anthropic configurado.

    Methods:
        execute: Executa a lógica principal do agente (abstrato).
        _call_claude: Chama Claude API com rate limiting e logging.
        _update_company: Atualiza dados de empresa no banco.
        _check_rate_limit: Verifica limites de API antes de chamar.
    """

    def __init__(self, agent_name: str) -> None:
        """
        Inicializa agente base.

        Args:
            agent_name: Nome identificador do agente.
        """
        self.agent_name = agent_name
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        logger.info(
            f"Agente inicializado: {agent_name}",
            extra={'agent': agent_name}
        )

    @abstractmethod
    def execute(
        self,
        companies: List[Dict[str, Any]],
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Executa a lógica principal do agente.

        Args:
            companies: Lista de empresas para processar.
            **kwargs: Parâmetros adicionais.

        Returns:
            Lista de resultados processados.
        """
        pass

    def _call_claude(
        self,
        prompt: str,
        model: str = 'fast',
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        max_retries: int = 3
    ) -> str:
        """
        Chama Claude API com retry, rate limiting e logging.

        Args:
            prompt: Mensagem do usuário.
            model: 'fast' (Haiku) ou 'quality' (Sonnet).
            system_prompt: Prompt de sistema opcional.
            max_tokens: Máximo de tokens na resposta.
            max_retries: Tentativas em caso de erro.

        Returns:
            Texto da resposta do Claude.

        Raises:
            Exception: Se falhar após todas as tentativas.

        Example:
            >>> response = self._call_claude("Analise esta escola", model='fast')
        """
        model_id = (
            settings.CLAUDE_MODEL_FAST if model == 'fast'
            else settings.CLAUDE_MODEL_QUALITY
        )

        messages = [{"role": "user", "content": prompt}]

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_id,
                    "max_tokens": max_tokens,
                    "messages": messages,
                }
                if system_prompt:
                    kwargs["system"] = system_prompt

                response = self.client.messages.create(**kwargs)

                elapsed_ms = (time.time() - start_time) * 1000

                log_api_call(
                    api_name='anthropic',
                    endpoint=model_id,
                    status_code=200,
                    response_time_ms=elapsed_ms
                )

                # Registra uso no banco
                db.insert_api_usage({
                    'api_name': 'anthropic',
                    'endpoint': model_id,
                    'credits_used': 1,
                    'success': True,
                    'response_time_ms': elapsed_ms,
                    'context': {'agent': self.agent_name}
                })

                return response.content[0].text

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                error_msg = str(e)

                logger.warning(
                    f"Claude API tentativa {attempt + 1}/{max_retries} falhou",
                    extra={
                        'agent': self.agent_name,
                        'model': model_id,
                        'attempt': attempt + 1,
                        'error': error_msg
                    }
                )

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    db.insert_api_usage({
                        'api_name': 'anthropic',
                        'endpoint': model_id,
                        'credits_used': 0,
                        'success': False,
                        'response_time_ms': elapsed_ms,
                        'error_message': error_msg,
                        'context': {'agent': self.agent_name}
                    })
                    raise

        raise Exception(f"Claude API falhou após {max_retries} tentativas")

    def _update_company(
        self,
        company_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Atualiza dados de empresa no banco.

        Args:
            company_id: UUID da empresa.
            updates: Campos a atualizar.

        Returns:
            Dados atualizados ou None.
        """
        try:
            result = db.update_company(company_id, updates)
            logger.debug(
                "Empresa atualizada pelo agente",
                extra={
                    'agent': self.agent_name,
                    'company_id': company_id,
                    'fields': list(updates.keys())
                }
            )
            return result
        except Exception as e:
            logger.error(
                "Falha ao atualizar empresa",
                extra={
                    'agent': self.agent_name,
                    'company_id': company_id,
                    'error': str(e)
                },
                exc_info=True
            )
            return None

    def _check_rate_limit(self, api_name: str) -> bool:
        """
        Verifica se API ainda tem créditos disponíveis no mês.

        Args:
            api_name: Nome da API (anthropic, apollo, snov, etc).

        Returns:
            True se pode usar, False se atingiu limite.
        """
        limits = settings.get_api_limits()
        limit = limits.get(api_name)

        if limit is None:
            return True

        used = db.count_api_usage_this_month(api_name)
        remaining = limit - used

        if remaining <= 0:
            logger.warning(
                f"Rate limit atingido para {api_name}",
                extra={
                    'api_name': api_name,
                    'used': used,
                    'limit': limit,
                    'agent': self.agent_name
                }
            )
            return False

        return True
