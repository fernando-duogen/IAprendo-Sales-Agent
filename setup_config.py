#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_config.py - Wizard Interativo de Configuração
IAprendo Sales Agent - VERSÃO ATUALIZADA

Adaptado para CSV com estrutura real:
- Restrição de Atendimento
- Código INEP
- Latitude/Longitude
- Porte da Escola
- Etapas e Modalidade de Ensino Oferecidas

Uso:
    python setup_config.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import re


class Colors:
    """Cores ANSI para terminal"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Imprime cabeçalho colorido"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_section(text: str):
    """Imprime título de seção"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.ENDC}\n")


def print_success(text: str):
    """Imprime mensagem de sucesso"""
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Imprime aviso"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")


def print_error(text: str):
    """Imprime erro"""
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Imprime informação"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")


def validate_email(email: str) -> bool:
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_csv_path(path: str) -> bool:
    """Verifica se arquivo CSV existe"""
    return os.path.isfile(path) and path.endswith('.csv')


def ask_question(
    question: str,
    default: Optional[str] = None,
    required: bool = True,
    validator: Optional[callable] = None,
    validator_message: str = "Valor inválido!"
) -> str:
    """Faz uma pergunta ao usuário"""
    while True:
        if default:
            prompt = f"{question} ({Colors.BOLD}padrão: {default}{Colors.ENDC}): "
        else:
            prompt = f"{question}: "
        
        answer = input(prompt).strip()
        
        if not answer:
            if default:
                return default
            elif not required:
                return ""
            else:
                print_error("Este campo é obrigatório!")
                continue
        
        if validator and not validator(answer):
            print_error(validator_message)
            continue
        
        return answer


def ask_yes_no(question: str, default: bool = False) -> bool:
    """Pergunta sim/não"""
    default_str = "S/n" if default else "s/N"
    answer = input(f"{question} ({default_str}): ").strip().lower()
    
    if not answer:
        return default
    
    return answer in ['s', 'sim', 'y', 'yes']


def ask_multiple_choice(
    question: str,
    options: List[str],
    default: Optional[int] = None
) -> str:
    """Pergunta de múltipla escolha"""
    print(f"\n{question}")
    for i, option in enumerate(options, 1):
        marker = " (padrão)" if default and i == default else ""
        print(f"  {i}. {option}{marker}")
    
    while True:
        if default:
            answer = input(f"\nEscolha (1-{len(options)}) [padrão: {default}]: ").strip()
            if not answer:
                return options[default - 1]
        else:
            answer = input(f"\nEscolha (1-{len(options)}): ").strip()
        
        try:
            choice = int(answer)
            if 1 <= choice <= len(options):
                return options[choice - 1]
            else:
                print_error(f"Escolha um número entre 1 e {len(options)}")
        except ValueError:
            print_error("Digite um número válido")


def detect_csv_encoding(csv_path: str) -> str:
    """Detecta encoding do CSV automaticamente"""
    try:
        import chardet
        with open(csv_path, 'rb') as f:
            result = chardet.detect(f.read(50000))
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        print_info(f"Encoding detectado: {encoding} (confiança: {confidence:.0%})")
        return encoding
    except ImportError:
        print_warning("chardet não instalado, assumindo utf-8. Instale com: pip install chardet")
        return 'utf-8'
    except Exception:
        return 'utf-8'


def check_csv_structure(csv_path: str) -> Dict[str, any]:
    """Analisa estrutura do CSV e mostra preview"""
    try:
        import pandas as pd
        
        encoding = detect_csv_encoding(csv_path)
        df = pd.read_csv(csv_path, nrows=5, encoding=encoding)
        
        print_info(f"CSV encontrado: {len(df.columns)} colunas detectadas")
        print("\nPrimeiras colunas encontradas:")
        for i, col in enumerate(df.columns[:15], 1):
            print(f"  {i}. {col}")
        
        if len(df.columns) > 15:
            print(f"  ... e mais {len(df.columns) - 15} colunas")
        
        return {
            'columns': df.columns.tolist(),
            'sample': df.head(2).to_dict('records'),
            'total_columns': len(df.columns),
            'encoding': encoding
        }
    
    except Exception as e:
        print_warning(f"Não foi possível analisar CSV: {e}")
        return {'columns': [], 'sample': [], 'total_columns': 0, 'encoding': 'utf-8'}


