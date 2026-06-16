# 🎯 IAprendo Sales Agent - Project Guide

> Sistema híbrido (IA + Humano) de prospecção B2B para plataforma educacional

**Versão**: 1.0.0  
**Última Atualização**: 2026-06-08  
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

# 4. Dashboard (entrypoint = main.py, que monta o menu via st.navigation)
streamlit run dashboard/main.py
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

### Core
- ✅ Qualificação automática com IA (GPT-4.1-mini para score e escrita)
- ✅ Enriquecimento multi-fonte com fallbacks (Apollo→Snov→Hunter→Perplexity→Scraping)
- ✅ Geração de mensagens hiperpersonalizadas (nunca templates genéricos)
- ✅ Dashboard Streamlit (11 páginas) para aprovação humana
- ✅ **Chat IAlex no navegador** (`dashboard/pages/0_💬_Chat_IAlex.py`) — 1ª página do menu; conversa com a IA no dashboard, reusa 100% do Brain (mesmas tools do WhatsApp), histórico por usuário, botões de download XLSX inline
- ✅ IAlex — agente WhatsApp + chat web com **85 tools** (acesso a CRM/ENEM/Censo)
- ✅ **Seleção automática de template por alvo** (`utils/template_selector.py`) — matriz audience (nominal/genérico) × dados (matrículas/ENEM); modo `template_auto` no pipeline/brain; colunas `audience_type`/`data_profile` em `message_templates`
- ✅ **Agregação inteligente** (`agregar_estatisticas_escolas`) — soma matrículas/docentes com cobertura + estimativa transparente (concreto vs estimado)
- ✅ **Export XLSX** (`utils/export_utils.py`) — escolas + contatos (3 abas) via Pipeline, Contatos e chat (`exportar_escolas_xlsx`, signed URL 24h)
- ✅ **Delete em massa** de escolas no Pipeline (confirmação 2-clicks)
- ✅ **Filtros UF + Cidade** (cascata) em Escolas, Contatos e Pipeline
- ✅ **Anexos PDF por usuário** (sticky) nos emails (`integrations/email_attachments.py`)
- ✅ **email_sender_name** por usuário (Nome | DUOGEN) no "De:" do email
- ✅ Integração HubSpot bidirecional (Supabase ↔ HubSpot push + pull)
- ✅ Tracking completo (enviado→entregue→aberto→clicado→respondido)
- ✅ Registro manual de interações (aba "Registrar Contato" em Escolas + tool `registrar_contato` no IAlex) — paridade dashboard ↔ WhatsApp para logar contatos feitos fora da plataforma
- ✅ Multi-user (login + identidade dinâmica) — **3 usuários: Fernando, Lizianne, Felipe**. `streamlit-authenticator` no dashboard + `utils/sender_profile.py` resolve identidade ativa em tempo real (writer/brain/brevo). IAlex detecta automaticamente quem mandou o comando pelo número do WhatsApp e usa o perfil correto (configurados em `config/users.yaml`)
- ✅ Health-check robusto do IAlex no startup (`whatsapp_bridge.ping_real()` + `restart_instance()`) — detecta sessão Baileys "fantasma" (Connection Closed) e reinicia automático

### Inteligência ENEM (Fase 1-3, Abril 2026)
- ✅ 185k escolas com analytics ENEM 2024 (média, ranking, peer group, potencial)
- ✅ Ranking P1/P2/P3 de leads por temperatura comercial
- ✅ Radar comparativo (escola vs município vs estado, 5 áreas ENEM + 5 competências redação)
- ✅ Query builder flexível (comparação, ranking, distribuição, série temporal)
- ✅ Série histórica Censo 2020-2025 por escola (matrículas, docentes, tech, infra)
- ✅ Métricas derivadas (razão aluno/professor, tech score, infra score, composição matrícula)
- ✅ Insight seeds (correlações pré-detectadas: ratio vs matrícula, salto tech, etc.)
- ✅ Defense in depth ética (amostra_confiavel gate, peer≠escola, socio=município)

### One Page Report + Graficos (F1)
- ✅ **One Page Report (OPR)**: HTML auto-contido com diagnostico ENEM por escola
  - Radar 5 areas ENEM (escola vs benchmark), metricas, gap, evolucao matriculas, insights
  - Publicado via GitHub Pages: `https://fernando-duogen.github.io/IAprendo-Sales-Agent/reports/{inep}.html`
  - Gerador: `tools/report_generator.py` → `generate_and_upload_report(inep)`
  - Acesso: Dashboard (Escolas → detalhe → aba Acoes) ou IAlex (WhatsApp: "gera relatorio da escola X")
