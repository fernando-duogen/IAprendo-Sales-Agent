"""Pagina 1 - Guia & Manual Completo do IAprendo Sales Agent.
Reescrito com todas as features, fluxograma visual e passo a passo didatico."""
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

breadcrumb(["IAprendo", "Guia & Manual"])
st.markdown("# 📖 Guia & Manual Completo")
st.caption("Tudo que voce precisa saber para usar o sistema — do zero ao resultado.")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "Visao Geral",
    "Fluxograma",
    "Passo a Passo",
    "IAlex (WhatsApp)",
    "Configuracoes",
    "Features",
    "Paginas",
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
        '<div style="font-size:15px;line-height:1.8">'
        'Sistema <strong>hibrido IA + Humano</strong> de prospeccao B2B para escolas. '
        'Voce tem dois canais de controle:'
        '<br/><br/>'
        '<strong>1. Dashboard</strong> — esta plataforma visual com 13 paginas<br/>'
        '<strong>2. IAlex</strong> — agente IA com 58 ferramentas no seu WhatsApp, 24/7<br/><br/>'
        '<em style="color:#D32F2F">Regra #1: NADA e enviado para uma escola sem a sua aprovacao explicita.</em>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
    section_header("Como funciona em 4 etapas", "account_tree")

    pipeline_stepper([
        {"label": "1. Importar", "count": "CSV MEC", "color": "#9E9E9E"},
        {"label": "2. Qualificar", "count": "Score IA", "color": COLORS["primary"]},
        {"label": "3. Enriquecer", "count": "Contatos", "color": COLORS["secondary"]},
        {"label": "4. Prospectar", "count": "Emails", "color": COLORS["accent"]},
    ])

    st.markdown("""
**Etapa 1 — Importar**: Voce seleciona escolas do CSV do MEC (212k) por cidade, tipo e porte.

**Etapa 2 — Qualificar**: A IA analisa cada escola e da um score de 0 a 100 (quanto maior, melhor fit).

**Etapa 3 — Enriquecer**: O sistema busca contatos (diretor, coordenador, email, telefone) via web.

**Etapa 4 — Prospectar**: A IA gera emails personalizados. Voce revisa, edita e aprova. So entao sao enviados.

Apos o envio, o sistema acompanha: abriu? clicou? respondeu? E gera follow-ups automaticos baseados no comportamento.
""")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("O que torna este sistema especial", "star")

    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            '<div class="data-card" style="text-align:center;padding:16px">'
            '<div style="font-size:28px">🤖</div>'
            '<strong>58 ferramentas IA</strong><br/>'
            '<span style="font-size:13px;color:#757575">Tudo via WhatsApp: buscar, gerar, aprovar, agendar</span>'
            '</div>', unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            '<div class="data-card" style="text-align:center;padding:16px">'
            '<div style="font-size:28px">🛡️</div>'
            '<strong>Controle total</strong><br/>'
            '<span style="font-size:13px;color:#757575">Nada sai sem sua aprovacao. 3 niveis de autonomia.</span>'
            '</div>', unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            '<div class="data-card" style="text-align:center;padding:16px">'
            '<div style="font-size:28px">🧠</div>'
            '<strong>Aprende sozinho</strong><br/>'
            '<span style="font-size:13px;color:#757575">ML preditivo, RAG, memoria, follow-ups comportamentais</span>'
            '</div>', unsafe_allow_html=True,
        )

