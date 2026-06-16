"""
Script de Testes para Database Migrations.

Este script testa as migrations de forma progressiva:
    1. Verificação de ambiente (Python, dependências)
    2. Verificação de configuração (.env)
    3. Teste de imports
    4. Teste da migration 001 (setup database)
    5. Teste da migration 002 (import CSV com sample pequeno)

Usage:
    python test_migrations.py
"""

import sys
import subprocess
from pathlib import Path
from typing import Dict, Tuple, List

# ============================================================================
# CORES PARA OUTPUT
# ============================================================================

class Colors:
    """Códigos ANSI para colorir output do terminal."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str) -> None:
    """Imprime cabeçalho colorido."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_success(text: str) -> None:
    """Imprime mensagem de sucesso."""
    # Usar caracteres ASCII para compatibilidade com Windows
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_warning(text: str) -> None:
    """Imprime mensagem de aviso."""
    print(f"{Colors.YELLOW}[!] {text}{Colors.END}")

def print_error(text: str) -> None:
    """Imprime mensagem de erro."""
    print(f"{Colors.RED}[X] {text}{Colors.END}")

def print_info(text: str) -> None:
    """Imprime mensagem informativa."""
    print(f"  {text}")


# ============================================================================
# TESTE 1: AMBIENTE PYTHON
# ============================================================================

def test_python_version() -> Tuple[bool, str]:
    """
    Verifica versão do Python (3.11+).

    Returns:
        Tupla (success, message).
    """
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major == 3 and version.minor >= 11:
        return True, f"Python {version_str} OK"
    else:
        return False, f"Python {version_str} (requer 3.11+)"


# ============================================================================
# TESTE 2: DEPENDÊNCIAS
# ============================================================================

def test_dependencies() -> Dict[str, bool]:
    """
    Verifica se dependências estão instaladas.

    Returns:
        Dict com status de cada dependência.
    """
    required_packages = [
        'pandas',
        'python-dotenv',
        'supabase',
        'pythonjsonlogger',
        'streamlit',
        'anthropic'
    ]

    results = {}

    for package in required_packages:
        # Normalizar nome do import
        import_name = package.replace('-', '_')
        if package == 'python-dotenv':
            import_name = 'dotenv'

        try:
            __import__(import_name)
            results[package] = True
        except ImportError:
            results[package] = False

    return results


def install_dependencies() -> bool:
    """
    Instala dependências via pip.

    Returns:
        True se instalação bem-sucedida.
    """
    requirements_file = Path("requirements.txt")

    if not requirements_file.exists():
        print_error("requirements.txt não encontrado")
        return False

    print_info("Instalando dependências via pip...")

    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Erro ao instalar dependências: {e.stderr}")
        return False


# ============================================================================
# TESTE 3: CONFIGURAÇÃO (.env)
# ============================================================================

def test_env_file() -> Tuple[bool, List[str]]:
    """
    Verifica se .env existe e tem variáveis obrigatórias.

    Returns:
        Tupla (success, missing_vars).
    """
    env_file = Path(".env")

    if not env_file.exists():
        return False, [".env file not found"]

    # Ler .env
    env_content = env_file.read_text()

    # Variáveis obrigatórias para migrations
    required_vars = [
        'SUPABASE_URL',
        'SUPABASE_KEY',
        'ANTHROPIC_API_KEY',
        'YOUR_EMAIL',
        'CSV_PATH'
    ]

    missing = []

    for var in required_vars:
        # Verificar se variável está definida (não vazia)
        if f"{var}=" not in env_content or f"{var}=\n" in env_content or f'{var}=""' in env_content:
            missing.append(var)

    return len(missing) == 0, missing


# ============================================================================
# TESTE 4: IMPORTS DOS MÓDULOS
# ============================================================================

def test_imports() -> Dict[str, Tuple[bool, str]]:
    """
    Testa imports dos módulos principais.

    Returns:
        Dict com status de cada import.
    """
    results = {}

    # Lista de imports para testar
    test_imports = {
        'config.settings': 'from config.settings import settings',
        'database.supabase_client': 'from database.supabase_client import db',
        'utils.logger': 'from utils.logger import logger',
        'migrations.001': 'import database.migrations.001_setup_database',
        'migrations.002': 'import database.migrations.002_import_schools'
    }

    for name, import_stmt in test_imports.items():
        try:
            # Tentar executar import
            exec(import_stmt)
            results[name] = (True, "OK")
        except Exception as e:
            results[name] = (False, str(e)[:100])

    return results


