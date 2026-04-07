-- Migration 006: Agendamento de envio de emails
-- Adiciona campo scheduled_send_at à tabela approval_queue
-- para permitir agendar horário de envio (individual ou em massa).
--
-- Se scheduled_send_at = NULL → envia imediatamente ao ser aprovada (comportamento atual)
-- Se scheduled_send_at = futuro → aguarda até o horário chegar para enviar
--
-- APLICAR: Execute este SQL no Supabase SQL Editor

ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS scheduled_send_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX IF NOT EXISTS idx_approval_queue_scheduled ON approval_queue(scheduled_send_at);

COMMENT ON COLUMN approval_queue.scheduled_send_at IS 'Horario agendado para envio. NULL = enviar imediatamente ao ser aprovada.';