def setup_wizard() -> Dict[str, any]:
    """Wizard principal de configuração"""
    config = {}
    
    print_header("🎯 BEM-VINDO AO SETUP DO IAPRENDO SALES AGENT")
    
    print(f"""
{Colors.BOLD}Este assistente vai configurar o sistema pela primeira vez.{Colors.ENDC}

Vou fazer perguntas sobre:
- Seus dados de contato
- Arquivo de dados das escolas (CSV com 210k escolas)
- Público-alvo (ICP)
- Integrações com APIs

Leva cerca de {Colors.BOLD}5-10 minutos{Colors.ENDC}.
""")
    
    continuar = ask_yes_no("Pronto para começar?", default=True)
    if not continuar:
        print("\n👋 Até logo!")
        sys.exit(0)
    
    # ==============================================
    # SEÇÃO 1: DADOS DO NEGÓCIO
    # ==============================================
    print_section("📊 SEÇÃO 1: DADOS DO SEU NEGÓCIO")
    
    config['COMPANY_NAME'] = ask_question(
        "Nome da sua empresa",
        default="IAprendo"
    )
    
    config['YOUR_NAME'] = ask_question(
        "Seu nome completo (para assinar emails)",
        default="Fernando"
    )
    
    config['YOUR_EMAIL'] = ask_question(
        "Seu email profissional",
        required=True,
        validator=validate_email,
        validator_message="Email inválido!"
    )
    
    config['YOUR_PHONE'] = ask_question(
        "Seu telefone/WhatsApp (opcional, formato: +5551999999999)",
        required=False
    )
    
    config['WEBSITE'] = ask_question(
        "Site da empresa (opcional)",
        required=False
    )
    
    # ==============================================
    # SEÇÃO 2: ARQUIVO DE DADOS
    # ==============================================
    print_section("📁 SEÇÃO 2: ARQUIVO DE DADOS (CSV)")
    
    print_info("Você tem um CSV com ~210 mil escolas do Brasil.")
    print("Vou precisar saber onde está e confirmar a estrutura.")
    
    # Localização do CSV
    while True:
        config['CSV_PATH'] = ask_question(
            "\nCaminho completo do arquivo CSV",
            default="data/raw/escolas_brasil.csv"
        )
        
        if validate_csv_path(config['CSV_PATH']):
            print_success(f"Arquivo encontrado: {config['CSV_PATH']}")
            break
        else:
            print_error("Arquivo não encontrado!")
            
            criar = ask_yes_no("Quer que eu crie a pasta data/raw/?", default=True)
            if criar:
                os.makedirs("data/raw", exist_ok=True)
                print_success("Pasta criada: data/raw/")
                print_info("Coloque seu CSV lá e rode este setup novamente.")
                sys.exit(0)
    
    # Analisa estrutura
    print("\n🔍 Analisando estrutura do CSV...")
    csv_info = check_csv_structure(config['CSV_PATH'])
    config['CSV_ENCODING'] = csv_info.get('encoding', 'utf-8')
    
    # Verifica se é a estrutura padrão esperada
    print("\n📋 ESTRUTURA DO CSV")
    print_info("Seu CSV tem esta estrutura padrão do MEC?")
    print("  • Escola")
    print("  • Código INEP")
    print("  • UF, Município, Endereço, Telefone")
    print("  • Restrição de Atendimento")
    print("  • Etapas e Modalidade de Ensino Oferecidas")
    print("  • Categoria Administrativa, Dependência Administrativa")
    print("  • Latitude, Longitude")
    print("  • Porte da Escola")
    
    usar_padrao = ask_yes_no(
        "\nSeu CSV tem EXATAMENTE esses nomes de colunas?",
        default=True
    )
    
    if usar_padrao:
        config['CSV_COL_NAME'] = "Escola"
        config['CSV_COL_INEP'] = "Código INEP"
        config['CSV_COL_CITY'] = "Município"
        config['CSV_COL_STATE'] = "UF"
        config['CSV_COL_ADDRESS'] = "Endereço"
        config['CSV_COL_PHONE'] = "Telefone"
        config['CSV_COL_RESTRICTION'] = "Restrição de Atendimento"
        config['CSV_COL_LEVELS'] = "Etapas e Modalidade de Ensino Oferecidas"
        config['CSV_COL_ADMIN_CATEGORY'] = "Categoria Administrativa"
        config['CSV_COL_ADMIN_DEPENDENCY'] = "Dependência Administrativa"
        config['CSV_COL_LATITUDE'] = "Latitude"
        config['CSV_COL_LONGITUDE'] = "Longitude"
        config['CSV_COL_SIZE'] = "Porte da Escola"
        
        print_success("✅ Usando estrutura padrão!")
    else:
        # Mapeamento manual
        print("\nVou perguntar o nome de cada coluna no SEU CSV:")
        config['CSV_COL_NAME'] = ask_question("Coluna com NOME da escola", default="Escola")
        config['CSV_COL_INEP'] = ask_question("Coluna com CÓDIGO INEP", default="Código INEP")
        config['CSV_COL_CITY'] = ask_question("Coluna com MUNICÍPIO/CIDADE", default="Município")
        config['CSV_COL_STATE'] = ask_question("Coluna com UF/ESTADO", default="UF")
        config['CSV_COL_ADDRESS'] = ask_question("Coluna com ENDEREÇO", default="Endereço")
        config['CSV_COL_PHONE'] = ask_question("Coluna com TELEFONE", default="Telefone")
        config['CSV_COL_RESTRICTION'] = ask_question("Coluna com STATUS/RESTRIÇÃO", default="Restrição de Atendimento")
        config['CSV_COL_LEVELS'] = ask_question("Coluna com NÍVEIS DE ENSINO", default="Etapas e Modalidade de Ensino Oferecidas")
        config['CSV_COL_ADMIN_CATEGORY'] = ask_question("Coluna com CATEGORIA ADMINISTRATIVA", default="Categoria Administrativa")
        config['CSV_COL_ADMIN_DEPENDENCY'] = ask_question("Coluna com DEPENDÊNCIA ADMINISTRATIVA", default="Dependência Administrativa")
        config['CSV_COL_LATITUDE'] = ask_question("Coluna com LATITUDE", default="Latitude")
        config['CSV_COL_LONGITUDE'] = ask_question("Coluna com LONGITUDE", default="Longitude")
        config['CSV_COL_SIZE'] = ask_question("Coluna com PORTE DA ESCOLA", default="Porte da Escola")
    
    # ==============================================
    # SEÇÃO 3: PÚBLICO-ALVO
    # ==============================================
    print_section("🎯 SEÇÃO 3: PÚBLICO-ALVO (ICP)")
    
    config['TARGET_CITY'] = ask_question(
        "Cidade alvo",
        default="Porto Alegre"
    )
    
    config['TARGET_STATE'] = ask_question(
        "Estado (sigla)",
        default="RS"
    )
    
    # Filtros de níveis
    print("\n🎓 NÍVEIS DE ENSINO")
    print("Seu CSV tem 'Etapas e Modalidade de Ensino Oferecidas'")
    print("Vamos filtrar escolas que tenham PELO MENOS:")
    
    incluir_fundamental = ask_yes_no("Ensino Fundamental (6º-9º ano)?", default=True)
    incluir_medio = ask_yes_no("Ensino Médio?", default=True)
    
    niveis = []
    if incluir_fundamental:
        niveis.append("fundamental")
    if incluir_medio:
        niveis.append("medio")
    
    config['TARGET_EDUCATION_LEVELS'] = ','.join(niveis) if niveis else "fundamental,medio"
    
    # Tipos de escola
    print("\n🏫 TIPOS DE ESCOLA")
    incluir_publica = ask_yes_no("Incluir escolas PÚBLICAS?", default=True)
    incluir_privada = ask_yes_no("Incluir escolas PRIVADAS?", default=True)
    
    tipos = []
    if incluir_publica:
        tipos.extend(["publica", "municipal", "estadual", "federal"])
    if incluir_privada:
        tipos.append("privada")
    
    config['TARGET_SCHOOL_TYPES'] = ','.join(tipos)
    
    # Volume
    config['TARGET_LEADS_PER_WEEK'] = ask_question(
        "\nQuantos leads NOVOS processar por semana?",
        default="10"
    )
    
    config['MAX_DAILY_EMAILS'] = ask_question(
        "Limite de emails para enviar por dia?",
        default="20"
    )
    
    # ==============================================
    # SEÇÃO 4: FEATURES EXTRAS
    # ==============================================
    print_section("✨ SEÇÃO 4: FEATURES EXTRAS")
    
    # Geocoding
    print("📍 GEOCODIFICAÇÃO")
    print("Algumas escolas no CSV não têm Latitude/Longitude.")
    config['ENABLE_GEOCODING'] = ask_yes_no(
        "Quer que o sistema busque coordenadas automaticamente (Google Maps)?",
        default=True
    )
    
    # Phone finding
    print("\n📞 BUSCA DE TELEFONES")
    print("Algumas escolas não têm telefone no CSV.")
    config['ENABLE_PHONE_SEARCH'] = ask_yes_no(
        "Quer que o sistema busque telefones automaticamente (Google)?",
        default=True
    )
    
    # Visualização mapa
    config['ENABLE_MAP_VIEW'] = ask_yes_no(
        "\n🗺️ Quer visualizar escolas em mapa no dashboard?",
        default=True
    )
    
    # ==============================================
    # SEÇÃO 5: INTEGRAÇÕES
    # ==============================================
    print_section("🔑 SEÇÃO 5: INTEGRAÇÕES (APIs)")
    
    # Anthropic
    print(f"{Colors.BOLD}Claude API (OBRIGATÓRIO){Colors.ENDC}")
    config['HAS_ANTHROPIC'] = ask_yes_no(
        "Você JÁ TEM uma API key do Anthropic/Claude?",
        default=False
    )
    
    if config['HAS_ANTHROPIC']:
        config['ANTHROPIC_API_KEY'] = ask_question(
            "Cole sua API key (começa com 'sk-ant-')"
        )
    else:
        print_warning("Crie em: https://console.anthropic.com")
        config['ANTHROPIC_API_KEY'] = ""
    
    # Supabase
    print(f"\n{Colors.BOLD}Supabase - Banco de Dados (OBRIGATÓRIO){Colors.ENDC}")
    config['HAS_SUPABASE'] = ask_yes_no(
        "Você JÁ TEM um projeto no Supabase?",
        default=False
    )
    
    if config['HAS_SUPABASE']:
        config['SUPABASE_URL'] = ask_question("URL do projeto (https://xxxxx.supabase.co)")
        config['SUPABASE_KEY'] = ask_question("API Key (anon/public)")
    else:
        print_warning("Crie em: https://supabase.com")
        config['SUPABASE_URL'] = ""
        config['SUPABASE_KEY'] = ""
    
    # HubSpot
    print(f"\n{Colors.BOLD}HubSpot CRM (OBRIGATÓRIO){Colors.ENDC}")
    config['HAS_HUBSPOT'] = ask_yes_no(
        "Você JÁ TEM conta no HubSpot?",
        default=False
    )
    
    if config['HAS_HUBSPOT']:
        config['HUBSPOT_API_KEY'] = ask_question("API Key (começa com 'pat-na1-')")
        config['HUBSPOT_PORTAL_ID'] = ask_question("Portal ID (opcional)", required=False)
    else:
        print_warning("Crie em: https://hubspot.com")
        config['HUBSPOT_API_KEY'] = ""
        config['HUBSPOT_PORTAL_ID'] = ""
    
    # Email Provider
    print(f"\n{Colors.BOLD}Provedor de Email{Colors.ENDC}")
    email_provider = ask_multiple_choice(
        "Qual provedor quer usar?",
        [
            "Gmail (conta Google - 500/dia grátis)",
            "Brevo (300/dia grátis)",
            "Configurar depois"
        ],
        default=2
    )
    
    if "Gmail" in email_provider:
        config['EMAIL_PROVIDER'] = "gmail"
        print_info("Configure OAuth2: https://developers.google.com/gmail/api/quickstart/python")
    elif "Brevo" in email_provider:
        config['EMAIL_PROVIDER'] = "brevo"
        config['HAS_BREVO'] = ask_yes_no("Tem API key do Brevo?", default=False)
        if config['HAS_BREVO']:
            config['BREVO_API_KEY'] = ask_question("API Key Brevo")
        else:
            config['BREVO_API_KEY'] = ""
    else:
        config['EMAIL_PROVIDER'] = "none"
    
    # Google Maps (para geocoding)
    if config.get('ENABLE_GEOCODING'):
        print(f"\n{Colors.BOLD}Google Maps API (para geocoding){Colors.ENDC}")
        config['HAS_GOOGLE_MAPS'] = ask_yes_no(
            "Tem API key do Google Maps?",
            default=False
        )
        
        if config['HAS_GOOGLE_MAPS']:
            config['GOOGLE_MAPS_API_KEY'] = ask_question("API Key Google Maps")
        else:
            print_warning("$200 créditos grátis/mês: https://console.cloud.google.com")
            config['GOOGLE_MAPS_API_KEY'] = ""
    
    # APIs opcionais
    print(f"\n{Colors.BOLD}APIs de Enriquecimento (OPCIONAIS){Colors.ENDC}")
    print("Ajudam a encontrar emails. Todas têm planos gratuitos.")
    
    config['HAS_APOLLO'] = ask_yes_no("Tem Apollo.io?", default=False)
    if config['HAS_APOLLO']:
        config['APOLLO_API_KEY'] = ask_question("API Key Apollo")
    else:
        config['APOLLO_API_KEY'] = ""
    
    config['HAS_SNOV'] = ask_yes_no("Tem Snov.io?", default=False)
    if config['HAS_SNOV']:
        config['SNOV_API_KEY'] = ask_question("API Key Snov")
    else:
        config['SNOV_API_KEY'] = ""
    
    config['HAS_HUNTER'] = ask_yes_no("Tem Hunter.io?", default=False)
    if config['HAS_HUNTER']:
        config['HUNTER_API_KEY'] = ask_question("API Key Hunter")
    else:
        config['HUNTER_API_KEY'] = ""
    
    # WhatsApp
    print(f"\n{Colors.BOLD}WhatsApp{Colors.ENDC}")
    config['WHATSAPP_PROVIDER'] = "manual"  # Por enquanto sempre manual
    
    # ==============================================
    # CONFIRMAÇÃO
    # ==============================================
    print_section("📋 REVISÃO")
    
    print(f"{Colors.BOLD}Negócio:{Colors.ENDC}")
    print(f"  • {config['COMPANY_NAME']}")
    print(f"  • {config['YOUR_NAME']} ({config['YOUR_EMAIL']})")
    
    print(f"\n{Colors.BOLD}CSV:{Colors.ENDC}")
    print(f"  • {config['CSV_PATH']}")
    
    print(f"\n{Colors.BOLD}Alvo:{Colors.ENDC}")
    print(f"  • {config['TARGET_CITY']}, {config['TARGET_STATE']}")
    print(f"  • Níveis: {config['TARGET_EDUCATION_LEVELS']}")
    print(f"  • {config['TARGET_LEADS_PER_WEEK']} leads/semana")
    
    print(f"\n{Colors.BOLD}APIs:{Colors.ENDC}")
    print(f"  • Claude: {'✅' if config['HAS_ANTHROPIC'] else '⚠️'}")
    print(f"  • Supabase: {'✅' if config['HAS_SUPABASE'] else '⚠️'}")
    print(f"  • HubSpot: {'✅' if config['HAS_HUBSPOT'] else '⚠️'}")
    
    confirma = ask_yes_no("\nGerar arquivos de configuração?", default=True)
    
    if not confirma:
        print_warning("Cancelado.")
        sys.exit(0)
    
    return config


