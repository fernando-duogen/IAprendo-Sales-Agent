-- Migration 014: Tabela de overrides manuais de nome de rede
-- ============================================================================
-- O algoritmo _derivar_nome_rede em agent/brain.py e heuristico (prefixo
-- comum dos nomes das escolas, com stopwords). Ele falha em redes onde
-- os nomes das escolas compartilham termos religiosos/genericos como "Mae",
-- "Deus", "Jesus", "Anjo", retornando esses como nome da rede.
--
-- Esta tabela armazena correcoes manuais feitas via aba Redes no dashboard.
-- Sempre consultada antes da derivacao heuristica (camada 1 do resolver).
--
-- APLICAR: Execute no Supabase SQL Editor
-- ============================================================================

CREATE TABLE IF NOT EXISTS rede_overrides (
    cnpj_mantenedora TEXT PRIMARY KEY,
    nome_oficial TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'fernando'
);

CREATE INDEX IF NOT EXISTS idx_rede_overrides_updated
    ON rede_overrides(updated_at DESC);

COMMENT ON TABLE rede_overrides IS
    'Overrides manuais de nome de rede quando a derivacao heuristica falha. PK = cnpj_mantenedora da tabela companies.';
COMMENT ON COLUMN rede_overrides.nome_oficial IS
    'Nome oficial da rede definido por Fernando (ex: "Rede ICM"). Tem precedencia sobre a derivacao heuristica.';
