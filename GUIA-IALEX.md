# Guia Completo do IAlex — Agente de Vendas IAprendo

> Última atualização: 20/04/2026
> Para: Fernando Teixeira

---

## O que é o IAlex?

O IAlex é um **agente de vendas inteligente** que funciona via WhatsApp. Ele é seu CRO (Chief Revenue Officer) virtual — busca escolas, qualifica leads, gera emails, gera relatórios interativos, acompanha pipeline e muito mais. Tudo pelo WhatsApp, sem precisar abrir nenhum outro sistema.

**Ele tem acesso a:**
- Base do MEC com **212.386 escolas** de todo o Brasil
- **185k escolas** com analytics ENEM 2024 (média, ranking, peer group)
- **Censo 2020-2025** (série histórica de matrículas, docentes, tech, infra)
- Banco CRM (Supabase) com suas escolas importadas
- Envio de emails via Brevo
- HubSpot CRM (sincronização bidirecional)
- **100+ ferramentas** de vendas em 12 categorias

---

## Novidades 2026-04

🎯 **OPR Interativo** — 1 link por escola com seletor de benchmark (Estadual/Municipal/Federal/Privada). Radar, cards e insights atualizam sem recarregar.

⭐ **Skills Aprendidas** — Diga "padroniza isso" após uma resposta aprovada. IAlex salva como modelo reutilizável.

🔥 **Urgency Score F2** — Score unificado 0-100 (engagement + ML + intent + ENEM). Alertas automáticos para tier CRITICAL.

🩺 **Auto-healing** — Sistema se corrige sozinho (restart Baileys, notifica fila parada, etc.) a cada 30 min.

🧠 **Intent Detection com LLM** — Análise semântica de respostas (não só keywords).

🛡️ **Modos de Autonomia** — Manual / Semi-Auto / Full-Auto com guardrails. Em Manual, zero alertas proativos.

📊 **Comparar Escolas** — "Compara Anchieta com Militar" → relatório lado a lado.

---

## Arquitetura — Como funciona por baixo

```
Você (WhatsApp)
    ↓ mensagem
Evolution API (Docker, porta 8080) — v2.3.7 com Redis cache
    ↓ webhook HTTP
Webhook Server (Python/Flask, porta 5001)
    ↓ processa
Brain (GPT-4.1-mini + 100+ ferramentas)
    ↓ consulta
Supabase (banco CRM) + school_analytics (ENEM 185k) + school_censo_yearly (Censo 2020-2025)
    ↓ resposta via Evolution API
Você (WhatsApp)
```

**Serviços que precisam estar rodando:**
1. **Docker Desktop** (Windows) — daemon dos containers
2. **Evolution API** (container `evolution_api`, porta 8080) — bridge WhatsApp via Baileys
3. **Postgres** (container `evolution_postgres`) — persistência da sessão Baileys
4. **Redis** (container `evolution_redis`) — cache de chaves criptográficas
5. **IAlex webhook** (Python local, porta 5001) — processa mensagens e responde

**Guard de instância única**: o `start_ialex.py` verifica se a porta 5001 já está em uso antes de iniciar — impede duplicação que causaria mensagens repetidas.

---

## 1. PM2 — Gerenciador de Processos

### O que é?
PM2 é um gerenciador de processos para Node.js/Python. Ele mantém o IAlex rodando **permanentemente em background** — se cair, reinicia sozinho. Se o computador reiniciar, o IAlex volta automaticamente.

### Sem PM2 (como funciona hoje)
Você precisa abrir 2 terminais e deixá-los abertos:
```bash
# Terminal 1 — Bridge
cd whatsapp-bridge
node index.js

# Terminal 2 — Webhook
cd agente-de-vendas
venv/Scripts/python.exe agent/webhook_server.py
```
**Problema:** Se fechar o terminal, o IAlex para.

### Com PM2 (como vai funcionar)

#### Instalar PM2 (uma vez só):
```bash
npm install -g pm2
```

