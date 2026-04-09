"""
Merge Catalogo INEP + Censo 2025.

Gera um CSV unificado (escolas_brasil_merged.csv) combinando:
1. Censo Escolar 2025 (180.540 escolas ativas com 77 colunas ricas)
2. Catalogo INEP (4.739 escolas ativas exclusivas — sem dados ricos mas com
   endereco, telefone, etapas)

Estrategia:
- Parte do Censo 2025 (fonte primaria, dados ricos)
- Adiciona escolas do Catalogo INEP que NAO estao no Censo e estao ATIVAS
- Para escolas do catalogo, parseia o endereco (campo unico) em
  rua+num/bairro/cep para manter compatibilidade com o schema
- Marca cada linha com coluna "FONTE_DADOS": "censo_2025" ou "catalogo_inep"
- Colunas do Censo que nao existem no catalogo (matriculas, equipe, tech,
  etc.) ficam vazias nas linhas do catalogo

Usage:
    python database/migrations/merge_catalogo_inep.py

Output:
    data/raw/escolas_brasil_merged.csv
"""
import sys
import os
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd

BASE_DIR = Path(__file__).parent.parent.parent
CENSO_PATH = BASE_DIR / "data" / "raw" / "escolas_brasil_crm.csv"
CATALOGO_PATH = BASE_DIR / "data" / "raw" / "escolas_brasil.csv"
OUTPUT_PATH = BASE_DIR / "data" / "raw" / "escolas_brasil_merged.csv"


# =============================================================================
# Parser de endereco do Catalogo INEP
# =============================================================================
# Formato tipico:
#   "RUA DOM DIOGO DE SOUZA, 100 CRISTO REDENTOR. 91350-000 Porto Alegre - RS."
#   "AVENIDA FLORIANOPOLIS, 359 AZENHA. 90880-460 Porto Alegre - RS."
#   "RUA JOSE BRAULIO DA FONSECA, 44 ESCOLA. ABERTA DOS MORROS. 91787-895 Porto Alegre - RS."

CEP_REGEX = re.compile(r"(\d{5}-?\d{3})")
UF_REGEX = re.compile(r"\s-\s([A-Z]{2})\.?\s*$")


def parse_endereco(addr: str) -> dict:
    """Parseia endereco concatenado do Catalogo INEP em componentes.

    Formatos suportados:
    - 'RUA X, 100 BAIRRO. CEP Cidade - UF.'  (bairro inline apos numero)
    - 'RUA X, 100 COMPLEMENTO. BAIRRO. CEP Cidade - UF.'  (bairro em secao propria)
    - 'RUA X, S/N BAIRRO. CEP...'
    """
    if not addr or pd.isna(addr):
        return {"rua_num": None, "bairro": None, "cep": None}

    s = str(addr).strip()

    # CEP
    cep_m = CEP_REGEX.search(s)
    cep = None
    if cep_m:
        raw = cep_m.group(1)
        cep = raw if "-" in raw else f"{raw[:5]}-{raw[5:]}"

    # Recortar parte antes do CEP
    if cep_m:
        before = s[: cep_m.start()].rstrip(" .,;")
    else:
        before = s

    # Separar por '.': se tiver mais de 1 parte, a ultima e o bairro
    parts = [p.strip() for p in before.split(".") if p.strip()]

    bairro = None
    rua_num = None
    if len(parts) == 1:
        rua_num = parts[0]
    elif len(parts) >= 2:
        bairro = parts[-1]
        rua_num = ". ".join(parts[:-1])

    # Se nao achou bairro via ponto, tenta extrair de dentro do rua_num:
    # "RUA X, 100 CRISTO REDENTOR" -> rua="RUA X", num="100", bairro="CRISTO REDENTOR"
    if not bairro and rua_num and "," in rua_num:
        rua_part, resto = rua_num.split(",", 1)
        resto = resto.strip()
        # Resto pode ser: "100 CRISTO REDENTOR" ou "S/N VILA NOVA"
        tokens = resto.split()
        # Primeiro token e o numero (digito, S/N, SN, S/INF)
        if tokens:
            primeiro = tokens[0].upper()
            is_numero = (
                primeiro.isdigit()
                or primeiro in ("S/N", "SN", "S/INF", "S/INFO", "SN.")
                or (primeiro[0].isdigit() if primeiro else False)
            )
            if is_numero and len(tokens) > 1:
                numero = primeiro
                possivel_bairro = " ".join(tokens[1:]).strip()
                # Filtra "palavras de complemento" comuns que nao sao bairro
                complemento_words = {"CASA", "RUA", "PREDIO", "ESCOLA", "GINASIO",
                                     "LOT", "LOTEAMENTO", "ANDAR", "CONJUNTO", "CJ",
                                     "SALA", "LOJA", "BLOCO", "BL", "APT", "APTO"}
                palavras = possivel_bairro.split()
                # Se a primeira palavra e complemento, pula ela
                if palavras and palavras[0].upper() in complemento_words and len(palavras) > 1:
                    possivel_bairro = " ".join(palavras[1:]).strip()
                if possivel_bairro and len(possivel_bairro) >= 3:
                    bairro = possivel_bairro
                    rua_num = f"{rua_part.strip()}, {numero}"

    return {"rua_num": rua_num, "bairro": bairro, "cep": cep}


