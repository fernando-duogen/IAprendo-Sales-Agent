# SPEC OPERACIONAL — Agenda de Atividades + Metas + Gestao do Time (v2)

> Guia de implementacao das fases F1/F2 do redesign "Dia de Venda".
> **Status**: PROPOSTA v1.0 (2026-06-10) — complementa `docs/BLUEPRINT_V2.md`
> §4/§7/§14 (nao os repete; onde houver conflito, esta spec prevalece por ser
> mais recente e mais detalhada).
> **Principio-mae**: *uma agenda so funciona se NUNCA mentir.* Atividade aberta
> cujo motivo ja morreu e mentira. Meta cujo "realizado" muda retroativamente e
> mentira. Toda regra abaixo existe para impedir essas duas mentiras.

---

## 0. Premissas operacionais

| Premissa | Valor decidido |
|---|---|
| Fuso de TUDO que o usuario ve | **America/Sao_Paulo (BRT)**. Banco grava `TIMESTAMPTZ` em UTC; conversao na borda (UI, IAlex, digest). "Hoje" = 00:00–23:59 BRT. |
| Horario comercial (SLA e horas uteis) | **Seg–Sex, 8h–18h BRT**. O engine nunca agenda `due_at` em sabado/domingo — rola para segunda 9h. |
| Capacidade saudavel | **6–10 execucoes/dia/vendedor** (sao socios com outras funcoes). Acima de 12 abertas para hoje, o digest avisa "dia sobrecarregado — ataque so as prioridade 1". |
| Quem e quem | Fernando = admin/gestor. Lizianne e Felipe = vendedores. Todos veem tudo (dados compartilhados, sem RLS); permissoes de ESCRITA seguem §1.2. |
| Quando o engine roda | Scheduler local a cada 30min **+** load da Home (cache 5min). Cada execucao faz, NESTA ordem: (1) varredor de auto-resolucao → (2) reabertura de snoozed vencidos → (3) expiracao → (4) criacao de novas. Criar antes de varrer geraria atividade ja morta. |

---

## 1. Ciclo de vida da atividade

### 1.1 Maquina de estados

```
                    ┌──────────── snoozed_until chegou (engine) ───────────┐
                    ▼                                                      │
 (criacao) ──► open ──► done        (✓ humano, IAlex, ou varredor)         │
                │  ╲──► snoozed     (⏰ humano/IAlex, respeitando §1.5) ───┘
                ╰──► dismissed      (humano com motivo, ou varredor/expiracao)
```

- `done` e `dismissed` sao **terminais**. Nao existe "reabrir" (anti-bagunca):
  se o assunto volta, o engine ou o humano cria atividade nova. Unica excecao:
  "Desfazer" no toast em ate 10 minutos (protege o clique errado).
- `snoozed` e `open` adormecida: nao aparece na agenda, nao conta no teto,
  volta sozinha.
- **Toda transicao grava quem e quando**: `completed_at/by` para done; para
  dismiss/expiracao usa-se o campo `resolution` (§9).

### 1.2 Matriz de permissoes

| Acao | Dono da atividade | Admin | Outro socio | IAlex | Engine |
|---|---|---|---|---|---|
| Criar manual (pra si) | ✓ | ✓ | ✓ | ✓ (a pedido) | — |
| Criar para OUTRO | ✗ | ✓ (`source=manual`, `created_by=fernando`) | ✗ | ✓ so a pedido do admin | ✓ (auto) |
| Concluir / Adiar | ✓ | ✓ (cobertura) | ✗ | ✓ (a pedido do dono) | ✓ (auto-resolucao) |
| Dispensar | ✓ (1 clique + motivo) | ✓ | ✗ | ✓ | ✓ (gatilho morto/expiracao) |
| Editar titulo/detalhes/prio/due | ✓ **so em `source=manual\|ialex`** | ✓ idem | ✗ | ✓ idem | ✓ (atualiza auto in-place, §1.4) |
| Reatribuir (mudar owner) | ✗ | ✓ (individual ou junto c/ transferencia do lead) | ✗ | ✓ (lote, admin) | ✓ (segue o lead) |

