"""Pagina 5 - Mapa de Poder: organograma de decisores por escola com cards coloridos e edicao."""
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, avatar, breadcrumb, COLORS, STATUS_COLORS, score_color,
)

apply_theme_no_config()

try:
    from database.supabase_client import db
    from utils.role_classifier import POWER_MAP_ROLES, ROLE_LABELS, ALL_ROLE_TYPES
except Exception as e:
    st.error(f"Erro ao importar modulos: {e}")
    st.stop()

# Hierarquia para o organograma
HIERARCHY = [
    {"key": "diretor", "label": "Direcao", "icon": "school", "level": 0, "color": COLORS["primary"]},
    {"key": "vice_diretor", "label": "Vice-Direcao", "icon": "supervisor_account", "level": 0, "color": COLORS["info"]},
    {"key": "coordenador_pedagogico", "label": "Coord. Pedagogica", "icon": "menu_book", "level": 1, "color": COLORS["secondary"]},
    {"key": "secretaria", "label": "Secretaria", "icon": "assignment", "level": 2, "color": COLORS["warning"]},
    {"key": "administrativo", "label": "Administrativo", "icon": "business_center", "level": 2, "color": COLORS["accent"]},
    {"key": "outro", "label": "Outros", "icon": "person", "level": 2, "color": COLORS["on_surface_secondary"]},
]

HIERARCHY_BY_KEY = {h["key"]: h for h in HIERARCHY}

SRC_LABELS = {
    "perplexity": "Perplexity",
    "hunter": "Hunter",
    "apollo": "Apollo",
    "web_scraping": "Scraping",
    "manual": "Manual",
    "email_pattern": "Padrao",
    "snov": "Snov",
}

# Tipos de decisor para select
DM_TYPES = [
    ("diretor", "Diretor(a)"),
    ("vice_diretor", "Vice-Diretor(a)"),
    ("coordenador_pedagogico", "Coord. Pedagogico(a)"),
    ("secretaria", "Secretaria"),
    ("administrativo", "Administrativo"),
    ("outro", "Outro"),
]

# ===========================================================================
# HEADER
# ===========================================================================
section_header("Mapa de Poder", "hub")
st.caption("Organograma de decisores por escola. Hierarquia: Direcao > Coordenacao > Apoio. Clique em Editar para alterar dados.")

# ===========================================================================
# FILTROS — barra horizontal no topo
# ===========================================================================
col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
with col_f1:
    search = st.text_input("Buscar escola:", placeholder="Nome da escola...", label_visibility="collapsed")
with col_f2:
    coverage_filter = st.selectbox("Cobertura:", ["Todos", "Completa", "Parcial", "Sem decisor"],
                                   label_visibility="collapsed")
with col_f3:
    show_limit = st.selectbox("Exibir:", [25, 50, 100], index=0, label_visibility="collapsed")

# ===========================================================================
# CARREGAR DADOS
# ===========================================================================
try:
    all_companies = db.client.table("companies").select(
        "id,name,city,state,qualification_score,status"
    ).order("qualification_score", desc=True).limit(200).execute().data or []
except Exception as e:
    st.error(f"Erro: {e}")
    st.stop()

if not all_companies:
    alert_banner("Nenhuma escola no banco.", "info")
    st.stop()

try:
    all_contacts = db.client.table("contacts").select(
        "id,company_id,full_name,role,email,phone,phone_whatsapp,source,"
        "decision_maker_type,outreach_priority,confidence_score"
    ).execute().data or []
except Exception:
    all_contacts = []

contacts_by_company = {}
for c in all_contacts:
    cid = c.get("company_id")
    if cid not in contacts_by_company:
        contacts_by_company[cid] = []
    contacts_by_company[cid].append(c)


def calc_coverage(contacts):
    if not contacts:
        return 0
    found = set()
    for c in contacts:
        dm = c.get("decision_maker_type")
        if dm in POWER_MAP_ROLES and c.get("email"):
            found.add(dm)
    return len(found)


