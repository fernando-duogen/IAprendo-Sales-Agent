-- Migration 016: school_censo_yearly (serie historica individual por escola)
-- =====================================================================
-- Armazena snapshot anual do Censo Escolar por escola (CO_ENTIDADE = INEP).
-- Permite analises de evolucao individual ao longo dos anos para escolas
-- que participaram do Censo em multiplos anos.
--
-- Chave composta natural: (inep_code, vintage_censo)
-- Um registro por escola por ano.
--
-- Contexto:
--   - Censo 2020-2024: arquivo monolitico microdados_ed_basica_{ANO}.csv
--     (ate 426 colunas, 1 linha por escola). Processado pelo pipeline
--     scripts/historico/process_censo_year.py.
--   - Censo 2025: INEP mudou formato para multi-arquivo (Tabela_Escola +
--     Tabela_Matricula + Tabela_Docente + Tabela_Turma + Tabela_Gestor +
--     Tabela_Curso_Tecnico). Ja foi integrado em companies via migration 010.
--     Para popular school_censo_yearly com 2025, basta copiar de companies.
--
-- Por que NAO estender companies:
--   - companies ja tem 219+ colunas
--   - Multiplicar por 6 anos seria inviavel (30 cols * 6 anos = 180 colunas novas)
--   - Normalizacao por tempo e' mais limpa e escala para anos futuros
--
-- APLICAR: Execute no Supabase SQL Editor (copie TUDO de uma vez)
-- =====================================================================

CREATE TABLE IF NOT EXISTS school_censo_yearly (
    -- Identidade
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inep_code VARCHAR(20) NOT NULL,
    vintage_censo SMALLINT NOT NULL,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,

    -- Identidade snapshot (nome/bairro podem ter mudado entre anos)
    name TEXT,
    city TEXT,
    state VARCHAR(2),
    bairro TEXT,
    cep VARCHAR(10),
    tp_dependencia SMALLINT,
    categoria_privada SMALLINT,
    localizacao SMALLINT,
    situacao_funcionamento SMALLINT,

    -- Matriculas (campos QT_MAT_* do microdado)
    qt_mat_bas INTEGER,
    qt_mat_inf INTEGER,
    qt_mat_fund INTEGER,
    qt_mat_fund_ai INTEGER,
    qt_mat_fund_af INTEGER,
    qt_mat_med INTEGER,
    qt_mat_eja INTEGER,
    qt_mat_prof INTEGER,

    -- Equipe (campos QT_DOC_*)
    qt_doc_bas INTEGER,
    qt_doc_fund INTEGER,
    qt_doc_med INTEGER,

    -- Tecnologia (IN_INTERNET_* e QT_* de equipamentos)
    in_internet BOOLEAN,
    in_internet_alunos BOOLEAN,
    in_internet_aprendizagem BOOLEAN,
    in_laboratorio_informatica BOOLEAN,
    qt_desktop_aluno INTEGER,
    qt_comp_portatil_aluno INTEGER,
    qt_tablet_aluno INTEGER,

    -- Infraestrutura (IN_*)
    in_biblioteca BOOLEAN,
    in_biblioteca_sala_leitura BOOLEAN,
    in_quadra_esportes BOOLEAN,
    in_laboratorio_ciencias BOOLEAN,
    in_alimentacao BOOLEAN,

    -- Metadata
    source_file TEXT,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Chave composta natural
    UNIQUE (inep_code, vintage_censo),
    -- Vintage deve estar em intervalo razoavel
    CONSTRAINT valid_vintage CHECK (vintage_censo BETWEEN 2015 AND 2035)
);

-- Indices para as queries tipicas
CREATE INDEX IF NOT EXISTS idx_sc_yearly_inep
    ON school_censo_yearly(inep_code);

CREATE INDEX IF NOT EXISTS idx_sc_yearly_vintage
    ON school_censo_yearly(vintage_censo);

CREATE INDEX IF NOT EXISTS idx_sc_yearly_inep_vintage
    ON school_censo_yearly(inep_code, vintage_censo);

CREATE INDEX IF NOT EXISTS idx_sc_yearly_company
    ON school_censo_yearly(company_id)
    WHERE company_id IS NOT NULL;

-- Trigger de updated_at
DROP TRIGGER IF EXISTS update_school_censo_yearly_updated_at ON school_censo_yearly;
CREATE TRIGGER update_school_censo_yearly_updated_at
    BEFORE UPDATE ON school_censo_yearly
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comments (documentacao inline)
COMMENT ON TABLE school_censo_yearly IS
    'Serie historica individual por escola baseada nos microdados do Censo '
    'Escolar INEP. Um registro por (inep_code, vintage_censo). Permite '
    'analises de evolucao ao longo dos anos (matriculas, equipe, tech, infra).';

COMMENT ON COLUMN school_censo_yearly.vintage_censo IS
    'Ano do Censo Escolar (ex: 2020, 2021, 2022, 2023, 2024, 2025). '
    'Fonte: NU_ANO_CENSO dos microdados.';

COMMENT ON COLUMN school_censo_yearly.tp_dependencia IS
    'Codigo dependencia administrativa (1=Federal, 2=Estadual, 3=Municipal, 4=Privada).';

COMMENT ON COLUMN school_censo_yearly.qt_mat_bas IS
    'Total de matriculas na educacao basica no ano do Censo.';

-- =====================================================================
-- FIM MIGRATION 016
-- =====================================================================
-- Proximos passos:
--   1. Rodar scripts/historico/process_censo_year.py para 2020-2024
--   2. Rodar scripts/historico/seed_censo_2025_from_companies.py
--   3. Validar contagem: SELECT vintage_censo, COUNT(*) FROM school_censo_yearly
--      GROUP BY vintage_censo ORDER BY vintage_censo;
