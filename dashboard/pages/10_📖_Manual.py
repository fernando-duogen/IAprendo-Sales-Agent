"""Pagina 10 - Manual Completo: guia de treinamento para novos membros.

12 abas cobrindo cada aspecto da plataforma IAprendo Sales Agent,
desde visao geral ate glossario tecnico.
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config,
    section_header,
    alert_banner,
    breadcrumb,
    COLORS,
)

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

# =============================================================================
# Header
# =============================================================================
breadcrumb(["IAprendo", "Manual"])
st.markdown("# Manual da Plataforma")
st.caption(
    "Guia completo para operar o IAprendo Sales Agent. "
    "Use as abas abaixo para navegar entre os topicos."
)

# =============================================================================
# 12 Tabs
# =============================================================================
(
    tab_visao, tab_fluxo, tab_passo, tab_crm,
    tab_pipeline, tab_comunicacao, tab_intel, tab_ialex,
    tab_config, tab_boas, tab_usecases, tab_glossario,
) = st.tabs([
    "Visao Geral",
    "Fluxograma",
    "Passo a Passo",
    "CRM (Escolas)",
    "Pipeline",
    "Comunicacao",
    "Inteligencia ENEM",
    "IAlex (Chat & WhatsApp)",
    "Configuracoes",
    "Boas Praticas",
    "Use Cases",
    "Glossario",
])


# #############################################################################
# TAB 1 — VISAO GERAL
# #############################################################################
with tab_visao:
    section_header("O que e o IAprendo Sales Agent", "info")

    st.markdown("""
O **IAprendo Sales Agent** e um sistema hibrido (IA + Humano) de prospeccao B2B
para a plataforma educacional IAprendo. Ele combina automacao inteligente com
supervisao humana obrigatoria para garantir qualidade e etica em cada interacao.

### Componentes Principais

| Componente | Descricao |
|---|---|
| **Dashboard Streamlit** | Interface web com 11 paginas para gestao completa |
| **Chat IAlex (navegador)** | Conversa com a IA dentro do dashboard (1a pagina do menu) |
| **IAlex (WhatsApp)** | Mesmo agente de IA, via WhatsApp — 85 ferramentas |
| **Supabase** | Banco de dados PostgreSQL com 7+ tabelas |
| **HubSpot CRM** | Sincronizacao bidirecional de contatos e deals |
| **Brevo / Gmail** | Envio de emails com tracking completo |
| **ENEM Analytics** | Dados de desempenho de 185 mil escolas |

> **2 jeitos de usar a IA**: pelo **💬 Chat IAlex** no navegador (1a pagina) OU pelo
> **WhatsApp**. Os dois usam o mesmo cerebro (mesmas 85 ferramentas). Acesso
> multi-usuario: Fernando, Lizianne e Felipe, cada um com seu login.
""")

    st.divider()
    section_header("Principios Fundamentais", "verified")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**1. Aprovacao Humana Obrigatoria**
> NENHUMA mensagem e enviada sem revisao e aprovacao manual.
> Este e o principio mais importante do sistema inteiro.

**2. Zero Hardcode**
> Todas as configuracoes vem de variaveis de ambiente (.env) ou do banco.
> Nenhum email, telefone ou URL e fixo no codigo.

**3. Codigo INEP como Chave Unica**
> Toda escola e identificada pelo seu codigo INEP (MEC).
> Isso evita duplicatas e garante rastreabilidade.
""")
    with col2:
        st.markdown("""
**4. Validation First**
> Dados sao validados antes de qualquer processamento.
> Garbage in, garbage out nao e aceitavel.

**5. Graceful Degradation**
> Se uma API falha, o sistema continua com fallbacks.
> Apollo falhou? Tenta Snov. Snov falhou? Tenta Hunter.

**6. Logging Estruturado**
> Toda acao e logada em JSON para auditoria.
> Nenhuma decisao da IA e uma caixa preta.
""")

    st.divider()
    section_header("Arquitetura em 5 Camadas", "layers")

    st.markdown("""
```
Camada 5 — Interface      : Dashboard Streamlit (11 paginas) + Chat IAlex web + IAlex WhatsApp
Camada 4 — Orquestracao    : Pipeline diario, Follow-ups automaticos, Scheduler
Camada 3 — Agentes IA      : Qualificador, Escritor, Enriquecedor, Buscador
Camada 2 — Integracoes     : HubSpot, Brevo, Apollo, Snov, Hunter, Google Maps
Camada 1 — Dados           : Supabase (PostgreSQL), CSV MEC, ENEM Analytics
```
""")

    st.divider()
    section_header("Numeros Atuais", "analytics")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Base MEC", "210k escolas")
    with c2:
        st.metric("CRM Ativo", "~88 escolas")
    with c3:
        st.metric("ENEM Analytics", "185k escolas")
    with c4:
        st.metric("Tools IAlex", "85 ferramentas")

    st.markdown("""
---
**Stack Tecnologico**

- **Backend**: Python 3.11+, Anthropic Claude API (Haiku 4.5 + Sonnet 4.5)
- **Database**: Supabase (PostgreSQL) com 7+ tabelas
- **Frontend**: Streamlit com tema Material Design customizado
- **Mapas**: PyDeck (Deck.gl) para visualizacao geografica
- **Emails**: Brevo (300/dia gratis) ou Gmail API (500/dia)
- **CRM**: HubSpot (free tier com sincronizacao bidirecional)
""")


# #############################################################################
# TAB 2 — FLUXOGRAMA
# #############################################################################
with tab_fluxo:
    section_header("Fluxo Completo do Pipeline", "account_tree")

    st.markdown("O diagrama abaixo mostra o caminho de uma escola desde o CSV do MEC ate a conversao em cliente.")

    flowchart_html = """
<div style="font-family: 'Inter', sans-serif; overflow-x: auto; padding: 20px 0;">

  <!-- Row 1: Data Sources -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#E3F2FD; border:2px solid #1976D2; border-radius:12px; padding:14px 20px; text-align:center; min-width:140px;">
      <div style="font-size:24px;">📄</div>
      <div style="font-weight:600; color:#1976D2; font-size:13px;">CSV MEC</div>
      <div style="font-size:11px; color:#757575;">210k escolas</div>
    </div>
    <div style="background:#E8F5E9; border:2px solid #2E7D32; border-radius:12px; padding:14px 20px; text-align:center; min-width:140px;">
      <div style="font-size:24px;">📊</div>
      <div style="font-weight:600; color:#2E7D32; font-size:13px;">ENEM 2024</div>
      <div style="font-size:11px; color:#757575;">185k escolas</div>
    </div>
    <div style="background:#FFF3E0; border:2px solid #E65100; border-radius:12px; padding:14px 20px; text-align:center; min-width:140px;">
      <div style="font-size:24px;">🏛️</div>
      <div style="font-weight:600; color:#E65100; font-size:13px;">Censo Historico</div>
      <div style="font-size:11px; color:#757575;">2020-2025</div>
    </div>
  </div>

  <!-- Arrow Down -->
  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 2: Import + Filter -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFFFFF; border:2px solid #1976D2; border-radius:12px; padding:14px 20px; text-align:center; min-width:260px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">1️⃣ Importar + Filtrar</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Municipio + UF + Nivel de Ensino + Tipo de Escola<br/>
        <span style="color:#1976D2; font-weight:500;">Resultado: ~88 escolas em Porto Alegre</span>
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 3: Qualify -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFFFFF; border:2px solid #7B1FA2; border-radius:12px; padding:14px 20px; text-align:center; min-width:260px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">2️⃣ Qualificar (IA)</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Claude Haiku analisa cada escola e atribui<br/>
        <strong>Score 0-100</strong> (Fit + Tech + Infra)<br/>
        <span style="color:#7B1FA2; font-weight:500;">Prioridades: P1 (&gt;70), P2 (50-70), P3 (&lt;50)</span>
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 4: Enrich + Find Contacts -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFFFFF; border:2px solid #00897B; border-radius:12px; padding:14px 20px; text-align:center; min-width:180px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">3️⃣ Enriquecer</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Apollo &rarr; Snov &rarr; Hunter<br/>
        <span style="color:#00897B; font-weight:500;">Dados web + redes sociais</span>
      </div>
    </div>
    <div style="background:#FFFFFF; border:2px solid #00897B; border-radius:12px; padding:14px 20px; text-align:center; min-width:180px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">4️⃣ Encontrar Decisores</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Diretor, Coordenador, Secretaria<br/>
        <span style="color:#00897B; font-weight:500;">Power Map hierarquico</span>
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 5: Write Messages -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFFFFF; border:2px solid #FF6D00; border-radius:12px; padding:14px 20px; text-align:center; min-width:260px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">5️⃣ Gerar Mensagens (IA)</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Claude Sonnet cria emails personalizados<br/>
        usando dados da escola + ENEM + contexto<br/>
        <span style="color:#FF6D00; font-weight:500;">NUNCA templates genericos</span>
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 6: APPROVAL (highlighted) -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFF9C4; border:3px solid #F57F17; border-radius:12px; padding:16px 24px; text-align:center; min-width:280px; box-shadow: 0 4px 12px rgba(245,127,23,0.2);">
      <div style="font-size:24px;">6️⃣ APROVACAO HUMANA</div>
      <div style="font-size:13px; color:#E65100; font-weight:600; margin-top:6px;">
        OBRIGATORIA — Nenhum email sai sem revisao<br/>
      </div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Aprovar / Editar+Aprovar / Reescrever / Rejeitar
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#9E9E9E; margin:4px 0;">&#9660;</div>

  <!-- Row 7: Send + Track -->
  <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;">
    <div style="background:#FFFFFF; border:2px solid #2E7D32; border-radius:12px; padding:14px 20px; text-align:center; min-width:180px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">7️⃣ Enviar</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Brevo ou Gmail API<br/>
        <span style="color:#2E7D32; font-weight:500;">Com tracking pixel</span>
      </div>
    </div>
    <div style="background:#FFFFFF; border:2px solid #2E7D32; border-radius:12px; padding:14px 20px; text-align:center; min-width:180px; box-shadow: 0 2px 6px rgba(0,0,0,0.08);">
      <div style="font-size:20px;">8️⃣ Tracking</div>
      <div style="font-size:12px; color:#757575; margin-top:4px;">
        Entregue &rarr; Aberto &rarr; Respondido<br/>
        <span style="color:#2E7D32; font-weight:500;">+ Sync HubSpot</span>
      </div>
    </div>
  </div>

  <div style="text-align:center; font-size:28px; color:#2E7D32; margin:8px 0;">&#9660;</div>

  <!-- Row 8: Conversion -->
  <div style="display:flex; justify-content:center; margin-bottom:8px;">
    <div style="background:#E8F5E9; border:2px solid #1B5E20; border-radius:12px; padding:16px 24px; text-align:center; min-width:200px;">
      <div style="font-size:24px;">🎉</div>
      <div style="font-weight:700; color:#1B5E20; font-size:14px;">CONVERSAO</div>
      <div style="font-size:12px; color:#757575;">Reuniao &rarr; Proposta &rarr; Cliente</div>
    </div>
  </div>
</div>
"""
    st.markdown(flowchart_html, unsafe_allow_html=True)

    st.divider()

    with st.expander("Legenda de Cores"):
        st.markdown("""
| Cor | Significado |
|---|---|
| **Azul** | Dados e importacao |
| **Roxo** | Qualificacao por IA |
| **Teal** | Enriquecimento e contatos |
| **Laranja** | Geracao de mensagens |
| **Amarelo** | Aprovacao humana (critico) |
| **Verde** | Envio, tracking e conversao |
""")