# Filtros aplicados
filtered = all_companies
if search:
    filtered = [c for c in filtered if search.lower() in c.get("name", "").lower()]
if coverage_filter == "Completa":
    filtered = [c for c in filtered if calc_coverage(contacts_by_company.get(c["id"], [])) == 3]
elif coverage_filter == "Parcial":
    filtered = [c for c in filtered if 0 < calc_coverage(contacts_by_company.get(c["id"], [])) < 3]
elif coverage_filter == "Sem decisor":
    filtered = [c for c in filtered if calc_coverage(contacts_by_company.get(c["id"], [])) == 0]
filtered = filtered[:show_limit]

# ===========================================================================
# METRICAS
# ===========================================================================
total = len(all_companies)
com_diretor = sum(1 for c in all_companies if any(
    ct.get("decision_maker_type") == "diretor" and ct.get("email")
    for ct in contacts_by_company.get(c["id"], [])))
total_contacts = len(all_contacts)
com_email = sum(1 for ct in all_contacts if ct.get("email"))

mc1, mc2, mc3, mc4 = st.columns(4)
with mc1:
    metric_card("Escolas", total, COLORS["primary"], icon="domain")
with mc2:
    metric_card("Com Diretor+Email", com_diretor, COLORS["success"], icon="verified_user")
with mc3:
    metric_card("Total Contatos", total_contacts, COLORS["info"], icon="contacts")
with mc4:
    metric_card("Com Email", com_email, COLORS["secondary"], icon="email")

st.markdown("")

if not filtered:
    alert_banner("Nenhuma escola encontrada com os filtros atuais.", "warning")
    st.stop()

st.caption(f"Exibindo {len(filtered)} escolas")

# ===========================================================================
# FUNCAO DE CARD DE CONTATO — Versao simplificada sem div aninhado
# ===========================================================================
def render_contact_card_md(ct, h, company_id, col):
    """Renderiza contato como texto simples com botao editar."""
    ct_id = ct.get("id")
    role_detail = ct.get("role", "") or h["label"]
    email_str = ct.get("email", "") or "sem email"
    phone_str = ct.get("phone", "") or ""
    src = ct.get("source", "")
    src_label = SRC_LABELS.get(src, src)
    card_color = h.get("color", COLORS["primary"])

    with col:
        st.markdown(
            f'<p style="background:#FFF;border-radius:8px;padding:10px 12px;margin-bottom:6px;'
            f'box-shadow:0 1px 2px rgba(0,0,0,0.06);border-left:3px solid {card_color}">'
            f'<strong style="font-size:13px;color:#212121">{ct.get("full_name", "?")}</strong><br/>'
            f'<span style="font-size:11px;color:#757575">{role_detail}</span><br/>'
            f'<span style="font-size:11px;color:#1976D2">{email_str}</span>'
            f'{"<br/><span style=font-size:11px;color:#757575>" + phone_str + "</span>" if phone_str else ""}'
            f'</p>',
            unsafe_allow_html=True,
        )
        if st.button("Editar", key=f"edit_ct_{ct_id}", use_container_width=True,
                      icon=":material/edit:"):
            st.session_state["editing_contact"] = ct_id
            st.session_state["editing_company"] = company_id


