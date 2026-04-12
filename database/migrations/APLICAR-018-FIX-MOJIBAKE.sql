-- Migration 018: Fix mojibake em peer_mun_nome / socio_mun_nome
-- =====================================================================
-- Contexto:
--   O CSV fonte `escolas_brasil_enriquecido.csv` usado pela migration 015
--   chegou da fonte upstream ja com caracteres U+FFFD (REPLACEMENT CHAR,
--   bytes \xEF\xBF\xBD) nos nomes de municipios com acentos. Exemplos:
--     "S\uFFFDo Paulo"      (correto: "São Paulo")
--     "Rorain\uFFFDpolis"   (correto: "Rorainópolis")
--     "Uiramut\uFFFD"       (correto: "Uiramutã")
--     "Nova Mamor\uFFFD"    (correto: "Nova Mamoré")
--
--   Rows afetadas (detectadas em 2026-04-12):
--     - school_analytics.peer_mun_nome : 10.561 rows
--     - school_analytics.socio_mun_nome:  8.287 rows
--
--   As tabelas `companies`, `school_censo_yearly` e `school_enem_yearly`
--   estao LIMPAS (0 replacement chars) — importaram de CSVs diferentes
--   com encoding correto. Por isso `school_censo_yearly.city` serve como
--   fonte limpa para propagar os nomes corretos.
--
-- Estrategia:
--   Para cada row corrompida em school_analytics, buscar o `city` da mesma
--   escola (mesmo inep_code) no school_censo_yearly, preferindo o vintage
--   mais recente (nome mais atual). Se encontrado, substitui.
--
--   As rows que NAO existem em school_censo_yearly ficam como estao — o
--   helper _clean_text no runtime remove o U+FFFD antes de exibir, e o
--   helper _resolve_school_names ja usa companies/school_censo_yearly
--   como fonte de verdade para nomes e municipios.
--
-- APLICAR: SQL Editor do Supabase (3 blocos)
-- =====================================================================

-- Bloco A: Fix peer_mun_nome
-- ---------------------------------------------------------------------
-- Usa DISTINCT ON para pegar o city do vintage mais recente por inep_code.
-- UPDATE ... FROM funciona em Postgres >= 9.1 (todas as versoes modernas).

WITH clean_cities AS (
    SELECT DISTINCT ON (inep_code)
        inep_code,
        city
    FROM school_censo_yearly
    WHERE city IS NOT NULL AND city <> ''
    ORDER BY inep_code, vintage_censo DESC
)
UPDATE school_analytics sa
SET peer_mun_nome = cc.city,
    updated_at    = NOW()
FROM clean_cities cc
WHERE sa.inep_code = cc.inep_code
  AND sa.peer_mun_nome LIKE '%' || E'\uFFFD' || '%';

-- Bloco B: Fix socio_mun_nome
-- ---------------------------------------------------------------------
-- Mesma estrategia. Em principio peer_mun_nome == socio_mun_nome (ambos
-- sao a cidade da escola, s? diferem se a escola estiver em municipios
-- distintos por alguma categorizacao exotica — nao e o caso no BR).

WITH clean_cities AS (
    SELECT DISTINCT ON (inep_code)
        inep_code,
        city
    FROM school_censo_yearly
    WHERE city IS NOT NULL AND city <> ''
    ORDER BY inep_code, vintage_censo DESC
)
UPDATE school_analytics sa
SET socio_mun_nome = cc.city,
    updated_at     = NOW()
FROM clean_cities cc
WHERE sa.inep_code = cc.inep_code
  AND sa.socio_mun_nome LIKE '%' || E'\uFFFD' || '%';

-- Bloco C: Smoke test pos-fix
-- ---------------------------------------------------------------------
-- Conta quantas rows ainda tem U+FFFD depois da correcao. Esperado:
--   Antes:  peer_mun_nome=10561, socio_mun_nome=8287
--   Depois: numeros bem baixos (rows cujo inep nao existe em censo_yearly)
-- Se alguma row sobrar, o runtime _clean_text remove o U+FFFD na hora
-- de exibir, e o _resolve_school_names ja usa companies/censo como fonte
-- primaria de nomes.

SELECT
    'peer_mun_nome' AS campo,
    COUNT(*)       AS rows_ainda_com_FFFD
FROM school_analytics
WHERE peer_mun_nome LIKE '%' || E'\uFFFD' || '%'
UNION ALL
SELECT
    'socio_mun_nome' AS campo,
    COUNT(*)        AS rows_ainda_com_FFFD
FROM school_analytics
WHERE socio_mun_nome LIKE '%' || E'\uFFFD' || '%';

-- =====================================================================
-- FIM MIGRATION 018
-- =====================================================================
-- Proximos passos (aplicados em seguida pelo codigo):
--   1. Adicionar _clean_text helper em agent/tools/enem_tools.py
--   2. Modificar _motivo_prioridade para aceitar municipio_clean via param
--   3. Modificar formatters (trajetoria_peer, contexto_municipal) para
--      aplicar _clean_text nos outputs
--   4. Blindar import_school_analytics.py para sanear bytes do U+FFFD
--      na leitura (prevent regression em re-imports)