**Decisao critica**: atividades `source=auto` NAO sao editaveis em conteudo por
ninguem — titulo e detalhes pertencem a regra (o engine os atualiza, ex.:
"Aprovar **12** paradas" → "Aprovar **8** paradas"). Quem quiser algo diferente
cria uma manual. Editar auto-atividade quebraria o contrato do `dedupe_key` e
da auto-resolucao.

### 1.3 Criacao — fontes e chaves de idempotencia

Tres fontes (`source`): `auto` (engine), `manual` (UI: "+ Nova atividade" e
dialogs contextuais), `ialex` ("me lembra de ligar sexta"). Manual/IAlex:
`type` default `tarefa` (ou `ligar` se o texto indicar), prio default 2, due
default **9h** quando so vier a data ("sexta" → sexta 9h).

`dedupe_key` por regra — o formato E a semantica de "quando pode nascer de novo":

| auto_rule | dedupe_key | Consequencia |
|---|---|---|
| reply_received | `responder:{company_id}:{interaction_id_da_resposta}` | cada resposta nova = 1 atividade; a mesma resposta nunca duplica |
| followup_due | `followup:{company_id}:{message_id}:{n}` | 1 por mensagem-mae por nº de follow-up |
| sequencia_toques | `seq:{company_id}:{sequence_step}` | toque N nasce 1x por escola; resposta reseta a sequencia (§5.9) |
| meeting_prep | `prep:{meeting_id}:{data_ISO_da_reuniao}` | **remarcou = chave nova** → prep nova com due novo; a antiga morre no varredor (§1.4) |
| meeting_outcome | `outcome:{meeting_id}` | 1 por reuniao, independe de remarcacao |
| hot_no_contact | `hot:{company_id}:{data_do_ultimo_contato}` | novo episodio de esfriamento = chave nova; o mesmo episodio nunca duplica |
| approvals_aging | `approvals:{owner}:{yyyy-mm-dd}` | max 1/dia/dono |
| goal_reminder (§4.1) | `goalrem:{yyyy-mm}` | lembrete de metas 1x/mes para o admin |

**Horarios default por regra** (estagiados de proposito, para o dia ter ritmo):

| Regra | due_at |
|---|---|
| responder | criacao + **4h uteis** (SLA; criada 16h → due amanha 10h) |
| aprovar_mensagens | hoje **9h** |
| followup/sequencia | dia-alvo **10h** |
| hot_no_contact | hoje **14h** |
| preparar_reuniao | inicio da reuniao − 24h (min. hoje 16h se a reuniao e amanha cedo) |
| registrar_resultado | fim da reuniao + 2h uteis |

### 1.4 AUTO-RESOLUCAO — o varredor (a regra mais importante desta spec)

Sem isto a agenda vira lixo em 2 semanas: o vendedor responde pelo Outlook,
aprova pela fila, e a agenda continua cobrando. **A cada execucao, o engine
varre todas as auto-atividades `open|snoozed` e resolve as que perderam o
motivo.** Tabela normativa, POR TIPO:

