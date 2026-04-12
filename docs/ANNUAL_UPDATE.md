# Runbook de Atualização Anual — ENEM + Censo Escolar

> **Público-alvo:** quem for rodar essa atualização no ano seguinte (você mesmo, outro operador, ou um Claude que venha depois). Este documento descreve passo a passo o que fazer quando a INEP publicar novos microdados.
>
> **Última atualização:** 2026-04-12 (cobertura atual: Censo 2020-2025, ENEM 2024)

---

## 🗺️ Como construímos a base (Abril 2026)

A base atual foi montada em **8 etapas** ao longo de 2 sessões de trabalho. Esta seção documenta o caminho completo para que, no futuro, você saiba exatamente de onde cada dado veio.

### Etapa 1 — Catálogo de Escolas INEP (base inicial, ~185k escolas)

**O que fizemos:** Baixamos o Catálogo oficial de Escolas do INEP, que lista TODAS as escolas ativas do Brasil com dados cadastrais básicos (nome, endereço, INEP, telefone, dependência, porte, etapas de ensino).

**Arquivo gerado:** `data/raw/escolas_brasil.csv` (82 MB, ~185k linhas)
**Script usado:** `database/migrations/import_schools.py` — aplica 4 filtros ICP (funcionamento, localização, nível de ensino, tipo) e importa para `companies`
**Resultado:** ~1.500 escolas para Porto Alegre/RS importadas no CRM com `status='raw'`

### Etapa 2 — Censo Escolar 2025 (dados ricos, ~180k escolas)

**O que fizemos:** Baixamos os microdados do Censo Escolar 2025 da INEP. Esse Censo veio em formato **multi-tabela** (6 arquivos CSV separados: Escola, Matrícula, Docente, Turma, Gestor, Curso Técnico). A Etapa 1 tinha só dados cadastrais; o Censo trouxe dados ricos: matrículas por etapa, número de docentes, tecnologia (internet, labs, devices), infraestrutura (biblioteca, quadra).

**Arquivos fonte:** `data/raw/Censo_2025/dados/Tabela_Escola_2025.csv` + 5 outros (total ~445 MB)
**Pipeline:** Cowork session processou os 6 CSVs, fez JOIN por CO_ENTIDADE, e gerou `data/raw/escolas_brasil_crm.csv` (77 MB, 180.5k escolas, 77 colunas)
**Guia de colunas:** `docs/GUIA_BASE_ESCOLAS_CRM.md` — documenta cada um dos 77 campos em 9 blocos
**Script de update:** `database/migrations/update_existing_schools.py` — atualiza `companies` com os dados ricos do Censo
**Migration aplicada:** `APLICAR-010-NOVA-BASE-2025.sql` (adiciona 219+ colunas em companies)

### Etapa 3 — Merge Censo + Catálogo (base unificada, ~184.8k escolas)

**O que fizemos:** Nem todas as escolas estavam nas duas bases. ~4.200 escolas ativas existiam no Catálogo INEP mas NÃO no Censo 2025 (escolas muito novas ou que não reportaram o censo). Fizemos um merge inteligente para ter a base mais completa possível.

**Script:** `database/migrations/merge_catalogo_inep.py`
**Entrada:** `escolas_brasil_crm.csv` (180.5k do Censo) + `escolas_brasil.csv` (185k do Catálogo)
**Saída:** `data/raw/escolas_brasil_merged.csv` (80 MB, 184.8k escolas)
**Lógica:** Censo como base primária (dados mais ricos) + escolas exclusivas do Catálogo adicionadas com parsing de endereço
**Campo de rastreio:** `fonte_dados` = 'censo_2025' ou 'catalogo_inep' (via migration `APLICAR-011-FONTE-DADOS.sql`)

### Etapa 4 — ENEM 2024 (analytics, peer groups, socioeconomia)

