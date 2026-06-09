"""Pagina 4 - Mapa Interativo: visualiza escolas importadas ou explora o CSV completo do MEC.
Redesigned com Material Design theme — metric cards, styled filters, alert banners."""
import streamlit as st
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header,
    alert_banner, breadcrumb, COLORS,
)

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

# --- Header ---
breadcrumb(["IAprendo", "Mapa de Escolas"])
st.markdown("# Mapa de Escolas")


def _run_perplexity_search(school_name: str, city: str, state: str):
    """Executa busca Perplexity como subprocesso. Retorna lista de contatos."""
    import subprocess, json as _json, os
    # Pre-checagem: playwright instalado? (subprocess usa o mesmo venv)
    try:
        import importlib.util as _ilu
        if _ilu.find_spec("playwright") is None:
            st.error(
                "Playwright nao instalado neste ambiente. No servidor local rode:\n"
                "`venv\\Scripts\\python.exe -m pip install playwright`\n"
                "`venv\\Scripts\\python.exe -m playwright install chromium`"
            )
            return []
    except Exception:
        pass
    python_exe = str(ROOT / "venv" / "Scripts" / "python.exe")
    safe_name = school_name.replace("'", "\\'").replace('"', '\\"')
    safe_city = city.replace("'", "\\'").replace('"', '\\"')
    safe_state = state.replace("'", "\\'").replace('"', '\\"')
    script = (
        "import json, sys, os, logging; "
        "sys.stdout.reconfigure(encoding='utf-8'); "
        "sys.path.insert(0, '.'); "
        "logging.disable(logging.CRITICAL); "
        "os.environ['IAPRENDO_QUIET']='1'; "
        "from tools.perplexity_browser import perplexity_browser; "
        f"r = perplexity_browser.search_school_contacts('{safe_name}', '{safe_city}', '{safe_state}'); "
        "perplexity_browser._close(); "
        "print('PERPLEXITY_JSON_START'); "
        "print(json.dumps(r, ensure_ascii=True)); "
        "print('PERPLEXITY_JSON_END')"
    )
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.run(
            [python_exe, "-c", script],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
            encoding="utf-8", errors="replace", env=env,
        )
        if proc.returncode == 0 and "PERPLEXITY_JSON_START" in proc.stdout:
            json_text = proc.stdout.split("PERPLEXITY_JSON_START")[1].split("PERPLEXITY_JSON_END")[0].strip()
            return _json.loads(json_text)
        else:
            if proc.stderr:
                st.caption(f"Log: {proc.stderr[-200:]}")
            return []
    except subprocess.TimeoutExpired:
        alert_banner("Timeout: busca excedeu 2 minutos.", "warning")
        return []
    except Exception as e:
        st.error(f"Erro: {e}")
        return []


try:
    import pydeck as pdk
    import pandas as pd
except ImportError as e:
    st.error(f"Dependencia nao encontrada: {e}. Instale: pip install pydeck pandas")
    st.stop()

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
STATUS_PT = {
    "raw": "Novo",
    "qualified": "Qualificado",
    "enriched": "Enriquecido",
    "contacted": "Contatado",
    "responded": "Respondeu",
    "converted": "Convertido",
    "rejected": "Descartado",
}

STATUS_COLORS_MAP = {
    "raw": [100, 150, 255, 180],
    "qualified": [255, 200, 0, 200],
    "enriched": [0, 180, 180, 200],
    "contacted": [0, 200, 100, 200],
    "responded": [200, 0, 255, 220],
    "converted": [0, 255, 100, 220],
    "rejected": [150, 150, 150, 120],
}

DEP_ADM_COLORS = {
    "Estadual": [70, 130, 230, 180],
    "Municipal": [50, 190, 100, 180],
    "Privada": [230, 150, 50, 180],
    "Federal": [160, 80, 220, 180],
}

TECH_COLORS = {
    "Alto": [46, 125, 50, 200],     # verde
    "Medio": [245, 124, 0, 200],    # laranja
    "Médio": [245, 124, 0, 200],
    "Baixo": [198, 40, 40, 200],    # vermelho
    "Sem dado": [150, 150, 150, 120],
}

PORTE_PT = {
    "Ate 50 matriculas de escolarizacao": "Ate 50 alunos",
    "Entre 51 e 200 matriculas de escolarizacao": "51 a 200 alunos",
    "Entre 201 e 500 matriculas de escolarizacao": "201 a 500 alunos",
    "Entre 501 e 1000 matriculas de escolarizacao": "501 a 1000 alunos",
    "Mais de 1000 matriculas de escolarizacao": "Mais de 1000 alunos",
}

DEFAULT_COLOR = [150, 150, 150, 150]

# ---------------------------------------------------------------------------
# CSV loader (base mesclada: Censo 2025 + Catalogo INEP)
# ---------------------------------------------------------------------------
from config.settings import settings
CSV_PATH = ROOT / settings.CSV_PATH


