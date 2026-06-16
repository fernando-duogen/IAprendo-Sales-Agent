# Database Migrations - Guia de Execução

## 📋 Visão Geral

Este diretório contém 2 migrations que configuram o banco de dados do sistema IAprendo Sales Agent:

1. **001_setup_database.py** - Cria estrutura do banco (7 tabelas, ~20 índices, 4 triggers, 2 views)
2. **002_import_schools.py** - Importa CSV do MEC (210k escolas) com 4 filtros ICP

---

## 🚀 Ordem de Execução

### Pré-requisitos

```bash
# 1. Configurar .env
python setup_config.py

# 2. Verificar que variáveis estão configuradas
# - SUPABASE_URL
# - SUPABASE_KEY
# - CSV_PATH
# - TARGET_CITY
# - TARGET_STATE
```

### Migration 001: Setup Database

**Objetivo**: Criar as 7 tabelas principais do sistema.

```bash
# Executar
python database/migrations/001_setup_database.py
```

**O que faz**:
- ✅ Valida SUPABASE_URL e SUPABASE_KEY
- ✅ Lê `database/schemas.sql` (16KB)
- ✅ Parseia ~45 statements SQL
- ⚠️ **IMPORTANTE**: O script pede que você execute o SQL manualmente no Supabase SQL Editor
- ✅ Verifica que as 7 tabelas foram criadas

**Saída esperada**:
```
======================================================================
  DATABASE SETUP MIGRATION - RELATÓRIO FINAL
======================================================================

📊 EXECUÇÃO SQL:
  Total de statements: 45
  ✓ Sucesso: 45
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

**Troubleshooting**:

| Erro | Solução |
|------|---------|
| `SUPABASE_URL não configurada` | Execute `python setup_config.py` |
| `schemas.sql não encontrado` | Verifique que existe em `database/schemas.sql` |
| `Tabelas críticas não criadas` | Execute o SQL manualmente no Supabase SQL Editor |

---

### Migration 002: Import Schools

**Objetivo**: Importar escolas do CSV do MEC aplicando 4 filtros ICP.

#### Modo Teste (RECOMENDADO primeiro)

```bash
# Teste com 100 escolas
python database/migrations/002_import_schools.py --sample 100
```

#### Modo Completo

```bash
# Importação completa (210k linhas)
python database/migrations/002_import_schools.py
```

#### Modo Debug (sem validação)

```bash
# Para debug rápido
python database/migrations/002_import_schools.py --sample 50 --skip-validation
```

**O que faz**:
1. ✅ Valida que CSV existe (`data/raw/escolas_brasil.csv`)
2. ✅ Valida que tabela `companies` foi criada (migration 001)
3. ✅ Carrega CSV (com encoding configurável)
4. ✅ Aplica 4 filtros ICP:
   - **Filtro 1**: Restrição = "FUNCIONAMENTO E SEM RESTRIÇÃO"
   - **Filtro 2**: Cidade = `TARGET_CITY` AND Estado = `TARGET_STATE`
   - **Filtro 3**: Níveis de ensino contém "fundamental" OU "médio"
   - **Filtro 4**: Tipo de escola in `TARGET_SCHOOL_TYPES`
5. ✅ Processa em batches de 500 escolas
6. ✅ Verifica duplicatas por código INEP (evita duplicação)
7. ✅ Valida dados (coordenadas, estado, campos obrigatórios)
8. ✅ Insere com `status='raw'` e `source='csv_import'`

**Saída esperada**:

```
======================================================================
  CSV IMPORT MIGRATION - RELATÓRIO FINAL
======================================================================

🚀 MODO: Importação completa

🔍 FILTROS APLICADOS:
  Total inicial no CSV: 210,000
  ↓ Filtro 1 (Restrição): 185,000
  ↓ Filtro 2 (Localização): 3,500
  ↓ Filtro 3 (Níveis): 2,200
  ↓ Filtro 4 (Tipo): 1,500
  ✓ Total aprovado: 1,500
  Taxa de aprovação: 0.71%

📥 IMPORTAÇÃO:
  Escolas processadas: 1,500
  ✓ Inseridas: 1,485
  ⊗ Duplicatas: 10
  ✗ Inválidas: 3
  ⚠  Erros: 2
  Taxa de sucesso: 99.00%

📊 RESUMO:
  1,485 escolas adicionadas ao banco
  Status: raw
  Tabela: companies

🎯 PRÓXIMOS PASSOS:
  1. Verificar dados: streamlit run dashboard/main.py
  2. Qualificar escolas: python workflows/daily_pipeline.py
  3. (Opcional) Geocodificar: python -m tools.geocoder
  4. (Opcional) Buscar telefones: python -m tools.phone_finder

======================================================================