# =============================================================================
# TAB 2 — Fluxograma
# =============================================================================
with tab2:
    section_header("Fluxograma completo do sistema", "schema")

    st.caption("Este diagrama mostra TODAS as possibilidades em cada etapa.")

    st.markdown("""
```
╔═══════════════════════════════════════════════════════════════════╗
║                    IAPRENDO SALES AGENT                          ║
║                     Fluxograma Completo                          ║
╚═══════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────┐
│  FASE 1: ABASTECER O BANCO                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  CSV MEC (212k escolas) ──→ Importar (filtros: cidade, tipo,    │
│                              porte, nivel de ensino)             │
│                              ↓                                   │
│                         Banco de dados                           │
│                         (status: raw)                            │
│                                                                  │
│  Via Dashboard: pagina 📥 Importar                               │
│  Via WhatsApp: "importa escolas privadas de Canoas"             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 2: QUALIFICAR E ENRIQUECER                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Escolas raw ──→ Qualificacao IA ──→ Score 0-100                │
│                   (GPT analisa)       (status: qualified)        │
│                       ↓                                          │
│              Enriquecimento ──→ Site, telefone, contatos         │
│              (web scraping)     (status: enriched)               │
│                       ↓                                          │
│              Busca de decisores ──→ Diretor, email, cargo       │
│              (Apollo, DuckDuckGo)                                │
│                                                                  │
│  Automatico: pipeline roda no horario configurado               │
│  Manual: dashboard 📊 Pipeline ou WhatsApp "roda pipeline"      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 3: GERAR EMAILS                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Escola enriched ──→ Gerar email                                │
│                       ├─ Modo IA (personalizado do zero)        │
│                       └─ Modo Template (texto padrao)           │
│                              ↓                                   │
│                    Persona adaptativa?                            │
│                    ├─ Padrao (tom fixo)                          │
│                    └─ Adaptativo (inovadora/conservadora/        │
│                       pragmatica/entusiasta)                     │
│                              ↓                                   │
│                    Calendario inteligente                         │
│                    (agendado no melhor horario:                   │
│                     tracking + feriados + fase letiva)            │
│                              ↓                                   │
│                    ╔══════════════════════╗                       │
│                    ║  FILA DE APROVACAO   ║                       │
│                    ║  (status: pending)   ║                       │
│                    ╚══════════════════════╝                       │
│                                                                  │
│  Via Dashboard: pagina ✉️ Aprovacao                               │
│  Via WhatsApp: "mostra fila" → revisar → aprovar                │
│                "vamos prospectar" → sessao guiada                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 4: REVISAR E APROVAR                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Email pendente ──→ Fernando revisa                              │
│                      ├─ Aprovar (envia agora ou agendado)       │
│                      ├─ Editar (colar texto ou dar instrucoes)  │
│                      ├─ Reescrever (IAlex reescreve via GPT)    │
│                      ├─ Agendar (data/hora de envio)            │
│                      └─ Rejeitar                                │
│                              ↓                                   │
│                    Envio automatico                               │
│                    ├─ Email: via Brevo (com assinatura)          │
│                    ├─ WhatsApp: via bridge (se multichannel)     │
│                    └─ LinkedIn: notificacao manual                │
│                              ↓                                   │
│                    Tracking automatico                            │
│                    (abriu? clicou? respondeu? bounceou?)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 5: FOLLOW-UPS COMPORTAMENTAIS                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tracking analisa comportamento:                                 │
│                                                                  │
│  🔥 Clicou no link ──→ hot_click (tom comercial, agenda)        │
│  👀 Abriu 2+ vezes ──→ curious_open (valor adicional)           │
│  📬 Abriu 1x e sumiu ──→ silent_open (lembrete gentil)          │
│  🧊 Nao abriu nada ──→ revival (angulo novo, assunto novo)      │
│  💬 Respondeu ──→ ALERTA de intencao de compra (WhatsApp)       │
│                                                                  │
│  Follow-up gerado ──→ Fila de aprovacao (mesmo fluxo)           │
│  Maximo 3 follow-ups por escola (exceto hot_click)              │
│                                                                  │
│  Multichannel: email → WhatsApp → email → LinkedIn              │
│  (se ativado em Configuracoes)                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  FASE 6: INTELIGENCIA CONTINUA                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  🧠 ML Preditivo ──→ Score de probabilidade de fechamento       │
│  📚 RAG ──→ Novos emails inspirados nos que funcionaram         │
│  💡 Memoria ──→ Lembra fatos sobre cada escola entre sessoes    │
│  🔍 Enriquecimento web ──→ Rankings, premios, noticias          │
│  📅 Outlook Calendar ──→ Briefing pre-reuniao + pos-reuniao     │
│  📊 Smart Scheduler ──→ Envia no melhor horario por escola      │
│                                                                  │
│  Tudo alimenta o proximo ciclo automaticamente                   │
└─────────────────────────────────────────────────────────────────┘
```
""")

    alert_banner(
        "O fluxo acima e AUTOMATICO quando configurado. Fernando so precisa: "
        "(1) aprovar emails na fila, (2) responder resumos pos-reuniao. "
        "Todo o resto o IAlex faz sozinho.",
        "info",
    )

