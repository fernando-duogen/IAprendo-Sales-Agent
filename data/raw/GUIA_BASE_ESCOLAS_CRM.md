# Guia da Base de Dados: escolas_brasil_crm.csv

## Visão geral

Base consolidada a partir dos Microdados do Censo Escolar 2025 (INEP), otimizada para uso em CRM e agente de vendas. Contém **180.540 escolas ativas** em todo o Brasil, com **77 colunas** cruzando dados de 5 tabelas oficiais (Escola, Matrícula, Docente, Turma e Gestor).

**Fonte:** Censo Escolar da Educação Básica 2025 — Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira (INEP).

**Filtros aplicados:** Somente escolas com situação de funcionamento "Em atividade" (TP_SITUACAO_FUNCIONAMENTO = 1). Escolas paralisadas e extintas foram removidas.

**Encoding:** UTF-8 com BOM (utf-8-sig). Separador: vírgula.

---

## Estrutura das colunas

### BLOCO 1 — Identificação e Contato (colunas 1–13)

Dados para localizar, identificar e entrar em contato com a escola.

| # | Coluna | Tipo | Preenchimento | Descrição |
|---|--------|------|---------------|-----------|
| 1 | `CODIGO_INEP` | Inteiro | 100% | Código único de identificação da escola no INEP. É a chave primária da base. Cada escola tem um código exclusivo de 8 dígitos. Use este campo para cruzar com outras bases do governo ou para evitar duplicatas. |
| 2 | `NOME_ESCOLA` | Texto | 100% | Nome oficial da escola conforme cadastro no INEP. Está em caixa alta (maiúsculas). Pode conter siglas como EEEFM (Escola Estadual de Ensino Fundamental e Médio), EMEF, CEMEI, etc. |
| 3 | `CNPJ_ESCOLA` | Texto | 24% | CNPJ da escola, formatado (XX.XXX.XXX/XXXX-XX). Preenchido apenas para escolas **privadas**. Escolas públicas não possuem CNPJ próprio nesta base. |
| 4 | `CNPJ_MANTENEDORA` | Texto | 24% | CNPJ da entidade mantenedora (grupo educacional, associação, etc.). Também apenas para escolas privadas. Útil para identificar redes: escolas com o mesmo CNPJ_MANTENEDORA pertencem ao mesmo grupo. |
| 5 | `ENDERECO` | Texto | 100% | Endereço concatenado no formato "Rua, Número - Complemento". O número foi integrado à rua e dados duplicados foram removidos automaticamente. Quando não há número, aparece "S/N". |
| 6 | `BAIRRO` | Texto | 68% | Nome do bairro. Não preenchido para ~32% das escolas (principalmente rurais, indígenas e ribeirinhas, onde o conceito de bairro não se aplica). |
| 7 | `CEP` | Texto | 100% | CEP no formato XXXXX-XXX. |
| 8 | `MUNICIPIO` | Texto | 100% | Nome do município (com acentuação). São 5.298 municípios distintos na base. |
| 9 | `UF` | Texto | 100% | Sigla da unidade federativa (2 letras). 27 valores possíveis (26 estados + DF). |
| 10 | `REGIAO` | Texto | 100% | Nome da região geográfica. Valores: **Sudeste** (61.420 escolas), **Nordeste** (59.988), **Sul** (26.272), **Norte** (22.207), **Centro-Oeste** (10.653). |
| 11 | `TELEFONE` | Texto | 85% | Telefone no formato "(DDD) Número". Não possui hífen ou separação fixa. Pode ser fixo ou celular. 15% das escolas não possuem telefone cadastrado (especialmente rurais). |
| 12 | `LATITUDE` | Decimal | 81% | Coordenada geográfica (latitude). Valores negativos (hemisfério sul). Útil para cálculos de proximidade e geolocalização. |
| 13 | `LONGITUDE` | Decimal | 81% | Coordenada geográfica (longitude). Valores negativos (oeste de Greenwich). |

### BLOCO 2 — Classificação e Segmentação (colunas 14–21)

Campos categóricos para filtrar e segmentar escolas. São os filtros mais importantes para o agente de vendas.