# #############################################################################
# TAB 3 — PASSO A PASSO
# #############################################################################
with tab_passo:
    section_header("Seu Primeiro Lead em 10 Minutos", "rocket_launch")

    alert_banner(
        "Atalho pra quem nao e tecnico: abra a 1a pagina do menu (💬 Chat IAlex) e "
        "digite o que voce quer em linguagem natural (ex: 'qualifica e gera email "
        "pras 5 escolas privadas de Porto Alegre com maior fit'). O IAlex faz o "
        "pipeline por voce, conversando. O passo a passo abaixo e o jeito manual.",
        "success",
    )

    alert_banner(
        "Este tutorial assume que o sistema ja esta configurado (banco, APIs, .env). "
        "Se ainda nao configurou, va em Configuracoes primeiro.",
        "info",
    )

    st.markdown("### Etapa 1: Importar Escolas (2 min)")
    st.markdown("""
1. Clique em **Importar** no menu lateral
2. O arquivo CSV do MEC ja esta configurado no sistema
3. Selecione os filtros:
   - **Municipio**: Porto Alegre
   - **UF**: RS
   - **Nivel**: Fundamental AF e/ou Medio
   - **Tipo**: Privada (para comecar)
4. Clique em **Importar**
5. Aguarde — o sistema importa e cria os registros no Supabase
""")
    if st.button("Ir para Importar", key="passo_importar"):
        st.switch_page("pages/1_📥_Importar.py")

    st.divider()

    st.markdown("### Etapa 2: Visualizar no CRM (1 min)")
    st.markdown("""
1. Va em **Escolas** no menu lateral
2. Voce vera a tabela com todas as escolas importadas
3. Use os filtros (status, porte, dependencia) para explorar
4. Clique em uma escola para ver o **card de detalhe** completo
5. Confira: nome, endereco, telefone, INEP, porte, etapas de ensino
""")
    if st.button("Ir para Escolas", key="passo_escolas"):
        st.switch_page("pages/2_🏫_Escolas.py")

    st.divider()

    st.markdown("### Etapa 3: Rodar Pipeline (3 min)")
    st.markdown("""
1. Va em **Pipeline** no menu lateral
2. Na aba **Execucao**:
   - Selecione 1-3 escolas na tabela (comece pequeno!)
   - Clique **Qualificar** — a IA analisa e atribui scores
   - Clique **Enriquecer** — busca dados adicionais na web
   - Clique **Encontrar Contatos** — localiza decisores
   - Clique **Gerar Emails** — cria mensagens personalizadas
3. Cada etapa atualiza o status da escola no CRM
""")
    if st.button("Ir para Pipeline", key="passo_pipeline"):
        st.switch_page("pages/5_📊_Pipeline.py")

    st.divider()

    st.markdown("### Etapa 4: Aprovar e Enviar (2 min)")
    st.markdown("""
1. Va em **Comunicacao** no menu lateral
2. Na aba **Aprovacao** voce vera os emails gerados
3. Para cada email:
   - **Leia** o conteudo com atencao
   - Escolha uma acao:
     - **Aprovar** — o email e enviado como esta
     - **Editar + Aprovar** — faca ajustes e depois aprove
     - **Reescrever** — peca a IA para gerar nova versao
     - **Rejeitar** — descarte este email
4. Emails aprovados vao para a fila de envio
""")
    if st.button("Ir para Comunicacao", key="passo_comunicacao"):
        st.switch_page("pages/6_✉️_Comunicacao.py")

    st.divider()

    st.markdown("### Etapa 5: Acompanhar Resultados (2 min)")
    st.markdown("""
1. Volte para **Comunicacao** > aba **Metricas**
   - Veja taxas de abertura, resposta, bounce
2. Va em **Analytics** para visao consolidada
   - ROI, funil de conversao, custo por lead
3. Use o **Mapa** para visualizacao geografica dos leads
4. Confira **Inteligencia ENEM** para priorizar proximos contatos
""")

    st.divider()
    alert_banner(
        "Dica: Use o IAlex pelo WhatsApp para fazer tudo isso por conversa natural! "
        "Veja a aba 'IAlex (WhatsApp)' neste manual.",
        "success",
    )


# #############################################################################
# TAB 4 — CRM (ESCOLAS)
# #############################################################################
with tab_crm:
    section_header("Paginas de Gestao: Escolas, Contatos, Mapa, Importar", "business")

    # --- Escolas ---
    st.markdown("## 1. Escolas (Pagina Principal do CRM)")
    st.markdown("""
A pagina **Escolas** e o coracao do CRM. Aqui voce gerencia todas as escolas
importadas e acompanha o progresso de cada uma.

### Funcionalidades

**Tabela Principal**
- Lista todas as escolas com colunas: Nome, INEP, Status, Porte, Score, Cidade
- **Filtros** no topo: Status, Porte, Dependencia, Tech, Fonte, Potencial ENEM e
  **UF + Cidade** (a Cidade filtra em cascata pela UF escolhida)
- **Busca** por nome ou INEP
- **📥 Exportar XLSX** das escolas filtradas (planilha com todos os campos + contatos)
- Clique em qualquer linha para abrir o detalhe

**Card de Detalhe**
Ao clicar em uma escola, voce ve um card completo com 7 abas:
- **Dados** — edicao inline (nome, endereco, **telefone fixo**, **📱 WhatsApp da
  escola** — campo separado do fixo, status, etc)
- **Performance ENEM** — radar 5 areas, ranking, gap, peer group, trajetoria
- **Contatos** — decisores encontrados (Power Map)
- **Mensagens** — emails na fila de aprovacao desta escola
- **Registrar Contato** *(novo)* — log de contato manual feito fora da plataforma
  (WhatsApp pessoal, ligacao, email pessoal). Form: canal + direcao + data +
  contato + observacao + checkboxes para avancar status / Kanban
- **Historico** — timeline de todas as interacoes registradas
- **Acoes** — gerar OPR (One Page Report), gerar graficos, comparar, etc.

**Aba Redes**
- Escolas agrupadas por **CNPJ da mantenedora**
- Identifica redes de escolas (ex: Marista, Sesi, La Salle)
- Permite tratar uma rede como uma conta unica
""")

    with st.expander("Status possiveis de uma escola"):
        st.markdown("""
| Status | Significado | Cor |
|---|---|---|
| **Novo** (raw) | Recem-importada, sem processamento | Cinza |
| **Qualificado** | IA analisou e atribuiu score | Azul |
| **Enriquecido** | Dados complementares coletados | Teal |
| **Contatado** | Email enviado para decisor | Laranja |
| **Respondeu** | Decisor respondeu ao email | Verde |
| **Convertido** | Virou reuniao/proposta/cliente | Verde escuro |
| **Descartado** | Removido do pipeline | Vermelho |
""")

    if st.button("Ir para Escolas", key="crm_escolas"):
        st.switch_page("pages/2_🏫_Escolas.py")

    st.divider()

    # --- Contatos ---
    st.markdown("## 2. Contatos (Power Map)")
    st.markdown("""
A pagina **Contatos** gerencia os decisores encontrados em cada escola.

### Power Map
O Power Map e uma visualizacao hierarquica dos contatos por escola:
- **Decisor Principal**: Diretor(a) ou Mantenedor(a)
- **Influenciador**: Coordenador(a) Pedagogico(a)
- **Operacional**: Secretaria, TI, Financeiro

### Funcionalidades
- **Busca** por nome, email ou escola
- **Filtros**: tipo de cargo, email (com/sem), **UF + Cidade** (cascata), agrupamento
- **📱 WhatsApp separado**: cada contato tem telefone fixo E celular/WhatsApp em
  colunas distintas (o WhatsApp aparece em verde). O envio por WhatsApp prioriza
  o celular; o fixo serve so pra ligacao
- **📥 Exportar XLSX**: baixa as escolas filtradas + TODOS os seus contatos numa
  planilha (3 abas: Escolas, Contatos, Info) — util pra trabalhar offline ou
  compartilhar listas
- **Enriquecimento**: buscar dados complementares (LinkedIn, email profissional)
- **Detalhes do contato**: historico de interacoes, emails enviados, respostas
""")

    if st.button("Ir para Contatos", key="crm_contatos"):
        st.switch_page("pages/3_👥_Contatos.py")

    st.divider()

    # --- Mapa ---
    st.markdown("## 3. Mapa (Visualizacao Geografica)")
    st.markdown("""
O **Mapa** mostra todas as escolas do CRM posicionadas geograficamente.

### Funcionalidades
- **Visualizacao 3D** com hexagonos (PyDeck/Deck.gl)
- **Cores** representam o status de cada escola
- **Filtros**: Status, porte, score minimo
- **Hover**: Mostra nome e dados basicos da escola
- **Clique**: Abre o detalhe da escola

### Geocodificacao
- Escolas sao geocodificadas automaticamente via Google Maps API
- Usa latitude/longitude do CSV do MEC (quando disponivel)
- Fallback: geocodifica pelo endereco completo
""")

    if st.button("Ir para Mapa", key="crm_mapa"):
        st.switch_page("pages/4_🗺️_Mapa.py")

    st.divider()

    # --- Importar ---
    st.markdown("## 4. Importar (CSV do MEC)")
    st.markdown("""
A pagina **Importar** permite adicionar escolas ao CRM a partir do CSV oficial do MEC.

### Filtros de Importacao

| Filtro | Descricao | Valor Padrao |
|---|---|---|
| **Restricao** | Apenas escolas em funcionamento sem restricao | Fixo |
| **Municipio** | Cidade das escolas | Porto Alegre |
| **UF** | Estado | RS |
| **Nivel de Ensino** | Fundamental AF e/ou Medio | Ambos |
| **Dependencia** | Publica, Privada, Municipal, Estadual, Federal | Configuravel |

### Processo
1. Selecione os filtros desejados
2. Clique em **Importar**
3. O sistema le o CSV, aplica filtros, e insere no Supabase
4. Escolas ja existentes (mesmo INEP) sao atualizadas, nao duplicadas
5. Resultado: escolas aparecem em Escolas com status "Novo"

### Cuidados
- O CSV completo tem **210 mil linhas** — sempre use filtros
- Para testes, use `--sample 100` no script de importacao
- O codigo INEP e a chave unica (evita duplicatas)
""")

    if st.button("Ir para Importar", key="crm_importar"):
        st.switch_page("pages/1_📥_Importar.py")