@st.cache_data(show_spinner="Carregando base mesclada (185k escolas)...")
def load_csv():
    """Carrega base mesclada com mapeamento de colunas do Censo 2025."""
    if not CSV_PATH.exists():
        return None
    df = pd.read_csv(str(CSV_PATH), encoding=settings.CSV_ENCODING, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    # Mapear colunas da base mesclada para nomes internos
    rename_map = {
        "NOME_ESCOLA": "escola",
        "CODIGO_INEP": "inep",
        "UF": "uf",
        "MUNICIPIO": "municipio",
        "DEPENDENCIA": "dep_adm",
        "PORTE_ESCOLA": "porte",
        "PERFIL_ENSINO": "niveis",
        "LATITUDE": "latitude",
        "LONGITUDE": "longitude",
        "FONTE_DADOS": "fonte_dados",
    }
    df = df.rename(columns=rename_map)
    for col in ["escola", "inep", "uf", "municipio", "dep_adm", "porte", "niveis", "latitude", "longitude", "fonte_dados"]:
        if col not in df.columns:
            df[col] = ""
    return df


# ---------------------------------------------------------------------------
# Seletor de modo
# ---------------------------------------------------------------------------
modo = st.radio(
    "Fonte de dados:",
    ["Escolas Importadas", "Explorar Base Completa (185k)"],
    horizontal=True,
    help="Importadas = escolas ja no banco. Base completa = 180k Censo 2025 + 4.7k Catalogo INEP.",
)

is_csv_mode = "CSV" in modo

st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Variaveis que ambos os modos preenchem
# ---------------------------------------------------------------------------
df_map = None
tooltip_html = ""
legenda_md = ""
metricas = {}

# ===========================================================================
# MODO 1: Escolas Importadas (Supabase)
# ===========================================================================
if not is_csv_mode:
    st.caption("Escolas ja importadas no banco. Tamanho = score de qualificacao.")

    try:
        from database.supabase_client import db
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")
        st.stop()

    # --- Filtros --- styled filter bar
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        status_opts_en = ["raw", "qualified", "enriched", "contacted", "responded"]
        status_opts_pt = [STATUS_PT.get(s, s) for s in status_opts_en]
        status_sel_pt = st.multiselect("Status:", status_opts_pt, default=[])
        status_sel = [k for k, v in STATUS_PT.items() if v in status_sel_pt]
    with col_f2:
        min_score = st.slider("Score minimo:", 0, 100, 0)
    with col_f3:
        only_geocoded = st.checkbox("Apenas com coordenadas", value=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Toggle para colorir por status, nivel tecnologico ou dados ENEM
    colorir_por_db = st.radio(
        "Colorir pontos por:",
        ["Status", "Nivel tecnologico", "Potencial ENEM", "Trajetoria peer", "Prioridade P1-P3"],
        horizontal=True,
        key="mapa_colorir_por_db",
    )

    legenda_map = {
        "Status": "**Legenda:** Azul = Novo | Amarelo = Qualificado | Verde = Contatado | Roxo = Respondeu",
        "Nivel tecnologico": "**Legenda:** Verde = Alto | Laranja = Medio | Vermelho = Baixo | Cinza = Sem dado",
        "Potencial ENEM": "**Legenda:** 🔥 Vermelho = Alto | 🟡 Amarelo = Medio | 🟢 Verde = Baixo | Cinza = Sem amostra confiavel",
        "Trajetoria peer": "**Legenda:** Verde = Subindo forte | Verde claro = Subindo | Cinza = Estavel | Laranja = Caindo | Vermelho = Caindo forte",
        "Prioridade P1-P3": "**Legenda:** 🔥 Vermelho = P1 quente | Laranja = P2 gap | Roxo = P3 defensivo | Cinza = nao priorizado",
    }
    legenda_md = legenda_map.get(colorir_por_db, "")

    # --- Query ---
    try:
        query = db.client.table("companies").select(
            "id,name,city,state,status,qualification_score,address,latitude,longitude,"
            "nivel_tecnologico,matriculas_fund_af,matriculas_medio,inep_code,admin_dependency"
        )
        all_companies = query.execute().data or []
    except Exception as e:
        st.error(f"Erro ao buscar escolas: {e}")
        st.stop()

    # --- Fetch analytics (UI12d — fetch separado, falha silenciosa) ---
    # Batch fetch de school_analytics para todos os INEPs carregados.
    @st.cache_data(ttl=300)
    def _fetch_map_analytics(inep_tuple: tuple) -> dict:
        if not inep_tuple:
            return {}
        try:
            r = db.client.table("school_analytics").select(
                "inep_code,enem_amostra_confiavel,enem_potencial_melhoria,"
                "peer_trajetoria_5y,enem_gap_vs_peer_2024,enem_dependencia,"
                "enem_presentes,peer_delta_media_geral_2022_2024"
            ).in_("inep_code", list(inep_tuple)).execute()
            return {str(row["inep_code"]): row for row in (r.data or [])}
        except Exception:
            return {}

    inep_list = tuple(
        str(c["inep_code"]).strip()
        for c in all_companies
        if c.get("inep_code")
    )
    analytics_map = _fetch_map_analytics(inep_list)

    # Helper local: classifica prioridade P1/P2/P3 usando helper do enem_tools
    try:
        from agent.tools.enem_tools import _classificar_prioridade
    except Exception:
        _classificar_prioridade = lambda row: None  # fallback: tudo sem prioridade

    # Paletas para modos ENEM
    POTENCIAL_COLORS = {
        "Alto": [229, 57, 53],       # vermelho forte
        "Medio": [251, 192, 45],     # amarelo
        "Médio": [251, 192, 45],
        "Baixo": [67, 160, 71],      # verde
    }
    TRAJ_COLORS = {
        "Subindo forte": [46, 125, 50],
        "Subindo": [139, 195, 74],
        "Estavel": [158, 158, 158],
        "Caindo": [255, 152, 0],
        "Caindo forte": [229, 57, 53],
    }
    PRIO_COLORS = {
        "P1": [229, 57, 53],
        "P2": [255, 152, 0],
        "P3": [156, 39, 176],
    }

    if not all_companies:
        alert_banner("Nenhuma escola importada no banco ainda. Use a pagina 'Importar Escolas' primeiro.", "info")
        st.stop()

    # --- Aplica filtros ---
    filtered = all_companies
    if status_sel:
        filtered = [c for c in filtered if c.get("status") in status_sel]
    if min_score > 0:
        filtered = [c for c in filtered if (c.get("qualification_score") or 0) >= min_score]
    if only_geocoded:
        filtered = [c for c in filtered if c.get("latitude") and c.get("longitude")]

    # --- Monta DataFrame ---
    records = []
    for c in filtered:
        lat = c.get("latitude")
        lon = c.get("longitude")
        if not lat or not lon:
            lat = -30.0346 + (hash(c.get("name", "")) % 100) * 0.001
            lon = -51.2177 + (hash(c.get("city", "")) % 100) * 0.001
        score = c.get("qualification_score") or 0
        status = c.get("status", "raw")
        nivel_tech = c.get("nivel_tecnologico") or "Sem dado"

        # Lookup analytics (pode ser None se escola nao tem ENEM)
        sa_row = analytics_map.get(str(c.get("inep_code") or "").strip())
        enem_pot = None
        enem_traj = None
        enem_gap = None
        enem_prio = None
        if sa_row:
            # Regra #1: so citar metricas individuais se amostra_confiavel
            if sa_row.get("enem_amostra_confiavel"):
                enem_pot = sa_row.get("enem_potencial_melhoria")
                enem_gap = sa_row.get("enem_gap_vs_peer_2024")
            enem_traj = sa_row.get("peer_trajetoria_5y")
            # Classificar prioridade usando helper oficial
            row_for_helper = dict(sa_row)
            row_for_helper["admin_dependency"] = c.get("admin_dependency")
            row_for_helper["city"] = c.get("city")
            enem_prio = _classificar_prioridade(row_for_helper)

        # Escolher cor conforme modo
        if colorir_por_db == "Nivel tecnologico":
            cor = TECH_COLORS.get(nivel_tech, DEFAULT_COLOR)
        elif colorir_por_db == "Potencial ENEM":
            cor = POTENCIAL_COLORS.get(enem_pot, DEFAULT_COLOR) if enem_pot else DEFAULT_COLOR
        elif colorir_por_db == "Trajetoria peer":
            cor = TRAJ_COLORS.get(enem_traj, DEFAULT_COLOR) if enem_traj else DEFAULT_COLOR
        elif colorir_por_db == "Prioridade P1-P3":
            cor = PRIO_COLORS.get(enem_prio, DEFAULT_COLOR) if enem_prio else DEFAULT_COLOR
        else:
            cor = STATUS_COLORS_MAP.get(status, DEFAULT_COLOR)

        alvo = int((c.get("matriculas_fund_af") or 0) + (c.get("matriculas_medio") or 0))
        records.append({
            "lat": float(lat),
            "lon": float(lon),
            "name": c.get("name", "?"),
            "status": STATUS_PT.get(status, status),
            "score": score,
            "city": c.get("city", ""),
            "tech": nivel_tech,
            "alvo": alvo,
            "radius": max(50, score * 3),
            "color": cor,
            "potencial": enem_pot or "—",
            "trajetoria": enem_traj or "—",
            "prioridade": enem_prio or "—",
            "gap": f"{float(enem_gap):+.1f}" if enem_gap is not None else "—",
        })

    if not records:
        alert_banner("Nenhuma escola encontrada com os filtros selecionados.", "warning")
        st.stop()

    df_map = pd.DataFrame(records)
    tooltip_html = (
        "<b>{name}</b><br/>"
        "Status: {status}<br/>"
        "Score: {score}<br/>"
        "Cidade: {city}<br/>"
        "Nivel tec: {tech}<br/>"
        "<i>— ENEM —</i><br/>"
        "Potencial: {potencial}<br/>"
        "Trajet. peer: {trajetoria}<br/>"
        "Gap peer: {gap}<br/>"
        "Prioridade: {prioridade}"
    )

    total_banco = len(all_companies)
    com_coords = sum(1 for c in all_companies if c.get("latitude"))
    metricas = {
        "No mapa": (len(records), "place", COLORS["primary"]),
        "Total no banco": (total_banco, "storage", COLORS["secondary"]),
        "Com coordenadas": (com_coords, "my_location", COLORS["success"]),
        "Score medio": (f'{df_map["score"].mean():.0f}' if not df_map.empty else "0", "star", COLORS["accent"]),
    }

# ===========================================================================
# MODO 2: Explorar CSV Completo
# ===========================================================================
else:
    st.caption("Base mesclada: 180k Censo 2025 + 4.7k Catalogo INEP.")

    from dashboard._mec_source import get_mec_source
    source = get_mec_source()
    if source is None:
        alert_banner(
            "Base MEC indisponivel. Localmente: confirme o CSV em data/raw. No Cloud: "
            "rode add_mec_catalog.sql + load_mec_catalog.py (+ add_mec_facet_rpcs.sql "
            "para a cascata de cidades).",
            "error",
        )
        st.stop()

    total_ativo = source.total()
    _MAP_CAP = 20000  # teto de pontos plotados (payload/perf — vale local e online)

    # --- Filtros --- styled filter bar
    st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_ufs = st.multiselect("Estado(s):", source.ufs(), default=[])
    with col2:
        _city_opts = source.cities(sel_ufs)
        _city_help = ("Cascata requer a RPC mec_catalog_cities (rode add_mec_facet_rpcs.sql)."
                      if (sel_ufs and not _city_opts) else None)
        sel_cities = st.multiselect("Cidade(s):", _city_opts, default=[], help=_city_help)
    with col3:
        sel_dep = st.multiselect("Tipo de escola:", source.deps(), default=[])

    col4, col5 = st.columns(2)
    with col4:
        porte_options = sorted(
            [(PORTE_PT.get(p, p), p) for p in source.portes_raw()],
            key=lambda x: x[0],
        )
        porte_labels = [p[0] for p in porte_options]
        porte_raw_vals = [p[1] for p in porte_options]
        sel_porte_labels = st.multiselect("Porte:", porte_labels, default=[])
        sel_porte_raw = [porte_raw_vals[porte_labels.index(lbl)] for lbl in sel_porte_labels]
    with col5:
        inc_fundamental = st.checkbox("Fund. Anos Finais", value=True)
        inc_medio = st.checkbox("Ensino Medio", value=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Toggle para colorir por tipo ou nivel tec
    colorir_por_csv = st.radio(
        "Colorir pontos por:",
        ["Tipo administrativo", "Nivel tecnologico"],
        horizontal=True,
        key="mapa_colorir_por_csv",
    )

    # --- Busca os pontos (CSV local OU catalogo online), aplica filtros ---
    _filters = {
        "ufs": sel_ufs, "cities": sel_cities, "deps": sel_dep,
        "portes": sel_porte_raw, "inc_fund": inc_fundamental, "inc_medio": inc_medio,
    }
    df_filtered = source.points(_filters, limit=_MAP_CAP).copy()
    df_filtered["latitude"] = pd.to_numeric(df_filtered["latitude"], errors="coerce")
    df_filtered["longitude"] = pd.to_numeric(df_filtered["longitude"], errors="coerce")
    df_filtered = df_filtered.dropna(subset=["latitude", "longitude"])

    if df_filtered.empty:
        alert_banner("Nenhuma escola com esses filtros (ou sem coordenadas). Ajuste os criterios.", "warning")
        st.stop()
    if len(df_filtered) >= _MAP_CAP:
        alert_banner(
            f"Mostrando os primeiros {_MAP_CAP:,} pontos. Refine os filtros para ver outros.".replace(",", "."),
            "info",
        )

    # --- Monta DataFrame para o mapa ---
    # Coluna NIVEL_TECNOLOGICO existe apenas no CSV mesclado (load_csv nao
    # renomeia, entao ela mantem o nome original). Usa fallback se nao existir.
    if "nivel_tecnologico" in df_filtered.columns:
        tech_series = df_filtered["nivel_tecnologico"].fillna("Sem dado").replace("", "Sem dado")
    else:
        tech_series = pd.Series(["Sem dado"] * len(df_filtered), index=df_filtered.index)

    if colorir_por_csv == "Nivel tecnologico":
        color_series = tech_series.map(lambda x: TECH_COLORS.get(x, DEFAULT_COLOR))
    else:
        color_series = df_filtered["dep_adm"].fillna("Outro").map(
            lambda x: DEP_ADM_COLORS.get(x, DEFAULT_COLOR)
        )

    # Calcular alvo (Fund AF + Medio) — colunas canonicas do _mec_source
    if "mat_fund_af" in df_filtered.columns and "mat_medio" in df_filtered.columns:
        alvo_series = (
            pd.to_numeric(df_filtered["mat_fund_af"], errors="coerce").fillna(0)
            + pd.to_numeric(df_filtered["mat_medio"], errors="coerce").fillna(0)
        ).astype(int)
    else:
        alvo_series = pd.Series([0] * len(df_filtered), index=df_filtered.index)

    df_map = pd.DataFrame({
        "lat": df_filtered["latitude"].values,
        "lon": df_filtered["longitude"].values,
        "name": df_filtered["escola"].fillna("?").values,
        "city": df_filtered["municipio"].fillna("").values,
        "uf": df_filtered["uf"].fillna("").values,
        "tipo": df_filtered["dep_adm"].fillna("Outro").values,
        "tech": tech_series.values,
        "alvo": alvo_series.values,
        "porte": df_filtered["porte"].fillna("").str.strip().map(
            lambda x: PORTE_PT.get(x, x)
        ).values,
        "radius": 40,
        "color": color_series.values,
    })

    tooltip_html = "<b>{name}</b><br/>Cidade: {city} - {uf}<br/>Tipo: {tipo}<br/>Porte: {porte}<br/>Nivel tec: {tech}<br/>Alvo (Fund AF + Medio): {alvo}"
    if colorir_por_csv == "Nivel tecnologico":
        legenda_md = "**Legenda:** Verde = Alto | Laranja = Medio | Vermelho = Baixo | Cinza = Sem dado"
    else:
        legenda_md = "**Legenda:** Azul = Estadual | Verde = Municipal | Laranja = Privada | Roxo = Federal"

    metricas = {
        "No mapa": (f"{len(df_map):,}".replace(",", "."), "place", COLORS["primary"]),
        "Total em funcionamento": (f"{total_ativo:,}".replace(",", "."), "storage", COLORS["secondary"]),
        "Estados": (len(df_filtered["uf"].unique()), "public", COLORS["accent"]),
        "Cidades": (len(df_filtered["municipio"].unique()), "location_city", COLORS["success"]),
    }

# ===========================================================================
# Renderizacao comum (ambos os modos)
# ===========================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# Metricas — using metric_card
cols_m = st.columns(len(metricas))
for col, (label, (value, icon, color)) in zip(cols_m, metricas.items()):
    with col:
        metric_card(label, value, icon=icon, color=color)

# Legenda
st.markdown(f'<div class="mt-1" style="font-size:13px;color:#757575">{legenda_md}</div>', unsafe_allow_html=True)
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# Toggle de tipo de visualizacao (vale para ambos os modos)
tipo_viz = st.radio(
    "Tipo de visualizacao:",
    ["Pontos", "Mapa de calor", "Hexagonos"],
    horizontal=True,
    key="mapa_tipo_viz",
    help=(
        "Pontos: um marcador por escola (scatter). "
        "Mapa de calor: densidade ponderada por alunos alvo (Fund AF + Medio). "
        "Hexagonos: colunas 3D agregando densidade em regioes."
    ),
)

# Verifica se a coluna alvo existe (pode nao existir em bases antigas)
has_alvo = "alvo" in df_map.columns and df_map["alvo"].sum() > 0

# Se o usuario escolher Heatmap/Hexagon mas nao ha alvo, avisa e volta pra Pontos
if tipo_viz in ("Mapa de calor", "Hexagonos") and not has_alvo:
    alert_banner(
        "Dados de alunos alvo (Fund AF + Medio) nao disponiveis para essas escolas. "
        "Voltando para visualizacao em Pontos.",
        "warning",
    )
    tipo_viz = "Pontos"

# Montar camada(s) condicionalmente
layers = []
if tipo_viz == "Pontos":
    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_map,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="radius",
        radius_min_pixels=2 if is_csv_mode else 4,
        radius_max_pixels=40,
        pickable=True,
        auto_highlight=True,
    )
    layers.append(scatter_layer)

elif tipo_viz == "Mapa de calor":
    heatmap_layer = pdk.Layer(
        "HeatmapLayer",
        data=df_map,
        get_position=["lon", "lat"],
        get_weight="alvo",
        radius_pixels=60,
        opacity=0.8,
        aggregation="SUM",
        pickable=False,
    )
    layers.append(heatmap_layer)
    # Caption explicativa
    st.caption(
        f"Mapa de calor ponderado por alunos alvo. "
        f"Total: {int(df_map['alvo'].sum()):,} alunos em {len(df_map)} escolas.".replace(",", ".")
    )

elif tipo_viz == "Hexagonos":
    # Config original (commit 5ae0cee) — funcionava visualmente.
    # Tentativas de adicionar get_color_weight pra exibir contagem no tooltip
    # quebraram a renderizacao (deck.gl nao mostrava nenhum hexagono), entao
    # voltamos ao minimo: so elevation_weight=alvo. O tooltip mostra apenas
    # a soma de alvos, sem contagem de escolas.
    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=df_map,
        get_position=["lon", "lat"],
        get_elevation_weight="alvo",
        elevation_scale=0.5,
        elevation_range=[0, 3000],
        radius=800,
        extruded=True,
        coverage=0.85,
        opacity=0.7,
        pickable=True,
        auto_highlight=True,
    )
    layers.append(hex_layer)
    # Tooltip so com elevationValue (soma de alvo). Contagem de escolas nao
    # eh exposta via tooltip nativo do PyDeck sem get_color_weight — e isso
    # quebra o rendering, entao abrimos mao.
    tooltip_html = (
        "<b>Regiao agregada</b><br/>"
        "Alunos alvo (soma): {elevationValue}"
    )
    st.caption(
        f"Hexagonos 3D agregando {int(df_map['alvo'].sum()):,} alunos alvo em regioes de ~800m. "
        "Altura e cor = densidade de alvo.".replace(",", ".")
    )

# Centralizar no centroide dos dados
center_lat = df_map["lat"].mean()
center_lon = df_map["lon"].mean()
# Zoom automatico baseado na dispersao dos dados
lat_range = df_map["lat"].max() - df_map["lat"].min()
lon_range = df_map["lon"].max() - df_map["lon"].min()
max_range = max(lat_range, lon_range, 0.01)
if max_range > 30:
    auto_zoom = 4
elif max_range > 10:
    auto_zoom = 5
elif max_range > 3:
    auto_zoom = 7
elif max_range > 1:
    auto_zoom = 9
elif max_range > 0.1:
    auto_zoom = 11
else:
    auto_zoom = 13

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=auto_zoom,
    pitch=40 if tipo_viz == "Hexagonos" else 0,
    bearing=0,
)