**O que fizemos:** Processamos os microdados do ENEM 2024 da INEP para calcular ~297 colunas analíticas por escola: médias por área (MT, CN, CH, LC, Redação), rankings, peer groups (comparação com escolas da mesma cidade × mesma dependência), trajetórias 5 anos do peer group, contexto socioeconômico municipal, e perfil dos inscritos.

**Pipeline externo (Cowork):**
- Local: `C:\Users\Fernando Nienaber\Downloads\microdados_enem_2024\pipeline\`
- Scripts: `01_aggregate_resultados.py` → `02_aggregate_participantes.py` → `01b_aggregate_legacy.py` → `04_build_trends.py` → `03_merge_and_enrich.py`
- Output: `outputs/escolas_brasil_enriquecido.csv` (177 MB, 185k escolas, 297 colunas)

**Análise do CSV:** `scripts/inspect_enem_csv.py` — analisou a estrutura e gerou relatório de tipos
**Relatório gerado:** `scripts/enem_schema_report.json` (metadados de 297 colunas: nome, tipo SQL, grupo)
**Migration gerada:** `scripts/generate_migration_015.py` → `APLICAR-015-SCHOOL-ANALYTICS.sql` (DDL com 297+ colunas, índices parciais, coluna GENERATED para média sem redação)
**Script de import:** `database/migrations/import_school_analytics.py` — lê o JSON report + CSV, faz UPSERT em `school_analytics` por inep_code
**Resultado:** `school_analytics` com 185k escolas, 4 grupos de métricas (98 enem_*, 63 peer_*, 30 socio_*, 28 pnt_*)

### Etapa 5 — Série histórica Censo 2020-2024 (evolução individual)

**O que fizemos:** Para permitir análises do tipo "como a escola evoluiu nos últimos 5 anos?", processamos os microdados do Censo Escolar de 2020 a 2024 (cada um com ~220k escolas). Esses censos vieram em formato **monolítico** (1 CSV gigante por ano).

**Migration:** `APLICAR-016-SCHOOL-CENSO-YEARLY.sql` — tabela `school_censo_yearly` com chave composta (inep_code, vintage_censo)
**Script:** `scripts/historico/process_censo_year.py` — processa 1 ano por vez, detecta encoding e schema dinamicamente, UPSERT por (inep, vintage)
**Execução:** `python scripts/historico/process_censo_year.py 2020 2021 2022 2023 2024` (rodou ano a ano, ~3-8 min cada)
**Retry/backoff:** Adicionado após o primeiro run travar por rate limit do Supabase (bug diagnosticado e corrigido)
**Resultado:** ~1.1M linhas (220k escolas × 5 vintages), 39 colunas por registro

### Etapa 6 — Seed do Censo 2025 a partir de companies

**O que fizemos:** O Censo 2025 já estava em `companies` (via Etapa 2), mas NÃO em `school_censo_yearly` (que é a tabela de série). Criamos um script que copia os campos relevantes de `companies` → `school_censo_yearly` com `vintage_censo=2025`.

**Script:** `scripts/historico/seed_censo_2025_from_companies.py`
**Resultado:** 6 vintages na série (2020-2025), completando a base histórica

### Etapa 7 — Infra para série ENEM futura

**O que fizemos:** Criamos a tabela `school_enem_yearly` para armazenar vintages ENEM à medida que saem novos anos. Hoje só tem 2024 (primeiro ano com CO_ESCOLA nos microdados públicos). Em 2020-2023, o INEP anonimizou os microdados removendo CO_ESCOLA, impossibilitando série individual.

**Migration:** `APLICAR-017-SCHOOL-ENEM-YEARLY.sql`
**Script de seed:** `scripts/historico/seed_enem_2024_from_analytics.py` — copia snapshot de `school_analytics` → `school_enem_yearly` com `vintage_enem=2024`

### Etapa 8 — Limpeza e métricas derivadas

**O que fizemos:**
- **Mojibake:** O CSV fonte ENEM chegou com ~10.500 nomes de município corrompidos (caractere `�` no lugar de acentos). Corrigido via script que propagou nomes limpos de `school_censo_yearly` → `school_analytics`.
  - Script: `scripts/fix_mojibake_school_analytics.py`
  - Migration: `APLICAR-018-FIX-MOJIBAKE.sql` (documenta o SQL equivalente)
- **Métricas derivadas:** Handler `analisar_trajetoria_escola` expandido para computar razão aluno/professor, tech_score, infra_score, composição matricular por ano — tudo server-side (Python), com detecção automática de insights/correlações.
- **Nomes de escolas:** Helper `_resolve_school_names` que resolve nomes via cascata `companies` → `school_censo_yearly`, eliminando o fallback "Escola INEP XXXXX" nos rankings.

---

## 📦 Mapa de artefatos

### Dados fonte (não modificar — são a verdade)

| Arquivo | Tamanho | Origem | O que contém |
|---|---|---|---|
| `data/raw/escolas_brasil.csv` | 82 MB | Catálogo INEP | 185k escolas com dados cadastrais básicos |
| `data/raw/Censo_2025/dados/*.csv` (6 arquivos) | 445 MB | INEP Censo 2025 | Escola + Matrícula + Docente + Turma + Gestor + Curso Técnico |
| `data/raw/escolas_brasil_crm.csv` | 77 MB | Pipeline Cowork | Censo 2025 convertido pra schema CRM (77 colunas) |
| `data/raw/escolas_brasil_merged.csv` | 80 MB | merge_catalogo_inep.py | Censo + Catálogo unificados (184.8k escolas) |
| `data/raw/escolas_brasil_enriquecido.csv` | 177 MB | Pipeline Cowork (ENEM) | 185k escolas × 297 colunas (enem + peer + socio + pnt) |

### Scripts de processamento (rodar na atualização)

| Script | Quando usar | Input | Output |
|---|---|---|---|
| `database/migrations/import_schools.py` | Setup inicial, novo Catálogo | escolas_brasil.csv | companies (filtrado) |
| `database/migrations/update_existing_schools.py` | Novo Censo processado | escolas_brasil_merged.csv | companies (atualizado) |
| `database/migrations/merge_catalogo_inep.py` | Novo Censo + Catálogo | _crm.csv + escolas_brasil.csv | _merged.csv |
| `database/migrations/import_school_analytics.py` | Novo ENEM processado | _enriquecido.csv + schema_report.json | school_analytics |
| `scripts/historico/process_censo_year.py` | Novo Censo (monolítico) | microdados_ed_basica_YYYY.csv | school_censo_yearly |
| `scripts/historico/seed_censo_2025_from_companies.py` | Novo Censo (multi-tabela) | companies | school_censo_yearly |
| `scripts/historico/seed_enem_2024_from_analytics.py` | **Antes** de importar novo ENEM | school_analytics | school_enem_yearly |
| `scripts/inspect_enem_csv.py` | Novo CSV ENEM com schema diferente | CSV ENEM | enem_schema_report.json |
| `scripts/generate_migration_015.py` | Novo schema ENEM | enem_schema_report.json | SQL DDL |
| `scripts/fix_mojibake_school_analytics.py` | Se CSV fonte tiver encoding ruim | school_censo_yearly + school_analytics | school_analytics (corrigido) |

### Migrations SQL (aplicar via Supabase SQL Editor)

| Migration | Tabela criada/alterada | Quando aplicar |
|---|---|---|
| `APLICAR-010-NOVA-BASE-2025.sql` | companies (219+ colunas) | Primeiro Censo |
| `APLICAR-011-FONTE-DADOS.sql` | companies (+fonte_dados) | Junto com 010 |
| `APLICAR-015-SCHOOL-ANALYTICS.sql` | school_analytics | Primeiro ENEM |
| `APLICAR-016-SCHOOL-CENSO-YEARLY.sql` | school_censo_yearly | Primeiro Censo histórico |
| `APLICAR-017-SCHOOL-ENEM-YEARLY.sql` | school_enem_yearly | Primeira série ENEM |
| `APLICAR-018-FIX-MOJIBAKE.sql` | school_analytics (fix) | Se mojibake detectado |

### Documentação

| Arquivo | Conteúdo |
|---|---|
| `docs/ANNUAL_UPDATE.md` | **Este documento** — runbook completo + narrativa |
| `docs/GUIA_BASE_ESCOLAS_CRM.md` | Dicionário de dados do CSV CRM (77 campos em 9 blocos) |
| `docs/ARCHITECTURE.md` | Arquitetura do sistema (5 camadas, fluxo de dados) |
| `docs/IMPLEMENTATION.md` | Especificações técnicas (tabelas, agentes, dashboard) |
| `database/migrations/readme.md` | Guia das migrations 001-002 + validação |
| `scripts/enem_schema_report.json` | Metadados das 297 colunas do CSV ENEM |
| `scripts/enem_schema_report.txt` | Versão legível do relatório de schema |

### Pipeline externo (Cowork — gera o CSV enriquecido)

| Local | Script | Função |
|---|---|---|
| `C:\...\microdados_enem_2024\pipeline\` | `01_aggregate_resultados.py` | Agrega notas por escola (parquet) |
| | `02_aggregate_participantes.py` | Agrega socio por município |
| | `01b_aggregate_legacy.py` | Agrega anos anteriores (pra séries) |
| | `04_build_trends.py` | Computa trends 5 anos (peer trajetória) |
| | `03_merge_and_enrich.py` | Merge final → escolas_brasil_enriquecido.csv |

---

## Visão geral — o que é atualização anual

Este sistema usa 4 fontes da INEP que atualizam em ciclos:

| Fonte | Frequência | Meses típicos de publicação | Onde cai no banco |
|---|---|---|---|
| **Censo Escolar** | Anual | Março-Maio do ano seguinte | `school_censo_yearly` (série) + `companies` (snapshot atual) |
| **Microdados ENEM** | Anual | Abril-Junho do ano seguinte | `school_analytics` (snapshot) + `school_enem_yearly` (série, a partir de 2024) |
| **Catálogo de Escolas INEP** | Contínuo | Atualizado ao longo do ano | `companies` (complementa Censo) |
| **IDEB / SAEB** | Bianual | 2 anos após a aplicação | Ainda não integrado — candidato a fase 3 |

Cada fonte tem seu próprio pipeline e seu próprio runbook abaixo.

---

## Quando você souber que há dados novos

**Você só precisa agir quando a INEP anunciar publicação.** Acompanhe:

- Site oficial INEP: https://www.gov.br/inep/pt-br
- Portal de microdados: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados
- Releases de Censo Escolar: https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/censo-escolar
- Releases de ENEM: https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem

Dica: os microdados ENEM costumam sair **6-8 meses** depois da aplicação (ex: ENEM 2024 saiu em 2025). O Censo Escolar sai **3-5 meses** depois do encerramento do ano letivo (ex: Censo 2025 saiu em 2026).

---

## 📚 Cenário 1: Saiu um Censo Escolar novo (ex: Censo 2026)

**Tempo estimado:** 30-60 minutos de mãos no teclado + 10-20 minutos de processamento.

### Passo 1 — Baixar os microdados

1. Vá na página de microdados do Censo Escolar do INEP
2. Baixe o ZIP do ano novo (ex: `microdados_censo_escolar_2026.zip`, ~2 GB)
3. Extraia para: `C:\Users\Fernando Nienaber\Downloads\microdados_censo_escolar_2025\microdados_censo_escolar_2026\`
   (ou o que for o caminho equivalente no seu setup — importante manter a mesma estrutura `microdados_censo_escolar_<ano>/dados/`)

### Passo 2 — Identificar o formato do ano novo

A INEP pode mudar o formato entre anos. Teste qual dos dois é:

**Formato A — monolítico (como 2020-2024):**
```
microdados_censo_escolar_2026/dados/microdados_ed_basica_2026.csv   (arquivo único gigante)
```

**Formato B — multi-tabela (como 2025):**
```
microdados_censo_escolar_2026/dados/Tabela_Escola_2026.csv
microdados_censo_escolar_2026/dados/Tabela_Matricula_2026.csv
microdados_censo_escolar_2026/dados/Tabela_Docente_2026.csv
...
```

### Passo 3 — Processar o Censo para `school_censo_yearly`

**Se for formato A (monolítico):**

```bash
cd caminho/para/agente-de-vendas

# 1. Testar com sample pequeno e dry-run (não grava)
venv/Scripts/python.exe scripts/historico/process_censo_year.py --sample 1000 --dry-run 2026

# 2. Se passar sem erro: rodar full
venv/Scripts/python.exe scripts/historico/process_censo_year.py 2026
```

**Se for formato B (multi-tabela), como o 2025:**

Formato B não é coberto pelo `process_censo_year.py` atual. Use uma das 2 alternativas:

- **Alternativa 1 — usar o pipeline completo do Cowork** (se tiver a nova versão): extrai os microdados, roda os scripts 01-04 do pipeline para gerar um novo `escolas_brasil_enriquecido.csv`, roda `update_existing_schools.py` para popular `companies`, e então roda `seed_censo_2025_from_companies.py` (adaptado para o ano novo) para popular a série.

- **Alternativa 2 — estender `process_censo_year.py` com suporte multi-tabela**: fazer JOIN em Python entre `Tabela_Escola_2026`, `Tabela_Matricula_2026` e `Tabela_Docente_2026` por `CO_ENTIDADE` antes de chamar o mesmo fluxo de conversão.

Se cair nessa situação, recomendo perguntar a um Claude (nesta sessão ou outra) para adaptar o script, porque o schema muda de ano em ano e o acompanhamento precisa ser feito caso a caso. Palavras-chave que funcionam bem para contextualizar: *"estender process_censo_year.py para suportar o Censo YYYY que vem em multi-tabela, fazendo JOIN por CO_ENTIDADE entre Tabela_Escola, Tabela_Matricula e Tabela_Docente"*.

### Passo 4 — Atualizar o snapshot em `companies` (opcional mas recomendado)

Se você quer que o **IAlex também enxergue o ano novo como "estado atual"** (e não apenas como "mais um ponto da série"), rode também:

```bash
# 1. Gerar o merged (precisa do pipeline do Cowork ou fallback manual)
#    Depois de ter o escolas_brasil_<ano>_merged.csv no data/raw/:
venv/Scripts/python.exe database/migrations/update_existing_schools.py
```

Isso vai atualizar as colunas de Censo em `companies` (`matriculas_*`, `total_docentes`, `nivel_tecnologico`, etc.) com o ano novo. As colunas continuam sendo "atual" — a série histórica fica em `school_censo_yearly`.

### Passo 5 — Validar

```sql
-- Confirmar que o ano novo entrou
SELECT vintage_censo, COUNT(*) AS escolas
FROM school_censo_yearly
GROUP BY vintage_censo
ORDER BY vintage_censo;

-- Confirmar linked com companies (para o CRM de PoA, deve bater ~88)
SELECT vintage_censo, COUNT(*) AS linked
FROM school_censo_yearly
WHERE company_id IS NOT NULL
GROUP BY vintage_censo
ORDER BY vintage_censo;

-- Spot check de uma escola conhecida (ex: COLEGIO JOAO PAULO inep 43238203)
SELECT vintage_censo, name, qt_mat_bas, qt_mat_med, qt_doc_bas
FROM school_censo_yearly
WHERE inep_code = '43238203'
ORDER BY vintage_censo;
```

A última query deve mostrar uma linha por ano, evidenciando a evolução.

---

## 📊 Cenário 2: Saiu um ENEM novo (ex: ENEM 2025)

**Tempo estimado:** 45-90 minutos de mãos no teclado + 30-60 minutos de processamento.

### Passo 1 — Baixar os microdados

1. Vá em https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem
2. Baixe o ZIP do ano novo (ex: `microdados_enem_2025.zip`, ~5-10 GB)
3. Extraia para: `C:\Users\Fernando Nienaber\Downloads\microdados_enem_2024\microdados_enem_2025\`
   (mantém a mesma convenção do pipeline do Cowork)

### Passo 2 — Identificar os arquivos

A partir de 2024, a INEP separou em 2 arquivos principais:

```
microdados_enem_2025/DADOS/RESULTADOS_2025.csv      ← notas por inscrito COM CO_ESCOLA
microdados_enem_2025/DADOS/PARTICIPANTES_2025.csv   ← perfil socio sem CO_ESCOLA
```

**Atenção:** se o INEP voltar a publicar MICRODADOS unificado (como em 2020-2023) mas com `CO_ESCOLA` presente, o pipeline vai precisar ser adaptado. Neste momento o pipeline do Cowork assume o formato 2024 (dois arquivos separados).

### Passo 3 — Rodar o pipeline do Cowork

Os scripts originais estão em `C:\Users\Fernando Nienaber\Downloads\microdados_enem_2024\pipeline\`. Eles já são multi-ano:

```bash
cd "C:\Users\Fernando Nienaber\Downloads\microdados_enem_2024\pipeline"

# 1. Agregar notas por escola (gera parquet por ano)
python 01_aggregate_resultados.py 2025

# 2. Agregar participantes (socio) por município
python 02_aggregate_participantes.py 2025

# 3. Reconstruir trends com o ano novo incluído (atualiza peer_trajetoria e socio série)
python 01b_aggregate_legacy.py 2025    # gera enem_2025_por_mun_dep.parquet
python 04_build_trends.py              # recomputa tudo 2020-2025

# 4. Gerar CSV enriquecido final
python 03_merge_and_enrich.py          # gera outputs/escolas_brasil_enriquecido.csv
```

### Passo 4 — Atualizar `school_analytics` (snapshot do ENEM mais recente)

O pipeline vai **sobrescrever** a vintage "atual" em `school_analytics`. Isso é intencional — `school_analytics` sempre representa a foto mais recente.

```bash
cd caminho/para/agente-de-vendas

# Copiar o novo CSV enriquecido para data/raw/
cp "/c/Users/Fernando Nienaber/Downloads/microdados_enem_2024/outputs/escolas_brasil_enriquecido.csv" \
   "data/raw/escolas_brasil_enriquecido.csv"

# Re-importar (UPSERT)
venv/Scripts/python.exe database/migrations/import_school_analytics.py
```

### Passo 5 — Adicionar o ano ANTIGO à série em `school_enem_yearly`

**Antes** de sobrescrever a vintage atual, você quer preservar a que era "atual" até agora (ex: se antes era 2024 e agora vai virar 2025, você quer que 2024 vá para a série):

⚠️ **Sequência crítica:**

```bash
# Passo 5a: arquivar a vintage atual ANTES de sobrescrever
venv/Scripts/python.exe scripts/historico/seed_enem_2024_from_analytics.py
# (este script copia school_analytics atual → school_enem_yearly com vintage=2024)

# Passo 5b: SÓ DEPOIS rodar o import do novo (passo 4 acima)
# Assim o 2024 fica preservado na série e o 2025 vira o novo snapshot
```

**Se você esquecer e rodar o import antes:** o snapshot 2024 vai ter sido sobrescrito pelo 2025 em `school_analytics`, mas o `school_enem_yearly` ainda tem o 2024 (se você já o havia arquivado antes) — basta arquivar o 2025 novo a partir do analytics atual.

### Passo 6 — Adaptar `seed_enem_2024_from_analytics.py` para arquivar o ano novo

Abra `scripts/historico/seed_enem_2024_from_analytics.py`, procure por `2024` e substitua pelo ano que você acabou de importar. Renomeie o arquivo para deixar explícito (opcional).

Alternativa mais limpa: transformar o script para receber o ano como argumento. Isso é um upgrade de ~10 linhas que recomendo fazer quando estiver nessa situação.

### Passo 7 — Validar

```sql
-- Confirmar que a série está crescendo
SELECT vintage_enem, COUNT(*) AS escolas_com_dado,
       COUNT(*) FILTER (WHERE enem_amostra_confiavel) AS confiaveis
FROM school_enem_yearly
GROUP BY vintage_enem
ORDER BY vintage_enem;

-- Spot check de uma escola conhecida
SELECT vintage_enem, enem_media_geral, enem_media_mt, enem_rank_uf_dep
FROM school_enem_yearly
WHERE inep_code = '43238203'
ORDER BY vintage_enem;
```

---

## 🗂 Cenário 3: Quero atualizar o Catálogo de Escolas INEP

A INEP mantém um catálogo contínuo de escolas ativas. Essa fonte é usada para:
- Preencher escolas que **não participaram do Censo do ano** (e portanto não aparecem no microdado)
- Manter uma base nacional de ~185k escolas no `data/raw/escolas_brasil_merged.csv`

### Quando fazer

- Quando você notar que o IAlex não encontra escolas novas que aparentemente existem
- Pelo menos 1x por ano, junto com a atualização do Censo

### Como fazer

1. Baixar do site do INEP: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/indicadores-educacionais/catalogo-de-escolas
2. Rodar o pipeline `merge_catalogo_inep.py` (já existe no projeto):
```bash
venv/Scripts/python.exe database/migrations/merge_catalogo_inep.py
```
3. Re-rodar o `update_existing_schools.py` para refletir mudanças

Este cenário **não gera novos registros em `school_censo_yearly` nem em `school_enem_yearly`** — só mantém `companies` atualizada.

---

## 🚦 Quanto tempo cada coisa deveria levar (benchmarks)

| Operação | Duração típica | Notas |
|---|---|---|
| Baixar microdados Censo (zip 2GB) | 5-15 min | Depende da sua internet |
| Extrair zip Censo | 1-3 min | |
| Processar 1 ano Censo (~220k escolas) | 3-8 min | Gargalo: upsert no Supabase |
| Sample run + dry-run validação | 30-60 s | |
| Baixar microdados ENEM (zip 5-10GB) | 20-60 min | |
| Pipeline Cowork completo (1 ano ENEM) | 20-40 min | CPU-bound |
| `import_school_analytics.py` full | 5-10 min | 185k rows |
| `seed_enem_*_from_analytics.py` | 2-5 min | |

**Total para uma atualização anual completa (Censo + ENEM):** 1.5 a 3 horas, dominado por downloads.

---

## 🧪 Smoke tests pós-atualização

Sempre que rodar uma atualização, execute estes 4 checks no Supabase SQL Editor:

```sql
-- 1. Nenhuma tabela crítica perdeu dados (sanity check)
SELECT
  (SELECT COUNT(*) FROM companies) AS companies,
  (SELECT COUNT(*) FROM school_analytics) AS school_analytics,
  (SELECT COUNT(*) FROM school_censo_yearly) AS school_censo_yearly,
  (SELECT COUNT(*) FROM school_enem_yearly) AS school_enem_yearly;

-- 2. A série está crescendo (novo ano apareceu)
SELECT 'censo' AS tabela, vintage_censo AS vintage, COUNT(*) FROM school_censo_yearly GROUP BY vintage_censo
UNION ALL
SELECT 'enem', vintage_enem, COUNT(*) FROM school_enem_yearly GROUP BY vintage_enem
ORDER BY tabela, vintage;

-- 3. Escolas do CRM estão linkadas na série
SELECT
  (SELECT COUNT(*) FROM companies) AS total_cias,
  (SELECT COUNT(DISTINCT inep_code) FROM school_censo_yearly WHERE company_id IS NOT NULL) AS linked_censo,
  (SELECT COUNT(DISTINCT inep_code) FROM school_enem_yearly WHERE company_id IS NOT NULL) AS linked_enem;

-- 4. Spot-check: pegue uma escola qualquer do CRM e veja a série completa dela
SELECT c.name, sey.vintage_enem, sey.enem_media_geral, scy.vintage_censo, scy.qt_mat_bas
FROM companies c
LEFT JOIN school_enem_yearly sey ON sey.inep_code = c.inep_code
LEFT JOIN school_censo_yearly scy ON scy.inep_code = c.inep_code AND scy.vintage_censo = sey.vintage_enem
WHERE c.name ILIKE '%COLEGIO JOAO PAULO%'
ORDER BY sey.vintage_enem;
```

Se qualquer um destes quatro retornar resultado "estranho" (contagem zerada, ano faltando, série quebrada), investigue antes de considerar a atualização bem-sucedida.

---

## ❓ Perguntas frequentes

**P: O que faço se o INEP mudar o schema de um ano para outro?**
R: O pipeline `process_censo_year.py` usa **detecção dinâmica de schema** — ele só lê os campos que estão no header daquele arquivo e grava NULL para os que faltam. Na maioria dos casos, um campo novo não quebra nada. Mas se a INEP renomear um campo crítico (ex: `CO_ENTIDADE` → `CO_ESC`), o pipeline vai gravar linhas sem identificador e você vai ver isso no smoke test #1 acima (contagem zerada para o ano novo). A solução é adicionar uma entrada de mapeamento alternativo no `FIELD_MAP` do script.

**P: Posso pular um ano (ex: não rodar 2027 e só voltar em 2028)?**
R: Sim, sem problema. A série é por `(inep_code, vintage_censo)` — basta rodar o ano que você quer, o resto fica intacto.

**P: E se eu rodar o mesmo ano duas vezes?**
R: O `UPSERT` por `(inep_code, vintage_censo)` garante idempotência. Rodar duas vezes não duplica linhas — só atualiza `updated_at`.

**P: Preciso parar o IAlex durante a atualização?**
R: Não. Todas as operações são `UPSERT`, então leituras concorrentes funcionam normalmente. O pior cenário é o IAlex ver dados "intermediários" durante o upsert — mas como o import dura poucos minutos, isso é tolerável.

**P: Como faço se a INEP voltar a publicar série individual ENEM 2020-2023 no futuro (via LAI, por exemplo)?**
R: O `school_enem_yearly` aceita qualquer vintage de 2020 a 2035 (via `CHECK constraint`). Basta rodar um pipeline adaptado com os dados novos e inserir com a vintage correta. Nada precisa mudar no schema.

**P: Tem como automatizar via cron / scheduled task?**
R: Tem, mas a recomendação atual é **manual**. A INEP às vezes muda o schema, renomeia colunas, muda URL de download — automatizar completamente vira um sistema frágil que quebra no pior momento. Um runbook manual (este documento) é mais robusto a longo prazo.

---

## Histórico de atualizações

| Data | Operador | O que foi feito |
|---|---|---|
| 2026-04-11 | Fernando + Claude | Setup inicial: Censo 2020-2025 + ENEM 2024 |

**Quando fizer uma atualização, adicione uma linha aqui.** Isso ajuda você (ou outra pessoa) a saber o que foi rodado e quando, especialmente quando algo sair "estranho".

---

**Fim do runbook.** Se durante uma atualização você encontrar um caso não coberto aqui, adicione-o ao documento antes de finalizar o trabalho. Assim a próxima pessoa não precisa reaprender.
