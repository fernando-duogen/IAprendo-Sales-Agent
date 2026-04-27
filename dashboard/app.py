"""IAprendo Sales Agent - Central de Comando (Material Design)."""
import os
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta

# === Streamlit Cloud: copiar secrets para os.environ ANTES de tudo ===
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ[_k] = _v
except Exception:
    pass

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme, metric_card, metric_card_clickable, action_tile, section_header, alert_banner,
    COLORS, STATUS_COLORS, timeline_item,
)

apply_theme()

# =========================================================================
# AUTENTICACAO (streamlit-authenticator) — gate de TODAS as paginas
# =========================================================================
# config/users.yaml e gitignored. Localmente vem do arquivo.
# No Streamlit Cloud: copiar secao "auth" do users.yaml para Secrets (TOML).
import yaml
import streamlit_authenticator as stauth

_AUTH_PATH = ROOT / "config" / "users.yaml"
_auth_config = None
try:
    if _AUTH_PATH.exists():
        with _AUTH_PATH.open("r", encoding="utf-8") as _f:
            _auth_config = yaml.safe_load(_f)
    elif "auth" in st.secrets:
        # Streamlit Cloud: secrets.toml com secao [auth] estruturada
        _auth_config = dict(st.secrets["auth"])
except Exception as _e:
    st.error(f"Falha ao carregar config de autenticacao: {_e}")
    st.stop()

if not _auth_config:
    st.error(
        "Config de autenticacao nao encontrada. "
        "Crie `config/users.yaml` (use `config/users.yaml.example` como template) "
        "ou configure `st.secrets['auth']` no Streamlit Cloud."
    )
    st.stop()

authenticator = stauth.Authenticate(
    _auth_config["credentials"],
    _auth_config["cookie"]["name"],
    _auth_config["cookie"]["key"],
    _auth_config["cookie"]["expiry_days"],
)

# Renderiza form de login (popula st.session_state automaticamente)
try:
    authenticator.login(location="main")
except Exception as _e:
    st.error(f"Erro no login: {_e}")
    st.stop()

if st.session_state.get("authentication_status") is False:
    st.error("Usuario ou senha incorretos")
    st.stop()
elif st.session_state.get("authentication_status") is None:
    st.warning("Faca login para acessar o IAprendo")
    st.info(
        "**Primeira vez?** Senhas iniciais foram entregues pelo administrador. "
        "Recomendamos trocar pela sidebar apos o login."
    )
    st.stop()

# A partir daqui o usuario esta autenticado
_current_user = _auth_config["credentials"]["usernames"].get(
    st.session_state.get("username", ""), {}
)