| Tipo / regra | O gatilho morre quando… | Desfecho | `resolution` |
|---|---|---|---|
| **responder** | existe interaction OUTBOUND (`email_sent`, `whatsapp_sent`, registro manual, ligacao) para a MESMA escola com timestamp > `created_at` da atividade — **por qualquer socio** — OU a resposta foi marcada "tratada" | **auto-done** (`completed_by='system'`) | `auto_trabalho_detectado` |
| **follow_up / sequencia_toques** | (a) outbound para a escola apos a criacao; (b) o lead respondeu → a cadencia morre (nasce "Responder" no mesmo ciclo); (c) etapa mudou para reuniao/proposta/cliente/perdido | (a) **auto-done**; (b)(c) **auto-dismiss** | (a) `auto_trabalho_detectado`; (b)(c) `auto_gatilho_morto` |
| **preparar_reuniao** | (a) reuniao cancelada; (b) remarcada (chave nova nasce); (c) a reuniao ja passou com a atividade aberta | **auto-dismiss** nos 3. (c) NAO vira done: nao sabemos se preparou; inflar conclusao corrompe a metrica §7 | (a,b) `auto_gatilho_morto`; (c) `expirada` |
| **registrar_resultado** | `meetings.outcome` preenchido (UI, IAlex ou Negocios) | **auto-done** | `auto_trabalho_detectado` |
| **aprovar_mensagens** | fila pendente >24h do dono zerou | **auto-done**. Se diminuiu sem zerar, o engine **atualiza o titulo in-place** — nunca cria outra no dia | `auto_trabalho_detectado` |
| **hot_no_contact** | (a) outbound/registro para a escola; (b) prioridade caiu abaixo de Quente | (a) **auto-done**; (b) **auto-dismiss** | (a) `auto_trabalho_detectado`; (b) `auto_gatilho_morto` |
| **tarefa / ligar (manual, ialex)** | **NUNCA auto-resolve** — so o humano sabe se fez. Excecoes: escola deletada (cascade, §5.3) e lead transferido (vai junto, §5.1) | — | — |

Deteccao de outbound: query em `interactions` (tipos `email_sent`,
`whatsapp_sent` + registro manual) por `company_id` e `created_at >
activity.created_at`. Zero coluna nova para isso.

### 1.5 Snooze — adiar sem enterrar

| Regra | Valor |
|---|---|
| Opcoes na UI (1 clique) | **+2h · Amanha 9h · Segunda 9h · Escolher data** |
| Prioridade 1 | so **+2h** ou **Amanha 9h** (resposta de lead nao hiberna uma semana) |
| Maximo de adiamentos | **3 por atividade** (`snooze_count`). No 3º, o botao ⏰ vira **"Dispensar com motivo"** |
| Horizonte maximo | `snoozed_until` ≤ `due_at original` + **14 dias** |
| Retorno | engine reabre quando `snoozed_until` chega; volta com badge "adiada 2x" |
| Interacao com auto-resolucao | o varredor TAMBEM olha snoozed — se o gatilho morreu durante o snooze, resolve la dentro (nunca ressuscita zumbi) |

### 1.6 Atrasadas — rollover e expiracao (anti-acumulo)

Atrasada = `open` com `due_at` < agora. Permanece em **⚠️ Atrasadas** com badge
de idade. Expiracao POR ORIGEM — auto-atividade irrelevante se apaga; divida
real nao:

| Origem/regra | Expira? | TTL apos o due | Racional |
|---|---|---|---|
| responder (prio 1) | **NAO** | — | resposta de lead e a coisa mais valiosa do sistema; fica vermelha ate alguem agir |
| registrar_resultado | **NAO** | — | divida de dado real; sem isso funil e metas furam |
| follow_up / sequencia | sim | **7 dias** | o engine recria o passo certo conforme o estado REAL do lead |
| hot_no_contact | sim | **5 dias** | se ninguem agiu, o caso migra para "parados >7d" do painel Equipe |
| aprovar_mensagens | sim | **fim do dia** | e diaria por construcao; renasce amanha se persistir |
| preparar_reuniao | sim | quando a reuniao passa | §1.4 |
| manual / ialex | **NAO** | — | compromisso humano; nunca some sozinho |

Expiracao = `dismissed` + `resolution='expirada'`. **% de expiradas e metrica de
saude (§7)**: se uma regra expira demais, a regra esta ruidosa — conserta-se a
regra, nao se educa o usuario.

### 1.7 Anti-colisao — max 1 auto-atividade "de contato" por escola/dono

- **Precedencia**: `responder` (1) > `registrar_resultado` (2) >
  `preparar_reuniao` (3) > `hot_no_contact` (4) > `follow_up`/`sequencia` (5).
  (`aprovar_mensagens` e por dono, fora da disputa.)
