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
    "IAlex (WhatsApp)",
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
| **Dashboard Streamlit** | Interface web com 10 paginas para gestao completa |
| **IAlex (WhatsApp)** | Agente de IA conversacional com 73 ferramentas |
| **Supabase** | Banco de dados PostgreSQL com 7+ tabelas |
| **HubSpot CRM** | Sincronizacao bidirecional de contatos e deals |
| **Brevo / Gmail** | Envio de emails com tracking completo |
| **ENEM Analytics** | Dados de desempenho de 185 mil escolas |
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
Camada 5 — Interface      : Dashboard Streamlit (10 paginas) + IAlex WhatsApp
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
        st.metric("Tools IAlex", "73 ferramentas")

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
        st.switch_page("pages/4_📥_Importar.py")

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
        st.switch_page("pages/1_🏫_Escolas.py")

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
- **Filtros** no topo: Status, Porte, Dependencia Administrativa
- **Busca** por nome ou INEP
- Clique em qualquer linha para abrir o detalhe

**Card de Detalhe**
Ao clicar em uma escola, voce ve um card completo com:
- **Dados basicos**: Nome, INEP, endereco, telefone, email
- **Classificacao**: Porte, dependencia administrativa, etapas de ensino
- **Scores**: Qualification Score, Fit Score, Tech Score, Infra Score
- **Historico**: Timeline de todas as acoes realizadas
- **Contatos**: Decisores encontrados (com Power Map)

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
        st.switch_page("pages/1_🏫_Escolas.py")

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
- **Filtro** por tipo de cargo (decisor, influenciador, operacional)
- **Enriquecimento**: Buscar dados complementares (LinkedIn, email profissional)
- **Detalhes do contato**: Historico de interacoes, emails enviados, respostas
""")

    if st.button("Ir para Contatos", key="crm_contatos"):
        st.switch_page("pages/2_👥_Contatos.py")

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
        st.switch_page("pages/3_🗺️_Mapa.py")

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
        st.switch_page("pages/4_📥_Importar.py")


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

### Como Usar
1. Selecione escolas na tabela (checkbox)
2. Clique no botao da etapa desejada
3. Aguarde o processamento (barra de progresso)
4. O status da escola e atualizado automaticamente
5. Para enviar, va em **Comunicacao** > **Aprovacao**

### Dicas
- Voce pode rodar etapas em lote (varias escolas de uma vez)
- Cada etapa depende da anterior (nao pode enriquecer sem qualificar)
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
A pagina **Comunicacao** consolida tudo relacionado a emails e mensagens.
Ela e dividida em **4 abas**: Aprovacao, Follow-ups, Templates, Metricas.
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
Gerencia templates de email reutilizaveis.

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

**Importante**: A IA usa templates como base mas SEMPRE personaliza.
Templates genericos nunca sao enviados como estao.
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

    if st.button("Ir para Inteligencia", key="intel_go"):
        st.switch_page("pages/7_🎯_Inteligencia.py")


# #############################################################################
# TAB 8 — IALEX (WHATSAPP)
# #############################################################################
with tab_ialex:
    section_header("IAlex — Assistente de Vendas via WhatsApp", "smart_toy")

    st.markdown("""