| # | Coluna | Tipo | Preenchimento | Descrição |
|---|--------|------|---------------|-----------|
| 14 | `DEPENDENCIA` | Texto | 100% | Dependência administrativa. Indica quem mantém a escola. Valores possíveis e quantidades: **Municipal** (107.372 — 59%), **Privada** (42.454 — 24%), **Estadual** (29.998 — 17%), **Federal** (716 — 0,4%). Este é o filtro mais fundamental para segmentação: escolas privadas são tipicamente clientes diretos; públicas podem exigir licitação. |
| 15 | `CATEGORIA_PRIVADA` | Texto | 24% | Subcategoria das escolas privadas. Preenchido APENAS quando DEPENDENCIA = "Privada". Valores: **Particular** (31.232 — escolas com fins lucrativos, o maior mercado), **Filantrópica** (8.431), **Comunitária** (2.287), **Confessional** (504 — ligadas a igrejas). Vazio para escolas públicas. |
| 16 | `LOCALIZACAO` | Texto | 100% | Zona da escola. Valores: **Urbana** (129.777 — 72%) ou **Rural** (50.763 — 28%). |
| 17 | `LOCALIZACAO_DIFERENCIADA` | Texto | 100% | Indica se a escola está em área de localização diferenciada. Valores: **Não** (169.571 — maioria), **Área de assentamento** (4.519), **Terra indígena** (3.713), **Quilombola** (2.737). Escolas em localização diferenciada tendem a ter menor infraestrutura e demandas específicas. |
| 18 | `REGULAMENTACAO` | Texto | 100% | Status de regulamentação pelo Conselho de Educação. Valores: **Sim, pelo Conselho de Educação** (162.966), **Em tramitação** (13.708), **Não regulamentada** (3.866). Escolas não regulamentadas podem ter limitações para compra de certos produtos/serviços. |
| 19 | `PORTE_ESCOLA` | Texto | 100% | Classificação por volume total de matrículas. Valores (do menor para o maior): **Sem matrículas** (1.774), **Até 50 matrículas** (33.047), **51 a 200 matrículas** (69.619), **201 a 500 matrículas** (50.315), **501 a 1000 matrículas** (20.887), **Mais de 1000 matrículas** (4.898). Use este campo para qualificar leads rapidamente — escolas com mais de 200 matrículas representam o mercado mais interessante em volume. |
| 20 | `PERFIL_ENSINO` | Texto | 100% | Combinação de etapas de ensino que a escola efetivamente possui (baseado em matrículas, não apenas na oferta declarada). Exemplos comuns: "Infantil + Fundamental" (50.264 escolas), "Infantil" (45.019), "Fundamental" (27.943), "Fundamental + Médio" (6.722). Existem 31 combinações diferentes. Use para direcionar produtos específicos por etapa — por exemplo, um material de Ensino Médio só faz sentido para escolas cujo perfil inclui "Médio". |
| 21 | `NIVEL_TECNOLOGICO` | Texto | 100% | Classificação derivada do nível de infraestrutura tecnológica. Valores: **Alto** (83.928 — têm internet, banda larga, dispositivos para alunos, lab), **Médio** (80.123 — infraestrutura parcial), **Baixo** (16.489 — pouca ou nenhuma infraestrutura digital). Pontuação baseada em 6 critérios: internet, internet para alunos, banda larga, lab informática, existência de dispositivos, e mais de 20 dispositivos. |

### BLOCO 3 — Volume de Matrículas: Totais (colunas 22–28)

Números agregados de alunos por grande etapa de ensino. Use para dimensionar o tamanho da escola.

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 22 | `TOTAL_MATRICULAS` | Inteiro | Total geral de matrículas na educação básica. Soma de todas as etapas. É o principal indicador de tamanho. Média nacional: 255, mediana: 158, máximo: 41.946. |
| 23 | `MATRICULAS_INFANTIL` | Inteiro | Total de matrículas na Educação Infantil (creche + pré-escola). |
| 24 | `MATRICULAS_CRECHE` | Inteiro | Matrículas em creche (0 a 3 anos). |
| 25 | `MATRICULAS_PRE` | Inteiro | Matrículas em pré-escola (4 a 5 anos). |
| 26 | `MATRICULAS_FUNDAMENTAL` | Inteiro | Total de matrículas no Ensino Fundamental (anos iniciais + anos finais). |
| 27 | `MATRICULAS_FUND_AI` | Inteiro | Matrículas nos Anos Iniciais do Fundamental (1° ao 5° ano). É a soma de MAT_1_ANO a MAT_5_ANO. |
| 28 | `MATRICULAS_FUND_AF` | Inteiro | Matrículas nos Anos Finais do Fundamental (6° ao 9° ano). É a soma de MAT_6_ANO a MAT_9_ANO. |