- Por (escola, dono): **max 1 atividade aberta do grupo {responder,
  hot_no_contact, follow_up/sequencia}**. Existe uma de precedencia maior ou
  igual → a nova NAO nasce. Nasce uma maior (chegou resposta) → o varredor
  dismissa a menor no mesmo ciclo.
- `preparar_reuniao` e `registrar_resultado` coexistem com qualquer outra
  (presas a reuniao, nao a conversa).
- **Teto de 25 auto abertas/dono**: vale para prio 2–3. **Prio 1 fura o teto**
  (perder resposta de lead para um limite de spam inverte a prioridade do
  negocio). Trava absoluta: 40 — acima, o engine para de criar e loga erro.

### 1.8 Ordem de exibicao da agenda

Grupos fixos: **⚠️ Atrasadas → Hoje → Amanha**. Dentro de cada grupo:
`priority ASC` → `due_at ASC` → `created_at ASC`. Atrasadas: a mais antiga de
cada prioridade primeiro. "Hoje" exibe ate 10 linhas + "ver mais N"; concluidas
do dia somem da lista mas alimentam o contador "✓ 5 concluidas hoje" no rodape
(reforco positivo barato, sem gamificacao).

---

## 2. Rotina diaria do vendedor

A agenda decide POR ele; o dia tem 3 blocos. A ordem de exibicao (§1.8) ja E a
ordem de ataque.

**8h00–8h15 — abertura (5 min, no celular)**
1. Digest do IAlex as 8:15: *"Bom dia! Sua agenda: 7 atividades (2 atrasadas, 1
   prioridade maxima). Respostas esperando: 1 (ha 14h ⚠️). Reuniao hoje:
   nenhuma. Meta de junho: e-mails 70% · reunioes 60%."* Se >12 atividades:
   *"dia cheio — ataque so as 3 de prioridade 1"*.
2. Abre a Home. Os 3 numeros dizem o tamanho do dia. Nada para decidir.

**Manha — bloco de resposta (o mais valioso)**
1. **Atrasadas prio 1** primeiro, sempre. SLA de resposta = 4h uteis.
2. **Respostas novas** → Mensagens > Recebidas → "Responder com IA" → revisa →
   envia. O varredor auto-conclui a atividade "Responder" no proximo ciclo —
   ele nem precisa voltar a Home para dar ✓.
3. **Aprovar mensagens** (due 9h): "Aprovar e proxima" em serie (12 ≈ 10 min).

**Meio do dia — bloco de avanco**
4. Follow-ups e toques da sequencia (due 10h): texto ja gerado; revisa e dispara.
5. Ligacoes e tarefas proprias (due 11h+).
6. 12h: se sobrou prio 1 atrasada >24h, o midday_check pinga UMA mensagem (§6).

**Tarde — bloco de preparo**
7. `hot_no_contact` (due 14h) e `preparar_reuniao` (due 16h — clica, abre o
   Relatorio da escola + ultimas interacoes).

**17h–17h30 — fechamento (5 min)**
8. End-of-day do IAlex (17h): *"Ficaram 2 abertas: [Ligar X] [Follow-up Y].
   Concluir, adiar pra amanha ou deixar atrasar?"* — "adia tudo" resolve pelo
   WhatsApp.
9. Regra de ouro: **nenhuma atividade de hoje fica sem decisao consciente**
   (done, snooze ou dismiss). Atrasada "por decisao" e ok; "por esquecimento" e
   o que o sistema combate.
10. Registra contatos feitos fora da plataforma — alimenta a auto-resolucao e
    as metas.
11. Olha "Amanha" por 30 segundos. Fim.

---

## 3. Rotina do gestor (Fernando)

**Segunda, 8h30 — ritual semanal (15 min, toggle Equipe)**, nesta ordem:

| # | Olha | Acao possivel (1 clique) |
|---|---|---|
| 1 | **Atrasadas por vendedor** | "Ver agenda" do socio → prio 1 parada? cobra no grupo ou assume (cobertura) |
| 2 | **Leads sem dono** | atribui dono (select inline) |
| 3 | **Parados >7d por dono** | "Reatribuir ▸" ou pede decisao de arquivar |
| 4 | **Fila de aprovacao envelhecendo** | abre Mensagens como o dono ("Enviar como") ou cobra |
| 5 | **Semana anterior vs ritmo da meta** (pro-rata) | anota 1 ponto de conversa por pessoa |