tooltip = {
    "html": tooltip_html,
    "style": {
        "background": "#1976D2",
        "color": "white",
        "font-family": "Inter, Arial, sans-serif",
        "font-size": "13px",
        "border-radius": "8px",
        "padding": "8px 12px",
        "z-index": "10000",
    },
}

# Tooltip nao funciona bem em HeatmapLayer
deck_tooltip = tooltip if tipo_viz != "Mapa de calor" else None

deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    tooltip=deck_tooltip,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
)

st.pydeck_chart(deck, key=f"mapa_deck_{tipo_viz}")

# --- Tabela de dados com selecao ---
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Escolas no mapa", "list")

# Filtros da tabela
tc1, tc2 = st.columns([3, 2])
with tc1:
    # Selectbox com escolas do DataFrame ja filtrado (melhor que text_input livre)
    _mapa_name_col = "name" if "name" in df_map.columns else (df_map.columns[0] if len(df_map.columns) > 0 else None)
    if _mapa_name_col and len(df_map) <= 2000:
        _mapa_escola_opts = ["(todas)"] + sorted(df_map[_mapa_name_col].dropna().unique().tolist())
        table_search_sel = st.selectbox(
            "Buscar escola:", _mapa_escola_opts,
            key="mapa_search", label_visibility="collapsed",
        )
        table_search = "" if table_search_sel == "(todas)" else table_search_sel
    else:
        # Fallback: text_input se o DF for muito grande (>2000)
        table_search = st.text_input(
            "Buscar escola:", placeholder="Digite o nome...",
            key="mapa_search_txt", label_visibility="collapsed",
        )