### BLOCO 4 — Volume de Matrículas: Por Ano/Série (colunas 29–42)

Detalhamento ano a ano. Permite calcular o número exato de alunos para qualquer combinação de séries. Por exemplo, para saber quantos alunos do 6° ao 8° ano uma escola tem, some MAT_6_ANO + MAT_7_ANO + MAT_8_ANO.

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 29 | `MAT_1_ANO` | Inteiro | Matrículas no **1° ano** do Ensino Fundamental (anos iniciais). |
| 30 | `MAT_2_ANO` | Inteiro | Matrículas no **2° ano** do Ensino Fundamental (anos iniciais). |
| 31 | `MAT_3_ANO` | Inteiro | Matrículas no **3° ano** do Ensino Fundamental (anos iniciais). |
| 32 | `MAT_4_ANO` | Inteiro | Matrículas no **4° ano** do Ensino Fundamental (anos iniciais). |
| 33 | `MAT_5_ANO` | Inteiro | Matrículas no **5° ano** do Ensino Fundamental (anos iniciais). |
| 34 | `MAT_6_ANO` | Inteiro | Matrículas no **6° ano** do Ensino Fundamental (anos finais). |
| 35 | `MAT_7_ANO` | Inteiro | Matrículas no **7° ano** do Ensino Fundamental (anos finais). |
| 36 | `MAT_8_ANO` | Inteiro | Matrículas no **8° ano** do Ensino Fundamental (anos finais). |
| 37 | `MAT_9_ANO` | Inteiro | Matrículas no **9° ano** do Ensino Fundamental (anos finais). |
| 38 | `MATRICULAS_MEDIO` | Inteiro | Total geral de matrículas no Ensino Médio (todas as modalidades). |
| 39 | `MAT_MEDIO_1_ANO` | Inteiro | Matrículas no **1° ano** do Ensino Médio (soma propedêutico + normal/magistério + integrado técnico). |
| 40 | `MAT_MEDIO_2_ANO` | Inteiro | Matrículas no **2° ano** do Ensino Médio. |
| 41 | `MAT_MEDIO_3_ANO` | Inteiro | Matrículas no **3° ano** do Ensino Médio. |
| 42 | `MAT_MEDIO_4_ANO` | Inteiro | Matrículas no **4° ano** do Ensino Médio. Valor residual (apenas 769 matrículas no Brasil). Existe em cursos técnicos integrados de 4 anos. |

**Nota sobre cobertura:** A soma dos anos individuais cobre 100% das matrículas do Fundamental e ~92% do Médio. Os ~8% restantes do Médio correspondem a turmas de itinerário formativo avulso e turmas não seriadas que não são atribuídas a um ano específico.

### BLOCO 5 — Outras Modalidades e Indicadores (colunas 43–48)

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 43 | `MATRICULAS_EJA` | Inteiro | Matrículas na Educação de Jovens e Adultos. Público com perfil diferente (adultos que retomam os estudos). |
| 44 | `MATRICULAS_PROFISSIONAL` | Inteiro | Matrículas em cursos profissionalizantes/técnicos. Indica escolas com foco vocacional. |
| 45 | `MATRICULAS_ED_ESPECIAL` | Inteiro | Matrículas de alunos com necessidades especiais (inclusão ou classes exclusivas). |
| 46 | `MATRICULAS_INTEGRAL` | Inteiro | Matrículas em regime de tempo integral. Alunos que permanecem o dia todo na escola. |
| 47 | `ALUNOS_POR_DOCENTE` | Decimal | Razão TOTAL_MATRICULAS / TOTAL_DOCENTES. Média nacional: 15,0. Indica a "densidade" da escola. Valores altos (>20) podem sinalizar escolas sobrecarregadas, que podem precisar de mais recursos de suporte. Valores baixos (<10) são comuns em escolas rurais pequenas ou escolas especializadas. Zero quando não há docentes cadastrados. |
| 48 | `PERC_INTEGRAL` | Decimal | Percentual de matrículas em tempo integral sobre o total (0 a 100). Média: 28%. Escolas com alto percentual de integral têm os alunos por mais tempo — relevante para produtos que dependem de permanência prolongada (alimentação, material complementar, atividades extracurriculares). |