- ✅ **Graficos de Insight**: 3 PNGs otimizados para email (Plotly + kaleido)
  - Radar ENEM (5 areas vs benchmark), Gap Indicator (area mais fraca), Trend de matriculas
  - Upload para Supabase Storage → URLs publicas em `approval_queue.chart_urls`
  - Gerador: `tools/insight_charts.py` → `generate_all_relevant_charts(inep)`
  - Inseridos automaticamente nos emails de prospecao (final do body, antes da assinatura)
  - Acesso: Dashboard (Escolas → detalhe → aba Acoes) ou IAlex ("gera graficos da escola X")

### Score de Urgencia Unificado (F2)
- ✅ Score 0-100 combinando engagement + preditivo ML + intent + ENEM P1/P2/P3
- ✅ Tiers: CRITICAL (80+), HOT (60-79), WARM (40-59), COLD (0-39)
- ✅ Alertas WhatsApp imediatos para novos CRITICALs
- ✅ Digest diario as 8:15 com leads por tier + trends + inatividade
- ✅ 3 tools IAlex: `score_urgencia`, `proximas_acoes`, `digest_urgencia`
- ✅ Dashboard: widget Hot Leads na Home + coluna Urgencia em Escolas e Pipeline

### Extras
- ✅ Geocodificação automática via Google Maps API
- ✅ Busca automática de telefones via Google Search
- ✅ Visualização de leads em mapa interativo (PyDeck)
- ✅ Score preditivo ML + detecção de sinais de compra
- ✅ Memória persistente (IAlex lembra fatos sobre escolas/contatos)
- ✅ Follow-ups comportamentais (Hot Click, Curious Open, Silent Open, Revival)
- ✅ Autocomplete de escolas (cascata UF→Município→Escola via Censo)

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

### Dashboard — 11 Paginas (reorganizado Abril 2026; Chat IAlex adicionado Jun 2026)
```
📊 Home (app.py) — Central de Comando com KPIs e tiles de acesso rapido
0  💬 Chat IAlex      — Conversa com a IA no navegador (reusa Brain; 1a do menu)
─── CRM ───
1  🏫 Escolas         — Gestao de escolas, detalhe, redes, performance ENEM (+ filtros UF/Cidade, export XLSX, WhatsApp da escola)
2  👥 Contatos        — Power Map de decisores (+ filtros UF/Cidade, export XLSX, phone_whatsapp separado)
3  🗺️ Mapa           — Visualizacao geografica interativa (PyDeck)
4  📥 Importar        — Importar escolas da base MEC (212k)
─── Execucao ───
5  📊 Pipeline        — Execucao (tabela checkbox + filtros + 3 modos msg + Forcar + export/delete) + Descoberta + Kanban
6  ✉️ Comunicacao     — Aprovacao + Follow-ups + Templates (selecao auto por alvo + matriz + anexos PDF) + Metricas
─── Inteligencia ───
7  🎯 Inteligencia    — Ranking ENEM P1/P2/P3, Radar Comparativo, Explorador Livre
8  📈 Analytics       — ROI, Funil, Conversoes, Custos
─── Sistema ───
9  ⚙️ Configuracoes  — Automacoes, Memoria, Diagnostico, Multi-user/Acesso
10 📖 Manual          — Manual completo da plataforma (12 tabs)
```

### Backend — ~70+ arquivos em 14 pastas
```
agente-vendas-iaprendo/
├── 📁 agent/            (brain.py + tools/enem_tools.py + webhook + bridge)
├── 📁 config/           (settings.py + users.yaml [gitignored, multi-user auth])
├── 📁 database/         (supabase_client + migrations/)
├── 📁 agents/           (qualifier, enricher, writer, etc.)
├── 📁 integrations/     (hubspot, brevo, memory, email_rag, outlook)
├── 📁 tools/            (geocoder, phone_finder, health_check, predictive, etc.)
├── 📁 approval_queue/   (queue_manager)
├── 📁 workflows/        (daily_pipeline, follow_up_manager, send_approved)
├── 📁 dashboard/        (app.py + pages/ + theme.py + helpers/)
├── 📁 prompts/          (templates de email)
├── 📁 utils/            (logger, template_renderer, fit_score, role_classifier, date_pt, sender_profile)
├── 📁 scripts/          (historico/, inspect, generate_migration, fix_mojibake)
├── 📁 docs/             (ARCHITECTURE, IMPLEMENTATION, STANDARDS, ANNUAL_UPDATE, RELOCATION)
└── 📁 data/             (raw/ CSVs MEC + ENEM)
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
streamlit run dashboard/main.py           # Dashboard UI (entrypoint st.navigation)

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