def generate_env_file(config: Dict):
    """Gera arquivo .env"""
    
    env_content = f"""# ============================================
# IAPRENDO SALES AGENT - CONFIGURAÇÃO
# Gerado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ============================================

# NEGÓCIO
COMPANY_NAME={config['COMPANY_NAME']}
YOUR_NAME={config['YOUR_NAME']}
YOUR_EMAIL={config['YOUR_EMAIL']}
YOUR_PHONE={config.get('YOUR_PHONE', '')}
WEBSITE={config.get('WEBSITE', '')}

# CSV
CSV_PATH={config['CSV_PATH']}
CSV_ENCODING={config.get('CSV_ENCODING', 'utf-8')}
CSV_COL_NAME={config['CSV_COL_NAME']}
CSV_COL_INEP={config['CSV_COL_INEP']}
CSV_COL_CITY={config['CSV_COL_CITY']}
CSV_COL_STATE={config['CSV_COL_STATE']}
CSV_COL_ADDRESS={config['CSV_COL_ADDRESS']}
CSV_COL_PHONE={config['CSV_COL_PHONE']}
CSV_COL_RESTRICTION={config['CSV_COL_RESTRICTION']}
CSV_COL_LEVELS={config['CSV_COL_LEVELS']}
CSV_COL_ADMIN_CATEGORY={config['CSV_COL_ADMIN_CATEGORY']}
CSV_COL_ADMIN_DEPENDENCY={config['CSV_COL_ADMIN_DEPENDENCY']}
CSV_COL_LATITUDE={config['CSV_COL_LATITUDE']}
CSV_COL_LONGITUDE={config['CSV_COL_LONGITUDE']}
CSV_COL_SIZE={config['CSV_COL_SIZE']}

# ICP
TARGET_CITY={config['TARGET_CITY']}
TARGET_STATE={config['TARGET_STATE']}
TARGET_SCHOOL_TYPES={config['TARGET_SCHOOL_TYPES']}
TARGET_EDUCATION_LEVELS={config['TARGET_EDUCATION_LEVELS']}
TARGET_LEADS_PER_WEEK={config['TARGET_LEADS_PER_WEEK']}
MAX_DAILY_EMAILS={config['MAX_DAILY_EMAILS']}

# FEATURES
ENABLE_GEOCODING={str(config.get('ENABLE_GEOCODING', False)).lower()}
ENABLE_PHONE_SEARCH={str(config.get('ENABLE_PHONE_SEARCH', False)).lower()}
ENABLE_MAP_VIEW={str(config.get('ENABLE_MAP_VIEW', True)).lower()}

# ANTHROPIC
ANTHROPIC_API_KEY={config.get('ANTHROPIC_API_KEY', '')}
CLAUDE_MODEL_FAST=claude-haiku-4-5-20251001
CLAUDE_MODEL_QUALITY=claude-sonnet-4-5-20250929

# SUPABASE
SUPABASE_URL={config.get('SUPABASE_URL', '')}
SUPABASE_KEY={config.get('SUPABASE_KEY', '')}

# HUBSPOT
HUBSPOT_API_KEY={config.get('HUBSPOT_API_KEY', '')}
HUBSPOT_PORTAL_ID={config.get('HUBSPOT_PORTAL_ID', '')}

# EMAIL
EMAIL_PROVIDER={config.get('EMAIL_PROVIDER', 'none')}
{"BREVO_API_KEY=" + config.get('BREVO_API_KEY', '') if config.get('EMAIL_PROVIDER') == 'brevo' else "# BREVO_API_KEY="}
{"GMAIL_CREDENTIALS_PATH=credentials.json" if config.get('EMAIL_PROVIDER') == 'gmail' else "# GMAIL_CREDENTIALS_PATH="}

# GOOGLE MAPS
{"GOOGLE_MAPS_API_KEY=" + config.get('GOOGLE_MAPS_API_KEY', '') if config.get('ENABLE_GEOCODING') else "# GOOGLE_MAPS_API_KEY="}

# ENRIQUECIMENTO (OPCIONAL)
APOLLO_API_KEY={config.get('APOLLO_API_KEY', '')}
APOLLO_MONTHLY_LIMIT=60
SNOV_API_KEY={config.get('SNOV_API_KEY', '')}
SNOV_MONTHLY_LIMIT=50
HUNTER_API_KEY={config.get('HUNTER_API_KEY', '')}
HUNTER_MONTHLY_LIMIT=25

# WHATSAPP
WHATSAPP_PROVIDER=manual

# SISTEMA
LOG_LEVEL=INFO
ENVIRONMENT=development
DASHBOARD_PORT=8501
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print_success("Arquivo .env criado!")


def generate_review_file(config: Dict):
    """Gera CONFIG_REVIEW.md"""
    
    content = f"""# 📋 CONFIGURAÇÃO DO SISTEMA