#### Iniciar o IAlex:
```bash
cd agente-de-vendas
pm2 start ecosystem.config.js
```
Isso inicia os 2 processos. Você pode fechar o terminal que eles continuam rodando.

#### Comandos úteis do PM2:

| Comando | O que faz |
|---------|-----------|
| `pm2 status` | Ver se os processos estão rodando |
| `pm2 logs` | Ver logs em tempo real (Ctrl+C para sair) |
| `pm2 logs ialex-webhook` | Ver logs só do webhook |
| `pm2 logs ialex-bridge` | Ver logs só do bridge |
| `pm2 restart all` | Reiniciar tudo |
| `pm2 restart ialex-webhook` | Reiniciar só o webhook |
| `pm2 stop all` | **Parar tudo** (IAlex fica offline) |
| `pm2 stop ialex-webhook` | Parar só o webhook |
| `pm2 start all` | Iniciar tudo de novo |
| `pm2 delete all` | Remover os processos do PM2 |

#### Fazer sobreviver a reinicializações do Windows:
```bash
pm2 save          # Salva o estado atual
pm2 startup       # Cria serviço do Windows (siga as instruções que aparecem)
```

#### Desativar completamente o PM2:
```bash
pm2 stop all      # Para todos os processos
pm2 delete all    # Remove do PM2
pm2 unstartup     # Remove do boot do Windows
```

#### Arquivo de configuração:
O arquivo `ecosystem.config.js` na raiz do projeto define os 2 processos. Você não precisa editar, mas se quiser mudar algo, ele está lá.

---

## 2. Scheduler — Briefings Automáticos

### O que é?
O Scheduler envia mensagens **proativas** para você no WhatsApp, sem você precisar pedir. Funciona como um assistente que te lembra das coisas.

### Quando ele manda mensagem?

| Horário | O que envia |
|---------|-------------|
| 8h da manhã | **Briefing matinal** — emails pendentes de aprovação, follow-ups vencidos, stats do dia |
| 12h | **Check do meio-dia** — lembrete se tem aprovações pendentes |
| 17h | **Resumo do dia** — quantos emails foram enviados, respostas recebidas |
| Sexta 17:30 | **Relatório semanal** — stats da semana, tendências, top oportunidades |
| A cada 15min | **Alerta de resposta** — se alguma escola respondeu um email, você recebe alerta IMEDIATO |

### Como ativar?
O scheduler é ativado automaticamente quando o webhook inicia. Se você usa PM2, ele já está ativo.

### Como desativar?
Não tem como desativar pelo WhatsApp. Para desativar, seria necessário editar o código em `agent/webhook_server.py` e remover a linha `_start_scheduler()`.

### Notas:
- O scheduler só funciona enquanto o webhook estiver rodando
- Se o IAlex reiniciar, os horários resetam (não tem memória de "já mandei hoje")
- Os alertas de resposta a cada 15min são os mais úteis — você sabe na hora quando alguém responde

---

## 3. HubSpot — Sincronização CRM

### O que é?
O HubSpot é um CRM profissional onde você pode acompanhar todo o pipeline de vendas num painel bonito. O IAlex sincroniza escolas, contatos e deals entre o Supabase (banco interno) e o HubSpot.

### Como usar?
No WhatsApp, diga:
- *"Sincroniza com o HubSpot"* — sincroniza todas as escolas enriquecidas
- *"Sincroniza a escola La Salle com o HubSpot"* — sincroniza uma escola específica

### O que é sincronizado?
- **Escolas** → Companies no HubSpot (nome, endereço, telefone, score)
- **Contatos** → Contacts no HubSpot (nome, cargo, email, telefone)
- **Emails enviados** → Notas no Deal (log de atividades)
- **Status do pipeline** → Deal stage (Prospectado → Contatado → Respondeu → Reunião)

### Requisito:
Já está configurado no `.env` com `HUBSPOT_API_KEY`. Se a chave expirar, atualize no arquivo `.env`.

---

## 4. Localização via WhatsApp

