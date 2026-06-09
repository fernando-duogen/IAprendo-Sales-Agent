-- =====================================================================
-- RPCs de FACETS do mec_catalog (distinct rapido p/ os multiselects)
-- =====================================================================
-- O Importar/Mapa (versao online) montam os filtros UF / Cidade(cascata) /
-- Tipo / Porte a partir de valores DISTINCT do catalogo. PostgREST nao faz
-- DISTINCT; sem estas funcoes, a cascata de cidades exigiria puxar dezenas de
-- milhares de linhas. Estas RPCs fazem o DISTINCT no servidor (rapido).
--
-- Rode este bloco no Supabase SQL Editor 1x. Idempotente (create or replace).
-- =====================================================================

-- Distinct de cidades das UFs dadas (cascata UF -> Cidade).
CREATE OR REPLACE FUNCTION public.mec_catalog_cities(p_states text[] DEFAULT NULL)
RETURNS TABLE(city text)
LANGUAGE sql STABLE
AS $$
  SELECT DISTINCT mc.city
  FROM public.mec_catalog mc
  WHERE mc.city IS NOT NULL
    AND (
      p_states IS NULL
      OR array_length(p_states, 1) IS NULL
      OR mc.state = ANY(p_states)
    )
  ORDER BY 1
$$;

-- Distinct de states / dependencias / portes (poucos valores) num unico JSON.
CREATE OR REPLACE FUNCTION public.mec_catalog_facets()
RETURNS json
LANGUAGE sql STABLE
AS $$
  SELECT json_build_object(
    'states', (SELECT COALESCE(array_agg(DISTINCT state ORDER BY state), '{}')
               FROM public.mec_catalog WHERE state IS NOT NULL),
    'dependencias', (SELECT COALESCE(array_agg(DISTINCT admin_dependency ORDER BY admin_dependency), '{}')
                     FROM public.mec_catalog WHERE admin_dependency IS NOT NULL),
    'portes', (SELECT COALESCE(array_agg(DISTINCT school_size ORDER BY school_size), '{}')
               FROM public.mec_catalog WHERE school_size IS NOT NULL)
  )
$$;

-- Permitir chamada via PostgREST (so leitura de dado publico do MEC).
GRANT EXECUTE ON FUNCTION public.mec_catalog_cities(text[]) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.mec_catalog_facets() TO anon, authenticated, service_role;

-- =====================================================================
-- "Success. No rows returned" = RPCs criadas. A cascata UF->Cidade no
-- Importar/Mapa online passa a funcionar.
-- =====================================================================
