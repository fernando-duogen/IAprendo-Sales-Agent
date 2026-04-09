"""
Settings - Configurações centralizadas do sistema.

Este módulo é a FONTE ÚNICA DE VERDADE para todas as configurações.
Carrega ~50 variáveis de ambiente do arquivo .env e fornece validação robusta.

Princípio: Configuration Over Convention (Zero Hardcode)

Usage:
    from config.settings import settings

    # Acessar configurações
    email = settings.YOUR_EMAIL
    api_key = settings.ANTHROPIC_API_KEY

    # Validar configuração
    settings.validate_required()

    # Verificar features opcionais
    features = settings.validate_optional()
"""

import os
from typing import List, Dict, Any

# =====================================================================
# ORDEM CRITICA: Streamlit secrets PRIMEIRO, depois .env
# No Streamlit Cloud nao existe .env, entao os secrets sao a unica fonte.
# Os secrets devem ser copiados para os.environ ANTES de load_dotenv e
# ANTES da classe Settings ser definida (atributos de classe sao avaliados
# no momento da definicao via os.getenv).
# =====================================================================

# Passo 1: Streamlit Cloud secrets → os.environ
try:
    import streamlit as st
    for key, value in st.secrets.items():
        if isinstance(value, str):
            os.environ[key] = value
except Exception:
    pass  # Nao esta rodando no Streamlit ou sem secrets

# Passo 2: .env local (nao sobrescreve o que ja veio dos secrets)
from dotenv import load_dotenv
load_dotenv(override=False)