# #############################################################################
# TAB 5 — PIPELINE
# #############################################################################
with tab_pipeline:
    section_header("Pipeline de Prospeccao", "timeline")

    st.markdown("""
A pagina **Pipeline** e onde a prospeccao acontece de verdade. Ela tem **3 abas**
que cobrem todo o ciclo de vendas.
""")

    st.markdown("## Aba 1: Execucao")
    st.markdown("""
A aba de Execucao e o painel operacional do pipeline. Aqui voce seleciona
escolas e roda cada etapa manualmente.

### As 5 Etapas do Pipeline

| Etapa | O que faz | IA usada |
|---|---|---|
| **Qualificar** | Analisa escola e atribui score 0-100 | Claude Haiku 4.5 |
| **Enriquecer** | Busca dados na web (site, redes, noticias) | Apollo/Snov/Hunter |
| **Encontrar Contatos** | Localiza decisores (diretor, coordenador) | Apollo + Scraping |
| **Gerar Email** | Cria mensagem personalizada | Claude Sonnet 4.5 |
| **Enviar** | Coloca na fila de aprovacao | - |

### Como selecionar escolas
A tabela de selecao tem **filtros** e **checkbox** por linha:
- **Filtros**: UF, Cidade (cascata pela UF), Status, Score minimo, busca por nome
- **Checkbox** na 1a coluna: marque as escolas que quer processar
- **Contador** "X escolas selecionadas no total" — escolas marcadas fora do filtro
  atual permanecem selecionadas
- **Selecao rapida (presets)**: Top 10 por Score, Top 10 por Fit, Todas nao
  processadas, Todas privadas, Prontas p/ email, Limpar selecao
- **Busca avancada**: autocomplete por nome OU colar lista de nomes/INEPs

### Como rodar
1. Selecione escolas (checkbox ou preset)
2. Escolha o **Modo de mensagem** (so afeta a etapa "Gerar"):
   - **IA (personalizada)** — Claude escreve do zero
   - **Template (padrao)** — usa o template marcado como padrao
   - **Template (auto por alvo)** — escolhe automaticamente o melhor template
     conforme o contato (nominal/generico) e os dados da escola (matriculas/ENEM).
     Configure os templates em Comunicacao > Templates
3. Clique no botao da etapa (Qualificar / Enriquecer / Contatos / Gerar / Enviar)
4. O resultado aparece logo abaixo (caixa colorida + detalhe por etapa) e fica
   visivel ate voce limpar — sobrevive a recarregamentos da tela
5. Para enviar, va em **Comunicacao** > **Aprovacao**

### Opcoes extras
- **🔁 Forcar reprocessar**: por padrao, cada etapa pula escolas que ja passaram
  por ela (ex: enrich nao roda em escola ja enriquecida). Marque essa opcao pra
  RODAR DE NOVO numa escola que ja passou (ex: re-enriquecer pra atualizar dados)
- **📥 Exportar XLSX**: baixa as escolas selecionadas + contatos numa planilha
- **🗑️ Deletar selecionadas**: remove as escolas selecionadas do banco (escola +
  contatos + interacoes). Confirmacao em 2 cliques — **irreversivel**
- **🔄 Atualizar dados**: limpa o cache local (use apos rodar pipeline pra ver os
  contadores atualizados)

### Dicas
- Rode etapas em lote (varias escolas de uma vez); no Cloud, prefira lotes <= 100
- Cada etapa depende da anterior — mas os botoes rodam em **cascata** (clicar
  "Enriquecer" qualifica as raw e enriquece as qualified automaticamente)
- Se uma etapa falha, a escola fica no status anterior
""")

    st.divider()

    st.markdown("## Aba 2: Descoberta")
    st.markdown("""
A aba de Descoberta e para enriquecimento avancado e busca de sinais de compra.

### Enriquecimento em Lote
- Selecione varias escolas e enriqueca de uma vez
- O sistema usa cascata de APIs: Apollo > Snov > Hunter > Scraping
- Cada fonte complementa a anterior (nao substitui)

### Sinais de Compra
O sistema busca automaticamente sinais que indicam propensao a compra:
- **Site atualizado recentemente** — escola investindo em presenca digital
- **Vaga para professor de tecnologia** — interesse em inovacao
- **Projeto pedagogico mencionando tecnologia** — alinhamento com IAprendo
- **Participacao em eventos de educacao** — escola conectada
- **Certificacoes recentes** — escola investindo em qualidade
""")

    st.divider()

    st.markdown("## Aba 3: Pipeline Comercial")
    st.markdown("""
O Pipeline Comercial e um **kanban** que mostra as escolas nos estagios reais
de vendas, similar ao que se ve no HubSpot.

### Estagios do Kanban

| Estagio | Descricao |
|---|---|
| **Prospectado** | Escola identificada e qualificada |
| **Contatado** | Primeiro email enviado |
| **Engajado** | Escola abriu/respondeu email |
| **Reuniao** | Reuniao agendada ou realizada |
| **Proposta** | Proposta comercial enviada |
| **Negociacao** | Em negociacao de valores/termos |
| **Cliente** | Contrato assinado |
| **Perdido** | Oportunidade nao convertida |

### Funcionalidades
- Arraste cards entre colunas para atualizar status
- Cada card mostra: nome, score, ultimo contato, proxima acao
- Filtros: periodo, responsavel, valor
- Sincroniza bidirecionalmente com HubSpot
""")

    if st.button("Ir para Pipeline", key="pipeline_go"):
        st.switch_page("pages/5_📊_Pipeline.py")


# #############################################################################
# TAB 6 — COMUNICACAO
# #############################################################################
with tab_comunicacao:
    section_header("Central de Comunicacao", "mail")

    st.markdown("""
A pagina **Comunicacao** consolida tudo relacionado a emails, WhatsApp e mensagens.
Ela e dividida em **5 abas**: Aprovacao, Follow-ups, Templates, Metricas e WhatsApp.
""")

    st.markdown("## Aba 1: Aprovacao")
    st.markdown("""
Esta e a aba mais importante do sistema. **NENHUM email sai sem passar por aqui.**

### Fila de Aprovacao
- Lista todos os emails pendentes de revisao
- Cada email mostra: destinatario, assunto, preview do corpo
- Angulo de abordagem usado pela IA

### Acoes Disponiveis

| Acao | Descricao |
|---|---|
| **Aprovar** | Envia o email exatamente como esta |
| **Editar + Aprovar** | Permite ajustar o texto antes de enviar |
| **Reescrever** | Pede a IA para gerar nova versao com novo angulo |
| **Rejeitar** | Descarta este email (escola volta ao status anterior) |

### Boas Praticas
- Leia SEMPRE o email completo antes de aprovar
- Verifique se o nome do decisor esta correto
- Confirme que os dados da escola estao atualizados
- Se algo parecer generico demais, peca para reescrever
""")

    st.divider()

    st.markdown("## Aba 2: Follow-ups")
    st.markdown("""
Gerencia os follow-ups automaticos para emails ja enviados.

### Logica de Follow-ups
- **Follow-up 1**: 3 dias apos o envio (se nao abriu)
- **Follow-up 2**: 7 dias apos o envio (se abriu mas nao respondeu)
- **Follow-up 3**: 14 dias apos o envio (ultimo contato)

### Status de Follow-up
- **Pendente**: Agendado mas ainda nao chegou a data
- **Pronto**: Data chegou, aguardando aprovacao
- **Enviado**: Follow-up ja foi enviado
- **Cancelado**: Escola respondeu (follow-up desnecessario)

### Acoes
- Aprovar follow-ups individualmente ou em lote
- Editar texto do follow-up antes de enviar
- Cancelar follow-ups para escolas que ja responderam
""")

    st.divider()

    st.markdown("## Aba 3: Templates")
    st.markdown("""
Gerencia templates de email reutilizaveis, com **selecao automatica por alvo**.

### Selecao automatica por alvo (matriz 2x4)
Ao gerar emails no modo **"Template (auto por alvo)"** (no Pipeline) ou pedindo
"template automatico" no chat, o sistema escolhe sozinho o melhor template
conforme 2 dimensoes:

- **Publico**: pessoa nominal (diretor "Maria") vs endereco generico (secretaria@)
- **Dados da escola**: Matriculas (Censo) + ENEM / so Matriculas / so ENEM / Nenhum

Sao **8 combinacoes** possiveis. O ideal e sempre o template **nominal + ambos os
dados** (mais valor); se a escola nao tiver esses dados, o sistema degrada pro
melhor disponivel (nunca cita ENEM/matriculas que a escola nao tem).

| # | Publico | Dados | Prioridade |
|---|---|---|---|
| 1 | Nominal | Matriculas+ENEM | ⭐ ideal |
| 2 | Nominal | So Matriculas | alta |
| 3 | Nominal | So ENEM | alta |
| 4 | Nominal | Nenhum | media |
| 5 | Generico | Matriculas+ENEM | media |
| 6 | Generico | So Matriculas | baixa |
| 7 | Generico | So ENEM | baixa |
| 8 | Generico | Nenhum | fallback universal |

**Como configurar**: ao criar/editar um template, preencha os 2 campos novos
(**Publico-alvo** + **Dados que usa**). A **Matriz de cobertura** (grid ✅/⬜ logo
abaixo do form) mostra quais combos ja tem template. Comece pelo ⭐ (#1) e pelo
fallback (#8); o resto pode vir depois.

### Anexos PDF
Cada usuario cadastra PDFs (ex: apresentacao institucional) que vao
**automaticamente** anexados nos emails que ele enviar (sticky). Da pra
sobrescrever por mensagem na tela de Aprovacao.

### Nome do remetente (email_sender_name)
O nome que aparece no "De:" do email e configuravel por usuario — ex:
`Fernando Teixeira | DUOGEN`, `Lizianne P. K. Nienaber | DUOGEN`. Definido no
perfil de cada usuario (config multi-user).

### Tipos de Template
- **Primeiro contato**: Email inicial de apresentacao
- **Follow-up**: Lembrete apos primeiro contato
- **Proposta**: Email com proposta comercial
- **Evento**: Convite para webinar/demo
- **Custom**: Templates personalizados

### Variaveis Disponiveis
Templates usam variaveis que sao substituidas automaticamente:

| Variavel | Descricao |
|---|---|
| `{escola_nome}` | Nome da escola |
| `{contato_nome}` | Nome do decisor |
| `{contato_cargo}` | Cargo do decisor |
| `{cidade}` | Cidade da escola |
| `{porte}` | Porte (pequena, media, grande) |
| `{score}` | Score de qualificacao |
| `{contact_first_name}` | Primeiro nome do contato (saudacao pessoal) |
| `{sender_name}` | Nome do remetente ativo |
| `{meeting_link}` | Link de agendamento (HubSpot) |
| `{chart_radar}` | Grafico ENEM 5 areas (inserido inline no email) |
| `{chart_gap}` | Grafico gap vs escolas similares |
| `{chart_trend}` | Grafico de evolucao de matriculas |
| `{report_link}` | Link do One Page Report (OPR) da escola |

**Importante**: no modo IA, a IA usa templates como base mas SEMPRE personaliza.
No modo Template, as variaveis sao substituidas e o email vai como esta (mas
ainda passa pela aprovacao humana). Templates que usam `{chart_*}`/`{report_link}`
so devem ter Dados = Matriculas/ENEM (senao o grafico fica vazio).
""")

    st.divider()

    st.markdown("## Aba 4: Metricas")
    st.markdown("""
Acompanhe o desempenho das suas campanhas de email.

### Metricas Principais

| Metrica | O que mede | Meta |
|---|---|---|
| **Taxa de Entrega** | Emails que chegaram ao inbox | > 95% |
| **Taxa de Abertura** | Emails que foram abertos | > 30% |
| **Taxa de Resposta** | Emails que receberam resposta | > 10% |
| **Taxa de Bounce** | Emails que voltaram | < 5% |
| **Taxa de Conversao** | Respostas que viraram reuniao | > 20% |

### Graficos
- Evolucao temporal das metricas
- Comparacao entre campanhas
- Heatmap de melhor horario de envio
- Performance por angulo de abordagem
""")

    st.divider()

    st.markdown("## Aba 5: WhatsApp")
    st.markdown("""
Gerencia tudo relacionado a comunicacao via WhatsApp.

### Fila WhatsApp
- Mensagens enviadas pelo IAlex via WhatsApp passam pela mesma fila de aprovacao
- Filtro automatico por canal `whatsapp` — mostra apenas mensagens desse canal
- KPIs dedicados: pendentes, aprovados, enviados via WhatsApp

### Templates WhatsApp
- **3 templates padrao** (apresentacao, agendamento, mensagem curta)
- **Templates personalizados**: crie e salve templates com variaveis `{contact_name}` e `{company_name}`
- Preview com dados de exemplo para visualizar antes de usar

### Numeros Descobertos
- Visao geral de cobertura: quantos contatos tem telefone vs quantos faltam
- Percentual de cobertura
- Tabela com todos os contatos que tem telefone (nome, telefone, escola)
- Para descobrir novos numeros, use o **Pipeline > Descoberta** ou peca ao IAlex

### Dicas
- O IAlex pode enviar WhatsApp direto via comando: "mande WhatsApp para a diretora da escola X"
- Mensagens WhatsApp sao mais informais — use os templates curtos
- Ideal para follow-ups rapidos apos email sem resposta
""")

    if st.button("Ir para Comunicacao", key="comunicacao_go"):
        st.switch_page("pages/6_✉️_Comunicacao.py")


