-- ============================================================================
-- IAprendo Sales Agent - Database Schema
-- ============================================================================
-- Versão: 1.0.0
-- Database: PostgreSQL 15+ (Supabase)
-- Total de Tabelas: 7
-- Executar no: Supabase SQL Editor
-- ============================================================================

-- ----------------------------------------------------------------------------
-- EXTENSÕES (Opcional - Comentadas por Padrão)
-- ----------------------------------------------------------------------------
-- ATENÇÃO: Habilite apenas se necessário para queries geoespaciais avançadas
-- Alguns ambientes Supabase podem ter problemas com estas extensões

-- CREATE EXTENSION IF NOT EXISTS cube;
-- CREATE EXTENSION IF NOT EXISTS earthdistance;

-- Para habilitar busca geoespacial por raio:
-- 1. Descomente as 2 linhas acima
-- 2. Execute no Supabase SQL Editor
-- 3. Use: SELECT * FROM companies WHERE earth_distance(ll_to_earth(lat, lng), ll_to_earth(?, ?)) < ?

-- ----------------------------------------------------------------------------
-- TABELA 1: companies (Escolas/Leads)
-- ----------------------------------------------------------------------------
-- Armazena dados das escolas/leads em diferentes estágios do funil
-- Chave única: inep_code (evita duplicatas)

CREATE TABLE IF NOT EXISTS companies (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inep_code VARCHAR(20) UNIQUE NOT NULL,  -- Código INEP (chave única)
    name VARCHAR(500) NOT NULL,

    -- Localização
    city VARCHAR(200),
    state VARCHAR(2),
    address TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),

    -- Classificação
    admin_category VARCHAR(100),     -- Ex: "Pública", "Privada"
    admin_dependency VARCHAR(100),   -- Ex: "Municipal", "Estadual"
    education_levels TEXT,           -- Ex: "Fundamental, Médio"
    school_size VARCHAR(50),         -- Ex: "Grande", "Médio"

    -- Contato
    phone VARCHAR(50),
    website VARCHAR(500),

    -- Qualificação IA
    status VARCHAR(50) DEFAULT 'raw',  -- raw, filtered, qualified, enriched, contacted
    qualification_score INTEGER,        -- 0-100 (gerado por Claude)
    qualification_reasoning TEXT,       -- Por que este score?

    -- Metadata
    source VARCHAR(100) DEFAULT 'csv_import',
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_contacted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_score CHECK (qualification_score IS NULL OR (qualification_score >= 0 AND qualification_score <= 100)),
    CONSTRAINT valid_state CHECK (state ~ '^[A-Z]{2}$' OR state IS NULL)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_companies_inep ON companies(inep_code);
CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_companies_score ON companies(qualification_score DESC);
CREATE INDEX IF NOT EXISTS idx_companies_city_state ON companies(city, state);
CREATE INDEX IF NOT EXISTS idx_companies_location ON companies(latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_created_at ON companies(created_at DESC);

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- TABELA 2: contacts (Decisores/Pessoas de Contato)
-- ----------------------------------------------------------------------------
-- Armazena pessoas de contato encontradas (diretores, coordenadores, etc)

CREATE TABLE IF NOT EXISTS contacts (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,

    -- Dados Pessoais
    full_name VARCHAR(200) NOT NULL,
    role VARCHAR(200),              -- Ex: "Diretor", "Coordenador Pedagógico"
    email VARCHAR(300),
    phone VARCHAR(50),
    linkedin_url VARCHAR(500),

    -- Validação
    email_verified BOOLEAN DEFAULT FALSE,
    phone_verified BOOLEAN DEFAULT FALSE,

    -- Source
    source VARCHAR(100),            -- apollo, snov, hunter, scraping, manual
    confidence_score INTEGER,       -- 0-100 (confiança nos dados)

    -- Metadata
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$' OR email IS NULL),
    CONSTRAINT at_least_one_contact CHECK (email IS NOT NULL OR phone IS NOT NULL OR linkedin_url IS NOT NULL)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_contacts_company_id ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);
CREATE INDEX IF NOT EXISTS idx_contacts_source ON contacts(source);

-- Trigger para updated_at
CREATE TRIGGER update_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- TABELA 3: approval_queue (Fila de Aprovação Humana)
-- ----------------------------------------------------------------------------
-- ⭐ CRÍTICO - Mensagens aguardando aprovação humana antes do envio
-- NUNCA enviar sem passar por esta fila (Regra #1 do sistema)

CREATE TABLE IF NOT EXISTS approval_queue (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,

    -- Mensagem
    subject VARCHAR(500) NOT NULL,
    body TEXT NOT NULL,
    channel VARCHAR(50) NOT NULL,   -- email, whatsapp, linkedin

    -- Status
    status VARCHAR(50) DEFAULT 'pending',  -- pending, approved, rejected, sent

    -- Aprovação
    approved_by VARCHAR(200),       -- Nome de quem aprovou
    approved_at TIMESTAMP WITH TIME ZONE,
    rejection_reason TEXT,

    -- Edições (mensagem pode ser editada antes do envio)
    edited BOOLEAN DEFAULT FALSE,
    original_subject VARCHAR(500),
    original_body TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_channel CHECK (channel IN ('email', 'whatsapp', 'linkedin')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'approved', 'rejected', 'sent'))
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_approval_queue_status ON approval_queue(status);
CREATE INDEX IF NOT EXISTS idx_approval_queue_company ON approval_queue(company_id);
CREATE INDEX IF NOT EXISTS idx_approval_queue_created_at ON approval_queue(created_at DESC);

-- Trigger para updated_at
CREATE TRIGGER update_approval_queue_updated_at
    BEFORE UPDATE ON approval_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- TABELA 4: interactions (Histórico Completo)
-- ----------------------------------------------------------------------------
-- Registra TODAS as interações com leads (enviado, aberto, respondido, etc)

CREATE TABLE IF NOT EXISTS interactions (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    approval_queue_id UUID REFERENCES approval_queue(id) ON DELETE SET NULL,

    -- Tipo de Interação
    type VARCHAR(50) NOT NULL,      -- email_sent, email_opened, email_clicked, email_replied, meeting_scheduled, etc
    channel VARCHAR(50) NOT NULL,   -- email, whatsapp, linkedin, phone

    -- Conteúdo
    subject VARCHAR(500),
    message_snippet TEXT,           -- Primeiras 500 chars da mensagem

    -- Metadata
    metadata JSONB,                 -- Dados específicos (tracking IDs, links clicados, etc)

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_interaction_type CHECK (type IN (
        'email_sent', 'email_delivered', 'email_opened', 'email_clicked', 'email_replied', 'email_bounced',
        'whatsapp_sent', 'whatsapp_delivered', 'whatsapp_read', 'whatsapp_replied',
        'linkedin_sent', 'linkedin_opened', 'linkedin_replied',
        'meeting_scheduled', 'meeting_completed', 'call_made', 'call_received'
    ))
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_interactions_company_id ON interactions(company_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interactions(type);
CREATE INDEX IF NOT EXISTS idx_interactions_created_at ON interactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_metadata ON interactions USING GIN (metadata);

-- ----------------------------------------------------------------------------
-- TABELA 5: meetings (Reuniões Agendadas)
-- ----------------------------------------------------------------------------
-- Armazena reuniões/calls agendados com leads

CREATE TABLE IF NOT EXISTS meetings (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,

    -- Agendamento
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 30,

    -- Detalhes
    title VARCHAR(300) NOT NULL,
    description TEXT,
    location VARCHAR(500),          -- Endereço físico, link Zoom, etc
    meeting_type VARCHAR(50),       -- online, in_person, phone

    -- Status
    status VARCHAR(50) DEFAULT 'scheduled',  -- scheduled, completed, cancelled, no_show

    -- Notas pós-reunião
    outcome VARCHAR(100),           -- interested, not_interested, follow_up, closed
    notes TEXT,

    -- Integration IDs (Google Calendar, HubSpot, etc)
    google_calendar_id VARCHAR(500),
    hubspot_engagement_id VARCHAR(100),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_meeting_status CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    CONSTRAINT valid_meeting_outcome CHECK (outcome IN ('interested', 'not_interested', 'follow_up', 'closed', 'pending') OR outcome IS NULL)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_meetings_company_id ON meetings(company_id);
CREATE INDEX IF NOT EXISTS idx_meetings_scheduled_at ON meetings(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON meetings(status);

-- Trigger para updated_at
CREATE TRIGGER update_meetings_updated_at
    BEFORE UPDATE ON meetings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ----------------------------------------------------------------------------
-- TABELA 6: api_usage (Controle de Créditos/Rate Limiting)
-- ----------------------------------------------------------------------------
-- ⭐ CRÍTICO - Rate limiting persistente que sobrevive a restarts
-- Rastreia uso de APIs pagas (Anthropic, Apollo, Snov, Hunter, Google Maps)

CREATE TABLE IF NOT EXISTS api_usage (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- API
    api_name VARCHAR(100) NOT NULL,      -- anthropic, apollo, snov, hunter, google_maps
    endpoint VARCHAR(300),               -- Endpoint específico chamado

    -- Uso
    credits_used INTEGER DEFAULT 1,      -- Quantos créditos consumiu
    success BOOLEAN DEFAULT TRUE,        -- Chamada teve sucesso?

    -- Response info
    status_code INTEGER,
    response_time_ms DECIMAL(10, 2),
    error_message TEXT,

    -- Context
    context JSONB,                       -- Metadata adicional (company_id, operation, etc)

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_api_name CHECK (api_name IN ('anthropic', 'apollo', 'snov', 'hunter', 'google_maps', 'brevo', 'hubspot'))
);

-- Índices CRÍTICOS para rate limiting
CREATE INDEX IF NOT EXISTS idx_api_usage_api_name ON api_usage(api_name);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_api_date ON api_usage(api_name, created_at DESC);

-- ----------------------------------------------------------------------------
-- TABELA 7: campaigns (Campanhas - Futuro)
-- ----------------------------------------------------------------------------
-- Agrupa envios em campanhas (futuro)

CREATE TABLE IF NOT EXISTS campaigns (
    -- Identificação
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(300) NOT NULL,
    description TEXT,

    -- Configuração
    channel VARCHAR(50) NOT NULL,        -- email, whatsapp, linkedin
    target_filters JSONB,                -- Filtros aplicados (city, score_min, etc)

    -- Status
    status VARCHAR(50) DEFAULT 'draft',  -- draft, active, paused, completed

    -- Métricas
    total_sent INTEGER DEFAULT 0,
    total_opened INTEGER DEFAULT 0,
    total_clicked INTEGER DEFAULT 0,
    total_replied INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_campaign_status CHECK (status IN ('draft', 'active', 'paused', 'completed'))
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON campaigns(created_at DESC);

-- Trigger para updated_at
CREATE TRIGGER update_campaigns_updated_at
    BEFORE UPDATE ON campaigns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VIEWS ÚTEIS (Opcional)
-- ============================================================================

-- View: Leads qualificados prontos para contato
CREATE OR REPLACE VIEW leads_qualified AS
SELECT
    c.id,
    c.inep_code,
    c.name,
    c.city,
    c.state,
    c.qualification_score,
    c.status,
    COUNT(DISTINCT ct.id) as contact_count,
    MAX(i.created_at) as last_interaction_at
FROM companies c
LEFT JOIN contacts ct ON ct.company_id = c.id
LEFT JOIN interactions i ON i.company_id = c.id
WHERE c.status = 'qualified'
  AND c.qualification_score >= 70
GROUP BY c.id;

-- View: Estatísticas de API usage (últimos 30 dias)
CREATE OR REPLACE VIEW api_usage_monthly AS
SELECT
    api_name,
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as total_calls,
    SUM(credits_used) as total_credits,
    AVG(response_time_ms) as avg_response_time_ms,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as error_count
FROM api_usage
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY api_name, DATE_TRUNC('day', created_at)
ORDER BY date DESC, api_name;

-- ============================================================================
-- DADOS DE TESTE (Opcional - Descomentar para popular tabela de teste)
-- ============================================================================

-- INSERT INTO companies (inep_code, name, city, state, status) VALUES
-- ('43000001', 'Escola Teste 1', 'Porto Alegre', 'RS', 'raw'),
-- ('43000002', 'Escola Teste 2', 'Porto Alegre', 'RS', 'filtered');

-- ============================================================================
-- FIM DO SCHEMA
-- ============================================================================
-- Total de Tabelas: 7
-- Total de Índices: ~20
-- Total de Triggers: 4
-- Total de Views: 2
-- ============================================================================
