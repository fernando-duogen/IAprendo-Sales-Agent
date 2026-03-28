"""Pagina 10 - Guia de Uso: manual interativo passo a passo.
Redesigned com Material Design theme — section cards, visual hierarchy, expandable FAQ."""
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, section_header, alert_banner,
    breadcrumb, pipeline_stepper, metric_card, COLORS,
)

apply_theme_no_config()

# --- Header ---
breadcrumb(["IAprendo", "Guia de Uso"])
st.markdown("# Guia de Uso")
st.caption("Manual completo para usar o sistema do zero ao resultado.")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "O que e o sistema",
    "Passo a Passo",
    "Ciclo Semanal",
    "Expandir Regioes",
    "Duvidas Frequentes",
])

# =============================================================================
# TAB 1 — O que e o sistema
# =============================================================================
with tab1:
    section_header("O que e o IAprendo Sales Agent?", "smart_toy")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["primary"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'Este sistema e um <strong>assistente de vendas semi-automatico</strong> que ajuda voce a encontrar '
        'escolas para oferecer a plataforma IAprendo, pesquisar o(a) diretor(a) responsavel, '
        'escrever um e-mail personalizado e, somente depois da <strong>sua aprovacao</strong>, enviar a mensagem.'
        '<br/><br/>'
        '<em>Resumo: A IA faz o trabalho pesado -- voce decide o que vai e o que nao vai.</em>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    # Fluxo como stepper visual
    st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
    section_header("Fluxo Completo", "account_tree")

    pipeline_stepper([
        {"label": "CSV MEC", "count": "210k", "color": "#9E9E9E"},
        {"label": "Importar", "count": "Filtros", "color": COLORS["primary"]},
        {"label": "Qualificar", "count": "Score", "color": COLORS["secondary"]},
        {"label": "Enriquecer", "count": "Dados", "color": COLORS["accent"]},
    ])

    pipeline_stepper([
        {"label": "Gerar Email", "count": "IA", "color": "#7B1FA2"},
        {"label": "Aprovar", "count": "Voce!", "color": COLORS["error"]},
        {"label": "Enviar", "count": "Brevo", "color": COLORS["success"]},
        {"label": "Tracking", "count": "CRM", "color": COLORS["info"]},
    ])

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Pre-requisito: o CSV do MEC", "download")

    alert_banner(
        "<strong>Antes de comecar</strong>, voce precisa do arquivo com todas as escolas do Brasil.",
        "info",
    )

    st.markdown(
        '<div class="data-card">'
        '<ol style="font-size:14px;line-height:1.8;margin:0;padding-left:20px">'
        '<li>Acesse: <a href="https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/sinopses-estatisticas" target="_blank">gov.br/inep - Sinopses Estatisticas</a></li>'
        '<li>Baixe o Censo Escolar mais recente</li>'
        '<li>Salve como <strong>escolas_brasil.csv</strong> dentro de <strong>data/raw/</strong></li>'
        '<li>Tamanho: ~80 MB, ~210.000 linhas</li>'
        '</ol>'
        '<div style="font-size:13px;color:#757575;margin-top:8px">Se o arquivo ja estiver la, voce esta pronto.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Menu lateral -- ordem logica", "menu")

    menu_items = [
        ("1 - Pipeline", "Selecione escolas e execute as etapas: qualificar, enriquecer, contatos e emails", "play_circle"),
        ("2 - Visao Geral", "Metricas do pipeline: funil, scores, status", "dashboard"),
        ("3 - Escolas", "Gerenciar escolas: editar dados, excluir, ver contatos e historico", "school"),
        ("4 - Mapa", "Visualizacao geografica das escolas importadas OU explorar o CSV completo (212k)", "map"),
        ("5 - Contatos", "Mapa de poder: decisores-chave por escola (diretor, vice, coordenador)", "people"),
        ("6 - Fila de Aprovacao", "AQUI VOCE APROVA OS E-MAILS. Acoes em massa disponiveis.", "task_alt"),
        ("8 - Templates", "Criar e gerenciar modelos de mensagem padrao", "description"),
        ("9 - Importar Escolas", "Filtrar e importar escolas do CSV do MEC para o banco", "cloud_upload"),
        ("10 - Guia de Uso", "Este manual.", "menu_book"),
    ]
    for nome, desc, icon in menu_items:
        st.markdown(
            f'<div class="data-card" style="padding:10px 16px;display:flex;align-items:center;gap:12px">'
            f'<span class="material-icons-outlined" style="color:{COLORS["primary"]};font-size:20px">{icon}</span>'
            f'<div><strong style="font-size:14px">{nome}</strong>'
            f'<div style="font-size:13px;color:#757575">{desc}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 2 — Passo a Passo
# =============================================================================
with tab2:
    section_header("Como usar -- Passo a Passo", "checklist")

    steps_data = [
        (
            "PASSO 1 -- Importar escolas do CSV",
            "cloud_upload",
            COLORS["primary"],
            True,
            """**Onde:** Menu lateral -> **9 - Importar Escolas**

**O que fazer:**
1. Selecione o **Estado (UF)** -- ex: RS
2. Selecione a **Cidade** -- ex: Porto Alegre
3. Escolha o **Tipo de escola** (Municipal, Estadual, Privada, Federal)
4. Escolha o **Porte** -- recomendo comecar com escolas maiores
5. Veja o numero de escolas encontradas
6. No campo **"Limite de importacao"**, coloque 100 na primeira vez
7. Clique em **"Confirmar e Importar Agora"**

**Dica:** Comece com 50 a 200 escolas para testar o fluxo.""",
        ),
        (
            "PASSO 2 -- Executar o pipeline",
            "play_circle",
            COLORS["secondary"],
            False,
            """**Onde:** Menu lateral -> **1 - Pipeline**

**O que acontece:**
- Voce seleciona quais escolas quer processar (filtros, presets ou manual)
- Executa etapas individualmente ou todas de uma vez
- A IA qualifica cada escola (score 0-100)
- Para escolas com score alto, busca contatos e gera e-mail personalizado

**O que fazer:**
1. Selecione escolas (use "Top 10 por score" ou os filtros)
2. Clique nas etapas do pipeline que deseja executar
3. Ou clique em **"Pipeline Completo"** para rodar tudo de uma vez

**Anti-duplicata:** O pipeline NAO gera mensagem para escolas que ja tem mensagem pendente na fila.

**Custo:** ~R$ 0,50 a R$ 2,00 para 20 qualificacoes + 10 e-mails

**Pelo terminal:**""",
        ),
        (
            "PASSO 3 -- Revisar e aprovar os e-mails (OBRIGATORIO)",
            "task_alt",
            COLORS["error"],
            False,
            """**Onde:** Menu lateral -> **6 - Fila de Aprovacao**

**Este e o passo mais importante.** Nenhum e-mail e enviado sem a sua aprovacao.

**O que fazer:**
1. Acesse a **Fila de Aprovacao**
2. Para cada e-mail: leia, edite se necessario, clique **Aprovar** ou **Rejeitar**
3. Verifique que o e-mail do destinatario esta correto

**Acoes em massa:**
- Clique em "Acoes em massa" no topo para **rejeitar todas**, **excluir todas** ou **aprovar todas** de uma vez

**O que verificar antes de aprovar:**
- Nome da escola e do(a) diretor(a) corretos?
- Tom adequado?
- Link de agendamento presente? (meetings.hubspot.com)
- Nao parece generico?""",
        ),
        (
            "PASSO 4 -- Enviar os e-mails aprovados",
            "send",
            COLORS["success"],
            False,
            """**Quando:** Apos aprovar os e-mails na Fila de Aprovacao

**Automatico:** O pipeline envia os aprovados na proxima execucao.

**Manual (enviar na hora):**
```bash
venv/Scripts/python.exe -m workflows.send_approved
```

**Limite:** Brevo permite ate 300 e-mails/dia no plano gratuito.

**HubSpot:** Apos o envio, o sistema registra automaticamente:
- Nota de atividade no Contact e Company
- Deal atualizado para stage "Email Enviado" """,
        ),
        (
            "PASSO 5 -- Acompanhar os resultados",
            "analytics",
            COLORS["info"],
            False,
            """**Onde:** Menu lateral -> **2 - Visao Geral** ou **3 - Escolas**

| Status | Significado |
|--------|-------------|
| Novo | Escola importada, ainda nao processada |
| Qualificado | IA deu nota >= 70, escola promissora |
| Enriquecido | Diretor(a) e e-mail encontrados |
| Contatado | E-mail enviado |
| Respondeu | Escola respondeu ao seu e-mail |

**Gestao de escolas:**
- Na pagina **3 - Escolas**, clique em **"Ver"** para abrir os detalhes
- Edite dados (telefone, website, status)
- Veja contatos, mensagens e historico
- Exclua escolas ou limpe a fila de mensagens
- Acoes em massa: selecione varias e exclua ou altere status

**Mapa:** Use o **4 - Mapa** para ver as escolas. Mude para "Explorar CSV Completo" para visualizar todas as 212k escolas do Brasil.

**HubSpot:** Acompanhe deals e atividades em https://app.hubspot.com""",
        ),
    ]

    for title, icon, color, expanded, content in steps_data:
        with st.expander(title, expanded=expanded):
            st.markdown(content)

# =============================================================================
# TAB 3 — Ciclo Semanal
# =============================================================================
with tab3:
    section_header("Ciclo semanal recomendado", "event_repeat")
    st.markdown(
        "Para ter resultados consistentes, siga este ritual. "
        "Leva menos de **30 minutos por semana**."
    )
    st.markdown("""
| Dia | O que fazer | Onde | Tempo |
|-----|------------|------|-------|
| **Segunda** | Rodar pipeline (qualificar 30, escrever 15) | 1 - Pipeline | 5 min |
| **Terca** | Revisar e aprovar mensagens | 6 - Fila de Aprovacao | 15 min |
| **Quarta** | Verificar respostas | Seu e-mail ou HubSpot | 5 min |
| **Sexta** | Checar metricas da semana | 2 - Visao Geral | 5 min |
""")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Ritmo de crescimento", "trending_up")

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["info"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Semana 1-2 -- Teste</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>Importar 100 a 200 escolas</li>'
            '<li>Qualificar 20, escrever 10</li>'
            '<li>Aprovar 5 a 10 e-mails</li>'
            '<li>Verificar qualidade</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )
    with col_r2:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["success"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Semana 3-4 -- Operacao</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>50 qualificacoes/semana</li>'
            '<li>20 a 30 e-mails/semana</li>'
            '<li>Monitorar taxa de resposta</li>'
            '<li>Ajustar filtros</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )
    with col_r3:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["accent"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Mes 2+ -- Escala</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>100+ qualificacoes/semana</li>'
            '<li>Expandir para outras cidades</li>'
            '<li>Analisar padroes de resposta</li>'
            '<li>Otimizar mensagens</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 4 — Expandir Regioes
# =============================================================================
with tab4:
    section_header("Como expandir para outras cidades e estados", "public")
    st.markdown(
        "O sistema comeca em **Porto Alegre - RS**, mas voce pode expandir para qualquer regiao "
        "usando a pagina **9 - Importar Escolas**. Tambem pode explorar o mapa com todas as 212k "
        "escolas do CSV na pagina **4 - Mapa** (modo 'Explorar CSV Completo') para identificar "
        "regioes promissoras antes de importar."
    )

    st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
    section_header("Estrategia de expansao", "rocket_launch")

    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["primary"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Fase 1 -- Base local</div>'
            '<div style="font-size:14px;font-weight:600;color:#1976D2;margin-bottom:4px">Porto Alegre (RS)</div>'
            '<div style="font-size:13px;color:#757575">Dominar a cidade natal, calibrar os e-mails, '
            'entender o comportamento.</div></div>',
            unsafe_allow_html=True,
        )
    with col_e2:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["secondary"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Fase 2 -- Estado</div>'
            '<div style="font-size:14px;font-weight:600;color:#00897B;margin-bottom:4px">Rio Grande do Sul</div>'
            '<div style="font-size:13px;color:#757575">Caxias do Sul, Pelotas, Canoas quando POA estiver funcionando.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with col_e3:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["accent"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Fase 3 -- Brasil</div>'
            '<div style="font-size:14px;font-weight:600;color:#FF6D00;margin-bottom:4px">Grandes centros</div>'
            '<div style="font-size:13px;color:#757575">SP, RJ, BH, Curitiba, Fortaleza. '
            'Priorize cidades com muitas escolas privadas.</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown("""
**Como importar nova regiao:**
1. Va em **9 - Importar Escolas**
2. Selecione o novo estado e cidade
3. Configure os filtros
4. Clique em **Confirmar e Importar**

**Importante:** O banco **nunca duplica** escolas -- cada escola tem um Codigo INEP unico.
""")

# =============================================================================
# TAB 5 — Duvidas Frequentes
# =============================================================================
with tab5:
    section_header("Perguntas Frequentes", "help_outline")

    perguntas = [
        (
            "O agente vai enviar e-mails sem eu saber?",
            "**Nunca.** Toda mensagem passa pela **Fila de Aprovacao**. Voce precisa clicar "
            "Aprovar para cada e-mail. Essa regra nao pode ser desativada.",
        ),
        (
            "Posso editar os e-mails antes de enviar?",
            "**Sim.** Na Fila de Aprovacao, cada e-mail tem campo editavel. "
            "Edite antes de aprovar.",
        ),
        (
            "O que acontece se eu rejeitar uma mensagem?",
            "A mensagem muda para status 'rejeitada'. A escola permanece no banco e pode "
            "receber uma nova mensagem no proximo pipeline. O pipeline anti-duplicata "
            "so bloqueia se houver mensagem 'pendente' ou 'aprovada'.",
        ),
        (
            "Posso rejeitar ou excluir todas as mensagens de uma vez?",
            "**Sim.** Na Fila de Aprovacao, clique em 'Acoes em massa' no topo. "
            "Voce pode rejeitar todas, excluir todas ou aprovar todas.",
        ),
        (
            "Como excluo uma escola do banco?",
            "Na pagina **3 - Escolas**, clique em 'Ver' na escola desejada. "
            "Na tela de detalhes, clique em 'Excluir escola'. Isso remove a escola "
            "e todos os dados relacionados (contatos, mensagens, historico).",
        ),
        (
            "O que e o link de agendamento nos e-mails?",
            "Os e-mails incluem automaticamente o link do HubSpot Meeting "
            "(meetings.hubspot.com/fernando612). O prospect pode agendar uma conversa "
            "direto na sua agenda, sem troca de e-mails.",
        ),
        (
            "O que o HubSpot faz neste sistema?",
            "O HubSpot e o CRM que rastreia tudo: Companies (escolas), Contacts (decisores), "
            "Deals (oportunidades) e atividades (e-mails enviados). Quando o pipeline envia "
            "um e-mail, o HubSpot e atualizado automaticamente.",
        ),
        (
            "O pipeline gera mensagens duplicadas?",
            "**Nao.** O sistema verifica se a escola ja tem mensagem pendente ou "
            "aprovada antes de gerar uma nova. So gera se a anterior foi rejeitada ou enviada.",
        ),
        (
            "Quanto custa rodar o pipeline?",
            "~R$ 0,50 a R$ 2,00 para 20 qualificacoes + 10 e-mails. "
            "O custo maior e do Claude Sonnet (escrita). Comece pequeno.",
        ),
        (
            "Posso usar o sistema em outro computador?",
            "**Sim.** O banco fica na nuvem (Supabase). Copie o .env e instale o projeto.",
        ),
    ]

    for pergunta, resposta in perguntas:
        with st.expander(pergunta):
            st.markdown(resposta)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Problemas comuns", "bug_report")

    st.markdown("""
| Problema | Causa | Solucao |
|---------|-------|---------|
| CSV nao encontrado | Arquivo nao baixado | Baixe do MEC e salve em data/raw/escolas_brasil.csv |
| Pipeline demora muito | Volume grande | Reduza o numero de qualificacoes |
| E-mail com nome errado | Contato nao encontrado | Edite na Fila de Aprovacao ou em Escolas > Contatos |
| Dashboard nao abre | venv inativa | `venv/Scripts/python.exe -m streamlit run dashboard/app.py` |
| Erro "No module named..." | Pacote corrompido | Remova a pasta do pacote em venv/ e reinstale com pip |
| HubSpot nao sincroniza | Token expirado | Gere novo token em app.hubspot.com > Private Apps |
""")
