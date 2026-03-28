"""
Testes de Validação - Fase 1: Fundação

Este script valida que todos os componentes da Fase 1 foram implementados
corretamente e estão funcionando.

Execute: python test_fase1.py
"""

import sys
import io
from pathlib import Path

# Forçar UTF-8 no Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("="*80)
print("TESTES DE VALIDACAO - FASE 1: FUNDACAO")
print("="*80)
print()

# ============================================================================
# TESTE 1: Estrutura de Arquivos
# ============================================================================
print("[TESTE 1] Estrutura de Arquivos")
print("-" * 80)

arquivos_necessarios = [
    ".gitignore",
    ".env.example",
    "requirements.txt",
    "README.md",
    "config/__init__.py",
    "config/settings.py",
    "database/__init__.py",
    "database/schemas.sql",
    "database/supabase_client.py",
    "utils/__init__.py",
    "utils/logger.py",
]

diretorios_necessarios = [
    "config",
    "database",
    "database/migrations",
    "utils",
    "data/raw",
    "data/processed",
    "data/exports",
    "logs",
]

erros = []

# Verificar arquivos
for arquivo in arquivos_necessarios:
    caminho = Path(arquivo)
    if caminho.exists():
        tamanho = caminho.stat().st_size
        print(f"  ✅ {arquivo} ({tamanho:,} bytes)")
    else:
        print(f"  ❌ {arquivo} - FALTANDO")
        erros.append(f"Arquivo faltando: {arquivo}")

# Verificar diretórios
for diretorio in diretorios_necessarios:
    caminho = Path(diretorio)
    if caminho.exists() and caminho.is_dir():
        print(f"  ✅ {diretorio}/")
    else:
        print(f"  ❌ {diretorio}/ - FALTANDO")
        erros.append(f"Diretório faltando: {diretorio}")

print()

# ============================================================================
# TESTE 2: Configuração (settings.py)
# ============================================================================
print("[TESTE 2] Sistema de Configuracao")
print("-" * 80)

try:
    from config.settings import settings
    print("  ✅ Módulo config.settings importado")

    # Verificar atributos principais
    atributos = [
        'COMPANY_NAME', 'YOUR_EMAIL', 'CSV_PATH', 'ANTHROPIC_API_KEY',
        'SUPABASE_URL', 'SUPABASE_KEY', 'CLAUDE_MODEL_FAST',
        'CLAUDE_MODEL_QUALITY', 'CSV_ENCODING'
    ]

    for attr in atributos:
        if hasattr(settings, attr):
            valor = getattr(settings, attr)
            # Mascarar chaves sensíveis
            if 'KEY' in attr or 'URL' in attr:
                display = f"{valor[:20]}..." if len(valor) > 20 else valor
            else:
                display = valor
            print(f"  ✅ {attr} = {display}")
        else:
            print(f"  ❌ {attr} - FALTANDO")
            erros.append(f"Atributo faltando em settings: {attr}")

    # Testar métodos
    try:
        csv_mapping = settings.get_csv_column_mapping()
        print(f"  ✅ get_csv_column_mapping() retornou {len(csv_mapping)} colunas")
    except Exception as e:
        print(f"  ❌ get_csv_column_mapping() falhou: {e}")
        erros.append(f"get_csv_column_mapping() falhou: {e}")

    try:
        api_limits = settings.get_api_limits()
        print(f"  ✅ get_api_limits() retornou {len(api_limits)} APIs")
    except Exception as e:
        print(f"  ❌ get_api_limits() falhou: {e}")
        erros.append(f"get_api_limits() falhou: {e}")

    try:
        optional_features = settings.validate_optional()
        print(f"  ✅ validate_optional() retornou {len(optional_features)} features")
    except Exception as e:
        print(f"  ❌ validate_optional() falhou: {e}")
        erros.append(f"validate_optional() falhou: {e}")

except ImportError as e:
    print(f"  ❌ Falha ao importar config.settings: {e}")
    erros.append(f"Import config.settings falhou: {e}")
except Exception as e:
    print(f"  ❌ Erro inesperado em config: {e}")
    erros.append(f"Erro em config: {e}")

print()

# ============================================================================
# TESTE 3: Logger (utils/logger.py)
# ============================================================================
print("[TESTE 3] Sistema de Logging")
print("-" * 80)

try:
    from utils.logger import logger, log_function_call, log_api_call
    print("  ✅ Módulo utils.logger importado")

    # Testar logging
    logger.info("Teste de log INFO", extra={'test_id': 'fase1'})
    print("  ✅ logger.info() funcionou")

    logger.warning("Teste de log WARNING", extra={'test_id': 'fase1'})
    print("  ✅ logger.warning() funcionou")

    # Testar helpers
    log_function_call("test_function", param1="value1", param2=123)
    print("  ✅ log_function_call() funcionou")

    log_api_call(
        api_name="test_api",
        endpoint="/test",
        method="GET",
        status_code=200,
        duration_ms=123.45
    )
    print("  ✅ log_api_call() funcionou")

    # Verificar se arquivo de log foi criado
    log_file = Path("logs/application.log")
    if log_file.exists():
        tamanho = log_file.stat().st_size
        print(f"  ✅ Arquivo de log criado ({tamanho:,} bytes)")
    else:
        print(f"  ⚠️  Arquivo de log não encontrado (pode ser normal)")

