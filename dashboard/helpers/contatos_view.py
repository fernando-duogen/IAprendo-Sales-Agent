"""Visao "Pessoas" (Power Map global) — extraida de 3_👥_Contatos.py (rodada 5).

Renderizada como secao da pagina Escolas. A pagina antiga virou casca.
"""
import streamlit as st

from dashboard.theme import (
    metric_card, status_badge, section_header,
    alert_banner, avatar, COLORS, STATUS_COLORS, score_color,
)
from dashboard.helpers.table_select import (
    reset_if_rows_changed, selected_positions,
)
from database.supabase_client import db
from utils.role_classifier import POWER_MAP_ROLES, ROLE_LABELS, ALL_ROLE_TYPES

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
    "web_search": "Busca web (IA)",
    "perplexity": "Perplexity (legado)",  # contatos historicos
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



def render_contatos() -> None:
    """Power Map de decisores de todas as escolas (lista + hierarquia)."""
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
        from dashboard.helpers.school_lookup import get_crm_schools as _get_crm_c, format_school_option as _fmt_c, parse_inep_from_option as _parse_c
        _crm_c = _get_crm_c()
        _crm_c_opts = ["(todas)"] + [_fmt_c(n, i) for n, i in _crm_c]
        _sel_c = st.selectbox("Buscar escola:", _crm_c_opts, label_visibility="collapsed", key="contato_escola_search")
        search = ""  # compatibilidade com filtro downstream
        if _sel_c != "(todas)":
            _inep_c = _parse_c(_sel_c)
            search = _inep_c if _inep_c else _sel_c
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
            "id,name,inep_code,city,state,qualification_score,status,"
            "matriculas_fund_af,matriculas_medio,nivel_tecnologico,"
            "qt_coordenadores,fonte_dados,categoria_privada,admin_dependency"
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
        if search.isdigit():
            filtered = [c for c in filtered if str(c.get("inep_code", "")).strip() == search]
        else:
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

    # ===========================================================================
    # SECAO: COBERTURA DE CONTATOS (expansivel)
    # ===========================================================================
    with st.expander("📊 Cobertura de contatos (insights + gaps prioritarios)", expanded=False):
        import pandas as pd
        import plotly.express as px
        from utils.contact_stats import compute_contact_coverage, rank_sem_contato_por_fit
        from utils.fit_score import calcular_fit_score

        stats = compute_contact_coverage(all_companies, all_contacts)

        def _cor_pct(pct: float) -> str:
            """Verde >=80%, amarelo 50-80%, vermelho <50%."""
            if pct >= 80:
                return COLORS["success"]
            if pct >= 50:
                return COLORS["warning"]
            return COLORS["error"]

        cov1, cov2, cov3, cov4 = st.columns(4)
        with cov1:
            metric_card(
                "% com Email",
                f"{stats['pct_com_email']}%",
                _cor_pct(stats["pct_com_email"]),
                icon="email",
            )
        with cov2:
            metric_card(
                "% com WhatsApp",
                f"{stats['pct_com_whatsapp']}%",
                _cor_pct(stats["pct_com_whatsapp"]),
                icon="chat",
            )
        with cov3:
            metric_card(
                "% com Diretor",
                f"{stats['pct_com_diretor']}%",
                _cor_pct(stats["pct_com_diretor"]),
                icon="school",
            )
        with cov4:
            metric_card(
                "% Diretor + Email",
                f"{stats['pct_com_diretor_email']}%",
                _cor_pct(stats["pct_com_diretor_email"]),
                icon="verified_user",
            )

        st.caption(
            f"Base: **{stats['total_escolas']} escolas**, "
            f"**{stats['total_contatos']} contatos**. "
            f"{len(stats['escolas_sem_contato_ids'])} escolas sem nenhum contato, "
            f"{len(stats['escolas_sem_email_ids'])} sem email, "
            f"{len(stats['escolas_sem_whatsapp_ids'])} sem WhatsApp."
        )

        st.markdown("")

        # Grafico de fonte dos contatos
        if stats["por_fonte"]:
            SRC_LABELS_FULL = {
                "web_search": "Busca web (IA)",
                "perplexity": "Perplexity (legado)",
                "hunter": "Hunter.io",
                "apollo": "Apollo.io",
                "web_scraping": "Scraping",
                "manual": "Manual",
                "email_pattern": "Padrao de email",
                "deduced:nome.sobrenome": "Deduzido (nome.sobrenome)",
                "snov": "Snov",
                "placeholder": "Placeholder",
                "desconhecida": "Desconhecida",
            }
            df_fonte = pd.DataFrame([
                {"Fonte": SRC_LABELS_FULL.get(k, k), "Contatos": v}
                for k, v in stats["por_fonte"].items()
            ]).sort_values("Contatos", ascending=False)

            fig_fonte = px.pie(
                df_fonte,
                values="Contatos",
                names="Fonte",
                title="Contatos por fonte de coleta",
                hole=0.4,
            )
            fig_fonte.update_traces(textposition="inside", textinfo="percent+label")
            fig_fonte.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_fonte, use_container_width=True)

        st.markdown("")

        # Top 10 escolas sem contato, priorizadas por Fit
        top_sem_contato = rank_sem_contato_por_fit(
            all_companies, stats["escolas_sem_contato_ids"], calcular_fit_score, limite=10
        )
        top_sem_email = rank_sem_contato_por_fit(
            all_companies, stats["escolas_sem_email_ids"], calcular_fit_score, limite=10
        )

        col_gap1, col_gap2 = st.columns(2)
        with col_gap1:
            st.markdown("**🚨 Top 10 escolas SEM contato, por Fit IAprendo**")
            if top_sem_contato:
                df_sc = pd.DataFrame([{
                    "Escola": t["name"][:38],
                    "Cidade": f"{t['city'] or ''}/{t['state'] or ''}",
                    "Alvo": t["alvo"],
                    "Fit": t["fit"],
                } for t in top_sem_contato])
                st.dataframe(
                    df_sc,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100),
                        "Alvo": st.column_config.NumberColumn("Alvo"),
                    },
                )
            else:
                st.caption("Nenhuma escola sem contato — cobertura total.")

        with col_gap2:
            st.markdown("**📭 Top 10 escolas SEM email, por Fit IAprendo**")
            if top_sem_email:
                df_se = pd.DataFrame([{
                    "Escola": t["name"][:38],
                    "Cidade": f"{t['city'] or ''}/{t['state'] or ''}",
                    "Alvo": t["alvo"],
                    "Fit": t["fit"],
                } for t in top_sem_email])
                st.dataframe(
                    df_se,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Fit": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100),
                        "Alvo": st.column_config.NumberColumn("Alvo"),
                    },
                )
            else:
                st.caption("Nenhuma escola sem email — todas cobertas.")

        st.caption(
            "💡 Essas sao as escolas com maior potencial (Fit IAprendo) que "
            "ainda nao tem contato ou email. Priorize-as no enriquecimento."
        )

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
        wpp_str = ct.get("phone_whatsapp", "") or ""
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
                f'{"<br/><span style=font-size:11px;color:#757575>☎️ " + phone_str + "</span>" if phone_str else ""}'
                f'{"<br/><span style=font-size:11px;color:#25D366>📱 " + wpp_str + "</span>" if wpp_str else ""}'
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
    # TABS: Lista (tabela) + Hierarquia (Power Map)
    # ===========================================================================
    DM_TYPE_LABEL = {
        "diretor": "👔 Diretor",
        "vice_diretor": "🧑‍💼 Vice-Diretor",
        "coordenador_pedagogico": "📋 Coord. Pedagogico",
        "secretaria": "📝 Secretaria",
        "administrativo": "💼 Administrativo",
        "outro": "👤 Outro",
    }

    tab_lista, tab_hierarquia = st.tabs(["📋 Lista", "🏛️ Hierarquia (Power Map)"])

    # ===========================================================================
    # TAB 1: LISTA — Tabela completa com filtros avançados, agrupamento e ações
    # ===========================================================================
    with tab_lista:
        import unicodedata
        import pandas as pd

        def _normalize_name(name: str) -> str:
            """Normaliza nome para deteccao de duplicatas: lowercase, sem acentos."""
            if not name:
                return ""
            nfkd = unicodedata.normalize("NFKD", name)
            ascii_str = nfkd.encode("ASCII", "ignore").decode("ASCII")
            return " ".join(ascii_str.lower().split())

        def _find_duplicates(contacts_list):
            """Encontra grupos de contatos duplicados (mesmo email OR mesmo nome normalizado)."""
            by_key = {}
            for ct in contacts_list:
                email = (ct.get("email") or "").strip().lower()
                name_norm = _normalize_name(ct.get("full_name") or "")
                key = f"email:{email}" if email else f"name:{name_norm}"
                if not email and not name_norm:
                    continue
                by_key.setdefault(key, []).append(ct)
            return [group for group in by_key.values() if len(group) > 1]

        # Montar lista plana de contatos das escolas filtradas
        filtered_ids = {c["id"] for c in filtered}
        company_by_id = {c["id"]: c for c in all_companies}
        contatos_plano = []
        for ct in all_contacts:
            cid = ct.get("company_id")
            if cid not in filtered_ids:
                continue
            comp = company_by_id.get(cid, {})
            contatos_plano.append({
                "id": ct.get("id"),
                "company_id": cid,
                "Escola": comp.get("name", "?"),
                "Cidade": comp.get("city", ""),
                "UF": comp.get("state", ""),
                "Score Escola": comp.get("qualification_score") or 0,
                "Nome": ct.get("full_name") or "?",
                "Cargo": ct.get("role") or "",
                "Tipo": DM_TYPE_LABEL.get(ct.get("decision_maker_type", "outro"), "👤 Outro"),
                "Email": ct.get("email") or "",
                "Telefone": ct.get("phone") or "",
                "WhatsApp": ct.get("phone_whatsapp") or "",
                "Prioridade": ct.get("outreach_priority") or 99,
                "Fonte": SRC_LABELS.get(ct.get("source", ""), ct.get("source", "") or ""),
                "Confiança": ct.get("confidence_score") or 0,
            })

        # Detectar duplicatas (por escola) para mostrar aviso + botao de limpeza
        total_duplicatas = 0
        duplicatas_por_escola = {}
        for comp in filtered:
            cid = comp["id"]
            cts = contacts_by_company.get(cid, [])
            dup_groups = _find_duplicates(cts)
            if dup_groups:
                duplicatas_por_escola[cid] = dup_groups
                total_duplicatas += sum(len(g) - 1 for g in dup_groups)

        # ------------------- FILTROS AVANÇADOS -------------------
        st.markdown(
            '<p style="font-size:12px;font-weight:600;color:#757575;text-transform:uppercase;'
            'letter-spacing:0.5px;margin-bottom:4px">Filtros e agrupamento</p>',
            unsafe_allow_html=True,
        )
        # Linha 1: busca + UF + Cidade (cascata UF → Cidade)
        fcA, fcB, fcC = st.columns([3, 1.5, 2.5])
        with fcA:
            ct_search = st.text_input(
                "Buscar (nome, escola, email, cargo):",
                placeholder="Digite qualquer texto...",
                key="ct_global_search",
            )
        with fcB:
            ufs_disp_ct = sorted({c["UF"] for c in contatos_plano if c.get("UF")})
            ct_uf = st.multiselect(
                "UF:", ufs_disp_ct, default=[],
                key="ct_uf_filter", placeholder="Todas",
            )
        with fcC:
            # Cidade filtrada pela UF (cascata)
            if ct_uf:
                cidades_pool_ct = [c for c in contatos_plano if c.get("UF") in ct_uf]
            else:
                cidades_pool_ct = contatos_plano
            cidades_disp_ct = sorted({c["Cidade"] for c in cidades_pool_ct if c.get("Cidade")})
            ct_cidade = st.multiselect(
                "Cidade:", cidades_disp_ct, default=[],
                key="ct_cidade_filter", placeholder="Todas",
            )
        # Linha 2: tipo + email + agrupar
        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            tipo_opts = sorted({c["Tipo"] for c in contatos_plano})
            ct_tipo = st.multiselect("Tipo de decisor:", tipo_opts, default=[], key="ct_tipo_filter")
        with fc2:
            ct_email_filter = st.selectbox(
                "Email:",
                ["Todos", "Com email", "Sem email"],
                key="ct_email_filter",
            )
        with fc3:
            ct_group_by = st.selectbox(
                "Agrupar por:",
                ["Nenhum (tabela plana)", "Escola", "Cidade/UF", "Tipo", "Fonte"],
                key="ct_group_by",
            )

        # Aplicar filtros
        filtered_cts = contatos_plano
        if ct_search:
            q = ct_search.lower()
            filtered_cts = [
                c for c in filtered_cts
                if q in c["Nome"].lower()
                or q in c["Escola"].lower()
                or q in c["Email"].lower()
                or q in c["Cargo"].lower()
            ]
        if ct_uf:
            filtered_cts = [c for c in filtered_cts if c.get("UF") in ct_uf]
        if ct_cidade:
            filtered_cts = [c for c in filtered_cts if c.get("Cidade") in ct_cidade]
        if ct_tipo:
            filtered_cts = [c for c in filtered_cts if c["Tipo"] in ct_tipo]
        if ct_email_filter == "Com email":
            filtered_cts = [c for c in filtered_cts if c["Email"]]
        elif ct_email_filter == "Sem email":
            filtered_cts = [c for c in filtered_cts if not c["Email"]]

        # ------------------- EXPORT DAS ESCOLAS FILTRADAS -------------------
        if filtered_cts:
            try:
                from utils.export_utils import escolas_to_xlsx_bytes, export_filename
                _exp_company_ids = sorted({c["company_id"] for c in filtered_cts if c.get("company_id")})
                _exp_cols = st.columns([2, 8])
                with _exp_cols[0]:
                    if _exp_company_ids:
                        _xlsx = escolas_to_xlsx_bytes(_exp_company_ids)
                        st.download_button(
                            f"📥 Exportar XLSX ({len(_exp_company_ids)} escolas)",
                            data=_xlsx,
                            file_name=export_filename("contatos_iaprendo", "xlsx"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                            help="Baixa XLSX com escolas filtradas + todos seus contatos",
                        )
            except Exception as _ex_ct_exp:
                st.caption(f"Export indisponivel: {_ex_ct_exp}")

        # ------------------- AVISO DUPLICATAS -------------------
        if total_duplicatas > 0:
            dup_col1, dup_col2 = st.columns([3, 1])
            with dup_col1:
                alert_banner(
                    f"Detectei {total_duplicatas} contato(s) duplicado(s) em {len(duplicatas_por_escola)} escola(s).",
                    "warning",
                )
            with dup_col2:
                if st.button(
                    f"Remover {total_duplicatas} duplicatas",
                    type="primary",
                    icon=":material/cleaning_services:",
                    use_container_width=True,
                    key="btn_remove_dups",
                ):
                    removed = 0
                    for cid, dup_groups in duplicatas_por_escola.items():
                        for group in dup_groups:
                            def _score(c):
                                return (
                                    c.get("confidence_score") or 0,
                                    1 if c.get("email") else 0,
                                    1 if c.get("phone") else 0,
                                    -((c.get("outreach_priority") or 99)),
                                )
                            sorted_group = sorted(group, key=_score, reverse=True)
                            for c in sorted_group[1:]:
                                try:
                                    db.client.table("contacts").delete().eq("id", c["id"]).execute()
                                    removed += 1
                                except Exception:
                                    pass
                    st.success(f"Removidas {removed} duplicatas!")
                    st.rerun()

        # ------------------- EXIBIÇÃO -------------------
        if not filtered_cts:
            alert_banner("Nenhum contato encontrado com esses filtros.", "info")
        else:
            col_defs = {
                "Escola": st.column_config.TextColumn("Escola", width="medium"),
                "Cidade": st.column_config.TextColumn("Cidade", width="small"),
                "UF": st.column_config.TextColumn("UF", width="small"),
                "Score Escola": st.column_config.ProgressColumn("Score", width="small", min_value=0, max_value=100, format="%d"),
                "Nome": st.column_config.TextColumn("Nome", width="medium"),
                "Cargo": st.column_config.TextColumn("Cargo", width="medium"),
                "Tipo": st.column_config.TextColumn("Tipo", width="small"),
                "Email": st.column_config.TextColumn("Email", width="medium"),
                "Telefone": st.column_config.TextColumn("Telefone", width="small"),
                "WhatsApp": st.column_config.TextColumn("📱 WhatsApp", width="small"),
                "Prioridade": st.column_config.NumberColumn("Prior.", width="small", format="%d"),
                "Fonte": st.column_config.TextColumn("Fonte", width="small"),
                "Confiança": st.column_config.ProgressColumn("Confiança", width="small", min_value=0, max_value=100, format="%d"),
            }
            display_cols = ["Escola", "Cidade", "UF", "Nome", "Cargo", "Tipo", "Email", "Telefone", "WhatsApp", "Prioridade", "Fonte", "Confiança", "Score Escola"]

            # ========== TABELA PLANA (sem agrupamento) ==========
            if ct_group_by == "Nenhum (tabela plana)":
                st.caption(f"Exibindo {len(filtered_cts)} contato(s). Ordene clicando nos cabeçalhos. Clique em uma linha para ver ações.")

                df_contatos = pd.DataFrame(filtered_cts)
                # A selecao do st.dataframe e POSICIONAL e sobrevive a mudanca de
                # filtro (ver dashboard/helpers/table_select.py). Sem isto, mudar
                # o filtro fazia "Excluir" apagar OUTRO contato — sem confirmacao.
                _flat_dropped = reset_if_rows_changed(
                    "contatos_table_flat", [c.get("id") for c in filtered_cts])
                selected = st.dataframe(
                    df_contatos[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config=col_defs,
                    height=500,
                    key="contatos_table_flat",
                )
                if _flat_dropped:
                    st.caption("A lista mudou (filtro) — a selecao anterior foi limpa "
                               "para nao agir no contato errado.")

                # Ações rápidas abaixo da tabela quando uma linha é selecionada
                selected_rows = selected_positions(selected, len(filtered_cts))
                if not selected_rows:
                    st.session_state.pop("ct_flat_confirm_del", None)
                if selected_rows:
                    sel = filtered_cts[selected_rows[0]]
                    st.markdown(
                        '<p style="font-size:12px;font-weight:600;color:#757575;text-transform:uppercase;'
                        'letter-spacing:0.5px;margin-top:12px;margin-bottom:4px">Ações rápidas</p>',
                        unsafe_allow_html=True,
                    )
                    ac1, ac2, ac3, ac4 = st.columns([3, 1, 1, 1])
                    with ac1:
                        st.markdown(f"**{sel['Nome']}** — _{sel['Escola']}_ ({sel['Tipo']})")
                    with ac2:
                        if st.button("Editar", type="primary", icon=":material/edit:",
                                      use_container_width=True, key="ct_flat_edit"):
                            st.session_state["editing_contact"] = sel["id"]
                            st.session_state["editing_company"] = sel["company_id"]
                            st.rerun()
                    with ac3:
                        if st.button("Ver escola", icon=":material/school:",
                                      use_container_width=True, key="ct_flat_school"):
                            st.session_state["escola_detail_id"] = sel["company_id"]
                            st.switch_page("pages/2_🏫_Escolas.py")
                    with ac4:
                        # Exclusao de contato era o unico destrutivo do painel SEM
                        # confirmacao — 1 clique apagava (e, com selecao orfa, o
                        # contato errado). Agora 2 passos, com o alvo no rotulo.
                        _flat_cfk = "ct_flat_confirm_del"
                        if st.session_state.get(_flat_cfk) == sel["id"]:
                            if st.button("⚠️ Confirmar", type="primary",
                                          use_container_width=True, key="ct_flat_del_yes",
                                          help=f"Excluir definitivamente {sel['Nome']}"):
                                try:
                                    db.client.table("contacts").delete().eq(
                                        "id", sel["id"]).execute()
                                    st.session_state.pop(_flat_cfk, None)
                                    st.toast(f"{sel['Nome']} excluido.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao excluir: {e}")
                        else:
                            if st.button("Excluir", icon=":material/delete:",
                                          use_container_width=True, key="ct_flat_del",
                                          help="Clique 2x para confirmar (irreversivel)"):
                                st.session_state[_flat_cfk] = sel["id"]
                                st.rerun()

            # ========== TABELA AGRUPADA ==========
            else:
                group_key_map = {
                    "Escola": "Escola",
                    "Cidade/UF": "Cidade",
                    "Tipo": "Tipo",
                    "Fonte": "Fonte",
                }
                group_col = group_key_map[ct_group_by]
                groups = {}
                for c in filtered_cts:
                    key = c[group_col] or "(sem valor)"
                    if ct_group_by == "Cidade/UF":
                        key = f"{c.get('Cidade') or '?'}/{c.get('UF') or '?'}"
                    groups.setdefault(key, []).append(c)

                # Ordenar grupos pelo tamanho (maior primeiro)
                sorted_groups = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
                st.caption(f"Exibindo {len(filtered_cts)} contato(s) em {len(sorted_groups)} grupo(s). Clique em um grupo para expandir.")

                expand_all_groups = st.checkbox("Expandir todos os grupos", value=False, key="ct_expand_all")

                # Colunas visíveis dentro de cada grupo (remover a coluna usada como grupo)
                inner_cols = [c for c in display_cols if c != group_col]
                if ct_group_by == "Cidade/UF":
                    inner_cols = [c for c in inner_cols if c not in ("Cidade", "UF")]
                inner_col_defs = {k: v for k, v in col_defs.items() if k in inner_cols}

                for _gi, (group_name, group_cts) in enumerate(sorted_groups):
                    header = f"📁 {group_name} — {len(group_cts)} contato(s)"
                    with st.expander(header, expanded=expand_all_groups):
                        df_group = pd.DataFrame(group_cts)
                        # Chave por INDICE, nao pelo nome do grupo: a chave antiga
                        # (f"ct_group_{group_name}") vinha do dado, entao renomear
                        # uma escola destruia o widget e a selecao sumia. O reset
                        # abaixo cobre a reordenacao dos grupos.
                        _gkey = f"ct_group_{_gi}"
                        _grp_dropped = reset_if_rows_changed(
                            _gkey, [c.get("id") for c in group_cts])
                        sel_group = st.dataframe(
                            df_group[inner_cols],
                            use_container_width=True,
                            hide_index=True,
                            on_select="rerun",
                            selection_mode="single-row",
                            column_config=inner_col_defs,
                            key=_gkey,
                        )
                        if _grp_dropped:
                            st.caption("A lista deste grupo mudou — a selecao anterior "
                                       "foi limpa para nao agir no contato errado.")
                        sel_rows = selected_positions(sel_group, len(group_cts))
                        if sel_rows:
                            sel_ct = group_cts[sel_rows[0]]
                            ac1, ac2, ac3, ac4 = st.columns([3, 1, 1, 1])
                            with ac1:
                                st.markdown(f"**{sel_ct['Nome']}** — _{sel_ct['Escola']}_")
                            with ac2:
                                if st.button("Editar", type="primary", icon=":material/edit:",
                                              use_container_width=True, key=f"ct_g_edit_{sel_ct['id']}"):
                                    st.session_state["editing_contact"] = sel_ct["id"]
                                    st.session_state["editing_company"] = sel_ct["company_id"]
                                    st.rerun()
                            with ac3:
                                if st.button("Ver escola", icon=":material/school:",
                                              use_container_width=True, key=f"ct_g_sch_{sel_ct['id']}"):
                                    st.session_state["escola_detail_id"] = sel_ct["company_id"]
                                    st.switch_page("pages/2_🏫_Escolas.py")
                            with ac4:
                                _grp_cfk = "ct_group_confirm_del"
                                if st.session_state.get(_grp_cfk) == sel_ct["id"]:
                                    if st.button("⚠️ Confirmar", type="primary",
                                                  use_container_width=True,
                                                  key=f"ct_g_del_yes_{sel_ct['id']}",
                                                  help=f"Excluir definitivamente {sel_ct['Nome']}"):
                                        try:
                                            db.client.table("contacts").delete().eq(
                                                "id", sel_ct["id"]).execute()
                                            st.session_state.pop(_grp_cfk, None)
                                            st.toast(f"{sel_ct['Nome']} excluido.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro ao excluir: {e}")
                                else:
                                    if st.button("Excluir", icon=":material/delete:",
                                                  use_container_width=True,
                                                  key=f"ct_g_del_{sel_ct['id']}",
                                                  help="Clique 2x para confirmar (irreversivel)"):
                                        st.session_state[_grp_cfk] = sel_ct["id"]
                                        st.rerun()

    # ===========================================================================
    # TAB 2: HIERARQUIA — Power Map (visualizacao original)
    # ===========================================================================
    with tab_hierarquia:
        st.caption("Organograma de decisores por escola. Hierarquia: Direcao > Coordenacao > Apoio.")

        # Busca e ordenacao dentro da hierarquia
        hc1, hc2, hc3 = st.columns([3, 1, 1])
        with hc1:
            hier_search = st.text_input(
                "Buscar escola:",
                placeholder="Digite parte do nome da escola...",
                label_visibility="collapsed",
                key="hier_search",
            )
        with hc2:
            hier_sort = st.selectbox(
                "Ordenar por:",
                ["Mais contatos", "Nome (A-Z)", "Cobertura", "Score"],
                label_visibility="collapsed",
                key="hier_sort",
            )
        with hc3:
            hier_expand_all = st.checkbox("Expandir todas", value=False, key="hier_expand")

        # Filtrar e ordenar
        filtered_hier = filtered
        if hier_search:
            filtered_hier = [c for c in filtered_hier if hier_search.lower() in c.get("name", "").lower()]

        if hier_sort == "Mais contatos":
            filtered_hier = sorted(filtered_hier, key=lambda c: len(contacts_by_company.get(c["id"], [])), reverse=True)
        elif hier_sort == "Nome (A-Z)":
            filtered_hier = sorted(filtered_hier, key=lambda c: (c.get("name") or "").lower())
        elif hier_sort == "Cobertura":
            filtered_hier = sorted(filtered_hier, key=lambda c: calc_coverage(contacts_by_company.get(c["id"], [])), reverse=True)
        elif hier_sort == "Score":
            filtered_hier = sorted(filtered_hier, key=lambda c: c.get("qualification_score") or 0, reverse=True)

        if not filtered_hier:
            alert_banner(f"Nenhuma escola encontrada com '{hier_search}'.", "warning")
            st.stop()

        st.caption(f"Exibindo {len(filtered_hier)} escola(s)")

        for company in filtered_hier:
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

            with st.expander(f"{school_name} -- {company.get('city', '')}{score_str} | {len(contacts)} contatos", expanded=hier_expand_all):
                st.markdown(
                    f'<span class="badge" style="background:{cov_color}20;color:{cov_color}">{cov_label}</span>',
                    unsafe_allow_html=True,
                )

                if not contacts:
                    st.caption("Nenhum contato encontrado. Use 'Buscar contatos na web (IA)' na pagina Escolas.")
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