### O que é?
Quando você está na rua e quer saber que escolas tem perto de você, basta **compartilhar sua localização** no WhatsApp. O IAlex recebe suas coordenadas e automaticamente busca escolas num raio de 2km.

### Como usar?
1. No WhatsApp, toque no ícone de **anexo** (📎)
2. Selecione **Localização**
3. Toque em **Enviar sua localização atual**
4. IAlex responde com as escolas próximas

### O que ele retorna?
- Nome de cada escola perto de você
- Distância em km
- Endereço, telefone, tipo, porte
- Se a escola já está no seu banco CRM ou não

### Notas:
- O raio padrão é 2km, mas você pode pedir diferente: *"Escolas num raio de 5km de onde estou"*
- Nem todas as escolas do MEC têm coordenadas (~60% têm)
- Funciona em qualquer lugar do Brasil

---

## 5. Campanhas Segmentadas

### O que é?
Campanhas permitem **agrupar suas ações de prospecção**. Em vez de enviar emails avulsos, você cria uma campanha (ex: "Privadas POA Abril") e todos os envios ficam vinculados a ela, com métricas separadas.

### Como usar?

**Criar campanha:**
- *"Cria uma campanha chamada Privadas POA Abril para prospectar escolas privadas de Porto Alegre"*

**Listar campanhas:**
- *"Lista minhas campanhas"*
- *"Campanhas ativas"*

### Status de uma campanha:
- **draft** — criada, ainda não iniciada
- **active** — em andamento
- **paused** — pausada temporariamente
- **completed** — finalizada

### Notas:
- A tabela de campanhas já existia no banco, agora você pode gerenciar pelo WhatsApp
- Futuramente: vincular emails da fila de aprovação a uma campanha específica

---

## 6. Templates de Email

### O que é?
Templates são modelos de email pré-prontos com variáveis que são preenchidas automaticamente. Em vez de pedir para a IA gerar cada email do zero (que custa créditos), você pode usar templates (custo zero).

### Variáveis disponíveis:
| Variável | O que vira |
|----------|-----------|
| `{contact_name}` | Nome completo do contato |
| `{contact_first_name}` | Primeiro nome |
| `{contact_role}` | Cargo (Diretora, Coordenador) |
| `{school_name}` | Nome da escola |
| `{city}` | Cidade |
| `{state}` | Estado (RS, SP, etc.) |
| `{education_levels}` | Níveis de ensino |
| `{sender_name}` | Seu nome (Fernando) |
| `{meeting_link}` | Link do HubSpot para agendar reunião |

### Como usar?

**Listar templates:**
- *"Lista templates de email"*

**Criar template:**
- *"Cria um template chamado pos-visita com assunto 'Foi um prazer, {contact_first_name}!' e corpo 'Olá {contact_first_name}, obrigado pela conversa sobre o {school_name}...'"*

### Template padrão:
Já existe 1 template "Primeiro Contato - Padrão" que é usado quando você roda o pipeline no modo template.

---

## 7. WhatsApp para Escolas

### O que é?
Além de enviar emails, agora o IAlex pode enviar **mensagens WhatsApp diretamente para as escolas**. A mensagem passa pela fila de aprovação — você sempre revisa antes de enviar.

### Como usar?
- *"Manda um WhatsApp pro Colégio La Salle dizendo que gostaríamos de apresentar a plataforma IAprendo"*

### Fluxo:
1. IAlex encontra a escola no banco e pega o telefone
2. Cria a mensagem e coloca na fila de aprovação com canal "whatsapp"
3. Você aprova: *"Aprova a mensagem X"*
4. Quando aprovada, pode ser enviada pelo WhatsApp do IAlex

### Requisitos:
- A escola precisa ter telefone cadastrado no banco
- O número precisa ser um celular com WhatsApp (números fixos não funcionam)

### Nota:
- Use com moderação — WhatsApp é mais invasivo que email
- Ideal para follow-ups quentes (escola que já demonstrou interesse)

---

## 8. Transcrição de Áudio

