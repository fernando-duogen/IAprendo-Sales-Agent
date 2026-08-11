-- =====================================================================
-- 023 — Nota do Google + link do Maps na escola (Ago/2026)
-- =====================================================================
-- 100% ADITIVA: so adiciona colunas novas (nada e alterado/removido).
--
-- Por que: o Google Places JA retorna `rating` e `googleMapsUri` no
-- fieldMask que pagamos (integrations/google_places.py DEFAULT_FIELDS),
-- mas o enricher descartava os dois. Passamos a gravar:
--   - google_rating: nota 1-5 dos pais/comunidade (sinal de qualificacao)
--   - google_reviews_count: quantas avaliacoes sustentam a nota
--   - google_maps_url: atalho pro mapa/ficha da escola
--
-- Como aplicar: Supabase -> SQL Editor -> New query -> colar -> Run.
-- (Idempotente: pode rodar de novo sem efeito.)
-- =====================================================================

ALTER TABLE companies ADD COLUMN IF NOT EXISTS google_rating NUMERIC(2,1);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS google_reviews_count INTEGER;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS google_maps_url TEXT;

COMMENT ON COLUMN companies.google_rating IS
  'Nota da escola no Google (1.0-5.0), vinda do Places API no enriquecimento.';
COMMENT ON COLUMN companies.google_reviews_count IS
  'Qtd de avaliacoes que sustentam google_rating (nota com 3 reviews != com 300).';
COMMENT ON COLUMN companies.google_maps_url IS
  'Link direto da escola no Google Maps (atalho no painel).';

-- Indice parcial: usado para ordenar/filtrar por reputacao sem pesar a tabela
CREATE INDEX IF NOT EXISTS idx_companies_google_rating
  ON companies (google_rating DESC NULLS LAST)
  WHERE google_rating IS NOT NULL;

-- =====================================================================
-- ROLLBACK (se preciso):
--   DROP INDEX IF EXISTS idx_companies_google_rating;
--   ALTER TABLE companies DROP COLUMN IF EXISTS google_rating;
--   ALTER TABLE companies DROP COLUMN IF EXISTS google_reviews_count;
--   ALTER TABLE companies DROP COLUMN IF EXISTS google_maps_url;
-- =====================================================================
