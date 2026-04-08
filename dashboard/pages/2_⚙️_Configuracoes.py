"""Pagina 11 - Configuracoes: pipeline automatico do IAlex.

Permite ao Fernando configurar horario, dias, etapas e limites do pipeline
automatico sem precisar mexer no codigo. A config e salva em
conversation_memory (scope=global) e o scheduler recarrega automaticamente.
"""
import sys
from datetime import datetime, time as dtime
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
    metric_card,
    COLORS,
)
from integrations.pipeline_config import pipeline_config

apply_theme_no_config()

# =============================================================================
# Header
# =============================================================================
breadcrumb(["IAprendo", "Configuracoes"])
st.markdown("# ⚙️ Configuracoes")
st.caption("Configure o pipeline automatico do IAlex — rodar sozinho nos horarios definidos.")

# Carregar config atual
cfg = pipeline_config.get_config()
current_level = cfg.get("autonomy_level", "semi_auto")

# =============================================================================
# Secao 0 - MODO DE AUTONOMIA (topo, destaque maximo)
# =============================================================================
section_header("🛡️ Modo de Autonomia", "security")

# Card explicativo grande
level_cards = {
    "manual": {
        "emoji": "🛡️",
        "title": "MANUAL",
        "subtitle": "Zero automacao — tudo manual",
        "color": "#9E9E9E",
        "description": "Nenhum job roda sozinho. Fernando dispara tudo manualmente no dashboard ou via WhatsApp. Modo de maxima seguranca.",
    },
    "semi_auto": {
        "emoji": "🤖",
        "title": "SEMI-AUTO",
        "subtitle": "IAlex gera, voce aprova (RECOMENDADO)",
        "color": COLORS["primary"],
        "description": "IAlex pode qualificar, enriquecer, buscar contatos, gerar emails e follow-ups AUTOMATICAMENTE. Tudo cai na fila de aprovacao. NADA e enviado sem voce aprovar 1 a 1.",
    },
    "full_auto": {
        "emoji": "⚡",
        "title": "FULL-AUTO",
        "subtitle": "IAlex tambem envia automaticamente",
        "color": COLORS["error"],
        "description": "IAlex ALEM de gerar, tambem ENVIA os emails que voce ja aprovou — sem perguntar de novo. So ative se voce vai supervisionar a fila regularmente.",
    },
}

active = level_cards[current_level]
st.markdown(
    f'<div class="data-card" style="border-left:6px solid {active["color"]};padding:20px">'
    f'<div style="font-size:28px;font-weight:700;color:{active["color"]}">'
    f'{active["emoji"]} MODO ATUAL: {active["title"]}'
    f'</div>'
    f'<div style="font-size:15px;color:#666;margin-top:4px">{active["subtitle"]}</div>'
    f'<div style="font-size:14px;line-height:1.6;margin-top:12px">{active["description"]}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)
st.markdown("**Trocar modo:**")

col_m1, col_m2, col_m3 = st.columns(3)

def _switch_level(to_level: str):
    """Muda o nivel e recarrega scheduler."""
    result = pipeline_config.set_autonomy_level(to_level)
    if result.get("ok"):
        try:
            from agent.scheduler import ialex_scheduler
            if getattr(ialex_scheduler, "_running", False):
                ialex_scheduler.reload_pipeline_schedule()
                ialex_scheduler.reload_followup_schedule()
        except Exception:
            pass
        st.success(f"✅ Modo alterado de {result['from']} para {result['to']}")
        st.rerun()
    else:
        st.error(f"❌ Falha: {result.get('error', '?')}")

with col_m1:
    is_current = current_level == "manual"
    if st.button(
        "🛡️ MANUAL",
        use_container_width=True,
        type="primary" if is_current else "secondary",
        disabled=is_current,
        key="btn_manual",
    ):
        _switch_level("manual")
    st.caption("Zero automacao")

with col_m2:
    is_current = current_level == "semi_auto"
    if st.button(
        "🤖 SEMI-AUTO",
        use_container_width=True,
        type="primary" if is_current else "secondary",
        disabled=is_current,
        key="btn_semi",
    ):
        _switch_level("semi_auto")
    st.caption("Gera, nao envia (seguro)")

with col_m3:
    is_current = current_level == "full_auto"
    if st.button(
        "⚡ FULL-AUTO",
        use_container_width=True,
        type="primary" if is_current else "secondary",
        disabled=is_current,
        key="btn_full",
    ):
        # Confirmacao dupla via session state
        st.session_state["_full_auto_pending"] = True
        st.rerun()
    st.caption("Tambem envia (requer confirm)")

# Modal de confirmacao dupla para full_auto
if st.session_state.get("_full_auto_pending") and current_level != "full_auto":
    st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)
    alert_banner(
        "⚠️ <strong>ATENCAO — ATIVACAO DE ENVIO AUTOMATICO</strong><br/>"
        "Ao confirmar, o IAlex vai enviar automaticamente TODOS os emails que voce aprovar "
        "daqui pra frente, sem perguntar de novo. Supervisione a fila de aprovacao regularmente.",
        "warning",
    )
    confirm_text = st.text_input(
        "Digite exatamente: **autorizo envio automatico**",
        key="full_auto_confirm_text",
        placeholder="autorizo envio automatico",
    )
    col_cf1, col_cf2 = st.columns(2)
    with col_cf1:
        if st.button("✅ Confirmar FULL-AUTO", type="primary", use_container_width=True, key="btn_confirm_full"):
            if confirm_text.strip().lower() == "autorizo envio automatico":
                _switch_level("full_auto")
                st.session_state["_full_auto_pending"] = False
            else:
                st.error("Frase incorreta. Digite exatamente: autorizo envio automatico")
    with col_cf2:
        if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel_full"):
            st.session_state["_full_auto_pending"] = False
            st.rerun()

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# Aviso quando em modo manual
if current_level == "manual":
    alert_banner(
        "🛡️ <strong>Modo MANUAL ativo</strong> — As configuracoes de pipeline e follow-ups abaixo ficam desabilitadas. "
        "Mude para SEMI-AUTO para permitir automacao.",
        "info",
    )