**Sexta, 17h30 — weekly report (IAlex, formato = painel Equipe)**: 7 KPIs da
semana, destaca o 🏆 no grupo, decide reforcos de segunda.

**Dia 25**: o engine cria "🎯 Definir metas de {mes+1}" para o admin
(`goalrem:{yyyy-mm}`, due dia 25 9h). O dialog abre com calibracao historica e
pre-preenche com as metas do mes corrente.

**1º dia util do mes**: digest de fechamento (§4.6) + 5 min na grade de
Resultados. Decisoes tipicas: recalibrar metas, redistribuir carteira.

---

## 4. Metas — ciclo completo

### 4.1 Calendario (mensal; week/quarter ficam no schema, fora da UI na onda 1)

| Quando | O que | Quem |
|---|---|---|
| Dia 25 | atividade auto + digest: "definir metas de {mes+1}" | admin |
| Ate o ultimo dia util | metas definidas no dialog (com calibracao) | admin |
| Dia 1, 00:05 | **rollover automatico**: (vendedor, metrica) com meta anterior e SEM meta nova → **copia** com marca `herdada` no `revision_log` | engine |
| Dia 1, digest | fechamento do mes anterior + metas novas ("herdadas" sinalizadas) | IAlex |
| Dias 1–5 | janela de ajuste livre | admin |
| Dia 6+ | mudanca exige **motivo** (gravado no `revision_log`); a barra exibe ✎ "ajustada em DD/MM" | admin |

Decisoes: (a) meta vazia e pior que herdada — rollover SEMPRE, sinalizado;
(b) mudar meta no meio do mes e PERMITIDO, nunca silencioso; (c) admin de
ferias nao trava (metas podem ser definidas pra qualquer period_start futuro +
rollover cobre o esquecimento).

### 4.2 Periodo parcial

`period_start` SEMPRE normalizado pro dia 1 (semana → segunda). O que se ajusta
e a EXPECTATIVA: `no ritmo ⇔ realizado ≥ target × (dias uteis decorridos /
dias uteis do mes) × 0,9`. Vendedor novo no dia 10: admin define target
proporcional (a calibracao mostra a conta).

### 4.3 Fechamento historico — O BURACO que esta spec tapa

"Realizado ao vivo" so preserva o mes fechado se TODAS as fontes forem eventos
timestamped imutaveis. Auditoria:

| Metrica | Fonte | Historico seguro? |
|---|---|---|
| emails_enviados | `interactions.email_sent` | ✅ |
| respostas | `interactions.*_replied` | ✅ |
| reunioes_realizadas | `meetings.status='completed'` + data | ✅ |
| atividades_concluidas | `activities.completed_at` (done humano + `auto_trabalho_detectado`; exclui dismissed/expiradas) | ✅ |
| **propostas / clientes / valor_fechado** | hoje seria `companies.status` — **MUTA** | ❌ **furo** |

Se um cliente de junho cair em agosto, "junho fechado" mudaria retroativamente.
**Correcao (F1, obrigatoria)**: trigger `ON UPDATE OF status/commercial_stage ON
companies` → `INSERT INTO interactions (type='stage_changed',
metadata={from,to,valor})`. Trigger (nao codigo) porque captura TODOS os
caminhos: dashboard v1, v2, IAlex, HubSpot pull. As 3 metricas passam a contar
**eventos de entrada na etapa no periodo**. Com isso, consulta por
`period_start` resolve o historico — **sem snapshot, sem coluna `current`**.

### 4.4 Time vs individual

Meta de time (`username='team'`) e **registro independente, nao soma
automatica**. O dialog mostra a soma das individuais como referencia. Sem meta
team → header usa a soma com nota "(soma das metas individuais)". Vendedor ve as
proprias barras + a do time (transparencia entre socios).

### 4.5 Quem ve o que