# ===========================================================================
# MODAL DE EDICAO
# ===========================================================================
editing_id = st.session_state.get("editing_contact")
if editing_id:
    ct_current = None
    for ct in all_contacts:
        if ct.get("id") == editing_id:
            ct_current = ct
            break

    if ct_current:
        company_name = "?"
        for c in all_companies:
            if c["id"] == ct_current.get("company_id"):
                company_name = c.get("name", "?")
                break

        st.divider()
        section_header(f"Editando: {ct_current.get('full_name', '?')} -- {company_name}", "edit")

        with st.form(key="edit_contact_form"):
            ec1, ec2 = st.columns(2)
            with ec1:
                new_name = st.text_input("Nome completo", value=ct_current.get("full_name", ""))
                new_role = st.text_input("Cargo / Funcao", value=ct_current.get("role", ""),
                                         help="Ex: Coord. Pedagogica - Anos Finais e Medio")
                current_dm = ct_current.get("decision_maker_type", "outro")
                dm_options = [d[0] for d in DM_TYPES]
                dm_idx = dm_options.index(current_dm) if current_dm in dm_options else len(dm_options) - 1
                new_dm = st.selectbox("Tipo de decisor", options=dm_options,
                                      format_func=lambda x: dict(DM_TYPES).get(x, x),
                                      index=dm_idx)
            with ec2:
                new_email = st.text_input("Email", value=ct_current.get("email", "") or "")
                new_phone = st.text_input("Telefone", value=ct_current.get("phone", "") or "")
                new_whatsapp = st.text_input("WhatsApp", value=ct_current.get("phone_whatsapp", "") or "")
                priority_options = [1, 2, 3, 5, 99]
                priority_labels = {1: "1 - Alta (Diretor)", 2: "2 - Alta (Vice)", 3: "3 - Media (Coord.)", 5: "5 - Baixa (Apoio)", 99: "99 - Outro"}
                current_pri = ct_current.get("outreach_priority", 99)
                pri_idx = priority_options.index(current_pri) if current_pri in priority_options else len(priority_options) - 1
                new_priority = st.selectbox("Prioridade de contato", options=priority_options,
                                            format_func=lambda x: priority_labels.get(x, str(x)),
                                            index=pri_idx)

            fc1, fc2, fc3 = st.columns([1, 1, 2])
            with fc1:
                save_btn = st.form_submit_button("Salvar", type="primary", use_container_width=True,
                                                  icon=":material/save:")
            with fc2:
                cancel_btn = st.form_submit_button("Cancelar", use_container_width=True,
                                                    icon=":material/close:")
            with fc3:
                delete_btn = st.form_submit_button("Excluir contato", use_container_width=True,
                                                    icon=":material/delete:")

            if save_btn:
                update_data = {
                    "full_name": new_name.strip(),
                    "role": new_role.strip(),
                    "email": new_email.strip() or None,
                    "phone": new_phone.strip() or None,
                    "phone_whatsapp": new_whatsapp.strip() or None,
                    "decision_maker_type": new_dm,
                    "outreach_priority": new_priority,
                }
                try:
                    db.client.table("contacts").update(update_data).eq("id", editing_id).execute()
                    st.session_state.pop("editing_contact", None)
                    st.success("Contato atualizado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

            if cancel_btn:
                st.session_state.pop("editing_contact", None)
                st.rerun()

            if delete_btn:
                st.session_state["confirm_delete_contact"] = editing_id

    # Confirmacao de exclusao
    if st.session_state.get("confirm_delete_contact") == editing_id:
        alert_banner(f"Tem certeza que deseja excluir {ct_current.get('full_name', '?')}?", "error")
        dc1, dc2 = st.columns(2)
        with dc1:
            if st.button("Sim, excluir", type="primary", icon=":material/delete:"):
                try:
                    db.client.table("contacts").delete().eq("id", editing_id).execute()
                    st.session_state.pop("editing_contact", None)
                    st.session_state.pop("confirm_delete_contact", None)
                    st.success("Contato excluido!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro: {e}")
        with dc2:
            if st.button("Nao, cancelar"):
                st.session_state.pop("confirm_delete_contact", None)
                st.rerun()

    st.divider()

# ===========================================================================
# ORGANOGRAMA POR ESCOLA — Cards coloridos por hierarquia
# ===========================================================================
for company in filtered:
    company_id = company["id"]
    school_name = company.get("name", "?")
    score = company.get("qualification_score")
    contacts = contacts_by_company.get(company_id, [])
    cov = calc_coverage(contacts)

    # Coverage badge
    if cov == 3:
        cov_color = COLORS["success"]
        cov_label = "Completa"
    elif cov > 0:
        cov_color = COLORS["warning"]
        cov_label = "Parcial"
    else:
        cov_color = COLORS["error"]
        cov_label = "Sem decisor"

    score_str = f" | Score: {score}" if score is not None else ""
    header_html = f"""
    <div style="display:flex; align-items:center; gap:8px;">
        <span class="badge" style="background:{cov_color}20;color:{cov_color}">{cov_label}</span>
        <span style="font-weight:600;">{school_name}</span>
        <span style="color:#757575; font-size:13px;">{company.get('city', '')}{score_str} | {len(contacts)} contatos</span>
    </div>
    """

    with st.expander(f"{school_name} -- {company.get('city', '')}{score_str} | {len(contacts)} contatos"):
        # Show coverage badge inside
        st.markdown(f'<span class="badge" style="background:{cov_color}20;color:{cov_color}">{cov_label}</span>',
                    unsafe_allow_html=True)

        if not contacts:
            st.caption("Nenhum contato encontrado. Use o Perplexity na pagina Escolas para buscar.")
            continue

        # Agrupar por tipo de decisor
        by_type = {}
        for ct in contacts:
            dm = ct.get("decision_maker_type", "outro")
            if dm not in by_type:
                by_type[dm] = []
            by_type[dm].append(ct)

        # --- Nivel 0: Direcao (topo, lado a lado) ---
        top_roles = [h for h in HIERARCHY if h["level"] == 0]
        top_cols = st.columns(len(top_roles))
        for col, h in zip(top_cols, top_roles):
            with col:
                role_contacts = by_type.get(h["key"], [])
                st.markdown(
                    f'<p style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                    f'<span class="material-icons-outlined" style="font-size:18px;color:{h["color"]}">{h["icon"]}</span>'
                    f'<strong style="font-size:14px">{h["label"]}</strong></p>',
                    unsafe_allow_html=True,
                )
                if role_contacts:
                    for ct in role_contacts:
                        render_contact_card_md(ct, h, company_id, col)
                else:
                    st.caption("_vazio_")

        # --- Nivel 1: Coordenacao (meio) ---
        mid_roles = [h for h in HIERARCHY if h["level"] == 1]
        for h in mid_roles:
            role_contacts = by_type.get(h["key"], [])
            if role_contacts:
                st.markdown("---")
                st.markdown(
                    f'<p style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                    f'<span class="material-icons-outlined" style="font-size:18px;color:{h["color"]}">{h["icon"]}</span>'
                    f'<strong style="font-size:14px">{h["label"]}</strong>'
                    f'<span style="font-size:12px;color:#757575">({len(role_contacts)})</span></p>',
                    unsafe_allow_html=True,
                )
                mid_cols = st.columns(min(len(role_contacts), 4))
                for i, ct in enumerate(role_contacts):
                    render_contact_card_md(ct, h, company_id, mid_cols[i % len(mid_cols)])

        # --- Nivel 2: Apoio (base) ---
        bottom_roles = [h for h in HIERARCHY if h["level"] == 2]
        bottom_contacts = []
        for h in bottom_roles:
            for ct in by_type.get(h["key"], []):
                bottom_contacts.append((h, ct))

        if bottom_contacts:
            st.markdown("---")
            st.markdown(
                f'<p style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
                f'<span class="material-icons-outlined" style="font-size:18px;color:{COLORS["on_surface_secondary"]}">groups</span>'
                f'<strong style="font-size:14px">Apoio e outros</strong>'
                f'<span style="font-size:12px;color:#757575">({len(bottom_contacts)})</span></p>',
                unsafe_allow_html=True,
            )
            bot_cols = st.columns(min(len(bottom_contacts), 4))
            for i, (h, ct) in enumerate(bottom_contacts):
                render_contact_card_md(ct, h, company_id, bot_cols[i % len(bot_cols)])