⏱️  Tempo total: 142.3 segundos
```

**Troubleshooting**:

| Erro | Solução |
|------|---------|
| `CSV não encontrado` | Coloque o CSV em `data/raw/escolas_brasil.csv` ou ajuste `CSV_PATH` no `.env` |
| `Tabela companies não encontrada` | Execute migration 001 primeiro |
| `Nenhuma escola aprovada nos filtros` | Verifique `TARGET_CITY`, `TARGET_STATE`, `TARGET_SCHOOL_TYPES` no `.env` |
| `Muitas duplicatas` | Normal se executar múltiplas vezes - duplicatas são ignoradas |

---

## 📊 Verificação Pós-Migração

### Via SQL (Supabase SQL Editor)

```sql
-- Contar total de escolas importadas
SELECT COUNT(*) FROM companies WHERE status = 'raw';

-- Ver primeiras 10 escolas
SELECT name, city, state, inep_code FROM companies LIMIT 10;

-- Verificar distribuição por cidade
SELECT city, state, COUNT(*) as total
FROM companies
GROUP BY city, state
ORDER BY total DESC;
```

### Via Dashboard

```bash
streamlit run dashboard/main.py
```

Navegue para a página "Companies" para ver as escolas importadas.

---

## 🔄 Re-executando Migrations

### Migration 001 (Setup)
- ✅ **Idempotente**: Pode re-executar sem problemas
- ⚠️ Se tabelas já existem, vai detectar e reportar

### Migration 002 (Import)
- ✅ **Idempotente**: Detecta duplicatas automaticamente por INEP
- ✅ Escolas já existentes são ignoradas (não sobrescritas)
- ✅ Seguro executar múltiplas vezes

---

## 📝 Logs

Todos os logs estruturados em JSON ficam em:

```bash
# Log principal
tail -f logs/application.log | grep "migration"

# Apenas erros
tail -f logs/errors.log
```

---

## 🎯 Próximos Passos

Após migrations concluídas:

1. **Verificar dados**: `streamlit run dashboard/main.py`
2. **Qualificar leads**: `python workflows/daily_pipeline.py`
3. **(Opcional) Geocodificar**: `python -m tools.geocoder`
4. **(Opcional) Buscar telefones**: `python -m tools.phone_finder`

---

## ⚙️ Configurações Importantes

### .env - Variáveis para Migration 002

```env
# CSV
CSV_PATH=data/raw/escolas_brasil.csv
CSV_ENCODING=utf-8

# ICP - Filtros de Perfil de Cliente Ideal
TARGET_CITY=Porto Alegre
TARGET_STATE=RS
TARGET_SCHOOL_TYPES=publica,privada
TARGET_EDUCATION_LEVELS=fundamental,medio

# Mapeamento de Colunas (ajustar se CSV diferente)
CSV_COL_NAME=Escola
CSV_COL_INEP=Código INEP
CSV_COL_CITY=Município
CSV_COL_STATE=UF
CSV_COL_RESTRICTION=Restrição de Atendimento
CSV_COL_LEVELS=Etapas e Modalidade de Ensino Oferecidas
CSV_COL_ADMIN_DEPENDENCY=Dependência Administrativa
# ... (ver .env.example para lista completa)
```

---

## 📈 Estatísticas Esperadas

### Filtros (exemplo Porto Alegre, RS)

| Etapa | Escolas | % do Total |
|-------|---------|------------|
| CSV Total | 210,000 | 100% |
| Após Filtro 1 (Restrição) | 185,000 | 88% |
| Após Filtro 2 (Localização) | 3,500 | 1.7% |
| Após Filtro 3 (Níveis) | 2,200 | 1.0% |
| Após Filtro 4 (Tipo) | 1,500 | 0.7% |

**Taxa de aprovação típica**: 0.5% - 1.5% (varia por cidade)

### Performance

| Operação | Tempo Estimado |
|----------|----------------|
| 001 (Setup) | 5-10 segundos |
| 002 (Sample 100) | 10-20 segundos |
| 002 (Completo 210k) | 2-5 minutos |

---

## 🛡️ Segurança e Boas Práticas

### ✅ SEMPRE
- Execute `--sample` primeiro para validar filtros
- Verifique `TARGET_*` antes de importação completa
- Monitore logs durante importação longa
- Faça backup do Supabase antes de re-executar

### ❌ NUNCA
- Modifique código INEP manualmente no banco
- Execute importação completa sem testar com sample
- Ignore erros críticos (tabelas não criadas)
- Execute 002 antes de 001

---

## 📞 Suporte

- **Logs**: `logs/application.log` (JSON estruturado)
- **Erros**: `logs/errors.log` (apenas ERROR+)
- **Documentação**: `docs/IMPLEMENTATION.md`

---

**Versão**: 1.0.0
**Última Atualização**: 2026-02-10