# #############################################################################
# TAB 7 — INTELIGENCIA ENEM
# #############################################################################
with tab_intel:
    section_header("Inteligencia ENEM", "school")

    st.markdown("""
A pagina **Inteligencia** usa dados do ENEM 2024 para identificar as melhores
oportunidades de venda. Ela combina desempenho academico, contexto socioeconomico
e comparacao com peer groups.
""")

    st.markdown("## Conceitos Fundamentais")

    with st.expander("O que e P1, P2, P3?"):
        st.markdown("""
O sistema classifica escolas em 3 niveis de prioridade baseado no **gap vs peer group**:

| Prioridade | Gap vs Peer | Descricao | Acao |
|---|---|---|---|
| **P1** (Alta) | Negativo grande | Escola abaixo da media do peer group | Abordagem urgente — precisa de ajuda |
| **P2** (Media) | Proximo de zero | Escola na media do peer group | Abordagem de diferenciacao |
| **P3** (Baixa) | Positivo grande | Escola acima da media do peer group | Abordagem de excelencia |

**Por que P1 e prioridade?**
Uma escola que esta significativamente abaixo das similares tem mais dor
(pain point) e maior propensao a investir em solucoes educacionais.
""")

    with st.expander("O que e Peer Group?"):
        st.markdown("""
O **Peer Group** (grupo de pares) agrupa escolas com caracteristicas similares:
- Mesma **dependencia administrativa** (publica/privada)
- Mesmo **porte** (numero de alunos)
- Mesma **regiao** (estado ou municipio)
- Mesmo **nivel socioeconomico** (INSE)

A comparacao com o peer group e mais justa do que comparar com a media geral,
porque escolas em contextos diferentes tem desafios diferentes.
""")

    with st.expander("O que e Amostra Confiavel?"):
        st.markdown("""
Uma escola tem **amostra confiavel** quando o numero de alunos que fizeram
o ENEM e suficiente para que a media seja estatisticamente representativa.

- **Confiavel**: >= 10 participantes (flag `amostra_confiavel = true`)
- **Nao confiavel**: < 10 participantes (resultados podem ser outliers)

O sistema indica quando uma escola tem amostra nao confiavel e sugere
cautela ao usar os dados para argumentacao de vendas.
""")

    st.divider()

    st.markdown("## As 3 Sub-abas")

    st.markdown("### Ranking P1/P2/P3")
    st.markdown("""
Lista as escolas ordenadas por prioridade. Voce pode filtrar por:
- **Prioridade**: P1, P2 ou P3
- **Dependencia**: Publica ou Privada
- **Porte**: Pequena, Media, Grande
- **Amostra**: Apenas confiaveis

Cada escola mostra: nome, INEP, media ENEM, gap vs peer, classificacao.
""")

    st.markdown("### Radar Comparativo")
    st.markdown("""
Grafico radar que compara uma escola com seu peer group em 5 dimensoes:
1. **Linguagens** (nota ENEM)
2. **Matematica** (nota ENEM)
3. **Ciencias Humanas** (nota ENEM)
4. **Ciencias da Natureza** (nota ENEM)
5. **Redacao** (nota ENEM)

O radar sobrepoe a escola (linha azul) sobre o peer group (area cinza),
tornando visual onde a escola esta forte e onde precisa melhorar.
""")

    st.markdown("### Explorador Livre")
    st.markdown("""
Ferramenta analitica para explorar os dados do ENEM com total liberdade:
- **Metricas**: Qualquer coluna numerica do school_analytics
- **Agrupamentos**: Por dependencia, porte, UF, municipio
- **Operacoes**: Media, mediana, soma, contagem, desvio padrao
- **Filtros**: Combinacao livre de criterios

Ideal para responder perguntas como:
- "Qual a media de matematica das privadas de Porto Alegre?"
- "Quantas escolas de medio porte tem amostra confiavel?"
- "Qual o desvio padrao de redacao por dependencia?"
""")

    st.divider()

    st.markdown("## OPR Interativo (One Page Report) — Novidade 2026")
    st.markdown("""
O **OPR Interativo** e um relatorio HTML visual auto-contido com **seletor de benchmark**.
Gerado via IAlex (WhatsApp: *"gera OPR do Colegio X"*) ou via Dashboard (botao em Escolas).

### Caracteristicas

- **1 link unico por escola** (permanente, servido via `dados.iaprendo.com.br/reports/{INEP}.html`)
- **4 abas comparativas** no topo: 🏫 Estaduais / 🏛️ Municipais / 🎖️ Federais / 🏆 Privadas
- **Clica na aba → atualiza tudo** sem recarregar: radar ENEM, cards, insights, ranking
- **Badges de oportunidade** em cada aba: 🔴 grande oportunidade / 🟠 moderada / 🟡 proximo / 🟢 destaque
- **Abas desabilitadas** quando nao ha dados suficientes (ex: cidade sem federais)

### O que cada aba mostra

| Secao | Comportamento |
|---|---|
| Visao Geral | Media ENEM (fixa) + alunos presentes (fixo) + **diferenca vs escolas [tipo]** (muda por aba) |
| Radar ENEM | Compara escola com media das escolas [tipo] da cidade nas 5 areas |
| Cards de comparacao | 5 cards (CN, CH, LC, MT, Redacao) com valor escola vs benchmark |
| Insights | Gerados automaticamente a partir dos gaps com aquele benchmark |

### Badges de forca de argumento

Cada aba tem um badge visual indicando a forca do argumento comercial:

| Badge | Condicao | Interpretacao |
|---|---|---|
| 🔴 Grande oportunidade | Gap > -50 pts | Melhor angulo de venda — escola muito abaixo do grupo |
| 🟠 Moderada | Gap -20 a -50 pts | Argumento razoavel — espaco de melhoria visivel |
| 🟡 Proxima | Gap -20 a 0 pts | Escola proxima do benchmark — argumento sutil |
| 🟢 Destaque | Gap > 0 pts | Elogio — escola acima do benchmark (use no email!) |

### Tracking via URL

- `URL#estadual`, `URL#privada` etc. abrem ja na aba especifica
- Util para enviar links focados: *"Veja a comparacao com as privadas: URL#privada"*

### Quando usar

- **Email de prospecao**: incluir link para a escola explorar a performance
- **Preparacao de reuniao**: Fernando revisa as 4 comparacoes antes de conversar
- **Material de Marketing**: link publico que pode ser compartilhado no LinkedIn
""")

    if st.button("Ir para Inteligencia", key="intel_go"):
        st.switch_page("pages/7_🎯_Inteligencia.py")


