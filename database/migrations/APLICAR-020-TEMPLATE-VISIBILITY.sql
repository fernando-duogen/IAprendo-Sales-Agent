-- ============================================================================
-- APLICAR-020: Visibilidade de modelos de mensagem (Rodada 3 do redesign v2)
--
-- Blueprint v1.4: modelos sao COMPARTILHADOS por padrao (todo o time ve/usa);
-- um modelo pode ser PESSOAL (so o dono ve). O dashboard ja esta preparado:
-- sem estas colunas ele simplesmente mostra tudo (guard no codigo).
--
-- 100% ADDITIVE-ONLY (banco unico prod=dev — regra de ouro do redesign).
-- Rodar no SQL Editor do Supabase (projeto vgmvpghwkeirnjdbjcwl).
-- ============================================================================

ALTER TABLE message_templates
  ADD COLUMN IF NOT EXISTS visibility VARCHAR(20) NOT NULL DEFAULT 'shared',
  ADD COLUMN IF NOT EXISTS owner_username VARCHAR(100) DEFAULT NULL;

COMMENT ON COLUMN message_templates.visibility IS
  'shared (default, todo o time) | personal (so o owner_username ve)';
COMMENT ON COLUMN message_templates.owner_username IS
  'Dono do modelo quando visibility=personal (username de config/users.yaml)';

-- Templates pre-existentes ficam shared (default ja cobre, explicito por clareza)
UPDATE message_templates SET visibility = 'shared' WHERE visibility IS NULL;

-- Verificacao
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'message_templates'
  AND column_name IN ('visibility', 'owner_username');