except ImportError as e:
    print(f"  ❌ Falha ao importar utils.logger: {e}")
    erros.append(f"Import utils.logger falhou: {e}")
except Exception as e:
    print(f"  ❌ Erro inesperado em logger: {e}")
    erros.append(f"Erro em logger: {e}")

print()

# ============================================================================
# TESTE 4: Database Client (database/supabase_client.py)
# ============================================================================
print("[TESTE 4] Cliente de Banco de Dados")
print("-" * 80)

try:
    from database.supabase_client import Database, db, DatabaseError
    print("  ✅ Módulo database.supabase_client importado")

    # Verificar se instância db existe
    if db is not None:
        print("  ✅ Instância singleton 'db' criada")
    else:
        print("  ❌ Instância 'db' é None")
        erros.append("Instância db é None")

    # Verificar métodos da classe Database
    metodos_necessarios = [
        'get_company_by_inep',
        'insert_company',
        'update_company',
        'get_companies_by_status',
        'insert_contact',
        'get_contacts_by_company',
        'get_pending_approvals',
        'insert_interaction',
        'count_api_usage_since',
        'count_api_usage_this_month',
        'insert_api_usage'
    ]

    for metodo in metodos_necessarios:
        if hasattr(Database, metodo):
            print(f"  ✅ Database.{metodo}() existe")
        else:
            print(f"  ❌ Database.{metodo}() - FALTANDO")
            erros.append(f"Método faltando: Database.{metodo}()")

    # NOTA: Não testamos conexão real porque pode não ter .env configurado ainda

except ImportError as e:
    print(f"  ❌ Falha ao importar database.supabase_client: {e}")
    erros.append(f"Import database.supabase_client falhou: {e}")
except Exception as e:
    print(f"  ❌ Erro inesperado em database: {e}")
    erros.append(f"Erro em database: {e}")

print()

# ============================================================================
# TESTE 5: SQL Schema
# ============================================================================
print("[TESTE 5] Schema SQL")
print("-" * 80)

schema_file = Path("database/schemas.sql")
if schema_file.exists():
    conteudo = schema_file.read_text(encoding='utf-8')

    # Verificar tabelas
    tabelas = [
        'companies',
        'contacts',
        'approval_queue',
        'interactions',
        'meetings',
        'api_usage',
        'campaigns'
    ]

    for tabela in tabelas:
        if f"CREATE TABLE IF NOT EXISTS {tabela}" in conteudo:
            print(f"  ✅ Tabela '{tabela}' definida")
        else:
            print(f"  ❌ Tabela '{tabela}' - FALTANDO")
            erros.append(f"Tabela faltando no schema: {tabela}")

    # Verificar índices críticos
    if "CREATE INDEX" in conteudo:
        num_indices = conteudo.count("CREATE INDEX")
        print(f"  ✅ {num_indices} índices definidos")
    else:
        print(f"  ⚠️  Nenhum índice encontrado")

    # Verificar triggers
    if "CREATE TRIGGER" in conteudo:
        num_triggers = conteudo.count("CREATE TRIGGER")
        print(f"  ✅ {num_triggers} triggers definidos")
    else:
        print(f"  ⚠️  Nenhum trigger encontrado")

    # Verificar UNIQUE constraint em inep_code
    if "inep_code VARCHAR(20) UNIQUE NOT NULL" in conteudo:
        print(f"  ✅ UNIQUE constraint em inep_code (evita duplicatas)")
    else:
        print(f"  ⚠️  UNIQUE constraint em inep_code não encontrado")

else:
    print(f"  ❌ Arquivo schemas.sql não encontrado")
    erros.append("schemas.sql não encontrado")

print()

# ============================================================================
# RESUMO FINAL
# ============================================================================
print("="*80)
print("RESUMO DOS TESTES")
print("="*80)

if len(erros) == 0:
    print("[OK] TODOS OS TESTES PASSARAM!")
    print()
    print("Fase 1: Fundacao implementada com sucesso!")
    print()
    print("Proximos passos:")
    print("1. Configure o sistema: python setup_config.py")
    print("2. Execute o schema SQL no Supabase SQL Editor")
    print("3. Teste a conexao: python -c 'from database.supabase_client import db'")
    print()
    sys.exit(0)
else:
    print(f"[ERRO] {len(erros)} ERRO(S) ENCONTRADO(S):")
    print()
    for i, erro in enumerate(erros, 1):
        print(f"  {i}. {erro}")
    print()
    print("Por favor, corrija os erros acima antes de prosseguir.")
    print()
    sys.exit(1)
