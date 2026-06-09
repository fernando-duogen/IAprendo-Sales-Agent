-- =====================================================================
-- RLS nas tabelas de dados do CRM (defense-in-depth)
-- =====================================================================
-- Liga Row Level Security nas tabelas com dados de negocio/PII. Efeito:
--   - service_role (a chave do APP, server-side) IGNORA RLS (BYPASSRLS) ->
--     o app, o IAlex e o backup continuam funcionando IGUAL.
--   - Com RLS ligado e SEM policy, as chaves anon/authenticated ficam
--     BLOQUEADAS -> mesmo que a chave anon (publica) vaze, ela NAO le nem
--     escreve esses dados via API REST.
--
-- Por que: hoje a protecao desses dados e so o login do app + a service_role
-- rodar server-side. Isto adiciona uma 2a camada (a base nega anon por padrao).
--
-- Impacto conhecido (aceitavel): o Cloudflare Worker (dados.iaprendo.com.br)
-- le 'companies' com a chave anon so pra resolver company_id do tracking OPR.
-- Com RLS, essa leitura volta VAZIA (nao da erro) -> o worker segue sem
-- company_id (ja tem try/except: "continua sem company_id"). Os pageviews
-- continuam sendo gravados por inep. Se quiser manter o company_id, depois
-- troque a chave do worker pra service_role.
--
-- Rode este bloco no Supabase SQL Editor. Idempotente (rodar de novo nao quebra).
-- =====================================================================

DO $$
DECLARE
    t TEXT;
    alvos TEXT[] := ARRAY[
        'companies', 'contacts', 'interactions', 'approval_queue',
        'meetings', 'campaigns'
    ];
BEGIN
    FOREACH t IN ARRAY alvos LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
            RAISE NOTICE 'RLS ligado em %', t;
        ELSE
            RAISE NOTICE 'tabela % nao existe (pulado)', t;
        END IF;
    END LOOP;
END $$;

-- =====================================================================
-- "Success" = RLS ligado. Teste o app depois (busca/aprovacao devem funcionar
-- normal, pois usam service_role). Se algo der "permission denied" pra anon,
-- e exatamente o objetivo: a anon nao acessa mais o CRM.
-- =====================================================================