# =============================================================================
# TAB 3 — Passo a Passo (novo usuario)
# =============================================================================
with tab3:
    section_header("Passo a passo — do zero ao primeiro email", "checklist")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["primary"] + '">'
        '<div style="font-size:14px;line-height:1.7">'
        'Se voce nunca usou o sistema, siga estes 7 passos na ordem. '
        'Leva cerca de <strong>20 minutos</strong> para enviar seu primeiro email.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    steps = [
        ("PASSO 1 — Importar escolas", "cloud_upload", COLORS["primary"], True, """
**Onde:** Menu → 📥 Importar (ou WhatsApp: "importa escolas privadas de Porto Alegre")

1. Selecione **Estado** (ex: RS) e **Cidade** (ex: Porto Alegre)
2. Escolha **Tipo** (Privada, Publica) e **Porte** (comece com maiores)
3. Defina limite: **50-100 escolas** na primeira vez
4. Clique **Confirmar e Importar**

_Dica: comece pequeno (50 escolas) para testar o fluxo._"""),
        ("PASSO 2 — Rodar o pipeline", "play_circle", COLORS["secondary"], False, """
**Onde:** Menu → 📊 Pipeline (ou WhatsApp: "roda pipeline")

O pipeline faz 4 coisas em sequencia:
1. **Qualifica** cada escola (score 0-100)
2. **Enriquece** com dados da web (site, telefone)
3. **Busca contatos** (diretor, coordenador, emails)
4. **Gera emails** personalizados

Selecione as escolas e clique **Pipeline Completo** ou rode etapa por etapa.

_Custo: ~R$ 0,50 a R$ 2,00 para 20 qualificacoes + 10 emails._"""),
        ("PASSO 3 — Revisar e aprovar emails", "task_alt", COLORS["error"], False, """
**Onde:** Menu → ✉️ Aprovacao (ou WhatsApp: "mostra fila")

Este e o passo mais importante. Voce revisa cada email antes do envio:

- **Aba Pendentes**: emails aguardando sua revisao
- Para cada email: leia, edite se necessario
- Pode **reescrever** (dar instrucoes ao IAlex) ou **colar texto** editado
- Verifique o contato, assunto e link de agendamento
- Clique **Aprovar** (com ou sem agendamento de horario)
- Ou **Rejeitar** se nao quiser enviar

_Pelo WhatsApp: "mostra email 1 completo" → revisar → "aprova"_"""),
        ("PASSO 4 — Acompanhar envios", "analytics", COLORS["info"], False, """
**Onde:** ✉️ Aprovacao → aba **📤 Enviadas** | Menu → 🎯 CRM

Apos aprovar, o email e enviado automaticamente (a cada 5 minutos).

Na aba **Enviadas** voce ve: escola, assunto, data, tracking (abriu/clicou/respondeu).

No **CRM** (Kanban) voce ve o funil visual de vendas.

_IAlex avisa no WhatsApp quando detecta sinais de compra (escola que clicou ou respondeu)._"""),
        ("PASSO 5 — Follow-ups automaticos", "autorenew", "#FF6D00", False, """
**Onde:** Automatico (se configurado em ⚙️ Configuracoes)

O IAlex analisa o comportamento de cada escola apos o email:
- 🔥 **Clicou** → follow-up comercial direto
- 👀 **Abriu 2+ vezes** → valor adicional
- 📬 **Abriu 1x e sumiu** → lembrete gentil
- 🧊 **Nao abriu** → angulo totalmente novo

Cada follow-up vai para a fila de aprovacao — voce revisa antes de enviar.

_Ative em: ⚙️ Configuracoes → Follow-ups automaticos → ON_"""),
        ("PASSO 6 — Configurar automacoes (opcional)", "settings", "#7B1FA2", False, """
**Onde:** Menu → ⚙️ Configuracoes

Quando estiver confortavel, ative as automacoes:

- **Modo de Autonomia**: Semi-Auto (gera tudo, voce aprova)
- **Pipeline automatico**: roda todo dia no horario que voce definir
- **Follow-ups automaticos**: gera follow-ups comportamentais diariamente
- **Persona adaptativa**: IA adapta tom por tipo de escola
- **Multichannel**: alterna entre email, WhatsApp e LinkedIn
- **Calendario inteligente**: envia no melhor horario por escola

_Comece com Semi-Auto + Pipeline automatico. Adicione o resto gradualmente._"""),
        ("PASSO 7 — Usar o IAlex no dia a dia", "chat", COLORS["success"], False, """
**Onde:** WhatsApp — mande qualquer mensagem para o IAlex

O IAlex e seu assistente 24/7. Exemplos do que pode fazer:

- "vamos prospectar" → sessao guiada escola a escola
- "mostra fila" → revisar emails pendentes
- "busca escolas privadas em Canoas" → busca no MEC
- [compartilhar localizacao] → modo campo (escola proxima)
- "envia teste pra mim" → testar assinatura e links
- "menu" → ver todas as opcoes

_Dica: fale naturalmente, como com um colega. Nao precisa de comandos exatos._"""),
    ]

    step_pages = {
        "PASSO 1": "pages/11_📥_Importar.py",
        "PASSO 2": "pages/3_📊_Pipeline.py",
        "PASSO 3": "pages/8_✉️_Aprovacao.py",
        "PASSO 4": "pages/3_📊_Pipeline.py",
        "PASSO 5": "pages/2_⚙️_Configuracoes.py",
        "PASSO 6": "pages/2_⚙️_Configuracoes.py",
    }

    for title, icon, color, expanded, content in steps:
        with st.expander(title, expanded=expanded):
            st.markdown(content)
            # Botao que leva a pagina correspondente
            step_key = title.split(" —")[0].strip()
            page = step_pages.get(step_key)
            if page:
                if st.button(f"Ir para esta pagina →", key=f"step_{step_key}", use_container_width=True):
                    st.switch_page(page)