### BLOCO 6 — Equipe (colunas 49–54)

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 49 | `TOTAL_TURMAS` | Inteiro | Número total de turmas na escola. Útil para dimensionar volume de material didático ou licenças por turma. |
| 50 | `TOTAL_DOCENTES` | Inteiro | Número total de docentes (professores). Média: 17, máximo: 337. Relevante para produtos voltados a professores (formação, plataformas pedagógicas). |
| 51 | `TOTAL_GESTORES` | Inteiro | Número de gestores (diretores e vice-diretores). Valores: 1 (172.173 escolas), 2 (6.633) ou 3 (1.734). Indica o nível de gestão — escolas com 2+ gestores tendem a ser maiores e mais organizadas. |
| 52 | `QT_ADMINISTRATIVOS` | Inteiro | Funcionários administrativos. |
| 53 | `QT_COORDENADORES` | Inteiro | Coordenadores pedagógicos. Escolas com coordenadores são mais propensas a adotar novos projetos pedagógicos. |
| 54 | `QT_SERVICOS_GERAIS` | Inteiro | Funcionários de serviços gerais. Indicador indireto de infraestrutura física. |

### BLOCO 7 — Etapas Oferecidas (colunas 55–64)

Flags (Sim/Não) indicando quais etapas e modalidades a escola declara oferecer. Diferente do BLOCO 3 que mostra matrículas efetivas — aqui é a oferta declarada ao INEP.

| # | Coluna | Valores | Descrição |
|---|--------|---------|-----------|
| 55 | `OFERECE_CRECHE` | Sim (78.186) / Não | A escola oferece creche (0-3 anos). |
| 56 | `OFERECE_PRE_ESCOLA` | Sim (98.010) / Não | Oferece pré-escola (4-5 anos). |
| 57 | `OFERECE_FUND_ANOS_INICIAIS` | Sim (99.682) / Não | Oferece Fundamental Anos Iniciais (1°-5°). |
| 58 | `OFERECE_FUND_ANOS_FINAIS` | Sim (61.016) / Não | Oferece Fundamental Anos Finais (6°-9°). |
| 59 | `OFERECE_ENSINO_MEDIO` | Sim (26.822) / Não | Oferece Ensino Médio regular. |
| 60 | `OFERECE_MEDIO_INTEGRADO` | Sim (7.791) / Não | Oferece Ensino Médio integrado ao técnico. |
| 61 | `OFERECE_EJA` | Sim (29.696) / Não | Oferece Educação de Jovens e Adultos. |
| 62 | `OFERECE_PROFISSIONALIZANTE` | Sim (16.765) / Não | Oferece cursos profissionalizantes/técnicos. |
| 63 | `OFERECE_EDUCACAO_ESPECIAL` | Sim (3.854) / Não | Oferece educação especial exclusiva (APAEs, etc.). |
| 64 | `MEDIACAO_EAD` | Sim (1.449) / Não | Oferece modalidade EAD (ensino a distância). |

### BLOCO 8 — Tecnologia (colunas 65–72)

Infraestrutura tecnológica da escola. Essencial para qualificar oportunidades em EdTech.

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 65 | `TEM_INTERNET` | Sim/Não | A escola possui conexão à internet (qualquer tipo). Sim em 95% das escolas. |
| 66 | `INTERNET_ALUNOS` | Sim/Não | A internet está disponível para uso dos alunos (não apenas administrativo). Sim em apenas 43%. Grande gap em relação ao TEM_INTERNET — muitas escolas têm internet mas não oferecem aos alunos. |
| 67 | `INTERNET_APRENDIZAGEM` | Sim/Não | A internet é utilizada no processo de aprendizagem. Sim em 73%. |
| 68 | `BANDA_LARGA` | Sim/Não | A escola possui banda larga. Sim em 83%. |
| 69 | `LAB_INFORMATICA` | Sim/Não | Possui laboratório de informática. Sim em apenas 29%. |
| 70 | `QT_DESKTOP_ALUNO` | Inteiro | Quantidade de computadores de mesa disponíveis para alunos. Zero quando não há. |
| 71 | `QT_NOTEBOOK_ALUNO` | Inteiro | Quantidade de notebooks/chromebooks disponíveis para alunos. |
| 72 | `QT_TABLET_ALUNO` | Inteiro | Quantidade de tablets disponíveis para alunos. |