# =============================================================================
# Normalizacao de valores do Catalogo INEP para o formato do Censo 2025
# =============================================================================

def normalizar_dependencia(dep: str) -> str:
    """Catalogo: 'Estadual'/'Municipal'/'Federal'/'Privada' -> Censo: idem."""
    return str(dep).strip() if pd.notna(dep) else ""


def normalizar_categoria_privada(cat: str) -> str:
    """Catalogo: 'Particular'/'Comunitaria'/etc. -> Censo: idem."""
    if pd.isna(cat) or str(cat).strip() in ("Nao Informado", "N\u00e3o Informado", ""):
        return ""
    return str(cat).strip()


def normalizar_localizacao(loc: str) -> str:
    """Catalogo: 'Urbana'/'Rural' -> Censo: idem."""
    return str(loc).strip() if pd.notna(loc) else ""


def normalizar_porte(porte: str) -> str:
    """Catalogo: 'Entre 51 e 200 matriculas de escolarizacao' -> Censo: '51 a 200 matriculas'."""
    if pd.isna(porte):
        return ""
    p = str(porte).strip()
    mapping = {
        "Escola com at\u00e9 50 matr\u00edculas de escolariza\u00e7\u00e3o": "At\u00e9 50 matr\u00edculas",
        "Entre 51 e 200 matr\u00edculas de escolariza\u00e7\u00e3o": "51 a 200 matr\u00edculas",
        "Entre 201 e 500 matr\u00edculas de escolariza\u00e7\u00e3o": "201 a 500 matr\u00edculas",
        "Entre 501 e 1000 matr\u00edculas de escolariza\u00e7\u00e3o": "501 a 1000 matr\u00edculas",
        "Mais de 1000 matr\u00edculas de escolariza\u00e7\u00e3o": "Mais de 1000 matr\u00edculas",
    }
    return mapping.get(p, p)


def normalizar_perfil_ensino(etapas: str) -> str:
    """Catalogo: 'Educacao Infantil, Ensino Fundamental, Ensino Medio' ->
    Censo: 'Infantil + Fundamental + Medio'.
    """
    if pd.isna(etapas):
        return ""
    e = str(etapas)
    componentes = []
    if "Infantil" in e:
        componentes.append("Infantil")
    if "Fundamental" in e:
        componentes.append("Fundamental")
    if "M\u00e9dio" in e or "Medio" in e:
        componentes.append("M\u00e9dio")
    if "EJA" in e or "Jovens e Adultos" in e:
        componentes.append("EJA")
    if "Profissional" in e:
        componentes.append("Profissional")
    return " + ".join(componentes) if componentes else e


def limpar_telefone(tel: str) -> str:
    """Remove espacos, parenteses e hifens para ficar no padrao do Censo."""
    if pd.isna(tel):
        return ""
    t = str(tel).strip()
    # Censo usa formato "(51) 993928946" — manter assim
    return t


