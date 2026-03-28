"""Versão não-interativa do test_migrations.py"""
import sys
from pathlib import Path

# Import do teste original
sys.path.insert(0, str(Path(__file__).parent))

# Executar testes
from test_migrations import (
    test_python_version,
    test_dependencies,
    test_env_file,
    test_imports,
    test_csv_file,
    test_supabase_connection,
    test_migration_001_dry_run,
    test_migration_002_dry_run
)

print("="*70)
print("  TESTES AUTOMATIZADOS - IAprendo Sales Agent")
print("="*70)
print()

# Teste 1
print("[1/8] Python Version")
success, msg = test_python_version()
print(f"  {'[OK]' if success else '[X]'} {msg}")
print()

# Teste 2
print("[2/8] Dependências Python")
deps = test_dependencies()
missing = [pkg for pkg, installed in deps.items() if not installed]
if not missing:
    print(f"  [OK] Todas as {len(deps)} dependências instaladas")
else:
    print(f"  [X] {len(missing)} faltando: {', '.join(missing)}")
print()

# Teste 3
print("[3/8] Arquivo .env")
env_ok, missing_vars = test_env_file()
if env_ok:
    print("  [OK] Arquivo .env configurado")
else:
    print(f"  [X] Variáveis faltando: {', '.join(missing_vars)}")
print()

# Teste 4
print("[4/8] Imports de Módulos")
imports = test_imports()
for module, (success, msg) in imports.items():
    status = "[OK]" if success else "[X]"
    print(f"  {status} {module}")
print()

# Teste 5
print("[5/8] Arquivo CSV")
csv_ok, csv_msg = test_csv_file()
print(f"  {'[OK]' if csv_ok else '[!]'} {csv_msg}")
print()

# Teste 6
print("[6/8] Conexão Supabase")
supabase_ok, supabase_msg = test_supabase_connection()
print(f"  {'[OK]' if supabase_ok else '[X]'} {supabase_msg}")
print()

# Teste 7
print("[7/8] Migration 001")
mig001_ok, mig001_msg = test_migration_001_dry_run()
print(f"  {'[OK]' if mig001_ok else '[X]'} {mig001_msg}")
print()

# Teste 8
print("[8/8] Migration 002")
mig002_ok, mig002_msg = test_migration_002_dry_run()
print(f"  {'[OK]' if mig002_ok else '[X]'} {mig002_msg}")
print()

# Resumo
print("="*70)
print("  RESUMO")
print("="*70)

all_ok = success and not missing and env_ok and supabase_ok and mig001_ok and mig002_ok

if all_ok:
    print()
    print("[OK] TODOS OS TESTES PASSARAM!")
    print()
    print("PRÓXIMOS PASSOS:")
    print("  1. python database/migrations/001_setup_database.py")
    print("  2. python database/migrations/002_import_schools.py --sample 10")
    print()
else:
    print()
    print("[X] ALGUNS TESTES FALHARAM")
    print()
    if not env_ok:
        print("AÇÃO: Configure .env com suas credenciais")
        print("  python setup_config.py")
    if not supabase_ok:
        print("AÇÃO: Verifique credenciais Supabase no .env")
    print()