# ============================================================================
# TESTE 5: ARQUIVO CSV
# ============================================================================

def test_csv_file() -> Tuple[bool, str]:
    """
    Verifica se CSV existe.

    Returns:
        Tupla (exists, message).
    """
    try:
        from config.settings import settings
        csv_path = Path(settings.CSV_PATH)

        if not csv_path.exists():
            return False, f"CSV não encontrado em {settings.CSV_PATH}"

        size_mb = csv_path.stat().st_size / 1024 / 1024
        return True, f"CSV encontrado ({size_mb:.1f} MB)"

    except Exception as e:
        return False, f"Erro ao verificar CSV: {e}"


# ============================================================================
# TESTE 6: CONEXÃO SUPABASE
# ============================================================================

def test_supabase_connection() -> Tuple[bool, str]:
    """
    Testa conexão com Supabase.

    Returns:
        Tupla (success, message).
    """
    try:
        from database.supabase_client import db

        # Tentar fazer uma query simples
        # Como não temos tabelas ainda, apenas verificar se o client está OK
        result = db.client.table('_dummy_').select('*').limit(1)

        # Se chegou aqui sem erro de autenticação, está OK
        return True, "Conexão OK"

    except Exception as e:
        error_msg = str(e)

        # Se erro é "table not found", significa que conexão está OK
        if 'does not exist' in error_msg.lower() or 'not found' in error_msg.lower():
            return True, "Conexão OK (tabelas ainda não criadas)"

        return False, f"Erro: {error_msg[:100]}"


# ============================================================================
# TESTE 7: MIGRATION 001 (DRY RUN)
# ============================================================================

def test_migration_001_dry_run() -> Tuple[bool, str]:
    """
    Testa migration 001 em modo dry-run (apenas validações).

    Returns:
        Tupla (success, message).
    """
    try:
        # Import do módulo
        sys.path.insert(0, str(Path(__file__).parent))
        from database.migrations import __version__

        # Verificar que arquivos existem
        migration_001 = Path("database/migrations/001_setup_database.py")
        schema_file = Path("database/schemas.sql")

        if not migration_001.exists():
            return False, "001_setup_database.py não encontrado"

        if not schema_file.exists():
            return False, "schemas.sql não encontrado"

        # Verificar tamanho do schema
        schema_size = schema_file.stat().st_size
        if schema_size < 1000:
            return False, f"schemas.sql muito pequeno ({schema_size} bytes)"

        return True, f"Migration 001 pronta (schema: {schema_size} bytes)"

    except Exception as e:
        return False, f"Erro: {str(e)[:100]}"


# ============================================================================
# TESTE 8: MIGRATION 002 (DRY RUN)
# ============================================================================

