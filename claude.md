# 🎯 IAprendo Sales Agent - Project Guide

> Sistema híbrido (IA + Humano) de prospecção B2B para plataforma educacional

**Versão**: 1.0.0  
**Última Atualização**: 2026-02-09  
**Mantenedor**: Fernando  
**Projeto**: IAprendo - Plataforma de IA Educacional BNCC

---

## 📖 Documentação Estruturada

A documentação completa está organizada em arquivos especializados:

### 🏗️ [ARCHITECTURE.md](docs/ARCHITECTURE.md) 
**Leia PRIMEIRO** - Fundamentos do sistema
- Princípios e filosofia (Validation First, Zero Hardcode, etc)
- Arquitetura de 5 camadas
- Componentes principais e como interagem
- Fluxo de dados completo
- Stack tecnológico

### 📐 [STANDARDS.md](docs/STANDARDS.md)
**Leia ANTES de codificar** - Padrões obrigatórios
- Convenções de código (nomenclatura, estrutura)
- Type hints e docstrings (obrigatórios)
- Error handling patterns (try/except em tudo)
- Logging estruturado (JSON)
- Database access (sempre via cliente)
- API integration patterns (rate limiting, fallbacks)
- Testing requirements

### 🛠️ [IMPLEMENTATION.md](docs/IMPLEMENTATION.md)
**Consulte DURANTE implementação** - Especificações técnicas
- Estrutura completa de arquivos (~60 arquivos)
- Especificação de cada componente
- Database schemas detalhados
- Prompts para agentes IA
- Dashboard e workflows
- Troubleshooting comum

---

## 🚀 Quick Start

### Para Claude Code
1. Leia `docs/ARCHITECTURE.md` (entenda o sistema)
2. Leia `docs/STANDARDS.md` (aprenda os padrões)
3. Leia `docs/IMPLEMENTATION.md` (veja o que criar)
4. Use o prompt fornecido para gerar código

### Para Desenvolvedores
```bash
# 1. Setup
python setup_config.py

# 2. Criar banco
python database/migrations/001_setup_database.py

# 3. Importar CSV (teste)
python database/migrations/002_import_schools.py --sample 100

# 4. Dashboard
streamlit run dashboard/app.py
```

---

## 🎯 Contexto Essencial

### O Desafio
- **Base de dados**: 210.000 escolas do Brasil (CSV oficial MEC)
- **Problema**: Filtrar leads qualificados e personalizar abordagem
- **Escala**: 40-60 leads/mês inicialmente, escalável para 1000+/mês

### A Solução
Sistema em 8 etapas com validação humana obrigatória:
```
1. CSV (210k) → 2. Filtro (4 critérios) → 3. Qualificação IA (score 0-100) →
4. Enriquecimento (APIs) → 5. Encontra Decisores → 6. Gera Mensagens →
7. ⚠️ APROVAÇÃO HUMANA → 8. Envio + Tracking + HubSpot
```

### Diferencial Crítico
**NUNCA envia sem aprovação humana** - isso é o que torna o sistema ético e eficaz.

---

## 📊 Estrutura do CSV

**Arquivo**: `data/raw/escolas_brasil.csv` (~210k linhas)  
**Origem**: Base oficial do MEC

### Filtros Obrigatórios (aplicados na importação)

1. **Restrição de Atendimento**
   - Apenas: `"ESCOLA EM FUNCIONAMENTO E SEM RESTRIÇÃO DE ATENDIMENTO"`
   
2. **Localização**
   - Município: `Porto Alegre`
   - UF: `RS`
   
3. **Níveis de Ensino**
   - Deve conter: `"Fundamental"` (anos finais) **E/OU** `"Médio"`
   
4. **Tipo de Escola**
   - Configurável via `.env`: pública, privada, municipal, estadual, federal

### Campos Principais
- **Identificação**: Escola, Código INEP (chave única)
- **Localização**: Endereço, Latitude, Longitude
- **Contato**: Telefone (pode estar vazio - sistema busca)
- **Classificação**: Categoria/Dependência Administrativa, Porte
- **Ensino**: Etapas e Modalidade de Ensino Oferecidas

---

## 🔑 5 Regras Críticas

### 1. APROVAÇÃO OBRIGATÓRIA
```python
# ❌ NUNCA FAÇA ISSO
def send_email_direct(contact, message):
    brevo.send(contact['email'], message)  # PROIBIDO!

# ✅ SEMPRE FAÇA ISSO
def prepare_for_approval(contact, message):
    approval_queue.add_to_queue({
        'contact_id': contact['id'],
        'message': message,
        'status': 'pending_approval'  # Aguarda humano
    })
```

### 2. ZERO HARDCODE
```python
# ❌ ERRADO
email_from = "fernando@iaprendo.com.br"

# ✅ CORRETO
email_from = settings.YOUR_EMAIL
```

### 3. TYPE HINTS SEMPRE
```python
def qualify_school(
    self, 
    school: Dict[str, Any]
) -> Dict[str, Union[int, str, List[str]]]:
    """Qualifica escola usando IA"""
```

### 4. ERROR HANDLING SEMPRE
```python
try:
    result = external_api.call()
except APIException as e:
    logger.error(f"API failed: {e}")
    result = fallback_strategy()
except Exception as e:
    logger.critical(f"Unexpected: {e}")
    return safe_default_value
```

### 5. CÓDIGO INEP COMO CHAVE ÚNICA
```python
# Evita duplicatas - use INEP sempre
existing = db.get_company_by_inep(inep_code)
if existing:
    db.update_company(existing['id'], new_data)
else:
    db.insert_company(new_data)
```

---

## ✨ Features do Sistema