**Gerado em:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## ✅ Configurações

### Negócio
- **Empresa:** {config['COMPANY_NAME']}
- **Nome:** {config['YOUR_NAME']}
- **Email:** {config['YOUR_EMAIL']}

### CSV
- **Arquivo:** `{config['CSV_PATH']}`
- **Estrutura:** {"Padrão MEC" if config['CSV_COL_NAME'] == "Escola" else "Customizada"}

### Público-Alvo
- **Local:** {config['TARGET_CITY']}, {config['TARGET_STATE']}
- **Tipos:** {config['TARGET_SCHOOL_TYPES']}
- **Níveis:** {config['TARGET_EDUCATION_LEVELS']}
- **Volume:** {config['TARGET_LEADS_PER_WEEK']} leads/semana

### Features Extras
- **Geocoding:** {'✅ Ativado' if config.get('ENABLE_GEOCODING') else '❌ Desativado'}
- **Phone Search:** {'✅ Ativado' if config.get('ENABLE_PHONE_SEARCH') else '❌ Desativado'}
- **Map View:** {'✅ Ativado' if config.get('ENABLE_MAP_VIEW') else '❌ Desativado'}

### Integrações
- **Claude:** {'✅' if config.get('HAS_ANTHROPIC') else '❌ CONFIGURE'}
- **Supabase:** {'✅' if config.get('HAS_SUPABASE') else '❌ CONFIGURE'}
- **HubSpot:** {'✅' if config.get('HAS_HUBSPOT') else '❌ CONFIGURE'}
- **Email:** {config.get('EMAIL_PROVIDER', 'none').upper()}
- **Google Maps:** {'✅' if config.get('GOOGLE_MAPS_API_KEY') else '❌'}

