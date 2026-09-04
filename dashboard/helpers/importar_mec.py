"""importar_mec — miolo da busca/importacao da base MEC (185k escolas).

Extraido da pagina Importar para ser REUSADO pela tab "Buscar no Brasil" do
Prospectar (redesign v2, mockup prospectar.html) — zero mudanca de comportamento.
A pagina 1_📥_Importar.py vira casca que chama esta funcao (compatibilidade).
"""
import streamlit as st

from dashboard.theme import metric_card, section_header, alert_banner, COLORS
from dashboard._mec_source import get_mec_source


_SIT_ICONE = {
    "nova": "✅", "ja_no_crm": "ℹ️", "nao_existe": "❌", "invalido": "⚠️",
}
_SIT_LABEL = {
    "nova": "Pronta para importar", "ja_no_crm": "Ja no CRM",
    "nao_existe": "Nao encontrada", "invalido": "Codigo invalido",
}


def render_colar_ineps() -> None:
    """Importa um lote EXATO de escolas a partir de codigos INEP colados.

    Contrato desta tela — cada ponto veio de uma falha observada:
      - valida ANTES de importar e mostra o destino de cada linha;
      - o botao diz o numero exato que sera importado, e esse numero e o
        tamanho da lista colada — nunca o total do filtro geografico, que e o
        que torna "importar" assustador (milhares num clique);
      - "ja no CRM" e sucesso, nao erro: a escola esta la, que era o objetivo.
    """
    with st.expander("📋 Colar codigos INEP (importar escolas especificas)",
                     expanded=True, icon=":material/content_paste:"):
        st.caption("Um codigo por linha (8 digitos). Vale colar de planilha — "
                   "virgula, ponto-e-virgula e texto em volta sao ignorados.")

        texto = st.text_area(
            "Codigos INEP:", height=120, key="mec_inep_paste",
            placeholder="35106446\n31311723\n42003903",
        )
        linhas = _quebrar_linhas(texto)

        b1, b2 = st.columns([1, 3])
        with b1:
            conferir = st.button(
                f"Conferir {len(linhas)} codigo(s)" if linhas else "Conferir",
                disabled=not linhas, key="mec_inep_check",
                icon=":material/fact_check:", use_container_width=True,
            )
        with b2:
            if linhas:
                st.caption(f"{len(linhas)} linha(s) reconhecida(s) no texto colado.")

        if conferir:
            from database.supabase_client import db as _db
            with st.spinner("Conferindo os codigos na base do MEC..."):
                st.session_state["mec_inep_check_result"] = _db.check_ineps_for_import(linhas)

        resultado = st.session_state.get("mec_inep_check_result")
        if not resultado:
            return

        import pandas as pd
        st.dataframe(
            pd.DataFrame([{
                "": _SIT_ICONE.get(r["situacao"], ""),
                "INEP": r.get("inep") or r.get("entrada"),
                "Escola": r.get("nome") or "—",
                "Cidade/UF": (f"{r.get('cidade')}/{r.get('uf')}"
                              if r.get("cidade") else "—"),
                "Fund. 6º-9º": r.get("mat_fund_af"),
                "Situacao": _SIT_LABEL.get(r["situacao"], r["situacao"]),
            } for r in resultado]),
            use_container_width=True, hide_index=True,
            column_config={
                "": st.column_config.TextColumn(width="small"),
                "Fund. 6º-9º": st.column_config.NumberColumn(
                    "Fund. 6º-9º", help="Matriculas no 6º ao 9º ano (Censo)."),
            },
        )

        novas = [r for r in resultado if r["situacao"] == "nova"]
        ja = [r for r in resultado if r["situacao"] == "ja_no_crm"]
        ruins = [r for r in resultado if r["situacao"] in ("nao_existe", "invalido")]

        if ja:
            st.info(f"ℹ️ {len(ja)} ja estava(m) no CRM — nada a fazer com essa(s).")
        if ruins:
            st.warning(
                "⚠️ " + " · ".join(
                    f"`{r.get('entrada')}`: {r['motivo']}" for r in ruins[:5])
                + (f" (+{len(ruins) - 5})" if len(ruins) > 5 else "")
            )

        if not novas:
            if resultado and not ruins:
                st.success("✅ Todas as escolas coladas ja estao no CRM.")
            return

        if st.button(f"⬇️ Importar {len(novas)} escola(s)", type="primary",
                     key="mec_inep_import", icon=":material/download:"):
            _importar_ineps(novas)