| Visao | Vendedor | Admin |
|---|---|---|
| Anel na Home | proprias metricas com meta | + mini-resumo do time no toggle Equipe |
| Resultados > Metas | proprias barras + barra do time | grade completa + "Definir metas" |
| IAlex | `minha_meta` | + `metas_time`, `definir_meta` |

### 4.6 Celebracao (barato, sem gamificacao)

Digest do 1º dia util: *"Maio fechado: time 9/15 reunioes (60%). Lizianne bateu
respostas (10/8 🏆). Junho comeca com: …"*. 🏆 na celula ≥100%. Weekly report
nomeia 1 destaque. SEM ranking permanente (3 socios; ranking so azeda).

---

## 5. Edge cases (15, com resolucao normativa)

| # | Caso | Resolucao |
|---|---|---|
| 1 | Lead transferido com atividades abertas | Vao JUNTO (update owner em todas open/snoozed, auto e manuais), com nota em `details` + `resolution` de auditoria. due NAO muda (a divida com o lead nao reseta por troca de dono). |
| 2 | Ferias de um socio | Flag `away:{username}` em Ajustes. Engine NAO cria auto prio 2–3 pro ausente; prio 1 nasce MAS destaca no painel Equipe ("dono ausente — reatribuir?"); admin decide ou transfere em lote. Digest suspenso. Metas mantidas; weekly report anota "ausente N dias". |
| 3 | Atividade orfa (escola deletada) | FK `ON DELETE CASCADE`. O dialog de delete em massa avisa: "X atividades abertas serao removidas junto". |
| 4 | Duas auto-regras no mesmo lead no mesmo dia | Resolvido por construcao: precedencia + max 1 "de contato" por (escola, dono) (§1.7). |
| 5 | Vendedor ignora a agenda 1 semana | Escalonamento de VISIBILIDADE, nunca de automacao: badge no Equipe (dia 1) → midday pinga o proprio (>24h prio 1) → weekly report nomeia (sexta) → ritual do gestor (segunda). NUNCA reatribui sozinho. Auto de baixo valor expira (§1.6) — sobra so o que importa. |
| 6 | Manual duplicada da automatica | Nao bloqueia (humano manda). UI avisa: "ja existem 2 atividades abertas desta escola — [ver]". Varredor NUNCA auto-resolve manuais. |
| 7 | Reuniao remarcada | Chave de prep inclui a data: remarcou → prep antiga `auto_gatilho_morto`, nova nasce com due certo. Outcome nao duplica (chave sem data). |
| 8 | Snooze alem do due da sequencia | Toques seguintes NAO sao pre-criados — toque N+1 so nasce apos o N ser RESOLVIDO, e o relogio (3d/7d) conta do envio REAL (interactions). Snooze segura a sequencia; limite de 3 impede hibernar pra sempre. |
| 9 | Lead respondeu DEPOIS do break-up | `reply_received` cria "Responder" prio 1 normal. Varredor dismissa a "Decidir: arquivar?" e **reseta a sequencia** (novo ciclo, novas chaves). |
| 10 | Nenhuma meta definida (estado vazio) | So no 1º mes (rollover cobre depois). Home: anel vira CTA; IAlex avisa. KPIs continuam visiveis SEM alvo — nunca esconder o realizado por falta de meta. |
| 11 | Admin de ferias na virada do mes | Metas antecipaveis (period_start futuro) + rollover do dia 1. Sem "admin substituto". |
| 12 | Relogio/fuso | §0: UTC no banco, BRT na borda, "hoje" = dia BRT, nunca due em fim de semana, sempre `America/Sao_Paulo` explicito (cobre engine em servidor UTC no futuro). |
| 13 | Resposta em lead SEM dono | Nasce pro **admin** com titulo "(lead sem dono) Responder X" + destaque no Equipe. Atribuir dono reatribui a atividade junto. |
| 14 | Vendedor da ✓ sem ter feito | Aceito (confianca entre socios). Os KPIs de verdade vem de `interactions`, nunca da atividade — conclusao falsa nao infla metrica de negocio, so a propria taxa de conclusao (§7), visivel ao gestor. Auto-correcao social. |
| 15 | PC local desligado (scheduler off) | Engine roda no load da Home (cache 5min). Pushes atrasam (aceito); numeros da Home sao AO VIVO. |