# #############################################################################
# TAB 8 — IALEX (WHATSAPP)
# #############################################################################
with tab_ialex:
    section_header("IAlex — Assistente de Vendas (Chat web + WhatsApp)", "smart_toy")

    st.markdown("""
O **IAlex** e o agente de IA conversacional. Ele tem acesso a **85 ferramentas**
organizadas em 12 categorias e pode fazer tudo que o dashboard faz — e mais —
apenas conversando. Voce fala com ele de **2 jeitos** (mesmo cerebro nos dois):
""")

    st.markdown("### 💬 Chat IAlex (no navegador) — 1a pagina do menu")
    st.markdown("""
A forma mais natural pra quem nao usa WhatsApp. Abra **💬 Chat IAlex** (primeira
pagina) e digite o que quer em linguagem natural. Vantagens vs WhatsApp:
- **Formatacao rica**: tabelas, listas, **botoes de download** (XLSX)
- **Historico proprio por usuario** (Fernando, Lizianne e Felipe nao se misturam)
- **Multi-usuario simultaneo**: varias pessoas conversando ao mesmo tempo

**Exemplos do que pedir** (perguntas, acoes, agregacao e exportacao):
- *"quantas escolas estaduais tem em Porto Alegre?"*
- *"quantos alunos no total nessas escolas?"* → responde com **transparencia**:
  X alunos confirmados (escolas com dado) + Y estimados (escolas sem dado, usando
  a media do grupo) — sempre deixando claro o que e dado real vs estimativa
- *"gera um excel com as escolas de POA com ensino medio e telefone"* → aparece
  um **botao de download do XLSX** (escolas + contatos)
- *"qualifica e gera email pro Colegio Anchieta com template automatico"*

### 📱 WhatsApp
Mesmo agente, pelo WhatsApp do IAlex. Ideal pra usar no celular, em movimento.
Roda no PC do Fernando (precisa estar ligado). Detecta automaticamente quem
mandou a mensagem (Fernando / Lizianne / Felipe) e usa o perfil/assinatura certo.

> **Novidades recentes (Mai/Jun 2026)**:
> - 💬 **Chat IAlex no navegador**: 1a pagina do dashboard, mesmas tools do WhatsApp
> - 📊 **Agregacao inteligente**: "quantos alunos/docentes" com cobertura +
>   estimativa transparente (concreto vs estimado)
> - 📥 **Exportar XLSX por chat**: "gera um excel com..." entrega link de download
> - 🎯 **Selecao automatica de template por alvo** (nominal/generico x dados)

> **Novidades anteriores (Abril 2026)**:
> - 🎯 **OPR Interativo**: relatorio HTML com seletor de benchmark (1 link, 4 comparacoes)
> - ⭐ **Skills Aprendidas**: "padroniza isso" salva modelos de resposta reutilizaveis
> - 🔥 **Urgency Score F2**: ranking unificado de leads (CRITICAL/HOT/WARM/COLD)
> - 🩺 **Auto-healing**: sistema se corrige sozinho em problemas conhecidos
> - 🧠 **Intent Detection com LLM**: analise semantica de respostas (nao so keywords)
> - 🛡️ **Modos de Autonomia**: Manual / Semi-Auto / Full-Auto com guardrails
> - 📞 **Registrar Contato Manual** (25/04): tool `registrar_contato` para logar
>   ligacoes / WhatsApp pessoal / emails feitos fora da plataforma; equivalente
>   a aba "Registrar Contato" no detalhe da escola — paridade dashboard ↔ IAlex
> - 🇧🇷 **Briefings em portugues** (25/04): "Sex, 25/04" em vez de "Fri, 25/04"

### Como Funciona
1. Envie uma mensagem no WhatsApp para o numero do IAlex
2. O IAlex interpreta sua intencao (NLU com Claude)
3. Ele seleciona e executa a ferramenta apropriada
4. Retorna o resultado formatado no chat
5. Voce pode refinar, pedir mais detalhes ou encadear acoes

### Dicas de Uso
- Seja direto: "Qualifique a escola X" funciona melhor que "voce pode qualificar?"
- Use nomes ou INEP: "Escola Marista" ou "INEP 43123456"
- Encadeie: "Qualifique e depois gere email para a escola Y"
- Peca ajuda: "O que voce sabe fazer?" lista as categorias
""")

    st.divider()
    st.markdown("## Catalogo de 85 Ferramentas em 12 Categorias")

    st.markdown("### 1. Buscar Escolas e Dados (8 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Buscar no CRM** | Pesquisa escolas ja importadas | "Busque escolas privadas de Porto Alegre" |
| **Buscar no MEC** | Pesquisa na base completa de 210k | "Procure escolas no MEC em Canoas" |
| **Agregar estatisticas** | Soma matriculas/docentes com cobertura+estimativa | "Quantos alunos nas estaduais de POA?" |
| **Exportar XLSX** | Gera planilha de escolas+contatos com link | "Gera um excel das escolas de POA" |
| **Buscar Proximidade** | Encontra escolas perto de um endereco | "Escolas num raio de 2km da Av. Ipiranga" |
| **Discovery** | Busca com criterios avancados | "Escolas privadas, medio, porte grande, RS" |
| **Buscar Sinais** | Identifica sinais de compra | "Que sinais a escola X tem?" |
| **Importar Escola** | Importa uma escola especifica | "Importa INEP 43001234 para o CRM" |
""")

    st.markdown("### 2. Inteligencia ENEM (5 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Performance ENEM** | Dados de desempenho de uma escola | "Qual a media ENEM da escola X?" |
| **Priorizar Leads P1/P2/P3** | Lista escolas por prioridade | "Mostre as top 10 P1 privadas" |
| **Busca ENEM** | Pesquisa por criterios ENEM | "Escolas com media > 600 em matematica" |
| **Analisar Analytics** | Analise agregada dos dados | "Media de redacao por porte" |
| **Trajetoria** | Evolucao historica da escola | "Mostre a evolucao da escola X de 2020 a 2024" |
""")

    st.markdown("### 3. Pipeline e Prospeccao (8 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Prospeccao Guiada** | Wizard passo a passo | "Inicie prospeccao para escola X" |
| **Pipeline** | Roda etapa especifica | "Qualifique a escola Y" |
| **Lote** | Processa varias escolas | "Qualifique todas as novas" |
| **Estatisticas** | Numeros do pipeline | "Quantas escolas em cada status?" |
| **Funil** | Visualiza funil de conversao | "Mostre o funil de vendas" |
| **Score ML** | Modelo preditivo de conversao | "Qual a chance de conversao da escola X?" |
| **Sinais de Compra** | Indicadores de propensao | "Que sinais a escola Z apresenta?" |
| **Melhor Horario** | Horario ideal de envio | "Qual melhor horario para enviar emails?" |
""")

    st.markdown("### 4. Emails (10 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Sugerir Angulos** | Propoe angulos de abordagem | "Sugira angulos para escola X" |
| **Gerar Email** | Cria email personalizado | "Gere email para a diretora da escola Y" |
| **Fila de Aprovacao** | Lista emails pendentes | "O que tem na fila?" |
| **Ver Email** | Mostra detalhes de um email | "Mostre o email #42" |
| **Aprovar** | Aprova email para envio | "Aprove o email #42" |
| **Rejeitar** | Rejeita email da fila | "Rejeite o email #42" |
| **Reescrever** | Pede nova versao | "Reescreva o email #42 com tom mais formal" |
| **Editar + Aprovar** | Edita e aprova | "Mude o assunto do #42 e aprove" |
| **Follow-ups** | Gerencia follow-ups | "Quais follow-ups estao pendentes?" |
| **Tracking** | Status de envio | "O email pra escola X foi aberto?" |
""")

    st.markdown("### 5. Campanhas e Templates (4 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Criar Campanha** | Nova campanha de outreach | "Crie campanha 'Privadas POA Abril'" |
| **Listar Campanhas** | Lista campanhas ativas | "Quais campanhas temos?" |
| **Criar Template** | Novo template de email | "Crie template de primeiro contato" |
| **Listar Templates** | Lista templates disponiveis | "Mostre os templates ativos" |
""")

    st.markdown("### 6. Contatos e Gestao de Relacionamento (8 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Buscar Contato** | Pesquisa decisores | "Quem e o diretor da escola X?" |
| **Enriquecer Contato** | Busca dados complementares | "Enriqueca o contato do diretor Y" |
| **WhatsApp** | Prepara mensagem WhatsApp | "Mande WhatsApp para a diretora Z" |
| **Detalhes** | Info completa do contato | "Detalhes do contato #15" |
| **Reuniao** | Agenda/registra reuniao | "Registre reuniao com escola X amanha" |
| **Registrar Contato** *(novo)* | Loga contato MANUAL feito fora da plataforma (WhatsApp pessoal, ligacao, email) — atualiza historico, `last_contacted_at` e (opcional) avanca status para `contacted` | "Liguei pra escola X agora, falamos sobre matricula 2027" |
| **Proposta** | Registra envio de proposta | "Registre proposta para escola Y" |
| **Ganho/Perdido** | Marca resultado | "Escola X virou cliente" |

> 💡 **Quando usar `Registrar Contato` (manual) vs as outras**:
> - **Reuniao**: voce vai ter / teve uma reuniao agendada (com data/hora)
> - **Registrar Contato**: foi um contato pontual fora da plataforma (ligacao,
>   WhatsApp pessoal, email pessoal). Logado com canal + direcao (voce contatou
>   ou eles te contataram) + observacao opcional.
> - **WhatsApp** (acima): mandar mensagem AUTOMATICA via Evolution API (entra
>   na fila de aprovacao, nao eh contato manual).
""")

    st.markdown("### 7. Integracoes (2 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **HubSpot Push** | Envia dados para HubSpot | "Sincronize escola X com HubSpot" |
| **HubSpot Pull** | Traz dados do HubSpot | "Atualize a escola Y com dados do HubSpot" |
""")

    st.markdown("### 8. Automacoes (5 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Autonomia** | Configura nivel de autonomia | "Aumente autonomia para nivel 3" |
| **Pipeline Auto** | Configura pipeline automatico | "Configure pipeline automatico as 9h" |
| **Follow-ups Auto** | Configura follow-ups automaticos | "Ative follow-ups automaticos" |
| **Rodar Pipeline** | Executa pipeline agora | "Rode o pipeline agora" |
| **Rodar Follow-ups** | Processa follow-ups agora | "Processe follow-ups pendentes" |
""")

    st.markdown("### 9. Memoria (5 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Lembrar** | Salva informacao na memoria | "Lembre que diretora X prefere manha" |
| **Buscar** | Consulta memorias | "O que sei sobre a escola Y?" |
| **Esquecer** | Remove memoria | "Esqueca que escola Z tem projeto tech" |
| **Info Modelo ML** | Sobre o modelo preditivo | "Como funciona o score ML?" |
| **Info RAG Emails** | Sobre o RAG de emails | "Como funciona a base de emails?" |
""")

    st.markdown("### 10. Relatorios e Insights Visuais (3 ferramentas) — NOVO")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Gerar OPR** | Relatorio HTML interativo (One Page Report) com **seletor de benchmark** (Estadual/Municipal/Federal/Privada) — 1 link unico por escola | "Gera o OPR do Colegio Militar" |
| **Comparar Escolas** | Relatorio comparativo entre 2 escolas (ou 1 escola vs grupo) com radar, cards e insights | "Compara Anchieta com Militar" |
| **Gerar Graficos** | 3 PNGs (radar, gap, trend) para inserir em emails | "Gera graficos para Colegio X" |

**Destaque**: o OPR agora e **interativo** — 1 link unico por escola. O usuario pode trocar entre 4 benchmarks (Estaduais/Municipais/Federais/Privadas) sem recarregar. Inclui badges de oportunidade (🔴🟠🟡🟢) em cada aba indicando a forca do argumento comercial.
""")

    st.markdown("### 11. Urgencia e Priorizacao (3 ferramentas) — F2")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Score Urgencia** | Score unificado 0-100 (engagement + ML + intent + ENEM) | "Qual a urgencia da escola X?" |
| **Proximas Acoes** | Lista priorizada de leads com maior urgencia | "Quais sao as proximas acoes?" |
| **Digest Urgencia** | Resumo diario completo por tier (CRITICAL/HOT/WARM/COLD) | "Me da o digest de urgencia" |

**Tiers**: 🔴 CRITICAL (80-100) → alerta imediato + auto-draft | 🟠 HOT (60-79) → briefing matinal | 🟡 WARM (40-59) → dashboard | ⚫ COLD (<40) → background

**Gate de autonomia**: em modo `manual`, IAlex NAO envia alertas proativos — so calcula scores em background.
""")

    st.markdown("### 12. Skills Aprendidas e Health (5 ferramentas) — F6")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Padronizar Resposta** | Salva ultimo padrao aprovado como skill reutilizavel | "Ficou otimo, padroniza isso" |
| **Listar Skills** | Lista skills aprendidas (ativas ou arquivadas) | "Quais skills voce aprendeu?" |
| **Arquivar Skill** | Remove skill da rotacao | "Arquiva a skill comparacao_redacao" |
| **Diagnostico Sistema** | Health check + auto-healing | "Como esta o sistema?" |
| **Uso APIs** | Quotas e limites de APIs externas | "Quanto ja gastei de API esse mes?" |

**Como funciona**: quando Fernando aprova uma resposta com "padroniza", o IAlex salva o padrao em `learned_skills`. Nas proximas conversas, o IAlex injeta as skills ativas no contexto como referencia de formato/tom. Gerenciamento tambem disponivel em **Configuracoes > aba Skills Aprendidas**.
""")

    st.divider()

    with st.expander("Desambiguacao: como o IAlex escolhe a ferramenta certa"):
        st.markdown("""
O IAlex usa um processo de 3 etapas para entender sua intencao:

1. **Classificacao de Intencao**: O Claude analisa sua mensagem e identifica
   a categoria (buscar, qualificar, email, etc.)

2. **Selecao de Ferramenta**: Dentro da categoria, escolhe a ferramenta mais
   adequada baseado em palavras-chave e contexto

3. **Extracao de Parametros**: Extrai os dados necessarios da sua mensagem
   (nome da escola, INEP, filtros, etc.)

**Se houver ambiguidade**, o IAlex pergunta para confirmar:
- "Voce quis dizer buscar no CRM ou no MEC?"
- "Qual escola: Marista Champagnat ou Marista Rosario?"
- "Deseja qualificar ou apenas ver o score atual?"
""")


