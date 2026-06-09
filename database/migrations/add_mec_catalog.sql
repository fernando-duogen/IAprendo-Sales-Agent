-- =====================================================================
-- CATALOGO MEC ONLINE — base completa de escolas pesquisavel no Cloud
-- =====================================================================
-- Tabela LEVE (so colunas de busca/display) com as ~185k escolas da base
-- MEC. Substitui a dependencia do CSV de 80MB (que so existe no PC local).
-- Busca = SQL com filtro (nunca carrega tudo na RAM) -> funciona no Cloud.
--
-- Rode este bloco no Supabase SQL Editor 1x. Depois, no PC local, rode:
--   venv\Scripts\python.exe scripts\load_mec_catalog.py
-- (carrega o CSV -> esta tabela; ~poucos minutos)
-- =====================================================================

CREATE TABLE IF NOT EXISTS mec_catalog (
    inep_code           TEXT PRIMARY KEY,
    name                TEXT,
    name_norm           TEXT,   -- nome sem acento/minusculo (busca)
    city                TEXT,
    city_norm           TEXT,   -- cidade sem acento/minusculo (busca)
    state               VARCHAR(2),
    regiao              TEXT,
    bairro              TEXT,
    cep                 TEXT,
    address             TEXT,
    phone               TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    admin_category      TEXT,
    admin_dependency    TEXT,
    categoria_privada   TEXT,
    school_size         TEXT,
    perfil_ensino       TEXT,
    education_levels    TEXT,
    levels_norm         TEXT,   -- niveis sem acento (busca: "medio" acha "Médio")
    localizacao         TEXT,
    nivel_tecnologico   TEXT,
    total_matriculas    INTEGER,
    matriculas_fund_af  INTEGER,
    matriculas_medio    INTEGER,
    total_docentes      INTEGER,
    qt_coordenadores    INTEGER,
    fonte_dados         TEXT,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mec_catalog_state ON mec_catalog(state);
CREATE INDEX IF NOT EXISTS idx_mec_catalog_city_norm ON mec_catalog(city_norm);
CREATE INDEX IF NOT EXISTS idx_mec_catalog_name_norm ON mec_catalog(name_norm);

-- =====================================================================
-- RLS (Row Level Security)
-- =====================================================================
-- Ligamos o RLS por boa pratica. NAO precisa criar policy nenhuma:
-- o backend (loader + busca online) usa a chave service_role, que IGNORA
-- o RLS (BYPASSRLS) -> continua lendo/escrevendo normal. Com RLS ligado e
-- sem policy, a chave anon (publica, do Cloudflare Worker) fica bloqueada
-- de tocar nesta tabela. Resultado: mesmo funcionamento + mais seguro.
ALTER TABLE mec_catalog ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- "Success. No rows returned" = tabela criada. Agora rode o load no PC.
-- =====================================================================