### O que é?
Você pode **gravar um áudio** no WhatsApp e o IAlex transcreve e processa como se fosse texto. Usa o modelo **Whisper** da OpenAI.

### Como funciona?
1. Grave um áudio no WhatsApp dizendo, por exemplo: *"Quantas escolas privadas temos em Porto Alegre?"*
2. O IAlex recebe o áudio
3. Envia para a API Whisper da OpenAI para transcrever
4. Processa o texto transcrito normalmente
5. Responde com os dados

### Custos:
O Whisper usa a **mesma API key da OpenAI** que você já tem configurada. O custo é:
- **$0.006 por minuto de áudio** (menos de 1 centavo por minuto)
- Um áudio de 10 segundos custa ~$0.001 (praticamente nada)
- É parte da mesma conta/API key do GPT-4.1-mini

### Quando usar:
- Quando está dirigindo e não pode digitar
- Para ditar notas de reunião: *"Registra que visitei o La Salle hoje, conversei com o diretor, ele demonstrou interesse e quer uma demo semana que vem"*
- Para comandos rápidos em campo

### Limitações:
- Funciona melhor com áudios de até 2 minutos
- Precisa falar claramente em português
- Se a transcrição falhar, o IAlex pede para digitar

---

## 9. Dashboard (Streamlit)

### O que é?
O Dashboard é uma interface web com 10 páginas para gerenciar tudo visualmente. Funciona no navegador do computador ou celular.

### Páginas:

| # | Página | O que faz |
|---|--------|-----------|
| 1 | Pipeline | Executar qualificação, enriquecimento e geração de emails |
| 2 | CRM | Kanban visual do pipeline (arrastar escolas entre etapas) |
| 3 | Escolas | Tabela com todas as escolas, edição inline |
| 4 | Mapa | Mapa interativo com localização das escolas |
| 5 | Contatos | Power Map — decisores por hierarquia |
| 6 | Fila de Aprovação | **CRÍTICO** — revisar, editar e aprovar emails antes de enviar |
| 7 | Follow-ups | Sequências de follow-up e tracking de emails |
| 8 | Templates | Criar/editar templates de email |
| 9 | Importar Escolas | Importar do CSV do MEC com filtros |
| 10 | Guia de Uso | Documentação e FAQ |

### Como rodar localmente:
```bash
cd agente-de-vendas
venv\Scripts\python.exe -m streamlit run dashboard/app.py
```
Abre no navegador em `http://localhost:8501`

### Como publicar online (Streamlit Cloud):

**Passo 1 — Subir para GitHub:**
Se o projeto ainda não está no GitHub:
```bash
cd agente-de-vendas
git init
git add .
git commit -m "IAlex sales agent"
git remote add origin https://github.com/SEU-USUARIO/iaprendo-sales.git
git push -u origin main
```

**Passo 2 — Criar conta no Streamlit Cloud:**
1. Acesse https://share.streamlit.io
2. Faça login com sua conta GitHub
3. Clique em "New app"

**Passo 3 — Configurar o app:**
- Repository: `SEU-USUARIO/iaprendo-sales`
- Branch: `main`
- Main file path: `dashboard/app.py`
- Clique em "Advanced settings"

**Passo 4 — Adicionar secrets (IMPORTANTE):**
Na aba "Secrets" do Streamlit Cloud, cole:
```toml
SUPABASE_URL = "https://vgmvpghwkeirnjdbjcwl.supabase.co"
SUPABASE_KEY = "sua-chave-aqui"
ANTHROPIC_API_KEY = "sua-chave-aqui"
HUBSPOT_API_KEY = "sua-chave-aqui"
```
(Copie os valores do seu arquivo `.env`)

**Passo 5 — Deploy:**
Clique em "Deploy". Em 2-3 minutos seu dashboard estará online com uma URL tipo:
`https://iaprendo-sales.streamlit.app`

**Passo 6 — Proteger com senha (opcional):**
No secrets, adicione:
```toml
[passwords]
fernando = "sua-senha-aqui"
```
E no `dashboard/app.py`, adicione no início:
```python
if not st.experimental_user.is_logged_in:
    st.stop()
```