# #############################################################################
# TAB 9 — CONFIGURACOES
# #############################################################################
with tab_config:
    section_header("Pagina de Configuracoes", "settings")

    st.markdown("""
A pagina **Configuracoes** permite ajustar o comportamento do sistema sem
mexer em codigo. Ela esta dividida em 4 abas:

1. ⚙️ **Configuracoes** — Pipeline automatico + Modo de Autonomia
2. 🧠 **Memorias** — Fatos, preferencias e insights persistentes
3. ⭐ **Skills Aprendidas** — Padroes que o IAlex aprendeu (F6)
4. 🩺 **Diagnostico** — Health check do sistema + auto-healing
""")

    st.markdown("## 1. Modo de Autonomia (topo da aba Configuracoes)")
    st.markdown("""
Define **quanto** o IAlex pode fazer sem sua autorizacao. 3 modos disponiveis:

| Modo | Descricao | Quando usar |
|---|---|---|
| 🛡️ **Manual** | IAlex nao faz NADA automatico. So responde quando voce pergunta. Zero alertas proativos. | Quando quer silencio total, so interagir por escolha |
| 🤖 **Semi-Auto** (DEFAULT) | IAlex GERA emails, follow-ups e qualificacoes automaticamente. Mas TUDO vai para fila de aprovacao — nada sai sem seu OK. | **Producao padrao**. Melhor custo-beneficio. |
| ⚡ **Full-Auto** | IAlex gera E envia automaticamente emails previamente aprovados em batches. Requer **dupla confirmacao** para ativar. | Times de alta velocidade com revisao diaria da fila |

**Gate F2 de alertas**: mesmo em Semi-Auto/Full-Auto, voce recebe alertas de urgencia (CRITICAL, HOT). Em Manual, **TODOS os alertas proativos sao suprimidos** — so calcula scores em background.

**Como trocar**: na aba Configuracoes, clique no card do modo desejado. Full-Auto pede confirmacao textual ("autorizo envio automatico") + registra timestamp.
""")

    st.markdown("## 2. Pipeline Automatico")
    st.markdown("""
Dentro do modo de autonomia escolhido, configure **quando e o que** rodar automaticamente.

### Parametros

| Parametro | Descricao | Padrao |
|---|---|---|
| **Horario de Inicio** | Hora que o pipeline comeca | 09:00 |
| **Dias da Semana** | Quais dias rodar | Seg a Sex |
| **Limite Diario** | Maximo de escolas/dia por etapa | 20 qualificacoes, 10 enriquecimentos |
| **Etapas Ativas** | Quais etapas rodar automaticamente | Qualificar, Enriquecer, Contatos, Escrever |
| **Send Approved** | Envia emails ja aprovados? | So ativado em **Full-Auto** |
| **Persona Mode** | Tom fixo ou adaptativo | padrao |
| **Follow-ups Auto** | Gera follow-ups comportamentais diariamente | Habilitado |
""")

    st.divider()

    st.markdown("## 3. Memoria do IAlex")
    st.markdown("""
A memoria do IAlex armazena informacoes persistentes sobre escolas, contatos
e preferencias. Isso permite que o agente mantenha contexto entre conversas.

### Tipos de Memoria

| Tipo | Escopo | Exemplo |
|---|---|---|
| **Fato** | Global ou Escola | "Escola X tem 500 alunos" |
| **Preferencia** | Global ou Contato | "Diretora prefere contato de manha" |
| **Insight** | Global | "Escolas privadas respondem mais a 2a feira" |
| **Alerta** | Escola ou Contato | "Nao contatar escola Y ate marco" |
| **Lembrete** | Global | "Enviar proposta para escola Z ate sexta" |

### Gestao de Memorias
- Criar: Adicione memorias manualmente ou peca ao IAlex
- Buscar: Filtre por tipo, escopo, data
- Editar: Atualize o conteudo de uma memoria
- Excluir: Remova memorias desatualizadas
""")

    st.divider()

    st.markdown("## 4. Skills Aprendidas (F6 — NOVO)")
    st.markdown("""
Padroes de resposta que o IAlex aprendeu com suas aprovacoes.

### Como criar uma skill

**Via WhatsApp**: apos uma resposta que voce gostou, diga *"padroniza isso"*.
O IAlex salva o padrao em `learned_skills`.

**Via Dashboard**: na aba Skills Aprendidas, use o formulario "Criar nova skill"
com nome, tipo, gatilho, conteudo e exemplo.

### Tipos de skill

| Tipo | Uso | Exemplo |
|---|---|---|
| 📧 **Email Template** | Padrao de email aprovado | email_pressao_enem |
| 📊 **Report Format** | Formato de OPR customizado | opr_compacto_diretora |
| 🔍 **Analysis Pattern** | Estrutura de analise | trajetoria_3anos |
| 💬 **Response Style** | Tom/formato de resposta | resposta_breve_formal |
| 📱 **WhatsApp Template** | Mensagem WhatsApp padrao | wa_convite_reuniao |

### Como funcionam

Quando o IAlex processa uma mensagem, ele **injeta as skills ativas** no system prompt
como referencia. Se o contexto bater com o gatilho de uma skill, ele segue o padrao
registrado em `template_content`.

### Gestao

- **Listar**: ver todas as skills ativas, seus usos e metricas
- **Detalhes**: visualizar conteudo, exemplos e gatilho
- **Arquivar**: desativa a skill (soft delete) — pode reativar depois
- **Reativar**: volta a incluir no system prompt

### Sincronizacao WhatsApp ↔ Dashboard

Skills criadas por qualquer canal aparecem em ambos. Arquivamento no Dashboard
tambem afeta o IAlex (skill nao e mais injetada). Coerencia total.
""")

    st.divider()

    st.markdown("## 5. Health Check e Auto-Healing (F6 Fase 3A — NOVO)")
    st.markdown("""
O diagnostico do sistema verifica todos os componentes E **tenta corrigir sozinho**
problemas conhecidos antes de alertar Fernando.

### Componentes Verificados (10 checks)

| Componente | O que verifica |
|---|---|
| **Supabase** | Latencia do banco (<500ms) |
| **Schema** | Colunas criticas presentes (migrations up-to-date) |
| **WhatsApp Bridge** | Evolution API online + instancia conectada |
| **Flask Webhook** | Porta 5001 respondendo |
| **Brain Tools** | Consistencia TOOLS vs TOOL_HANDLERS |
| **Fila de Aprovacao** | Contagem de pendentes + stuck (>7 dias) |
| **Error Rate 1h** | Picos de erro recentes |
| **Error Rate 24h** | Tendencia de erros |
| **API Quotas** | Apollo, Hunter, Snov, Brevo proximo do limite |
| **Pipeline Config** | Autonomy level e send_approved coerentes |

### Indicadores
- 🟢 **Verde (healthy)**: Componente funcionando normalmente
- 🟡 **Amarelo (degraded)**: Funcionando com limitacoes (rate limit proximo, etc.)
- 🔴 **Vermelho (critical)**: Componente indisponivel ou com erro

### Auto-Healing (automatico a cada 30 min)

O sistema **TENTA remediar** antes de pedir ajuda:

| Problema detectado | Acao automatica |
|---|---|
| WhatsApp Bridge critical | Restart da instancia `ialex` via Evolution API |
| Webhook Flask critical | Notifica Fernando (nao pode auto-restart o proprio processo) |
| Fila parada (>7 dias) | Notifica Fernando para limpar manualmente |
| Error rate 1h critical | Notifica Fernando para investigar |
| API quota >90% | Notifica Fernando para upgrade ou aguardar reset |

**Filosofia**: remediar apenas acoes seguras (restart de containers) e notificar
para acoes ambiguas (intervencao humana necessaria). Frequencia: a cada 30 min.
""")

    st.divider()

    st.markdown("## 6. Acesso, Login e Multi-user")
    st.markdown("""
### Como acessar a plataforma
- **Pelo navegador** (Felipe, Lizianne, qualquer um, de qualquer lugar): abra o
  endereco da plataforma — `iaprendo-sales-agent.streamlit.app` (ou o dominio
  proprio `vendasiaprendo.duogen.com.br` quando o Cloudflare estiver ativo) — e
  faca login com **seu usuario e senha**
- O app fica **sempre ativo** (nao hiberna) gracas a um ping automatico
  (keep-alive). 1o acesso apos muito tempo pode levar ~30s
- **IAlex WhatsApp** roda no **PC do Fernando** (precisa estar ligado). Ja o
  dashboard e o **💬 Chat IAlex** funcionam de qualquer lugar, sempre

### Divisao de trabalho (importante)
- **Importar a base bruta do MEC** (185k escolas): Fernando faz no PC dele, 1x
  por safra. Depois, todos veem as escolas no banco automaticamente
- **Pipeline** (qualificar/enriquecer/contatos/gerar): qualquer um roda pelo
  dashboard, em **lotes** (no Cloud, ate ~100 escolas por vez)

A plataforma suporta **3 usuarios** com identidade propria: **Fernando,
Lizianne e Felipe**. Cada email gerado/enviado usa a identidade do usuario
**ativo** (quem esta logado no dashboard ou quem mandou o comando no WhatsApp).

### Como funciona

| Cenario | Como a identidade e resolvida |
|---|---|
| **Dashboard (Streamlit)** | Login com usuario/senha (`streamlit-authenticator`). Sender ativo = usuario logado. Visivel na sidebar. |
| **IAlex (WhatsApp)** | Auto-detectado pelo numero do telefone que enviou. Fernando manda do dele -> IAlex assina como Fernando. Lizianne manda do dela -> IAlex assina como Lizianne. |
| **Workflows automaticos (cron)** | Fallback para `settings.YOUR_*` (.env, padrao Fernando). |

### Onde mexer
- **Cadastro/edicao de usuarios**: `config/users.yaml` (gitignored). Use `config/users.yaml.example` como template.
- **Trocar senha**: sidebar do dashboard apos login -> "Trocar senha".
- **Adicionar novo numero ao IAlex**: em `config/users.yaml`, sob o usuario, adicione em `whatsapp_numbers:` os 2 formatos (com e sem nono digito).
- **Adicionar novo usuario**:
  1. Gerar hash da senha: `venv/Scripts/python.exe -c "import bcrypt; print(bcrypt.hashpw(b'<senha>', bcrypt.gensalt()).decode())"`
  2. Editar `config/users.yaml`, copiar bloco existente, ajustar campos
  3. Atualizar `IALEX_AUTHORIZED_NUMBERS` no `.env` para o numero ser aceito pelo IAlex
  4. Reiniciar IAlex (Streamlit auto-reload pega na hora)

### Brevo (envio de email)
Cada usuario tem seu proprio `email` no perfil. Para emails saírem de cada
remetente, **cada email precisa estar verificado como sender** na conta
Brevo (mesma conta — adicionar sender adicional no painel Brevo). Sem
verificacao, o Brevo rejeita o envio.

**Nome do remetente** (`email_sender_name`): o nome que aparece no "De:" do email
e configuravel por usuario — ex: `Fernando Teixeira | DUOGEN`,
`Lizianne P. K. Nienaber | DUOGEN`, `Felipe Fangueiro | DUOGEN`. Fica no perfil
de cada usuario (`users.yaml` / Secrets). So afeta o email — saudacao no chat e
sidebar continuam usando so o primeiro nome.

### Streamlit Cloud
O `config/users.yaml` e gitignored — para o Cloud, configure via Secrets:
estrutura TOML equivalente em **Settings -> Secrets** com `[auth.credentials.usernames.<user>]` etc.

### Helper canonico
`utils/sender_profile.py` resolve a identidade ativa em qualquer ponto do
codigo: `from utils.sender_profile import get_active_sender; sender = get_active_sender()`.
Usado em `agents/writer.py`, `agent/brain.py`, `tools/brevo_sender.py` e
`workflows/follow_up_manager.py`.
""")

    st.divider()

    st.markdown("## 7. Helpers e Documentos Operacionais")
    st.markdown("""
Algumas peças que **nao tem UI** mas valem conhecer:

| Helper / Doc | Onde fica | Para que serve |
|---|---|---|
| **`utils/date_pt.py`** | `utils/` | Traduz `%a/%A/%b/%B` do strftime para pt_BR sem depender de `locale.setlocale`. Briefings agora mostram "Sex, 25/04" em vez de "Fri, 25/04". Usado em `agent/brain.py` (briefing matinal). |
| **`docs/RELOCATION.md`** | `docs/` | Runbook de mudanca de pasta do projeto (ex: de OneDrive para `C:\\Dev\\`). Cobre: recriar venv, preservar volumes Docker do WhatsApp via `name:` no compose, atualizar paths em `.claude/settings.local.json`, copiar historico de sessoes Claude Code. Use quando precisar mover o projeto. |
| **`docs/ANNUAL_UPDATE.md`** | `docs/` | Runbook anual: importar nova edicao do ENEM e Censo, recalcular peer groups e rankings. |
""")

    if st.button("Ir para Configuracoes", key="config_go"):
        st.switch_page("pages/9_⚙️_Configuracoes.py")


