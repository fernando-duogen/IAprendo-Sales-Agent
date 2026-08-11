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

from config.settings import settings
from database.supabase_client import db
from utils.logger import logger, log_api_call

# LLM: OpenAI primary (configurado no projeto), Anthropic fallback
try:
    from openai import OpenAI as _OpenAI
except ImportError:
    _OpenAI = None
try:
    from anthropic import Anthropic as _Anthropic
except ImportError:
    _Anthropic = None


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

        # Determinar LLM disponivel: OpenAI primary, Anthropic fallback
        import os
        from dotenv import load_dotenv
        load_dotenv()
        self._openai_key = os.getenv("OPENAI_API_KEY", "")
        self._anthropic_key = settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY", "")
        self._openai_model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")

        if self._openai_key and _OpenAI:
            self._llm_backend = "openai"
            self._openai_client = _OpenAI(api_key=self._openai_key)
        elif self._anthropic_key and _Anthropic:
            self._llm_backend = "anthropic"
            self._anthropic_client = _Anthropic(api_key=self._anthropic_key)
        else:
            self._llm_backend = "none"
            logger.warning(f"Agent {agent_name}: nenhuma API key LLM disponivel")

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
        # Resolver model_id baseado no backend
        if self._llm_backend == "openai":
            model_id = self._openai_model
        elif self._llm_backend == "anthropic":
            model_id = (
                settings.CLAUDE_MODEL_FAST if model == 'fast'
                else settings.CLAUDE_MODEL_QUALITY
            )
        else:
            raise RuntimeError("Nenhuma API key LLM configurada (OpenAI ou Anthropic)")

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                if self._llm_backend == "openai":
                    msgs = []
                    if system_prompt:
                        msgs.append({"role": "system", "content": system_prompt})
                    msgs.append({"role": "user", "content": prompt})
                    resp = self._openai_client.chat.completions.create(
                        model=model_id,
                        messages=msgs,
                        max_tokens=max_tokens,
                        temperature=0.3,
                    )
                    response_text = resp.choices[0].message.content or ""
                else:
                    kwargs: Dict[str, Any] = {
                        "model": model_id,
                        "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                    if system_prompt:
                        kwargs["system"] = system_prompt
                    resp = self._anthropic_client.messages.create(**kwargs)
                    response_text = resp.content[0].text

                elapsed_ms = (time.time() - start_time) * 1000

                log_api_call(
                    api_name=self._llm_backend,
                    endpoint=model_id,
                    status_code=200,
                    response_time_ms=elapsed_ms
                )

                # Capturar tokens do response
                usage_data = {
                    'api_name': self._llm_backend,
                    'endpoint': model_id,
                    'credits_used': 1,
                    'success': True,
                    'response_time_ms': elapsed_ms,
                    'context': {'agent': self.agent_name},
                }
                try:
                    if self._llm_backend == "openai" and hasattr(resp, 'usage') and resp.usage:
                        usage_data['prompt_tokens'] = resp.usage.prompt_tokens
                        usage_data['completion_tokens'] = resp.usage.completion_tokens
                        usage_data['total_tokens'] = resp.usage.total_tokens
                        usage_data['model'] = model_id
                        # Custo por modelo (USD por 1M tokens)
                        pricing = {"gpt-4.1-mini": {"in": 0.40, "out": 1.60}, "gpt-4.1": {"in": 2.00, "out": 8.00}}
                        p = pricing.get(model_id, {"in": 0.40, "out": 1.60})
                        cost = (resp.usage.prompt_tokens * p["in"] + resp.usage.completion_tokens * p["out"]) / 1_000_000
                        usage_data['cost_usd'] = round(cost, 6)
                except Exception:
                    pass
                db.insert_api_usage(usage_data)

                return response_text

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                error_msg = str(e)

                logger.warning(
                    f"LLM API tentativa {attempt + 1}/{max_retries} falhou",
                    extra={
                        'agent': self.agent_name,
                        'model': model_id,
                        'backend': self._llm_backend,
                        'attempt': attempt + 1,
                        'error': error_msg
                    }
                )

                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    db.insert_api_usage({
                        'api_name': self._llm_backend,
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
            # Coluna ainda nao existe (migration pendente)? Reenvia SEM os
            # campos novos em vez de perder a atualizacao inteira. Assim um
            # deploy de codigo nunca fica bloqueado esperando a migration.
            _msg = str(e)
            if "PGRST204" in _msg or "column" in _msg.lower():
                _opcionais = {"google_rating", "google_reviews_count", "google_maps_url"}
                _reduzido = {k: v for k, v in updates.items() if k not in _opcionais}
                if _reduzido and len(_reduzido) < len(updates):
                    try:
                        result = db.update_company(company_id, _reduzido)
                        logger.warning(
                            "Update sem campos opcionais (migration pendente?)",
                            extra={
                                'agent': self.agent_name,
                                'company_id': company_id,
                                'ignorados': sorted(set(updates) - set(_reduzido)),
                            }
                        )
                        return result
                    except Exception:
                        pass
            logger.error(
                "Falha ao atualizar empresa",
                extra={
                    'agent': self.agent_name,
                    'company_id': company_id,
                    'error': _msg
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