with tc2:
    if is_csv_mode and "city" in df_map.columns:
        city_col = "city"
    elif "city" in df_map.columns:
        city_col = "city"
    else:
        city_col = None
    if city_col:
        all_table_cities = sorted(df_map[city_col].dropna().unique().tolist())
        if len(all_table_cities) > 1:
            table_city = st.selectbox(
                "Cidade:", ["Todas"] + all_table_cities,
                key="mapa_city_filter", label_visibility="collapsed",
            )
        else:
            table_city = "Todas"
    else:
        table_city = "Todas"

# Preparar display dataframe
if is_csv_mode:
    display_df = df_map[["name", "city", "uf", "tipo", "porte"]].copy()
    display_df.columns = ["Escola", "Cidade", "UF", "Tipo", "Porte"]
else:
    display_df = df_map[["name", "status", "score", "city"]].copy()
    display_df.columns = ["Escola", "Status", "Score", "Cidade"]

# Aplicar filtros da tabela
if table_search:
    display_df = display_df[display_df["Escola"].str.contains(table_search, case=False, na=False)]
if table_city != "Todas":
    display_df = display_df[display_df["Cidade"] == table_city]

# Limitar para performance
display_df = display_df.head(200)
st.caption(f"{len(display_df)} escolas listadas" + (" (max 200)" if len(display_df) == 200 else ""))