---

## 6. Notificacoes — politica anti-ruido

Principio: **push e interrupcao; interrupcao so para o que vale dinheiro
AGORA.** O resto espera o digest ou a Home.

| Evento | 📲 Push imediato | 🌅 Digest 8:15 | 🕛 Midday 12h | 🌇 Fim do dia 17h | So na Home |
|---|---|---|---|---|---|
| Resposta de lead recebida | ✓ (sempre) | recap | — | — | — |
| Lead CRITICAL novo | ✓ (max 3/dia; excedente → digest) | recap | — | — | — |
| Reuniao em 2h | ✓ (com link do Relatorio) | ✓ | — | — | — |
| Agenda do dia / atrasadas | — | ✓ | — | — | ✓ |
| Prio 1 atrasada >24h | — | — | ✓ (1 linha) | — | ✓ |
| Fila de aprovacao parada | — | ✓ (se >24h) | — | — | ✓ |
| Progresso da meta | — | ✓ (1 linha) | — | — | ✓ (anel) |
| Atividades que sobraram | — | — | — | ✓ ("adia tudo" via WhatsApp) | — |
| Auto-resolucao/expiracao/snooze | — | — | — | — | ✓ (silencioso) |
| Fechamento do mes / metas | — | ✓ (dia 1) | — | — | ✓ |
| Weekly report | — | — | — | sexta 17:30 (gestor) | painel Equipe |

**Limites duros**: max **6 pushes imediatos/dia/pessoa** (resposta de lead NAO
conta no teto); excedentes agrupam no proximo digest. **Quiet hours 19h–7h45
BRT** (respostas noturnas abrem o digest com "⚠️ esperando desde ontem 21h").
Os jobs existentes (morning 8:15, midday, end-of-day, weekly, check_replies
15min) viram os CARTEIROS desta matriz — nenhum job novo, so conteudo novo.

---

## 7. Metricas do proprio sistema (a agenda se mede)

Onde: **Ajustes > Diagnostico, card "Saude da agenda"** (admin — metrica de
SISTEMA, nao de venda). Excecao: taxa de conclusao semanal por vendedor no
painel Equipe (e gestao).

| Metrica | Calculo | Saudavel | Alarme |
|---|---|---|---|
| Taxa de conclusao no dia | done ate 23:59 do due ÷ vencidas no dia | ≥70% | <50% = agenda gera mais do que cabe |
| % auto-resolvidas | `auto_trabalho_detectado` ÷ done | 25–50% | >60% = time nao olha a agenda; <10% = varredor quebrado |
| % expiradas | `expirada` ÷ criadas auto | <15% | >25% = regra fabricando lixo (o log diz qual) |
| Idade media das abertas | media de `now − due_at` das atrasadas | <2 dias uteis | crescendo = acumulo estrutural |
| Snoozes por concluida | media de `snooze_count` | <1,0 | >1,5 = horarios default errados |
| Atividades por cliente fechado | done ÷ clientes do periodo | tendencia | explosao = esforco sem conversao; revisar ICP |
| Pushes/dia/pessoa | log do IAlex | ≤6 | teto batendo todo dia = matriz §6 mal calibrada |

Revisao: 1x/mes (junto do fechamento). 1º mes da F2 = baseline; ajustes de
regra so com 4 semanas de dado.

---

## 8. O que NAO fazer (anti-overengineering — 3 socios, produto early)

1. Recorrencia de atividades ("toda terca ligar pra X") — o engine recria pelo
   ESTADO real; recorrencia cega gera lixo.
2. Subtarefas / checklists / dependencias — atividade e 1 acao executavel.
3. Comentarios/mencoes/threads — os 3 conversam no WhatsApp; `details` basta.
4. Atribuicao multipla / co-dono — 1 atividade, 1 dono. Sempre.
5. Calendario visual drag-drop / sync Google Calendar bidirecional — o poll do
   Outlook ja alimenta reunioes.