# #############################################################################
# TAB 10 — BOAS PRATICAS
# #############################################################################
with tab_boas:
    section_header("Boas Praticas de Operacao", "tips_and_updates")

    st.markdown("## Ciclo Semanal Recomendado")

    st.markdown("""
| Dia | Atividade | Tempo |
|---|---|---|
| **Segunda** | Revisar metricas da semana anterior. Planejar metas. | 30 min |
| **Terca** | Importar novas escolas (se necessario). Rodar qualificacao. | 45 min |
| **Quarta** | Enriquecer escolas qualificadas. Buscar contatos. | 45 min |
| **Quinta** | Gerar e aprovar emails. Revisar fila de aprovacao. | 60 min |
| **Sexta** | Acompanhar respostas. Processar follow-ups. Atualizar pipeline. | 45 min |
""")

    st.divider()

    st.markdown("## Logue cada contato MANUAL (regra basica de CRM)")
    st.markdown("""
Sempre que voce ligar, mandar WhatsApp pessoal ou email pessoal para uma escola
**fora da plataforma**, registre o contato. Isso mantem o CRM como **fonte unica
de verdade** e ajuda em 3 frentes:

1. **Historico completo** na timeline da escola — qualquer pessoa olhando
   sabe que aquele lead ja foi contatado (e como).
2. **Status do pipeline atualizado** — o lead deixa de aparecer como
   `qualified` parado e vai para `contacted`, refletindo a realidade.
3. **IAlex contextualizado** — o agente sabe do contato e nao vai sugerir
   "envia primeiro email" para uma escola com quem voce ja conversou.

### Como registrar (2 caminhos equivalentes)

| Canal | Como |
|---|---|
| **Dashboard** | Escolas → ver detalhe → aba **Registrar Contato** → escolher canal/direcao/data + observacao + checkboxes |
| **IAlex (WhatsApp)** | Frase natural: *"Liguei pra Anchieta agora, falamos sobre matricula 2027"* — IAlex usa a tool `registrar_contato` |

Ambos chamam o mesmo helper canonico (`db.register_manual_interaction()`), entao
o resultado e identico: linha em `interactions` + `last_contacted_at` atualizado
+ status avancado (se aplicavel).
""")

    st.divider()

    st.markdown("## Fases de Crescimento")

    with st.expander("Fase 1: Validacao (Mes 1-2) — 10-20 leads/mes"):
        st.markdown("""
**Objetivo**: Validar que o processo funciona e gera respostas.

- Foque em Porto Alegre (mercado local, facil de visitar)
- Comece com escolas **privadas** (decisao mais agil)
- Rode o pipeline manualmente (nivel autonomia 1-2)
- Aprove CADA email pessoalmente — aprenda o tom ideal
- Meta: 3-5 respostas positivas no mes

**Metricas-chave**:
- Taxa de abertura > 30%
- Taxa de resposta > 8%
- Pelo menos 1 reuniao agendada
""")

    with st.expander("Fase 2: Otimizacao (Mes 3-4) — 40-60 leads/mes"):
        st.markdown("""
**Objetivo**: Aumentar volume mantendo qualidade.

- Expanda para cidades proximas (Canoas, Gravataí, Viamao)
- Adicione escolas **publicas estaduais** (Fundamental AF + Medio)
- Aumente autonomia para nivel 3 (gera email automatico)
- Use dados ENEM para priorizar P1
- Crie templates otimizados baseado nos melhores emails

**Metricas-chave**:
- Manter taxa de abertura > 30%
- Taxa de resposta > 10%
- 3-5 reunioes por mes
- Custo por lead < R$ 5
""")

    with st.expander("Fase 3: Escala (Mes 5+) — 100+ leads/mes"):
        st.markdown("""
**Objetivo**: Escalar para todo o RS e depois nacional.

- Expanda para todo o RS
- Adicione segmentos: escolas tecnicas, municipais
- Use modelo ML de score para priorizar automaticamente
- Follow-ups automaticos (nivel autonomia 3-4)
- Integre com HubSpot para gestao completa do funil

**Metricas-chave**:
- Volume: 100+ leads processados/mes
- Reunioes: 10+ por mes
- Conversao lead-para-reuniao > 5%
- ROI do sistema > 10x
""")

    st.divider()

    st.markdown("## Dicas para Emails Eficazes")
    st.markdown("""
### O que Funciona
- **Assunto curto** (< 50 caracteres): "Como a escola X pode melhorar em ENEM"
- **Personalizacao real**: Mencionar dados especificos (media ENEM, porte, regiao)
- **Pergunta no final**: "Podemos conversar 15 minutos na proxima semana?"
- **1 CTA claro**: Nao oferecer varias opcoes ao mesmo tempo
- **Tom consultivo**: Ajudar, nao vender

### O que NAO Funciona
- Assuntos genericos: "Solucao educacional inovadora"
- Emails longos (> 200 palavras para primeiro contato)
- Multiplos links ou anexos
- Tom excessivamente formal ou robotico
- Promessas vagas sem dados concretos
""")

    st.divider()

    st.markdown("## Uso Inteligente de P1/P2/P3")

    st.markdown("""
### Estrategia por Prioridade

**P1 (Alta prioridade — Gap negativo)**
- **Angulo**: "Sabemos que escolas como a sua enfrentam desafios em [area]. Podemos ajudar."
- **Dado**: Use o gap vs peer group como argumento
- **Tom**: Empatico, consultivo, sem julgar
- **Timing**: Priorize envio — maior urgencia do prospect

**P2 (Media prioridade — Proximo da media)**
- **Angulo**: "Sua escola esta na media — com IAprendo, pode se destacar."
- **Dado**: Compare com as melhores do peer group
- **Tom**: Motivacional, focado em diferenciacao
- **Timing**: Bom para campanhas regulares

**P3 (Prioridade menor — Acima da media)**
- **Angulo**: "Parabens pelos resultados. Veja como manter a lideranca."
- **Dado**: Destaque os pontos fortes, mostre areas de melhoria
- **Tom**: Elogioso, focado em excelencia continua
- **Timing**: Pode aguardar — menor urgencia
""")


# #############################################################################
# TAB 11 — USE CASES
# #############################################################################
with tab_usecases:
    section_header("Cenarios de Uso Passo a Passo", "cases")

    st.markdown("Abaixo estao 5 cenarios reais que voce pode seguir como tutorial.")

    st.divider()

    with st.expander("Cenario 1: Prospectar uma escola nova pelo dashboard", expanded=True):
        st.markdown("""
**Situacao**: Voce ouviu falar de uma escola privada em Porto Alegre e quer
adiciona-la ao pipeline.

**Passo a passo**:

1. **Va em Importar**
   - Se a escola ja esta no CRM, va direto ao passo 3
   - Se nao, importe pelo CSV (filtre por nome ou INEP)

2. **Verifique em Escolas**
   - Busque pelo nome da escola
   - Confirme que os dados estao corretos (endereco, porte, etapas)

3. **Va em Pipeline > Execucao**
   - Selecione a escola
   - Clique **Qualificar** — veja o score
   - Clique **Enriquecer** — busque dados web
   - Clique **Encontrar Contatos** — localize o diretor(a)

4. **Gere o Email**
   - Clique **Gerar Email** no Pipeline
   - O email vai para a fila de aprovacao

5. **Aprove em Comunicacao**
   - Va em Comunicacao > Aprovacao
   - Leia o email gerado
   - Aprove, edite ou peca reescrita
   - Apos aprovacao, o email e enviado automaticamente

6. **Acompanhe**
   - Em Comunicacao > Metricas, veja se foi aberto
   - Em 3 dias, o follow-up automatico sera gerado (se nao abriu)
""")

    with st.expander("Cenario 2: Usar ENEM para priorizar escolas"):
        st.markdown("""
**Situacao**: Voce tem 50 escolas no CRM e quer saber por onde comecar.

**Passo a passo**:

1. **Va em Inteligencia**
   - Selecione a aba **Ranking P1/P2/P3**
   - Filtre por: Privadas, Porte Medio+, Amostra Confiavel

2. **Analise as P1**
   - Veja quais escolas estao mais abaixo do peer group
   - Essas tem mais "dor" e maior propensao a investir

3. **Use o Radar para entender**
   - Selecione uma escola P1
   - Veja o radar: onde ela esta fraca vs o peer group?
   - Matematica? Redacao? Ciencias?
   - Esse dado vai personalizar o email

4. **Gere email com contexto ENEM**
   - No IAlex: "Gere email para escola X usando dados ENEM"
   - Ou no Pipeline: selecione a escola e gere email
   - O email ja incluira os dados de desempenho automaticamente

5. **Estrategia**
   - P1: Foque 70% do esforco aqui
   - P2: Use para preencher pipeline (20%)
   - P3: Aborde quando houver capacidade (10%)
""")

    with st.expander("Cenario 3: Operar tudo via IAlex (WhatsApp)"):
        st.markdown("""
**Situacao**: Voce esta fora do escritorio e quer rodar o pipeline pelo celular.

**Passo a passo**:

1. **Abra o WhatsApp e mande mensagem para o IAlex**

2. **Verifique o pipeline**:
   - "Quantas escolas em cada status?"
   - "Quais follow-ups estao pendentes?"

3. **Processe novas escolas**:
   - "Qualifique todas as escolas novas"
   - "Enriqueca as 5 melhores qualificadas"

4. **Gere emails**:
   - "Gere emails para as 3 escolas top P1"
   - O IAlex gera e coloca na fila

5. **Aprove emails**:
   - "Mostre a fila de aprovacao"
   - "Mostre o email #42"
   - "Aprove o email #42"
   - Ou: "Reescreva #42 com tom mais casual"

6. **Acompanhe resultados**:
   - "O email da escola X foi aberto?"
   - "Quais escolas responderam essa semana?"

7. **Registre contexto**:
   - "Lembre que a diretora da escola Y pediu para ligar quinta"
   - O IAlex salva na memoria para uso futuro
""")

    with st.expander("Cenario 4: Campanha para rede de escolas"):
        st.markdown("""
**Situacao**: Voce identificou que 4 escolas pertencem a mesma rede (ex: Marista)
e quer criar uma campanha coordenada.

**Passo a passo**:

1. **Identifique a rede em Escolas**
   - Va em Escolas > aba Redes
   - Encontre o grupo (mesmo CNPJ de mantenedora)
   - Anote as escolas da rede

2. **Crie uma campanha no IAlex**
   - "Crie campanha 'Rede Marista Abril 2026'"
   - Defina: angulo unico para toda a rede

3. **Personalize por unidade**
   - Cada escola da rede recebe email proprio
   - Mas o angulo e consistente (mencionar a rede como um todo)
   - Use dados ENEM de cada unidade para personalizar

4. **Aborde o decisor certo**
   - Para redes, o decisor pode ser centralizado (mantenedora)
   - Busque o contato da mantenedora, nao apenas das unidades
   - Use Power Map em Contatos para mapear a hierarquia

5. **Acompanhe a campanha**
   - Em Comunicacao > Metricas, filtre pela campanha
   - Veja resultados por unidade e consolidado
""")

    with st.expander("Cenario 5: Registrar contato manual feito fora da plataforma"):
        st.markdown("""
**Situacao**: Voce ligou pra escola Anchieta no celular pessoal, ou trocou
WhatsApp com a diretora pelo numero direto, ou respondeu um email pessoal —
nada disso foi via IAprendo, mas precisa entrar no historico.

**Caminho A — pelo dashboard** (mais visual):

1. Va em **Escolas** > busque "Anchieta" > clique para ver detalhe
2. Abra a aba **Registrar Contato**
3. Preencha:
   - **Canal**: WhatsApp / Ligacao / Email
   - **Direcao**: "Eu contatei" ou "Eles me contataram"
   - **Data**: padrao hoje (mude se foi outro dia)
   - **Contato (decisor)**: opcional, se for um decisor especifico
   - **Observacao**: o que foi conversado, proximos passos
   - **Mover status para 'Contatado'**: marcado por padrao
4. Clique **Registrar contato**
5. O contato vai aparecer na aba **Historico** dessa escola

**Caminho B — pelo IAlex** (mais rapido se voce ja esta no WhatsApp):

Mande qualquer uma destas frases:
- *"Liguei pra escola Anchieta agora, falamos sobre matricula 2027"*
- *"Mandei whatsapp pro diretor da Marista, marcamos reuniao quinta"*
- *"Recebi email da Sao Bento respondendo a proposta"*

O IAlex entende canal+direcao automaticamente, registra a interacao, atualiza
`last_contacted_at` e responde *"Contato registrado: Anchieta (call_made) | Status -> contacted"*.

**Quando NAO registrar**:
- Se foi reuniao (use **Registra reuniao** — tem campo de outcome)
- Se foi mensagem via Evolution API (ja entra automatico no historico)
- Se foi email enviado pela plataforma (ja entra automatico via tracking)

**Comece a usar**: faz parte do **ciclo semanal** acima — sempre que
trocar contato fora da plataforma, registre. Mantem o CRM 100% confiavel.
""")

    with st.expander("Cenario 6: Analise semanal de resultados"):
        st.markdown("""
**Situacao**: Toda segunda-feira voce precisa analisar a semana anterior
e planejar a proxima.

**Passo a passo**:

1. **Metricas de email** (Comunicacao > Metricas)
   - Taxa de abertura da semana
   - Taxa de resposta
   - Quais emails performaram melhor (angulo, horario)
   - Bounces ou problemas de entrega

2. **Pipeline** (Pipeline > Pipeline Comercial)
   - Quantas escolas avancaram de estagio?
   - Quais estao paradas ha mais de 7 dias?
   - Alguma reuniao agendada?

3. **Analytics** (Analytics)
   - ROI do sistema (custo vs valor gerado)
   - Funil de conversao atualizado
   - Tendencias ao longo das semanas

4. **Planejar proxima semana**
   - Quantas novas escolas importar?
   - Quais P1 abordar?
   - Follow-ups pendentes para aprovar?
   - Ajustar templates com base no que funcionou?

5. **Registrar aprendizados**
   - No IAlex: "Lembre que emails com pergunta no assunto tiveram 40% mais abertura"
   - Essas memorias melhoram os emails futuros
""")


