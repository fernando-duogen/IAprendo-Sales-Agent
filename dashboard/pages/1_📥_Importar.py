"""Pagina 9 - Importar Escolas: filtros visuais sobre o CSV do MEC e importacao seletiva.
Redesigned com Material Design theme — filtros inline, metric cards, progress visual."""
import streamlit as st
import pandas as pd
import sys, os, subprocess
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, metric_card, section_header,
    alert_banner, breadcrumb, COLORS,
)
from config.settings import settings

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

# --- Header ---
breadcrumb(["IAprendo", "Importar Escolas"])
st.markdown("# Importar Escolas")
st.caption("Base mesclada Censo 2025 + Catalogo INEP — 185k escolas ativas com dados ricos.")

# --- Configuracoes ---
CSV_PATH = ROOT / settings.CSV_PATH

PORTE_PT = {
    "Ate 50 matriculas": "Ate 50 alunos",
    "51 a 200 matriculas": "51 a 200 alunos",
    "201 a 500 matriculas": "201 a 500 alunos",
    "501 a 1000 matriculas": "501 a 1000 alunos",
    "Mais de 1000 matriculas": "Mais de 1000 alunos",
    # Fallbacks para formato antigo do catalogo
    "Ate 50 matriculas de escolarizacao": "Ate 50 alunos",
    "Entre 51 e 200 matriculas de escolarizacao": "51 a 200 alunos",
    "Entre 201 e 500 matriculas de escolarizacao": "201 a 500 alunos",
    "Entre 501 e 1000 matriculas de escolarizacao": "501 a 1000 alunos",
    "Mais de 1000 matriculas de escolarizacao": "Mais de 1000 alunos",
}


