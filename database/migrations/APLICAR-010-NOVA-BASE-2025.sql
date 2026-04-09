-- Migration 010: Expandir tabela companies para nova base MEC 2025 (77 colunas)
-- Adiciona ~40 colunas SEM apagar dados existentes.
-- As 88 escolas atuais mantêm contatos, emails, memórias e scores.
--
-- APLICAR: Execute no Supabase SQL Editor (copie TUDO de uma vez)
-- ===================================================================

-- Bloco 1: Classificação expandida
ALTER TABLE companies ADD COLUMN IF NOT EXISTS regiao VARCHAR(20);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS bairro VARCHAR(200);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS cep VARCHAR(10);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS cnpj_escola VARCHAR(20);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS cnpj_mantenedora VARCHAR(20);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS categoria_privada VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS localizacao VARCHAR(10);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS regulamentacao VARCHAR(50);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS perfil_ensino VARCHAR(200);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS nivel_tecnologico VARCHAR(10);

-- Bloco 2: Matrículas totais
ALTER TABLE companies ADD COLUMN IF NOT EXISTS total_matriculas INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_infantil INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_fundamental INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_fund_ai INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_fund_af INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_medio INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_integral INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS perc_integral DECIMAL(5,2);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS matriculas_eja INTEGER DEFAULT 0;

-- Bloco 3: Matrículas por ano (Fundamental)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_1_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_2_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_3_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_4_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_5_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_6_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_7_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_8_ano INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_9_ano INTEGER DEFAULT 0;

-- Bloco 4: Matrículas por ano (Médio)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_medio_1 INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_medio_2 INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS mat_medio_3 INTEGER DEFAULT 0;

-- Bloco 5: Equipe
ALTER TABLE companies ADD COLUMN IF NOT EXISTS total_docentes INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS total_gestores INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qt_coordenadores INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qt_administrativos INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS total_turmas INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS alunos_por_docente DECIMAL(5,1);

-- Bloco 6: Tecnologia
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tem_internet BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS internet_alunos BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS internet_aprendizagem BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS banda_larga BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS lab_informatica BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qt_desktop_aluno INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qt_notebook_aluno INTEGER DEFAULT 0;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS qt_tablet_aluno INTEGER DEFAULT 0;

-- Bloco 7: Infraestrutura
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tem_alimentacao BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tem_biblioteca BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tem_quadra BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS tem_lab_ciencias BOOLEAN;

-- Bloco 8: Etapas oferecidas (flags)
ALTER TABLE companies ADD COLUMN IF NOT EXISTS oferece_fund_af BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS oferece_medio BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS oferece_eja BOOLEAN;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS oferece_profissionalizante BOOLEAN;

-- Índices para as novas colunas mais usadas em filtros
CREATE INDEX IF NOT EXISTS idx_companies_nivel_tech ON companies(nivel_tecnologico);
CREATE INDEX IF NOT EXISTS idx_companies_total_mat ON companies(total_matriculas DESC);
CREATE INDEX IF NOT EXISTS idx_companies_regiao ON companies(regiao);
CREATE INDEX IF NOT EXISTS idx_companies_localizacao ON companies(localizacao);
CREATE INDEX IF NOT EXISTS idx_companies_mantenedora ON companies(cnpj_mantenedora);

-- ===================================================================
-- APÓS APLICAR: execute o script update_existing_schools.py para
-- preencher as colunas novas nas 88 escolas existentes.
-- ===================================================================