# =============================================================================
# Merge
# =============================================================================

def main():
    print("=" * 70)
    print("MERGE Catalogo INEP + Censo 2025")
    print("=" * 70)
    print()

    # 1. Carregar Censo 2025
    print(f"Carregando Censo 2025 ({CENSO_PATH.name})...")
    df_censo = pd.read_csv(
        CENSO_PATH,
        encoding="utf-8-sig",
        low_memory=False,
        dtype={"CODIGO_INEP": str},
    )
    print(f"  {len(df_censo):,} escolas, {len(df_censo.columns)} colunas")

    # 2. Carregar Catalogo INEP
    print(f"\nCarregando Catalogo INEP ({CATALOGO_PATH.name})...")
    df_cat = pd.read_csv(
        CATALOGO_PATH,
        encoding="utf-8-sig",
        sep=",",
        low_memory=False,
        dtype={"C\u00f3digo INEP": str},
    )
    # Renomear colunas com acentos para nomes simples
    df_cat.rename(columns={
        "C\u00f3digo INEP": "INEP",
        "Restri\u00e7\u00e3o de Atendimento": "RESTRICAO",
        "Endere\u00e7o": "ENDERECO_RAW",
        "Munic\u00edpio": "MUNICIPIO",
        "Depend\u00eancia Administrativa": "DEPENDENCIA",
        "Categoria Escola Privada": "CATEGORIA_PRIVADA",
        "Conveniada Poder P\u00fablico": "CONVENIADA",
        "Regulamenta\u00e7\u00e3o pelo Conselho de Educa\u00e7\u00e3o": "REGULAMENTACAO",
        "Porte da Escola": "PORTE_ESCOLA",
        "Etapas e Modalidade de Ensino Oferecidas": "ETAPAS",
        "Outras Ofertas Educacionais": "OUTRAS_OFERTAS",
        "Localiza\u00e7\u00e3o": "LOCALIZACAO",
        "Localidade Diferenciada": "LOC_DIFERENCIADA",
        "Escola": "NOME_ESCOLA",
        "Telefone": "TELEFONE",
        "Latitude": "LATITUDE",
        "Longitude": "LONGITUDE",
        "Categoria Administrativa": "CATEGORIA_ADMIN",
    }, inplace=True)
    print(f"  {len(df_cat):,} escolas totais")

    # 3. Filtrar Catalogo: so ATIVAS e nao duplicadas com Censo
    ativas_mask = df_cat["RESTRICAO"].str.contains(
        "SEM RESTRI", case=False, na=False
    )
    df_cat_ativas = df_cat[ativas_mask].copy()
    print(f"  {len(df_cat_ativas):,} escolas ATIVAS")

    ineps_censo = set(df_censo["CODIGO_INEP"].astype(str))
    df_cat_unique = df_cat_ativas[~df_cat_ativas["INEP"].isin(ineps_censo)].copy()
    print(f"  {len(df_cat_unique):,} ATIVAS exclusivas do catalogo (nao estao no Censo)")

    # 4. Parsear enderecos e construir colunas no schema do Censo
    print(f"\nParseando enderecos do catalogo...")
    parsed_list = df_cat_unique["ENDERECO_RAW"].apply(parse_endereco)
    df_cat_unique["ENDERECO"] = parsed_list.apply(
        lambda p: ", ".join([x for x in [p.get("rua_num")] if x]) or ""
    )
    df_cat_unique["BAIRRO"] = parsed_list.apply(lambda p: p.get("bairro") or "")
    df_cat_unique["CEP"] = parsed_list.apply(lambda p: p.get("cep") or "")
    parse_ok = df_cat_unique["CEP"].str.len().gt(0).sum()
    print(f"  CEP extraido em {parse_ok}/{len(df_cat_unique)} enderecos")

    # 5. Construir DataFrame compativel com schema do Censo
    print(f"\nConstruindo DataFrame mesclado...")
    colunas_censo = list(df_censo.columns)

    # Linhas do Censo: adiciona FONTE_DADOS
    df_censo["FONTE_DADOS"] = "censo_2025"

    # Linhas do Catalogo: cria com NaN e preenche o que tem
    df_cat_new = pd.DataFrame(index=df_cat_unique.index, columns=colunas_censo)
    df_cat_new["CODIGO_INEP"] = df_cat_unique["INEP"].values
    df_cat_new["NOME_ESCOLA"] = df_cat_unique["NOME_ESCOLA"].values
    df_cat_new["ENDERECO"] = df_cat_unique["ENDERECO"].values
    df_cat_new["BAIRRO"] = df_cat_unique["BAIRRO"].values
    df_cat_new["CEP"] = df_cat_unique["CEP"].values
    df_cat_new["MUNICIPIO"] = df_cat_unique["MUNICIPIO"].values
    df_cat_new["UF"] = df_cat_unique["UF"].values
    df_cat_new["TELEFONE"] = df_cat_unique["TELEFONE"].apply(limpar_telefone).values
    df_cat_new["LATITUDE"] = df_cat_unique["LATITUDE"].values
    df_cat_new["LONGITUDE"] = df_cat_unique["LONGITUDE"].values
    df_cat_new["DEPENDENCIA"] = df_cat_unique["DEPENDENCIA"].apply(normalizar_dependencia).values
    df_cat_new["CATEGORIA_PRIVADA"] = df_cat_unique["CATEGORIA_PRIVADA"].apply(normalizar_categoria_privada).values
    df_cat_new["LOCALIZACAO"] = df_cat_unique["LOCALIZACAO"].apply(normalizar_localizacao).values
    df_cat_new["PORTE_ESCOLA"] = df_cat_unique["PORTE_ESCOLA"].apply(normalizar_porte).values
    df_cat_new["PERFIL_ENSINO"] = df_cat_unique["ETAPAS"].apply(normalizar_perfil_ensino).values

    # Regiao aproximada via UF
    regiao_uf = {
        "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
        "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
        "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
        "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
        "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
        "PR": "Sul", "RS": "Sul", "SC": "Sul",
    }
    df_cat_new["REGIAO"] = df_cat_new["UF"].map(regiao_uf).fillna("")

    df_cat_new["FONTE_DADOS"] = "catalogo_inep"

    # 6. Concatenar e salvar
    df_merged = pd.concat([df_censo, df_cat_new], ignore_index=True)
    print(f"\nTotal mesclado: {len(df_merged):,} escolas")
    print(f"  Censo 2025: {(df_merged['FONTE_DADOS'] == 'censo_2025').sum():,}")
    print(f"  Catalogo INEP (exclusivas): {(df_merged['FONTE_DADOS'] == 'catalogo_inep').sum():,}")

    print(f"\nSalvando em {OUTPUT_PATH.name}...")
    df_merged.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"  OK ({size_mb:.1f} MB)")

    # 7. Verificar as 8 escolas problemaes
    print()
    print("=" * 70)
    print("VERIFICACAO DAS 8 ESCOLAS QUE FALTAVAM")
    print("=" * 70)
    missing = [
        ("43105114", "COLEGIO SAO JUDAS TADEU"),
        ("43181155", "EEF CRISTA DA BRASA"),
        ("43173314", "ESC DE ENS FUND PROF ANA MARIA"),
        ("43105033", "COLEGIO LA SALLE DORES"),
        ("43108849", "EEF LA SALLE ESMERALDA"),
        ("43186700", "COLEGIO UNIFICADO RAMIRO"),
        ("43214754", "COLEGIO UNIFICADO - ZONA SUL"),
        ("43107524", "COL METODISTA AMERICANO"),
    ]
    for inep, nome in missing:
        m = df_merged[df_merged["CODIGO_INEP"] == inep]
        if len(m) > 0:
            r = m.iloc[0]
            print(f"  OK [{inep}] {r['NOME_ESCOLA'][:35]:35s} | {r['FONTE_DADOS']}")
        else:
            print(f"  FALTA [{inep}] {nome}")

    print()
    print("Merge concluido com sucesso!")


if __name__ == "__main__":
    main()