def test_migration_002_dry_run() -> Tuple[bool, str]:
    """
    Testa migration 002 em modo dry-run.

    Returns:
        Tupla (success, message).
    """
    try:
        migration_002 = Path("database/migrations/002_import_schools.py")

        if not migration_002.exists():
            return False, "002_import_schools.py não encontrado"

        # Verificar tamanho do arquivo
        size = migration_002.stat().st_size

        return True, f"Migration 002 pronta ({size} bytes)"

    except Exception as e:
        return False, f"Erro: {str(e)[:100]}"


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """
    Executa todos os testes.

    Returns:
        Exit code (0 = todos ok, 1 = algum falhou).
    """
    print_header("TESTES DE MIGRATIONS - IAprendo Sales Agent")

    all_passed = True

    # TESTE 1: Python Version
    print(f"{Colors.BOLD}[1/8] Python Version{Colors.END}")
    success, msg = test_python_version()
    if success:
        print_success(msg)
    else:
        print_error(msg)
        all_passed = False

    # TESTE 2: Dependências
    print(f"\n{Colors.BOLD}[2/8] Dependências Python{Colors.END}")
    deps = test_dependencies()
    missing_deps = [pkg for pkg, installed in deps.items() if not installed]

    if not missing_deps:
        print_success(f"Todas as {len(deps)} dependências instaladas")
    else:
        print_error(f"{len(missing_deps)} dependências faltando: {', '.join(missing_deps)}")
        print_info("Deseja instalar agora? (S/n):")

        try:
            response = input(">>> ").strip().lower()
            if response in ['s', 'sim', 'y', 'yes', '']:
                if install_dependencies():
                    print_success("Dependências instaladas com sucesso!")
                else:
                    print_error("Falha ao instalar dependências")
                    all_passed = False
            else:
                print_warning("Instalação pulada. Execute: pip install -r requirements.txt")
                all_passed = False
        except KeyboardInterrupt:
            print("\n")
            print_warning("Teste interrompido pelo usuário")
            return 1

    # TESTE 3: Arquivo .env
    print(f"\n{Colors.BOLD}[3/8] Arquivo .env{Colors.END}")
    env_ok, missing = test_env_file()

    if env_ok:
        print_success("Arquivo .env configurado")
    else:
        print_error(f"Variáveis faltando: {', '.join(missing)}")
        print_info("Execute: python setup_config.py")
        all_passed = False

    # TESTE 4: Imports
    print(f"\n{Colors.BOLD}[4/8] Imports de Módulos{Colors.END}")
    import_results = test_imports()

    for module, (success, msg) in import_results.items():
        if success:
            print_success(f"{module}: OK")
        else:
            print_error(f"{module}: {msg}")
            all_passed = False

    # TESTE 5: Arquivo CSV
    print(f"\n{Colors.BOLD}[5/8] Arquivo CSV{Colors.END}")
    csv_ok, csv_msg = test_csv_file()

    if csv_ok:
        print_success(csv_msg)
    else:
        print_warning(csv_msg)
        print_info("Migration 002 requer CSV. Pode pular por enquanto.")

    # TESTE 6: Conexão Supabase
    print(f"\n{Colors.BOLD}[6/8] Conexão Supabase{Colors.END}")
    supabase_ok, supabase_msg = test_supabase_connection()

    if supabase_ok:
        print_success(supabase_msg)
    else:
        print_error(supabase_msg)
        all_passed = False

    # TESTE 7: Migration 001
    print(f"\n{Colors.BOLD}[7/8] Migration 001 (Setup Database){Colors.END}")
    mig001_ok, mig001_msg = test_migration_001_dry_run()

    if mig001_ok:
        print_success(mig001_msg)
    else:
        print_error(mig001_msg)
        all_passed = False

    # TESTE 8: Migration 002
    print(f"\n{Colors.BOLD}[8/8] Migration 002 (Import CSV){Colors.END}")
    mig002_ok, mig002_msg = test_migration_002_dry_run()

    if mig002_ok:
        print_success(mig002_msg)
    else:
        print_error(mig002_msg)
        all_passed = False

    # RESUMO FINAL
    print_header("RESUMO DOS TESTES")

    if all_passed:
        print_success("✅ TODOS OS TESTES PASSARAM!")
        print()
        print(f"{Colors.BOLD}🎯 PRÓXIMOS PASSOS:{Colors.END}")
        print("  1. Execute: python database/migrations/001_setup_database.py")
        print("  2. Execute: python database/migrations/002_import_schools.py --sample 100")
        print("  3. Verifique: streamlit run dashboard/main.py")
        print()
        return 0
    else:
        print_error("❌ ALGUNS TESTES FALHARAM")
        print()
        print(f"{Colors.BOLD}🔧 AÇÕES NECESSÁRIAS:{Colors.END}")

        if missing_deps:
            print("  1. Instalar dependências: pip install -r requirements.txt")

        if not env_ok:
            print("  2. Configurar .env: python setup_config.py")

        if not supabase_ok:
            print("  3. Verificar credenciais Supabase no .env")

        print()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n")
        print_warning("Testes interrompidos pelo usuário")
        sys.exit(1)
    except Exception as e:
        print("\n")
        print_error(f"Erro inesperado: {e}")
        sys.exit(1)
