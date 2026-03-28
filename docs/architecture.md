# 🏗️ ARCHITECTURE.md - Arquitetura do Sistema

> Princípios fundamentais, componentes e fluxo de dados

---

## 📖 Índice

1. [Princípios Fundamentais](#-princípios-fundamentais)
2. [Arquitetura de 5 Camadas](#-arquitetura-de-5-camadas)
3. [Componentes Principais](#-componentes-principais)
4. [Fluxo de Dados](#-fluxo-de-dados)
5. [Integrações](#-integrações)

---

## 🎨 Princípios Fundamentais

### 1. Validation First - Humano no Loop

**Princípio**: IA processa, humano decide e aprova
```
IA analisa → IA gera mensagem → Adiciona à fila → 
👤 HUMANO REVISA → Humano aprova → Sistema envia
```

**Por quê:**
- Evita mensagens inadequadas ou erros
- Permite ajuste fino da personalização
- Mantém controle de qualidade 100%
- Aprende com feedback humano

**Implementação:**
- NUNCA bypass da `approval_queue`
- Dashboard mostra reasoning da IA
- Edição inline antes de aprovar
- Opção de regenerar mensagem

---

### 2. Personalization Over Scale

**Princípio**: 40 mensagens personalizadas > 400 templates genéricos

**Por quê:**
- Taxa de resposta 5-10x maior
- Constrói reputação positiva
- Evita filtros de spam
- Respeita o receptor

**Implementação:**
- Claude Sonnet para escrita (melhor qualidade)
- Prompt com contexto específico da escola
- Sem templates - cada mensagem única
- Pesquisa contextual antes de escrever

---

### 3. Configuration Over Convention

**Princípio**: Zero hardcode - tudo configurável
```python
# ❌ NUNCA
email = "fernando@iaprendo.com.br"

# ✅ SEMPRE
email = settings.YOUR_EMAIL
```

**Por quê:**
- Reutilizável por outras pessoas
- Fácil manutenção
- Evita bugs por premissas erradas
- Testável

**Implementação:**
- `setup_config.py` questiona tudo
- `.env` é única fonte de verdade
- `config/settings.py` centraliza acesso
- `CONFIG_REVIEW.md` para revisão

---

### 4. Graceful Degradation

**Princípio**: Sistema funciona mesmo com recursos limitados
```
APIs pagas (Apollo) → APIs gratuitas (Snov) → Scraping gratuito
```

**Por quê:**
- Custo zero inicial
- Escalabilidade gradual
- Resiliência a falhas
- Usuário escolhe investimento

**Implementação:**
- Credit tracking para APIs
- Fallbacks automáticos em cascata
- Web scraping como última opção
- Logs de qual método funcionou

---

### 5. Data Integrity

**Princípio**: Código INEP como chave única absoluta
```python
# SEMPRE verificar se escola já existe
existing = db.get_company_by_inep(inep_code)
if existing:
    db.update_company(existing['id'], new_data)
else:
    db.insert_company(new_data)
```

**Por quê:**
- Evita duplicatas (crítico!)
- INEP é único por escola no Brasil
- Permite re-importações seguras
- Auditoria e rastreabilidade

---

## 🏛️ Arquitetura de 5 Camadas
```
┌─────────────────────────────────────────────────┐
│         CAMADA 5: PRESENTATION                  │
│              (Streamlit Dashboard)               │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│    │ Overview │  │ Approval │  │   Map    │   │
│    │  Metrics │  │  Queue   │  │   View   │   │
│    └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│         CAMADA 4: APPROVAL                      │
│          (Validação Humana - CRÍTICO)           │
│                                                 │
│  approval_queue table:                          │
│  • status: pending_approval                     │
│  • Humano SEMPRE aprova                         │
│  • Edição inline permitida                     │
│                                                 │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│         CAMADA 3: AGENT                         │
│           (Processamento IA)                    │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Filterer │→ │Qualifier │→ │ Enricher │    │
│  └──────────┘  └──────────┘  └──────────┘    │
│                     ↓              ↓           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Contact  │→ │Researcher│→ │  Writer  │→   │
│  │  Finder  │  └──────────┘  └──────────┘    │
│  └──────────┘                                  │
│                                                 │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│         CAMADA 2: INTEGRATION                   │
│          (Mundo Externo)                        │
│                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ HubSpot  │  │  Brevo   │  │  Claude  │    │
│  │   CRM    │  │  Email   │  │   API    │    │
│  └──────────┘  └──────────┘  └──────────┘    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Apollo  │  │  Google  │  │   Web    │    │
│  │   API    │  │   Maps   │  │ Scraping │    │
│  └──────────┘  └──────────┘  └──────────┘    │
│                                                 │
└─────────────────────────────────────────────────┘
                      ↕
┌─────────────────────────────────────────────────┐
│         CAMADA 1: DATA                          │
│         (Supabase PostgreSQL)                   │
│                                                 │
│  companies │ contacts │ approval_queue          │
│  interactions │ meetings │ api_usage            │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🧩 Componentes Principais

### CAMADA 1: Data Layer (Supabase)

**Responsabilidade**: Persistência e integridade dos dados

**Tabelas**:
```sql
companies (escolas - leads)
├── id, name, inep_code (UNIQUE)
├── address, city, state, latitude, longitude
├── phone, phone_source, website
├── school_type, admin_category, restriction_status
├── education_levels[], school_size, student_count
├── score, priority, status
└── hubspot_company_id

contacts (decisores)
├── id, company_id (FK)
├── name, title, department
├── email, phone, whatsapp, linkedin_url
├── is_decision_maker, decision_power
└── status, hubspot_contact_id

approval_queue ⭐ (CRÍTICO)
├── id, company_id, contact_id (FKs)
├── channel (email/whatsapp)
├── subject, message, ai_reasoning
├── status (pending_approval → approved → sent)
├── edited, original_message
└── approved_by, approved_at

interactions (histórico completo)
├── id, company_id, contact_id (FKs)
├── channel, direction, interaction_type
├── message, response
├── status (sent → delivered → opened → replied)
└── sent_at, opened_at, replied_at

meetings (reuniões agendadas)
├── id, company_id, contact_id (FKs)
├── scheduled_date, duration_minutes
├── meeting_type, status
└── meeting_link, notes, outcome

api_usage (controle de créditos)
├── id, api_name, endpoint
├── credits_used, success
├── company_id, contact_id (contexto)
└── created_at

campaigns (futuro - campanhas)
├── id, name, description
├── status, start_date, end_date
└── metrics
```

**Índices Críticos**:
- `inep_code` (UNIQUE) - evita duplicatas
- `status` (companies) - queries frequentes
- `score DESC` - priorização
- `(latitude, longitude)` - queries de mapa

**Extensões Supabase (habilitar no SQL Editor se precisar busca por proximidade)**:
```sql
CREATE EXTENSION IF NOT EXISTS cube;
CREATE EXTENSION IF NOT EXISTS earthdistance;
```

---

### CAMADA 2: Agent Layer (Python + IA)

**Responsabilidade**: Processamento inteligente

#### FilterAgent
```python
Entrada: CSV bruto (210k escolas)
Processo:
  1. Filtro "Restrição de Atendimento"
  2. Filtro cidade (Porto Alegre) + estado (RS)
  3. Filtro níveis ensino (Fundamental/Médio)
  4. Filtro tipo escola (configurável)
Saída: ~1.500 escolas com status='filtered'
IA: Não usa
```

#### QualifierAgent
```python
Entrada: Companies status='filtered'
Processo: Claude Haiku analisa e pontua
Critérios:
  • Fit ICP (40 pts): níveis, tipo, tamanho
  • Tamanho estimado (20 pts): porte da escola
  • Sinais inovação (20 pts): metodologia, tech
  • Probabilidade conversão (20 pts)
Saída: score 0-100, priority, reasoning
IA: Claude Haiku 4.5 (~R$0.01/lead)
```

#### EnricherAgent
```python
Entrada: Companies score >= 60
Processo: Cascata de APIs
  1. Apollo.io (se tem créditos)
  2. Snov.io (se tem créditos)
  3. Hunter.io (se tem créditos)
  4. Web scraping (sempre disponível)
Saída: website, tecnologias, contatos
IA: Não usa (apenas APIs)
```

#### ContactFinderAgent
```python
Entrada: Companies enriched
Processo:
  1. LinkedIn search via APIs
  2. Website scraping (página "Equipe")
  3. Email pattern guess + validação
Cargos alvo: Diretor, Coord. Pedagógico, etc
Saída: Contacts com is_decision_maker=true
IA: Não usa diretamente
```

#### ResearcherAgent (Opcional)
```python
Entrada: Company + Contact
Processo:
  1. Google search sobre a escola
  2. Busca notícias recentes
  3. Identifica diferenciais
Saída: Context dict com insights
IA: Claude Haiku 4.5 para análise (~R$0.02/lead)
```

#### WriterAgent ⭐
```python
Entrada: Company + Contact + Context
Processo:
  1. Analisa contexto específico
  2. Gera mensagem ÚNICA (não template)
  3. Adapta tom e abordagem
Saída: Email OU WhatsApp personalizado
IA: Claude Sonnet 4.5 (~R$0.05/lead)
Regra: NUNCA templates genéricos
```

#### SchedulerAgent
```python
Entrada: Contact + interaction history
Processo:
  1. Define próximo toque (email/whatsapp)
  2. Calcula timing ideal (3-7 dias)
  3. Respeita limites (máx 3 toques)
Saída: Next action scheduled
IA: Não usa (regras de negócio)
```

---

### CAMADA 3: Integration Layer

**Responsabilidade**: Conectar mundo externo

#### HubSpot Integration
```python
Operações:
  • create_or_update_contact()
  • create_or_update_company()
  • create_email_engagement()
  • create_note()
  
Sincronização Bidirecional:
  Supabase → HubSpot:
    - Lead qualificado → cria no HubSpot
    - Status muda → atualiza HubSpot
    - Email enviado → registra atividade
  
  HubSpot → Supabase (via webhooks):
    - Resposta → atualiza interactions
    - Reunião → atualiza meetings
    - Status manual → sincroniza

Campos Customizados:
  • iaprendo_score (NUMBER 0-100)
  • iaprendo_priority (DROPDOWN)
  • iaprendo_status (DROPDOWN)
  • iaprendo_is_decision_maker (CHECKBOX)
```

#### Email Integration
```python
Providers:
  • Brevo: 300 emails/dia grátis
  • Gmail API: 500 emails/dia grátis

Recursos:
  • Tracking: abertura, cliques
  • Webhooks: bounces, respostas
  • Templates: suportado mas NÃO usado
  • SPF/DKIM: configuração necessária
```

#### Enrichment APIs
```python
Apollo.io (60/mês):
  • find_contacts(company_domain)
  • enrich_company(domain)

Snov.io (50/mês):
  • find_emails(domain)
  • verify_email(email)

Hunter.io (25/mês):
  • verify_email(email)
  • find_email(domain, first, last)

Web Scraper (ilimitado):
  • extract_emails(website)
  • get_company_info(website)
```

---

### CAMADA 4: Approval Layer ⭐ CRÍTICO

**Responsabilidade**: Validação humana obrigatória
```python
Workflow Completo:

1. add_to_queue(message_data)
   └─ Agent gera mensagem
   └─ Adiciona com status='pending_approval'
   └─ ⚠️ PARA AQUI - aguarda humano

2. Dashboard mostra:
   └─ Lead completo (escola + contato)
   └─ Score + reasoning da IA
   └─ Preview da mensagem

3. Humano decide:
   ├─ approve() → status='approved'
   ├─ edit_and_approve() → salva edit + aprova
   ├─ reject(reason) → status='rejected'
   └─ regenerate() → chama Writer novamente

4. send_approved_messages()
   └─ Busca status='approved' + sent_at=null
   └─ Envia via provider
   └─ Atualiza status='sent'
   └─ Cria interaction record
   └─ Loga no HubSpot
```

**REGRA ABSOLUTA**: NUNCA bypass (exceto follow-ups pré-aprovados)

---

### CAMADA 5: Presentation Layer (Streamlit)

**Responsabilidade**: Interface humana
```
Dashboard (6 páginas):

1. Overview (1_overview.py)
   └─ Métricas gerais, funil, gráficos

2. Approval Queue ⭐ (2_approval_queue.py)
   └─ Interface principal de aprovação
   └─ Card por lead com navegação
   └─ Preview + edição inline
   └─ Botões: Aprovar, Editar, Rejeitar, Regenerar

3. Leads (3_leads.py)
   └─ Tabela completa de leads
   └─ Filtros por status, score, cidade

4. Campaigns (4_campaigns.py)
   └─ Campanhas ativas
   └─ Performance de cada

5. Settings (5_settings.py)
   └─ Configurações do sistema
   └─ Ajustar ICP dinamicamente
   └─ Ver créditos APIs

6. Map View (6_map_view.py)
   └─ Visualização geográfica
   └─ Pins interativos
   └─ Filtros por score/status
```

---

## 🔄 Fluxo de Dados Completo
```
FASE 1: IMPORTAÇÃO
CSV (210k) → FilterAgent → DB (companies status='raw')
                    ↓
             Aplica 4 filtros
                    ↓
         DB (companies status='filtered', ~1.500)

FASE 2: QUALIFICAÇÃO
DB ('filtered') → QualifierAgent (Claude Haiku) → DB (score + priority)
                         ↓
            Status → 'qualified' (score >= 60)
                  ou 'disqualified' (score < 60)

FASE 3: ENRIQUECIMENTO
DB ('qualified') → EnricherAgent → Apollo/Snov/Hunter/Scraping
                         ↓
                  Salva: website, tech
                         ↓
            Status → 'enriched'

FASE 4: BUSCA DECISORES
DB ('enriched') → ContactFinderAgent → APIs/Scraping
                         ↓
                  Insere: contacts table
                         ↓
         Marca: is_decision_maker=true

FASE 5: GERAÇÃO MENSAGEM
DB (companies + contacts) → ResearcherAgent (opcional) → Context
                                   ↓
                            WriterAgent (Claude Sonnet)
                                   ↓
                         Mensagem personalizada
                                   ↓
                         approval_queue table
                                   ↓
                    Status: 'pending_approval'
                                   ↓
                         ⚠️ AGUARDA HUMANO

FASE 6: APROVAÇÃO
Dashboard → Humano revisa → Decisão
                              ↓
                    [Aprovar / Editar / Rejeitar]
                              ↓
                    Status: 'approved'

FASE 7: ENVIO
send_approved_messages() → Brevo/Gmail API
                              ↓
                    Cria: interactions table
                              ↓
                    Loga: HubSpot engagement
                              ↓
            approval_queue.status → 'sent'
            interactions.status → 'sent'

FASE 8: TRACKING
Webhooks (Brevo/Gmail) → Atualiza status
                              ↓
                    'delivered' → 'opened' → 'replied'
                              ↓
                    Sincroniza: HubSpot
                              ↓
            Se replied: alerta humano para responder
```

---

## 🔗 Integrações Detalhadas

### Google Maps API (Geocoding)
```python
Uso: Buscar lat/long para escolas sem coordenadas

Input: Endereço + Município + UF
Output: (latitude, longitude)

Rate Limit: 50 req/s (usamos 2 req/s)
Custo: $200 créditos grátis/mês (~40k geocodificações)

Implementação:
  • tools/geocoder.py
  • Batch de 50 escolas por execução
  • Intervalo 0.5s entre chamadas
  • Salva: geocoded=true, geocode_source='google_geocoding'
```

### Google Search (Phone Finding)
```python
Uso: Buscar telefones faltantes

Input: Nome escola + Município
Output: Telefone BR formatado

Método preferido: Google Custom Search JSON API (100 queries/dia grátis)
  Alternativa: googlesearch-python (scraping, menos estável)
  Alternativa: SerpAPI (100/mês grátis)

⚠️ EVITAR scraping direto do Google (contra ToS, bloqueio rápido)

Rate Limit: 20 buscas/execução
Custo: Grátis (planos free)

Implementação:
  • tools/phone_finder.py
  • Regex: \(?\d{2}\)?\s?\d{4,5}-?\d{4}
  • Salva: phone_source='google_search'
```

---

## 📊 Custos e Escalabilidade

### Fase Teste (40-60 leads/mês)
```
Claude API:
  • Haiku (qualificação): R$5-10/mês
  • Sonnet (escrita): R$5-10/mês
  
Outras ferramentas: GRÁTIS
  • Supabase: 500MB
  • HubSpot: Plano gratuito
  • Brevo: 300/dia
  • Google Maps: $200 créditos
  • APIs enriquecimento: Planos free

TOTAL: R$10-20/mês
```

### Fase Escala (100-200 leads/mês)
```
Claude API: R$30-50/mês
Apollo Pro: R$250/mês (opcional)
Hunter Starter: R$250/mês (opcional)

TOTAL: R$30-550/mês (conforme necessidade)
```

---

**Para especificações de código**: Veja `STANDARDS.md`  
**Para detalhes de implementação**: Veja `IMPLEMENTATION.md`