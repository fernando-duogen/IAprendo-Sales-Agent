"""Renderer dos blocos ricos do chat IAlex (operador v1, F1).

Mapeia os blocos derivados em agent/render_blocks.py para os componentes
visuais JA existentes do dashboard (theme.py + st nativo). Contrato:

  render_block(block, key=...)  — renderiza UM bloco; NUNCA levanta excecao
                                  (fallback silencioso: nada quebra o chat).

Tipos suportados: school_list, download, chart_ref, report_link,
approval_list, email_preview, metric_summary, suggestion (F3).
Tipos desconhecidos caem num expander JSON (transparencia > sumir).
"""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dashboard.theme import COLORS, alert_banner  # noqa: F401 (COLORS p/ futuros)

# Ordem preferida de colunas nas listas de escolas (mostra o que vende).
_PREFERRED_COLS = [
    "name", "escola", "nome", "school_name",
    "city", "cidade", "municipio", "state", "uf",
    "status", "commercial_stage", "urgency_tier", "prioridade",
    "qualification_score", "fit_score", "score",
    "total_matriculas", "matriculas",
    "enem_media_geral", "media_geral", "media", "nota",
    "gap_vs_peer", "enem_gap_vs_peer_2025", "delta", "evolucao",
    "distancia_km", "admin_dependency", "dependencia",
    "phone", "email",
]
_MAX_COLS = 8


def render_blocks(blocks: List[Dict[str, Any]], key: str = "") -> None:
    """Renderiza uma lista de blocos (conveniencia)."""
    if not blocks:
        return
    for i, block in enumerate(blocks):
        render_block(block, key=f"{key}_{i}")


def render_block(block: Dict[str, Any], key: str = "") -> None:
    """Renderiza um bloco. Nunca levanta — erro vira caption discreta."""
    try:
        _render_inner(block, key)
    except Exception as e:  # noqa: BLE001 — chat jamais pode quebrar
        st.caption(f"⚠️ (bloco nao pode ser exibido: {str(e)[:80]})")


def _render_inner(block: Dict[str, Any], key: str) -> None:
    if not isinstance(block, dict):
        return
    btype = block.get("type")

    if btype == "school_list":
        _render_school_list(block, key)
    elif btype == "download":
        _render_download(block, key)
    elif btype == "chart_ref":
        _render_chart_ref(block, key)
    elif btype == "report_link":
        _render_report_link(block, key)
    elif btype == "approval_list":
        _render_approval_list(block, key)
    elif btype == "email_preview":
        _render_email_preview(block, key)
    elif btype == "metric_summary":
        _render_metric_summary(block, key)
    elif btype == "suggestion":
        _render_suggestion(block, key)
    else:
        with st.expander("📦 Dados estruturados", expanded=False):
            st.json(block)


# ---------------------------------------------------------------------------
# school_list — tabela compacta + mapa opcional
# ---------------------------------------------------------------------------
def _render_school_list(block: Dict[str, Any], key: str) -> None:
    rows = block.get("escolas") or []
    if not rows:
        return
    df = pd.DataFrame(rows)

    # Seleciona colunas na ordem preferida (cap _MAX_COLS); ids/urls ficam fora
    cols = [c for c in _PREFERRED_COLS if c in df.columns][:_MAX_COLS]
    if not cols:
        cols = [c for c in df.columns if c not in ("id", "company_id")][:_MAX_COLS]
    df_show = df[cols] if cols else df

    total = block.get("total", len(rows))
    fonte = block.get("fonte")
    cap = f"📋 {len(rows)} de {total} resultado(s)"
    if fonte:
        cap += f" — fonte: {fonte}"
    st.caption(cap)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Mapa opcional (st.map nativo — sem widget keys, seguro em historico)
    lat_col = next((c for c in ("latitude", "lat") if c in df.columns), None)
    lon_col = next((c for c in ("longitude", "lng", "lon") if c in df.columns), None)
    if lat_col and lon_col:
        df_geo = df[[lat_col, lon_col]].dropna()
        if len(df_geo) >= 2:
            with st.expander(f"🗺️ Ver {len(df_geo)} escola(s) no mapa", expanded=False):
                st.map(df_geo.rename(columns={lat_col: "latitude", lon_col: "longitude"}))


# ---------------------------------------------------------------------------
# download / report_link / chart_ref
# ---------------------------------------------------------------------------
def _render_download(block: Dict[str, Any], key: str) -> None:
    url = block.get("url")
    if not url:
        return
    st.link_button(
        f"📥 {block.get('label') or 'Baixar arquivo'}",
        url,
        type="primary",
        help=block.get("filename") or None,
    )
    if block.get("detalhe"):
        st.caption(block["detalhe"])