@st.cache_data(show_spinner="Carregando base mesclada (185k escolas)...")
def load_csv():
    if not CSV_PATH.exists():
        return None
    df = pd.read_csv(str(CSV_PATH), encoding=settings.CSV_ENCODING, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    # Mapear colunas da base mesclada (Censo 2025 + Catalogo) para nomes internos
    rename_map = {
        "NOME_ESCOLA": "escola",
        "UF": "uf",
        "MUNICIPIO": "municipio",
        "DEPENDENCIA": "dep_adm",
        "PORTE_ESCOLA": "porte",
        "PERFIL_ENSINO": "niveis",
        "FONTE_DADOS": "fonte_dados",
    }
    df = df.rename(columns=rename_map)
    # Garantir colunas obrigatorias
    for col in ["escola", "uf", "municipio", "dep_adm", "porte", "niveis", "fonte_dados"]:
        if col not in df.columns:
            df[col] = ""
    return df


# --- Carrega CSV ---
df_raw = load_csv()
if df_raw is None:
    alert_banner(
        f"CSV nao encontrado em {settings.CSV_PATH}. "
        "Rode: venv/Scripts/python.exe database/migrations/merge_catalogo_inep.py",
        "error",
    )
    st.stop()

# --- Base mesclada ja vem so com escolas ativas (Censo 2025 so tem ativas,
#     Catalogo so incluimos as ativas no merge). Nao precisa filtro extra. ---
df_ativo = df_raw.copy()
total_ativos = len(df_ativo)

# =============================================================================
# FILTROS — inline (NOT sidebar), inside a filter-bar card
# =============================================================================
section_header("Filtros", "filter_list")

st.markdown('<div class="filter-bar">', unsafe_allow_html=True)
fc1, fc2, fc3 = st.columns(3)

with fc1:
    all_ufs = sorted(df_ativo["uf"].dropna().unique().tolist())
    sel_ufs = st.multiselect("Estado(s) (UF):", all_ufs, default=[])

with fc2:
    if sel_ufs:
        df_for_city = df_ativo[df_ativo["uf"].isin(sel_ufs)]
    else:
        df_for_city = df_ativo
    all_cities = sorted(df_for_city["municipio"].dropna().unique().tolist())
    sel_cities = st.multiselect("Cidade(s):", all_cities, default=[])

with fc3:
    all_dep = sorted(df_ativo["dep_adm"].dropna().unique().tolist())
    sel_dep = st.multiselect("Tipo de escola:", all_dep, default=[])

fc4, fc5 = st.columns(2)
with fc4:
    all_porte_raw = df_ativo["porte"].dropna().unique().tolist()
    porte_options = [
        (PORTE_PT.get(p.strip(), p.strip()), p.strip())
        for p in all_porte_raw
        if "Escola sem" not in p
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
    sel_porte_labels = st.multiselect("Porte da escola:", porte_labels, default=[])
    sel_porte_raw = [porte_raw_vals[porte_labels.index(lbl)] for lbl in sel_porte_labels]

with fc5:
    inc_fundamental = st.checkbox("Ensino Fundamental Anos Finais", value=True)
    inc_medio = st.checkbox("Ensino Medio", value=True)

st.markdown('</div>', unsafe_allow_html=True)

# --- Aplica filtros ---
df_filtered = df_ativo.copy()
if sel_ufs:
    df_filtered = df_filtered[df_filtered["uf"].isin(sel_ufs)]
if sel_cities:
    df_filtered = df_filtered[df_filtered["municipio"].isin(sel_cities)]
if sel_dep:
    df_filtered = df_filtered[df_filtered["dep_adm"].isin(sel_dep)]
if sel_porte_raw:
    df_filtered = df_filtered[df_filtered["porte"].str.strip().isin(sel_porte_raw)]
nivel_mask = pd.Series([False] * len(df_filtered), index=df_filtered.index)
if inc_fundamental:
    nivel_mask = nivel_mask | df_filtered["niveis"].str.contains("Fundamental", na=False)
if inc_medio:
    nivel_mask = nivel_mask | df_filtered["niveis"].str.contains("M.dio", na=False)
if inc_fundamental or inc_medio:
    df_filtered = df_filtered[nivel_mask]

# --- Metricas ao vivo ---
n_filtered = len(df_filtered)

# Busca quantas ja estao no banco
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
    metric_card(
        "Total no CSV", f"{total_ativos:,}".replace(",", "."),
        icon="storage", color=COLORS["on_surface_secondary"],
    )
with mc2:
    metric_card(
        "Com filtros atuais", f"{n_filtered:,}".replace(",", "."),
        icon="filter_alt", color=COLORS["primary"],
        delta=f"{n_filtered - total_ativos:+,}".replace(",", "."),
    )
with mc3:
    metric_card(
        "Ja no banco", f"{n_banco:,}".replace(",", "."),
        icon="cloud_done", color=COLORS["secondary"],
    )
with mc4:
    metric_card(
        "Novas p/ importar", f"{max(0, n_filtered - n_banco):,}".replace(",", "."),
        icon="add_circle", color=COLORS["success"],
    )

# --- Indicador visual ---
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
        f"{n_filtered} escolas -- muito grande para importar de uma vez. Use --sample no terminal.",
        "error",
    )

# =============================================================================
# PREVIEW TABELA
# =============================================================================
st.markdown('<hr class="divider">', unsafe_allow_html=True)
section_header("Preview (primeiras 15 escolas)", "table_chart")

if n_filtered > 0:
    preview_cols = [c for c in ["escola", "municipio", "uf", "dep_adm", "porte"] if c in df_filtered.columns]
    preview = df_filtered[preview_cols].head(15).copy()
    preview.columns = ["Escola", "Cidade", "UF", "Tipo", "Porte"][: len(preview_cols)]
    if "Porte" in preview.columns:
        preview["Porte"] = preview["Porte"].str.strip().map(PORTE_PT).fillna(preview["Porte"])
    # Sinalizacao de contagem (1.1 Quick Win)
    from dashboard._table_count import render_count
    render_count(
        total=len(df) if "df" in dir() else n_filtered,
        filtered=n_filtered,
        label_singular="escola elegivel",
        label_plural="escolas elegiveis",
    )
    st.caption(f"Mostrando primeiras 15 — total importavel: {n_filtered:,}")
    st.dataframe(preview, use_container_width=True, hide_index=True)
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
    # Resumo dos filtros selecionados — styled card
    resumo = []
    if sel_ufs:
        ufs_str = ", ".join(sel_ufs[:5]) + (" e mais..." if len(sel_ufs) > 5 else "")
        resumo.append(f"<strong>Estado(s):</strong> {ufs_str}")
    else:
        resumo.append("<strong>Estado(s):</strong> Todos")
    if sel_cities:
        cidades_str = ", ".join(sel_cities[:5]) + (" e mais..." if len(sel_cities) > 5 else "")
        resumo.append(f"<strong>Cidade(s):</strong> {cidades_str}")
    else:
        resumo.append("<strong>Cidade(s):</strong> Todas")
    if sel_dep:
        resumo.append(f"<strong>Tipo:</strong> {', '.join(sel_dep)}")
    else:
        resumo.append("<strong>Tipo:</strong> Todos")
    if sel_porte_labels:
        resumo.append(f"<strong>Porte:</strong> {', '.join(sel_porte_labels)}")
    else:
        resumo.append("<strong>Porte:</strong> Todos")
    niveis_sel = []
    if inc_fundamental:
        niveis_sel.append("Fund. Anos Finais")
    if inc_medio:
        niveis_sel.append("Ensino Medio")
    resumo.append(
        f"<strong>Niveis:</strong> {', '.join(niveis_sel) if niveis_sel else 'Nenhum'}"
    )

    st.markdown(
        '<div class="data-card">'
        '<div style="font-size:14px;font-weight:600;margin-bottom:8px">Filtros que serao aplicados:</div>'
        + "<br/>".join(f'<span style="font-size:13px">{item}</span>' for item in resumo)
        + "</div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "O script usara esses filtros via variaveis de ambiente temporarias. "
        "O banco de dados nao perdera as escolas existentes (chave INEP unica)."
    )

    imp_col1, imp_col2 = st.columns([1, 3])
    with imp_col1:
        sample_limit = st.number_input(
            "Limite de importacao (0 = sem limite):",
            min_value=0, max_value=50000, value=0, step=100,
        )
    with imp_col2:
        st.caption(
            "Use um limite durante testes (ex: 1, 10, 200). "
            "Para importar tudo, deixe 0. "
            f"Com os filtros atuais ha {n_filtered} escolas.\n\n"
            "ℹ️ **Como funciona o limite**: aplicado APOS os filtros — "
            "se voce marcar 1, vai importar 1 escola que passa nos filtros "
            "(nao 1 escola aleatoria do CSV bruto)."
        )

    if st.button("Confirmar e Importar Agora", type="primary"):
        env_extra = os.environ.copy()
        env_extra["TARGET_STATE"] = ",".join(sel_ufs) if sel_ufs else ""
        env_extra["TARGET_CITY"] = ",".join(sel_cities) if sel_cities else ""
        if sel_dep:
            dep_lower = [d.lower() for d in sel_dep]
            env_extra["TARGET_SCHOOL_TYPES"] = ",".join(dep_lower)
        else:
            env_extra.pop("TARGET_SCHOOL_TYPES", None)

        script_path = str(ROOT / "database" / "migrations" / "import_schools.py")
        python_exe = str(ROOT / "venv" / "Scripts" / "python.exe")
        if not Path(python_exe).exists():
            python_exe = sys.executable

        # Forcar UTF-8 no Python child pra evitar UnicodeEncodeError ao
        # printar emojis (🧪 ⚠️ ❌ etc) com locale Windows cp1252.
        env_extra["PYTHONIOENCODING"] = "utf-8"

        cmd = [python_exe, script_path]
        if sample_limit > 0:
            cmd += ["--sample", str(sample_limit)]

        with st.spinner("Importando escolas (isso pode levar alguns minutos para volumes grandes)..."):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",      # leitura stdout/stderr em UTF-8 (consistente com PYTHONIOENCODING)
                    errors="replace",      # se vier byte invalido, substitui ao inves de raise
                    env=env_extra,
                    timeout=300,
                )
                # Extrair contadores do stdout via regex pra feedback rico
                import re as _re
                _inserted_match = _re.search(r"Inseridas?[:\s]+(\d+)", result.stdout or "", _re.IGNORECASE)
                _duplicates_match = _re.search(r"Duplicatas?[:\s]+(\d+)", result.stdout or "", _re.IGNORECASE)
                _inserted_count = int(_inserted_match.group(1)) if _inserted_match else None
                _duplicates_count = int(_duplicates_match.group(1)) if _duplicates_match else 0

                if result.returncode == 0:
                    # Distinguir 4 cenarios bem-sucedidos:
                    # (a) inseridas > 0 → sucesso verde
                    # (b) 0 inseridas + duplicatas > 0 → info azul (escolas ja existiam)
                    # (c) 0 inseridas, filtros sem match → warning amarelo
                    # (d) 0 inseridas, sem contexto → info azul generico
                    if _inserted_count and _inserted_count > 0:
                        _dup_suffix = (
                            f" ({_duplicates_count} duplicata(s) ignorada(s).)"
                            if _duplicates_count else ""
                        )
                        st.success(
                            f"✅ **Importacao concluida** — {_inserted_count} escola(s) "
                            f"nova(s) inserida(s). Va pra aba **Escolas** pra ver."
                            + _dup_suffix
                        )
                    elif _duplicates_count > 0:
                        st.info(
                            f"ℹ️ **Nada novo a importar** — as {_duplicates_count} "
                            f"escola(s) processada(s) ja existem no banco (duplicatas "
                            f"detectadas pelo codigo INEP). Use filtros diferentes "
                            f"pra trazer escolas novas, ou aumente o limite."
                        )
                    elif "Nenhuma escola passa nos filtros" in (result.stdout or ""):
                        st.warning(
                            "ℹ️ **0 escolas inseridas** — nenhuma escola passa nos "
                            "filtros atuais. Verifique sua selecao de UF, cidade e "
                            "tipo de escola acima."
                        )
                    else:
                        st.info(
                            "ℹ️ Importacao concluida sem inserir escolas. "
                            "Veja stdout abaixo pra detalhes."
                        )
                    with st.expander("📋 Saida completa do script", expanded=False):
                        output_text = result.stdout or "(sem output)"
                        if len(output_text) > 5000:
                            output_text = output_text[-5000:]
                        st.code(output_text, language="text")
                else:
                    st.error(
                        f"❌ **Erro na importacao** (returncode={result.returncode}). "
                        f"Veja stderr e stdout abaixo pra diagnosticar."
                    )
                    err_text = result.stderr or "(stderr vazio)"
                    if len(err_text) > 3000:
                        err_text = err_text[-3000:]
                    st.code(err_text, language="text")
                    if result.stdout:
                        with st.expander("📋 Stdout completo", expanded=False):
                            out_text = result.stdout
                            if len(out_text) > 5000:
                                out_text = out_text[-5000:]
                            st.code(out_text, language="text")
            except subprocess.TimeoutExpired:
                alert_banner(
                    "A importacao excedeu 5 minutos. Use um limite menor para importar em lotes.",
                    "error",
                )
            except Exception as exc:
                st.error("Erro ao executar o script: " + str(exc))

        alert_banner("Atualize a pagina para ver o novo total no banco.", "info")