# =============================================================================
# TAB 4 — IAlex (WhatsApp)
# =============================================================================
with tab4:
    section_header("IAlex — seu agente no WhatsApp", "chat")

    st.markdown(
        '<div class="data-card" style="border-left:4px solid ' + COLORS["primary"] + '">'
        '<div style="font-size:15px;line-height:1.7">'
        'O <strong>IAlex</strong> e um agente de IA com <strong>58 ferramentas</strong> que roda no seu WhatsApp. '
        'Fale naturalmente — ele entende portugues livre.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### O que pode fazer (por categoria)")

    categorias = [
        ("🔍 Buscar escolas", [
            '"busca escolas privadas em Canoas"',
            '"tem escola La Salle no banco?"',
            '[compartilhar localizacao] → modo campo',
            '"escolas proximas num raio de 3km"',
        ]),
        ("📊 Pipeline e qualificacao", [
            '"roda pipeline" / "qualifica 20 escolas"',
            '"vamos prospectar" → sessao guiada',
            '"score preditivo top 10"',
            '"estatisticas gerais"',
        ]),
        ("✉️ Emails e comunicacao", [
            '"mostra fila" / "mostra email 1 completo"',
            '"reescreve mais curto" / "tira a parte do ENEM"',
            '"aprova" / "aprova pra segunda 8h"',
            '"envia teste pra mim" (testar assinatura)',
        ]),
        ("🔄 Follow-ups e sinais", [
            '"quais leads estao quentes?"',
            '"gera follow-ups agora"',
            '"busca sinais do Anchieta"',
            '"enriquece escolas de Canoas"',
        ]),
        ("🤖 Automacoes e config", [
            '"qual modo de autonomia?"',
            '"ativa pipeline pra 8h de seg a sex"',
            '"ativa follow-ups automaticos"',
            '"muda pra persona adaptativa"',
        ]),
        ("📅 Calendario e reunioes", [
            '"me mostra minha agenda"',
            '"a reuniao com o Marista foi boa"',
            '"lembra que o diretor do La Salle so atende de tarde"',
        ]),
    ]

    for cat_title, examples in categorias:
        with st.expander(cat_title):
            for ex in examples:
                st.markdown(f"- {ex}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    section_header("Regras de seguranca", "security")

    alert_banner(
        "• IAlex NUNCA envia email/WhatsApp sem sua aprovacao (modo semi-auto)<br/>"
        "• Ativar envio automatico (full-auto) exige frase exata 'autorizo envio automatico'<br/>"
        "• Antes de aprovar, IAlex SEMPRE mostra o texto final e pede confirmacao<br/>"
        "• Follow-ups vao para a fila de aprovacao, nunca sao enviados direto",
        "warning",
    )

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    section_header("Briefings automaticos", "notifications_active")

    st.markdown("""
| Horario | O que o IAlex envia no WhatsApp |
|---|---|
| **08:00** | Bom dia + resumo do dia (escolas, pendentes, follow-ups) |
| **12:00** | Lembrete de emails pendentes |
| **17:00** | Resumo do dia |
| **Sexta 17:30** | Relatorio semanal |
| **A cada 30 min** | Alertas de sinais de compra |
| **Apos pipeline** | Resumo do que foi gerado |
| **30 min antes de reuniao** | Briefing completo da escola (Outlook) |
| **Apos reuniao** | Pede resumo do resultado |
""")

# =============================================================================
# TAB 5 — Configuracoes
# =============================================================================
with tab5:
    section_header("Tudo que voce pode configurar", "tune")

    configs = [
        ("🛡️ Modo de Autonomia", "Manual (zero automacao) | Semi-Auto (gera, nao envia) | Full-Auto (envia aprovados)", "Padrao: Semi-Auto"),
        ("🤖 Pipeline automatico", "Horario, dias da semana, etapas (qualificar, enriquecer, contatos, emails), limites", "Padrao: desabilitado"),
        ("🔄 Follow-ups automaticos", "Horario, limite por dia, tipos comportamentais permitidos", "Padrao: desabilitado"),
        ("🎭 Persona de comunicacao", "Padrao (tom fixo) ou Adaptativo (IA adapta por escola)", "Padrao: Padrao"),
        ("📧 Assinatura de email", "Texto + imagem (logo) + link clicavel", "Pagina Templates"),
        ("📱 Multichannel", "Email + WhatsApp + LinkedIn. Checkboxes por canal, presets rapidos", "Padrao: so email"),
        ("⏰ Agendamento de envio", "Data/hora por email (individual ou em massa)", "Toggle na aprovacao"),
        ("📅 Calendario inteligente", "Horario otimo baseado em tracking + feriados + fase letiva", "Automatico"),
    ]

    for nome, desc, padrao in configs:
        st.markdown(
            f'<div class="data-card" style="padding:10px 16px">'
            f'<strong style="font-size:14px">{nome}</strong>'
            f'<div style="font-size:13px;color:#757575;margin-top:2px">{desc}</div>'
            f'<div style="font-size:12px;color:{COLORS["primary"]};margin-top:2px"><em>{padrao}</em></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.caption("Todas as configuracoes estao em: Menu → ⚙️ Configuracoes")

# =============================================================================
# TAB 6 — Features
# =============================================================================
with tab6:
    section_header("Todas as features implementadas", "auto_awesome")

    features = [
        ("Memoria persistente", "IAlex lembra fatos, preferencias e avisos entre sessoes", "psychology"),
        ("Score preditivo ML", "Logistic Regression que preve probabilidade de fechamento", "model_training"),
        ("RAG de emails", "Novos emails inspirados nos que ja funcionaram", "auto_awesome"),
        ("Detector de intencao de compra", "Alertas automaticos quando escola mostra sinais quentes", "local_fire_department"),
        ("Pipeline automatico", "Roda sozinho no horario configurado", "schedule"),
        ("Follow-ups comportamentais", "4 tipos: hot_click, curious_open, silent_open, revival", "psychology"),
        ("Modo de Autonomia", "3 niveis com confirmacao dupla para full-auto", "security"),
        ("Inteligencia de escolas", "Enriquece escolas com dados web (rankings, premios, noticias)", "explore"),
        ("Persona adaptativa", "IA adapta tom por tipo de escola (4 personas)", "face"),
        ("Calendario inteligente", "Envia no melhor horario (tracking + feriados + fase letiva)", "event"),
        ("Outlook Calendar", "Detecta reunioes, briefing pre-reuniao, pede resumo pos", "calendar_month"),
        ("Multichannel", "Email + WhatsApp + LinkedIn com cadencia configuravel", "campaign"),
        ("Modo campo", "Compartilha localizacao → briefing instantaneo da escola proxima", "location_on"),
        ("Sessao de prospeccao", "IAlex guia escola a escola com contatos e opcoes", "rocket_launch"),
        ("Revisao de emails via WhatsApp", "Ver completo, reescrever, colar texto, aprovar", "edit_note"),
        ("Email de teste", "Testar assinatura e links antes de enviar para escolas", "send"),
        ("Assinatura configuravel", "Texto + imagem em todos os emails", "draw"),
        ("Templates de follow-up", "Templates por tipo comportamental", "description"),
        ("Agendamento de envio", "Data/hora individual ou em massa", "schedule_send"),
    ]

    for nome, desc, icon in features:
        st.markdown(
            f'<div class="data-card" style="padding:8px 14px;display:flex;align-items:center;gap:10px">'
            f'<span class="material-icons-outlined" style="color:{COLORS["primary"]};font-size:20px">{icon}</span>'
            f'<div><strong style="font-size:13px">{nome}</strong>'
            f'<div style="font-size:12px;color:#757575">{desc}</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 7 — Paginas do dashboard
# =============================================================================
with tab7:
    section_header("Paginas do menu lateral", "menu")

    menu_items = [
        ("🏠 Painel", "KPIs, acoes rapidas, busca global, atividade recente", "app.py"),
        ("⚙️ Configuracoes", "Autonomia, pipeline, follow-ups, persona, multichannel", "pages/2_⚙️_Configuracoes.py"),
        ("📊 Pipeline", "Execucao tecnica + pipeline comercial (kanban de stages)", "pages/3_📊_Pipeline.py"),
        ("🏫 Escolas", "Gerenciar escolas: editar, excluir, historico", "pages/5_🏫_Escolas.py"),
        ("🗺️ Mapa", "Visualizacao geografica + explorar CSV completo", "pages/6_🗺️_Mapa.py"),
        ("👥 Contatos", "Lista e hierarquia de decisores por escola", "pages/7_👥_Contatos.py"),
        ("✉️ Aprovacao", "Revisar, editar e aprovar emails (Pendentes, Aprovadas, Enviadas)", "pages/8_✉️_Aprovacao.py"),
        ("🔄 Follow-ups", "Metricas, timeline, deducao de emails", "pages/9_🔄_Follow-ups.py"),
        ("📝 Templates", "Assinatura de email + templates de mensagem e follow-up", "pages/10_📝_Templates.py"),
        ("📥 Importar", "Filtrar e importar escolas do CSV do MEC", "pages/11_📥_Importar.py"),
        ("🔍 Inteligencia", "Enriquecer escolas com dados web (rankings, premios)", "pages/12_🔍_Discovery.py"),
    ]

    for nome, desc, page_path in menu_items:
        col_card, col_btn = st.columns([4, 1])
        with col_card:
            st.markdown(
                f'<div class="data-card" style="padding:10px 14px">'
                f'<strong style="font-size:14px">{nome}</strong>'
                f'<div style="font-size:12px;color:#757575">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            st.markdown('<div style="margin-top:8px"></div>', unsafe_allow_html=True)
            if st.button("Abrir →", key=f"goto_{page_path}", use_container_width=True):
                st.switch_page(page_path)

# =============================================================================
# TAB 8 — Ciclo Semanal
# =============================================================================
with tab8:
    section_header("Ciclo semanal recomendado", "event_repeat")

    st.markdown("**Com automacoes ativas (Semi-Auto), seu trabalho e minimo:**")

    st.markdown("""
| Dia | O que fazer | Onde | Tempo |
|---|---|---|---|
| **Segunda** | Revisar resumo do IAlex | WhatsApp | 2 min |
| **Terca** | Aprovar emails da fila | ✉️ Aprovacao | 10 min |
| **Quarta** | Verificar respostas + sinais | WhatsApp / CRM | 5 min |
| **Quinta** | Enriquecer escolas com dados web | 🔍 Inteligencia | 5 min |
| **Sexta** | Checar relatorio semanal | WhatsApp | 3 min |
| **Total** | | | **~25 min/sem** |
""")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Fases de crescimento", "trending_up")

    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["info"]}">'
            '<strong>Semana 1-2 — Teste</strong>'
            '<ul style="font-size:13px;color:#757575;margin:8px 0 0;padding-left:18px">'
            '<li>Importar 50-100 escolas</li>'
            '<li>Rodar pipeline manual</li>'
            '<li>Aprovar 5-10 emails</li>'
            '<li>Verificar qualidade</li></ul></div>',
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["success"]}">'
            '<strong>Semana 3-4 — Operacao</strong>'
            '<ul style="font-size:13px;color:#757575;margin:8px 0 0;padding-left:18px">'
            '<li>Ativar pipeline automatico</li>'
            '<li>Ativar follow-ups</li>'
            '<li>50 qualificacoes/semana</li>'
            '<li>20-30 emails/semana</li></ul></div>',
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f'<div class="data-card" style="border-left:4px solid {COLORS["accent"]}">'
            '<strong>Mes 2+ — Escala</strong>'
            '<ul style="font-size:13px;color:#757575;margin:8px 0 0;padding-left:18px">'
            '<li>100+ qualificacoes/semana</li>'
            '<li>Expandir para novas cidades</li>'
            '<li>ML preditivo otimiza</li>'
            '<li>RAG melhora emails</li></ul></div>',
            unsafe_allow_html=True,
        )

# =============================================================================
# TAB 9 — Duvidas
# =============================================================================
with tab9:
    section_header("Perguntas Frequentes", "help_outline")

    perguntas = [
        ("O IAlex pode enviar emails sem eu saber?",
         "**Somente se voce ativar FULL-AUTO** (exige frase 'autorizo envio automatico'). No modo padrao (Semi-Auto), tudo vai pra fila."),
        ("Posso editar emails antes de enviar?",
         "**Sim.** Na fila de aprovacao ou via WhatsApp (colar texto, dar instrucoes, reescrever)."),
        ("O que sao follow-ups comportamentais?",
         "Em vez de dias fixos, o sistema analisa comportamento (abriu? clicou? sumiu?) e gera follow-up adequado."),
        ("Como funciona o modo campo?",
         "Compartilhe localizacao no WhatsApp. Se tem escola do banco em ate 1km, IAlex mostra briefing instantaneo com diretor, score e pitch."),
        ("O que e a persona adaptativa?",
         "A IA classifica cada escola (inovadora, conservadora, pragmatica, entusiasta) e adapta tom, argumentos e CTA."),
        ("Como funciona o multichannel?",
         "Quando ativado, follow-ups alternam entre email, WhatsApp e LinkedIn conforme cadencia configurada. LinkedIn e manual."),
        ("O Outlook Calendar funciona?",
         "Sim. IAlex detecta reunioes, envia briefing 30 min antes e pede resumo depois. Requer App Registration no Azure."),
        ("Quanto custa rodar?",
         "~R$ 0,50 a R$ 2,00 para 20 qualificacoes + 10 emails (API OpenAI). DuckDuckGo, Brevo e Supabase: gratis nos planos free."),
        ("Posso usar so o dashboard sem WhatsApp?",
         "**Sim.** O dashboard tem todas as funcoes. O WhatsApp e complementar."),
        ("Posso usar em outro computador?",
         "**Sim.** O banco fica na nuvem (Supabase). Dashboard no Streamlit Cloud (acesso por URL)."),
    ]

    for pergunta, resposta in perguntas:
        with st.expander(pergunta):
            st.markdown(resposta)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Problemas comuns", "bug_report")

    st.markdown("""
| Problema | Solucao |
|---|---|
| CSV nao encontrado | Baixe do MEC e salve em `data/raw/escolas_brasil.csv` |
| Discovery sem resultados | Tente outra cidade ou keyword |
| Email nao chegou | Verifique spam. Envie teste para Gmail pessoal |
| IAlex nao responde | Reinicie: `venv/Scripts/python.exe agent/webhook_server.py` |
| Pipeline nao roda auto | Mude para Semi-Auto em ⚙️ Configuracoes |
| Msg bloqueada | Contato sem email/telefone. Adicione no dashboard |
""")
