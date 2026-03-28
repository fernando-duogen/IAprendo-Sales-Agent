"""
Pagina de Follow-ups, Tracking e Metricas.
Gerencia sequencias de follow-up, visualiza aberturas/cliques e deduz emails.
Redesigned com Material Design theme.
"""
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, status_badge, section_header,
    alert_banner, timeline_item, breadcrumb, pipeline_stepper, COLORS, STATUS_COLORS,
)

apply_theme_no_config()

# --- Header ---
breadcrumb(["IAprendo", "Follow-ups & Metricas"])
st.markdown("# Follow-ups & Metricas")
st.caption("Gerencie sequencias de follow-up, visualize aberturas/cliques e deduza emails.")

# --- Tabs principais ---
tab_metrics, tab_followups, tab_deduce, tab_timeline = st.tabs([
    "Metricas de Email",
    "Follow-ups",
    "Deducao de Emails",
    "Timeline por Escola",
])

# =============================================================================
# TAB 1: METRICAS
# =============================================================================
with tab_metrics:
    try:
        from database.supabase_client import db

        # Buscar dados
        sent = db.client.table("approval_queue").select(
            "id,sent_at,opened_at,clicked_at,replied_at,bounced_at,company_id,contact_id,subject,follow_up_number"
        ).eq("status", "sent").execute().data or []
        pending = db.client.table("approval_queue").select("id").eq("status", "pending").execute().data or []
        approved = db.client.table("approval_queue").select("id").eq("status", "approved").execute().data or []

        total_sent = len(sent)
        total_opened = len([s for s in sent if s.get("opened_at")])
        total_clicked = len([s for s in sent if s.get("clicked_at")])
        total_replied = len([s for s in sent if s.get("replied_at")])
        total_bounced = len([s for s in sent if s.get("bounced_at")])

        # KPIs — metric cards
        section_header("Performance de Emails", "analytics")
        c1, c2, c3 = st.columns(3)
        with c1:
            metric_card(
                "Enviados", total_sent,
                color=COLORS["primary"], icon="send",
            )
        with c2:
            metric_card(
                "Abertos", total_opened,
                color=COLORS["secondary"],
                delta=f"{total_opened/total_sent*100:.0f}%" if total_sent else "0%",
                icon="visibility",
            )
        with c3:
            metric_card(
                "Clicados", total_clicked,
                color=COLORS["info"],
                delta=f"{total_clicked/total_sent*100:.0f}%" if total_sent else "0%",
                icon="touch_app",
            )

        st.markdown('<div class="mt-2"></div>', unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        with c4:
            metric_card(
                "Respondidos", total_replied,
                color=COLORS["success"],
                delta=f"{total_replied/total_sent*100:.0f}%" if total_sent else "0%",
                icon="reply",
            )
        with c5:
            metric_card(
                "Rejeitado", total_bounced,
                color=COLORS["error"],
                delta=f"{total_bounced/total_sent*100:.0f}%" if total_sent else "0%",
                icon="error_outline",
            )
        with c6:
            metric_card(
                "Pendentes", len(pending) + len(approved),
                color=COLORS["warning"], icon="schedule",
            )

        # Funil visual — stepper
        if total_sent > 0:
            st.markdown('<div class="mt-3"></div>', unsafe_allow_html=True)
            section_header("Funil de Conversao", "filter_alt")
            pipeline_stepper([
                {"label": "Enviados", "count": total_sent, "color": COLORS["primary"]},
                {"label": "Abertos", "count": total_opened, "color": COLORS["secondary"]},
                {"label": "Clicados", "count": total_clicked, "color": COLORS["info"]},
                {"label": "Respondidos", "count": total_replied, "color": COLORS["success"]},
            ])

            import pandas as pd
            funil_data = pd.DataFrame({
                "Etapa": ["Enviados", "Abertos", "Clicados", "Respondidos"],
                "Quantidade": [total_sent, total_opened, total_clicked, total_replied],
            })
            st.bar_chart(funil_data.set_index("Etapa"), height=300)

        # Sync tracking
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Sincronizar Tracking", "sync")
        st.caption("Busca eventos de abertura e clique no Brevo para atualizar as metricas.")

        if st.button("Sincronizar eventos do Brevo", type="primary"):
            try:
                from tools.email_tracker import email_tracker as tracker
                with st.spinner("Buscando eventos no Brevo..."):
                    result = tracker.sync_tracking_events()
                if result.get("error"):
                    st.error(f"Erro: {result['error']}")
                else:
                    updated = result.get("updated", 0)
                    alert_banner(f"Sincronizado! {updated} eventos atualizados.", "success")
                    if updated > 0:
                        st.rerun()
            except ImportError:
                alert_banner("Modulo de tracking nao disponivel. Verifique tools/email_tracker.py", "warning")
            except Exception as e:
                st.error(f"Erro: {e}")

        # Tabela de emails enviados com status de tracking
        if sent:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            section_header("Emails Enviados - Status de Tracking", "email")
            import pandas as pd
            rows = []
            for s in sorted(sent, key=lambda x: x.get("sent_at", ""), reverse=True):
                fu = s.get("follow_up_number", 0)
                fu_label = f"FU-{fu}" if fu > 0 else "Inicial"
                rows.append({
                    "Assunto": (s.get("subject") or "")[:50],
                    "Tipo": fu_label,
                    "Enviado": (s.get("sent_at") or "")[:16],
                    "Aberto": "Sim" if s.get("opened_at") else "Nao",
                    "Clicado": "Sim" if s.get("clicked_at") else "Nao",
                    "Respondido": "Sim" if s.get("replied_at") else "Nao",
                    "Rejeitado": "Sim" if s.get("bounced_at") else "--",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Erro ao carregar metricas: {e}")

# =============================================================================
# TAB 2: FOLLOW-UPS
# =============================================================================
with tab_followups:
    try:
        from database.supabase_client import db

        section_header("Gerenciar Follow-ups", "autorenew")
        alert_banner(
            "O sistema gera follow-ups automaticamente para escolas que receberam email "
            "mas nao responderam. Cada follow-up passa pela fila de aprovacao antes do envio.",
            "info",
        )

        # Sequencias configuradas — stepper visual
        try:
            sequences = db.client.table("follow_up_sequences").select("*").execute().data or []
        except Exception:
            sequences = []

        if sequences:
            for seq in sequences:
                active = seq.get("is_active", False)
                badge = status_badge("active", "Ativo") if active else status_badge("paused", "Pausado")
                st.markdown(
                    f'<div class="data-card"><div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<strong>{seq["name"]}</strong>{badge}</div></div>',
                    unsafe_allow_html=True,
                )

                steps = seq.get("steps", [])
                if isinstance(steps, str):
                    import json
                    steps = json.loads(steps)

                if steps:
                    stepper_stages = []
                    colors_cycle = [COLORS["primary"], COLORS["secondary"], COLORS["accent"], COLORS["success"], "#7B1FA2"]
                    for i, step in enumerate(steps):
                        stepper_stages.append({
                            "label": step.get("label", f"Passo {step['step']}"),
                            "count": f"+{step['days_after']}d" if step["days_after"] > 0 else "Agora",
                            "color": colors_cycle[i % len(colors_cycle)],
                        })
                    pipeline_stepper(stepper_stages)

        # Verificar follow-ups pendentes
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Follow-ups Pendentes", "pending_actions")

        if st.button("Verificar follow-ups pendentes", type="primary"):
            try:
                from workflows import follow_up_manager
                with st.spinner("Verificando escolas que precisam de follow-up..."):
                    due = follow_up_manager.get_due_follow_ups()

                if due:
                    alert_banner(f"{len(due)} escolas precisam de follow-up!", "success")
                    import pandas as pd
                    rows = []
                    for d in due:
                        rows.append({
                            "Escola": d.get("company_name", "?"),
                            "Contato": d.get("contact_name", "?"),
                            "Email": d.get("contact_email", "?"),
                            "Ultimo envio": (d.get("last_sent_at") or "")[:10],
                            "Dias sem resposta": d.get("days_since_last", 0),
                            "Proximo FU": f"Follow-up {d.get('next_follow_up', 1)}",
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    if st.button("Gerar follow-ups para aprovacao"):
                        with st.spinner("Gerando mensagens de follow-up..."):
                            result = follow_up_manager.run_follow_up_check()
                        alert_banner(
                            f"Gerados {result.get('generated', 0)} follow-ups! Veja na Fila de Aprovacao.",
                            "success",
                        )
                else:
                    alert_banner("Nenhuma escola precisa de follow-up no momento.", "info")
            except ImportError:
                alert_banner("Modulo de follow-up nao disponivel. Verifique workflows/follow_up_manager.py", "warning")
            except Exception as e:
                st.error(f"Erro: {e}")

        # Historico de follow-ups — timeline visual
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        section_header("Historico de Follow-ups", "history")
        try:
            fups = db.client.table("approval_queue").select(
                "id,subject,status,sent_at,follow_up_number,opened_at,replied_at"
            ).gt("follow_up_number", 0).order("created_at", desc=True).limit(20).execute().data or []

            if fups:
                timeline_html = ""
                for f in fups:
                    fu_num = f.get("follow_up_number", 0)
                    status = f.get("status", "?")
                    date_str = (f.get("sent_at") or "--")[:10]
                    subject = (f.get("subject") or "")[:50]
                    detail_parts = [f"FU #{fu_num}"]
                    if f.get("opened_at"):
                        detail_parts.append("Aberto")
                    if f.get("replied_at"):
                        detail_parts.append("Respondido")
                    color = STATUS_COLORS.get(status, COLORS["primary"])
                    timeline_html += timeline_item(
                        date=date_str,
                        title=subject,
                        detail=" | ".join(detail_parts) + f" | {status_badge(status)}",
                        color=color,
                    )
                st.markdown(timeline_html, unsafe_allow_html=True)
            else:
                st.caption("Nenhum follow-up enviado ainda.")
        except Exception as e:
            st.error(f"Erro: {e}")

    except Exception as e:
        st.error(f"Erro: {e}")

# =============================================================================
# TAB 3: DEDUCAO DE EMAILS
# =============================================================================
with tab_deduce:
    try:
        from database.supabase_client import db

        section_header("Deducao Inteligente de Emails", "psychology")
        alert_banner(
            "Quando encontramos 1 email pessoal de uma escola (ex: fernanda.radajeski@escola.com), "
            "deduzimos o padrao e aplicamos para os outros contatos da mesma escola.",
            "info",
        )

        # Selecionar empresa
        companies = db.client.table("companies").select(
            "id,name,email_pattern,email_domain"
        ).order("name").execute().data or []

        if companies:
            options = {f"{c['name']} ({c.get('email_domain', '?')})": c["id"] for c in companies}
            selected = st.selectbox("Selecione uma escola:", list(options.keys()))
            company_id = options[selected]

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Analisar padroes", type="primary"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Analisando..."):
                        analysis = email_deducer.analyze(company_id)

                    st.session_state["deduce_analysis"] = analysis
                    personal_count = analysis.get(
                        "personal_emails", analysis.get("personal_emails_found", 0)
                    )

                    if analysis.get("pattern"):
                        alert_banner(
                            f"Padrao detectado: <strong>{analysis['pattern']}</strong> ({analysis['domain']})",
                            "success",
                        )
                        st.write(f"Emails pessoais encontrados: {personal_count}")
                    elif analysis.get("domain"):
                        alert_banner(
                            f"Dominio encontrado ({analysis['domain']}), mas sem email pessoal para detectar padrao.",
                            "warning",
                        )
                        st.write("Sera usado o padrao mais comum: **nome.sobrenome**")
                        st.caption(
                            "Dica: busque contatos no Perplexity (pagina Escolas) "
                            "para encontrar emails pessoais que ajudem a detectar o padrao."
                        )
                    elif analysis.get("suggested_patterns"):
                        alert_banner(
                            "Nenhum email pessoal encontrado, mas podemos tentar o padrao "
                            "<strong>nome.sobrenome</strong> se voce souber o dominio.",
                            "info",
                        )
                    else:
                        alert_banner(
                            "Nenhum email (pessoal ou de departamento) encontrado para esta escola.",
                            "warning",
                        )
                        st.caption(
                            "Dica: busque contatos no Perplexity (pagina Escolas ou Mapa) "
                            "para encontrar emails que permitam detectar o dominio e padrao."
                        )

            with col2:
                if st.button("Deduzir emails (preview)"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Deduzindo..."):
                        result = email_deducer.deduce_for_company(company_id, dry_run=True)

                    st.session_state["deduce_result"] = result

                    if result.get("deduced"):
                        alert_banner(
                            f"{len(result['deduced'])} emails deduzidos (padrao: {result['pattern']})",
                            "success",
                        )
                    elif result.get("error"):
                        st.error(result["error"])
                    else:
                        alert_banner(
                            "Todos os contatos ja tem email ou nao ha nomes suficientes.",
                            "info",
                        )

            # Mostrar preview
            if st.session_state.get("deduce_result", {}).get("deduced"):
                st.markdown('<hr class="divider">', unsafe_allow_html=True)
                result = st.session_state["deduce_result"]
                import pandas as pd

                section_header(
                    f"Emails deduzidos (padrao: {result['pattern']}@{result['domain']})",
                    "alternate_email",
                )
                rows = []
                for d in result["deduced"]:
                    rows.append({
                        "Nome": d["name"],
                        "Cargo": d.get("role", ""),
                        "Email deduzido": d["deduced_email"],
                        "Confianca": f"{d['confidence']}%",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                alert_banner(
                    "Emails deduzidos nao sao verificados. Podem nao existir.",
                    "warning",
                )

                if st.button("Salvar emails deduzidos no banco", type="primary"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Salvando..."):
                        save_result = email_deducer.deduce_for_company(company_id, dry_run=False)
                    alert_banner(f"Salvos {save_result.get('saved', 0)} emails!", "success")
                    st.session_state.pop("deduce_result", None)
                    st.rerun()

            # Deducao em massa
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            section_header("Deducao em Massa", "rocket_launch")
            st.caption("Deduz emails para TODAS as escolas que tem pelo menos 1 email pessoal.")

            if st.button("Deduzir para todas as escolas (preview)"):
                from tools.email_deducer import email_deducer
                with st.spinner("Analisando todas as escolas..."):
                    mass_result = email_deducer.deduce_all(dry_run=True)

                st.session_state["mass_deduce"] = mass_result

                if mass_result.get("total_deduced", 0) > 0:
                    alert_banner(
                        f"{mass_result['total_deduced']} emails podem ser deduzidos "
                        f"em {mass_result['total_companies']} escolas!",
                        "success",
                    )
                else:
                    alert_banner("Nenhum email pode ser deduzido no momento.", "info")

            if st.session_state.get("mass_deduce", {}).get("total_deduced", 0) > 0:
                mass = st.session_state["mass_deduce"]
                import pandas as pd
                rows = []
                for d in mass["details"]:
                    for email in d["emails"]:
                        rows.append({
                            "Escola": d["company"],
                            "Padrao": d["pattern"],
                            "Email deduzido": email,
                        })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                if st.button("Salvar todos os emails deduzidos", type="primary"):
                    from tools.email_deducer import email_deducer
                    with st.spinner("Salvando..."):
                        save_result = email_deducer.deduce_all(dry_run=False)
                    alert_banner(
                        f"Salvos {save_result.get('total_deduced', 0)} emails "
                        f"em {save_result.get('total_companies', 0)} escolas!",
                        "success",
                    )
                    st.session_state.pop("mass_deduce", None)
                    st.rerun()

        else:
            alert_banner("Nenhuma escola importada ainda.", "info")

    except Exception as e:
        st.error(f"Erro: {e}")

# =============================================================================
# TAB 4: TIMELINE POR ESCOLA
# =============================================================================
with tab_timeline:
    try:
        from database.supabase_client import db

        section_header("Timeline de Interacoes", "timeline")
        st.caption("Veja todo o historico de comunicacao com cada escola.")

        companies = db.client.table("companies").select("id,name").order("name").execute().data or []
        if companies:
            # Campo de busca
            search_term = st.text_input(
                "Buscar escola por nome:",
                placeholder="Digite o nome da escola...",
                key="timeline_search",
            )

            # Filtrar empresas pelo termo de busca
            filtered = companies
            if search_term:
                filtered = [c for c in companies if search_term.lower() in c["name"].lower()]

            if not filtered:
                alert_banner(f"Nenhuma escola encontrada com '{search_term}'.", "warning")
            else:
                options = {c["name"]: c["id"] for c in filtered}
                selected = st.selectbox(
                    "Selecione uma escola:", list(options.keys()), key="timeline_school"
                )
                company_id = options[selected]

                # Filtros
                fc1, fc2 = st.columns(2)
                with fc1:
                    event_filter = st.multiselect(
                        "Filtrar por tipo de evento:",
                        ["Enviado", "Pendente", "Aberto", "Clicado", "Respondido", "Rejeitado"],
                        default=[],
                        key="timeline_filter",
                    )
                with fc2:
                    sort_order = st.radio(
                        "Ordenar por:",
                        ["Mais recente primeiro", "Mais antigo primeiro"],
                        horizontal=True,
                        key="timeline_sort",
                    )

                # Buscar emails enviados
                emails = db.client.table("approval_queue").select(
                    "id,subject,status,sent_at,opened_at,clicked_at,replied_at,bounced_at,follow_up_number,created_at"
                ).eq("company_id", company_id).order("created_at", desc=True).execute().data or []

                if emails:
                    # Montar timeline unificada
                    events = []
                    type_colors = {
                        "Enviado": COLORS["primary"],
                        "Pendente": COLORS["warning"],
                        "Aberto": COLORS["secondary"],
                        "Clicado": COLORS["info"],
                        "Respondido": COLORS["success"],
                        "Rejeitado": COLORS["error"],
                    }

                    for e in emails:
                        fu = e.get("follow_up_number", 0)
                        label = f"Follow-up {fu}" if fu > 0 else "Email inicial"
                        status = e.get("status", "?")

                        if status == "sent":
                            events.append({
                                "data": (e.get("sent_at") or e.get("created_at") or "")[:19],
                                "tipo": "Enviado",
                                "evento": f"{label} enviado",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        elif status == "pending":
                            events.append({
                                "data": (e.get("created_at") or "")[:19],
                                "tipo": "Pendente",
                                "evento": f"{label} aguardando aprovacao",
                                "detalhe": (e.get("subject") or "")[:60],
                            })

                        if e.get("opened_at"):
                            events.append({
                                "data": e["opened_at"][:19],
                                "tipo": "Aberto",
                                "evento": "Email aberto",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("clicked_at"):
                            events.append({
                                "data": e["clicked_at"][:19],
                                "tipo": "Clicado",
                                "evento": "Link clicado",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("replied_at"):
                            events.append({
                                "data": e["replied_at"][:19],
                                "tipo": "Respondido",
                                "evento": "Resposta recebida!",
                                "detalhe": (e.get("subject") or "")[:60],
                            })
                        if e.get("bounced_at"):
                            events.append({
                                "data": e["bounced_at"][:19],
                                "tipo": "Rejeitado",
                                "evento": "Email bounced",
                                "detalhe": (e.get("subject") or "")[:60],
                            })

                    # Aplicar filtro de tipo
                    if event_filter:
                        events = [ev for ev in events if ev["tipo"] in event_filter]

                    # Ordenar
                    reverse = sort_order == "Mais recente primeiro"
                    events.sort(key=lambda x: x["data"], reverse=reverse)

                    if events:
                        st.caption(f"{len(events)} evento(s) encontrado(s)")
                        # Render as visual timeline
                        tl_html = ""
                        for ev in events:
                            color = type_colors.get(ev["tipo"], COLORS["primary"])
                            tl_html += timeline_item(
                                date=ev["data"],
                                title=ev["evento"],
                                detail=ev["detalhe"],
                                color=color,
                            )
                        st.markdown(tl_html, unsafe_allow_html=True)
                    else:
                        alert_banner("Nenhum evento corresponde aos filtros selecionados.", "info")
                else:
                    alert_banner("Nenhuma interacao registrada para esta escola.", "info")
        else:
            alert_banner("Nenhuma escola importada ainda.", "info")

    except Exception as e:
        st.error(f"Erro: {e}")
