# 🚀 Quick Start - Testando Migrations em 5 Minutos

Este guia mostra **exatamente o que fazer agora** para testar as migrations.

---

## 📋 Opção 1: Teste Automatizado (Mais Fácil)

### Passo 1: Executar Script de Testes

```bash
python test_migrations.py
```

**O que vai acontecer**:

1. ✅ Verifica Python 3.11+
2. ❌ Detecta que dependências faltam
3. ❓ Pergunta se quer instalar agora

**Responda**: `s` ou `sim` ou apenas `ENTER`

O script vai instalar tudo automaticamente!

### Passo 2: Após Instalação

O script vai continuar verificando:

4. ✅ Arquivo `.env` configurado (ou pede para configurar)
5. ✅ Conexão com Supabase
6. ✅ Migrations prontas para executar

### Passo 3: Seguir Próximos Passos

No final, o script vai mostrar:

```
🎯 PRÓXIMOS PASSOS:
  1. Execute: python database/migrations/001_setup_database.py
  2. Execute: python database/migrations/002_import_schools.py --sample 100
  3. Verifique: streamlit run dashboard/main.py
```

---

## 📋 Opção 2: Manual (Passo a Passo)

Se preferir fazer manualmente:

### Passo 1: Instalar Dependências

```bash
pip install -r requirements.txt
```

Isso vai instalar ~10 pacotes:
- pandas
- supabase
- python-dotenv
- pythonjsonlogger
- streamlit
- anthropic
- etc

**Tempo**: 1-2 minutos

### Passo 2: Configurar .env

Se ainda não tem `.env`:

```bash
# Opção A: Wizard interativo (recomendado)
python setup_config.py

# Opção B: Copiar exemplo e editar
cp .env.example .env
# Editar .env com suas credenciais
```

**Variáveis obrigatórias**:
```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-aqui
ANTHROPIC_API_KEY=sk-ant-...
YOUR_EMAIL=seu@email.com
CSV_PATH=data/raw/escolas_brasil.csv
TARGET_CITY=Porto Alegre
TARGET_STATE=RS
```

### Passo 3: Testar Conexão

```bash
python -c "from database.supabase_client import db; print('Conexão OK!')"
```

**Saída esperada**: `Conexão OK!`

### Passo 4: Executar Migration 001

```bash
python database/migrations/001_setup_database.py
```

**IMPORTANTE**: O script vai pedir para você executar o SQL manualmente:

1. Acesse: https://app.supabase.com/project/SEU-PROJETO/sql/new
2. Copie o conteúdo de `database/schemas.sql`
3. Cole no editor e clique RUN
4. Volte ao terminal e pressione ENTER

**Saída esperada**: `✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!`

### Passo 5: Executar Migration 002 (Teste)

```bash
# Teste com apenas 10 escolas primeiro
python database/migrations/002_import_schools.py --sample 10
```

**Saída esperada**:
```
📥 IMPORTAÇÃO:
  Escolas processadas: 10
  ✓ Inseridas: 2-5 (depende dos filtros)
  Taxa de sucesso: 100.00%

✅ MIGRAÇÃO CONCLUÍDA!
```

### Passo 6: Verificar Dados

```bash
# Via SQL (Supabase SQL Editor)
SELECT COUNT(*) FROM companies;

# OU via Python
python -c "
from database.supabase_client import db
companies = db.get_companies_by_status('raw', limit=100)
print(f'Total de escolas: {len(companies)}')
if companies:
    print(f'Primeira escola: {companies[0][\"name\"]}')
"
```

---

## 🎯 O Que Testar Agora (Em Ordem)

### ✅ Nível 1: Básico (5 minutos)

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar .env (se ainda não fez)
python setup_config.py

# 3. Testar imports
python -c "from config.settings import settings; print('OK')"
python -c "from database.supabase_client import db; print('OK')"
```

**Esperado**: Tudo imprime `OK` sem erros

### ✅ Nível 2: Migrations (10 minutos)

```bash
# 1. Setup database
python database/migrations/001_setup_database.py
# Seguir instruções (copiar SQL para Supabase)