### Notas:
- Streamlit Community Cloud é **gratuito** para 1 app
- O app "dorme" após 7 dias sem uso e acorda quando acessar
- Dados são sempre do Supabase (tempo real)
- Funciona no celular (responsivo)

---

## 10. Score Preditivo

### O que é?
O score preditivo analisa todas as suas escolas e **prevê quais têm mais chance de fechar negócio**, baseado em dados reais de engajamento.

### Como funciona?
Combina vários fatores:
- **Score de qualificação** (IA avaliou o fit da escola para o IAprendo)
- **Número de contatos** encontrados (+5 por contato, max +20)
- **Interações** feitas (emails, calls, etc.) (+3 por interação, max +15)
- **Escola privada** (+10, têm mais poder de compra)
- **Porte grande** (1000+ alunos = +15, 500+ = +10)
- **Tem telefone** (+5, facilita contato)

O resultado é um score de 0 a 100 — quanto maior, melhor.

### Como usar?
- *"Quais escolas têm mais chance de fechar?"*
- *"Me mostra o top 5 oportunidades"*
- *"Score preditivo das minhas escolas"*

### Notas:
- Atualmente usa um modelo heurístico (regras fixas)
- À medida que mais dados forem gerados (mais emails, mais respostas, mais reuniões), o modelo pode evoluir para machine learning real
- Os scores são calculados em tempo real a cada consulta

---

## Resumo de Todas as 34 Ferramentas do IAlex

### Busca de Escolas (5 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| consultar_escolas | Buscar no banco CRM (com fallback MEC) | *"Busca o colégio Anchieta"* |
| buscar_escola_brasil | Filtros avançados na base MEC | *"Escolas privadas em Curitiba com ensino médio"* |
| escolas_proximas | Buscar por localização | Compartilhar pin GPS |
| importar_escola | Importar escola do MEC pro CRM | *"Importa essa escola pro banco"* |
| detalhes_escola | Ver tudo de uma escola | *"Detalhes do La Salle"* |

### Contatos (3 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| buscar_contatos | Ver contatos já cadastrados | *"Contatos do Anchieta"* |
| enriquecer_contatos | Buscar novos via APIs | *"Busca contatos do La Salle"* |
| atualizar_escola | Atualizar dados da escola | *"Atualiza telefone do Anchieta"* |

### Pipeline (3 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| rodar_pipeline | Executar etapas do pipeline | *"Qualifica as escolas raw"* |
| operacao_lote | Ações em massa | *"Importa as 5 maiores privadas de Curitiba"* |
| atualizar_scores | Recalcular scores | *"Atualiza os scores"* |

### Emails (7 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| gerar_email | Criar email personalizado | *"Gera email pro La Salle"* |
| fila_aprovacao | Ver emails pendentes | *"O que tem na fila?"* |
| aprovar_mensagem | Aprovar email | *"Aprova"* |
| rejeitar_mensagem | Rejeitar email | *"Rejeita, muito longo"* |
| editar_e_aprovar | Editar antes de aprovar | *"Muda o assunto e aprova"* |
| enviar_aprovados | Disparar emails aprovados | *"Envia os emails aprovados"* |
| gerar_followups | Criar follow-ups automáticos | *"Tem follow-ups pendentes?"* |

### WhatsApp para Escolas (1 tool)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| enviar_whatsapp_escola | Mensagem WhatsApp pra escola | *"Manda WhatsApp pro La Salle"* |

### Analytics (5 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| tracking_emails | Resultados de emails | *"Taxa de abertura dos emails"* |
| relatorio_pipeline | Relatório completo | *"Como está meu pipeline?"* |
| funil_vendas | Funil de conversão | *"Me mostra o funil"* |
| melhor_horario | Horário ideal de envio | *"Qual melhor horário pra enviar?"* |
| estatisticas_gerais | Stats do CRM | *"Quantas escolas temos?"* |

