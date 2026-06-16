# 🧪 Guia de Testes - Database Migrations

Este guia mostra como testar as migrations do sistema IAprendo Sales Agent de forma progressiva e segura.

---

## 📋 Índice

1. [Pré-requisitos](#1-pré-requisitos)
2. [Teste Automatizado (Recomendado)](#2-teste-automatizado-recomendado)
3. [Testes Manuais Passo a Passo](#3-testes-manuais-passo-a-passo)
4. [Validação Pós-Migração](#4-validação-pós-migração)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Pré-requisitos

### 1.1. Verificar Python

```bash
python --version
# Deve retornar: Python 3.11.x ou 3.12.x ou superior
```

### 1.2. Verificar pip

```bash
pip --version
# Deve retornar: pip 23.x ou superior
```

### 1.3. Clonar/Ter o Projeto

```bash
cd "C:\Users\Fernando Nienaber\LAUFEN PARTICIPACOES LTDA\All Company - Documentos\ativos\duogen\produto\mvp\empresarial\iaprendo\agente-de-vendas"
```

---

## 2. Teste Automatizado (Recomendado)

### 🚀 Opção Rápida: Script Completo

Execute o script de testes automatizado que verifica tudo:

```bash
python test_migrations.py
```

**O que este script testa**:

- ✅ Versão do Python (3.11+)
- ✅ Dependências instaladas (pandas, supabase, etc)
- ✅ Arquivo `.env` configurado
- ✅ Imports dos módulos funcionando
- ✅ Arquivo CSV existe (se disponível)
- ✅ Conexão com Supabase
- ✅ Migrations 001 e 002 prontas

**Saída esperada**:

```
======================================================================
  TESTES DE MIGRATIONS - IAprendo Sales Agent
======================================================================

[1/8] Python Version
✓ Python 3.11.5 OK

[2/8] Dependências Python
✓ Todas as 6 dependências instaladas

[3/8] Arquivo .env
✓ Arquivo .env configurado

[4/8] Imports de Módulos
✓ config.settings: OK
✓ database.supabase_client: OK
✓ utils.logger: OK
✓ migrations.001: OK
✓ migrations.002: OK

[5/8] Arquivo CSV
⚠ CSV não encontrado em data/raw/escolas_brasil.csv
  Migration 002 requer CSV. Pode pular por enquanto.

[6/8] Conexão Supabase
✓ Conexão OK (tabelas ainda não criadas)

[7/8] Migration 001 (Setup Database)
✓ Migration 001 pronta (schema: 16437 bytes)

[8/8] Migration 002 (Import CSV)
✓ Migration 002 pronta (29821 bytes)

======================================================================
  RESUMO DOS TESTES
======================================================================

✅ TODOS OS TESTES PASSARAM!

🎯 PRÓXIMOS PASSOS:
  1. Execute: python database/migrations/001_setup_database.py
  2. Execute: python database/migrations/002_import_schools.py --sample 100
  3. Verifique: streamlit run dashboard/main.py
```

---

## 3. Testes Manuais Passo a Passo

Se preferir testar manualmente ou se o script automatizado falhar:

### 3.1. Instalar Dependências

```bash
# Verificar se requirements.txt existe
ls requirements.txt

# Instalar dependências
pip install -r requirements.txt

# Verificar instalação
pip list | grep -E "pandas|supabase|python-dotenv|anthropic"
```

**Dependências principais**:
- `pandas` - Leitura do CSV
- `supabase` - Cliente do banco
- `python-dotenv` - Carregar .env
- `pythonjsonlogger` - Logging JSON
- `anthropic` - API Claude (futuro)
- `streamlit` - Dashboard (futuro)

### 3.2. Configurar .env

```bash
# Verificar se .env existe
ls .env

# Se não existir, criar a partir do exemplo
cp .env.example .env

# OU executar wizard de configuração
python setup_config.py
```

**Variáveis obrigatórias para migrations**:

```env
# Supabase (OBRIGATÓRIO)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-aqui

# Anthropic (OBRIGATÓRIO para qualificação IA - futuro)
ANTHROPIC_API_KEY=sk-ant-...

# Email (OBRIGATÓRIO)
YOUR_EMAIL=seu@email.com

# CSV (OBRIGATÓRIO para migration 002)
CSV_PATH=data/raw/escolas_brasil.csv
CSV_ENCODING=utf-8

# ICP - Filtros (OBRIGATÓRIO para migration 002)
TARGET_CITY=Porto Alegre
TARGET_STATE=RS
TARGET_SCHOOL_TYPES=publica,privada
TARGET_EDUCATION_LEVELS=fundamental,medio
```

### 3.3. Testar Imports

```bash
# Testar import de settings
python -c "from config.settings import settings; print('Settings OK')"

# Testar import de database client
python -c "from database.supabase_client import db; print('Database client OK')"

# Testar import de logger
python -c "from utils.logger import logger; print('Logger OK')"
```

**Saída esperada**:
```
Settings OK
Database client OK
Logger OK
```

### 3.4. Testar Conexão Supabase

```bash
python -c "
from database.supabase_client import db
from config.settings import settings
print(f'Supabase URL: {settings.SUPABASE_URL[:30]}...')
print('Conexão: OK')
"
```

**Saída esperada**:
```
Supabase URL: https://abc123.supabase.co...
Conexão: OK
```

### 3.5. Verificar Arquivos de Migration

```bash
# Listar migrations
ls -lh database/migrations/

# Verificar sintaxe Python
python -m py_compile database/migrations/001_setup_database.py
python -m py_compile database/migrations/002_import_schools.py

# Se não der erro, sintaxe está OK
echo "Sintaxe OK!"
```

### 3.6. Teste da Migration 001 (Setup Database)

**Teste Seco** (sem executar, apenas validar):

```bash
# Verificar que schemas.sql existe
ls -lh database/schemas.sql

# Contar statements SQL
grep -c "CREATE" database/schemas.sql
# Deve retornar ~15 (tabelas, índices, funções, views)
```

**Teste Real** (executar):

```bash
python database/migrations/001_setup_database.py
```

**Saída esperada**:
```
======================================================================
  DATABASE SETUP MIGRATION - 001
======================================================================

📋 Validando pré-requisitos...
   ✓ Pré-requisitos OK

📄 Lendo schema SQL...
   ✓ Schema lido (16437 bytes)

🔍 Parseando SQL statements...
   ✓ 45 statements parseados

⚠️  ATENÇÃO:
   O Supabase Python client não suporta execução SQL direta.
   Por favor, execute o seguinte:

   1. Acesse o Supabase SQL Editor:
      https://seu-projeto.supabase.com/sql/new
   2. Copie o conteúdo de: database/schemas.sql
   3. Cole no editor e execute (RUN)

   Após executar, este script verificará as tabelas...

Pressione ENTER após executar o SQL no Supabase SQL Editor...
```

**Ação necessária**:

1. Abra o Supabase SQL Editor no navegador
2. Copie todo o conteúdo de `database/schemas.sql`
3. Cole no editor
4. Clique em "RUN" ou pressione Ctrl+Enter
5. Volte ao terminal e pressione ENTER

**Saída após pressionar ENTER**:
```
🔍 Verificando tabelas criadas...
   ✓ 7/7 tabelas verificadas

======================================================================
  DATABASE SETUP MIGRATION - RELATÓRIO FINAL
======================================================================

📊 EXECUÇÃO SQL:
  Total de statements: 45
  ✓ Sucesso: 7
  ✗ Falhas: 0

📋 TABELAS CRIADAS:
  ✓ companies [CRÍTICA]
  ✓ contacts
  ✓ approval_queue [CRÍTICA]
  ✓ interactions
  ✓ meetings
  ✓ api_usage [CRÍTICA]
  ✓ campaigns

📈 RESUMO: 7/7 tabelas criadas

✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!
======================================================================
```

### 3.7. Teste da Migration 002 (Import CSV)

**Pré-requisito**: Ter o CSV do MEC em `data/raw/escolas_brasil.csv`

**Teste com Sample Pequeno** (RECOMENDADO primeiro):

```bash
# Teste com apenas 10 escolas
python database/migrations/002_import_schools.py --sample 10
```

**Saída esperada**:
```
======================================================================
  CSV IMPORT MIGRATION - 002
======================================================================

🧪 MODO TESTE: Importando apenas 10 escolas

📋 Validando pré-requisitos...
   ✓ Pré-requisitos OK

📄 Carregando CSV...
   ✓ 10 escolas carregadas

🔍 Aplicando filtros ICP...
   ✓ 2 escolas aprovadas nos filtros

📥 Importando 2 escolas em 1 batches de 500...

  Batch 1/1: 100.0% (2/2) | ✓ 2 inseridas | ⊗ 0 duplicatas | ✗ 0 inválidas | ⚠ 0 erros

======================================================================
  CSV IMPORT MIGRATION - RELATÓRIO FINAL
======================================================================

🚀 MODO: Importação de amostra (10 linhas)

🔍 FILTROS APLICADOS:
  Total inicial no CSV: 10
  ↓ Filtro 1 (Restrição): 8
  ↓ Filtro 2 (Localização): 3
  ↓ Filtro 3 (Níveis): 2
  ↓ Filtro 4 (Tipo): 2
  ✓ Total aprovado: 2
  Taxa de aprovação: 20.00%

📥 IMPORTAÇÃO:
  Escolas processadas: 2
  ✓ Inseridas: 2
  ⊗ Duplicatas: 0
  ✗ Inválidas: 0
  ⚠  Erros: 0
  Taxa de sucesso: 100.00%

📊 RESUMO:
  2 escolas adicionadas ao banco
  Status: raw
  Tabela: companies

🎯 PRÓXIMOS PASSOS:
  1. Verificar dados: streamlit run dashboard/main.py
  2. Qualificar escolas: python workflows/daily_pipeline.py

======================================================================

⏱️  Tempo total: 3.2 segundos
```

**Teste com Sample Maior** (se o pequeno funcionou):

```bash
# Teste com 100 escolas
python database/migrations/002_import_schools.py --sample 100
```

**Importação Completa** (se tudo estiver OK):

```bash
# Importação completa (210k linhas - demora 2-5 minutos)
python database/migrations/002_import_schools.py
```

---

## 4. Validação Pós-Migração

### 4.1. Verificar Dados via SQL

Acesse o Supabase SQL Editor e execute:

```sql
-- Contar total de escolas
SELECT COUNT(*) as total FROM companies;

-- Ver primeiras 5 escolas
SELECT name, city, state, inep_code, status
FROM companies
LIMIT 5;

-- Verificar distribuição por status
SELECT status, COUNT(*) as total
FROM companies
GROUP BY status
ORDER BY total DESC;

-- Verificar distribuição por cidade
SELECT city, state, COUNT(*) as total
FROM companies
GROUP BY city, state
ORDER BY total DESC;
```

### 4.2. Verificar Logs

```bash
# Ver últimas 50 linhas do log
tail -n 50 logs/application.log

# Ver apenas logs de migração
grep "migration" logs/application.log | tail -n 20

# Ver apenas erros
tail -n 50 logs/errors.log
```

### 4.3. Verificar via Python

```python
# Execute no Python interativo
python

>>> from database.supabase_client import db

# Contar escolas
>>> companies = db.get_companies_by_status('raw', limit=1000)
>>> print(f"Total de escolas com status 'raw': {len(companies)}")

# Ver primeira escola
>>> if companies:
...     first = companies[0]
...     print(f"Nome: {first['name']}")
...     print(f"Cidade: {first['city']}")
...     print(f"INEP: {first['inep_code']}")
...     print(f"Status: {first['status']}")
```

---

## 5. Troubleshooting

### Problema 1: `ModuleNotFoundError: No module named 'dotenv'`

**Causa**: Dependências não instaladas.

**Solução**:
```bash
pip install -r requirements.txt
```

### Problema 2: `SUPABASE_URL não configurada`

**Causa**: Arquivo `.env` não existe ou está incompleto.

**Solução**:
```bash
# Opção 1: Wizard de configuração
python setup_config.py

# Opção 2: Copiar exemplo e editar
cp .env.example .env
# Editar .env com suas credenciais
```

### Problema 3: `CSV não encontrado`

**Causa**: Arquivo CSV não está no caminho configurado.

**Solução**:
```bash
# Verificar caminho configurado
python -c "from config.settings import settings; print(settings.CSV_PATH)"

# Criar diretório se não existir
mkdir -p data/raw

# Colocar CSV no diretório correto
# OU ajustar CSV_PATH no .env
```

### Problema 4: `Tabela companies não encontrada`

**Causa**: Migration 001 não foi executada.

**Solução**:
```bash
# Executar migration 001 primeiro
python database/migrations/001_setup_database.py
```

### Problema 5: `Nenhuma escola aprovada nos filtros`

**Causa**: Filtros ICP muito restritivos para o CSV carregado.

**Solução**:
```bash
# Verificar configurações ICP
python -c "
from config.settings import settings
print(f'Cidade: {settings.TARGET_CITY}')
print(f'Estado: {settings.TARGET_STATE}')
print(f'Tipos: {settings.TARGET_SCHOOL_TYPES}')
print(f'Níveis: {settings.TARGET_EDUCATION_LEVELS}')
"

# Ajustar no .env se necessário
# Ex: Para testar com mais escolas, adicionar mais tipos
# TARGET_SCHOOL_TYPES=publica,privada,municipal,estadual
```

### Problema 6: `Erro de conexão com Supabase`

**Causa**: URL ou chave inválida, ou projeto Supabase pausado.

**Solução**:
```bash
# 1. Verificar URL e chave no .env
cat .env | grep SUPABASE

# 2. Acessar Supabase Dashboard
# https://app.supabase.com

# 3. Verificar se projeto está ativo (não pausado)

# 4. Regenerar chave se necessário
# Settings > API > anon/public key
```

### Problema 7: Muitas duplicatas na importação

**Causa**: Script foi executado múltiplas vezes.

**Solução**:
```
✅ Isso é NORMAL e esperado!

O script detecta duplicatas automaticamente por código INEP
e as ignora, não sobrescrevendo dados existentes.

Se quiser limpar e re-importar do zero:
  1. Acesse Supabase SQL Editor
  2. Execute: DELETE FROM companies WHERE status = 'raw';
  3. Re-execute: python database/migrations/002_import_schools.py
```

---

## 📊 Checklist de Validação

Use este checklist após executar as migrations:

- [ ] Python 3.11+ instalado
- [ ] Dependências instaladas (`pip list | grep supabase`)
- [ ] Arquivo `.env` configurado
- [ ] Conexão Supabase OK
- [ ] Migration 001 executada (7 tabelas criadas)
- [ ] Tabelas verificadas no Supabase SQL Editor
- [ ] Migration 002 testada com `--sample 10`
- [ ] Escolas visíveis na tabela `companies`
- [ ] Logs sem erros críticos (`tail logs/errors.log`)
- [ ] Pronto para próxima fase (Agentes IA)

---

## 🎯 Próximos Passos

Após migrations concluídas com sucesso:

1. **Dashboard** (opcional, se Streamlit instalado):
   ```bash
   streamlit run dashboard/main.py
   ```

2. **Implementar Agentes IA** (Fase 2):
   - Qualifier Agent (Claude Haiku 4.5)
   - Enricher Agent (APIs de enriquecimento)
   - Writer Agent (Claude Sonnet 4.5)

3. **Geocodificar escolas** (opcional):
   ```bash
   python -m tools.geocoder
   ```

4. **Buscar telefones** (opcional):
   ```bash
   python -m tools.phone_finder
   ```

---

## 📞 Suporte

- **Logs**: `logs/application.log` (JSON estruturado)
- **Erros**: `logs/errors.log`
- **Documentação**: `docs/IMPLEMENTATION.md`
- **Migrations**: `database/migrations/README.md`

---

**Boa sorte com os testes! 🚀**