def _quebrar_linhas(texto: str) -> list:
    """Separa o texto colado em entradas, uma por codigo.

    Tolerante de proposito: planilha cola com tab, CSV com virgula, e gente cola
    "35106446 - Mobile SP". Cada pedaco vira UMA entrada e a validacao decide —
    e melhor a tela dizer "isto nao e um INEP" do que o texto sumir calado.
    """
    import re
    if not texto or not texto.strip():
        return []
    pedacos = re.split(r"[\n;,\t]+", texto)
    return [p.strip() for p in pedacos if p.strip()]


def _importar_ineps(novas: list) -> None:
    """Importa as escolas conferidas, uma a uma, com resultado por linha."""
    from database.supabase_client import db as _db

    barra = st.progress(0.0)
    status = st.empty()
    ok, falhou = [], []
    for i, item in enumerate(novas, start=1):
        nome = (item.get("nome") or item["inep"])[:45]
        status.caption(f"Importando {i}/{len(novas)} — {nome}")
        res = _db.import_company_from_catalog(item["inep"], source="dashboard_inep")
        (ok if res.get("ok") else falhou).append({**item, "res": res})
        barra.progress(i / len(novas))
    barra.empty()
    status.empty()

    from dashboard.helpers.school_lookup import invalidate_crm_schools
    invalidate_crm_schools()
    # A conferencia na tela agora esta velha (as importadas viraram "ja_no_crm").
    # Deixar o resultado antigo permitiria clicar "Importar" de novo sobre uma
    # lista ja processada.
    st.session_state.pop("mec_inep_check_result", None)

    if ok:
        st.success(
            f"✅ {len(ok)} escola(s) importada(s): "
            + ", ".join((r.get("nome") or r["inep"])[:32] for r in ok[:4])
            + (f" (+{len(ok) - 4})" if len(ok) > 4 else "")
            + " — agora selecione-as em **Preparar escolas**."
        )
    if falhou:
        st.error(
            f"❌ {len(falhou)} nao importada(s): "
            + " · ".join(f"`{r['inep']}`: {r['res'].get('message', '?')}"
                         for r in falhou[:4])
        )


