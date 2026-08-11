"""Pagina 11 - Configuracoes: pipeline automatico do IAlex.

Permite ao Fernando configurar horario, dias, etapas e limites do pipeline
automatico sem precisar mexer no codigo. A config e salva em
conversation_memory (scope=global) e o scheduler recarrega automaticamente.
"""
import sys
from datetime import datetime, time as dtime
from pathlib import Path

import streamlit as st
import pandas as pd

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

from dashboard._auth_gate import require_auth
require_auth()

# =============================================================================
# Header
# =============================================================================
breadcrumb(["IAprendo", "Configuracoes"])
st.markdown("# ⚙️ Configuracoes")
st.caption("Configure o pipeline automatico do IAlex — rodar sozinho nos horarios definidos.")


# =============================================================================
# render_memorias — migrado de pages/15_Memorias.py (deletada)
# =============================================================================
def render_memorias() -> None:
    """Renderiza a aba Memorias dentro de Configuracoes.
    Migrado de dashboard/pages/15_🧠_Memorias.py (deletada)."""
    from datetime import datetime, timezone, timedelta
    from collections import Counter
    import plotly.express as px
    from integrations.memory import memory
    from database.supabase_client import db

    if not memory.is_available():
        alert_banner("Tabela conversation_memory nao disponivel. Aplique a migration 005.", "error")
        return

    CAT_LABELS = {
        "fact": "📌 Fato",
        "preference": "⭐ Preferencia",
        "insight": "💡 Insight",
        "warning": "⚠️ Alerta",
        "reminder": "🔔 Lembrete",
    }
    SCOPE_LABELS = {
        "global": "Global",
        "company": "Escola",
        "contact": "Contato",
    }


    def _render_create_form(companies):
        """Form reutilizavel para criar uma nova memoria."""
        with st.form("create_mem_form"):
            cm_c1, cm_c2 = st.columns([2, 1])
            with cm_c1:
                conteudo = st.text_area(
                    "Conteudo *",
                    placeholder="Ex: Diretora prefere ser contatada de manha.",
                    height=90,
                )
            with cm_c2:
                cat = st.selectbox(
                    "Categoria",
                    ["fact", "preference", "insight", "warning", "reminder"],
                    format_func=lambda x: CAT_LABELS.get(x, x),
                )
                imp = st.slider("Importancia", 1, 10, 5)

            cm_c3, cm_c4 = st.columns(2)
            with cm_c3:
                escopo = st.radio(
                    "Escopo",
                    ["global", "company"],
                    format_func=lambda x: SCOPE_LABELS.get(x, x),
                    horizontal=True,
                )
            with cm_c4:
                escola_sel_id = None
                if escopo == "company" and companies:
                    escola_names = [f"{c.get('name', '?')} ({c.get('city', '')})" for c in companies]
                    idx = st.selectbox(
                        "Escola",
                        range(len(companies)),
                        format_func=lambda i: escola_names[i][:50],
                    )
                    escola_sel_id = companies[idx]["id"]

            if st.form_submit_button("💾 Criar memoria", type="primary"):
                if not conteudo or len(conteudo.strip()) < 5:
                    st.error("Conteudo muito curto (minimo 5 chars).")
                elif escopo == "company" and not escola_sel_id:
                    st.error("Selecione uma escola.")
                else:
                    mem_id = memory.remember(
                        content=conteudo,
                        scope=escopo,
                        scope_id=escola_sel_id if escopo == "company" else None,
                        category=cat,
                        importance=imp,
                        source="dashboard",
                    )
                    if mem_id:
                        st.success(f"Memoria criada: {mem_id[:8]}")
                        load_memories.clear()
                        st.rerun()
                    else:
                        st.error("Falha ao criar.")


    # =============================================================================
    # LOAD
    # =============================================================================
    @st.cache_data(ttl=60)
    def load_memories():
        try:
            r = db.client.table("conversation_memory").select("*").order("created_at", desc=True).execute()
            return r.data or []
        except Exception as e:
            st.error(f"Erro ao carregar memorias: {e}")
            return []


    @st.cache_data(ttl=60)
    def load_companies():
        try:
            r = db.client.table("companies").select("id,name,city,state").order("name").execute()
            return r.data or []
        except Exception:
            return []


    all_memories = load_memories()
    all_companies = load_companies()
    company_by_id = {c["id"]: c for c in all_companies}
    company_name_by_id = {c["id"]: c.get("name", "?") for c in all_companies}

    # =============================================================================
    # KPIs
    # =============================================================================
    total_mem = len(all_memories)
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    mem_semana = 0
    for m in all_memories:
        try:
            created = datetime.fromisoformat((m.get("created_at") or "").replace("Z", "+00:00"))
            if created >= week_ago:
                mem_semana += 1
        except Exception:
            pass

    cats = Counter(m.get("category", "?") for m in all_memories)
    top_cat = cats.most_common(1)[0] if cats else ("—", 0)

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Total de memorias", total_mem, COLORS["primary"], icon="psychology")
    with mc2:
        metric_card("Criadas na semana", mem_semana, COLORS["accent"], icon="update")
    with mc3:
        metric_card(
            "Top categoria",
            f"{CAT_LABELS.get(top_cat[0], top_cat[0])[:12]} ({top_cat[1]})",
            COLORS["info"],
            icon="category",
        )
    with mc4:
        n_com_escola = sum(1 for m in all_memories if m.get("scope") == "company")
        metric_card("De escolas", n_com_escola, COLORS["secondary"], icon="school")

    st.markdown("")

    if not all_memories:
        alert_banner(
            "Nenhuma memoria ainda. O IAlex cria automaticamente quando emails sao abertos/clicados, "
            "reunioes sao registradas ou qualifier gera insights.",
            "info",
        )
        with st.expander("➕ Criar primeira memoria manualmente"):
            _render_create_form(all_companies)
        return

    # =============================================================================
    # FILTROS
    # =============================================================================
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
    with fc1:
        sel_scope = st.multiselect(
            "Escopo",
            ["global", "company", "contact"],
            default=[],
            format_func=lambda x: SCOPE_LABELS.get(x, x),
            label_visibility="collapsed",
            placeholder="Escopo...",
        )
    with fc2:
        sel_cat = st.multiselect(
            "Categoria",
            ["fact", "preference", "insight", "warning", "reminder"],
            default=[],
            format_func=lambda x: CAT_LABELS.get(x, x),
            label_visibility="collapsed",
            placeholder="Categoria...",
        )
    with fc3:
        min_imp = st.slider("Importancia minima", 1, 10, 1, label_visibility="collapsed")
    with fc4:
        search = st.text_input(
            "Buscar",
            placeholder="Buscar conteudo...",
            label_visibility="collapsed",
            key="mem_search",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # Aplicar filtros
    mems_filt = all_memories
    if sel_scope:
        mems_filt = [m for m in mems_filt if m.get("scope") in sel_scope]
    if sel_cat:
        mems_filt = [m for m in mems_filt if m.get("category") in sel_cat]
    mems_filt = [m for m in mems_filt if (m.get("importance") or 5) >= min_imp]
    if search:
        s = search.lower()
        mems_filt = [m for m in mems_filt if s in (m.get("content") or "").lower()]

    st.caption(f"Exibindo **{len(mems_filt)}** de {len(all_memories)} memorias")

    # =============================================================================
    # TABELA PRINCIPAL
    # =============================================================================
    if mems_filt:
        rows = []
        for m in mems_filt:
            scope = m.get("scope", "?")
            scope_id = m.get("scope_id")
            escola_nome = ""
            if scope == "company" and scope_id:
                escola_nome = company_name_by_id.get(scope_id, "?")[:40]

            created_raw = m.get("created_at") or ""
            try:
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                created_str = created_dt.strftime("%d/%m/%Y")
            except Exception:
                created_str = "?"

            rows.append({
                "id": m.get("id"),
                "Categoria": CAT_LABELS.get(m.get("category", "fact"), m.get("category", "?")),
                "Conteudo": (m.get("content") or "")[:100],
                "Escopo": SCOPE_LABELS.get(scope, scope),
                "Escola": escola_nome,
                "Importancia": m.get("importance") or 5,
                "Criado": created_str,
                "Usos": m.get("use_count") or 0,
                "Fonte": m.get("source") or "—",
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df[["Categoria", "Conteudo", "Escola", "Importancia", "Usos", "Criado", "Fonte"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Importancia": st.column_config.ProgressColumn("Imp.", min_value=1, max_value=10),
                "Conteudo": st.column_config.TextColumn("Conteudo", width="large"),
                "Escola": st.column_config.TextColumn("Escola", width="medium"),
                "Fonte": st.column_config.TextColumn("Fonte", width="small"),
            },
            height=400,
        )

        # Selecionar memoria para excluir
        st.markdown("")
        exp_del = st.expander("🗑️ Excluir memoria")
        with exp_del:
            del_options = [
                f"{(m.get('content') or '')[:80]}... ({m.get('id', '')[:8]})"
                for m in mems_filt
            ]
            del_idx = st.selectbox(
                "Memoria a excluir",
                range(len(del_options)),
                format_func=lambda i: del_options[i],
                key="mem_del_select",
            )
            col_del_1, col_del_2 = st.columns([1, 4])
            with col_del_1:
                if st.button("Excluir", type="primary", icon=":material/delete:"):
                    target_id = mems_filt[del_idx].get("id")
                    if memory.forget(target_id):
                        st.success(f"Memoria {target_id[:8]} excluida.")
                        load_memories.clear()
                        st.rerun()
                    else:
                        st.error("Falha ao excluir.")

    # =============================================================================
    # CRIAR MEMORIA
    # =============================================================================
    st.markdown("")
    with st.expander("➕ Criar memoria manualmente"):
        _render_create_form(all_companies)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # =============================================================================
    # TOP ESCOLAS POR MEMORIAS
    # =============================================================================
    section_header("Top 10 escolas por numero de memorias", "leaderboard")

    by_school = Counter()
    for m in all_memories:
        if m.get("scope") == "company" and m.get("scope_id"):
            by_school[m["scope_id"]] += 1

    if by_school:
        top_10 = by_school.most_common(10)
        rows_top = []
        for cid, count in top_10:
            comp = company_by_id.get(cid, {})
            rows_top.append({
                "Escola": (comp.get("name") or cid[:8])[:45],
                "Cidade": comp.get("city") or "",
                "Memorias": count,
            })
        df_top = pd.DataFrame(rows_top)

        fig = px.bar(
            df_top,
            y="Escola",
            x="Memorias",
            orientation="h",
            color="Memorias",
            color_continuous_scale="Blues",
            title="Escolas com mais memorias registradas",
            height=380,
        )
        fig.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(l=0, r=0, t=40, b=0),
            showlegend=False,
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "💡 Essas escolas estao bem 'mapeadas' — o IAlex vai personalizar mensagens "
            "usando essas informacoes. Escolas sem memorias podem gerar emails genericos."
        )
    else:
        alert_banner(
            "Nenhuma memoria especifica de escola ainda. Registre reunioes ou deixe o "
            "tracking de emails (open/click/reply) capturar automaticamente.",
            "info",
        )

    # =============================================================================
    # DICA
    # =============================================================================
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.info(
        "💡 **Como alimentar memorias sem esforco:**\n\n"
        "• Eventos de email (opens/clicks/replies) viram memorias automaticamente via Brevo webhook.\n"
        "• Reunioes registradas viram memorias (outcome=positivo, notas).\n"
        "• Qualifier salva insights de escolas com score alto + sinais de inovacao.\n"
        "• Voce pode gravar via WhatsApp: 'Lembre que o diretor do Anchieta prefere WhatsApp'.\n"
        "• Dados ricos do Censo podem ser 'seedados' em batch via "
        "`venv/Scripts/python.exe scripts/seed_census_memories.py --yes`."
    )


# =============================================================================
# render_diagnostico — health check consolidado do sistema
# =============================================================================
def render_diagnostico() -> None:
    """Renderiza a aba Diagnostico: roda run_health_check() e mostra
    status de todos os componentes (DB, bridge, webhook, tools, fila,
    erros recentes, quotas de API, config)."""
    from tools.health_check import run_health_check

    st.caption(
        "Health check consolidado: banco, bridge WhatsApp, webhook, tools do IAlex, "
        "fila de aprovacao, erros recentes, quotas de API e configuracao. "
        "Atualiza automaticamente a cada 30s (cache)."
    )

    # Cache 30s pra evitar reload constante
    @st.cache_data(ttl=30, show_spinner=False)
    def _cached_health() -> dict:
        return run_health_check()

    # Botao pra forçar refresh
    col_refresh, col_ts = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Atualizar", key="diag_refresh", use_container_width=True):
            _cached_health.clear()
            st.rerun()

    with st.spinner("Rodando checks..."):
        report = _cached_health()

    overall = report.get("overall", "unknown")
    color_map = {
        "healthy": COLORS["success"],
        "degraded": COLORS["warning"],
        "critical": COLORS["error"],
        "unknown": "#9E9E9E",
    }
    emoji_map = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴", "unknown": "⚪"}
    overall_color = color_map.get(overall, "#9E9E9E")
    overall_emoji = emoji_map.get(overall, "⚪")

    with col_ts:
        ts = report.get("timestamp", "")[:19].replace("T", " ")
        st.caption(f"Ultima verificacao: {ts}")

    # === Overall card ===
    st.markdown(
        f'<div class="data-card" style="border-left:6px solid {overall_color};padding:20px">'
        f'<div style="display:flex;align-items:center;gap:16px">'
        f'<span style="font-size:36px">{overall_emoji}</span>'
        f'<div>'
        f'<div style="font-size:22px;font-weight:700;color:{overall_color}">{overall.upper()}</div>'
        f'<div style="font-size:14px;color:#616161">{report.get("summary","")}</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("")

    # === Grid de 10 checks ===
    checks = report.get("checks", {})
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Checks", "fact_check")

    check_labels = {
        "database": ("Banco de dados", "storage"),
        "schema_migrations": ("Schema/Migrations", "schema"),
        "bridge_whatsapp": ("Bridge WhatsApp", "sms"),
        "webhook_flask": ("Webhook Flask", "webhook"),
        "brain_tools": ("Tools do IAlex", "smart_toy"),
        "queue_state": ("Fila de aprovacao", "approval"),
        "error_rate_1h": ("Erros 1h", "error"),
        "error_rate_24h": ("Erros 24h", "history"),
        "api_quotas": ("Quotas de API", "speed"),
        "pipeline_config": ("Config autonomia", "security"),
    }

    # Render 2 linhas x 5 colunas
    check_order = list(check_labels.keys())
    for row_start in (0, 5):
        cols = st.columns(5)
        for i, name in enumerate(check_order[row_start:row_start + 5]):
            with cols[i]:
                info = check_labels.get(name, (name, "circle"))
                label, icon = info
                check = checks.get(name, {})
                status = check.get("status", "unknown")
                detail = check.get("detail", "")
                color = color_map.get(status, "#9E9E9E")
                emo = emoji_map.get(status, "⚪")
                metric_card(
                    label,
                    f"{emo}",
                    icon=icon,
                    color=color,
                    delta=detail[:40],
                )

    # === Alertas ===
    alerts = report.get("alerts", [])
    if alerts:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header(f"Alertas ({len(alerts)})", "warning")
        for a in alerts:
            icon_emoji = emoji_map.get(a.get("status", "unknown"), "⚪")
            st.markdown(
                f'<div class="data-card" style="border-left:4px solid {color_map.get(a.get("status"), "#9E9E9E")}">'
                f'{icon_emoji} <strong>{a.get("check", "?")}</strong> — {a.get("detail", "")}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # === Erros recentes (24h) ===
    error_check = checks.get("error_rate_24h", {})
    error_meta = error_check.get("meta", {})
    top_errors = error_meta.get("top_errors", [])
    if top_errors:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        with st.expander(f"📋 Top erros 24h ({len(top_errors)} tipo(s))", expanded=False):
            for err in top_errors:
                last = (err.get("last_seen") or "")[:19].replace("T", " ")
                st.markdown(
                    f"**{err.get('count', 0)}x** — `{err.get('message', '')[:150]}`  \n"
                    f"<span style='color:#757575;font-size:11px'>ultimo em {last}</span>",
                    unsafe_allow_html=True,
                )

    # === Quotas de API detalhadas ===
    api_check = checks.get("api_quotas", {})
    api_meta = api_check.get("meta", {})
    api_usage = api_meta.get("usage", {})
    if api_usage:
        with st.expander("📊 Quotas de API (24h)", expanded=False):
            qcols = st.columns(len(api_usage))
            for i, (api, data) in enumerate(api_usage.items()):
                with qcols[i]:
                    used = data.get("used", 0)
                    limit = data.get("limit", 1)
                    pct = data.get("pct", 0)
                    pct_color = COLORS["success"] if pct < 80 else COLORS["warning"] if pct < 100 else COLORS["error"]
                    metric_card(
                        api.capitalize(),
                        f"{used}/{limit}",
                        icon="speed",
                        color=pct_color,
                        delta=f"{pct:.0f}%",
                    )
                    st.progress(min(pct / 100, 1.0))


# =============================================================================
# TABS: Configuracoes + Memorias + Diagnostico
# =============================================================================
tab_config, tab_vendas, tab_memorias, tab_skills, tab_diag = st.tabs([
    "⚙️ Configuracoes",
    "💼 Vendas & Agenda",
    "🧠 Memorias",
    "⭐ Skills Aprendidas",
    "🩺 Diagnostico",
])

with tab_config:
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
                # O retorno era DESCARTADO: em modo MANUAL o scheduler bloqueia
                # a execucao e o painel mostrava ✅ mesmo assim, prometendo um
                # resumo no WhatsApp que nunca chegava.
                _res_run = ialex_scheduler.run_pipeline_now() or {}
                if _res_run.get("ok", True):
                    st.success(
                        "✅ Pipeline iniciado em segundo plano. Voce recebera o resumo no WhatsApp quando terminar."
                    )
                else:
                    st.warning(
                        "⚠️ " + (_res_run.get("message")
                                 or f"Execucao bloqueada ({_res_run.get('reason', 'motivo nao informado')}). "
                                    "Confira o Modo de autonomia acima.")
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
                _res_fu = ialex_scheduler.run_followup_now() or {}
                if _res_fu.get("ok", True):
                    st.success("✅ Geracao de follow-ups iniciada em segundo plano. Resumo chegara no WhatsApp.")
                else:
                    st.warning(
                        "⚠️ " + (_res_fu.get("message")
                                 or f"Execucao bloqueada ({_res_fu.get('reason', 'motivo nao informado')}). "
                                    "Confira o Modo de autonomia.")
                    )
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


with tab_memorias:
    render_memorias()

with tab_skills:
    # =========================================================================
    # ABA: Skills Aprendidas (F6 Fase 2)
    # Gestao das skills que o IAlex aprendeu via WhatsApp ("padroniza isso")
    # =========================================================================
    section_header("Skills Aprendidas", "auto_awesome")

    st.caption(
        "Skills sao padroes que o IAlex aprendeu e reutiliza automaticamente. "
        "Voce pode criar skills aqui ou via WhatsApp dizendo *'padroniza isso'*."
    )

    try:
        from database.supabase_client import db as _db_skills

        # --- KPIs ---
        all_skills = _db_skills.client.table("learned_skills").select(
            "id, name, description, skill_type, trigger_pattern, template_content, "
            "example_input, example_output, applies_to, metrics, status, created_at, updated_at"
        ).order("created_at", desc=True).execute().data or []

        active_skills = [s for s in all_skills if s.get("status") == "active"]
        archived_skills = [s for s in all_skills if s.get("status") == "archived"]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("Ativas", str(len(active_skills)), COLORS.get("success", "#2E7D32"), "check_circle")
        with c2:
            total_uses = sum((s.get("metrics") or {}).get("times_used", 0) for s in active_skills)
            metric_card("Usos totais", str(total_uses), COLORS.get("primary", "#1976D2"), "trending_up")
        with c3:
            types_count = len(set(s.get("skill_type", "") for s in active_skills))
            metric_card("Tipos", str(types_count), COLORS.get("info", "#1565C0"), "category")
        with c4:
            metric_card("Arquivadas", str(len(archived_skills)), COLORS.get("warning", "#F57F17"), "archive")

        st.divider()

        # --- Tabela de skills ativas ---
        if active_skills:
            type_emoji = {
                "email_template": "📧 Email",
                "report_format": "📊 Report",
                "analysis_pattern": "🔍 Analise",
                "response_style": "💬 Resposta",
                "whatsapp_template": "📱 WhatsApp",
                "other": "🎯 Outro",
            }

            rows = []
            for s in active_skills:
                metrics = s.get("metrics") or {}
                rows.append({
                    "Nome": s.get("name", ""),
                    "Tipo": type_emoji.get(s.get("skill_type", ""), s.get("skill_type", "")),
                    "Descricao": (s.get("description") or "")[:80],
                    "Gatilho": (s.get("trigger_pattern") or "")[:50],
                    "Usos": metrics.get("times_used", 0),
                    "Criada em": (s.get("created_at") or "")[:10],
                    "id": s.get("id"),
                })

            df_skills = pd.DataFrame(rows)

            st.subheader("Skills Ativas")
            st.dataframe(
                df_skills.drop(columns=["id"]),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Usos": st.column_config.NumberColumn("Usos", format="%d"),
                },
            )

            # --- Detalhes + acoes ---
            with st.expander("Ver detalhes / Arquivar skill"):
                selected_name = st.selectbox(
                    "Selecione uma skill",
                    options=[s.get("name", "") for s in active_skills],
                    key="skill_detail_select",
                )
                if selected_name:
                    skill = next((s for s in active_skills if s.get("name") == selected_name), None)
                    if skill:
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.markdown(f"**Tipo:** {type_emoji.get(skill.get('skill_type', ''), skill.get('skill_type', ''))}")
                            st.markdown(f"**Gatilho:** {skill.get('trigger_pattern') or '(nenhum)'}")
                            st.markdown(f"**Descricao:** {skill.get('description') or '(sem descricao)'}")
                        with col_b:
                            metrics = skill.get("metrics") or {}
                            st.markdown(f"**Usos:** {metrics.get('times_used', 0)}")
                            st.markdown(f"**Criada:** {(skill.get('created_at') or '')[:16]}")
                            st.markdown(f"**Atualizada:** {(skill.get('updated_at') or '')[:16]}")

                        st.markdown("**Conteudo/Template:**")
                        st.code(skill.get("template_content", ""), language=None)

                        if skill.get("example_input"):
                            st.markdown("**Exemplo de input:**")
                            st.text(skill["example_input"][:300])
                        if skill.get("example_output"):
                            st.markdown("**Exemplo de output:**")
                            st.text(skill["example_output"][:500])

                        if st.button("Arquivar esta skill", type="secondary", key=f"archive_{skill.get('id')}"):
                            _db_skills.client.table("learned_skills").update({
                                "status": "archived",
                            }).eq("id", skill["id"]).execute()
                            st.success(f"Skill '{selected_name}' arquivada!")
                            st.rerun()
        else:
            alert_banner(
                "Nenhuma skill aprendida ainda. Diga ao IAlex pelo WhatsApp: "
                "*'padroniza isso'* depois de uma resposta que voce gostou, "
                "ou crie uma skill abaixo.",
                "info",
            )

        st.divider()

        # --- Criar nova skill ---
        with st.expander("Criar nova skill"):
            with st.form("create_skill_form", clear_on_submit=True):
                sk_name = st.text_input("Nome da skill *", placeholder="ex: email_pressao_enem")
                sk_type = st.selectbox("Tipo", [
                    "email_template", "report_format", "analysis_pattern",
                    "response_style", "whatsapp_template", "other",
                ])
                sk_desc = st.text_input("Descricao", placeholder="Breve descricao do padrao")
                sk_trigger = st.text_input("Gatilho (keywords)", placeholder="ex: pressao, enem, competitivo")
                sk_content = st.text_area("Conteudo/Template *", height=150,
                    placeholder="O padrao que o IAlex deve seguir quando o contexto bater...")
                sk_ex_in = st.text_input("Exemplo de input (opcional)", placeholder="O que o usuario pede")
                sk_ex_out = st.text_area("Exemplo de output (opcional)", height=100,
                    placeholder="Como o IAlex deve responder")

                submitted = st.form_submit_button("Criar Skill", type="primary")
                if submitted:
                    if not sk_name or not sk_content:
                        st.error("Nome e conteudo sao obrigatorios.")
                    else:
                        _db_skills.client.table("learned_skills").insert({
                            "name": sk_name.strip(),
                            "description": sk_desc.strip() or None,
                            "skill_type": sk_type,
                            "trigger_pattern": sk_trigger.strip() or None,
                            "template_content": sk_content.strip(),
                            "example_input": sk_ex_in.strip() or None,
                            "example_output": sk_ex_out.strip() or None,
                            "status": "active",
                            "created_by": "dashboard",
                        }).execute()
                        st.success(f"Skill '{sk_name}' criada com sucesso!")
                        st.rerun()

        # --- Skills arquivadas ---
        if archived_skills:
            with st.expander(f"Skills arquivadas ({len(archived_skills)})"):
                for s in archived_skills[:10]:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.text(f"{s.get('name', '')} ({s.get('skill_type', '')})")
                    with col2:
                        if st.button("Reativar", key=f"reactivate_{s.get('id')}"):
                            _db_skills.client.table("learned_skills").update({
                                "status": "active",
                            }).eq("id", s["id"]).execute()
                            st.success(f"Skill '{s.get('name')}' reativada!")
                            st.rerun()

    except Exception as e:
        st.error(f"Erro ao carregar skills: {e}")
        st.info("Verifique se a tabela 'learned_skills' foi criada no Supabase.")

with tab_diag:
    render_diagnostico()

# =============================================================================
# TAB: VENDAS & AGENDA (Rodada 4 — parametros do agenda_config + matriz modelos)
# =============================================================================
with tab_vendas:
    try:
        from utils.sender_profile import is_admin as _va_is_admin
        _va_admin = _va_is_admin()
    except Exception:
        _va_admin = False

    from integrations.agenda_config import agenda_config as _ag_cfg
    _va_cfg = _ag_cfg.get_config()

    section_header("Parametros de venda e agenda", "tune")
    st.caption(
        "Valores que alimentam o Potencial R$/mes (Escolas/Prospectar), o teto de "
        "leads em conversa (Home) e os limites diarios de envio por canal."
    )

    if not _va_admin:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ticket por aluno", f"R$ {_va_cfg['ticket_por_aluno']:.2f}")
        c2.metric("Teto em conversa", _va_cfg["teto_em_conversa"])
        c3.metric("Limite e-mail/dia", _va_cfg["limite_email_dia"])
        c4.metric("Limite WhatsApp/dia", _va_cfg["limite_whatsapp_dia"])
        alert_banner("Somente o gestor (admin) altera estes parametros.", "info")
    else:
        with st.form(key="va_form_params"):
            _vc1, _vc2 = st.columns(2)
            with _vc1:
                _va_ticket = st.number_input(
                    "Ticket por aluno (R$/mes)", min_value=0.10, max_value=500.0,
                    value=float(_va_cfg["ticket_por_aluno"]), step=0.01, format="%.2f",
                    help="Base do Potencial R$/mes: alunos-alvo x este valor.",
                )
                _va_teto = st.number_input(
                    "Teto de leads em conversa (por vendedor)", min_value=1, max_value=100,
                    value=int(_va_cfg["teto_em_conversa"]),
                    help="Acima disso a Home alerta para fechar ou descartar antes de abrir novos.",
                )
            with _vc2:
                _va_lim_email = st.number_input(
                    "Limite de e-mails/dia (por vendedor)", min_value=1, max_value=500,
                    value=int(_va_cfg["limite_email_dia"]),
                    help="Anti-bloqueio de remetente (reputacao do dominio).",
                )
                _va_lim_wpp = st.number_input(
                    "Limite de WhatsApp/dia (por vendedor)", min_value=1, max_value=200,
                    value=int(_va_cfg["limite_whatsapp_dia"]),
                    help="Anti-ban do numero (Baileys).",
                )
            if st.form_submit_button("Salvar parametros", type="primary"):
                _va_cfg.update({
                    "ticket_por_aluno": _va_ticket,
                    "teto_em_conversa": int(_va_teto),
                    "limite_email_dia": int(_va_lim_email),
                    "limite_whatsapp_dia": int(_va_lim_wpp),
                })
                if _ag_cfg.save_config(_va_cfg):
                    st.success("Parametros salvos. Valem imediatamente em todo o sistema.")
                else:
                    st.error("Falha ao salvar — veja os logs.")

        # ----- Ausencias (ferias) — SPEC §5.2 -----
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Ausencias (ferias)", "beach_access")
        st.caption(
            "Vendedor ausente nao recebe atividades novas do motor da agenda ate a "
            "data marcada; os leads dele seguem visiveis pro gestor reatribuir."
        )
        try:
            from workflows.activity_engine import all_usernames as _va_all_users
            _va_users = sorted(_va_all_users())
        except Exception:
            _va_users = []
        _va_away = _va_cfg.get("away") or {}
        if _va_away:
            for _u, _until in sorted(_va_away.items()):
                _ac1, _ac2 = st.columns([4, 1])
                _ac1.markdown(f"🏖️ **{_u}** — ausente ate **{_until}**")
                if _ac2.button("Remover", key=f"va_away_rm_{_u}"):
                    _ag_cfg.set_away(_u, None)
                    st.rerun()
        else:
            st.caption("Ninguem marcado como ausente.")
        if _va_users:
            with st.form(key="va_form_away"):
                _fc1, _fc2 = st.columns(2)
                _va_away_user = _fc1.selectbox("Vendedor:", _va_users)
                _va_away_until = _fc2.date_input("Ausente ate:")
                if st.form_submit_button("Marcar ausencia"):
                    if _ag_cfg.set_away(_va_away_user, _va_away_until.isoformat()):
                        st.success(f"{_va_away_user} ausente ate {_va_away_until}.")
                        st.rerun()
                    else:
                        st.error("Falha ao salvar ausencia.")

    # ----- Selecao automatica de modelos (matriz fina prometida no banner) -----
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Selecao automatica de modelos", "grid_view")
    st.caption(
        "No modo 'Template auto por alvo', o sistema escolhe o modelo pela matriz "
        "publico (nominal/generico) × dados (matriculas/ENEM). Cobertura atual:"
    )
    try:
        from database.supabase_client import db as _va_db
        _va_tpls = (
            _va_db.client.table("message_templates").select("*")
            .eq("is_active", True).execute().data or []
        )
        from utils.template_selector import matriz_cobertura as _va_matriz
        _va_cob = _va_matriz(_va_tpls)
        _va_cols = st.columns(2)
        for _i, _item in enumerate(_va_cob):
            with _va_cols[_i % 2]:
                _icon = "✅" if _item["coberto"] else "⬜"
                _names = ", ".join(_item["templates"][:2]) if _item["templates"] else "_(faltando)_"
                st.markdown(f"{_icon} **{_item['label']}** — {_names}")
        _va_pess = len([t for t in _va_tpls if (t.get("visibility") or "shared") != "shared"])
        st.caption(
            f"{len(_va_tpls)} modelos ativos ({_va_pess} pessoais). "
            "Criacao e edicao ficam em Mensagens → 📄 Modelos."
        )
    except Exception as _e_va_m:
        st.caption(f"(matriz indisponivel: {_e_va_m})")
    try:
        st.page_link("pages/6_✉️_Comunicacao.py", label="Abrir Mensagens → Modelos", icon="📄")
    except Exception:
        # fora do st.navigation (ex: AppTest standalone) o page_link nao resolve
        st.caption("Criacao/edicao: ✉️ Mensagens → 📄 Modelos")