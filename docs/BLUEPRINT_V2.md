# 🧭 Blueprint v2 — "Dia de Venda"

> Redesign da plataforma IAprendo Sales Agent: de 11 paginas organizadas pelo
> fluxo tecnico dos dados para 8 espacos organizados pelo dia do vendedor.
>
> **Status**: PROPOSTA — para validacao com o time antes de qualquer codigo.
> **Data**: 2026-06-10 | **Base**: tag `v1-prod` | **Branch de trabalho**: `redesign-v2`
> **Mockups navegaveis**: `docs/mockups/index.html` (abra no navegador)

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

## 3. Principio organizador

> **A navegacao segue o dia do vendedor, nao o pipeline de dados.**
> Cada pagina responde a uma pergunta que o vendedor faria em voz alta.
> A primeira pagina responde: "o que eu faco agora?"

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
  Botao por linha: **"Trabalhar esta escola"** (importa + prepara + atribui dono).
- **Buscar no Brasil**: ex-Importar como wizard de 3 passos
  (*Escolher regiao → Revisar lista → Adicionar a minha carteira*).
- **Toggle Lista/Mapa**: o Mapa (PyDeck) vira visualizacao alternativa do mesmo
  filtro — deixa de ser pagina propria.
- **Preparar lote**: ex-Pipeline-Execucao como wizard guiado
  (*Selecionar → Buscar contatos → Gerar mensagens → vao para Mensagens*).
  Modos avancados ("Forcar" etc.) atras de "Opcoes avancadas".

### 🏫 ESCOLAS (funde Escolas + Contatos)

- Lista unica com colunas enxutas: Escola, Cidade, **Etapa** (pill), **Prioridade**,
  Dono, Ultimo contato. "Redes" vira filtro/agrupamento (nao aba).
- **Aba "Pessoas"**: a pagina Contatos inteira entra aqui (decisores + export).
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
- **"Aprovar e proxima"** para revisar em serie (botao verde grande).
- **Recebidas**: respostas com "Responder com IA" e "Marcar tratada".
- **Aba "Modelos"** (ex-Templates) com banner permanente:
  *"Modelos sao a base que a IA personaliza por escola. Voce sempre revisa antes de sair."*
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
- **Funil** (ex-Analytics), **Envios** (ex-Comunicacao>Metricas — o UNICO lugar de
  metricas de envio), **Explorar dados** (ex-Inteligencia>Explorador, admin).

### ⚙️ AJUSTES (admin-only) e ❓ AJUDA

- Ajustes = Configuracoes + config de follow-ups + matriz de templates. Oculta
  para nao-admin.
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

### IAlex (4 tools novas)
`minha_agenda(periodo)` · `criar_atividade(titulo, escola?, quando)` ("me lembra
de ligar pro Colegio Alfa sexta") · `concluir_atividade(ref)` · `adiar_atividade(ref, quando)`.
Digest 8:15 passa a abrir com "Sua agenda de hoje: N atividades (X atrasadas)".

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
| **F1 Fundacoes** | Migration activities/goals (additive); activity_engine + job; 4 tools IAlex; labels.py; componentes theme.py | v1 segue identica; engine roda 2x sem duplicar; "IAlex, minha agenda" responde |
| **F2 Hoje+Metas** | Home nova (agenda+numeros+busca acionavel+checklist novato); Resultados c/ Metas | concluir/adiar em ≤2 cliques; meta com progresso real; Home <3s |
| **F3 Mensagens** | Fila unica + chips; Recebidas; Modelos; labels em TODOS os badges | aprovar→enviar ponta-a-ponta no preview; zero status hardcoded |
| **F4 Prospectar+Escolas** | Recomendadas + wizards + toggle Mapa; detalhe 7→4; Pessoas | novato importa e gera 1a mensagem so pelo wizard; ENEM em exatamente 2 lugares |
| **F5 Negocios** | Kanban pagina propria + popover mover + valores + Reunioes; spike drag-drop | mover card reflete no IAlex; reuniao sem resultado gera atividade |
| **F6 Polimento+Ajuda** | Estados vazios; Ajuda 5 tabs; tour 1o login; Ajustes admin-only | **teste do novato**: pessoa externa completa o roteiro sem ajuda, <15min |
| **F7 Cutover** | Merge na main; stubs de redirect 30 dias; Manual+prompt IAlex atualizados; treinamento 1h | time opera 1 semana sem abrir a v1; rollback = revert; pytest verde |

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

## 12. Criterios de sucesso da v2

1. Um vendedor novo executa o ciclo (achar escola → aprovar mensagem → registrar
   contato → concluir atividade) **sozinho, sem treinamento, em <15 minutos**.
2. O ciclo diario de um vendedor experiente acontece em **≤2 paginas** (Hoje + Mensagens).
3. **Zero duplicacao** de funcao primaria entre paginas.
4. **Uma unica nocao de Prioridade** visivel; demais scores viram explicacao.
5. Gestor define metas e acompanha o time **sem sair de Resultados**.