## 🚀 Próximos Passos

1. **Complete API Keys no .env** (se faltou alguma)
2. **Configure Supabase:**
```bash
   python database/migrations/002_setup_database.py
```
3. **Importe CSV (teste):**
```bash
   python database/migrations/001_import_schools.py --sample 100
```
4. **Configure HubSpot** (campos customizados)
5. **Inicie dashboard:**
```bash
   streamlit run dashboard/main.py
```

## 📚 Documentação
- **CLAUDE.md** - Especificação técnica
- **README.md** - Guia do usuário
"""
    
    with open('CONFIG_REVIEW.md', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print_success("Arquivo CONFIG_REVIEW.md criado!")


def generate_gitignore():
    """Gera .gitignore"""
    
    gitignore = """# Python
__pycache__/
*.pyc
venv/
.env

# IDEs
.vscode/
.idea/

# OS
.DS_Store

# Logs
logs/
*.log

# Data
data/raw/*.csv
data/processed/*

# Credentials
credentials.json
token.json

# Config Review
CONFIG_REVIEW.md
"""
    
    if not os.path.exists('.gitignore'):
        with open('.gitignore', 'w') as f:
            f.write(gitignore)
        print_success(".gitignore criado!")


def create_directories():
    """Cria estrutura de diretórios"""
    
    dirs = [
        'config', 'database', 'database/migrations', 'agents',
        'integrations', 'tools', 'approval_queue', 'workflows',
        'dashboard', 'dashboard/components', 'dashboard/pages',
        'prompts', 'utils', 'data/raw', 'data/processed',
        'data/exports', 'logs', 'tests', 'scripts'
    ]
    
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        if not d.startswith('data') and d != 'logs' and d != 'prompts':
            init = os.path.join(d, '__init__.py')
            if not os.path.exists(init):
                with open(init, 'w') as f:
                    f.write(f'"""{d} package"""\n')
    
    print_success("Diretórios criados!")


def main():
    try:
        config = setup_wizard()
        
        print_section("📝 GERANDO ARQUIVOS")
        
        generate_env_file(config)
        generate_review_file(config)
        generate_gitignore()
        create_directories()
        
        print_header("✅ SETUP CONCLUÍDO!")
        
        print(f"""
{Colors.GREEN}Arquivos criados:{Colors.ENDC}
  ✅ .env
  ✅ CONFIG_REVIEW.md
  ✅ .gitignore
  ✅ Estrutura de diretórios

{Colors.BOLD}Próximos passos:{Colors.ENDC}
1. Revise CONFIG_REVIEW.md
2. Configure Supabase
3. Importe CSV
4. Configure HubSpot
5. Rode o dashboard

{Colors.GREEN}Tudo pronto! 🚀{Colors.ENDC}
""")
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup interrompido.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Erro: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()