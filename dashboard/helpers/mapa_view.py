"""Mapa das escolas filtradas — alternador Tabela/Mapa da pagina Escolas (rodada 5).

Versao enxuta do modo "Escolas importadas" da antiga 4_🗺️_Mapa.py: opera sobre o
DataFrame JA FILTRADO da lista (os filtros valem nos dois modos). Pontos, mapa
de calor e hexagonos 3D + geocodificacao de pendentes.
"""
from typing import Any, Dict, List

import pandas as pd
import pydeck as pdk
import streamlit as st

from dashboard.theme import alert_banner, section_header

# Paletas RGB (mesma linguagem da antiga pagina Mapa)
_ETAPA_COLORS: Dict[str, List[int]] = {
    "Prospectado": [144, 164, 174, 180],
    "Contatado": [66, 165, 245, 200],
    "Em conversa": [255, 167, 38, 210],
    "Reuniao": [171, 71, 188, 210],
    "Proposta": [255, 112, 67, 220],
    "Cliente": [102, 187, 106, 230],
    "Perdido": [120, 120, 120, 120],
}
_PRIO_COLORS: Dict[str, List[int]] = {
    "critica": [211, 47, 47, 230],
    "alta": [245, 124, 0, 220],
    "media": [251, 192, 45, 200],
    "baixa": [100, 181, 246, 180],
}
_DEFAULT_COLOR = [99, 110, 250, 190]


def _color_for(row: pd.Series, modo: str) -> List[int]:
    if modo == "Etapa":
        et = str(row.get("Etapa") or "")
        for k, c in _ETAPA_COLORS.items():
            if k.lower() in et.lower():
                return c
    elif modo == "Prioridade":
        u = str(row.get("Urgencia") or "").lower()
        for k, c in _PRIO_COLORS.items():
            if k in u:
                return c
    return _DEFAULT_COLOR