class Settings:
    """
    Configurações do sistema (fonte única de verdade).

    Todas as configurações são carregadas de variáveis de ambiente (.env).
    NUNCA use valores hardcoded fora desta classe.

    Attributes:
        Organizadas em 11 grupos:
        - NEGÓCIO (5 variáveis)
        - CSV (14 variáveis)
        - ICP (6 variáveis)
        - FEATURES (3 booleanas)
        - ANTHROPIC (3 variáveis)
        - SUPABASE (2 variáveis)
        - HUBSPOT (2 variáveis)
        - EMAIL (3+ variáveis)
        - GOOGLE MAPS (1 variável)
        - ENRIQUECIMENTO (6 variáveis)
        - WHATSAPP (1 variável)
        - SISTEMA (3 variáveis)
    """

    # ========================================================================
    # NEGÓCIO (5 variáveis)
    # ========================================================================
    COMPANY_NAME: str = os.getenv("COMPANY_NAME", "")
    YOUR_NAME: str = os.getenv("YOUR_NAME", "")
    YOUR_EMAIL: str = os.getenv("YOUR_EMAIL", "")
    YOUR_PHONE: str = os.getenv("YOUR_PHONE", "")
    WEBSITE: str = os.getenv("WEBSITE", "")

    # ========================================================================
    # CSV - Mapeamento de Colunas (14 variáveis)
    # ========================================================================
    # Nova base MEC 2025 (escolas_brasil_crm.csv — 180k escolas, 77 colunas)
    CSV_PATH: str = os.getenv("CSV_PATH", "data/raw/escolas_brasil_crm.csv")
    CSV_ENCODING: str = os.getenv("CSV_ENCODING", "utf-8-sig")

    # Mapeamento de colunas — Nova base MEC 2025
    CSV_COL_NAME: str = os.getenv("CSV_COL_NAME", "NOME_ESCOLA")
    CSV_COL_INEP: str = os.getenv("CSV_COL_INEP", "CODIGO_INEP")
    CSV_COL_CITY: str = os.getenv("CSV_COL_CITY", "MUNICIPIO")
    CSV_COL_STATE: str = os.getenv("CSV_COL_STATE", "UF")
    CSV_COL_ADDRESS: str = os.getenv("CSV_COL_ADDRESS", "ENDERECO")
    CSV_COL_PHONE: str = os.getenv("CSV_COL_PHONE", "TELEFONE")
    CSV_COL_RESTRICTION: str = os.getenv("CSV_COL_RESTRICTION", "")  # Nova base ja filtrada (so ativas)
    CSV_COL_LEVELS: str = os.getenv("CSV_COL_LEVELS", "PERFIL_ENSINO")
    CSV_COL_ADMIN_CATEGORY: str = os.getenv("CSV_COL_ADMIN_CATEGORY", "DEPENDENCIA")
    CSV_COL_ADMIN_DEPENDENCY: str = os.getenv("CSV_COL_ADMIN_DEPENDENCY", "DEPENDENCIA")
    CSV_COL_LATITUDE: str = os.getenv("CSV_COL_LATITUDE", "LATITUDE")
    CSV_COL_LONGITUDE: str = os.getenv("CSV_COL_LONGITUDE", "LONGITUDE")
    CSV_COL_SIZE: str = os.getenv("CSV_COL_SIZE", "PORTE_ESCOLA")

    # Colunas extras da nova base (para busca avançada)
    CSV_COL_REGIAO: str = "REGIAO"
    CSV_COL_NIVEL_TECH: str = "NIVEL_TECNOLOGICO"
    CSV_COL_TOTAL_MATRICULAS: str = "TOTAL_MATRICULAS"
    CSV_COL_PERFIL_ENSINO: str = "PERFIL_ENSINO"
    CSV_COL_LOCALIZACAO: str = "LOCALIZACAO"

    # ========================================================================
    # ICP - Perfil de Cliente Ideal (6 variáveis)
    # ========================================================================
    # Suporta multiplas cidades/estados separados por virgula.
    # Ex: "Porto Alegre,Canoas" ou vazio para sem filtro.
    TARGET_CITY: str = os.getenv("TARGET_CITY", "Porto Alegre")
    TARGET_STATE: str = os.getenv("TARGET_STATE", "RS")

    @property
    def TARGET_SCHOOL_TYPES(self) -> List[str]:
        """
        Tipos de escola alvo (ex: ['publica', 'privada']).

        Returns:
            Lista de tipos de escola.
        """
        types_str = os.getenv("TARGET_SCHOOL_TYPES", "publica,privada")
        return [t.strip() for t in types_str.split(",") if t.strip()]

    @property
    def TARGET_EDUCATION_LEVELS(self) -> List[str]:
        """
        Níveis de ensino alvo (ex: ['fundamental', 'medio']).

        Returns:
            Lista de níveis de ensino.
        """
        levels_str = os.getenv("TARGET_EDUCATION_LEVELS", "fundamental,medio")
        return [l.strip() for l in levels_str.split(",") if l.strip()]

    TARGET_LEADS_PER_WEEK: int = int(os.getenv("TARGET_LEADS_PER_WEEK", "10"))
    MAX_DAILY_EMAILS: int = int(os.getenv("MAX_DAILY_EMAILS", "20"))

    # ========================================================================
    # FEATURES OPCIONAIS (3 booleanas)
    # ========================================================================
    @property
    def ENABLE_GEOCODING(self) -> bool:
        """Geocodificação via Google Maps API."""
        return os.getenv("ENABLE_GEOCODING", "true").lower() == "true"

    @property
    def ENABLE_PHONE_SEARCH(self) -> bool:
        """Busca de telefones via Google Search."""
        return os.getenv("ENABLE_PHONE_SEARCH", "true").lower() == "true"

    @property
    def ENABLE_MAP_VIEW(self) -> bool:
        """Visualização de mapa no dashboard."""
        return os.getenv("ENABLE_MAP_VIEW", "true").lower() == "true"

    # ========================================================================
    # ANTHROPIC (3 variáveis)
    # ========================================================================
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Modelos Claude 4.5 (atualizados)
    CLAUDE_MODEL_FAST: str = os.getenv(
        "CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001"
    )
    CLAUDE_MODEL_QUALITY: str = os.getenv(
        "CLAUDE_MODEL_QUALITY", "claude-sonnet-4-5-20250929"
    )

    # ========================================================================
    # SUPABASE (2 variáveis)
    # ========================================================================
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

    # ========================================================================
    # HUBSPOT (2 variáveis)
    # ========================================================================
    HUBSPOT_API_KEY: str = os.getenv("HUBSPOT_API_KEY", "")
    HUBSPOT_PORTAL_ID: str = os.getenv("HUBSPOT_PORTAL_ID", "")
    HUBSPOT_MEETING_LINK: str = os.getenv("HUBSPOT_MEETING_LINK", "https://meetings.hubspot.com/fernando612")
    HUBSPOT_MEETING_LINK_TEXT: str = os.getenv("HUBSPOT_MEETING_LINK_TEXT", "Agendar conversa com Fernando")
    HUBSPOT_PIPELINE_NAME: str = os.getenv("HUBSPOT_PIPELINE_NAME", "IAprendo Sales")

    # ========================================================================
    # EMAIL (3+ variáveis)
    # ========================================================================
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "none")

    # Brevo (300/dia grátis)
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")

    # Gmail (500/dia)
    GMAIL_CREDENTIALS_PATH: str = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")

    # ========================================================================
    # GOOGLE MAPS (1 variável)
    # ========================================================================
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # ========================================================================
    # ENRIQUECIMENTO (6 variáveis)
    # ========================================================================
    # Apollo.io (60/mês grátis)
    APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
    APOLLO_MONTHLY_LIMIT: int = int(os.getenv("APOLLO_MONTHLY_LIMIT", "60"))

    # Snov.io (50/mês grátis)
    SNOV_CLIENT_ID: str = os.getenv("SNOV_CLIENT_ID", "")   # User ID em snov.io -> Profile -> API
    SNOV_API_KEY: str = os.getenv("SNOV_API_KEY", "")       # Client Secret
    SNOV_MONTHLY_LIMIT: int = int(os.getenv("SNOV_MONTHLY_LIMIT", "50"))

    # Hunter.io (25/mês grátis)
    HUNTER_API_KEY: str = os.getenv("HUNTER_API_KEY", "")
    HUNTER_MONTHLY_LIMIT: int = int(os.getenv("HUNTER_MONTHLY_LIMIT", "25"))

    # Perplexity (via navegador - gratis com assinatura Pro)
    ENABLE_PERPLEXITY: bool = os.getenv("ENABLE_PERPLEXITY", "true").lower() == "true"
    PERPLEXITY_MONTHLY_LIMIT: int = int(os.getenv("PERPLEXITY_MONTHLY_LIMIT", "200"))

    # ========================================================================
    # WHATSAPP (1 variável)
    # ========================================================================
    WHATSAPP_PROVIDER: str = os.getenv("WHATSAPP_PROVIDER", "manual")

    # ========================================================================
    # SISTEMA (3 variáveis)
    # ========================================================================
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8501"))

    # ========================================================================
    # MÉTODOS DE VALIDAÇÃO
    # ========================================================================

    @classmethod
    def validate_required(cls) -> bool:
        """
        Valida variáveis OBRIGATÓRIAS para funcionamento básico.

        Variáveis obrigatórias:
            - ANTHROPIC_API_KEY: Acesso à Claude API
            - SUPABASE_URL: URL do projeto Supabase
            - SUPABASE_KEY: Chave de API do Supabase
            - YOUR_EMAIL: Email do remetente
            - CSV_PATH: Caminho do CSV de escolas

        Returns:
            True se todas as variáveis obrigatórias estão presentes.

        Raises:
            ValueError: Se alguma variável obrigatória estiver faltando.

        Example:
            >>> from config.settings import settings
            >>> settings.validate_required()
            True
        """
        required = {
            'ANTHROPIC_API_KEY': cls.ANTHROPIC_API_KEY,
            'SUPABASE_URL': cls.SUPABASE_URL,
            'SUPABASE_KEY': cls.SUPABASE_KEY,
            'YOUR_EMAIL': cls.YOUR_EMAIL,
            'CSV_PATH': cls.CSV_PATH
        }

        missing = [key for key, value in required.items() if not value]

        if missing:
            raise ValueError(
                f"❌ Configurações OBRIGATÓRIAS faltando: {', '.join(missing)}\n\n"
                f"Execute o wizard de configuração:\n"
                f"  python setup_config.py\n\n"
                f"Ou crie o arquivo .env manualmente:\n"
                f"  cp .env.example .env\n"
                f"  # Preencha os valores obrigatórios"
            )

        return True

    @classmethod
    def validate_optional(cls) -> Dict[str, bool]:
        """
        Valida variáveis OPCIONAIS e retorna status de cada feature.

        Returns:
            Dicionário com status de cada feature opcional:
                - hubspot: bool - Integração HubSpot configurada
                - email_brevo: bool - Email via Brevo configurado
                - email_gmail: bool - Email via Gmail configurado
                - geocoding: bool - Geocodificação habilitada
                - phone_search: bool - Busca de telefones habilitada
                - apollo: bool - API Apollo configurada
                - snov: bool - API Snov configurada
                - hunter: bool - API Hunter configurada

        Example:
            >>> features = settings.validate_optional()
            >>> if features['hubspot']:
            >>>     print("HubSpot integrado!")
        """
        return {
            'hubspot': bool(cls.HUBSPOT_API_KEY),
            'email_brevo': cls.EMAIL_PROVIDER == 'brevo' and bool(cls.BREVO_API_KEY),
            'email_gmail': cls.EMAIL_PROVIDER == 'gmail',
            'geocoding': cls().ENABLE_GEOCODING and bool(cls.GOOGLE_MAPS_API_KEY),
            'phone_search': cls().ENABLE_PHONE_SEARCH,
            'apollo': bool(cls.APOLLO_API_KEY),
            'snov': bool(cls.SNOV_API_KEY),
            'hunter': bool(cls.HUNTER_API_KEY)
        }

    @classmethod
    def get_api_limits(cls) -> Dict[str, int]:
        """
        Retorna limites mensais de cada API de enriquecimento.

        Returns:
            Dicionário com limites mensais:
                - apollo: int - Limite mensal Apollo
                - snov: int - Limite mensal Snov
                - hunter: int - Limite mensal Hunter

        Example:
            >>> limits = settings.get_api_limits()
            >>> print(f"Apollo: {limits['apollo']}/mês")
        """
        return {
            'apollo': cls.APOLLO_MONTHLY_LIMIT,
            'snov': cls.SNOV_MONTHLY_LIMIT,
            'hunter': cls.HUNTER_MONTHLY_LIMIT,
            'perplexity': cls.PERPLEXITY_MONTHLY_LIMIT,
        }

    @classmethod
    def get_csv_column_mapping(cls) -> Dict[str, str]:
        """
        Retorna mapeamento completo de colunas do CSV.

        Returns:
            Dicionário com mapeamento nome_interno -> nome_no_csv.

        Example:
            >>> mapping = settings.get_csv_column_mapping()
            >>> print(mapping['name'])  # "Escola"
        """
        return {
            'name': cls.CSV_COL_NAME,
            'inep_code': cls.CSV_COL_INEP,
            'city': cls.CSV_COL_CITY,
            'state': cls.CSV_COL_STATE,
            'address': cls.CSV_COL_ADDRESS,
            'phone': cls.CSV_COL_PHONE,
            'restriction': cls.CSV_COL_RESTRICTION,
            'education_levels': cls.CSV_COL_LEVELS,
            'admin_category': cls.CSV_COL_ADMIN_CATEGORY,
            'admin_dependency': cls.CSV_COL_ADMIN_DEPENDENCY,
            'latitude': cls.CSV_COL_LATITUDE,
            'longitude': cls.CSV_COL_LONGITUDE,
            'size': cls.CSV_COL_SIZE
        }



# Singleton - instância única para todo o sistema
settings = Settings()