selected = st.dataframe(
    display_df, use_container_width=True, hide_index=True,
    on_select="rerun", selection_mode="single-row",
    key="mapa_table",
)

# --- Painel de acoes para escola selecionada ---
selected_rows = selected.selection.rows if selected.selection else []
if selected_rows:
    row_idx = selected_rows[0]
    original_idx = display_df.index[row_idx]
    sel_row = df_map.iloc[original_idx]
    sel_name = sel_row.get("name", "?")
    sel_city = sel_row.get("city", "") if "city" in sel_row else sel_row.get("uf", "")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="data-card" style="border-left:4px solid {COLORS["primary"]}">'
        f'<div style="font-size:18px;font-weight:600">{sel_name}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if is_csv_mode:
        sel_uf = sel_row.get("uf", "")
        sel_tipo = sel_row.get("tipo", "")
        sel_porte = sel_row.get("porte", "")
        st.caption(f"{sel_city}/{sel_uf} | {sel_tipo} | {sel_porte}")

        ac1, ac2 = st.columns(2)
        from dashboard._runtime import is_streamlit_cloud as _is_cloud_pp2
        _on_cloud_pp = _is_cloud_pp2()
        with ac1:
            if _on_cloud_pp:
                st.caption(":material/cloud_off: Perplexity desabilitado no Cloud (precisa Chrome local).")
            elif st.button("Buscar contatos no Perplexity", key="mapa_ppx", type="primary"):
                with st.spinner("Buscando no Perplexity (30-60s)..."):
                    found = _run_perplexity_search(sel_name, sel_city, sel_uf)
                if found:
                    st.session_state["mapa_ppx_results"] = found
                    st.session_state["mapa_ppx_school"] = sel_name
                    st.session_state["mapa_ppx_city"] = sel_city
                    st.session_state["mapa_ppx_uf"] = sel_uf
                    st.session_state["mapa_ppx_tipo"] = sel_tipo
                    st.session_state["mapa_ppx_porte"] = sel_porte
                    st.session_state["mapa_ppx_lat"] = float(sel_row.get("lat", 0))
                    st.session_state["mapa_ppx_lon"] = float(sel_row.get("lon", 0))
                    st.session_state["mapa_ppx_msg"] = ("success", f"{len(found)} contatos encontrados para {sel_name}! Veja abaixo.")
                    st.rerun()
                else:
                    st.session_state["mapa_ppx_msg"] = ("warning", f"Nenhum contato encontrado para {sel_name}.")
                    st.rerun()
        with ac2:
            st.caption("A escola sera importada automaticamente ao salvar contatos.")

    else:
        # Modo importadas
        sel_status = sel_row.get("status", "")
        sel_score = sel_row.get("score", 0)
        st.caption(f"{sel_city} | Status: {sel_status} | Score: {sel_score}")

        company_match = db.client.table("companies").select("id").eq("name", sel_name).limit(1).execute().data
        if company_match:
            cid = company_match[0]["id"]
            contacts_count = len(db.get_contacts_by_company(cid))
            queue_count = len(db.get_queue_by_company(cid))
            st.caption(f"Contatos: {contacts_count} | Mensagens na fila: {queue_count}")

            company_detail = db.get_company_detail(cid) or {}
            imp_city = company_detail.get("city", sel_city)
            imp_state = company_detail.get("state", "")

            mc1, mc2 = st.columns(2)
            with mc1:
                if _on_cloud_pp:
                    st.caption(":material/cloud_off: Perplexity desabilitado no Cloud.")
                elif st.button("Buscar contatos no Perplexity", key="mapa_ppx_imported", type="primary"):
                    with st.spinner("Buscando no Perplexity (30-60s)..."):
                        found_contacts = _run_perplexity_search(sel_name, imp_city, imp_state)
                    if found_contacts:
                        from utils.role_classifier import classify_role
                        existing_contacts = db.client.table("contacts").select(
                            "full_name,email"
                        ).eq("company_id", cid).execute().data or []
                        existing_names = {(c.get("full_name") or "").lower() for c in existing_contacts}
                        existing_emails = {c.get("email", "").lower() for c in existing_contacts if c.get("email")}

                        saved = 0
                        skipped = 0
                        errors = 0
                        for ct in found_contacts:
                            if (ct.get("full_name") or "").lower() in existing_names:
                                skipped += 1
                                continue
                            if ct.get("email") and ct["email"].lower() in existing_emails:
                                skipped += 1
                                continue
                            dm_type, priority = classify_role(ct.get("role") or "")
                            ct_data = {
                                "company_id": cid,
                                "full_name": ct["full_name"],
                                "role": ct.get("role", ""),
                                "source": "perplexity",
                                "confidence_score": int(ct.get("confidence_score", 60)),
                                "decision_maker_type": dm_type,
                                "outreach_priority": priority,
                            }
                            email = ct.get("email") or ct.get("_suggested_email")
                            if email:
                                ct_data["email"] = email
                                if ct.get("_suggested_email") and not ct.get("email"):
                                    ct_data["email_verified"] = False
                                    ct_data["notes"] = "Email sugerido por padrao (nao verificado)"
                            if ct.get("phone"):
                                ct_data["phone"] = ct["phone"]
                            if ct.get("phone_whatsapp"):
                                ct_data["phone_whatsapp"] = ct["phone_whatsapp"]
                            if ct.get("_is_general_email"):
                                ct_data["decision_maker_type"] = "administrativo"
                                ct_data["outreach_priority"] = 99
                            try:
                                if db.insert_contact(ct_data):
                                    saved += 1
                                    existing_names.add((ct.get("full_name") or "").lower())
                            except Exception:
                                errors += 1
                        with_email = sum(1 for ct in found_contacts
                                         if ct.get("email") and not ct.get("_is_general_email"))
                        msg = f"{saved} contatos adicionados para {sel_name}!"
                        if skipped:
                            msg += f" ({skipped} ja existiam)"
                        if errors:
                            msg += f" ({errors} erros)"
                        if with_email == 0 and saved > 0:
                            msg += " | Dica: busque novamente para tentar encontrar emails pessoais (cada busca pode trazer dados diferentes)"
                        st.session_state["mapa_ppx_msg"] = ("success", msg)
                        st.rerun()
                    else:
                        st.session_state["mapa_ppx_msg"] = ("warning", f"Nenhum contato encontrado para {sel_name}.")
                        st.rerun()
            with mc2:
                if st.button("Abrir detalhes da escola"):
                    st.session_state.escola_detail_id = cid
                    st.switch_page("pages/2_🏫_Escolas.py")

