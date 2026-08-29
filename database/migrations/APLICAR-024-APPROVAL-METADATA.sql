-- =====================================================================
-- APLICAR-024 — approval_queue.metadata (JSONB)
-- =====================================================================
-- POR QUE: o codigo grava overrides por mensagem em `metadata` desde que o
-- "Enviar como" e o override de anexos existem, mas a coluna NUNCA foi criada.
-- O banco responde: 42703: column "metadata" does not exist.
--
-- Enquanto isso so afetava esses dois recursos (pouco usados), passou batido.
-- Em 28/08/2026 o carimbo de identidade (commit 4148d0f) passou a preencher
-- send_as_username em TODA aprovacao -> `metadata` entrou em todo UPDATE ->
-- a aprovacao quebrou para todos os usuarios ("Falha ao aprovar.").
--
-- O codigo ja foi tornado TOLERANTE (approve_message repete sem o campo, e o
-- send_approved tem fallback no select), entao aprovar funciona mesmo SEM esta
-- migration. Ela habilita o que estava inerte:
--   metadata.send_as_username  -> assinatura/anexos corretos no envio agendado
--   metadata.attachment_urls   -> override de anexos por mensagem
--
-- Additive-only e idempotente: pode rodar mais de uma vez sem efeito colateral.
-- Aplicar no SQL Editor do Supabase (o MCP e read-only).
-- =====================================================================

ALTER TABLE approval_queue ADD COLUMN IF NOT EXISTS metadata JSONB;

COMMENT ON COLUMN approval_queue.metadata IS
  'Overrides por mensagem: send_as_username (identidade que assina o e-mail) e '
  'attachment_urls (anexos desta mensagem). Lido por workflows/send_approved.py.';

-- Conferencia (deve retornar 1 linha, jsonb):
-- select column_name, data_type from information_schema.columns
--  where table_name = 'approval_queue' and column_name = 'metadata';