# Sidebar: identidade + logout + trocar senha
with st.sidebar:
    st.markdown(
        f'<div style="padding:12px 8px;border-bottom:1px solid #E0E0E0;margin-bottom:8px">'
        f'<div style="font-size:11px;color:#9E9E9E;text-transform:uppercase;letter-spacing:0.5px">Logado como</div>'
        f'<div style="font-weight:600;color:#212121">{_current_user.get("name", "?")}</div>'
        f'<div style="font-size:12px;color:#757575">{_current_user.get("email", "?")} &middot; {_current_user.get("role", "")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    authenticator.logout("Sair", location="sidebar")
    with st.expander("Trocar senha", icon=":material/lock_reset:"):
        try:
            if authenticator.reset_password(
                st.session_state.get("username"), location="main"
            ):
                # Persistir nova senha no users.yaml
                with _AUTH_PATH.open("w", encoding="utf-8") as _f:
                    yaml.safe_dump(_auth_config, _f, allow_unicode=True, sort_keys=False)
                st.success("Senha atualizada. Use no proximo login.")
        except Exception as _e:
            st.error(f"Erro ao trocar senha: {_e}")

# =========================================================================
# HEADER
# =========================================================================
st.markdown(
    '<h1 style="margin-bottom:0">IAprendo Sales Agent</h1>'
    '<p style="color:#757575;margin-top:4px;font-size:15px">'
    'Central de comando &mdash; prospeccao B2B para escolas</p>',
    unsafe_allow_html=True,
)

# =========================================================================
# BUSCA GLOBAL
# =========================================================================
search_query = st.text_input(
    "Busca rapida",
    placeholder="Digite nome de escola, contato ou email...",
    key="global_search",
    label_visibility="collapsed",
)

if search_query and len(search_query) >= 2:
    try:
        from database.supabase_client import db
        term = f"%{search_query}%"

        schools = db.client.table("companies").select(
            "id,name,city,status,qualification_score"
        ).ilike("name", term).limit(10).execute().data or []

        contacts_name = db.client.table("contacts").select(
            "id,full_name,email,role,company_id,companies(name)"
        ).ilike("full_name", term).limit(10).execute().data or []

        contacts_email = db.client.table("contacts").select(
            "id,full_name,email,role,company_id,companies(name)"
        ).ilike("email", term).limit(10).execute().data or []

        contacts_all = {c["id"]: c for c in contacts_name + contacts_email}.values()
        total_results = len(schools) + len(list(contacts_all))

        if total_results > 0:
            st.caption(f"{total_results} resultado(s) encontrado(s)")
            if schools:
                section_header("Escolas", "school")
                for s in schools:
                    score = s.get("qualification_score") or 0
                    st.markdown(
                        f'<div class="data-card">'
                        f'<strong>{s["name"]}</strong> &mdash; {s.get("city", "?")}'
                        f'<br><span style="color:#757575;font-size:13px">'
                        f'Status: {s.get("status", "?")} &bull; Score: {score}</span></div>',
                        unsafe_allow_html=True,
                    )
            contacts_list = list(contacts_all)
            if contacts_list:
                section_header("Contatos", "person")
                for c in contacts_list:
                    comp = c.get("companies") or {}
                    st.markdown(
                        f'<div class="data-card">'
                        f'<strong>{c.get("full_name", "?")}</strong> ({c.get("role", "?")})'
                        f'<br><span style="color:#757575;font-size:13px">'
                        f'{c.get("email", "&mdash;")} &bull; Escola: {comp.get("name", "?")}</span></div>',
                        unsafe_allow_html=True,
                    )
        else:
            st.caption(f"Nenhum resultado para '{search_query}'")
    except Exception as e:
        st.warning(f"Erro na busca: {e}")

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# =========================================================================
# CENTRAL DE COMANDO - KPIs
# =========================================================================
try:
    from database.supabase_client import db
    from approval_queue import queue_manager

    all_companies = db.client.table("companies").select(
        "id,status,qualification_score"
    ).execute().data or []
    stats = queue_manager.get_stats()

    total = len(all_companies)
    raw = len([c for c in all_companies if c.get("status") == "raw"])
    qualified = len([c for c in all_companies if c.get("status") == "qualified"])
    enriched = len([c for c in all_companies if c.get("status") == "enriched"])
    pending = stats.get("pending", 0)
    approved = stats.get("approved", 0)
    sent = stats.get("sent", 0)

    sent_items = db.client.table("approval_queue").select(
        "id,sent_at,opened_at,clicked_at,replied_at,bounced_at,follow_up_number"
    ).eq("status", "sent").execute().data or []

    opened = len([s for s in sent_items if s.get("opened_at")])
    clicked = len([s for s in sent_items if s.get("clicked_at")])
    replied = len([s for s in sent_items if s.get("replied_at")])

    try:
        from workflows.follow_up_manager import get_due_follow_ups
        due_fups = get_due_follow_ups(limit=50)
        due_count = len(due_fups)
    except Exception:
        due_count = 0

    try:
        from tools.notification_manager import notification_manager
        unread = notification_manager.get_unread_count()
    except Exception:
        unread = 0

    # === ALERT BANNERS ===
    if pending > 0:
        alert_banner(f"<strong>{pending} email(s)</strong> aguardando sua aprovacao na Fila de Aprovacao", "warning")
    if approved > 0:
        alert_banner(f"<strong>{approved} email(s)</strong> aprovados prontos para envio", "success")
    if due_count > 0:
        alert_banner(f"<strong>{due_count} escola(s)</strong> precisam de follow-up", "info")
    if unread > 0:
        alert_banner(f"<strong>{unread} notificacao(oes)</strong> nao lida(s)", "info")

    # === PAINEL (grid 4+3 tiles — sem redundancia com HubSpot futuro) ===
    section_header("Painel", "dashboard")

    row1 = st.columns(4)
    with row1[0]:
        if action_tile("school", "Escolas", f"{total} cadastradas",
                       color=COLORS["primary"], key="tile_escolas"):
            st.switch_page("pages/1_🏫_Escolas.py")
    with row1[1]:
        if action_tile("contacts", "Contatos", "Gerenciar decisores",
                       color=COLORS["success"], key="tile_contatos"):
            st.switch_page("pages/2_👥_Contatos.py")
    with row1[2]:
        if action_tile("rocket_launch", "Pipeline", "Execucao + pipeline comercial",
                       color=COLORS["primary"], key="tile_pipeline"):
            st.switch_page("pages/5_📊_Pipeline.py")
    with row1[3]:
        # Tile Comunicacao — consolida aprovacao + follow-ups + emails
        comm_parts = []
        if pending > 0:
            comm_parts.append(f"{pending} pendente(s)")
        if due_count > 0:
            comm_parts.append(f"{due_count} follow-up(s)")
        sub_comm = " · ".join(comm_parts) if comm_parts else f"{sent} enviados"
        color_comm = COLORS["warning"] if pending > 0 else (COLORS["accent"] if due_count > 0 else COLORS["info"])
        if action_tile("mail", "Comunicacao", sub_comm, color=color_comm,
                       key="tile_comunicacao", highlight=pending > 0 or due_count > 0):
            st.switch_page("pages/6_✉️_Comunicacao.py")

    row2 = st.columns(4)
    with row2[0]:
        if action_tile("insights", "Inteligencia", "ENEM + Radar + Analytics",
                       color=COLORS["info"], key="tile_inteligencia"):
            st.switch_page("pages/7_🎯_Inteligencia.py")
    with row2[1]:
        sub_emails = f"{sent} enviados · {opened} abertos" if sent else "Nenhum enviado"
        if action_tile("bar_chart", "Analytics", sub_emails, color=COLORS["primary"],
                       key="tile_analytics"):
            st.switch_page("pages/8_📈_Analytics.py")
    with row2[2]:
        if action_tile("map", "Mapa", "Visualizacao geografica",
                       color=COLORS["primary"], key="tile_mapa"):
            st.switch_page("pages/3_🗺️_Mapa.py")
    with row2[3]:
        # Tile Diagnostico — health check com cor dinamica
        @st.cache_data(ttl=30, show_spinner=False)
        def _cached_health_summary() -> dict:
            try:
                from tools.health_check import run_health_check
                return run_health_check()
            except Exception as _e:
                return {"overall": "unknown", "summary": f"falha: {str(_e)[:40]}"}

        health = _cached_health_summary()
        overall = health.get("overall", "unknown")
        overall_color = {
            "healthy": COLORS["success"],
            "degraded": COLORS["warning"],
            "critical": COLORS["error"],
            "unknown": COLORS["primary"],
        }[overall]
        health_sub = health.get("summary", "verificando...")
        is_hot = overall in ("degraded", "critical")
        if action_tile("health_and_safety", "Diagnostico", health_sub,
                       color=overall_color, key="tile_diagnostico",
                       highlight=is_hot):
            st.switch_page("pages/9_⚙️_Configuracoes.py")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # === PAINEL DIARIO ACIONAVEL (F7 - Action Panel) ===
    try:
        from dashboard.helpers.morning_panel import render_action_panel
        render_action_panel()
    except Exception as e:
        st.caption(f"Painel diario indisponivel: {e}")
        # Fallback: widget antigo de hot leads
        try:
            from dashboard.helpers.urgency_widgets import hot_leads_widget
            section_header("Leads Quentes", "local_fire_department")
            hot_leads_widget()
        except Exception:
            pass

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # === ATIVIDADE RECENTE ===
    section_header("Atividade Recente", "history")
    try:
        recent_sent = db.client.table("approval_queue").select(
            "subject,sent_at,companies(name),contacts(full_name)"
        ).eq("status", "sent").order("sent_at", desc=True).limit(5).execute().data or []

        if recent_sent:
            timeline_html = ""
            for item in recent_sent:
                comp = item.get("companies") or {}
                ct = item.get("contacts") or {}
                sent_at = (item.get("sent_at") or "")[:16].replace("T", " ")
                timeline_html += timeline_item(
                    date=sent_at,
                    title=f'{comp.get("name", "?")} \u2192 {ct.get("full_name", "?")}',
                    detail=item.get("subject", "")[:60],
                    color=COLORS["primary"],
                )
            st.markdown(timeline_html, unsafe_allow_html=True)
        else:
            st.caption("Nenhuma atividade recente.")
    except Exception:
        st.caption("Nenhuma atividade recente.")

    # === API USAGE ===
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Uso de APIs (ultimos 7 dias)", "api")
    try:
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        api_usage = db.client.table("api_usage").select(
            "api_name,credits_used"
        ).gte("created_at", seven_days_ago).execute().data or []

        if api_usage:
            api_costs = {}
            for u in api_usage:
                name = u.get("api_name", "?")
                api_costs[name] = api_costs.get(name, 0) + (u.get("credits_used") or 1)

            api_icons = {
                "anthropic": "smart_toy", "apollo": "search", "hunter": "mail",
                "snov": "contact_mail", "brevo": "send", "google": "cloud",
            }
            cost_cols = st.columns(min(len(api_costs), 5))
            for i, (api_name, count) in enumerate(sorted(api_costs.items(), key=lambda x: -x[1])):
                with cost_cols[i % len(cost_cols)]:
                    icon = api_icons.get(api_name.lower(), "memory")
                    metric_card(api_name.capitalize(), f"{count}", icon=icon,
                                color=COLORS["secondary"])
        else:
            st.caption("Nenhum uso de API registrado nos ultimos 7 dias.")
    except Exception:
        st.caption("Tabela api_usage nao disponivel.")

except Exception as e:
    st.warning(f"Nao foi possivel carregar dados: {e}")
    section_header("Como usar", "help")
    st.markdown("Use o **menu lateral** para navegar entre as paginas.")

st.markdown('<hr class="divider">', unsafe_allow_html=True)
st.caption("Fluxo: Importar \u2192 Pipeline \u2192 Aprovar \u2192 Enviar \u2192 Acompanhar via pipeline comercial + IAlex")
