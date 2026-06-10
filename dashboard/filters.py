"""filters.py — Conjunto PADRAO de filtros de escola + export (redesign v2 F1).

Blueprint §3.1: TODA lista de escolas usa o MESMO conjunto de filtros, vindo
deste componente (fim da reimplementacao por pagina — raiz dos bugs da v1).
Blueprint §3.3: o export e 1-clique em toda lista e respeita o que esta
filtrado/visivel.

Uso (paginas F2+):
    from dashboard.filters import school_filters, apply_school_filters, export_button
    flt = school_filters(df, key="escolas")        # renderiza e retorna selecoes
    df_f = apply_school_filters(df, flt)           # aplica em memoria
    export_button(df_f, prefix="escolas")          # XLSX do que esta na tela
"""
from typing import Any, Dict, List

import pandas as pd
import streamlit as st


def _opts(df: pd.DataFrame, col: str) -> List[str]:
    if col not in df.columns:
        return []
    return sorted([v for v in df[col].dropna().unique().tolist() if v])


def school_filters(df: pd.DataFrame, key: str = "flt",
                   show_crm_fields: bool = True) -> Dict[str, Any]:
    """Renderiza o conjunto padrao (UF, Cidade cascata, Tipo, Niveis, Faixa de
    alunos, Etapa/Prioridade/Dono, Completude) e retorna as selecoes.

    df precisa das colunas canonicas: state/city/admin_dependency e (CRM)
    Etapa/Prioridade/owner_username + matriculas. Colunas ausentes = filtro oculto.
    """
    f: Dict[str, Any] = {}
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        f["ufs"] = st.multiselect("UF", _opts(df, "state"), key=f"{key}_uf",
                                  placeholder="Todas")
    with c2:
        pool = df[df["state"].isin(f["ufs"])] if f.get("ufs") and "state" in df.columns else df
        f["cities"] = st.multiselect("Cidade", _opts(pool, "city"),
                                     key=f"{key}_cid", placeholder="Todas")
    with c3:
        f["deps"] = st.multiselect("Tipo", _opts(df, "admin_dependency"),
                                   key=f"{key}_dep", placeholder="Todos")
    with c4:
        if show_crm_fields:
            f["owners"] = st.multiselect("Dono", _opts(df, "owner_username"),
                                         key=f"{key}_own", placeholder="Todos")

    c5, c6, c7 = st.columns([1.2, 1.6, 2])
    with c5:
        f["inc_fund"] = st.checkbox("Fund. anos finais", value=True, key=f"{key}_fund")
        f["inc_medio"] = st.checkbox("Ensino Medio", value=True, key=f"{key}_med")
    with c6:
        lo, hi = st.columns(2)
        f["alunos_min"] = lo.number_input("Alunos: de", 0, 100000, 0, step=50,
                                          key=f"{key}_amin")
        f["alunos_max"] = hi.number_input("ate", 0, 100000, 0, step=50,
                                          key=f"{key}_amax",
                                          help="0 = sem limite superior")
    with c7:
        if show_crm_fields:
            comp1, comp2 = st.columns(2)
            f["contatos"] = comp1.selectbox("Contatos", ["Todos", "Com", "Sem"],
                                            key=f"{key}_ct")
            f["email"] = comp2.selectbox("E-mail", ["Todos", "Com", "Sem"],
                                         key=f"{key}_em")
    return f


def apply_school_filters(df: pd.DataFrame, f: Dict[str, Any]) -> pd.DataFrame:
    """Aplica as selecoes em memoria (mesma fonte das opcoes -> sem mismatch)."""
    out = df
    if f.get("ufs") and "state" in out.columns:
        out = out[out["state"].isin(f["ufs"])]
    if f.get("cities") and "city" in out.columns:
        out = out[out["city"].isin(f["cities"])]
    if f.get("deps") and "admin_dependency" in out.columns:
        out = out[out["admin_dependency"].isin(f["deps"])]
    if f.get("owners") and "owner_username" in out.columns:
        out = out[out["owner_username"].isin(f["owners"])]
    # niveis de ensino
    if "education_levels" in out.columns and (f.get("inc_fund") or f.get("inc_medio")):
        mask = pd.Series(False, index=out.index)
        if f.get("inc_fund"):
            mask |= out["education_levels"].str.contains("Fundamental", na=False)
        if f.get("inc_medio"):
            mask |= out["education_levels"].str.contains("M.dio", na=False, regex=True)
        out = out[mask]
    # faixa de alunos (alvo = fund_af + medio)
    if "matriculas_fund_af" in out.columns:
        alvo = (out["matriculas_fund_af"].fillna(0) +
                out.get("matriculas_medio", pd.Series(0, index=out.index)).fillna(0))
        if f.get("alunos_min"):
            out = out[alvo >= int(f["alunos_min"])]
        if f.get("alunos_max"):
            out = out[alvo <= int(f["alunos_max"])]
    # completude
    if f.get("contatos") in ("Com", "Sem") and "n_contatos" in out.columns:
        out = out[out["n_contatos"] > 0] if f["contatos"] == "Com" else out[out["n_contatos"] == 0]
    if f.get("email") in ("Com", "Sem") and "tem_email" in out.columns:
        out = out[out["tem_email"]] if f["email"] == "Com" else out[~out["tem_email"]]
    return out


def export_button(df: pd.DataFrame, prefix: str = "escolas",
                  label: str = "📥 Exportar (XLSX)") -> None:
    """Botao de export 1-clique do que esta FILTRADO/visivel (blueprint §3.3)."""
    if df is None or df.empty:
        return
    import io
    buf = io.BytesIO()
    try:
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=prefix[:30])
        from datetime import datetime
        fname = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        st.download_button(label, data=buf.getvalue(), file_name=fname,
                           mime="application/vnd.openxmlformats-officedocument"
                                ".spreadsheetml.sheet",
                           help="Exporta exatamente o que esta filtrado na tela")
    except Exception as e:  # openpyxl ausente etc.
        st.caption(f"Export indisponivel: {str(e)[:80]}")
