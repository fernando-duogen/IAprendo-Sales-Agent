-- ============================================================================
-- Migration 019: Agenda de Atividades + Metas (F1 do redesign v2 "Dia de Venda")
-- ============================================================================
-- Contexto: cria as fundacoes da Agenda (activities) e das Metas (goals) +
--   trigger de eventos de etapa (stage_changed) que torna o fechamento de mes
--   IMUTAVEL (sem ele, propostas/clientes/valor contados do status atual
--   mudariam retroativamente — ver docs/SPEC_AGENDA_METAS.md §4.3).
-- Precondicoes: schemas.sql base + APLICAR-013 (commercial_stage) aplicados.
-- 100% ADDITIVE: a v1 ignora tudo isto sem quebrar.
-- APLICAR: Execute este arquivo INTEIRO no Supabase SQL Editor (1x; idempotente).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. TABELA activities — agenda de atividades (SPEC §1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Vinculos (todos opcionais: "aprovar_mensagens"/"goal_reminder" nao tem escola)
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE SET NULL,
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,

    -- Dono e conteudo
    owner_username VARCHAR(100) NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(300) NOT NULL,
    details TEXT,

    -- Prazo e prioridade
    due_at TIMESTAMPTZ NOT NULL,
    priority SMALLINT NOT NULL DEFAULT 2,

    -- Estado (SPEC §1.1: open -> done | snoozed | dismissed; terminais nao reabrem)
    status VARCHAR(20) NOT NULL DEFAULT 'open',

    -- Origem (SPEC §1.3)
    source VARCHAR(20) NOT NULL DEFAULT 'manual',   -- manual | auto | ialex
    auto_rule VARCHAR(50),                          -- qual regra gerou (auditoria)
    dedupe_key VARCHAR(200),                        -- idempotencia da geracao automatica
    sequence_step SMALLINT,                         -- cadencia de toques (SPEC §1.3)

    -- Resolucao (SPEC §9: distingue "trabalho feito" de "gatilho morto")
    resolution VARCHAR(30),
    snooze_count SMALLINT NOT NULL DEFAULT 0,
    snoozed_until TIMESTAMPTZ,

    -- Auditoria de transicoes
    completed_at TIMESTAMPTZ,
    completed_by VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_activity_type CHECK (type IN (
        'follow_up', 'responder', 'ligar', 'preparar_reuniao',
        'registrar_resultado', 'aprovar_mensagens', 'tarefa'
    )),
    CONSTRAINT valid_activity_status CHECK (status IN ('open', 'done', 'snoozed', 'dismissed')),
    CONSTRAINT valid_activity_source CHECK (source IN ('manual', 'auto', 'ialex')),
    CONSTRAINT valid_activity_priority CHECK (priority BETWEEN 1 AND 3),
    CONSTRAINT valid_activity_resolution CHECK (resolution IN (
        'manual', 'auto_trabalho_detectado', 'auto_gatilho_morto',
        'expirada', 'lead_transferido'
    ) OR resolution IS NULL)
);

-- Indices (SPEC: agenda por dono + varredor por escola)
CREATE UNIQUE INDEX IF NOT EXISTS idx_activities_dedupe
    ON activities(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_activities_owner_due
    ON activities(owner_username, status, due_at);
CREATE INDEX IF NOT EXISTS idx_activities_company ON activities(company_id);

-- Trigger updated_at (function ja existe no schema base)
DROP TRIGGER IF EXISTS update_activities_updated_at ON activities;
CREATE TRIGGER update_activities_updated_at
    BEFORE UPDATE ON activities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS (defense-in-depth: anon bloqueado; o app usa service_role que bypassa)
ALTER TABLE activities ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE activities IS 'Agenda de atividades do time (v2). Ciclo de vida e regras: docs/SPEC_AGENDA_METAS.md';
COMMENT ON COLUMN activities.resolution IS 'Como foi resolvida: manual | auto_trabalho_detectado | auto_gatilho_morto | expirada | lead_transferido';
COMMENT ON COLUMN activities.dedupe_key IS 'Chave de idempotencia da geracao automatica (formatos na SPEC §1.3)';

-- ----------------------------------------------------------------------------
-- 2. TABELA goals — metas por usuario/metrica/periodo (SPEC §4)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    username VARCHAR(100) NOT NULL,        -- 'fernando' | 'lizianne' | 'felipe' | 'team'
    metric VARCHAR(50) NOT NULL,
    period_type VARCHAR(10) NOT NULL DEFAULT 'month',
    period_start DATE NOT NULL,            -- SEMPRE normalizado (dia 1 / segunda-feira)
    target NUMERIC(12,2) NOT NULL,

    -- Trilha de mudancas (SPEC §4.1: mudanca permitida, nunca silenciosa;
    -- o rollover automatico se declara como {by:'system', reason:'herdada'})
    revision_log JSONB NOT NULL DEFAULT '[]',

    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_goal_metric CHECK (metric IN (
        'emails_enviados', 'respostas', 'reunioes_realizadas',
        'propostas', 'clientes', 'valor_fechado', 'atividades_concluidas'
    )),
    CONSTRAINT valid_goal_period CHECK (period_type IN ('week', 'month', 'quarter')),
    CONSTRAINT uq_goal UNIQUE (username, metric, period_type, period_start)
);
-- SEM coluna `current`: o realizado e SEMPRE calculado ao vivo de eventos
-- timestamped (interactions/meetings/stage_changed) — ver SPEC §4.3.