O **IAlex** e o agente de IA conversacional que opera via WhatsApp. Ele tem
acesso a **73 ferramentas** organizadas em 9 categorias. Voce pode fazer
tudo que o dashboard faz — e mais — apenas conversando.

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
    st.markdown("## Catalogo de 73 Ferramentas")

    st.markdown("### 1. Buscar Escolas (6 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Buscar no CRM** | Pesquisa escolas ja importadas | "Busque escolas privadas de Porto Alegre" |
| **Buscar no MEC** | Pesquisa na base completa de 210k | "Procure escolas no MEC em Canoas" |
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

    st.markdown("### 6. Contatos (7 ferramentas)")
    st.markdown("""
| Ferramenta | Descricao | Exemplo de uso |
|---|---|---|
| **Buscar Contato** | Pesquisa decisores | "Quem e o diretor da escola X?" |
| **Enriquecer Contato** | Busca dados complementares | "Enriqueca o contato do diretor Y" |
| **WhatsApp** | Prepara mensagem WhatsApp | "Mande WhatsApp para a diretora Z" |
| **Detalhes** | Info completa do contato | "Detalhes do contato #15" |
| **Reuniao** | Agenda/registra reuniao | "Registre reuniao com escola X amanha" |
| **Proposta** | Registra envio de proposta | "Registre proposta para escola Y" |
| **Ganho/Perdido** | Marca resultado | "Escola X virou cliente" |
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
mexer em codigo. Ela esta dividida em 3 areas:
""")

    st.markdown("## 1. Pipeline Automatico")
    st.markdown("""
Configure o IAlex para rodar o pipeline sozinho em horarios definidos.

### Parametros

| Parametro | Descricao | Padrao |
|---|---|---|
| **Horario de Inicio** | Hora que o pipeline comeca | 09:00 |
| **Horario de Fim** | Hora que o pipeline para | 18:00 |
| **Dias da Semana** | Quais dias rodar | Seg a Sex |
| **Limite Diario** | Maximo de escolas/dia | 10 |
| **Etapas Ativas** | Quais etapas rodar automaticamente | Qualificar + Enriquecer |
| **Nivel de Autonomia** | Quanto o IAlex pode decidir sozinho (1-5) | 2 |

### Niveis de Autonomia

| Nivel | Descricao |
|---|---|
| **1** | Apenas relata — nao toma nenhuma acao |
| **2** | Qualifica e enriquece, mas para antes de gerar email |
| **3** | Gera emails e coloca na fila, mas nao aprova |
| **4** | Aprova emails simples, pede confirmacao para complexos |
| **5** | Autonomia total (NAO recomendado para producao) |

**Recomendacao**: Use nivel 2 ou 3 em producao. Nivel 4+ apenas em testes.
""")

    st.divider()

    st.markdown("## 2. Memoria do IAlex")
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

    st.markdown("## 3. Health Check")
    st.markdown("""
O diagnostico do sistema verifica todos os componentes e retorna o status.

### Componentes Verificados

| Componente | O que verifica |
|---|---|
| **Supabase** | Conexao com o banco de dados |
| **Claude API** | Chave valida e disponibilidade |
| **HubSpot** | Token valido e acesso a API |
| **Brevo/Gmail** | Credenciais de email validas |
| **Apollo/Snov/Hunter** | APIs de enriquecimento disponiveis |
| **Google Maps** | API de geocodificacao ativa |
| **Tabelas do Banco** | Todas as tabelas existem e tem dados |

### Indicadores
- **Verde**: Componente funcionando normalmente
- **Amarelo**: Funcionando com limitacoes (rate limit proximo, etc.)
- **Vermelho**: Componente indisponivel ou com erro
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

    with st.expander("Cenario 5: Analise semanal de resultados"):
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
        ("Amostra Confiavel",
         "Indicador de que uma escola tem numero suficiente de participantes "
         "no ENEM (>= 10) para que a media seja estatisticamente representativa. "
         "Escolas com amostra nao confiavel devem ser tratadas com cautela."),

        ("Approval Queue",
         "Fila de aprovacao. Mecanismo que garante que NENHUM email e enviado "
         "sem revisao humana. Toda mensagem gerada pela IA passa por essa fila "
         "antes do envio."),

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

        ("Gap vs Peer",
         "Diferenca entre a media ENEM da escola e a media do seu peer group. "
         "Gap negativo = abaixo da media (P1). Gap positivo = acima (P3)."),

        ("INEP",
         "Instituto Nacional de Estudos e Pesquisas Educacionais Anisio "
         "Teixeira. Orgao do MEC responsavel pelo Censo Escolar e ENEM. "
         "Cada escola tem um codigo INEP unico (8 digitos) que e a chave "
         "primaria no nosso sistema."),

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
        "Manual IAprendo Sales Agent v1.0 — Ultima atualizacao: Abril 2026"
    )