6. Notificacoes in-app (sininho) — a Home E a notificacao.
7. Score/priorizacao ML de atividades — prio 1-3 + due resolve.
8. Snapshot/tabela de historico de metas — eventos timestamped + trigger
   resolvem (§4.3). Nao criar `goal_snapshots`.
9. Workflow de aprovacao de metas — admin define; a conversa acontece na sala.
10. Metas por segmento/cidade/produto — 7 metricas × 4 linhas ja e o maximo.
11. Gamificacao alem do 🏆 pontual — ranking permanente entre 3 socios corroi.
12. Reatribuicao automatica (ferias/sobrecarga) — visibilidade sim, automacao
    nao; pessoas decidem sobre pessoas.
13. SLA configuravel por tipo/usuario — 4h uteis, fixo no labels.py.
14. App/PWA dedicado — IAlex no WhatsApp e o mobile.
15. Estados extras (in_progress, blocked, review) — open/done/snoozed/dismissed
    cobre 100% do uso real de 3 pessoas.

---

## 9. DDL adicional (somente o que falta, justificado)

```sql
-- activities (alem dos campos do blueprint §7)
ALTER TABLE activities ADD COLUMN resolution VARCHAR(30);
  -- 'manual' | 'auto_trabalho_detectado' | 'auto_gatilho_morto' | 'expirada' | 'lead_transferido'
  -- Sem isso, as metricas §7 e a auditoria "por que sumiu da minha agenda?" sao
  -- indecidiveis. completed_by='system' nao distingue "trabalho feito" de
  -- "gatilho morto" — e essa distincao separa agenda confiavel de agenda magica.

ALTER TABLE activities ADD COLUMN snooze_count SMALLINT NOT NULL DEFAULT 0;
  -- O limite de 3 adiamentos (§1.5) precisa de contador.

-- goals (alem de username/metric/period_type/period_start/target + UNIQUE)
ALTER TABLE goals ADD COLUMN created_by VARCHAR(50);
ALTER TABLE goals ADD COLUMN created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE goals ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE goals ADD COLUMN revision_log JSONB NOT NULL DEFAULT '[]';
  -- cada item: {at, by, old_target, new_target, reason} | {by:'system', reason:'herdada'}
  -- Mudanca de meta e permitida mas nunca silenciosa; o rollover se declara.

-- trigger de eventos de etapa (O item mais importante deste bloco — §4.3)
-- ON UPDATE OF status/commercial_stage ON companies:
--   INSERT INTO interactions(company_id, type='stage_changed',
--                            metadata=jsonb{from, to, changed_by, valor})
-- Trigger (nao codigo) captura dashboard v1, v2, IAlex e HubSpot pull de uma
-- vez. Sem isto, "realizado ao vivo sem snapshot" e promessa falsa.
```

Nada mais: nenhuma tabela nova, nenhum status novo; `away:{username}` vai no
storage de configuracoes existente de Ajustes.

## 10. Criterios de aceitacao (amarra F1/F2)

1. Engine roda 2x seguidas → zero duplicatas (dedupe) **e** zero atividades com
   gatilho morto sobrevivem (varredor).
2. Responder um lead pelo Mensagens (ou registrar contato manual) → a atividade
   "Responder" some sozinha em ≤30min (ou no proximo load da Home) com
   `resolution='auto_trabalho_detectado'`.
3. Cancelar/remarcar reuniao → prep antiga dismissada, prep nova com due
   correto, outcome intacta.
4. 4º clique em ⏰ → vira "Dispensar com motivo".
5. Virada do mes sem acao do admin → metas herdadas + sinalizadas; mes anterior
   consultavel com numeros identicos aos do dia 30 (teste: mover um lead de
   etapa em julho NAO muda o fechamento de junho).
6. Nenhum vendedor recebe >6 pushes nao-resposta num dia de teste de carga.
