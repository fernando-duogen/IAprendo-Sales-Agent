# 🧭 Blueprint v2 — "Dia de Venda"

> Redesign da plataforma IAprendo Sales Agent: de 11 paginas organizadas pelo
> fluxo tecnico dos dados para 8 espacos organizados pelo dia do vendedor.
>
> **Status**: PROPOSTA v1.2 — para validacao com o time antes de qualquer codigo.
> **Data**: 2026-06-10 (v1.1: feedback do dono + 3 auditorias adversariais —
> 12 jornadas de uso simulado + paridade v1->v2 · v1.2: impressoes do dono sobre
> os mockups — navegacao p/ ficha, filtros de completude, seletor de colunas,
> modelos visiveis)
> **Base**: tag `v1-prod` | **Branch de trabalho**: `redesign-v2`
> **Mockups navegaveis**: `docs/mockups/index.html` (abra no navegador)
> **Teste com o time**: `docs/mockups/TESTE_NOVATO.md` (roteiro de 15 min)

---

## 1. Por que mudar

A plataforma funciona ponta-a-ponta, mas e dificil de explicar a terceiros.
A auditoria completa (junho/2026) encontrou a causa-raiz:

**As paginas refletem o fluxo TECNICO dos dados (importar → qualificar →
enriquecer → gerar → aprovar → enviar), e nao o fluxo MENTAL do vendedor
("o que eu faco agora?").**

Sintomas medidos:
- **11 funcoes duplicadas** em 2-5 lugares (filtros UF/Cidade em 5 paginas; export
  em 3+; busca de escola de 4 formas; ENEM em 3 paginas; follow-ups em 3 lugares).
- **4 sistemas de prioridade concorrentes** sem explicacao (Score IA, Fit,
  P1/P2/P3, Urgencia) — o vendedor nao sabe qual usar.
- **~17 nomenclaturas inconsistentes** + jargao tecnico exposto ("raw", "INEP",
  "peer group", "deduced:nome.sobrenome").
- Paginas Escolas / Pipeline / Comunicacao com poluicao visual 4-5 (escala 1-5):
  Escolas tem detalhe com 7 sub-abas; Comunicacao tem 5 abas + 7 sub-tabs.
- Top confusao de novato: "onde comeco?" — a ordem das operacoes e implicita,
  documentada apenas no Manual.

## 2. Decisoes de direcao (tomadas pelo dono, 2026-06-10)

1. **Redesign visual profundo DENTRO do Streamlit** (sem migrar de stack).
2. Otimizar para **um vendedor novo operar sozinho no 1o dia** (zero jargao,
   fluxo guiado, estados vazios que ensinam).
3. **Agenda de atividades compartilhada + Metas na primeira onda** — a agenda e o
   coracao da nova Home; metas dao a visao do gestor.
4. **Blueprint validado antes de codar** (este documento + mockups).

## 3. Principios organizadores

> **A navegacao segue o dia do vendedor, nao o pipeline de dados.**
> Cada pagina responde a uma pergunta que o vendedor faria em voz alta.
> A primeira pagina responde: "o que eu faco agora?"

### 3.1 Conjunto padrao de filtros (v1.1 — feedback do dono)

Os filtros da v1 existem por motivo comercial e NAO somem na simplificacao.
TODA lista de escolas (Prospectar>Recomendadas, Prospectar>resultado da busca,
Escolas, e o export) oferece o MESMO conjunto padrao:

| Filtro | Detalhe |
|---|---|
| UF / Cidade | cascata (RPC ja existente) |
| Tipo de escola | Privada / Publica (+ dependencia: municipal/estadual/federal) |
| Niveis de ensino | Fundamental anos finais / Ensino Medio (checkboxes) |
| **Faixa de alunos** | **range numerico (ex: 400–1000)** — nao apenas porte fixo |
| Etapa | pill (Nova ... Cliente) — so em listas do CRM |
| Prioridade / Dono | so em listas do CRM |
| **Completude** (v1.2) | Contatos: Todos/Com/**Sem** · E-mail: Todos/Com/Sem · WhatsApp: Todos/Com/Sem · Telefone: Todos/Com/Sem — herdados dos "filtros de preparo" da v1, reescritos afirmativos ("escolas sem contatos" = Contatos: Sem) |

Implementacao: componente unico `school_filters()` (futuro `dashboard/filters.py`)
usado por todas as paginas — fim da reimplementacao por pagina (raiz dos bugs de
filtro da v1).

A aba **Pessoas** tem o proprio conjunto: filtro por escola (autocomplete —
"escolher uma escola e ver os contatos dela"), busca livre (nome/cargo/e-mail),
papel (decide/influencia/apoio) e com/sem e-mail. Cross-navegacao: em Pessoas, a
escola do contato linka a ficha; na ficha, a aba Pessoas ja mostra so os daquela
escola.

### 3.3 Seletor de colunas + export completo (v1.2 — ideia do dono)

As colunas default das tabelas sao otimizadas (enxutas), mas o usuario pode ver
**tudo o que temos** da escola: popover **"Colunas ▾"** ao lado do Exportar em
toda lista, com 4 presets — **★ Essencial** (default) · **Comercial** (etapa,
prioridade, potencial R$, dono, valores) · **Censo & ENEM** (matriculas por
nivel, docentes, tech, medias) · **Tudo** (~40 campos) — + checklist individual
com nomes amigaveis (labels.py). O **export respeita as colunas visiveis** e ha
a opcao "Exportar TUDO (todas as colunas)" — o export atual e curado
(utils/export_utils.py seleciona colunas "relevantes"); o modo completo e
extensao da F4. Preferencia de colunas lembrada por usuario.

### 3.4 Navegacao para a ficha da escola (v1.2 — regra explicita)

**O nome da escola e SEMPRE um link para a ficha** — na lista de Escolas, no
resultado da busca do Prospectar, nas Recomendadas, nos cards do kanban, na
busca global da Home e nas atividades da agenda. Na tabela de Escolas, alem do
nome-link (azul, sublinha no hover), ha a coluna de acao **"↗ Abrir"** como
primeira acao da linha. (Streamlit: selecao de linha + LinkColumn, na F4.)

### 3.2 Receita potencial — "Potencial R$/mes" (v1.1 — NOVO)

`receita_potencial = alunos_alvo x ticket_por_aluno` (ticket configuravel em
Ajustes; default unico, evolui para ticket por porte). Calculada ao vivo (sem
mudanca de banco). Aparece como **coluna em toda lista**, card na ficha da escola
e no export — transforma a faixa de alunos em leitura comercial direta (MRR
potencial do prospecto), do jeito que o time ja pensa.

---

## 4. Nova arquitetura: 8 espacos

```
🏠 Hoje          ← "O que eu faco agora?"          (Home nova: agenda + numeros do dia)
🤖 IAlex         ← "Pergunta pra IA"               (chat, mantido)
🔍 Prospectar    ← "Onde encontro escolas novas?"  (Recomendadas + Buscar + Mapa + Preparar lote)
🏫 Escolas       ← "Me conta tudo sobre esta escola" (ficha completa + pessoas)
✉️ Mensagens     ← "O que sai hoje? O que chegou?" (fila unica: aprovar/acompanhar/responder)
💼 Negocios      ← "Como estao minhas negociacoes?" (kanban comercial + reunioes + valores)
📊 Resultados    ← "Estou batendo a meta?"          (metas + funil + envios + explorador)
⚙️ Ajustes       ← admin apenas                     (automacoes, usuarios, diagnostico)
❓ Ajuda         ← manual reescrito + tour de 1o login
```

### 🏠 HOJE (Home reconstruida)

O vendedor abre de manha e sai com a lista do dia — sem decidir nada, so executar.

- **Minha Agenda** (nova tabela `activities`): atividades em *Atrasadas / Hoje /
  Amanha*, cada linha com ✓ Concluir, ⏰ Adiar, → Abrir escola (1 clique).
- **3 numeros do dia**: atividades de hoje · mensagens aguardando aprovacao ·
  respostas novas (cada um clicavel, leva direto a acao).
- **Lateral**: leads "🔴 Agir agora", reunioes das proximas 24h, anel de progresso
  da minha meta do mes.
- **Busca global acionavel**: resultado abre a escola (hoje a busca so informa).
- **Estado vazio (novato)**: checklist guiado de 4 passos com botoes que navegam
  ja filtrado. Gestor (admin) tem toggle "Minha agenda / Equipe".

### 🔍 PROSPECTAR (funde Importar + Descoberta + Ranking + Mapa + Pipeline-Execucao)

- **Recomendadas**: ex-Ranking P1/P2/P3, rebatizado "Potencial ★★★/★★/★".
  Com o **conjunto padrao de filtros** (§3.1) + coluna **Potencial R$/mes** +
  botao **Exportar**. Botao por linha: **"Trabalhar esta escola"** (importa +
  prepara + atribui dono; apos clicar, a escola aparece em Escolas com etapa
  "Pronta para contato" e toast com link).
- **Buscar no Brasil**: ex-Importar como wizard de 3 passos
  (*Escolher regiao → Revisar lista → Adicionar a minha carteira*). O passo 2 e
  uma TELA DE RESULTADO real: tabela com as escolas filtradas (Escola, Cidade,
  Niveis, Alunos, Potencial R$/mes) + Exportar — atende "me pediram uma planilha"
  mesmo sem importar nada.
- **Toggle Lista/Mapa**: o Mapa (PyDeck) vira visualizacao alternativa do mesmo
  filtro — deixa de ser pagina propria (2 modos de visual mantidos).
- **Preparar escolas** (v1.1 — decisao sobre o pipeline em etapas): UI default =
  **1 acao composta** com barra de progresso por etapa (avaliar → buscar contatos
  → gerar mensagens). As etapas sao restricao tecnica (rate limits/custos), nao
  decisao do vendedor — por isso somem da UI default. Etapas individuais +
  "Refazer mesmo se ja feito" ficam em "Opcoes avancadas" (power users). O motor
  (workflows/) nao muda. Feedback da etapa de contatos mostra o resultado
  concreto: "encontramos X pessoas, Y telefones, Z e-mails (W deduzidos ⚠️)".
- **Sinais de compra** (ex-Descoberta — orfao resolvido): secao propria dentro de
  Prospectar listando escolas com sinais detectados (noticias, premios, cliques).

### 🏫 ESCOLAS (funde Escolas + Contatos)

- Lista unica com colunas enxutas: Escola, Cidade, **Etapa** (pill), **Prioridade**,
  **Potencial R$/mes**, Dono, Ultimo contato. **Conjunto padrao de filtros** (§3.1)
  + **Exportar** 1-clique. "Redes" vira filtro/agrupamento (nao aba; override de
  nome da rede via dialog ✏️ no agrupamento).
- **Acao em lote (admin)**: selecionar N escolas → "Transferir para ▸ {vendedor}"
  (resolve ferias/redistribuicao; com registro de quem fez).
- **Aba "Pessoas"**: a pagina Contatos inteira entra aqui (decisores + export;
  e-mails deduzidos marcados ⚠️ "provavel, nao confirmado").
- **Ficha da escola — "Argumentos de venda"** (v1.1 — ENEM/Censo de forma
  inteligente): bloco na Visao Geral com os top 3-5 argumentos em linguagem de
  vendedor, gerados dos dados (ex: "Matematica 23 pts abaixo de escolas
  semelhantes — dor clara"; "matriculas +18% em 2 anos — orcamento crescendo";
  "sem coordenador de tecnologia — decisao centralizada na direcao"). Mesmos
  dados, virando municao de conversa no momento do contato. Header da ficha:
  botoes **"Relatorio da escola"** (One Page Report — casa fixa), **"+ Registrar
  contato"** e **"Gerar mensagem"**.
- **Detalhe da escola: 7 → 4 abas**:

| Sub-aba atual (7) | Destino (4) |
|---|---|
| Dados | **Visao Geral** (+ proxima atividade + botoes de acao no topo) |
| Performance ENEM | **Desempenho** (absorve tambem o Radar da Inteligencia) |
| Contatos | **Pessoas** (com o "Quem decide" / ex-Power Map embutido) |
| Mensagens + Historico | **Conversas** (timeline unica: mensagens + interacoes + atividades) |
| Registrar Contato | botao **"+ Registrar contato"** em dialog (aqui e na Home) |
| Acoes | dissolvida: relatorio/graficos viram botoes no header |

### ✉️ MENSAGENS (substitui Comunicacao: 5 abas + 7 sub-tabs → 1 fila + chips)

- **Fila unica** com chips de filtro de estado (*Aguardando aprovacao / Aprovadas /
  Enviadas / Recebidas / Follow-ups*) e de canal (*Todos / E-mail / WhatsApp*).
  Estados deixam de ficar escondidos em sub-abas.
- **"Aprovar e proxima"** para revisar em serie (botao verde grande). No painel de
  revisao: **agendar envio** (opcional, data/hora) e **"Enviar como"** (admin) —
  explicitados na v1.1 (existiam na v1, ficavam implicitos no blueprint).
- **Recebidas**: respostas com "Responder com IA" (**com escolha de canal**:
  e-mail ou WhatsApp) e "Marcar tratada".
- **Aba "Modelos"** (ex-Templates; v1.2 — aba VISIVEL, nao link discreto): lista
  dos modelos com chips de **situacao-alvo** (a matriz da selecao automatica:
  nominal/generico × com/sem dados ENEM) e **canal** (e-mail / WhatsApp — fim da
  aba WhatsApp separada), modelo padrao ★, botao "Novo modelo". Banner permanente:
  *"A IA escolhe o modelo pela situacao da escola e personaliza por dados — voce
  sempre revisa antes de sair."* A matriz fina da selecao automatica (situacao →
  modelo) e config de admin e fica em Ajustes.
- Metricas de envio SAEM daqui → Resultados (fim da triplicacao).

### 💼 NEGOCIOS (kanban comercial promovido a pagina propria)

- Colunas = etapa comercial (A contatar / Contatada / Respondeu / Reuniao /
  Proposta / Cliente / Perdida), cards ricos: escola, dono, valor, dias parado,
  prioridade. Mover via popover "Mover para ▸" (drag-drop e spike opcional).
- **Aba Reunioes**: proximas + passadas sem resultado ("Registrar resultado").
- Soma de valores propostos/fechados por coluna.

### 📊 RESULTADOS (Analytics + Metas)

- **Metas** (nova tabela `goals`): vendedor ve as proprias barras de progresso;
  admin ve grade time × metrica e define metas em dialog.
- **Funil** (ex-Analytics) com header de "numeros do pipeline" (contagem por
  etapa) e **filtros por cidade / tipo / porte** (v1.1 — gestor decide onde focar:
  "que segmento converte melhor?"). **Envios** (ex-Comunicacao>Metricas — o UNICO
  lugar de metricas de envio), **Explorar dados** (ex-Inteligencia>Explorador,
  admin, para analises ad-hoc alem da desagregacao simples do Funil).

### ⚙️ AJUSTES (admin-only) e ❓ AJUDA

- Ajustes = Configuracoes + config de follow-ups + matriz de templates + (v1.1)
  **aba Diagnostico** (uso de APIs/creditos dos ultimos 7 dias + health check +
  build stamp — orfaos da Home v1 resolvidos), **ticket por aluno** (da Receita
  potencial §3.2) e deducao de e-mails (modo avancado). Oculta para nao-admin.
- Ajuda = Manual REESCRITO no vocabulario novo: 12 tabs → 5 ("Comece aqui",
  "O dia a dia", "Trabalhando com o IAlex", "Entendendo a Prioridade", "FAQ")
  + tour de 1o login + botoes "?" contextuais nas paginas.

### Mapa DE → PARA (11 → 8)

| Pagina atual | Destino na v2 |
|---|---|
| Home (app.py) | 🏠 Hoje (reconstruida em volta da agenda) |
| 0 Chat IAlex | 🤖 IAlex (mantida + chips de sugestao) |
| 1 Importar | 🔍 Prospectar > Buscar no Brasil (wizard) |
| 2 Escolas | 🏫 Escolas (detalhe 7→4 abas) |
| 3 Contatos | 🏫 Escolas > Pessoas |
| 4 Mapa | 🔍 Prospectar (toggle Lista/Mapa) |
| 5 Pipeline | Execucao+Descoberta → 🔍 Prospectar; Kanban → 💼 Negocios |
| 6 Comunicacao | Aprovacao+Follow-ups+WhatsApp → ✉️ Mensagens; Templates → Mensagens>Modelos; Metricas → 📊 Resultados |
| 7 Inteligencia | Ranking → Prospectar>Recomendadas; Radar → Escolas>Desempenho; Explorador → Resultados |
| 8 Analytics | 📊 Resultados (+ aba Metas) |
| 9 Configuracoes | ⚙️ Ajustes (admin-only) |
| 10 Manual | ❓ Ajuda (reescrito) |

---

## 5. Prioridade unificada (fim dos 4 scores concorrentes)

**Constatacao**: o `urgency_score` (F2) JA e o score composto — combina
engagement + preditivo + intent + ENEM. O problema e a UI expor os 4 ingredientes
como 4 verdades concorrentes.

**Decisao**: "Prioridade" = urgency_tier, e SO ela aparece em listas.

| Score tecnico | Nome na UI | Onde aparece |
|---|---|---|
| urgency_tier | **Prioridade**: 🔴 Agir agora / 🟠 Quente / 🟡 Morno / ⚪ Frio | Todas as listas |
| P1/P2/P3 (ENEM) | **Potencial** ★★★/★★/★ | So em Prospectar (pre-contato) e detalhe>Desempenho |
| qualification_score | **Avaliacao da IA** | So no breakdown e detalhe>Visao Geral |
| fit_score | fundido na exibicao de Potencial | breakdown |

Todo badge de Prioridade abre um popover com o "porque" em linguagem natural
(3 mini-barras: Engajamento / Potencial / Avaliacao da IA).

**Regra de ouro**: *"Prioridade responde 'quem eu atendo primeiro hoje'.
Potencial responde 'quem eu prospecto primeiro'. Nunca os dois na mesma tabela."*

Nada muda no banco. Cria-se `dashboard/labels.py` (fonte unica de labels) e o
IAlex recebe o dicionario no system prompt (tools continuam as mesmas).

---

## 6. Dicionario unificado (vai virar `dashboard/labels.py`)

**Etapa da escola** (pill PREENCHIDA colorida — banco nao muda, labels traduz):

| Banco | UI |
|---|---|
| raw | **Nova** |
| filtered / qualified | **Avaliada** |
| enriched | **Pronta para contato** |
| contacted | **Contatada** |
| replied / respondeu | **Respondeu** |
| reuniao | **Em reuniao** |
| proposta | **Proposta enviada** |
| cliente | **Cliente** 🎉 |
| perdido | **Perdida** |

**Status de mensagem** (chip CONTORNADO com icone — familia visual distinta):
⏳ Aguardando sua aprovacao · ✅ Aprovada — sai as {hora} · ✖ Descartada ·
📤 Enviada · 👁 Aberta · 🔗 Clicou no link · 💬 Respondida · ⚠️ Nao entregue

**Outros termos**: enriquecer→**Buscar contatos** (mostrando o resultado:
"encontramos 2 pessoas e o telefone"); qualificar→Avaliar potencial;
approval queue→Caixa de saida; template→Modelo de mensagem; peer group→Escolas
semelhantes; amostra nao confiavel→"Poucos alunos fizeram ENEM — dado apenas
indicativo"; deduced→"E-mail provavel (nao confirmado)" ⚠️; INEP→Codigo da
escola (MEC); Power Map→Quem decide; One Page Report→Relatorio da escola;
Descoberta→Buscar escolas novas; Forcar→Refazer mesmo se ja feito.
Filtros com dupla negacao reescritos afirmativos ("Mostrar apenas com e-mail").

Regra: **nenhuma pagina escreve string de status na mao** — tudo via labels.py.

---

## 7. Agenda + Metas

### Modelo de dados (additive-only; v1 ignora sem quebrar)

`activities`: id, company_id, contact_id, meeting_id, **owner_username**, type
(follow_up | responder | ligar | preparar_reuniao | registrar_resultado |
aprovar_mensagens | tarefa), title, details, **due_at**, priority (1-3),
**status** (open | done | snoozed | dismissed), source (manual | auto | ialex),
auto_rule, **dedupe_key UNIQUE** (idempotencia), snoozed_until, completed_at/by,
created_by/at/updated_at. Indices: (owner, status, due_at), (company_id).

`goals`: username ('fernando'|'lizianne'|'felipe'|'team'), metric
(emails_enviados | respostas | reunioes_realizadas | propostas | clientes |
valor_fechado | atividades_concluidas), period_type (week|month|quarter),
period_start, target. UNIQUE(username, metric, period_type, period_start).
**Sem coluna `current`** — o realizado e calculado ao vivo das tabelas existentes
(queries ja existem no Analytics). Evita drift.

ALTERs: meetings + owner_username, created_by.

### Motor de atividades (`workflows/activity_engine.py` — 6 regras automaticas)

| Regra | Gatilho | Atividade |
|---|---|---|
| reply_received | resposta sem tratamento | "Responder {escola}" (prio 1, +4h) |
| followup_due | enviada ha N dias sem resposta | "Follow-up com {escola}" |
| meeting_prep | reuniao nas proximas 24h | "Preparar reuniao" (link p/ relatorio) |
| meeting_outcome | reuniao passada sem resultado | "Registrar resultado" |
| hot_no_contact | lead quente sem contato ha 5d | "Retomar {escola} — esfriando" (prio 1) |
| approvals_aging | fila pendente > 24h | "Aprovar {n} mensagens paradas" (1/dia) |

Idempotente (dedupe_key). Roda no scheduler local (30min) **e** no load da Home
(cache 5min) — cobre o caso do PC local desligado. Teto anti-spam: 25 atividades
auto abertas por dono.

### IAlex — cobertura completa das funcionalidades novas (v1.1)

Auditoria de cobertura: das necessidades novas, ~50% ja e atendido pelas ~105
tools existentes do brain.py (mover etapa, registrar proposta/cliente/perdido,
exportar planilha por voz, dados da escola). Faltam **16 tools novas/estendidas**:

| Grupo | Tools |
|---|---|
| Agenda (5) | `minha_agenda(periodo)` · `criar_atividade(titulo, escola?, quando)` · `concluir_atividade(ref)` · `adiar_atividade(ref, quando)` · `atividades_atrasadas()` |
| Metas (3) | `definir_meta(usuario, metrica, periodo, alvo)` (admin) · `minha_meta(periodo)` · `metas_time(periodo)` (admin) |
| Gestao (2) | `reatribuir_leads_lote(origem, destino)` (admin, com auditoria) · `kpi_periodo(inicio, fim, vendedor?)` |
| Inteligencia (2) | `argumentos_venda(escola)` (sintese dos dados ENEM/Censo em municao de conversa) · `preparar_reuniao(escola, data?)` (orquestra: agenda + relatorio + ultimas interacoes + argumentos) |
| Extensoes (4) | `tracking_emails`/`funil_vendas`/`ver_agenda` ganham filtro por vendedor (admin) · `exportar_escolas_xlsx` ganha filtros de data de contato e faixa de alunos |

Digest 8:15 passa a abrir com "Sua agenda de hoje: N atividades (X atrasadas)" +
progresso da meta. Exemplos de uso: "como estou na meta?", "passa os leads do
Felipe pra Lizianne", "o que preciso saber pra reuniao de amanha?", "planilha das
escolas contatadas em maio".

---

## 8. Tecnica do visual profundo (sem dependencias frageis)

**Kit**: theme.py estendido (~6 componentes novos: priority_badge, stage_pill,
message_chip, activity_row, goal_progress, empty_state) + **st.dialog** (mata as
sub-abas: registrar contato, criar atividade, definir meta, mover card) +
**st.fragment** (agenda e kanban sem rerun total) + **st.popover** (breakdown de
prioridade, mover card) + **st.segmented_control** (chips de filtro) +
**st.dataframe column_config** (dispensa AgGrid) + Plotly (ja instalado).

**NAO adotar**: streamlit-elements (abandonado, quebra no Cloud), AgGrid
(friccao de versao). Drag-drop do kanban: spike de 2 dias com streamlit-sortables
na F5 — se falhar, descarta (o popover "Mover para ▸" e o design oficial).
**Pinar `streamlit==1.56.*`** no requirements (hoje `>=1.31`, perigoso pro CSS).

---

## 9. Fases de implementacao (pos-validacao deste blueprint)

Branch `redesign-v2` + worktree `C:\Dev\IAprendo_Redesign`; preview proprio no
Streamlit Cloud apontando pro branch; **main (v1) intocada ate a F7**.

| Fase | Escopo | Aceitacao |
|---|---|---|
| **F1 Fundacoes** | Migration activities/goals (additive); activity_engine + job; **16 tools IAlex** (agenda+metas+gestao+inteligencia+extensoes); labels.py; componentes theme.py + `school_filters()` + `export_button()`; config ticket por aluno | v1 segue identica; engine roda 2x sem duplicar; "IAlex, minha agenda" e "como estou na meta?" respondem |
| **F2 Hoje+Metas** | Home nova (agenda+numeros+busca acionavel+checklist novato); Resultados c/ Metas + Funil com filtros cidade/tipo/porte | concluir/adiar em ≤2 cliques; meta com progresso real; Home <3s |
| **F3 Mensagens** | Fila unica + chips; Recebidas (responder c/ canal); Modelos c/ canal; agendar envio + "Enviar como" no painel; labels em TODOS os badges | aprovar→enviar ponta-a-ponta no preview; zero status hardcoded |
| **F4 Prospectar+Escolas** | Recomendadas + wizards (resultado da busca com export) + toggle Mapa + Sinais de compra; detalhe 7→4 c/ Argumentos de venda + Relatorio no header; Pessoas (⚠️ deduzidos, filtros proprios); filtros padrao (incl. Completude) + Potencial R$/mes + export em todas as listas; **seletor de colunas (4 presets) + export_utils modo completo**; nome-link + coluna ↗ p/ a ficha | novato importa e gera 1a mensagem so pelo wizard; ENEM em exatamente 2 lugares; "planilha" em 1 clique de qualquer lista (incl. TODAS as colunas); abrir a ficha a partir da lista em 1 clique; checklist de paridade da fase 100% |
| **F5 Negocios** | Kanban pagina propria + popover mover + valores + Reunioes; **transferencia de leads em lote (admin)**; spike drag-drop | mover card reflete no IAlex; reuniao sem resultado gera atividade; redistribuir N leads em <2min |
| **F6 Polimento+Ajuda** | Estados vazios; Ajuda 5 tabs; tour 1o login; Ajustes admin-only (+Diagnostico: APIs/health/build) | **teste do novato**: pessoa externa completa o roteiro sem ajuda, <15min |
| **F7 Cutover** | Merge na main; stubs de redirect 30 dias; Manual+prompt IAlex atualizados; treinamento 1h | time opera 1 semana sem abrir a v1; rollback = revert; pytest verde; checklist de paridade (apendice A) 100% |

## 10. Riscos e mitigacoes (top 8)

1. **Drag-drop inviavel** → design oficial NAO depende dele (popover); spike descartavel.
2. **URLs/bookmarks quebrados** → stubs de redirect 30 dias + grep por links hardcoded.
3. **UI diverge do IAlex** → labels.py fonte unica + dicionario no prompt do brain.
4. **Scheduler local desligado → agenda nao gera** → engine tambem roda no load da Home (idempotente).
5. **Supabase unico (prod=dev)** → migrations 100% additive; backup antes de cada uma.
6. **Escopo crescer** → este blueprint congela a onda 1; ideias novas viram backlog F8+.
7. **CSS quebrar com upgrade do Streamlit** → pinar 1.56.*; smoke visual a cada bump.
8. **Perda de produtividade dos 3 usuarios** → preview desde F2; treinamento antes do cutover; rollback trivial.

## 11. Preservacao (ja executada em 2026-06-10)

- Tag **`v1-prod`** no GitHub (restauracao: `git reset --hard v1-prod`).
- Branch **`redesign-v2`** publicado; desenvolvimento na worktree
  `C:\Dev\IAprendo_Redesign` (a pasta original fica na main rodando IAlex).
- Backup diario do CRM via GitHub Action → bucket privado `backups` (Supabase).
- Pasta duplicada manual do dono = reserva extra.
- Pendentes do dono: copia de `.env`+`users.yaml` em nuvem privada; teste manual
  do workflow de backup (Actions → Backup CRM → Run workflow).

## 12. Estrategia de testes (v1.1 — "imagine se voce fosse utilizar")

Tres camadas, cada uma barata em relacao ao erro que evita:

**Camada A — Testes de DESIGN (agora, antes de qualquer codigo)**
- 12 jornadas de uso simulado (7 vendedor + 5 gestor) re-executadas contra cada
  versao do blueprint/mockups. Criterio: **0 travas** (atritos viram backlog).
  Rodada 1 achou: ficha da escola sem desenho, export invisivel, resultado da
  busca ausente, reatribuicao em massa inexistente — corrigidos na v1.1.
- **Teste do novato em mockup** (`docs/mockups/TESTE_NOVATO.md`): Lizianne e
  Felipe executam 6 tarefas apontando onde clicariam, sem ajuda verbal, <15 min.
  Mede: travou? hesitou >10s? interpretou errado o nome?

**Camada B — Testes de CODIGO (durante o desenvolvimento, por fase)**
- Regra de arquitetura: logica fora das paginas (helpers/modulos testaveis).
- pytest para os motores novos: activity_engine (6 regras + dedupe idempotente),
  labels.py (todo mapeamento banco->UI), calculo de metas (realizado ao vivo) e
  receita potencial, school_filters (montagem de query).
- **Streamlit AppTest** (`st.testing.v1`) como smoke de TODA pagina nova: renderiza
  sem excecao + elementos-chave presentes. Roda no pytest normal (sem browser).
- A tabela de paridade (Apendice A) vira checklist de aceitacao por fase: a fase
  so fecha quando os itens dela estao na UI.

**Camada C — Testes de PRODUTO (antes do cutover F7)**
- Teste do novato REAL na preview (pessoa externa, roteiro da camada A, <15 min).
- 1 semana de uso paralelo (v1 na main + v2 na preview) com feedback diario.
- Suite pytest 100% verde (incl. os 75 testes atuais da v1 — nada regride).

## 13. Apendice A — Paridade v1->v2 (auditoria de 2026-06-10)

Auditoria sistematica das 11 paginas da v1: **~85% com casa explicita** no
blueprint. Itens que exigiram decisao (todas tomadas na v1.1):

**Orfaos resolvidos**
| Item da v1 | Casa na v2 |
|---|---|
| Uso de APIs/creditos (Home) | Ajustes > Diagnostico |
| Health check + build stamp (Home) | Ajustes > Diagnostico |
| Descoberta / sinais de compra (Pipeline) | Prospectar > Sinais de compra |
| One Page Report + graficos de insight | Ficha da escola > header "Relatorio da escola" |
| Deducao de e-mails | Feedback de "Buscar contatos" (+ avancado em Ajustes) |
| Override de nome de rede | Dialog ✏️ no agrupamento Redes (Escolas) |

**Implicitos explicitados** (existiam na v1; agora nomeados na v2): agendar envio
(painel de Aprovar) · "Enviar como" admin (painel de Aprovar) · modelos com canal
e-mail/WhatsApp · responder com escolha de canal · e-mails deduzidos ⚠️ (Pessoas)
· numeros do pipeline (header do Funil) · registro manual de interacao (botao na
ficha e na Home) · % de sucesso de geocodificacao/telefones (feedback do Preparar).

**Descontinuar de proposito** (decisao do dono na validacao): notificacoes in-app
inacabadas da v1 · morning_panel (absorvido pela agenda) · metricas duplicadas em
Comunicacao (movidas para Resultados) · edicao inline AgGrid-style (substituida
por dialogs — mais estavel no Streamlit).

## 14. Criterios de sucesso da v2

1. Um vendedor novo executa o ciclo (achar escola → aprovar mensagem → registrar
   contato → concluir atividade) **sozinho, sem treinamento, em <15 minutos**.
2. O ciclo diario de um vendedor experiente acontece em **≤2 paginas** (Hoje + Mensagens).
3. **Zero duplicacao** de funcao primaria entre paginas.
4. **Uma unica nocao de Prioridade** visivel; demais scores viram explicacao.
5. Gestor define metas e acompanha o time **sem sair de Resultados**.