# =============================================================================
# Secao 1 - Status atual
# =============================================================================
section_header("Status atual", "info")

status_color = COLORS["success"] if cfg.get("enabled") else COLORS["error"]
status_text = "ATIVO" if cfg.get("enabled") else "DESATIVADO"
status_icon = "✅" if cfg.get("enabled") else "⛔"

col1, col2, col3 = st.columns(3)
with col1:
    metric_card(
        label="Pipeline automatico",
        value=f"{status_icon} {status_text}",
        color=status_color,
    )
with col2:
    last_run = cfg.get("last_run_at")
    last_label = "Nunca"
    if last_run:
        try:
            dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
            last_label = dt.strftime("%d/%m %H:%M")
        except Exception:
            last_label = str(last_run)[:16]
    metric_card(
        label="Ultimo run",
        value=last_label,
        color=COLORS["info"],
    )
with col3:
    next_label = "-"
    if cfg.get("enabled") and cfg.get("days"):
        dias_pt = ", ".join([pipeline_config.day_label(d) for d in cfg["days"]])
        next_label = f"{cfg.get('schedule_time', '08:00')} ({dias_pt})"
    metric_card(
        label="Proxima execucao",
        value=next_label,
        color=COLORS["primary"],
    )

if cfg.get("last_run_status") == "error":
    alert_banner(
        "⚠️ O ultimo run do pipeline automatico falhou. Verifique os logs.",
        "error",
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 2 - Agendamento
# =============================================================================
section_header("Agendamento", "schedule")

enabled = st.toggle(
    "Ativar pipeline automatico",
    value=bool(cfg.get("enabled", False)),
    help="Quando ativado, o IAlex roda o pipeline sozinho nos horarios e dias configurados.",
)

col_a, col_b = st.columns([1, 2])
with col_a:
    # Parse horario atual
    try:
        hh, mm = cfg.get("schedule_time", "08:00").split(":")
        current_time = dtime(int(hh), int(mm))
    except Exception:
        current_time = dtime(8, 0)
    selected_time = st.time_input(
        "Horario de execucao",
        value=current_time,
        help="Horario em que o pipeline sera disparado (fuso horario do servidor).",
    )

with col_b:
    DAYS_OPTIONS = [
        ("mon", "Segunda"),
        ("tue", "Terca"),
        ("wed", "Quarta"),
        ("thu", "Quinta"),
        ("fri", "Sexta"),
        ("sat", "Sabado"),
        ("sun", "Domingo"),
    ]
    day_labels = [label for _, label in DAYS_OPTIONS]
    day_keys = [key for key, _ in DAYS_OPTIONS]

    current_days = cfg.get("days", ["mon", "tue", "wed", "thu", "fri"])
    default_labels = [label for key, label in DAYS_OPTIONS if key in current_days]

    selected_labels = st.multiselect(
        "Dias da semana",
        options=day_labels,
        default=default_labels,
        help="Dias em que o pipeline sera executado.",
    )
    selected_days = [day_keys[day_labels.index(lbl)] for lbl in selected_labels]

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 3 - Etapas
# =============================================================================
section_header("Etapas do pipeline", "list_alt")

st.caption(
    "Escolha quais etapas o pipeline automatico deve executar. "
    "A ordem e fixa: qualificar → enriquecer → contatos → gerar emails → enviar."
)

current_steps = set(cfg.get("steps", ["qualify", "enrich", "contacts", "write"]))

allow_send_step = (current_level == "full_auto")

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    step_qualify = st.checkbox("🎯 Qualificar", value="qualify" in current_steps, disabled=(current_level == "manual"))
with col2:
    step_enrich = st.checkbox("🔍 Enriquecer", value="enrich" in current_steps, disabled=(current_level == "manual"))
with col3:
    step_contacts = st.checkbox("👥 Contatos", value="contacts" in current_steps, disabled=(current_level == "manual"))
with col4:
    step_write = st.checkbox("📝 Gerar emails", value="write" in current_steps, disabled=(current_level == "manual"))
with col5:
    step_send = st.checkbox(
        "📤 Enviar aprovados",
        value=("send" in current_steps) and allow_send_step,
        disabled=(not allow_send_step),
        help="Disponivel apenas em modo FULL-AUTO" if not allow_send_step else None,
    )

if not allow_send_step:
    st.caption("🔒 _Etapa 'Enviar aprovados' bloqueada fora do modo FULL-AUTO (seguranca)._")
elif step_send:
    alert_banner(
        "⚠️ <strong>Atencao</strong>: a etapa 'Enviar aprovados' ira disparar "
        "automaticamente todos os emails da fila que ja estao com status <em>approved</em>. "
        "Certifique-se de que aprovou apenas o que realmente quer enviar.",
        "warning",
    )

selected_steps = []
if step_qualify:
    selected_steps.append("qualify")
if step_enrich:
    selected_steps.append("enrich")
if step_contacts:
    selected_steps.append("contacts")
if step_write:
    selected_steps.append("write")
if step_send:
    selected_steps.append("send")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 4 - Limites
# =============================================================================
section_header("Limites por execucao", "tune")

st.caption("Quantidades maximas processadas em cada etapa por execucao do pipeline.")

limits = cfg.get("limits", {}) or {}
col1, col2, col3, col4 = st.columns(4)
with col1:
    qualify_limit = st.number_input(
        "Qualificar (max)",
        min_value=1, max_value=500, step=5,
        value=int(limits.get("qualify_limit", 20)),
    )
with col2:
    enrich_limit = st.number_input(
        "Enriquecer (max)",
        min_value=1, max_value=500, step=5,
        value=int(limits.get("enrich_limit", 10)),
    )
with col3:
    write_limit = st.number_input(
        "Gerar emails (max)",
        min_value=1, max_value=500, step=5,
        value=int(limits.get("write_limit", 10)),
    )
with col4:
    write_mode = st.selectbox(
        "Modo de escrita",
        options=["ai", "template"],
        index=0 if cfg.get("write_mode", "ai") == "ai" else 1,
        format_func=lambda x: "IA personalizada" if x == "ai" else "Template padrao",
    )

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =============================================================================
# Secao 5 - Salvar e executar
# =============================================================================
section_header("Acoes", "save")

col_save, col_run = st.columns([2, 1])

with col_save:
    if st.button("💾 Salvar configuracao", type="primary", use_container_width=True):
        new_cfg = {
            **cfg,
            "enabled": enabled,
            "schedule_time": selected_time.strftime("%H:%M"),
            "days": selected_days,
            "steps": selected_steps,
            "limits": {
                "qualify_limit": int(qualify_limit),
                "enrich_limit": int(enrich_limit),
                "write_limit": int(write_limit),
            },
            "write_mode": write_mode,
            "send_approved": "send" in selected_steps,
        }
        if not selected_days:
            st.error("Selecione pelo menos um dia da semana.")
        elif not selected_steps:
            st.error("Selecione pelo menos uma etapa.")
        elif pipeline_config.save_config(new_cfg):
            # Recarregar scheduler
            try:
                from agent.scheduler import ialex_scheduler
                if getattr(ialex_scheduler, "_running", False):
                    ialex_scheduler.reload_pipeline_schedule()
            except Exception:
                pass
            st.success(
                f"✅ Configuracao salva! Pipeline {'ATIVO' if enabled else 'DESATIVADO'}. "
                f"Proximo run: {selected_time.strftime('%H:%M')} "
                f"nos dias {', '.join([pipeline_config.day_label(d) for d in selected_days])}."
            )
            st.rerun()
        else:
            st.error("Falha ao salvar. Verifique se a tabela conversation_memory esta disponivel.")

with col_run:
    if st.button("▶️ Executar agora (teste)", use_container_width=True):
        try:
            from agent.scheduler import ialex_scheduler
            ialex_scheduler.run_pipeline_now()
            st.success(
                "✅ Pipeline iniciado em segundo plano. Voce recebera o resumo no WhatsApp quando terminar."
            )
        except Exception as e:
            st.error(f"Erro ao disparar: {e}")

# =============================================================================
# Secao 6 - Follow-ups comportamentais (Item 6)
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Follow-ups automaticos (comportamentais)", "forum")

st.caption(
    "O IAlex analisa o tracking de cada email enviado (abriu? clicou? sumiu?) "
    "e gera follow-ups personalizados por comportamento. Tudo passa pela fila "
    "de aprovacao — voce so precisa revisar."
)

fu_enabled = st.toggle(
    "Ativar follow-ups automaticos",
    value=bool(cfg.get("followup_enabled", False)),
    key="fu_enabled_toggle",
)

col_fu_a, col_fu_b = st.columns([1, 2])
with col_fu_a:
    try:
        fh, fm = cfg.get("followup_time", "09:30").split(":")
        fu_current_time = dtime(int(fh), int(fm))
    except Exception:
        fu_current_time = dtime(9, 30)
    fu_time = st.time_input(
        "Horario (diario)",
        value=fu_current_time,
        key="fu_time_input",
    )
with col_fu_b:
    fu_limit = st.number_input(
        "Maximo de follow-ups por execucao",
        min_value=1, max_value=100, step=1,
        value=int(cfg.get("followup_limit", 20)),
        key="fu_limit_input",
    )

# Tipos comportamentais permitidos
FU_TYPE_OPTIONS = [
    ("hot_click", "🔥 Hot click — clicou em link (alta prioridade)"),
    ("curious_open", "👀 Curious open — abriu 2+ vezes sem responder"),
    ("silent_open", "📬 Silent open — abriu 1x e sumiu"),
    ("revival", "🧊 Revival — nao abriu, angulo totalmente novo"),
]
current_fu_types = set(cfg.get("followup_types", ["hot_click", "curious_open", "silent_open", "revival"]))

fu_type_labels = [lbl for _, lbl in FU_TYPE_OPTIONS]
fu_type_keys = [k for k, _ in FU_TYPE_OPTIONS]
default_fu_labels = [lbl for k, lbl in FU_TYPE_OPTIONS if k in current_fu_types]

selected_fu_type_labels = st.multiselect(
    "Tipos de follow-up permitidos",
    options=fu_type_labels,
    default=default_fu_labels,
    help="Escolha quais comportamentos disparam follow-up automatico.",
    key="fu_types_multi",
)
selected_fu_types = [fu_type_keys[fu_type_labels.index(lbl)] for lbl in selected_fu_type_labels]

col_fu_save, col_fu_run = st.columns([2, 1])
with col_fu_save:
    if st.button("💾 Salvar follow-ups", type="primary", use_container_width=True, key="btn_save_fu"):
        new_cfg = pipeline_config.get_config()  # recarrega pra nao sobrescrever pipeline
        new_cfg["followup_enabled"] = fu_enabled
        new_cfg["followup_time"] = fu_time.strftime("%H:%M")
        new_cfg["followup_limit"] = int(fu_limit)
        new_cfg["followup_types"] = selected_fu_types
        if not selected_fu_types:
            st.error("Selecione pelo menos um tipo de follow-up.")
        elif pipeline_config.save_config(new_cfg):
            try:
                from agent.scheduler import ialex_scheduler
                if getattr(ialex_scheduler, "_running", False):
                    ialex_scheduler.reload_followup_schedule()
            except Exception:
                pass
            st.success(
                f"✅ Follow-ups {'ATIVOS' if fu_enabled else 'DESATIVADOS'}. "
                f"Rodam diariamente as {fu_time.strftime('%H:%M')}."
            )
            st.rerun()
        else:
            st.error("Falha ao salvar configuracao de follow-ups.")

with col_fu_run:
    if st.button("▶️ Rodar follow-ups agora", use_container_width=True, key="btn_run_fu"):
        try:
            from agent.scheduler import ialex_scheduler
            ialex_scheduler.run_followup_now()
            st.success("✅ Geracao de follow-ups iniciada em segundo plano. Resumo chegara no WhatsApp.")
        except Exception as e:
            st.error(f"Erro: {e}")

# =============================================================================
# Secao 7 - Persona de comunicacao
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Persona de comunicacao", "face")

st.caption(
    "Controle como o IAlex adapta o tom dos emails para cada escola. "
    "No modo Padrao, todos os emails usam o mesmo tom. No modo Adaptativo, "
    "a IA classifica cada escola (inovadora, conservadora, pragmatica, entusiasta) "
    "e adapta tom, argumentos e CTA."
)

current_persona = cfg.get("persona_mode", "padrao")

persona_col1, persona_col2 = st.columns(2)
with persona_col1:
    is_padrao = current_persona == "padrao"
    st.markdown(
        f'<div class="data-card" style="border-left:4px solid '
        f'{"#4CAF50" if is_padrao else "#E0E0E0"};padding:12px 16px">'
        f'<strong style="font-size:15px">🟢 Padrao</strong>'
        f'<div style="font-size:13px;color:#757575;margin-top:4px">'
        f'Tom fixo (amigavel, humano, direto). Todos os emails usam o mesmo estilo. '
        f'Comportamento atual.</div></div>',
        unsafe_allow_html=True,
    )
with persona_col2:
    is_adapt = current_persona == "adaptativo"
    st.markdown(
        f'<div class="data-card" style="border-left:4px solid '
        f'{"#7B1FA2" if is_adapt else "#E0E0E0"};padding:12px 16px">'
        f'<strong style="font-size:15px">🔮 Adaptativo</strong>'
        f'<div style="font-size:13px;color:#757575;margin-top:4px">'
        f'IA classifica cada escola e adapta tom: '
        f'inovadora (entusiasmado), conservadora (respeitoso), '
        f'pragmatica (direto), entusiasta (caloroso).</div></div>',
        unsafe_allow_html=True,
    )

persona_choice = st.radio(
    "Modo de comunicacao",
    options=["padrao", "adaptativo"],
    index=0 if current_persona == "padrao" else 1,
    format_func=lambda x: "🟢 Padrão (tom fixo)" if x == "padrao" else "🔮 Adaptativo (IA adapta por escola)",
    horizontal=True,
    key="persona_radio",
    label_visibility="collapsed",
)

if persona_choice != current_persona:
    if st.button("💾 Salvar modo de comunicacao", type="primary", use_container_width=True, key="btn_save_persona"):
        new_cfg = pipeline_config.get_config()
        new_cfg["persona_mode"] = persona_choice
        if pipeline_config.save_config(new_cfg):
            st.success(
                f"✅ Modo de comunicacao alterado para "
                f"{'Padrao' if persona_choice == 'padrao' else 'Adaptativo'}."
            )
            st.rerun()
        else:
            st.error("Falha ao salvar.")

# =============================================================================
# Secao 8 - Cadencia multichannel
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Cadencia multichannel", "campaign")

st.caption(
    "Configure a sequencia de canais para prospecção. "
    "Quando desabilitado, tudo usa apenas email (comportamento padrao)."
)

mc_enabled = cfg.get("multichannel_enabled", False)
mc_toggle = st.toggle(
    "Ativar cadencia multichannel",
    value=mc_enabled,
    key="mc_toggle",
    help="Quando ativo, follow-ups podem alternar entre email, WhatsApp e LinkedIn conforme a cadencia configurada.",
)

if mc_toggle:
    st.markdown("**Canais ativos:**")
    current_channels = set(cfg.get("multichannel_channels", ["email"]))

    ch_email = st.checkbox("📧 Email (sempre ativo)", value=True, disabled=True, key="ch_email")
    ch_whatsapp = st.checkbox(
        "📱 WhatsApp",
        value="whatsapp" in current_channels,
        key="ch_whatsapp",
        help="Follow-ups por WhatsApp (mensagem curta, informal). Requer telefone da escola.",
    )
    ch_linkedin = st.checkbox(
        "💼 LinkedIn (manual)",
        value="linkedin" in current_channels,
        key="ch_linkedin",
        help="Gera texto para LinkedIn, mas Fernando envia manualmente. IAlex notifica no WhatsApp.",
    )

    selected_channels = ["email"]
    if ch_whatsapp:
        selected_channels.append("whatsapp")
    if ch_linkedin:
        selected_channels.append("linkedin")

    # Cadencia visual
    st.markdown("**Cadencia configurada:**")
    current_cadence = cfg.get("cadence_steps", [])

    # Presets
    preset = st.selectbox(
        "Preset rapido",
        options=["Personalizado", "So email", "Email + WhatsApp", "Completo"],
        index=0,
        key="mc_preset",
    )
    if preset == "So email":
        current_cadence = [
            {"step": 1, "day": 0, "channel": "email", "label": "Email inicial"},
            {"step": 2, "day": 3, "channel": "email", "label": "Follow-up 1"},
            {"step": 3, "day": 7, "channel": "email", "label": "Follow-up 2"},
            {"step": 4, "day": 14, "channel": "email", "label": "Follow-up 3"},
        ]
    elif preset == "Email + WhatsApp":
        current_cadence = [
            {"step": 1, "day": 0, "channel": "email", "label": "Email inicial"},
            {"step": 2, "day": 3, "channel": "whatsapp", "label": "WhatsApp curto"},
            {"step": 3, "day": 7, "channel": "email", "label": "Email follow-up"},
            {"step": 4, "day": 14, "channel": "whatsapp", "label": "WhatsApp final"},
        ]
    elif preset == "Completo":
        current_cadence = [
            {"step": 1, "day": 0, "channel": "email", "label": "Email inicial"},
            {"step": 2, "day": 3, "channel": "whatsapp", "label": "WhatsApp curto"},
            {"step": 3, "day": 7, "channel": "email", "label": "Email follow-up"},
            {"step": 4, "day": 14, "channel": "linkedin", "label": "LinkedIn (manual)"},
        ]

    # Mostrar cadencia
    channel_icons = {"email": "📧", "whatsapp": "📱", "linkedin": "💼"}
    for cs in current_cadence:
        icon = channel_icons.get(cs.get("channel", "email"), "📧")
        st.markdown(
            f'<div class="data-card" style="padding:8px 14px;border-left:3px solid #E0E0E0">'
            f'<strong>Passo {cs["step"]}</strong> — Dia {cs["day"]} — '
            f'{icon} {cs.get("channel", "email").title()} — '
            f'<em>{cs.get("label", "")}</em></div>',
            unsafe_allow_html=True,
        )

    if st.button("💾 Salvar cadencia", type="primary", use_container_width=True, key="btn_save_mc"):
        new_cfg = pipeline_config.get_config()
        new_cfg["multichannel_enabled"] = mc_toggle
        new_cfg["multichannel_channels"] = selected_channels
        new_cfg["cadence_steps"] = current_cadence
        if pipeline_config.save_config(new_cfg):
            st.success("✅ Cadencia multichannel salva!")
            st.rerun()
        else:
            st.error("Falha ao salvar.")
elif mc_enabled and not mc_toggle:
    # Desabilitando
    if st.button("💾 Desabilitar multichannel", type="primary", key="btn_disable_mc"):
        new_cfg = pipeline_config.get_config()
        new_cfg["multichannel_enabled"] = False
        if pipeline_config.save_config(new_cfg):
            st.success("✅ Multichannel desabilitado. Tudo voltou a usar apenas email.")
            st.rerun()

# =============================================================================
# Rodape - Dica
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.info(
    "💡 **Dica**: voce tambem pode controlar pelo WhatsApp. "
    "Diga ao IAlex: \"Como esta o pipeline automatico?\", \"Ativa os follow-ups\", "
    "\"Gera follow-ups agora\" ou \"Quais leads estao prontos para follow-up?\""
)