DROP TRIGGER IF EXISTS update_goals_updated_at ON goals;
CREATE TRIGGER update_goals_updated_at
    BEFORE UPDATE ON goals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

ALTER TABLE goals ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE goals IS 'Metas por usuario+metrica+periodo (v2). Ciclo: docs/SPEC_AGENDA_METAS.md §4';

-- ----------------------------------------------------------------------------
-- 3. meetings: dono e criador (blueprint §7)
-- ----------------------------------------------------------------------------
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100);
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS created_by VARCHAR(100);
CREATE INDEX IF NOT EXISTS idx_meetings_owner ON meetings(owner_username)
    WHERE owner_username IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 4. interactions: ampliar a CHECK constraint para aceitar 'stage_changed'
--    (CRITICO: sem isto o trigger abaixo falharia em TODA mudanca de etapa)
-- ----------------------------------------------------------------------------
ALTER TABLE interactions DROP CONSTRAINT IF EXISTS valid_interaction_type;
ALTER TABLE interactions ADD CONSTRAINT valid_interaction_type CHECK (type IN (
    'email_sent', 'email_delivered', 'email_opened', 'email_clicked', 'email_replied', 'email_bounced',
    'whatsapp_sent', 'whatsapp_delivered', 'whatsapp_read', 'whatsapp_replied',
    'linkedin_sent', 'linkedin_opened', 'linkedin_replied',
    'meeting_scheduled', 'meeting_completed', 'call_made', 'call_received',
    'stage_changed'
));

-- ----------------------------------------------------------------------------
-- 5. TRIGGER stage_changed — eventos imutaveis de mudanca de etapa (SPEC §4.3)
--    Captura TODOS os caminhos (dashboard v1, v2, IAlex, HubSpot pull) de uma
--    vez. "Virou cliente em junho" passa a ser fato eterno — metas de
--    propostas/clientes/valor nao mudam retroativamente.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION log_stage_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.status IS DISTINCT FROM NEW.status)
       OR (OLD.commercial_stage IS DISTINCT FROM NEW.commercial_stage) THEN
        INSERT INTO interactions (company_id, type, channel, subject, metadata)
        VALUES (
            NEW.id,
            'stage_changed',
            'system',
            CONCAT('Etapa: ',
                   COALESCE(OLD.commercial_stage, OLD.status, '?'), ' -> ',
                   COALESCE(NEW.commercial_stage, NEW.status, '?')),
            jsonb_build_object(
                'from_status', OLD.status,
                'to_status', NEW.status,
                'from_stage', OLD.commercial_stage,
                'to_stage', NEW.commercial_stage,
                'valor_mensal_proposto', NEW.valor_mensal_proposto,
                'valor_mensal_fechado', NEW.valor_mensal_fechado,
                'owner_username', NEW.owner_username
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_log_stage_change ON companies;
CREATE TRIGGER trg_log_stage_change
    AFTER UPDATE OF status, commercial_stage ON companies
    FOR EACH ROW
    EXECUTE FUNCTION log_stage_change();

-- ============================================================================
-- "Success. No rows returned" = aplicado. Criados: 2 tabelas (activities,
-- goals) + 2 colunas em meetings + constraint ampliada em interactions +
-- trigger trg_log_stage_change. A v1 segue funcionando identica.
-- ============================================================================
