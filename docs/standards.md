# 📐 STANDARDS.md - Padrões de Código

> Regras obrigatórias para todo o código do projeto

---

## 📖 Índice

1. [Convenções de Código](#-convenções-de-código)
2. [Type Hints Obrigatórios](#-type-hints-obrigatórios)
3. [Error Handling](#-error-handling)
4. [Logging Estruturado](#-logging-estruturado)
5. [Configuration Management](#-configuration-management)
6. [Database Access](#-database-access)
7. [API Integration Patterns](#-api-integration-patterns)
8. [Approval Flow](#-approval-flow)
9. [Testing Requirements](#-testing-requirements)

---

## 📝 Convenções de Código

### Nomenclatura
```python
# Arquivos e módulos
snake_case.py                    # filterer.py, contact_finder.py

# Classes
PascalCase                       # QualifierAgent, HubSpotClient

# Funções e variáveis
snake_case                       # qualify_school(), target_city

# Constantes
UPPER_SNAKE_CASE                 # MAX_RETRIES, API_TIMEOUT

# Privado (interno)
_prefixed_with_underscore        # _internal_method()
```

### Estrutura de Arquivo
```python
"""
Module docstring - O que este módulo faz

Descrição mais detalhada se necessário.
Exemplos de uso se aplicável.
"""

# 1. Imports padrão
import os
import sys
from typing import Dict, List, Optional

# 2. Imports terceiros
import pandas as pd
from anthropic import Anthropic

# 3. Imports locais
from config.settings import settings
from utils.logger import logger

# 4. Constantes do módulo
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

# 5. Classes e funções
class MyClass:
    """Class docstring"""
    pass

def my_function():
    """Function docstring"""
    pass

# 6. Entry point (se aplicável)
if __name__ == "__main__":
    main()
```

### Tamanho e Organização
```python
# Funções: máximo 50 linhas
# Se maior, dividir em funções menores

# Classes: máximo 300 linhas
# Se maior, dividir em múltiplas classes

# Arquivos: máximo 500 linhas
# Se maior, dividir em múltiplos arquivos

# Imports: agrupar e organizar
# Standard lib → Third party → Local
```

---

## 🔤 Type Hints Obrigatórios

### Regra: TODAS as funções públicas devem ter type hints
```python
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime

# ✅ CORRETO - Type hints completos
def qualify_school(
    self,
    school: Dict[str, Any],
    threshold: int = 60
) -> Dict[str, Union[int, str, List[str]]]:
    """
    Qualifica escola usando IA Claude
    
    Args:
        school: Dicionário com dados da escola
            Campos esperados: id, name, education_levels
        threshold: Score mínimo para qualificação (default: 60)
    
    Returns:
        Dict com resultado da qualificação:
            {
                'score': int (0-100),
                'priority': str ('baixa'|'media'|'alta'),
                'reasoning': str,
                'estimated_size': str,
                'innovation_signals': List[str]
            }
    
    Raises:
        ValueError: Se school não tiver campos obrigatórios
        APIError: Se Claude API falhar após retries
    
    Example:
        >>> school = {'id': '123', 'name': 'Colégio X', ...}
        >>> result = agent.qualify_school(school)
        >>> print(result['score'])
        85
    """
    pass


# ✅ CORRETO - Função com Optional e Union
def find_email(
    self,
    domain: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None
) -> Optional[str]:
    """Retorna email ou None se não encontrar"""
    pass


# ✅ CORRETO - Múltiplos retornos
def geocode_address(
    address: str,
    city: str,
    state: str
) -> Optional[Tuple[float, float]]:
    """
    Retorna (latitude, longitude) ou None
    """
    pass


# ✅ CORRETO - Função sem retorno
def update_database(company_id: str, data: Dict[str, Any]) -> None:
    """Atualiza dados no banco (sem retorno)"""
    pass


# ❌ ERRADO - Sem type hints
def process_data(school):
    """Não tem type hints - PROIBIDO"""
    pass
```

### Type Hints Comuns
```python
from typing import (
    Dict,           # Dicionários
    List,           # Listas
    Optional,       # Pode ser None
    Union,          # Múltiplos tipos possíveis
    Any,            # Qualquer tipo (usar com moderação)
    Tuple,          # Tuplas
    Callable,       # Funções como parâmetros
    TypedDict,      # Dicts com estrutura definida
)

# Exemplos práticos
company_data: Dict[str, Any]                    # Qualquer estrutura
education_levels: List[str]                     # Lista de strings
phone: Optional[str]                            # String ou None
score: Union[int, float]                        # Int ou float
coords: Tuple[float, float]                     # Tupla (lat, lng)
callback: Callable[[str], bool]                 # Função que recebe str e retorna bool
```

---

## 🛡️ Error Handling

### Regra: SEMPRE usar try/except em operações externas
```python
import time
from typing import Optional, Dict, Any

# ✅ CORRETO - Error handling completo
def call_external_api(
    endpoint: str,
    max_retries: int = 3
) -> Optional[Dict[str, Any]]:
    """
    Chama API externa com retry logic robusto
    """
    
    for attempt in range(max_retries):
        try:
            # Tentativa de chamada
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.Timeout:
            logger.warning(
                f"Timeout na tentativa {attempt + 1}/{max_retries}",
                extra={'endpoint': endpoint, 'attempt': attempt + 1}
            )
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                time.sleep(wait_time)
                continue
            else:
                logger.error(
                    f"Falha após {max_retries} tentativas",
                    extra={'endpoint': endpoint}
                )
                raise APITimeoutError(f"API {endpoint} não respondeu")
        
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            
            if status_code == 429:  # Rate limit
                logger.warning("Rate limited, aguardando 60s")
                time.sleep(60)
                continue
            
            elif status_code >= 500:  # Server error - retenta
                logger.error(f"Erro servidor: {status_code}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                else:
                    raise
            
            else:  # Client error (4xx) - não retenta
                logger.error(
                    f"Erro cliente: {status_code}",
                    extra={'response': e.response.text}
                )
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                return None
        
        except Exception as e:
            # Catch-all para erros inesperados
            logger.critical(
                f"Erro inesperado: {type(e).__name__}: {e}",
                exc_info=True  # Inclui stack trace
            )
            return None
    
    return None


# ✅ CORRETO - Exceções customizadas
class APIError(Exception):
    """Erro base de API"""
    pass

class APITimeoutError(APIError):
    """API não respondeu a tempo"""
    pass

class RateLimitError(APIError):
    """Rate limit atingido"""
    pass


# ✅ CORRETO - Uso com fallback
def get_company_data(domain: str) -> Dict[str, Any]:
    """Tenta múltiplas fontes com fallback"""
    
    # Tenta fonte 1
    try:
        data = apollo_api.get_company(domain)
        if data:
            return data
    except APIError as e:
        logger.warning(f"Apollo falhou: {e}")
    
    # Tenta fonte 2
    try:
        data = snov_api.get_company(domain)
        if data:
            return data
    except APIError as e:
        logger.warning(f"Snov falhou: {e}")
    
    # Fallback gratuito
    try:
        data = web_scraper.get_company(domain)
        return data
    except Exception as e:
        logger.error(f"Scraping falhou: {e}")
        return {}  # Retorna vazio como último recurso
```

### Hierarquia de Exceções
```python
# Criar hierarquia clara
class IAvendaException(Exception):
    """Exceção base do projeto"""
    pass

class DatabaseError(IAvendaException):
    """Erros de banco de dados"""
    pass

class APIError(IAvendaException):
    """Erros de APIs externas"""
    pass

class ValidationError(IAvendaException):
    """Erros de validação de dados"""
    pass

# Uso
try:
    process_data()
except ValidationError as e:
    logger.warning(f"Dados inválidos: {e}")
    return None
except DatabaseError as e:
    logger.error(f"Erro no banco: {e}")
    raise  # Re-raise erros críticos
except IAvendaException as e:
    logger.error(f"Erro conhecido: {e}")
    handle_error(e)
```

---

## 📊 Logging Estruturado

### Regra: Logs sempre em formato JSON com contexto
```python
import logging
from pythonjsonlogger import jsonlogger

# Setup logger (utils/logger.py)
def setup_logger(name: str) -> logging.Logger:
    """
    Configura logger estruturado com JSON
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Handler para arquivo
    file_handler = logging.FileHandler('logs/application.log')
    
    # Formatter JSON
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        timestamp=True
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler para console (desenvolvimento)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger


# ✅ CORRETO - Uso com contexto
class QualifierAgent:
    def __init__(self):
        self.logger = setup_logger("QualifierAgent")
    
    def qualify_school(self, school: Dict) -> Dict:
        # Log início com contexto
        self.logger.info(
            "Iniciando qualificação",
            extra={
                'school_id': school['id'],
                'school_name': school['name'],
                'agent': 'QualifierAgent',
                'action': 'qualify_start',
                'education_levels': school.get('education_levels', [])
            }
        )
        
        try:
            result = self._call_claude(school)
            
            # Log sucesso com resultado
            self.logger.info(
                "Qualificação concluída",
                extra={
                    'school_id': school['id'],
                    'score': result['score'],
                    'priority': result['priority'],
                    'agent': 'QualifierAgent',
                    'action': 'qualify_success',
                    'duration_ms': 1234  # Tempo de execução
                }
            )
            
            return result
        
        except Exception as e:
            # Log erro com contexto completo
            self.logger.error(
                "Falha na qualificação",
                extra={
                    'school_id': school['id'],
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                    'agent': 'QualifierAgent',
                    'action': 'qualify_error'
                },
                exc_info=True  # Stack trace
            )
            raise


# Níveis de log
logger.debug("Informação detalhada para debug")      # Desenvolvimento
logger.info("Operação normal")                       # Produção
logger.warning("Algo inesperado mas recuperável")    # Atenção
logger.error("Erro que precisa investigação")        # Problema
logger.critical("Sistema em risco")                  # Emergência
```

### Logs Estruturados Permitem
```bash
# Busca eficiente
grep '"action": "qualify_success"' logs/application.log

# Métricas
cat logs/application.log | jq 'select(.action == "qualify_success") | .score' | avg

# Alertas
tail -f logs/application.log | jq 'select(.levelname == "ERROR")'

# Debugging
cat logs/application.log | jq 'select(.school_id == "12345")'
```

---

## ⚙️ Configuration Management

### Regra: NUNCA hardcode - tudo via settings.py
```python
# config/settings.py
import os
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    Configurações centralizadas do sistema
    Lê de .env - NUNCA valores default reais
    """
    
    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # HubSpot
    HUBSPOT_API_KEY: str = os.getenv("HUBSPOT_API_KEY", "")
    HUBSPOT_PORTAL_ID: str = os.getenv("HUBSPOT_PORTAL_ID", "")
    
    # Email
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "none")
    EMAIL_FROM: str = os.getenv("YOUR_EMAIL", "")
    EMAIL_FROM_NAME: str = os.getenv("YOUR_NAME", "")
    
    # CSV
    CSV_PATH: str = os.getenv("CSV_PATH", "data/raw/escolas_brasil.csv")
    CSV_COL_NAME: str = os.getenv("CSV_COL_NAME", "Escola")
    CSV_COL_INEP: str = os.getenv("CSV_COL_INEP", "Código INEP")
    CSV_COL_CITY: str = os.getenv("CSV_COL_CITY", "Município")
    CSV_COL_STATE: str = os.getenv("CSV_COL_STATE", "UF")
    CSV_COL_RESTRICTION: str = os.getenv("CSV_COL_RESTRICTION", "Restrição de Atendimento")
    CSV_COL_LEVELS: str = os.getenv("CSV_COL_LEVELS", "Etapas e Modalidade de Ensino Oferecidas")
    
    # ICP
    TARGET_CITY: str = os.getenv("TARGET_CITY", "Porto Alegre")
    TARGET_STATE: str = os.getenv("TARGET_STATE", "RS")
    TARGET_SCHOOL_TYPES: List[str] = os.getenv("TARGET_SCHOOL_TYPES", "publica,privada").split(",")
    TARGET_EDUCATION_LEVELS: List[str] = os.getenv("TARGET_EDUCATION_LEVELS", "fundamental,medio").split(",")
    
    # Limites
    TARGET_LEADS_PER_WEEK: int = int(os.getenv("TARGET_LEADS_PER_WEEK", "10"))
    MAX_DAILY_EMAILS: int = int(os.getenv("MAX_DAILY_EMAILS", "20"))
    
    # APIs Limites
    APOLLO_MONTHLY_LIMIT: int = int(os.getenv("APOLLO_MONTHLY_LIMIT", "60"))
    SNOV_MONTHLY_LIMIT: int = int(os.getenv("SNOV_MONTHLY_LIMIT", "50"))
    HUNTER_MONTHLY_LIMIT: int = int(os.getenv("HUNTER_MONTHLY_LIMIT", "25"))
    
    # Features
    ENABLE_GEOCODING: bool = os.getenv("ENABLE_GEOCODING", "true").lower() == "true"
    ENABLE_PHONE_SEARCH: bool = os.getenv("ENABLE_PHONE_SEARCH", "true").lower() == "true"
    
    # Sistema
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    @classmethod
    def validate(cls) -> bool:
        """
        Valida configurações essenciais
        """
        required = [
            'ANTHROPIC_API_KEY',
            'SUPABASE_URL',
            'SUPABASE_KEY',
            'EMAIL_FROM',
            'CSV_PATH'
        ]
        
        missing = [key for key in required if not getattr(cls, key)]
        
        if missing:
            raise ValueError(f"Configurações faltando: {', '.join(missing)}")
        
        return True
    
    @classmethod
    def get_email_config(cls) -> Dict[str, Any]:
        """
        Retorna configuração de email baseada no provider
        """
        if cls.EMAIL_PROVIDER == "brevo":
            return {
                'provider': 'brevo',
                'api_key': os.getenv("BREVO_API_KEY", ""),
                'from_email': cls.EMAIL_FROM,
                'from_name': cls.EMAIL_FROM_NAME
            }
        elif cls.EMAIL_PROVIDER == "gmail":
            return {
                'provider': 'gmail',
                'credentials_path': os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
                'from_email': cls.EMAIL_FROM
            }
        else:
            raise ValueError(f"Email provider '{cls.EMAIL_PROVIDER}' não configurado")

# Instância global
settings = Settings()


# ✅ CORRETO - Uso no código
def send_email(to: str, subject: str, body: str):
    """Envia email usando configuração"""
    
    email_config = settings.get_email_config()
    
    if email_config['provider'] == 'brevo':
        brevo_client = BrevoAPI(email_config['api_key'])
        brevo_client.send(
            from_email=email_config['from_email'],
            from_name=email_config['from_name'],
            to_email=to,
            subject=subject,
            body=body
        )


# ❌ ERRADO - Hardcode
def send_email_wrong(to: str, subject: str, body: str):
    """PROIBIDO - valores hardcoded"""
    brevo_client = BrevoAPI("xkeysib-...")  # MAL!
    brevo_client.send(
        from_email="fernando@iaprendo.com.br",  # MAL!
        to_email=to,
        subject=subject,
        body=body
    )
```

---

## 🗄️ Database Access

### Regra: SEMPRE via cliente, NUNCA SQL direto
```python
# database/supabase_client.py
from supabase import create_client, Client
from typing import List, Dict, Optional
from config.settings import settings
from utils.logger import logger

class Database:
    """
    Cliente centralizado para operações de banco
    """
    
    def __init__(self):
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    
    # ✅ CORRETO - Métodos tipados
    def get_companies_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Busca empresas por status
        """
        try:
            result = self.client.table("companies")\
                .select("*")\
                .eq("status", status)\
                .limit(limit)\
                .execute()
            
            return result.data
        
        except Exception as e:
            logger.error(f"Erro ao buscar companies: {e}")
            return []
    
    def get_company_by_inep(self, inep_code: str) -> Optional[Dict]:
        """
        Busca escola por código INEP (chave única)
        """
        try:
            result = self.client.table("companies")\
                .select("*")\
                .eq("inep_code", inep_code)\
                .execute()
            
            return result.data[0] if result.data else None
        
        except Exception as e:
            logger.error(f"Erro ao buscar INEP {inep_code}: {e}")
            return None
    
    def update_company(
        self,
        company_id: str,
        updates: Dict
    ) -> Optional[Dict]:
        """
        Atualiza dados de uma empresa
        """
        try:
            # Adiciona timestamp
            updates['updated_at'] = 'now()'
            
            result = self.client.table("companies")\
                .update(updates)\
                .eq("id", company_id)\
                .execute()
            
            return result.data[0] if result.data else None
        
        except Exception as e:
            logger.error(f"Erro ao atualizar {company_id}: {e}")
            return None
    
    def insert_company(self, company_data: Dict) -> Optional[str]:
        """
        Insere nova empresa
        Verifica duplicata por INEP
        """
        try:
            # Verifica se já existe
            if 'inep_code' in company_data:
                existing = self.get_company_by_inep(company_data['inep_code'])
                if existing:
                    logger.warning(
                        f"Escola com INEP {company_data['inep_code']} já existe",
                        extra={'existing_id': existing['id']}
                    )
                    return existing['id']
            
            # Insere
            result = self.client.table("companies")\
                .insert(company_data)\
                .execute()
            
            return result.data[0]['id'] if result.data else None
        
        except Exception as e:
            logger.error(f"Erro ao inserir empresa: {e}")
            return None

# Instância global
db = Database()


# ✅ CORRETO - Uso no código
def import_school(school_data: Dict):
    """Importa escola do CSV"""
    
    # Tenta inserir
    company_id = db.insert_company({
        'name': school_data['Escola'],
        'inep_code': school_data['Código INEP'],
        'city': school_data['Município'],
        'state': school_data['UF'],
        'status': 'filtered'
    })
    
    if company_id:
        logger.info(f"Escola importada: {company_id}")
    else:
        logger.error("Falha ao importar escola")


# ❌ ERRADO - SQL direto
def import_school_wrong(school_data: Dict):
    """PROIBIDO - SQL direto"""
    db.client.execute(
        "INSERT INTO companies (name, city) VALUES (%s, %s)",
        (school_data['Escola'], school_data['Município'])
    )
```

---

## 🔌 API Integration Patterns

### Rate Limiting (Persistente via Banco)
```python
import time
from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, List

def rate_limit(api_name: str, calls: int, period: str):
    """
    Decorator para rate limiting PERSISTENTE via tabela api_usage.
    
    Importante: O rate limiting em memória não sobrevive a restarts,
    o que pode causar estouro de créditos mensais. Este decorator
    consulta a tabela api_usage para controle real.
    
    Args:
        api_name: Nome da API (ex: 'apollo', 'hunter', 'snov')
        calls: Número de chamadas permitidas
        period: "minute", "hour", "day", "month"
    
    Example:
        @rate_limit(api_name="apollo", calls=60, period="month")
        def call_apollo():
            ...
    """
    
    period_seconds = {
        'minute': 60,
        'hour': 3600,
        'day': 86400,
        'month': 2592000
    }
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from database.supabase_client import db
            
            # Consulta uso real no banco (sobrevive a restarts)
            cutoff = datetime.now() - timedelta(seconds=period_seconds[period])
            used = db.count_api_usage_since(api_name, cutoff)
            
            if used >= calls:
                raise RateLimitError(
                    f"Rate limit: {api_name} atingiu {calls}/{period}. "
                    f"Já usou {used} créditos."
                )
            
            # Executa a função
            result = func(*args, **kwargs)
            
            # Registra uso no banco
            db.insert_api_usage({
                'api_name': api_name,
                'endpoint': func.__name__,
                'credits_used': 1,
                'success': result is not None,
                'created_at': datetime.now().isoformat()
            })
            
            return result
        
        return wrapper
    return decorator


# ✅ CORRETO - Uso com rate limiting persistente
class ApolloAPI:
    @rate_limit(api_name="apollo", calls=60, period="month")
    def find_contacts(self, domain: str) -> List[Dict]:
        """
        Busca contatos (60 chamadas/mês grátis)
        """
        # Lógica da API
        pass
```

### Graceful Fallbacks
```python
from typing import Optional, Tuple

class EnrichmentService:
    """
    Serviço com fallbacks em cascata
    """
    
    def find_email(
        self,
        company: Dict,
        contact_name: str
    ) -> Optional[str]:
        """
        Tenta múltiplas fontes automaticamente
        """
        
        strategies = [
            ('apollo', lambda: self._try_apollo(company, contact_name)),
            ('snov', lambda: self._try_snov(company, contact_name)),
            ('hunter', lambda: self._try_hunter(company, contact_name)),
            ('scraper', lambda: self._try_scraper(company.get('website')))
        ]
        
        for source, strategy in strategies:
            try:
                logger.info(f"Tentando {source} para {company['name']}")
                
                email = strategy()
                
                if email:
                    logger.info(f"✅ Email encontrado via {source}")
                    
                    # Registra sucesso
                    db.insert_api_usage({
                        'api_name': source,
                        'company_id': company['id'],
                        'success': True,
                        'credits_used': 1
                    })
                    
                    return email
            
            except RateLimitError:
                logger.warning(f"{source} rate limited, próximo...")
                continue
            
            except Exception as e:
                logger.error(f"Erro em {source}: {e}")
                continue
        
        logger.warning(f"Email não encontrado para {company['name']}")
        return None
```

---

## ✅ Approval Flow

### REGRA CRÍTICA: NUNCA Bypass
```python
# ❌ PROIBIDO - Envio direto
def send_message_direct(contact: Dict, message: str):
    """NUNCA FAÇA ISSO"""
    brevo.send_email(contact['email'], message)  # PROIBIDO!


# ✅ CORRETO - Via approval queue
def prepare_message(
    company: Dict,
    contact: Dict,
    message_data: Dict
) -> None:
    """Adiciona à fila de aprovação"""
    
    approval_queue.add_to_queue({
        'company_id': company['id'],
        'contact_id': contact['id'],
        'channel': 'email',
        'subject': message_data['subject'],
        'message': message_data['body'],
        'ai_reasoning': message_data['reasoning'],
        'status': 'pending_approval',  # AGUARDA HUMANO
        'created_at': datetime.now()
    })
    
    logger.info(
        "Mensagem adicionada à fila",
        extra={
            'company_id': company['id'],
            'contact_id': contact['id'],
            'channel': 'email'
        }
    )


# ✅ CORRETO - Envio apenas de aprovados
def send_approved_messages() -> int:
    """Envia APENAS mensagens já aprovadas"""
    
    # Busca aprovados
    approved = db.client.table('approval_queue')\
        .select('*')\
        .eq('status', 'approved')\
        .is_('sent_at', 'null')\
        .execute()
    
    sent_count = 0
    
    for item in approved.data:
        try:
            # Envia
            if item['channel'] == 'email':
                brevo.send_email(
                    to=item['contact']['email'],
                    subject=item['subject'],
                    body=item['message']
                )
            
            # Atualiza status
            db.client.table('approval_queue')\
                .update({
                    'status': 'sent',
                    'sent_at': 'now()'
                })\
                .eq('id', item['id'])\
                .execute()
            
            # Registra interação
            db.insert_interaction({
                'company_id': item['company_id'],
                'contact_id': item['contact_id'],
                'channel': item['channel'],
                'interaction_type': 'first_contact',
                'message': item['message'],
                'status': 'sent'
            })
            
            sent_count += 1
        
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem {item['id']}: {e}")
    
    return sent_count
```

---

## 🧪 Testing Requirements

### Unit Tests - Agents
```python
# tests/test_agents.py
import pytest
from agents.qualifier import QualifierAgent
from unittest.mock import Mock, patch

@pytest.fixture
def qualifier():
    return QualifierAgent()

@pytest.fixture
def sample_school():
    return {
        'id': 'test-123',
        'name': 'Colégio Farroupilha',
        'address': 'Rua X, Três Figueiras',
        'city': 'Porto Alegre',
        'state': 'RS',
        'education_levels': ['fundamental_2', 'medio'],
        'school_type': 'privada',
        'school_size': 'grande'
    }

def test_qualifier_returns_valid_score(qualifier, sample_school):
    """Testa se retorna score válido"""
    result = qualifier.qualify_school(sample_school)
    
    assert 'score' in result
    assert isinstance(result['score'], int)
    assert 0 <= result['score'] <= 100

def test_qualifier_assigns_priority(qualifier, sample_school):
    """Testa atribuição de prioridade"""
    result = qualifier.qualify_school(sample_school)
    
    assert 'priority' in result
    assert result['priority'] in ['baixa', 'media', 'alta']

@patch('agents.qualifier.Anthropic')
def test_qualifier_handles_api_error(mock_anthropic, qualifier, sample_school):
    """Testa tratamento de erro da API"""
    mock_anthropic.return_value.messages.create.side_effect = Exception("API Error")
    
    with pytest.raises(Exception):
        qualifier.qualify_school(sample_school)
```

### Integration Tests
```python
# tests/test_integrations.py
import pytest
from integrations.hubspot_client import HubSpotClient
from config.settings import settings

@pytest.mark.integration
@pytest.mark.skipif(
    not settings.HUBSPOT_API_KEY,
    reason="HubSpot não configurado"
)
def test_hubspot_create_contact():
    """Testa criação no HubSpot"""
    hubspot = HubSpotClient()
    
    test_contact = {
        'email': 'test@example.com',
        'first_name': 'Teste',
        'last_name': 'Integração'
    }
    
    contact_id = hubspot.create_or_update_contact(test_contact)
    assert contact_id is not None
    
    # Cleanup
    hubspot.client.crm.contacts.basic_api.archive(contact_id)
```

---

**Para arquitetura do sistema**: Veja `ARCHITECTURE.md`  
**Para detalhes de implementação**: Veja `IMPLEMENTATION.md`