### Integrações (2 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| sincronizar_hubspot | Sync com HubSpot | *"Sincroniza com HubSpot"* |
| score_preditivo | Prever fechamento | *"Quais escolas vão fechar?"* |

### Gestão (5 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| registrar_reuniao | Registrar visita/call | *"Registra visita no La Salle"* |
| consultar_interacoes | Histórico de interações | *"Histórico do Anchieta"* |
| listar_campanhas | Ver campanhas | *"Campanhas ativas"* |
| criar_campanha | Nova campanha | *"Cria campanha Privadas POA"* |
| listar_templates | Ver templates de email | *"Lista templates"* |

### Utilitários (3 tools)
| Ferramenta | Quando usar | Exemplo |
|-----------|-------------|---------|
| criar_template | Novo template de email | *"Cria template pós-visita"* |
| uso_apis | Créditos de APIs | *"Quantos créditos Apollo restam?"* |
| consulta_livre | Query customizada no banco | *"Quantas escolas em cada cidade?"* |

---

## Custos Mensais Estimados

| Serviço | Custo | Uso |
|---------|-------|-----|
| OpenAI GPT-4.1-mini | ~R$ 5-15/mês | Conversas WhatsApp + qualificação |
| OpenAI Whisper | ~R$ 1-3/mês | Transcrição de áudios |
| Brevo (email) | Grátis | Até 300 emails/dia |
| Supabase | Grátis | Banco de dados (plano free) |
| Apollo | Grátis | 60 buscas/mês |
| Hunter | Grátis | 25 buscas/mês |
| Snov | Grátis | 50 buscas/mês |
| HubSpot | Grátis | CRM (plano free) |
| Streamlit Cloud | Grátis | Dashboard (1 app) |
| PM2 | Grátis | Gerenciador local |
| **TOTAL** | **~R$ 6-18/mês** | |

---

## Fluxo Completo de Vendas (passo a passo)

```
1. BUSCAR → "Busca escolas privadas em Caxias do Sul"
      ↓
2. IMPORTAR → "Importa o La Salle pro banco"
      ↓
3. QUALIFICAR → "Qualifica" (IA dá score 0-100)
      ↓
4. ENRIQUECER → "Busca contatos do La Salle" (Apollo/Hunter/Snov)
      ↓
5. EMAIL → "Gera email pro La Salle" (IA personaliza)
      ↓
6. APROVAR → "Aprova o email" (você revisa)
      ↓
7. ENVIAR → "Envia os aprovados" (Brevo dispara)
      ↓
8. TRACKING → "Taxa de abertura?" (opens/clicks/replies)
      ↓
9. FOLLOW-UP → "Gera follow-ups" (dia 3, 7, 14)
      ↓
10. REUNIÃO → "Registra visita no La Salle" (após visitar)
      ↓
11. ANÁLISE → "Como está meu funil?" (gargalos e oportunidades)
      ↓
12. REPETIR 🔄
```

---

## Troubleshooting — Problemas Comuns

**IAlex não responde no WhatsApp:**
1. Verifique se os processos estão rodando: `pm2 status`
2. Se não estiver: `pm2 start ecosystem.config.js`
3. Verifique a conexão WhatsApp: acesse `http://localhost:8090/status`
4. Se desconectou: acesse `http://localhost:8090/pair` e escaneie o QR

**IAlex responde mas não encontra escolas:**
- Verifique se a base MEC está no lugar: `data/raw/escolas_brasil.csv`

**Emails não estão sendo enviados:**
- Verifique se tem emails aprovados: *"O que tem na fila?"*
- Depois envie: *"Envia os aprovados"*
- Verifique a API key do Brevo no `.env`

**Áudio não transcreve:**
- Verifique se a API key do OpenAI está no `.env`
- Tente um áudio mais curto e claro
- Se falhar, o IAlex pedirá para digitar

**Dashboard não abre:**
- Rode: `venv\Scripts\python.exe -m streamlit run dashboard/app.py`
- Acesse: `http://localhost:8501`