### BLOCO 9 — Infraestrutura Complementar (colunas 73–77)

| # | Coluna | Tipo | Descrição |
|---|--------|------|-----------|
| 73 | `TEM_ALIMENTACAO` | Sim/Não | A escola oferece alimentação escolar. Sim em 84%. Praticamente todas as públicas oferecem; nem todas as privadas. |
| 74 | `TEM_BIBLIOTECA` | Sim/Não | Possui biblioteca ou sala de leitura. Sim em 37%. |
| 75 | `TEM_QUADRA_ESPORTES` | Sim/Não | Possui quadra de esportes (coberta ou descoberta). Sim em 40%. |
| 76 | `TEM_LAB_CIENCIAS` | Sim/Não | Possui laboratório de ciências. Sim em apenas 14%. |
| 77 | `ACESSIBILIDADE_INEXISTENTE` | Sim/Não | A escola **não possui** nenhum recurso de acessibilidade (rampas, corrimão, piso tátil, etc.). **Sim = escola SEM acessibilidade** (38.790 escolas = 21%). Atenção: a lógica é invertida — "Sim" aqui é negativo. |

---

## Dicas de uso para o agente de vendas

### Filtros rápidos de qualificação

Para encontrar rapidamente os melhores leads, combine estes campos:

- **Escolas privadas de porte médio-grande:** `DEPENDENCIA = "Privada"` e `PORTE_ESCOLA` em ["201 a 500 matrículas", "501 a 1000 matrículas", "Mais de 1000 matrículas"]
- **Escolas públicas estaduais com ensino médio:** `DEPENDENCIA = "Estadual"` e `OFERECE_ENSINO_MEDIO = "Sim"`
- **Escolas urbanas com infraestrutura digital precária:** `LOCALIZACAO = "Urbana"` e `NIVEL_TECNOLOGICO = "Baixo"` — bom mercado para soluções de infraestrutura
- **Escolas com alto % de integral:** `PERC_INTEGRAL > 50` — escolas com alunos o dia todo, que consomem mais recursos

### Calculando alunos para séries específicas

Para obter o total de alunos de uma faixa de anos, basta somar as colunas correspondentes. Exemplos:

- Alunos do ciclo de alfabetização (1°-3°): `MAT_1_ANO + MAT_2_ANO + MAT_3_ANO`
- Alunos do 6° ao 9° ano: `MAT_6_ANO + MAT_7_ANO + MAT_8_ANO + MAT_9_ANO`
- Alunos do Ensino Médio completo: `MAT_MEDIO_1_ANO + MAT_MEDIO_2_ANO + MAT_MEDIO_3_ANO`

### Identificando redes de escolas (grupos educacionais)

Escolas privadas que pertencem ao mesmo grupo educacional compartilham o mesmo `CNPJ_MANTENEDORA`. Para identificar redes: agrupe por CNPJ_MANTENEDORA e conte quantas escolas cada mantenedora possui. Redes grandes são leads de alto valor pois uma venda pode escalar para múltiplas unidades.

### Campos que podem ser vazios (e o motivo)

- `CNPJ_ESCOLA` e `CNPJ_MANTENEDORA`: vazios para escolas públicas (76% da base)
- `CATEGORIA_PRIVADA`: vazio para escolas públicas
- `BAIRRO`: vazio para ~32% das escolas (rurais, indígenas, ribeirinhas)
- `TELEFONE`: vazio para ~15% (rurais sem linha cadastrada)
- `LATITUDE` e `LONGITUDE`: vazios para ~19% (escolas sem georreferenciamento no INEP)

### Relação entre PERFIL_ENSINO e flags OFERECE_*

O campo `PERFIL_ENSINO` é baseado em **matrículas efetivas** (se a escola tem alunos de fato naquela etapa), enquanto os campos `OFERECE_*` são baseados na **oferta declarada**. Pode haver diferenças: uma escola pode declarar que oferece EJA mas ter 0 matrículas naquele momento. Use `PERFIL_ENSINO` para segmentação por realidade atual e `OFERECE_*` para potencial de oferta.
