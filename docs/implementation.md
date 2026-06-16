# 🛠️ IMPLEMENTATION.md - Guia de Implementação

> Especificações técnicas para criação do sistema

---

## 📖 Índice

1. [Estrutura de Arquivos](#-estrutura-de-arquivos)
2. [Database](#-database)
3. [Agents](#-agents)
4. [Tools & Features Extras](#-tools--features-extras)
5. [Dashboard](#-dashboard)
6. [Workflows](#-workflows)
7. [Troubleshooting](#-troubleshooting)

---

## 📁 Estrutura de Arquivos

Ver `ARCHITECTURE.md` para descrição completa de cada componente.
```
agente-vendas-iaprendo/
├── CLAUDE.md, README.md, setup_config.py
├── .env, .env.example, .gitignore, requirements.txt
├── docs/ (ARCHITECTURE.md, STANDARDS.md, IMPLEMENTATION.md)
├── config/ (settings.py, icp.py)
├── database/ (schemas.sql, supabase_client.py, migrations/)
├── agents/ (8 arquivos: filterer, qualifier, enricher, etc)
├── integrations/ (hubspot_client, hubspot_sync, webhooks)
├── tools/ (10 arquivos: APIs, geocoder, phone_finder, etc)
├── approval_queue/ (queue_manager, models)
├── workflows/ (daily_pipeline, weekly_analysis, send_approved)
├── dashboard/ (app.py, components/, pages/)
├── prompts/ (4 templates para Claude)
├── utils/ (logger, helpers, validators, metrics)
├── scripts/ (inspect_db, setup_hubspot_properties)
├── tests/ (test_agents, test_integrations, test_tools)
├── data/ (raw/, processed/, exports/)
└── logs/ (application.log, api_calls.log, errors.log)
```

**Total:** ~65 arquivos em 13 pastas

---

## 🗄️ Database

### Schema Completo

7 tabelas principais + views + triggers:
```sql
-- Tabelas
companies         -- Escolas (leads) - 30+ campos
contacts          -- Decisores - relacionados a companies
approval_queue    -- ⭐ CRÍTICO - validação humana
interactions      -- Histórico completo de contatos
meetings          -- Reuniões agendadas
api_usage         -- Controle de créditos APIs
campaigns         -- Campanhas (futuro)

-- Campos especiais em companies
inep_code TEXT UNIQUE           -- Chave única (evita duplicatas)
latitude/longitude DECIMAL      -- Geolocalização
geocoded BOOLEAN                -- Se foi geocodificado
phone_source TEXT               -- Origem: csv/google_search/manual
score INTEGER (0-100)           -- Qualificação IA
status TEXT                     -- Pipeline: raw→filtered→qualified→...

-- Índices críticos
idx_companies_inep              -- Busca por INEP
idx_companies_location          -- Busca por coordenadas (lat/lng)
idx_approval_status             -- Fila de aprovação

-- Extensões (habilitar no SQL Editor do Supabase se precisar busca por proximidade)
-- CREATE EXTENSION IF NOT EXISTS cube;
-- CREATE EXTENSION IF NOT EXISTS earthdistance;
```

Ver schema completo em: `database/schemas.sql` (fornecido no IMPLEMENTATION.md anterior)

---

## 🤖 Agents

### FilterAgent (agents/filterer.py)
**Responsabilidade:** Aplica 4 filtros obrigatórios no CSV
```python
Filtros:
1. Restrição: "ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO"
2. Localização: Porto Alegre, RS
3. Níveis: Fundamental (anos finais) E/OU Médio
4. Tipo: Pública/Privada (configurável)

Input: CSV 210k linhas
Output: ~1.500 escolas com status='filtered'
IA: Não usa
```

### QualifierAgent (agents/qualifier.py)
**Responsabilidade:** Qualifica escolas com IA
```python
Processo:
- Usa Claude Haiku 4.5 (barato)
- Prompt: prompts/qualification_prompt.txt
- Score 0-100 baseado em 4 critérios
- Priority: baixa/media/alta

Output JSON:
{
  "score": 0-100,
  "priority": "baixa|media|alta",
  "reasoning": "texto explicativo",
  "estimated_size": "pequena|media|grande",
  "innovation_signals": [...]
}

Custo: ~R$0.01/escola
```

### EnricherAgent (agents/enricher.py)
**Responsabilidade:** Enriquece dados em cascata
```python
Cascata (com fallbacks):
1. Apollo.io (se tem créditos)
2. Snov.io (se tem créditos)
3. Hunter.io (se tem créditos)
4. Web Scraping (sempre disponível)

Busca: website, tecnologias
Registra: api_usage table
Custo: R$0 (planos gratuitos)
```

### ContactFinderAgent (agents/contact_finder.py)
**Responsabilidade:** Encontra decisores
```python
Cargos alvo:
- Diretor / Diretora
- Coordenador(a) Pedagógico(a)
- Gestor(a) de Tecnologia

Estratégias:
1. LinkedIn via APIs
2. Website scraping (página Equipe)
3. Email pattern + validação

Marca: is_decision_maker=true
```

### WriterAgent (agents/writer.py) ⭐
**Responsabilidade:** Gera mensagens personalizadas
```python
Processo:
- Usa Claude Sonnet 4.5 (melhor qualidade)
- Prompt: prompts/email_writer_prompt.txt
- NUNCA usa templates
- Cada mensagem é única

Output:
{
  "subject": "...",
  "body": "...",
  "reasoning": "por que esta abordagem"
}

Custo: ~R$0.05/mensagem
```

### Outros Agents
- **ResearcherAgent**: Pesquisa contexto específico (opcional)
- **SchedulerAgent**: Gerencia sequências multi-touch
- **BaseAgent**: Classe abstrata com métodos comuns

---

## 🔧 Tools & Features Extras

### tools/geocoder.py (NOVO)
**Responsabilidade:** Buscar lat/long para escolas sem coordenadas
```python
API: Google Maps Geocoding
Input: Endereço + Município + UF
Output: (latitude, longitude)

Rate Limit: 2 chamadas/segundo
Custo: $200 créditos grátis/mês (~40k geocodificações)

Uso:
  python -m tools.geocoder
  # Processa 50 escolas por execução

Salva:
  geocoded=true
  geocode_source='google_geocoding'
```

### tools/phone_finder.py (NOVO)
**Responsabilidade:** Buscar telefones faltantes
```python
Método preferido: Google Custom Search JSON API (100 queries/dia grátis)
Alternativa: googlesearch-python (scraping, menos estável)
Alternativa: SerpAPI (100/mês grátis)

⚠️ EVITAR scraping direto do HTML do Google (contra ToS, quebra frequentemente)

Input: Nome escola + Município
Output: Telefone formatado

Rate Limit: 20 buscas/execução
Custo: Grátis (planos free)

Regex: \(?\d{2}\)?\s?\d{4,5}-?\d{4}

Uso:
  python -m tools.phone_finder
  
Salva:
  phone_source='google_search'
```

### Outros Tools
- **apollo.py, snov.py, hunter.py**: APIs de enriquecimento
- **brevo_sender.py, gmail_sender.py**: Envio de emails
- **whatsapp_sender.py**: WhatsApp (manual ou Twilio)
- **web_scraper.py**: Scraping genérico

---

## 🎨 Dashboard

### Streamlit - 6 Páginas
```python
# dashboard/app.py
import streamlit as st

st.set_page_config(
    page_title="IAprendo Sales Agent",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Navegação automática via pages/
```

### Páginas:

**1. Overview (1_overview.py)**
- Métricas gerais (leads, conversão, ROI)
- Gráfico de funil
- Últimas atividades

**2. Approval Queue ⭐ (2_approval_queue.py)**
```python
# Interface principal de aprovação
# Para cada mensagem pendente:

- Card da escola (nome, localização, score)
- Contato encontrado (nome, cargo, email)
- Reasoning da IA (por que escolheu)
- Preview da mensagem (formatado)
- Botões:
  [✅ Aprovar] [✏️ Editar] [🔄 Regenerar] [❌ Rejeitar]
  
# Editor inline com st.text_area
# Navegação: ← Anterior | 2/10 | Próximo →
```

**3. Leads (3_leads.py)**
- Tabela completa de leads
- Filtros por status, score, cidade
- Exportação CSV

**4. Campaigns (4_campaigns.py)**
- Campanhas ativas (futuro)
- Performance de cada

**5. Settings (5_settings.py)**
- Ajustar ICP dinamicamente
- Ver créditos APIs restantes
- Pausar/retomar automação

**6. Map View (6_map_view.py) - NOVO**
```python
import pydeck as pdk

# Plotar escolas em mapa
# Filtros: status, score mínimo
# Tooltip ao passar mouse
# Zoom automático em Porto Alegre

# Usa biblioteca pydeck (PyDeck)
```

---

## 🔄 Workflows

### daily_pipeline.py
```python
def daily_pipeline():
    """Pipeline diário completo"""
    
    # 1. Qualifica 20 escolas
    qualified = qualifier.execute(limit=20)
    
    # 2. Enriquece top 10
    enriched = enricher.execute(limit=10)
    
    # 3. Encontra decisores
    contacts = contact_finder.execute()
    
    # 4. Gera 10 mensagens
    messages = writer.generate_messages(limit=10)
    
    # 5. Adiciona à fila de aprovação
    for msg in messages:
        approval_queue.add_to_queue(msg)
        hubspot_sync.sync_lead(msg['company_id'])
    
    # 6. Envia mensagens JÁ aprovadas
    sent = approval_queue.send_approved_messages()
    
    # 7. Follow-ups automáticos
    followups = scheduler.send_scheduled_followups()
    
    # 8. Relatório
    send_daily_summary({
        'qualified': qualified,
        'enriched': enriched,
        'contacts': len(contacts),
        'pending_approval': len(approval_queue.get_pending()),
        'sent': sent
    })
```

### send_approved.py
```python
def send_approved_messages():
    """
    Envia APENAS mensagens aprovadas
    NUNCA envia sem aprovação
    """
    
    # Busca aprovadas
    approved = db.client.table('approval_queue')\
        .select('*')\
        .eq('status', 'approved')\
        .is_('sent_at', 'null')\
        .execute()
    
    for item in approved.data:
        # Envia
        send_email(item)
        
        # Atualiza
        mark_as_sent(item['id'])
        
        # Registra
        create_interaction(item)
        log_to_hubspot(item)
```

### weekly_analysis.py
```python
def weekly_analysis():
    """Análise semanal de performance"""
    
    # Métricas
    metrics = {
        'qualified': count_by_status('qualified'),
        'contacted': count_by_status('contacted'),
        'responded': count_by_status('responded'),
        'meetings': count_meetings(),
        'conversion_rate': calculate_conversion(),
        'avg_score': calculate_avg_score()
    }
    
    # Gera relatório PDF
    generate_pdf_report(metrics)
    
    # Envia por email
    send_report_email()
```

---

## 🔧 Troubleshooting

### Problema: CSV não importa
```bash
# 1. Verifique se arquivo existe
ls data/raw/escolas_brasil.csv

# 2. Teste estrutura
python -c "import pandas as pd; df = pd.read_csv('data/raw/escolas_brasil.csv', nrows=1); print(df.columns.tolist())"

# 3. Verifique mapeamento no .env
cat .env | grep CSV_COL

# 4. Teste com amostra
python database/migrations/001_import_schools.py --sample 10
```

### Problema: Nenhuma mensagem na fila
```bash
# 1. Verifique status das escolas
python scripts/inspect_db.py

# 2. Rode pipeline manualmente
python workflows/daily_pipeline.py

# 3. Veja logs
tail -f logs/application.log | grep "approval"
```

### Problema: API Error
```bash
# 1. Verifique API keys no .env
cat .env | grep API_KEY

# 2. Teste se estão carregando
python -c "from config.settings import settings; print(settings.ANTHROPIC_API_KEY[:10])"

# 3. Veja uso de créditos
python -c "from database.supabase_client import db; print(db.get_api_credits_used('apollo'))"
```

### Problema: Dashboard não abre
```bash
# 1. Verifique se Streamlit está instalado
pip list | grep streamlit

# 2. Tente porta diferente
streamlit run dashboard/main.py --server.port 8502

# 3. Veja erros
streamlit run dashboard/main.py --logger.level=debug
```

---

## 📋 Commands Reference

### Setup
```bash
python setup_config.py                    # Configurar sistema
```

### Database
```bash
python database/migrations/001_setup_database.py   # Criar tabelas
python database/migrations/002_import_schools.py   # Importar CSV
python database/migrations/002_import_schools.py --sample 100  # Teste
```

### Workflows
```bash
python workflows/daily_pipeline.py        # Pipeline completo
python workflows/send_approved.py         # Enviar aprovados
python workflows/weekly_analysis.py       # Análise semanal
```

### Dashboard
```bash
streamlit run dashboard/main.py            # Iniciar dashboard
```

### Features Extras
```bash
python -m tools.geocoder                  # Geocodificar escolas
python -m tools.phone_finder              # Buscar telefones
```

### Debug
```bash
python scripts/inspect_db.py              # Estado do banco
tail -f logs/application.log              # Logs em tempo real
tail -f logs/errors.log                   # Apenas erros
```

### Tests
```bash
pytest tests/                             # Todos os testes
pytest -v tests/test_agents.py            # Testes específicos
pytest --cov=agents tests/                # Com coverage
```

---

## 📦 Dependências (requirements.txt)
```txt
# Core
python>=3.11
anthropic>=0.18.0
supabase>=2.3.0
python-dotenv>=1.0.0

# Database
psycopg2-binary>=2.9.9

# Dashboard
streamlit>=1.31.0
plotly>=5.18.0
pydeck>=0.8.0

# Data Processing
pandas>=2.2.0
numpy>=1.26.0

# APIs
requests>=2.31.0
beautifulsoup4>=4.12.0
googlemaps>=4.10.0
hubspot-api-client>=8.0.0

# Email
brevo-python>=2.0.0
google-auth>=2.27.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.116.0

# Logging
python-json-logger>=2.0.7

# Testing
pytest>=8.0.0
pytest-cov>=4.1.0

# Utils
phonenumbers>=8.13.27
pydantic>=2.6.0
schedule>=1.2.0
chardet>=5.2.0
```

---

## ✅ Checklist de Implementação

### Fase 1: Fundação
- [ ] `.env.example`, `.gitignore`, `requirements.txt`
- [ ] `config/settings.py` com todas as variáveis
- [ ] `database/schemas.sql` completo
- [ ] `database/supabase_client.py` com métodos CRUD

### Fase 2: Importação CSV
- [ ] `database/migrations/001_setup_database.py`
- [ ] `database/migrations/002_import_schools.py`
- [ ] `agents/filterer.py` com 4 filtros

### Fase 3: Agentes Core
- [ ] `agents/base_agent.py`
- [ ] `agents/qualifier.py` (Claude Haiku)
- [ ] `agents/enricher.py` (cascata APIs)
- [ ] `agents/contact_finder.py`
- [ ] `agents/writer.py` (Claude Sonnet)

### Fase 4: Features Extras
- [ ] `tools/geocoder.py`
- [ ] `tools/phone_finder.py`
- [ ] `dashboard/pages/6_map_view.py`

### Fase 5: Integrações
- [ ] `integrations/hubspot_client.py`
- [ ] `integrations/hubspot_sync.py`
- [ ] `tools/brevo_sender.py` ou `gmail_sender.py`

### Fase 6: Approval & UI
- [ ] `approval_queue/queue_manager.py`
- [ ] `dashboard/app.py`
- [ ] `dashboard/pages/2_approval_queue.py` ⭐

### Fase 7: Workflows
- [ ] `workflows/daily_pipeline.py`
- [ ] `workflows/send_approved.py`
- [ ] `workflows/weekly_analysis.py`

### Fase 8: Prompts
- [ ] `prompts/qualification_prompt.txt`
- [ ] `prompts/email_writer_prompt.txt`
- [ ] `prompts/whatsapp_writer_prompt.txt`

### Fase 9: Utils & Tests
- [ ] `utils/logger.py`
- [ ] `tests/test_agents.py`
- [ ] `tests/test_integrations.py`

### Fase 10: Scripts
- [ ] `scripts/inspect_db.py`
- [ ] `scripts/setup_hubspot_properties.py`
- [ ] `main.py`

---

**Para princípios e arquitetura:** Veja `ARCHITECTURE.md`  
**Para padrões de código:** Veja `STANDARDS.md`  
**Para início rápido:** Veja `CLAUDE.md` e `README.md`