def render_buscar_brasil(embedded: bool = True) -> None:
    """Filtros MEC + metricas + preview + importacao (igual a pagina Importar)."""
    PORTE_PT = {
        "Ate 50 matriculas": "Ate 50 alunos",
        "51 a 200 matriculas": "51 a 200 alunos",
        "201 a 500 matriculas": "201 a 500 alunos",
        "501 a 1000 matriculas": "501 a 1000 alunos",
        "Mais de 1000 matriculas": "Mais de 1000 alunos",
        "Ate 50 matriculas de escolarizacao": "Ate 50 alunos",
        "Entre 51 e 200 matriculas de escolarizacao": "51 a 200 alunos",
        "Entre 201 e 500 matriculas de escolarizacao": "201 a 500 alunos",
        "Entre 501 e 1000 matriculas de escolarizacao": "501 a 1000 alunos",
        "Mais de 1000 matriculas de escolarizacao": "Mais de 1000 alunos",
    }

    # --- Fonte de dados (CSV local OU catalogo Supabase) ---
    source = get_mec_source()
    if source is None:
        alert_banner(
            "Base MEC indisponivel. Localmente: confirme o CSV em data/raw. No Cloud: "
            "rode database/migrations/add_mec_catalog.sql + scripts/load_mec_catalog.py "
            "(e add_mec_facet_rpcs.sql para a cascata de cidades).",
            "warning",
        )
        # `return` (nao st.stop): este helper roda DENTRO de uma aba, e o
        # st.stop() matava o resto do script — as abas "Preparar escolas" e
        # "Sinais" ficavam VAZIAS quando faltava o catalogo (cenario tipico da
        # VM). O Streamlit renderiza todas as abas no mesmo run.
        return

    total_base = source.total()

    # =============================================================================
    # COLAR INEPs — caminho direto para um lote pequeno e conhecido
    # =============================================================================
    # Vem ANTES dos filtros de proposito. Quem ja sabe QUAIS escolas quer nao
    # deveria ter que descrever essas escolas por UF/cidade/porte e torcer para
    # o recorte geografico conter exatamente elas — foi o que consumiu ~65min de
    # um operador para importar 3 escolas (e terminou em zero importadas).
    render_colar_ineps()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # =============================================================================
    # FILTROS
    # =============================================================================
    section_header("Filtros", "filter_list")
    st.caption("Para descobrir escolas por regiao. Se voce ja tem os codigos, "
               "use **Colar codigos INEP** acima.")

    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)

    # key= em todo filtro cujas OPCOES vem dos dados. Sem key, a identidade do
    # widget e derivada dos parametros — inclusive da lista de opcoes. Como
    # source.ufs()/cities()/deps() sao cacheadas com TTL 600/300, bastava o
    # cache expirar e a lista ser remontada para o filtro virar um widget novo e
    # voltar ao default no meio do trabalho ("escolhi 12 cidades e perdi").
    with fc1:
        sel_ufs = st.multiselect("Estado(s) (UF):", source.ufs(), default=[],
                                 key="mec_flt_uf")

    with fc2:
        city_opts = source.cities(sel_ufs)
        _city_help = None
        if sel_ufs and not city_opts:
            _city_help = ("Cascata de cidades requer a RPC mec_catalog_cities "
                          "(rode add_mec_facet_rpcs.sql no Supabase).")
        sel_cities = st.multiselect("Cidade(s):", city_opts, default=[],
                                    help=_city_help, key="mec_flt_cidade")

    with fc3:
        sel_dep = st.multiselect("Tipo de escola:", source.deps(), default=[],
                                 key="mec_flt_dep")

    fc4, fc5 = st.columns(2)
    with fc4:
        porte_options = [
            (PORTE_PT.get(p, p), p) for p in source.portes_raw()
        ]
        porte_options = sorted(
            porte_options,
            key=lambda x: (
                ["Ate 50", "51 a 200", "201 a 500", "501 a 1000", "Mais"].index(x[0].split()[0])
                if x[0].split()[0] in ["Ate 50", "51 a 200", "201 a 500", "501 a 1000", "Mais"]
                else 99
            ),
        )
        porte_labels = [p[0] for p in porte_options]
        porte_raw_vals = [p[1] for p in porte_options]
        sel_porte_labels = st.multiselect("Porte da escola:", porte_labels, default=[],
                                          key="mec_flt_porte")
        sel_porte_raw = [porte_raw_vals[porte_labels.index(lbl)] for lbl in sel_porte_labels]

    with fc5:
        # O rotulo antigo ("Ensino Fundamental Anos Finais") filtrava por
        # PERFIL_ENSINO contendo "Fundamental" — que e 1o ao 9o. Metade do
        # resultado era escola so de anos iniciais. Rotulo e filtro agora
        # dizem a mesma coisa (utils/nivel_ensino).
        from utils.nivel_ensino import LABEL_FUND_AF, HELP_FUND_AF
        inc_fundamental = st.checkbox(LABEL_FUND_AF, value=True,
                                      key="mec_flt_fund", help=HELP_FUND_AF)
        inc_medio = st.checkbox("Ensino Medio", value=True, key="mec_flt_medio")

    # Busca direta: achar UMA escola conhecida nao pode depender de acertar a
    # cidade dela num dropdown de milhares de itens.
    busca = st.text_input(
        "Buscar por nome ou codigo INEP:", key="mec_flt_q",
        placeholder="ex: Bernoulli   ou   31311723",
        help="Digite parte do nome da escola ou o codigo INEP exato (8 digitos).",
    )

    st.markdown('</div>', unsafe_allow_html=True)

    filters = {
        "ufs": sel_ufs, "cities": sel_cities, "deps": sel_dep,
        "portes": sel_porte_raw, "inc_fund": inc_fundamental, "inc_medio": inc_medio,
        "q": busca,
    }

    # --- Metricas ao vivo ---
    n_filtered = source.count(filters)

    n_banco = 0
    try:
        from database.supabase_client import db
        n_banco = db.client.table("companies").select("id", count="exact").execute().count or 0
    except Exception:
        pass

    # =============================================================================
    # RESULTADO DOS FILTROS — metric cards
    # =============================================================================
    section_header("Resultado dos Filtros", "assessment")

    mc1, mc2, mc3, mc4 = st.columns(4)
    with mc1:
        metric_card("Total na base", f"{total_base:,}".replace(",", "."),
                    icon="storage", color=COLORS["on_surface_secondary"])
    with mc2:
        metric_card("Com filtros atuais", f"{n_filtered:,}".replace(",", "."),
                    icon="filter_alt", color=COLORS["primary"],
                    delta=f"{n_filtered - total_base:+,}".replace(",", "."))
    with mc3:
        metric_card("Ja no banco", f"{n_banco:,}".replace(",", "."),
                    icon="cloud_done", color=COLORS["secondary"])
    with mc4:
        metric_card("Novas p/ importar", f"{max(0, n_filtered - n_banco):,}".replace(",", "."),
                    icon="add_circle", color=COLORS["success"])

    # --- Indicador visual (5 niveis de volume) ---
    st.markdown('<div class="mt-1"></div>', unsafe_allow_html=True)
    if n_filtered == 0:
        alert_banner("Nenhuma escola encontrada com esses filtros. Ajuste os criterios.", "warning")
    elif n_filtered < 50:
        alert_banner(f"{n_filtered} escolas encontradas -- volume baixo, bom para testes.", "info")
    elif n_filtered < 500:
        alert_banner(f"{n_filtered} escolas -- volume ideal para comecar.", "success")
    elif n_filtered < 5000:
        alert_banner(f"{n_filtered} escolas -- volume grande. Considere importar em lotes.", "warning")
    else:
        alert_banner(
            f"{n_filtered} escolas -- muito grande para importar de uma vez. Use o limite abaixo.",
            "error",
        )

    # =============================================================================
    # PREVIEW TABELA
    # =============================================================================
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Preview (primeiras 15 escolas)", "table_chart")

    if n_filtered > 0:
        preview = source.preview(filters, n=15)
        preview = preview.rename(columns={
            "inep": "INEP", "escola": "Escola", "municipio": "Cidade", "uf": "UF",
            "dep_adm": "Tipo", "porte": "Porte",
            "mat_fund_af": "Fund. 6º-9º", "mat_medio": "Medio",
        })
        if "Porte" in preview.columns:
            preview["Porte"] = preview["Porte"].astype(str).str.strip().map(PORTE_PT).fillna(preview["Porte"])
        from dashboard._table_count import render_count
        render_count(
            total=total_base, filtered=n_filtered,
            label_singular="escola elegivel", label_plural="escolas elegiveis",
        )
        st.caption(f"Mostrando primeiras 15 — total importavel: {n_filtered:,}".replace(",", "."))
        st.dataframe(
            preview, use_container_width=True, hide_index=True,
            column_config={
                "INEP": st.column_config.TextColumn(
                    "INEP", help="Copie para o campo 'Colar codigos INEP' acima "
                                 "se quiser importar so algumas."),
                "Fund. 6º-9º": st.column_config.NumberColumn(
                    "Fund. 6º-9º",
                    help="Matriculas no 6º ao 9º ano (Censo). Vazio = escola sem "
                         "dado de matricula na base."),
                "Medio": st.column_config.NumberColumn("Medio"),
            },
        )
    else:
        alert_banner("Ajuste os filtros para ver o preview.", "info")

    # =============================================================================
    # IMPORTACAO
    # =============================================================================
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Importar para o Banco de Dados", "cloud_upload")

    if n_filtered == 0:
        alert_banner("Defina os filtros acima para habilitar a importacao.", "info")
    else:
        # Resumo dos filtros selecionados
        resumo = []
        resumo.append(f"<strong>Estado(s):</strong> {', '.join(sel_ufs[:5]) + (' e mais...' if len(sel_ufs) > 5 else '') if sel_ufs else 'Todos'}")
        resumo.append(f"<strong>Cidade(s):</strong> {', '.join(sel_cities[:5]) + (' e mais...' if len(sel_cities) > 5 else '') if sel_cities else 'Todas'}")
        resumo.append(f"<strong>Tipo:</strong> {', '.join(sel_dep) if sel_dep else 'Todos'}")
        resumo.append(f"<strong>Porte:</strong> {', '.join(sel_porte_labels) if sel_porte_labels else 'Todos'}")
        if busca:
            resumo.append(f"<strong>Busca:</strong> {busca}")
        niveis_sel = []
        if inc_fundamental:
            niveis_sel.append("Fund. 6º ao 9º (com matricula)")
        if inc_medio:
            niveis_sel.append("Ensino Medio")
        resumo.append(f"<strong>Niveis:</strong> {', '.join(niveis_sel) if niveis_sel else 'Nenhum'}")

        st.markdown(
            '<div class="data-card">'
            '<div style="font-size:14px;font-weight:600;margin-bottom:8px">Filtros que serao aplicados:</div>'
            + "<br/>".join(f'<span style="font-size:13px">{item}</span>' for item in resumo)
            + "</div>",
            unsafe_allow_html=True,
        )
        st.caption("A importacao respeita estes filtros. Escolas ja existentes sao "
                   "ignoradas (chave INEP unica).")

        imp_col1, imp_col2 = st.columns([1, 3])
        with imp_col1:
            sample_limit = st.number_input(
                "Limite de importacao (0 = sem limite):",
                min_value=0, max_value=50000, value=0, step=100,
            )
        with imp_col2:
            st.caption(
                "Use um limite durante testes (ex: 1, 10, 200). Para importar tudo, "
                f"deixe 0. Com os filtros atuais ha {n_filtered:,} escolas.\n\n".replace(",", ".")
                + "ℹ️ O limite e aplicado APOS os filtros."
            )

        if st.button("Confirmar e Importar Agora", type="primary"):
            with st.spinner("Importando escolas (pode levar alguns minutos para volumes grandes)..."):
                result = source.import_filtered(filters, limit=int(sample_limit))
            # Sem isto, a escola recem importada nao aparecia no buscador da
            # pagina Escolas por ate 5 min (get_crm_schools, TTL 300, que nada
            # invalidava) — e o usuario concluia que a importacao falhou.
            from dashboard.helpers.school_lookup import invalidate_crm_schools
            invalidate_crm_schools()

            if not result.get("ok"):
                st.error("❌ **Erro na importacao**. Veja o detalhe abaixo.")
                _err = result.get("error") or result.get("stderr") or "(sem detalhe)"
                st.code(str(_err)[-3000:], language="text")
                if result.get("log"):
                    with st.expander("📋 Stdout completo", expanded=False):
                        st.code(result["log"][-5000:], language="text")
            else:
                ins = result.get("inseridas")
                dup = result.get("duplicatas") or 0
                if result.get("no_match"):
                    st.warning(
                        "ℹ️ **0 escolas inseridas** — nenhuma escola passa nos filtros atuais. "
                        "Verifique sua selecao de UF, cidade e tipo."
                    )
                elif ins and ins > 0:
                    _suffix = f" ({dup} duplicata(s) ignorada(s).)" if dup else ""
                    st.success(
                        f"✅ **Importacao concluida** — {ins} escola(s) nova(s) inserida(s). "
                        f"Va pra aba **Escolas** pra ver." + _suffix
                    )
                elif dup > 0:
                    st.info(
                        f"ℹ️ **Nada novo a importar** — as {dup} escola(s) processada(s) ja "
                        f"existem no banco (duplicatas detectadas pelo codigo INEP). Use "
                        f"filtros diferentes ou aumente o limite."
                    )
                else:
                    st.info("ℹ️ Importacao concluida sem inserir escolas.")
                if result.get("capped"):
                    alert_banner(
                        "Importado o teto de 5.000 por vez (limite=0). Rode de novo ou "
                        "refine os filtros para importar o restante.",
                        "info",
                    )
                if result.get("log"):
                    with st.expander("📋 Saida completa do script", expanded=False):
                        st.code(result["log"][-5000:], language="text")

            alert_banner("Atualize a pagina para ver o novo total no banco.", "info")

