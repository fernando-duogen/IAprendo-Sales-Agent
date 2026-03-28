# 🎯 IAprendo Sales Agent

> Sistema inteligente de prospecção e vendas B2B com IA para plataformas educacionais

Sistema híbrido que combina automação com IA (Claude) e validação humana para prospectar, qualificar e contatar escolas de forma personalizada e escalável.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Características](#-características)
- [Arquitetura](#-arquitetura)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Documentação](#-documentação)
- [Troubleshooting](#-troubleshooting)
- [Roadmap](#-roadmap)
- [Contribuindo](#-contribuindo)

---

## 🎯 Visão Geral

### O Problema

Você tem uma base de **210.000 escolas** do Brasil, mas precisa:
- ✅ Filtrar apenas as relevantes para seu produto
- ✅ Encontrar os decisores certos (não a secretaria)
- ✅ Criar abordagens personalizadas (não templates)
- ✅ Gerenciar o funil de vendas
- ✅ Fazer tudo isso de forma escalável

### A Solução

**IAprendo Sales Agent** automatiza o processo usando IA, mas **sempre com validação humana**:
```
📁 CSV 210k escolas
    ↓ Filtro Inteligente (IA)
🎯 ~1.500 escolas em Porto Alegre
    ↓ Qualificação (Claude Haiku)
⭐ ~400 escolas qualificadas (score 60-100)
    ↓ Enriquecimento (APIs + Scraping)
📧 ~200 com emails de decisores
    ↓ Geração de Mensagens (Claude Sonnet)
💌 Mensagens hiperpersonalizadas
    ↓ ⚠️ VOCÊ APROVA (Dashboard)
✅ Envio para leads aprovados
    ↓ Tracking + HubSpot CRM
📊 Funil completo até fechamento
```

### Por Que Usar?

| Sem o Sistema | Com o Sistema |
|----------------|---------------|
| 🐌 Dias para encontrar 10 leads qualificados | ⚡ Minutos (automático) |
| 📋 Templates genéricos | 🎨 Mensagens únicas e personalizadas |
| 🤷 Sem controle de quem foi contatado | 📊 Funil completo no HubSpot |
| ❌ Perda de leads (esquecimento) | ✅ Follow-ups automáticos |
| 💸 Custo: seu tempo | 💰 Custo: R$ 15-30/mês (100 leads) |

---

## ✨ Características

### 🤖 Automação Inteligente com IA

- **Qualificação automática** com Claude (score 0-100)
- **Mensagens personalizadas** únicas para cada lead
- **Pesquisa contextual** sobre cada escola
- **Multi-canal**: Email, WhatsApp, LinkedIn

### 🛡️ Validação Humana (Hybrid System)

- **Dashboard interativo** para aprovar mensagens
- **Preview completo** antes de enviar
- **Edição inline** se quiser ajustar
- **Regeneração** com um clique

### 🔗 Integrações Profissionais

- **HubSpot CRM**: Sincronização bidirecional completa
- **Brevo/Gmail**: Envio de emails com tracking
- **Apollo/Snov/Hunter**: Enriquecimento de dados
- **Web Scraping**: Fallback gratuito ilimitado

### 📊 Métricas e Analytics

- Taxa de abertura, resposta, conversão
- ROI por canal (email vs WhatsApp)
- Performance de mensagens (A/B testing)
- Uso de créditos de APIs

### 🎯 Features Especiais

- ✅ **Zero hardcode** - tudo configurável
- ✅ **Planos gratuitos** - comece sem pagar
- ✅ **Escalável** - de 10 a 1000 leads/mês
- ✅ **LGPD compliant** - opt-out automático
- ✅ **Logs detalhados** - auditoria completa

---

## 🏗️ Arquitetura

### Componentes Principais
```
┌─────────────────────────────────────────┐
│         DASHBOARD (Streamlit)           │
│    Interface de Aprovação Humana        │
└─────────────────────────────────────────┘
                  ↕
┌─────────────────────────────────────────┐
│       APPROVAL QUEUE (Crítico)          │
│   Fila de Mensagens Aguardando Você    │
└─────────────────────────────────────────┘
                  ↕
┌─────────────────────────────────────────┐
│         AGENTS LAYER (Python)           │
│  Filterer → Qualifier → Enricher →     │
│  ContactFinder → Writer → Scheduler     │
└─────────────────────────────────────────┘
                  ↕
┌─────────────────────────────────────────┐
│     INTEGRATION LAYER (APIs)            │
│  HubSpot | Brevo | Apollo | Claude     │
└─────────────────────────────────────────┘
                  ↕
┌─────────────────────────────────────────┐
│      DATA LAYER (Supabase)              │
│  PostgreSQL com 7 tabelas principais    │
└─────────────────────────────────────────┘
```

### Fluxo de Dados

1. **Importação**: CSV → Supabase (`companies` table)
2. **Filtro**: SQL query por cidade + níveis → `status='filtered'`
3. **Qualificação**: Claude Haiku analisa → `score` + `priority` → `status='qualified'`
4. **Enriquecimento**: APIs buscam website, techs → `status='enriched'`
5. **Busca Decisores**: APIs/Scraping encontram emails → `contacts` table
6. **Geração Mensagem**: Claude Sonnet cria mensagem → `approval_queue` → **PARA AQUI**
7. **Você Aprova**: Dashboard → `status='approved'`
8. **Envio**: Brevo/Gmail envia → `interactions` table
9. **Tracking**: Abre? Responde? → atualiza status
10. **HubSpot Sync**: Tudo sincroniza com CRM

---

## 🚀 Instalação

### Pré-requisitos

- **Python 3.11+** (obrigatório)
- **Git** (recomendado)
- **210k escolas em CSV** (você já tem!)

### Passo 1: Clone o Repositório
```bash
git clone https://github.com/seu-usuario/agente-vendas-iaprendo.git
cd agente-vendas-iaprendo
```

### Passo 2: Crie Ambiente Virtual
```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Passo 3: Instale Dependências
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Isso vai instalar (~50 pacotes):
- `anthropic` - Claude API
- `supabase` - Database
- `hubspot-api-client` - CRM
- `streamlit` - Dashboard
- `pandas` - Manipulação dados
- E mais...

### Passo 4: Configure o Sistema
```bash
python setup_config.py
```

Este wizard interativo vai:
- ✅ Perguntar sobre seu negócio
- ✅ Analisar seu CSV
- ✅ Configurar ICP (público-alvo)
- ✅ Verificar APIs disponíveis
- ✅ Gerar `.env` customizado
- ✅ Criar estrutura de diretórios

**Tempo estimado: 5-10 minutos**

### Passo 5: Revise a Configuração
```bash
# Abra e leia com atenção:
cat CONFIG_REVIEW.md
```

Este arquivo contém:
- ✅ Resumo do que você configurou
- ✅ Checklist de pendências
- ✅ Próximos passos detalhados

---

## ⚙️ Configuração

### APIs Necessárias

#### Obrigatórias (para começar)

| API | Custo | Como Obter | Para Que Serve |
|-----|-------|------------|----------------|
| **Anthropic Claude** | ~R$10/mês (100 leads) | [console.anthropic.com](https://console.anthropic.com) | IA para qualificação e escrita |
| **Supabase** | Gratuito (500MB) | [supabase.com](https://supabase.com) | Banco de dados |
| **HubSpot** | Gratuito | [hubspot.com](https://hubspot.com) | CRM |
| **Brevo** ou **Gmail** | Gratuito (300-500/dia) | [brevo.com](https://brevo.com) | Envio de emails |

**Total: R$ 10-15/mês**

#### Opcionais (melhoram enriquecimento)

| API | Plano Gratuito | Para Que Serve |
|-----|----------------|----------------|
| **Apollo.io** | 60 créditos/mês | Busca dados empresas + contatos |
| **Snov.io** | 50 créditos/mês | Busca emails de decisores |
| **Hunter.io** | 25 verificações/mês | Valida emails |
| **RocketReach** | 5 lookups/mês | Contatos premium |

**Total: R$ 0/mês (planos gratuitos)**

### Setup do Supabase

Depois de criar projeto no Supabase:
```bash
# 1. Copie URL e API Key para .env
# 2. Crie as tabelas:
python database/migrations/001_setup_database.py
```

Isso cria 7 tabelas:
- `companies` (escolas)
- `contacts` (decisores)
- `approval_queue` ⭐ (validação)
- `interactions` (histórico)
- `meetings` (reuniões)
- `api_usage` (controle créditos)
- `campaigns` (campanhas)

### Setup do HubSpot

Crie campos customizados no HubSpot:

1. Acesse: **Settings → Properties → Contact Properties**
2. Crie as seguintes propriedades:

| Nome | Tipo | Valores |
|------|------|---------|
| `iaprendo_score` | Number | 0-100 |
| `iaprendo_priority` | Dropdown | baixa, media, alta |
| `iaprendo_status` | Dropdown | new, contacted, responded, meeting_scheduled |
| `iaprendo_is_decision_maker` | Checkbox | true/false |

Ou rode o script automatizado:
```bash
python scripts/setup_hubspot_properties.py
```

### Importação do CSV

Teste com amostra pequena primeiro:
```bash
# Importa apenas 100 escolas
python database/migrations/002_import_schools.py --sample 100
```

Verifique no Supabase se importou corretamente. Se sim:
```bash
# Importa tudo (210k escolas - pode demorar ~5-10min)
python database/migrations/002_import_schools.py
```

---

## 📱 Uso

### Iniciar o Dashboard
```bash
streamlit run dashboard/app.py
```

Acesse: **http://localhost:8501**

O dashboard tem 5 páginas:

1. **Overview** 📊 - Métricas gerais, funil, gráficos
2. **Approval Queue** ✅ - **PRINCIPAL** - Aprovar mensagens
3. **Leads** 📋 - Gerenciar todos os leads
4. **Campaigns** 📧 - Campanhas ativas
5. **Settings** ⚙️ - Configurações do sistema

### Rodar o Pipeline (Manual)
```bash
python workflows/daily_pipeline.py
```

O pipeline executa:

1. ✅ Qualifica 20 escolas (`filtered` → `qualified`)
2. ✅ Enriquece 10 escolas (`qualified` → `enriched`)
3. ✅ Encontra decisores (cria `contacts`)
4. ✅ Gera 10 mensagens (adiciona à `approval_queue`)
5. ✅ Envia mensagens já aprovadas
6. ✅ Processa follow-ups automáticos

**Tempo de execução: ~2-5 minutos**

### Aprovar Mensagens (Dashboard)

1. Acesse: **Approval Queue** (página 2)
2. Você verá um card com:
   - 🏫 Dados da escola
   - 👤 Contato identificado
   - 📊 Score da IA + reasoning
   - 📧 Preview da mensagem
3. Ações:
   - **✅ Aprovar** - Envia na próxima execução
   - **✏️ Editar** - Ajusta mensagem inline
   - **🔄 Gerar Nova** - IA reescreve
   - **❌ Rejeitar** - Remove da fila
   - **⏭️ Pular** - Decide depois

### Automatizar (Pipeline Diário)

Edite `main.py` e execute:
```bash
# Roda em loop, executa pipeline todo dia às 8h
python main.py
```

Ou use **cron** (Linux/Mac):
```bash
# Edite crontab
crontab -e

# Adicione linha:
0 8 * * * cd /caminho/projeto && /caminho/venv/bin/python workflows/daily_pipeline.py
```

Ou **Task Scheduler** (Windows):
- Programa: `C:\caminho\venv\Scripts\python.exe`
- Argumentos: `C:\caminho\projeto\workflows\daily_pipeline.py`
- Gatilho: Diário, 8h

---

## 📁 Estrutura do Projeto
```
agente-vendas-iaprendo/
│
├── 📄 README.md                    # Este arquivo
├── 📄 CLAUDE.md                    # Especificações completas
├── 📄 CONFIG_REVIEW.md             # Sua configuração (gerado)
├── 📄 .env                         # Variáveis ambiente (SECRET)
├── 📄 .gitignore
├── 📄 requirements.txt
├── 📄 setup_config.py              # Wizard de configuração
├── 📄 main.py                      # Entry point
│
├── 📁 config/                      # Configurações
│   ├── settings.py                 # Lê .env
│   └── icp.py                      # ICP dinâmico
│
├── 📁 database/                    # Banco de dados
│   ├── schemas.sql                 # Schema SQL
│   ├── supabase_client.py          # Cliente CRUD
│   └── migrations/                 # Scripts setup/import
│
├── 📁 agents/                      # Agentes IA
│   ├── base_agent.py               # Classe base
│   ├── filterer.py                 # Filtra CSV
│   ├── qualifier.py                # Qualifica (Haiku)
│   ├── enricher.py                 # Enriquece dados
│   ├── contact_finder.py           # Encontra decisores
│   ├── researcher.py               # Pesquisa contexto
│   ├── writer.py                   # Gera mensagens (Sonnet)
│   └── scheduler.py                # Sequências
│
├── 📁 integrations/                # APIs externas
│   ├── hubspot_client.py           # Cliente HubSpot
│   ├── hubspot_sync.py             # Sincronização
│   └── webhooks.py                 # Recebe eventos
│
├── 📁 tools/                       # Utilitários APIs
│   ├── apollo.py                   # Apollo.io
│   ├── snov.py                     # Snov.io
│   ├── hunter.py                   # Hunter.io
│   ├── web_scraper.py              # Scraping
│   ├── brevo_sender.py             # Envio Brevo
│   ├── gmail_sender.py             # Envio Gmail
│   └── whatsapp_sender.py          # WhatsApp
│
├── 📁 approval_queue/              # Validação humana
│   ├── queue_manager.py            # CRUD fila
│   └── models.py                   # Modelos Pydantic
│
├── 📁 workflows/                   # Orquestração
│   ├── daily_pipeline.py           # Pipeline diário
│   ├── weekly_analysis.py          # Análise semanal
│   └── send_approved.py            # Envio aprovados
│
├── 📁 dashboard/                   # Interface Streamlit
│   ├── app.py                      # App principal
│   ├── components/                 # Componentes UI
│   └── pages/                      # Páginas
│       ├── 1_overview.py
│       ├── 2_approval_queue.py     # ⭐ Principal
│       ├── 3_leads.py
│       ├── 4_campaigns.py
│       ├── 5_settings.py
│       └── 6_map_view.py          # 🗺️ Mapa interativo
│
├── 📁 prompts/                     # Templates Claude
│   ├── qualification_prompt.txt
│   ├── email_writer_prompt.txt
│   ├── whatsapp_writer_prompt.txt
│   └── research_prompt.txt
│
├── 📁 utils/                       # Helpers
│   ├── logger.py
│   ├── helpers.py
│   ├── validators.py
│   └── metrics.py
│
├── 📁 data/                        # Dados locais
│   ├── raw/                        # CSV original
│   ├── processed/                  # Intermediários
│   └── exports/                    # Exportações
│
├── 📁 logs/                        # Logs aplicação
│   ├── application.log
│   ├── api_calls.log
│   └── errors.log
│
└── 📁 tests/                       # Testes
    ├── test_agents.py
    ├── test_integrations.py
    └── test_tools.py
```

---

## 📚 Documentação

### Arquivos Principais

| Arquivo | Conteúdo |
|---------|----------|
| **CLAUDE.md** | Especificações completas do projeto |
| **CONFIG_REVIEW.md** | Sua configuração específica |
| **README.md** | Este arquivo - guia rápido |

### Comandos Úteis
```bash
# SETUP
python setup_config.py              # Configurar sistema

# DATABASE
python database/migrations/001_setup_database.py  # Criar tabelas
python database/migrations/002_import_schools.py  # Importar CSV

# EXECUÇÃO
python workflows/daily_pipeline.py  # Pipeline manual
python main.py                      # Orquestrador (loop)

# DASHBOARD
streamlit run dashboard/app.py      # Interface

# TESTES
pytest tests/                       # Todos os testes
pytest -v tests/test_agents.py      # Testes específicos

# DEBUG
python scripts/inspect_db.py        # Estado do banco
tail -f logs/application.log        # Logs em tempo real
```

### Logs

Logs estruturados em JSON no diretório `logs/`:
```bash
# Log geral
tail -f logs/application.log

# Apenas erros
tail -f logs/errors.log | grep ERROR

# Chamadas de API
tail -f logs/api_calls.log
```

---

## 🐛 Troubleshooting

### Problema: "Module not found"
```bash
# Ative o ambiente virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstale dependências
pip install -r requirements.txt
```

### Problema: "Authentication Failed" (APIs)
```bash
# Verifique se API keys estão corretas no .env
cat .env | grep API_KEY

# Teste se estão carregando
python -c "from config.settings import settings; print(settings.ANTHROPIC_API_KEY)"

# Verifique validade no dashboard do provider
```

### Problema: "Nenhuma mensagem na fila de aprovação"
```bash
# 1. Verifique se pipeline rodou
tail logs/application.log | grep "pipeline"

# 2. Verifique status das escolas no banco
python scripts/inspect_db.py

# 3. Execute pipeline manualmente
python workflows/daily_pipeline.py
```

### Problema: "Emails indo para spam"

Soluções:

1. **Warmup do domínio** (começa com 5 emails/dia)
2. **Configure SPF/DKIM** no DNS
3. **Use Gmail** em vez de Brevo inicialmente
4. **Verifique conteúdo** (evite palavras spam)

Veja guia completo em: `CLAUDE.md` → Seção Troubleshooting

---

## 🎯 Roadmap

### ✅ v1.0 (Atual)

- [x] Qualificação automática com IA
- [x] Enriquecimento multi-fonte
- [x] Geração de mensagens personalizadas
- [x] Dashboard de aprovação
- [x] Integração HubSpot
- [x] Envio via Brevo/Gmail
- [x] Tracking completo

### 🚧 v1.1 (Próximo)

- [ ] WhatsApp API integrado (além de manual)
- [ ] A/B testing automático de mensagens
- [ ] Análise de sentimento em respostas
- [ ] LinkedIn outreach automatizado
- [ ] Agendamento automático de reuniões (Calendly)

### 🔮 v2.0 (Futuro)

- [ ] Multi-idioma (PT, EN, ES)
- [ ] Análise preditiva de conversão
- [ ] Auto-ajuste de ICP baseado em resultados
- [ ] Integração com mais CRMs (Salesforce, Pipedrive)
- [ ] Mobile app para aprovação

---

## 🤝 Contribuindo

Contribuições são bem-vindas! 

### Como Contribuir

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/NovaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona NovaFeature'`)
4. Push para a branch (`git push origin feature/NovaFeature`)
5. Abra um Pull Request

### Guidelines

- Siga os padrões do `CLAUDE.md`
- Adicione testes para novas features
- Atualize documentação
- Use type hints
- Docstrings em português

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja [LICENSE](LICENSE) para detalhes.

---

## 👤 Autor

**Fernando**
- Email: fernando@iaprendo.com.br (substitua pelo seu real)
- LinkedIn: [Seu LinkedIn]
- Website: [iaprendo.com.br]

---

## 🙏 Agradecimentos

- **Anthropic** - Claude API
- **Supabase** - Database incrível
- **HubSpot** - CRM gratuito
- **Streamlit** - Framework de dashboard

---

## 📞 Suporte

Precisa de ajuda?

1. 📖 Leia `CLAUDE.md` (documentação completa)
2. 📋 Verifique `CONFIG_REVIEW.md` (sua configuração)
3. 🐛 Veja seção Troubleshooting acima
4. 📧 Entre em contato: fernando@iaprendo.com.br

---

## 💡 FAQ

### Quanto custa rodar o sistema?

**Mês 1-3 (Teste):**
- Claude API: ~R$ 10-15/mês (100 leads)
- Ferramentas: GRÁTIS (planos free)
- **Total: R$ 10-15/mês**

**Escala (100 leads/mês):**
- Claude API: ~R$ 30-40/mês
- Apollo Pro: R$ 250/mês (opcional)
- Hunter Starter: R$ 250/mês (opcional)
- **Total: R$ 30-540/mês** (dependendo das APIs)

### Preciso saber programar?

**Não!** O sistema já vem pronto. Você só precisa:
1. Executar `setup_config.py` (wizard guia você)
2. Aprovar mensagens no dashboard (interface visual)
3. Acompanhar métricas

### E se eu não tiver 210k escolas?

Funciona com qualquer volume! O sistema é escalável:
- **Poucos leads** (10-50): Perfeito para começar
- **Médio volume** (100-500): Ideal
- **Alto volume** (1000+): Adicione mais automação

### Posso usar para outros produtos além de educação?

**Sim!** Basta ajustar o ICP:
- Mude `TARGET_SCHOOL_TYPES` para tipos de empresa
- Ajuste `TARGET_EDUCATION_LEVELS` para segmentos
- Customize prompts em `prompts/*.txt`

### O sistema envia mensagens sem eu aprovar?

**NÃO!** Princípio fundamental:
- Todas mensagens **SEMPRE** vão para fila de aprovação
- Você **SEMPRE** revisa antes de enviar
- Exceção: Follow-ups que você pré-aprovou

### Quanto tempo economizo?

**Sem o sistema:**
- Encontrar 10 leads qualificados: ~4-8 horas
- Escrever 10 mensagens personalizadas: ~2-3 horas
- **Total: ~6-11 horas/semana**

**Com o sistema:**
- Encontrar 10 leads: ~5 minutos (automático)
- Aprovar 10 mensagens: ~10-15 minutos
- **Total: ~15-20 minutos/semana**

**Economia: ~90% do tempo**

---

<div align="center">

**Feito com ❤️ para escalar vendas B2B com IA + Humano**

[⭐ Star no GitHub](https://github.com/seu-usuario/agente-vendas-iaprendo) • [🐛 Report Bug](https://github.com/seu-usuario/agente-vendas-iaprendo/issues) • [💡 Request Feature](https://github.com/seu-usuario/agente-vendas-iaprendo/issues)

</div>