# 2. Verificar tabelas criadas (via Supabase SQL Editor)
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
# Deve mostrar: companies, contacts, approval_queue, etc

# 3. Importar sample de 10 escolas
python database/migrations/002_import_schools.py --sample 10

# 4. Verificar dados
SELECT COUNT(*) FROM companies;
```

**Esperado**: 2-5 escolas importadas (depende dos filtros ICP)

### ✅ Nível 3: Importação Completa (15 minutos)

Se os testes acima funcionaram:

```bash
# 1. Teste com 100 escolas
python database/migrations/002_import_schools.py --sample 100

# 2. Se OK, importação completa (210k linhas)
python database/migrations/002_import_schools.py
# Demora 2-5 minutos

# 3. Verificar total
SELECT COUNT(*) FROM companies;
# Esperado: 1000-2000 escolas (varia por cidade)
```

---

## ❌ Problemas Comuns e Soluções

### Problema: `ModuleNotFoundError: No module named 'dotenv'`

**Solução**:
```bash
pip install -r requirements.txt
```

### Problema: `SUPABASE_URL não configurada`

**Solução**:
```bash
python setup_config.py
# OU editar .env manualmente
```

### Problema: `CSV não encontrado`

**Solução**:
```bash
# Criar diretório
mkdir -p data/raw

# Colocar CSV lá
# OU ajustar CSV_PATH no .env
```

### Problema: `Nenhuma escola aprovada nos filtros`

**Solução**:
```bash
# Verificar filtros
python -c "
from config.settings import settings
print(f'Cidade: {settings.TARGET_CITY}')
print(f'Estado: {settings.TARGET_STATE}')
"

# Ajustar no .env se necessário
```

---

## 📊 Como Saber Se Funcionou?

### ✅ Sucesso no Migration 001:

```
✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!

📈 RESUMO: 7/7 tabelas criadas
```

### ✅ Sucesso no Migration 002:

```
📥 IMPORTAÇÃO:
  ✓ Inseridas: X escolas
  Taxa de sucesso: 100.00%

✅ MIGRAÇÃO CONCLUÍDA!
```

### ✅ Dados Visíveis no Supabase:

Acesse: https://app.supabase.com/project/SEU-PROJETO/editor

1. Clique em `companies` na barra lateral
2. Deve ver escolas listadas
3. Verifique campos: name, city, state, inep_code, status='raw'

---

## 🎯 Checklist de Testes

Marque conforme for fazendo:

- [ ] Python 3.11+ instalado (`python --version`)
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] Arquivo `.env` configurado (`ls .env`)
- [ ] Imports funcionando (`python -c "from config.settings import settings"`)
- [ ] Conexão Supabase OK
- [ ] Migration 001 executada (7 tabelas criadas)
- [ ] Migration 002 testada com `--sample 10`
- [ ] Dados visíveis no Supabase Table Editor
- [ ] Logs sem erros (`tail logs/errors.log`)

---

## 🚀 Próximos Passos Após Testes

Quando tudo estiver funcionando:

1. **Dashboard** (opcional):
   ```bash
   streamlit run dashboard/main.py
   ```

2. **Qualificar escolas** (Fase 2 - Agentes IA):
   ```bash
   python workflows/daily_pipeline.py
   ```

3. **Features extras** (opcional):
   ```bash
   python -m tools.geocoder        # Geocodificar
   python -m tools.phone_finder    # Buscar telefones
   ```

---

## 📞 Precisa de Ajuda?

- **Logs detalhados**: `tail -f logs/application.log`
- **Apenas erros**: `tail -f logs/errors.log`
- **Guia completo**: `TESTING.md`
- **Migrations**: `database/migrations/README.md`

---

**Comece agora**: `python test_migrations.py` 🚀