def _render_report_link(block: Dict[str, Any], key: str) -> None:
    url = block.get("url")
    if not url:
        return
    escola = block.get("escola") or block.get("inep") or "escola"
    st.link_button(f"📄 Abrir One Page Report — {escola}", url, type="primary")


def _render_chart_ref(block: Dict[str, Any], key: str) -> None:
    charts = [c for c in (block.get("charts") or []) if c.get("url")]
    if not charts:
        return
    if block.get("escola"):
        st.caption(f"📊 Graficos de {block['escola']}")
    cols = st.columns(min(len(charts), 3))
    for i, chart in enumerate(charts):
        with cols[i % len(cols)]:
            st.image(chart["url"], caption=chart.get("alt") or "", use_container_width=True)


# ---------------------------------------------------------------------------
# approval_list / email_preview — fila e preview (botoes de acao chegam na F2)
# ---------------------------------------------------------------------------
_STATUS_EMOJI = {"pending": "⏳", "approved": "✅", "rejected": "🚫", "sent": "📤"}


def _render_approval_list(block: Dict[str, Any], key: str) -> None:
    items = block.get("items") or []
    if not items:
        return
    st.caption(f"✉️ Fila de aprovacao — {block.get('total', len(items))} item(ns)")
    df = pd.DataFrame([
        {
            "": _STATUS_EMOJI.get(it.get("status", ""), "•"),
            "Escola": it.get("escola", "?"),
            "Contato": it.get("contato", "?"),
            "Assunto": it.get("assunto") or "—",
            "Canal": it.get("canal") or "email",
            "Status": it.get("status") or "?",
        }
        for it in items
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "💡 Diga: *\"ver email 1\"* para o texto completo, depois *\"aprova\"* "
        "ou *\"rejeita\"* — nada e enviado sem a sua confirmacao."
    )


def _render_email_preview(block: Dict[str, Any], key: str) -> None:
    with st.container(border=True):
        st.markdown(
            f"**✉️ {block.get('assunto') or '(sem assunto)'}**"
        )
        meta_bits = []
        if block.get("escola"):
            meta_bits.append(f"🏫 {block['escola']}")
        if block.get("contato"):
            meta_bits.append(f"👤 {block['contato']}")
        if block.get("email_destino"):
            meta_bits.append(f"📧 {block['email_destino']}")
        if block.get("canal"):
            meta_bits.append(f"📮 {block['canal']}")
        if block.get("status"):
            _emoji = _STATUS_EMOJI.get(block["status"], "")
            meta_bits.append(f"{_emoji} {block['status']}")
        if meta_bits:
            st.caption(" · ".join(meta_bits))
        st.divider()
        # Corpo COMPLETO (gate de aprovacao: mostrar TUDO antes de confirmar).
        corpo = block.get("corpo") or ""
        st.markdown(corpo.replace("\n", "  \n"))
    st.caption(
        "💡 Para agir, diga: *\"aprova\"*, *\"rejeita\"* ou *\"reescreve mais curto\"* "
        "— o envio so acontece com a sua confirmacao explicita."
    )


# ---------------------------------------------------------------------------
# metric_summary — scalars viram st.metric; resto vai pro expander JSON
# ---------------------------------------------------------------------------
_METRIC_TITLES = {
    "estatisticas_gerais": "📊 Estatisticas gerais",
    "relatorio_pipeline": "📈 Pipeline",
    "funil_vendas": "🔻 Funil de vendas",
    "agregar_estatisticas_escolas": "🧮 Agregado das escolas",
    "kpi_periodo": "🎯 KPIs do periodo",
}
_SKIP_KEYS = {"instrucao", "instrucoes", "mensagem", "dica", "dica_tecnica", "aviso"}


def _render_metric_summary(block: Dict[str, Any], key: str) -> None:
    data = block.get("data") or {}
    title = _METRIC_TITLES.get(block.get("tool", ""), "📊 Resumo")
    st.caption(title)

    scalars = [
        (k, v) for k, v in data.items()
        if k not in _SKIP_KEYS
        and isinstance(v, (int, float, str))
        and (not isinstance(v, str) or len(v) <= 40)
    ][:8]
    if scalars:
        cols = st.columns(min(len(scalars), 4))
        for i, (k, v) in enumerate(scalars):
            label = k.replace("_", " ").capitalize()
            with cols[i % len(cols)]:
                st.metric(label, v if not isinstance(v, float) else round(v, 2))

    rest = {k: v for k, v in data.items() if k not in dict(scalars) and k not in _SKIP_KEYS}
    if rest:
        with st.expander("Ver detalhes", expanded=False):
            st.json(rest)


# ---------------------------------------------------------------------------
# suggestion — chips de proximo passo (populado na F3)
# ---------------------------------------------------------------------------
def _render_suggestion(block: Dict[str, Any], key: str) -> None:
    texto = block.get("texto") or block.get("text")
    if texto:
        alert_banner(f"💡 {texto}", "info")