def render_mapa_escolas(df_f: pd.DataFrame) -> None:
    """Renderiza o mapa das escolas filtradas (substitui a tabela no alternador)."""
    if df_f is None or df_f.empty:
        alert_banner("Nenhuma escola nos filtros atuais.", "info")
        return

    has_coords = (
        "latitude" in df_f.columns and "longitude" in df_f.columns
    )
    df_map = df_f.copy()
    if has_coords:
        df_map = df_map[df_map["latitude"].notna() & df_map["longitude"].notna()]
    else:
        df_map = df_map.iloc[0:0]

    sem_coords = len(df_f) - len(df_map)

    mc1, mc2 = st.columns([2, 2])
    with mc1:
        cor_por = st.radio(
            "Cor por:", ["Etapa", "Prioridade"], horizontal=True,
            key="escolas_mapa_cor",
        )
    with mc2:
        tipo_viz = st.radio(
            "Visualizacao:", ["Pontos", "Mapa de calor", "Hexagonos"],
            horizontal=True, key="escolas_mapa_viz",
            help="Calor e hexagonos sao ponderados por alunos-alvo (Fund AF + Medio).",
        )

    if df_map.empty:
        alert_banner(
            f"Nenhuma das {len(df_f)} escolas filtradas tem coordenadas. "
            "Geocodifique abaixo para ve-las no mapa.", "warning",
        )
    else:
        df_map = df_map.rename(columns={"latitude": "lat", "longitude": "lon"})
        df_map["lat"] = pd.to_numeric(df_map["lat"], errors="coerce")
        df_map["lon"] = pd.to_numeric(df_map["lon"], errors="coerce")
        df_map = df_map[df_map["lat"].notna() & df_map["lon"].notna()]
        _fund = pd.to_numeric(df_map.get("Fund AF", 0), errors="coerce").fillna(0)
        _medio = pd.to_numeric(df_map.get("Medio", 0), errors="coerce").fillna(0)
        df_map["alvo"] = (_fund + _medio).astype(int)
        df_map["radius"] = (df_map["alvo"].clip(lower=20) * 2.2).clip(upper=2200)
        df_map["color"] = df_map.apply(lambda r: _color_for(r, cor_por), axis=1)
        # Tooltip nao aceita NaN
        for c in ("name", "city", "UF", "Etapa", "Urgencia"):
            if c in df_map.columns:
                df_map[c] = df_map[c].fillna("")

        _keep = [c for c in ("lat", "lon", "alvo", "radius", "color",
                             "name", "city", "UF", "Etapa", "Urgencia") if c in df_map.columns]
        df_map = df_map[_keep]

        has_alvo = df_map["alvo"].sum() > 0
        if tipo_viz in ("Mapa de calor", "Hexagonos") and not has_alvo:
            alert_banner("Sem dados de alunos-alvo — voltando para Pontos.", "warning")
            tipo_viz = "Pontos"

        layers = []
        tooltip_html = (
            "<b>{name}</b><br/>{city}/{UF}<br/>"
            "Etapa: {Etapa}<br/>Alunos-alvo: {alvo}"
        )
        if tipo_viz == "Pontos":
            layers.append(pdk.Layer(
                "ScatterplotLayer", data=df_map,
                get_position=["lon", "lat"], get_color="color",
                get_radius="radius", radius_min_pixels=4, radius_max_pixels=40,
                pickable=True, auto_highlight=True,
            ))
        elif tipo_viz == "Mapa de calor":
            layers.append(pdk.Layer(
                "HeatmapLayer", data=df_map,
                get_position=["lon", "lat"], get_weight="alvo",
                radius_pixels=60, opacity=0.8, aggregation="SUM", pickable=False,
            ))
            st.caption(
                f"Calor ponderado por alunos-alvo. Total: "
                f"{int(df_map['alvo'].sum()):,} alunos em {len(df_map)} escolas.".replace(",", ".")
            )
        else:
            layers.append(pdk.Layer(
                "HexagonLayer", data=df_map,
                get_position=["lon", "lat"], get_elevation_weight="alvo",
                elevation_scale=0.5, elevation_range=[0, 3000], radius=800,
                extruded=True, coverage=0.85, opacity=0.7,
                pickable=True, auto_highlight=True,
            ))
            tooltip_html = "<b>Regiao agregada</b><br/>Alunos-alvo (soma): {elevationValue}"
            st.caption("Hexagonos 3D — altura = densidade de alunos-alvo (~800m).")

        # Zoom automatico pela dispersao (mesma heuristica da v1)
        lat_range = df_map["lat"].max() - df_map["lat"].min()
        lon_range = df_map["lon"].max() - df_map["lon"].min()
        max_range = max(lat_range, lon_range, 0.01)
        auto_zoom = (4 if max_range > 30 else 5 if max_range > 10 else
                     7 if max_range > 3 else 9 if max_range > 1 else
                     11 if max_range > 0.1 else 13)
        view_state = pdk.ViewState(
            latitude=df_map["lat"].mean(), longitude=df_map["lon"].mean(),
            zoom=auto_zoom, pitch=40 if tipo_viz == "Hexagonos" else 0, bearing=0,
        )
        tooltip = {
            "html": tooltip_html,
            "style": {
                "background": "#1976D2", "color": "white",
                "font-family": "Inter, Arial, sans-serif", "font-size": "13px",
                "border-radius": "8px", "padding": "8px 12px", "z-index": "10000",
            },
        }
        st.pydeck_chart(pdk.Deck(
            layers=layers, initial_view_state=view_state,
            tooltip=tooltip if tipo_viz != "Mapa de calor" else None,
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        ), key=f"escolas_mapa_deck_{tipo_viz}")
        st.caption(
            f"{len(df_map)} escolas no mapa"
            + (f" · {sem_coords} sem coordenadas (geocodifique abaixo)" if sem_coords else "")
        )

    # ----- Geocodificar pendentes (reusa tools.geocoder) -----
    with st.expander(
        f"Geocodificar escolas sem coordenadas ({sem_coords} nos filtros)",
        icon=":material/my_location:",
    ):
        gc1, gc2 = st.columns([1, 2])
        with gc1:
            gc_limit = st.number_input(
                "Quantas:", min_value=1, max_value=50, value=10, key="escolas_geo_limit",
            )
        with gc2:
            gc_use_ppx = st.checkbox(
                "Usar busca web (IA) como fallback", value=True, key="escolas_geo_ppx",
                help="Nominatim (gratis) + busca web por IA quando nao achar. 1 req/seg.",
            )
        if st.button("Geocodificar agora", type="primary",
                     key="escolas_geo_btn", disabled=(sem_coords == 0)):
            try:
                from database.supabase_client import db as _db_geo
                from tools.geocoder import geocoder
                _ids = df_f[df_f.get("latitude").isna()]["id"].tolist() if "latitude" in df_f.columns else []
                _rows = (
                    _db_geo.client.table("companies")
                    .select("id,name,address,city,state,latitude,longitude")
                    .in_("id", _ids[:200]).execute().data or []
                ) if _ids else []
                batch = [c for c in _rows if not c.get("latitude")][: int(gc_limit)]
                with st.spinner(f"Geocodificando {len(batch)} escolas..."):
                    result = geocoder.process_batch(
                        batch, max_per_run=int(gc_limit),
                        use_perplexity_fallback=gc_use_ppx,
                    )
                msg = f"Concluido: {result['found']} geocodificadas"
                if result.get("fallback_used"):
                    msg += f" ({result['fallback_used']} via busca web)"
                alert_banner(msg, "success")
                _fails = result.get("failed_details", [])
                if _fails:
                    st.dataframe(pd.DataFrame([
                        {"Escola": f.get("name", "?"), "Erro": f.get("error", "?")}
                        for f in _fails
                    ]), use_container_width=True, hide_index=True)
                else:
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao geocodificar: {e}")