# #############################################################################
# TAB 12 — GLOSSARIO
# #############################################################################
with tab_glossario:
    section_header("Glossario Tecnico", "menu_book")

    st.markdown("Termos tecnicos usados em todo o sistema, em ordem alfabetica.")

    glossary = [
        ("Agregacao Inteligente",
         "Quando o IAlex soma metricas (alunos, docentes) sobre um conjunto de "
         "escolas, ele SEMPRE separa dado CONCRETO (escolas que tem o dado) de "
         "ESTIMATIVA (escolas sem dado, usando a media do grupo). Ex: '117k alunos "
         "= 95k confirmados + 22k estimados'. Garante transparencia, nunca inventa."),

        ("Anexos PDF",
         "Arquivos PDF (ex: apresentacao) que cada usuario cadastra em "
         "Comunicacao > Templates. Vao anexados automaticamente nos emails que "
         "aquele usuario enviar (sticky). Da pra sobrescrever por mensagem na Aprovacao."),

        ("Audience / Data Profile",
         "As 2 dimensoes da selecao automatica de template. Audience = publico "
         "(nominal=pessoa real / generico=secretaria@). Data Profile = dados que o "
         "template exige (ambos / matriculas / enem / nenhum). O sistema cruza as "
         "2 pra escolher o melhor template pro alvo."),

        ("Amostra Confiavel",
         "Indicador de que uma escola tem numero suficiente de participantes "
         "no ENEM (>= 10) para que a media seja estatisticamente representativa. "
         "Escolas com amostra nao confiavel devem ser tratadas com cautela."),

        ("Approval Queue",
         "Fila de aprovacao. Mecanismo que garante que NENHUM email e enviado "
         "sem revisao humana. Toda mensagem gerada pela IA passa por essa fila "
         "antes do envio."),

        ("Chat IAlex",
         "Pagina de conversa com a IA dentro do dashboard (1a do menu, 💬). Mesmo "
         "cerebro e mesmas ferramentas do IAlex no WhatsApp, mas com formatacao "
         "rica (tabelas, botoes de download) e historico proprio por usuario. "
         "Digite em linguagem natural: perguntas, acoes, agregacoes, exports."),

        ("Cobertura / Estimativa",
         "Numa agregacao, COBERTURA = % de escolas que tem o dado real. "
         "ESTIMATIVA = valor calculado para as escolas sem dado (media do grupo "
         "x quantidade). A resposta sempre separa os dois pra deixar claro o que "
         "e fato vs aproximacao."),

        ("Commercial Stage",
         "Pipeline Kanban da escola, separado do `status`. Valores: prospectado, "
         "contatado, respondeu, reuniao, proposta, cliente, perdido. O `status` "
         "(raw/qualified/contacted/...) reflete o estado tecnico no funil; o "
         "`commercial_stage` reflete o estado COMERCIAL no Kanban. Podem avancar "
         "juntos via `register_manual_interaction(advance_commercial_stage=True)`."),

        ("BNCC",
         "Base Nacional Comum Curricular. Documento normativo do MEC que define "
         "o conjunto de aprendizagens essenciais que todos os alunos devem "
         "desenvolver. O IAprendo e alinhado a BNCC."),

        ("Dependencia Administrativa",
         "Classificacao de quem mantem a escola: Federal, Estadual, Municipal "
         "ou Privada. Determina o processo de compra e o tipo de decisor."),

        ("Discovery",
         "Processo de busca ativa por novas escolas potenciais, usando "
         "criterios avancados como sinais de compra, localizacao e perfil."),

        ("email_sender_name",
         "Nome que aparece no 'De:' do email, por usuario — ex: 'Fernando Teixeira "
         "| DUOGEN'. So afeta o email; saudacao no chat e sidebar usam so o primeiro "
         "nome. Configurado no perfil (users.yaml / Secrets do Cloud)."),

        ("Export XLSX",
         "Geracao de planilha Excel com escolas + contatos (3 abas: Escolas, "
         "Contatos, Info). Disponivel no Pipeline (selecionadas), em Contatos "
         "(filtradas) e pelo chat ('gera um excel...'). No chat/WhatsApp vem como "
         "link de download (valido 24h)."),

        ("Ensino Fundamental AF",
         "Ensino Fundamental — Anos Finais (6o ao 9o ano). Faixa etaria "
         "de 11 a 14 anos. Um dos publicos-alvo do IAprendo."),

        ("Ensino Medio",
         "Etapa final da educacao basica (1a a 3a serie). Faixa etaria "
         "de 15 a 17 anos. Outro publico-alvo do IAprendo."),

        ("Fit Score",
         "Componente do Qualification Score que mede o quao bem a escola "
         "se encaixa no perfil ideal de cliente (ICP). Considera porte, "
         "nivel de ensino, dependencia, localizacao."),

        ("Follow-up",
         "Email de acompanhamento enviado apos o primeiro contato. O sistema "
         "agenda automaticamente 3 follow-ups em intervalos crescentes."),

        ("Forcar Reprocessar",
         "Opcao no Pipeline (checkbox 🔁). Por padrao cada etapa pula escolas que "
         "ja passaram por ela; marcando 'Forcar', a etapa roda de novo (ex: "
         "re-enriquecer uma escola ja enriquecida pra atualizar dados)."),

        ("Gap vs Peer",
         "Diferenca entre a media ENEM da escola e a media do seu peer group. "
         "Gap negativo = abaixo da media (P1). Gap positivo = acima (P3)."),

        ("INEP",
         "Instituto Nacional de Estudos e Pesquisas Educacionais Anisio "
         "Teixeira. Orgao do MEC responsavel pelo Censo Escolar e ENEM. "
         "Cada escola tem um codigo INEP unico (8 digitos) que e a chave "
         "primaria no nosso sistema."),

        ("last_contacted_at",
         "Campo da tabela `companies` que guarda a data/hora do ultimo contato "
         "(automatico ou manual) com a escola. Atualizado por: envio de email, "
         "registro de reuniao, e a tool `registrar_contato` (ou aba 'Registrar "
         "Contato' no detalhe da escola). Util para filtrar 'leads inativos'."),

        ("Manual Interaction",
         "Contato realizado FORA da plataforma (WhatsApp pessoal, ligacao, "
         "email pessoal) e logado manualmente. Insere uma linha em `interactions` "
         "com `metadata.manual=true` e `metadata.source='dashboard'|'ialex'`. "
         "Equivalente entre dashboard (aba Registrar Contato) e IAlex (tool "
         "`registrar_contato`) — mesma operacao atomica."),

        ("Infra Score",
         "Componente do Qualification Score que avalia a infraestrutura "
         "tecnologica da escola: laboratorio de informatica, internet banda "
         "larga, tablets/chromebooks."),

        ("P1 / P2 / P3",
         "Sistema de priorizacao baseado no gap vs peer group do ENEM. "
         "P1 = alta prioridade (gap negativo grande), P2 = media (gap proximo "
         "de zero), P3 = baixa (gap positivo). P1 tem mais dor e maior "
         "propensao a investir."),

        ("Peer Group",
         "Grupo de escolas com caracteristicas similares (mesma dependencia, "
         "porte, regiao, nivel socioeconomico). Usado para comparacao justa "
         "de desempenho no ENEM."),

        ("phone_whatsapp",
         "Campo de celular/WhatsApp SEPARADO do telefone fixo, tanto em contatos "
         "quanto na escola. O envio por WhatsApp prioriza esse campo (o fixo de "
         "8 digitos nao funciona no WhatsApp). Aparece em verde 📱 na interface."),

        ("Pipeline",
         "Sequencia de etapas que uma escola percorre desde a importacao "
         "ate a conversao: Novo > Qualificado > Enriquecido > Contatado > "
         "Respondeu > Convertido."),

        ("Power Map",
         "Visualizacao hierarquica dos contatos de uma escola, mostrando "
         "decisores (diretor), influenciadores (coordenador) e operacionais "
         "(secretaria). Ajuda a identificar quem abordar."),

        ("Qualification Score",
         "Score de 0 a 100 atribuido pela IA a cada escola. Composto por: "
         "Fit Score (adequacao ao ICP) + Tech Score (maturidade tech) + "
         "Infra Score (infraestrutura). Usado para priorizar prospeccao."),

        ("RAG",
         "Retrieval-Augmented Generation. Tecnica de IA que busca informacoes "
         "relevantes em uma base de dados antes de gerar texto. O IAlex usa "
         "RAG para consultar emails anteriores e gerar mensagens melhores."),

        ("Tech Score",
         "Componente do Qualification Score que avalia a maturidade "
         "tecnologica da escola: presenca digital, uso de plataformas, "
         "projetos de inovacao."),

        ("Template Auto (selecao por alvo)",
         "Modo de geracao de email que escolhe automaticamente o melhor template "
         "conforme o alvo: publico (nominal/generico) x dados da escola "
         "(matriculas/ENEM). Ideal = nominal + ambos os dados; degrada pro melhor "
         "disponivel. Ativado no Pipeline ('Template auto por alvo') ou no chat."),

        ("Webhook",
         "Mecanismo de notificacao automatica entre sistemas. O HubSpot "
         "envia webhooks para o IAprendo quando um contato atualiza no CRM, "
         "e vice-versa."),
    ]

    # Render as a searchable list
    search_term = st.text_input(
        "Buscar no glossario",
        placeholder="Digite um termo...",
        key="glossario_search",
    )

    filtered = glossary
    if search_term:
        term_lower = search_term.lower()
        filtered = [
            (t, d) for t, d in glossary
            if term_lower in t.lower() or term_lower in d.lower()
        ]

    if not filtered:
        st.info("Nenhum termo encontrado. Tente outra busca.")
    else:
        for term, definition in filtered:
            st.markdown(
                f"**{term}**<br/>"
                f"<span style='color:#616161; font-size:14px;'>{definition}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<hr style='margin:8px 0; border:none; border-top:1px solid #EEEEEE;'/>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.caption(
        "Manual IAprendo Sales Agent v1.0 — Ultima atualizacao: 25/04/2026"
    )