### Core (Obrigatórias)
- ✅ Qualificação automática com Claude (Haiku 4.5 para score, Sonnet 4.5 para escrita)
- ✅ Enriquecimento multi-fonte com fallbacks (Apollo→Snov→Hunter→Scraping)
- ✅ Geração de mensagens hiperpersonalizadas (nunca templates)
- ✅ Dashboard Streamlit para aprovação humana
- ✅ Integração HubSpot bidirecional (Supabase ↔ HubSpot)
- ✅ Tracking completo (enviado→entregue→aberto→respondido)

### Extras (Opcionais mas Recomendadas)
- ✅ Geocodificação automática via Google Maps API
- ✅ Busca automática de telefones via Google Search
- ✅ Visualização de leads em mapa interativo (PyDeck)

---

## 🗄️ Stack Tecnológico

### Backend
- **Linguagem**: Python 3.11+
- **IA**: Anthropic Claude API (Haiku 4.5 + Sonnet 4.5)
- **Database**: Supabase (PostgreSQL) - 7 tabelas
- **CRM**: HubSpot (sincronização bidirecional)
- **Orquestração**: Python + schedule

### Frontend
- **Dashboard**: Streamlit
- **Mapas**: PyDeck (Deck.gl)

### Integrações
- **Email**: Brevo (300/dia grátis) ou Gmail API (500/dia)
- **Geocoding**: Google Maps API ($200 créditos/mês)
- **Enriquecimento**: Apollo.io (60/mês), Snov.io (50/mês), Hunter.io (25/mês)
- **Scraping**: BeautifulSoup + requests (ilimitado grátis)

### Custo Total Inicial
- **Fase teste**: R$ 10-20/mês (apenas Claude API)
- **Planos gratuitos**: Supabase, HubSpot, Brevo, APIs básicas

---

## 📦 Estrutura de Entrega

Claude Code deve criar **~60 arquivos** em **12 pastas**:
```
agente-vendas-iaprendo/
├── 📁 config/           (2 arquivos)
├── 📁 database/         (3 + migrations/)
├── 📁 agents/           (8 arquivos)
├── 📁 integrations/     (3 arquivos)
├── 📁 tools/            (10 arquivos) ← geocoder, phone_finder
├── 📁 approval_queue/   (2 arquivos)
├── 📁 workflows/        (3 arquivos)
├── 📁 dashboard/        (app + 6 pages) ← map_view
├── 📁 prompts/          (4 templates)
├── 📁 utils/            (4 helpers)
├── 📁 tests/            (3 suites)
├── 📁 scripts/          (2 helpers)
└── 📁 docs/             (3 documentações)
```

**Detalhes**: Ver `docs/IMPLEMENTATION.md`

---

## 🎯 Ordem de Implementação

### Fase 1: Fundação
- Configuration (settings.py, .env)
- Database (schemas.sql, client)
- Migrations (001_setup, 002_import CSV)

### Fase 2: Agentes IA
- Base Agent
- Filterer (4 critérios do CSV)
- Qualifier (Claude Haiku)
- Enricher (APIs em cascata)
- Contact Finder
- Writer (Claude Sonnet)

### Fase 3: Features Extras
- Geocoder (Google Maps)
- Phone Finder (Google Search)
- Map View (PyDeck)

### Fase 4: Integrações
- HubSpot (sync bidirecional)
- Email (Brevo/Gmail)
- Webhooks

### Fase 5: Approval & UI
- Approval Queue Manager
- Dashboard (6 páginas)

### Fase 6: Orchestration
- Daily Pipeline
- Send Approved
- Weekly Analysis

### Fase 7: Testes & Docs
- Unit tests
- Integration tests
- README, guias

---

## 📚 Comandos Úteis
```bash
# SETUP
python setup_config.py                    # Wizard configuração

# DATABASE
python database/migrations/001_setup_database.py   # Criar tabelas
python database/migrations/002_import_schools.py   # Importar CSV

# EXECUÇÃO
python workflows/daily_pipeline.py        # Pipeline manual
streamlit run dashboard/app.py            # Dashboard UI

# FEATURES EXTRAS
python -m tools.geocoder                  # Geocodificar escolas
python -m tools.phone_finder              # Buscar telefones

# DEBUGGING
python scripts/inspect_db.py              # Estado do banco
tail -f logs/application.log              # Logs em tempo real

# TESTES
pytest tests/                             # Todos os testes
pytest -v tests/test_agents.py            # Testes específicos
```

---

## ⚠️ Avisos Importantes

1. **CSV Grande**: 210k linhas - sempre teste com `--sample 100` primeiro
2. **Rate Limits**: Respeite limites de TODAS as APIs (veja `docs/STANDARDS.md`)
3. **Aprovação**: NUNCA bypass da `approval_queue` (regra #1)
4. **Código INEP**: SEMPRE use como chave única (regra #5)
5. **Teste Antes**: Execute `setup_config.py` antes de qualquer outra coisa

---

## 📞 Referências Rápidas

| Preciso de... | Veja... |
|---------------|---------|
| Entender arquitetura | `docs/ARCHITECTURE.md` |
| Padrões de código | `docs/STANDARDS.md` |
| O que implementar | `docs/IMPLEMENTATION.md` |
| Como instalar | `README.md` |
| Configurar sistema | `python setup_config.py` |
| Problemas comuns | `docs/IMPLEMENTATION.md` → Troubleshooting |

---

## 🎓 Para Aprender Mais

- **Anthropic Claude API**: https://docs.anthropic.com/
- **Supabase Docs**: https://supabase.com/docs
- **HubSpot API**: https://developers.hubspot.com/
- **Streamlit**: https://docs.streamlit.io/

---

**Documentação Completa**: Consulte `docs/` para especificações detalhadas

**Versão**: 1.0.0 | **Status**: Production Ready