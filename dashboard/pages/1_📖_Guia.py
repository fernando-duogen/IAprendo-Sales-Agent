"""Pagina 1 - Guia & Manual: manual completo do IAprendo Sales Agent + IAlex.
Reescrito para cobrir TODAS as features implementadas (Items 1-8 do roadmap).
Inclui: visao geral, passo a passo, IAlex WhatsApp, autonomia, discovery,
follow-ups, ciclo semanal, duvidas frequentes."""
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
breadcrumb(["IAprendo", "Guia & Manual"])
st.markdown("# 📖 Guia & Manual de Instrucoes")
st.caption("Manual completo: dashboard, IAlex via WhatsApp, automacoes, discovery, follow-ups e regras de seguranca.")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "Visao Geral",
    "Dashboard",
    "IAlex (WhatsApp)",
    "Automacoes",
    "Discovery",
    "Follow-ups",
    "Ciclo Semanal",
    "Duvidas",
])

# =============================================================================
# TAB 1 — Visao Geral
# =============================================================================
with tab1:
    section_header("O que e o IAprendo Sales Agent?", "smart_toy")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["primary"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'Sistema <strong>hibrido IA + Humano</strong> de prospeccao B2B para a plataforma educacional IAprendo. '
        'Inclui dois canais de controle:'
        '<br/><br/>'
        '<strong>1. Dashboard (esta plataforma)</strong> — interface visual para gerenciar escolas, pipeline, emails, contatos, discovery e configuracoes.'
        '<br/>'
        '<strong>2. IAlex (WhatsApp)</strong> — agente IA com 55 ferramentas, disponivel 24/7 no seu WhatsApp para comandos rapidos, consultas e acoes.'
        '<br/><br/>'
        '<em>Regra #1: NADA e enviado para uma escola sem a sua aprovacao explicita.</em>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
    section_header("Fluxo completo", "account_tree")

    pipeline_stepper([
        {"label": "CSV MEC", "count": "212k", "color": "#9E9E9E"},
        {"label": "Discovery", "count": "Web", "color": "#7B1FA2"},
        {"label": "Importar", "count": "Filtros", "color": COLORS["primary"]},
        {"label": "Qualificar", "count": "Score IA", "color": COLORS["secondary"]},
    ])
    pipeline_stepper([
        {"label": "Enriquecer", "count": "Dados", "color": COLORS["accent"]},
        {"label": "Gerar Email", "count": "IA+RAG", "color": "#7B1FA2"},
        {"label": "Aprovar", "count": "Voce!", "color": COLORS["error"]},
        {"label": "Enviar+Track", "count": "Brevo", "color": COLORS["success"]},
    ])
    pipeline_stepper([
        {"label": "Follow-up", "count": "Comportamental", "color": COLORS["info"]},
        {"label": "Sinais", "count": "Rankings", "color": "#FF6D00"},
        {"label": "ML Score", "count": "Preditivo", "color": "#00897B"},
        {"label": "CRM", "count": "HubSpot", "color": "#1565C0"},
    ])

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Features implementadas", "checklist")

    features = [
        ("Memoria persistente", "IAlex lembra fatos, preferencias e avisos entre sessoes", "psychology"),
        ("Score preditivo ML", "Logistic Regression que preve probabilidade de fechamento", "model_training"),
        ("RAG de emails", "Novos emails sao inspirados nos que ja funcionaram (replies/clicks)", "auto_awesome"),
        ("Detector de intencao de compra", "Alertas automaticos quando escola mostra sinais quentes", "local_fire_department"),
        ("Pipeline automatico", "Roda sozinho no horario configurado, envia resumo no WhatsApp", "schedule"),
        ("Follow-ups comportamentais", "Classifica por comportamento (clicou? abriu? sumiu?) e gera follow-up adequado", "psychology"),
        ("Modo de Autonomia", "3 niveis (Manual/Semi-Auto/Full-Auto) com confirmacao dupla", "security"),
        ("Discovery inteligente", "Descobre escolas fora do MEC via web search, busca rankings/premios", "explore"),
    ]
    for nome, desc, icon in features:
        st.markdown(
            f'<div class="data-card" style="padding:10px 16px;display:flex;align-items:center;gap:12px">'
            f'<span class="material-icons-outlined" style="color:{COLORS["primary"]};font-size:22px">{icon}</span>'
            f'<div><strong style="font-size:14px">{nome}</strong>'
            f'<div style="font-size:13px;color:#757575">{desc}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 2 — Dashboard (paginas)
# =============================================================================
with tab2:
    section_header("Paginas do dashboard", "dashboard")
    st.caption("Ordem do menu lateral e funcao de cada pagina.")

    menu_items = [
        ("🏠 Painel", "Visao geral com KPIs, acoes rapidas, busca global e atividade recente", "home"),
        ("📖 Guia & Manual", "Este manual. Tudo que voce precisa saber sobre o sistema", "menu_book"),
        ("⚙️ Configuracoes", "Modo de autonomia, pipeline automatico, follow-ups automaticos", "settings"),
        ("📊 Pipeline", "Executar as etapas: qualificar, enriquecer, buscar contatos, gerar emails", "play_circle"),
        ("🎯 CRM", "Pipeline visual de vendas (Kanban) com deals por estagio", "view_kanban"),
        ("🏫 Escolas", "Gerenciar escolas: editar, excluir, ver contatos e historico", "school"),
        ("🗺️ Mapa", "Visualizacao geografica das escolas + explorar CSV completo (212k)", "map"),
        ("👥 Contatos", "Lista e hierarquia de decisores por escola (diretor, vice, coord)", "people"),
        ("✉️ Aprovacao", "AQUI VOCE APROVA OS EMAILS. Nada e enviado sem passar aqui", "task_alt"),
        ("🔄 Follow-ups", "Metricas de follow-ups, timeline por escola, deducao de emails", "autorenew"),
        ("📝 Templates", "Criar e gerenciar modelos de mensagem padrao", "description"),
        ("📥 Importar", "Filtrar e importar escolas do CSV do MEC para o banco", "cloud_upload"),
        ("🔍 Discovery", "Descobrir escolas novas via web + buscar sinais (rankings/premios)", "explore"),
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

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Passo a passo basico", "checklist")

    st.markdown("""
**Primeiro uso:**
1. Va em **📥 Importar** → selecione Estado, Cidade, Tipo → importe 50-100 escolas
2. Va em **📊 Pipeline** → rode Qualificar + Enriquecer + Contatos + Gerar Emails
3. Va em **✉️ Aprovacao** → revise cada email, edite se necessario, clique Aprovar
4. Emails aprovados serao enviados no proximo ciclo do pipeline (ou clique "Enviar aprovados")
5. Acompanhe em **🎯 CRM** e **🔄 Follow-ups**

**Depois que tiver a base rodando:**
- Configure o **pipeline automatico** em ⚙️ Configuracoes (roda sozinho toda manha)
- Ative **follow-ups automaticos** (IAlex gera follow-ups baseado em comportamento)
- Use **🔍 Discovery** para achar escolas novas fora do MEC
""")

# =============================================================================
# TAB 3 — IAlex (WhatsApp)
# =============================================================================
with tab3:
    section_header("IAlex — seu agente no WhatsApp", "chat")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["primary"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'O <strong>IAlex</strong> e um agente de IA com <strong>55 ferramentas</strong> que roda 24/7 no seu WhatsApp. '
        'Ele consulta o banco de dados, busca escolas, gera emails, roda o pipeline, '
        'envia briefings e detecta sinais de compra — tudo via mensagem de texto.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("O que PODE fazer via WhatsApp", "check_circle")

    pode = [
        ("Buscar escolas", '"Busca escolas privadas em Canoas", "Tem alguma escola La Salle no banco?"'),
        ("Importar escola", '"Importa o Colegio Anchieta de POA" (busca no MEC e adiciona ao banco)'),
        ("Detalhes de escola", '"Me fala do Colegio Bom Conselho", "Qual o score do Anchieta?"'),
        ("Buscar contatos", '"Quem e o diretor do La Salle?", "Busca contatos do Anchieta"'),
        ("Gerar email", '"Gera um email para o Marista Rosario"'),
        ("Aprovar email", '"Aprova o email do Anchieta", "Aprova todos os pendentes"'),
        ("Ver fila", '"Mostra fila de aprovacao", "Quantos emails pendentes?"'),
        ("Rodar pipeline", '"Qualifica 20 escolas", "Roda pipeline completo"'),
        ("Follow-ups", '"Quais leads estao prontos para follow-up?", "Gera follow-ups agora"'),
        ("Discovery", '"Descobre escolas bilingues em Canoas", "Busca sinais do Anchieta"'),
        ("Staging", '"Mostra as descobertas", "Aprova a escola X", "Rejeita a Y"'),
        ("Memorias", '"Lembra que o diretor do La Salle so atende de tarde"'),
        ("Score ML", '"Quais escolas tem mais chance de fechar?", "Score preditivo do top 10"'),
        ("Autonomia", '"Qual o modo de autonomia?", "Ativa o semi-auto"'),
        ("Configurar", '"Como esta o pipeline automatico?", "Muda horario para 7h"'),
        ("Estatisticas", '"Estatisticas gerais", "Funil de vendas", "Uso de APIs"'),
    ]
    for titulo, exemplos in pode:
        st.markdown(
            f'<div class="data-card" style="padding:8px 14px">'
            f'<strong style="font-size:13px;color:{COLORS["primary"]}">{titulo}</strong>'
            f'<div style="font-size:12px;color:#757575;margin-top:2px"><em>{exemplos}</em></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("O que NAO pode / NAO deve fazer", "block")

    alert_banner(
        "<strong>Regras de seguranca do IAlex:</strong><br/>"
        "• NUNCA envia email/WhatsApp para escola sem sua aprovacao (modo semi-auto/manual)<br/>"
        "• NUNCA ativa envio automatico sem a frase exata 'autorizo envio automatico'<br/>"
        "• NUNCA altera dados de outra escola por engano — cada acao se refere a escola da conversa atual<br/>"
        "• NUNCA apaga escolas ou contatos sem confirmacao explicita<br/>"
        "• Follow-ups gerados vao SEMPRE para a fila de aprovacao, nunca sao enviados direto",
        "warning",
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Briefings automaticos", "notifications_active")

    st.markdown("""
O IAlex envia mensagens proativas no seu WhatsApp:

| Horario | O que envia |
|---------|-------------|
| **08:00** | Bom dia com resumo: escolas no pipeline, pendentes, follow-ups devidos |
| **12:00** | Lembrete de emails pendentes na fila |
| **17:00** | Resumo do dia |
| **Sexta 17:30** | Relatorio semanal completo |
| **A cada 30 min** | Alertas de sinais de compra (se houver) |
| **Apos pipeline** | Resumo do pipeline automatico (se ativo) |
| **Apos follow-ups** | Resumo dos follow-ups gerados (se ativo) |
""")

# =============================================================================
# TAB 4 — Automacoes
# =============================================================================
with tab4:
    section_header("Modo de Autonomia", "security")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["error"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'O sistema tem <strong>3 niveis de autonomia</strong> que controlam o que o IAlex pode fazer sozinho:'
        '<br/><br/>'
        '<strong>🛡️ MANUAL</strong> — Zero automacao. Nada roda sozinho. Voce faz tudo manualmente.<br/>'
        '<strong>🤖 SEMI-AUTO (padrao)</strong> — IAlex gera emails e follow-ups automaticamente, '
        'mas NUNCA envia sem voce aprovar 1 a 1.<br/>'
        '<strong>⚡ FULL-AUTO</strong> — IAlex tambem envia automaticamente os que voce ja aprovou. '
        'Requer confirmacao dupla com a frase "autorizo envio automatico".'
        '</div></div>',
        unsafe_allow_html=True,
    )

    alert_banner(
        "Para mudar o modo: va em <strong>⚙️ Configuracoes</strong> (topo da pagina) "
        "ou diga ao IAlex via WhatsApp: <em>\"muda para semi-auto\"</em>.",
        "info",
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Pipeline automatico", "schedule")

    st.markdown("""
**O que faz:** Roda o pipeline (qualificar, enriquecer, contatos, gerar emails) sozinho no horario configurado.

**Como ativar:**
1. Va em **⚙️ Configuracoes** → Modo de Autonomia = Semi-Auto ou Full-Auto
2. Ative o toggle "Pipeline automatico"
3. Defina horario, dias da semana, etapas e limites
4. Salve

**Resultado:** Toda manha o IAlex roda, gera emails e envia resumo no WhatsApp. Voce so revisa a fila.

**Via WhatsApp:** *"Ativa o pipeline para rodar as 8h de segunda a sexta"*
""")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Seguranca em camadas", "shield")

    st.markdown("""
| Camada | Protecao |
|--------|----------|
| **Config** | `send_approved=False` por padrao, step "send" removido fora de full-auto |
| **Scheduler** | Nao registra jobs em modo manual |
| **Runtime** | Re-valida autonomia em cada execucao |
| **Tools WhatsApp** | Bloqueia ativar envio sem frase de confirmacao |
| **Full-Auto** | Exige frase exata "autorizo envio automatico" |
| **Auditoria** | Toda mudanca de autonomia registrada em memoria |
""")

# =============================================================================
# TAB 5 — Discovery
# =============================================================================
with tab5:
    section_header("Discovery inteligente de escolas", "explore")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid #7B1FA2">'
        '<div style="font-size:15px;line-height:1.7">'
        'Alem do CSV MEC (212k escolas), o IAlex descobre escolas novas via busca web '
        '(DuckDuckGo + GPT) e busca <strong>sinais contextuais</strong> (rankings, premios, noticias) '
        'sobre qualquer escola.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("""
**Como usar no Dashboard:**
1. Va em **🔍 Discovery** → preencha cidade, tipo e keyword (opcional: "bilingue", "Waldorf")
2. Clique **Buscar agora** → sistema busca na web e mostra resultados
3. Escolas novas entram em **staging** (status "discovered")
4. Revise: **Aprovar** (vai pro pipeline) ou **Rejeitar** (descarta)
5. Clique **Buscar sinais** para enriquecer com rankings/premios/noticias

**Como usar via WhatsApp:**
- *"Descobre escolas bilingues em Canoas"*
- *"Mostra as descobertas"*
- *"Aprova a escola X"*
- *"Busca sinais do Colegio Anchieta"* → rankings/premios salvos na memoria

**Seguranca:**
- Escolas descobertas NUNCA entram no pipeline automaticamente
- Ficam em staging ate voce aprovar manualmente
- Discovery NAO envia nada para contatos externos (so le web + escreve no banco)
""")

# =============================================================================
# TAB 6 — Follow-ups
# =============================================================================
with tab6:
    section_header("Follow-ups comportamentais", "psychology")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["info"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'O IAlex nao envia follow-ups por sequencia fixa (dia 3, 7, 14). Ele <strong>analisa o '
        'comportamento</strong> de cada lead e escolhe o follow-up certo:'
        '</div></div>',
        unsafe_allow_html=True,
    )

    tipos_fu = [
        ("🔥 Hot Click", "Lead CLICOU em link do email", "Tom comercial direto, propoe agenda", COLORS["error"]),
        ("👀 Curious Open", "Abriu 2+ vezes sem responder", "Valor adicional, sem pressao", COLORS["accent"]),
        ("📬 Silent Open", "Abriu 1x e sumiu (3+ dias)", "Lembrete gentil, 3 linhas", COLORS["info"]),
        ("🧊 Revival", "NAO abriu nada (7+ dias)", "Assunto novo, angulo diferente", "#9E9E9E"),
    ]
    for emoji_nome, sinal, estilo, color in tipos_fu:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {color};padding:10px 16px">'
            f'<strong style="font-size:14px">{emoji_nome}</strong>'
            f'<div style="font-size:13px;color:#757575">Sinal: {sinal}</div>'
            f'<div style="font-size:13px;color:#424242">Estilo: <em>{estilo}</em></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("""
**Importante:** Se o lead JA RESPONDEU ao email, o IAlex NAO manda follow-up — aciona o **detector de intencao** e alerta voce no WhatsApp.

**Todos os follow-ups passam pela fila de aprovacao.** Voce revisa antes de qualquer envio.

**Como ativar automaticos:**
- **Dashboard:** ⚙️ Configuracoes → secao "Follow-ups automaticos" → ativar + horario + tipos
- **WhatsApp:** *"Ativa os followups automaticos para rodar as 9h30"*

**Comandos WhatsApp:**
- *"Quais leads estao prontos para follow-up?"* → lista por tipo
- *"Gera follow-ups agora"* → dispara e envia resumo
""")

# =============================================================================
# TAB 7 — Ciclo Semanal
# =============================================================================
with tab7:
    section_header("Ciclo semanal recomendado", "event_repeat")

    st.markdown("""
**Com automacoes ativas (Semi-Auto), seu trabalho e minimo:**

| Dia | O que fazer | Onde | Tempo |
|-----|------------|------|-------|
| **Segunda** | Revisar resumo do IAlex no WhatsApp | WhatsApp | 2 min |
| **Terca** | Aprovar emails na fila (pipeline rodou sozinho) | ✉️ Aprovacao | 10 min |
| **Quarta** | Verificar respostas + sinais de compra | WhatsApp / CRM | 5 min |
| **Quinta** | Discovery: buscar escolas novas + aprovar staging | 🔍 Discovery | 10 min |
| **Sexta** | Checar relatorio semanal do IAlex | WhatsApp | 3 min |
| **Total** | | | **~30 min/sem** |
""")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Fases de crescimento", "trending_up")

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["info"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Semana 1-2 — Teste</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>Importar 100-200 escolas</li>'
            '<li>Rodar pipeline manual (20 qualify, 10 emails)</li>'
            '<li>Aprovar 5-10 emails, verificar qualidade</li>'
            '<li>Ajustar filtros e tom</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )
    with col_r2:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["success"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Semana 3-4 — Operacao</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>Ativar pipeline + follow-ups automaticos</li>'
            '<li>50 qualificacoes/semana</li>'
            '<li>20-30 emails/semana</li>'
            '<li>Usar Discovery para novas cidades</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )
    with col_r3:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["accent"]}">'
            '<div style="font-size:15px;font-weight:600;margin-bottom:8px">Mes 2+ — Escala</div>'
            '<ul style="font-size:13px;color:#757575;margin:0;padding-left:18px">'
            '<li>100+ qualificacoes/semana</li>'
            '<li>Expandir para novas cidades/estados</li>'
            '<li>ML preditivo identifica top oportunidades</li>'
            '<li>RAG melhora emails automaticamente</li>'
            '</ul></div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 8 — Duvidas Frequentes
# =============================================================================
with tab8:
    section_header("Perguntas Frequentes", "help_outline")

    perguntas = [
        (
            "O IAlex pode enviar emails sem eu saber?",
            "**Somente se voce ativar FULL-AUTO** (exige a frase 'autorizo envio automatico'). "
            "No modo padrao (Semi-Auto), tudo vai pra fila de aprovacao e voce decide 1 a 1.",
        ),
        (
            "Posso editar os emails antes de enviar?",
            "**Sim.** Na Fila de Aprovacao, cada email tem campo editavel. Edite antes de aprovar.",
        ),
        (
            "O que sao follow-ups comportamentais?",
            "Em vez de enviar follow-up fixo no dia 3/7/14, o sistema analisa se o lead "
            "abriu, clicou ou ignorou o email e gera um follow-up personalizado pro comportamento "
            "(hot_click, curious_open, silent_open, revival). Tudo passa pela fila de aprovacao.",
        ),
        (
            "O que e o Discovery?",
            "Funcao que descobre escolas que NAO estao no CSV do MEC — escolas novas, bilingues, "
            "internacionais, etc. Tambem busca rankings, premios e noticias sobre qualquer escola. "
            "As descobertas ficam em staging ate voce aprovar.",
        ),
        (
            "O que e o score preditivo ML?",
            "Um modelo de Machine Learning (Logistic Regression) treinado com seus dados reais "
            "que preve probabilidade de fechamento de cada escola. Retreina automaticamente todo domingo.",
        ),
        (
            "O que e o RAG de emails?",
            "Retrieval-Augmented Generation: quando o sistema gera um email novo, ele busca emails "
            "passados que tiveram resposta/click e usa como referencia de tom e estilo. Quanto mais "
            "respostas voce recebe, melhores ficam os novos emails.",
        ),
        (
            "Como o IAlex me alerta sobre sinais de compra?",
            "A cada 30 minutos, o IAlex verifica se alguma escola abriu, clicou ou respondeu ao email. "
            "Se detectar sinal forte (especialmente keywords como 'orcamento', 'reuniao'), envia alerta "
            "no WhatsApp com a escola, contato e acao recomendada.",
        ),
        (
            "Posso usar so o dashboard sem WhatsApp?",
            "**Sim.** O dashboard tem todas as funcoes. O WhatsApp (IAlex) e complementar — "
            "util quando voce esta fora do computador ou quer comandos rapidos.",
        ),
        (
            "Quanto custa rodar o sistema?",
            "~R$ 0,50 a R$ 2,00 para 20 qualificacoes + 10 emails (custo da API OpenAI/Claude). "
            "DuckDuckGo (discovery) e gratuito. Brevo: 300 emails/dia gratis. Supabase: plano free.",
        ),
        (
            "Posso usar em outro computador?",
            "**Sim.** O banco fica na nuvem (Supabase). Copie o .env e instale o projeto. "
            "O dashboard tambem esta no Streamlit Cloud (acesso por URL).",
        ),
    ]

    for pergunta, resposta in perguntas:
        with st.expander(pergunta):
            st.markdown(resposta)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Problemas comuns", "bug_report")

    st.markdown("""
| Problema | Causa provavel | Solucao |
|---------|-------|---------|
| CSV nao encontrado | Arquivo nao baixado | Baixe do MEC e salve em `data/raw/escolas_brasil.csv` |
| Discovery "nao retornou dados" | DuckDuckGo bloqueou ou sem internet | Tente novamente em 1 min |
| Email com nome errado | Contato nao encontrado corretamente | Edite na Fila de Aprovacao antes de aprovar |
| Dashboard nao abre | venv inativa | `venv/Scripts/python.exe -m streamlit run dashboard/app.py` |
| IAlex nao responde no WhatsApp | Webhook ou bridge desconectado | Reinicie: `venv/Scripts/python.exe agent/webhook_server.py` |
| HubSpot nao sincroniza | Token expirado | Gere novo token em app.hubspot.com > Private Apps |
| Pipeline nao roda automatico | Modo manual ativo | Mude para Semi-Auto em ⚙️ Configuracoes |
""")