if is_csv_mode and len(df_map) > 500:
    st.caption(f"Mostrando 500 de {len(df_map):,} escolas. Use filtros para refinar.".replace(",", "."))

# --- Geocodificacao (apenas modo importadas) ---
if not is_csv_mode:
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    section_header("Geocodificar Escolas", "my_location")
    try:
        from database.supabase_client import db as db_geo
        all_for_geo = db_geo.client.table("companies").select(
            "id,name,address,city,state,latitude,longitude"
        ).execute().data or []
        without_coords = [c for c in all_for_geo if not c.get("latitude")]
    except Exception:
        without_coords = []

    alert_banner(
        f"{len(without_coords)} escola(s) sem coordenadas. Geocodifique para ve-las no mapa.",
        "info",
    )

    gc_col1, gc_col2, gc_col3 = st.columns([1, 2, 2])
    with gc_col1:
        gc_limit = st.number_input("Quantas geocodificar:", min_value=1, max_value=50, value=10)
    with gc_col2:
        gc_use_ppx = st.checkbox(
            "Usar Perplexity como fallback",
            value=True,
            help="Quando o Nominatim não encontrar, pergunta o endereço ao Perplexity e tenta de novo. Mais lento mas mais preciso.",
        )
    with gc_col3:
        st.caption("Nominatim (gratuito) + Perplexity (fallback). Limite: 1 req/seg.")

    if st.button("Geocodificar Agora", type="primary", disabled=(len(without_coords) == 0)):
        try:
            from tools.geocoder import geocoder
            batch = without_coords[:gc_limit]
            with st.spinner(f"Geocodificando {len(batch)} escolas..."):
                result = geocoder.process_batch(
                    batch, max_per_run=gc_limit, use_perplexity_fallback=gc_use_ppx
                )
            msg = f'Concluido: {result["found"]} geocodificadas'
            if result.get("fallback_used", 0) > 0:
                msg += f' ({result["fallback_used"]} via Perplexity)'
            if result.get("skipped", 0) > 0:
                msg += f', {result["skipped"]} ja tinham coords'
            alert_banner(msg, "success")

            # Mostrar falhas (se houver) para o usuario saber quais tentar de novo
            failed_details = result.get("failed_details", [])
            if failed_details:
                with st.expander(f"⚠ {len(failed_details)} escola(s) nao geocodificada(s)", expanded=True):
                    import pandas as pd
                    df_fail = pd.DataFrame([
                        {
                            "Escola": f.get("name", "?"),
                            "Erro": f.get("error", "?"),
                            "Endereco sugerido (Perplexity)": f.get("perplexity_address", "") or "",
                        }
                        for f in failed_details
                    ])
                    st.dataframe(df_fail, use_container_width=True, hide_index=True)
                    st.caption(
                        "Dica: se a coluna 'Endereco sugerido' tem algo, o Perplexity achou mas o Nominatim nao "
                        "reconheceu. Edite o endereco manualmente na pagina Escolas e tente novamente."
                    )
            else:
                st.rerun()
        except Exception as e:
            st.error(f"Erro ao geocodificar: {e}")

