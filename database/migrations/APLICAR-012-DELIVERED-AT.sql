-- Migration 012: Adicionar coluna delivered_at em approval_queue
-- Corrige bug silencioso em tools/email_tracker.py linha 274:
-- o sync de eventos do Brevo mapeia "delivered" -> "delivered_at",
-- mas a coluna nunca existiu. Eventos de entrega estavam sendo
-- silenciosamente descartados.
--
-- APLICAR: Execute no Supabase SQL Editor
-- ============================================================================

ALTER TABLE approval_queue
  ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_approval_queue_delivered_at
  ON approval_queue(delivered_at) WHERE delivered_at IS NOT NULL;

COMMENT ON COLUMN approval_queue.delivered_at IS
  'Timestamp do evento delivered do Brevo. Preenchido por tools/email_tracker.py via webhook ou sync periodico.';
