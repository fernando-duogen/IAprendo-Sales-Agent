-- Migration 013: Stages comerciais reais em companies
-- ============================================================================
-- Substitui hack antigo de tag [crm:xxx] em companies.notes por colunas
-- dedicadas pra stages proposta/cliente/perdido, com valor, datas e motivo.
--
-- Contexto: o CRM antigo (dashboard/pages/4_CRM.py) usava notes LIKE '%[crm:proposta]%'
-- pra inferir stage. Nao tinha valor, data, nem motivo de perda. Esta migration
-- cria colunas reais pras tools novas do IAlex (registrar_proposta_enviada,
-- marcar_cliente_ganho, marcar_perdido) gravarem dados estruturados.
--
-- APLICAR: Execute no Supabase SQL Editor
-- ============================================================================

ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS commercial_stage TEXT,
  ADD COLUMN IF NOT EXISTS valor_mensal_proposto NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS valor_mensal_fechado NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS data_proposta TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS data_fechamento TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS motivo_perda_texto TEXT,
  ADD COLUMN IF NOT EXISTS motivo_perda_categoria TEXT;

-- Constraint leve: commercial_stage in (7 valores esperados), mas aceita NULL
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'companies_commercial_stage_chk'
  ) THEN
    ALTER TABLE companies
      ADD CONSTRAINT companies_commercial_stage_chk
      CHECK (commercial_stage IS NULL OR commercial_stage IN (
        'prospectado', 'contatado', 'respondeu', 'reuniao',
        'proposta', 'cliente', 'perdido'
      ));
  END IF;
END $$;

-- Index pra kanban rapido
CREATE INDEX IF NOT EXISTS idx_companies_commercial_stage
  ON companies(commercial_stage) WHERE commercial_stage IS NOT NULL;

COMMENT ON COLUMN companies.commercial_stage IS
  'Stage comercial manual. NULL = usar inferencia automatica (email/reply/meeting). Valores: prospectado, contatado, respondeu, reuniao, proposta, cliente, perdido.';
COMMENT ON COLUMN companies.valor_mensal_proposto IS
  'Valor mensal (R$) proposto ao cliente. Setado por IAlex ao registrar proposta enviada.';
COMMENT ON COLUMN companies.valor_mensal_fechado IS
  'Valor mensal (R$) efetivamente fechado. Setado por IAlex ao marcar cliente ganho.';
COMMENT ON COLUMN companies.data_proposta IS
  'Data/hora do envio da proposta comercial.';
COMMENT ON COLUMN companies.data_fechamento IS
  'Data/hora de fechamento do deal (cliente ou perdido).';
COMMENT ON COLUMN companies.motivo_perda_texto IS
  'Motivo de perda em texto livre, como Fernando descreveu originalmente.';
COMMENT ON COLUMN companies.motivo_perda_categoria IS
  'Enum classificado pela IA (Haiku) a partir de motivo_perda_texto. Valores esperados: preco, timing, concorrente, orcamento, nao_prioridade, outro.';