# ===========================================================================
# Feedback e Resultados Perplexity (independente da selecao da tabela)
# ===========================================================================
if st.session_state.get("mapa_ppx_msg"):
    msg_type, msg_text = st.session_state.pop("mapa_ppx_msg")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    if msg_type == "success":
        alert_banner(msg_text, "success")
    elif msg_type == "warning":
        alert_banner(msg_text, "warning")
    elif msg_type == "error":
        alert_banner(msg_text, "error")

if st.session_state.get("mapa_ppx_results"):
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    ppx_school = st.session_state.get("mapa_ppx_school", "?")
    ppx_found = st.session_state["mapa_ppx_results"]
    section_header(f"Contatos encontrados: {ppx_school}", "people")
    alert_banner(f"{len(ppx_found)} contato(s). Selecione quais importar:", "success")

    ppx_selected = []
    has_suggested = any(ct.get("_suggested_email") for ct in ppx_found)
    if has_suggested:
        alert_banner(
            "Emails sugeridos por padrao detectado (marcados com ?). Verifique antes de importar.",
            "info",
        )

    for i, ct in enumerate(ppx_found):
        is_general = ct.get("_is_general_email", False)
        label = f"{ct.get('full_name', '?')} -- {ct.get('role', '?')}"
        if ct.get("email"):
            label += f" | {ct['email']}"
        elif ct.get("_suggested_email"):
            label += f" | {ct['_suggested_email']} (sugerido)"
        if ct.get("phone"):
            label += f" | {ct['phone']}"
        if is_general:
            label += " [DEPARTAMENTO]"
        if st.checkbox(label, value=not is_general, key=f"mapa_ppx_sel_{i}"):
            ppx_selected.append(ct)

    pc1, pc2 = st.columns(2)
    with pc1:
        if st.button(f"Importar {len(ppx_selected)} contatos", type="primary", disabled=not ppx_selected):
            from database.supabase_client import db as db_ppx
            from utils.role_classifier import classify_role
            ppx_city = st.session_state.get("mapa_ppx_city", "")
            ppx_uf = st.session_state.get("mapa_ppx_uf", "")
            ppx_tipo = st.session_state.get("mapa_ppx_tipo", "")
            ppx_porte = st.session_state.get("mapa_ppx_porte", "")
            ppx_lat = st.session_state.get("mapa_ppx_lat", 0)
            ppx_lon = st.session_state.get("mapa_ppx_lon", 0)

            existing = db_ppx.client.table("companies").select("id").eq("name", ppx_school).limit(1).execute().data
            if existing:
                cid_ppx = existing[0]["id"]
            else:
                new_company = {
                    "name": ppx_school,
                    "city": ppx_city,
                    "state": ppx_uf,
                    "status": "raw",
                    "admin_dependency": ppx_tipo,
                    "school_size": ppx_porte,
                    "latitude": ppx_lat,
                    "longitude": ppx_lon,
                }
                cid_ppx = db_ppx.insert_company(new_company)

            if cid_ppx:
                saved = 0
                for ct in ppx_selected:
                    dm_type, priority = classify_role(ct.get("role", ""))
                    ct_data = {
                        "company_id": cid_ppx,
                        "full_name": ct["full_name"],
                        "role": ct.get("role", ""),
                        "source": "perplexity",
                        "confidence_score": int(ct.get("confidence_score", 60)),
                        "decision_maker_type": dm_type,
                        "outreach_priority": priority,
                    }
                    email = ct.get("email") or ct.get("_suggested_email")
                    if email:
                        ct_data["email"] = email
                        if ct.get("_suggested_email") and not ct.get("email"):
                            ct_data["email_verified"] = False
                            ct_data["notes"] = "Email sugerido por padrao (nao verificado)"
                    if ct.get("phone"):
                        ct_data["phone"] = ct["phone"]
                    if ct.get("_is_general_email"):
                        ct_data["decision_maker_type"] = "administrativo"
                        ct_data["outreach_priority"] = 99
                    try:
                        if db_ppx.insert_contact(ct_data):
                            saved += 1
                    except Exception:
                        pass
                st.session_state.pop("mapa_ppx_results", None)
                st.session_state.pop("mapa_ppx_school", None)
                alert_banner(
                    f"{'Escola importada + ' if not existing else ''}{saved} contatos salvos!",
                    "success",
                )
                st.rerun()
            else:
                st.error("Falha ao importar escola.")
    with pc2:
        if st.button("Descartar resultados", key="mapa_ppx_discard"):
            st.session_state.pop("mapa_ppx_results", None)
            st.session_state.pop("mapa_ppx_school", None)
            st.rerun()
