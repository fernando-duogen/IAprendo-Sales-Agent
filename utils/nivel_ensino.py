# -*- coding: utf-8 -*-
"""Regra unica de "esta escola tem Fundamental ANOS FINAIS?".

## O problema que este modulo existe para resolver

"Fundamental" na base do MEC cobre do 1o ao 9o ano. Anos INICIAIS (1o-5o) e
anos FINAIS (6o-9o) sao a mesma palavra no campo de texto. Filtrar por
`education_levels contains "Fundamental"` — que era o que as tres telas faziam —
devolve escola de anos iniciais como se fosse alvo nosso.

Medido no mec_catalog em 04/09/2026:

    marcam "fundamental" no texto ............ 122.275
    tem matricula em anos finais de verdade ... 61.354   (50,2%)
    tem ZERO matricula em anos finais ......... 60.921   (49,8%)  <- lixo

Metade do resultado era ruido. Quem filtrava "Anos Finais" e recebia uma escola
de 1o ao 5o ano concluia, com razao, que o filtro estava quebrado.

## A regra

Excluir apenas o que se SABE que nao tem anos finais:

    matriculas_fund_af > 0                       -> tem (censo confirma)
    matriculas_fund_af IS NULL + texto "fundamental" -> desconhecido, mantem
    matriculas_fund_af = 0                       -> NAO tem, exclui

O ramo do NULL nao e detalhe: 4.739 escolas vem do `catalogo_inep` sem merge do
Censo e nao tem matricula nenhuma preenchida (3.031 delas marcam "fundamental").
Tratar NULL como zero sumiria com elas em silencio — pior que o bug original,
porque some com escola boa em vez de trazer escola ruim.

## Por que Medio nao esta aqui

Medido na mesma data: das 30.614 que marcam "medio" no texto, ZERO tem
matricula_medio = 0. "Medio" nao tem subdivisao no campo, entao o texto e
confiavel e o checkbox de Medio nunca mentiu. Mexer nele seria risco sem ganho.

## Por que um modulo compartilhado

A mesma regra e aplicada em tres lugares com tecnologias diferentes — SQL
(PostgREST, base MEC online), pandas sobre o CSV local, e pandas sobre o CRM.
Tres copias e o caminho garantido para as tres divergirem; foi assim que a
mentira sobreviveu em `dashboard/filters.py` mesmo depois de notada na tela de
importar.
"""
from typing import Any

# ---------------------------------------------------------------------------
# SQL / PostgREST (base MEC online — o backend que roda em producao)
# ---------------------------------------------------------------------------
# Formato do `or_()` do postgrest-py. Validado contra a base real: devolve
# 64.385 = 61.354 (com AF) + 3.031 (desconhecidas que citam fundamental).
PG_FUND_AF = ("matriculas_fund_af.gt.0,"
              "and(matriculas_fund_af.is.null,levels_norm.ilike.%fundamental%)")

# Medio segue pelo texto (ver docstring: o texto e confiavel aqui).
PG_MEDIO = "levels_norm.ilike.%medio%"


# ---------------------------------------------------------------------------
# pandas (CSV local e CRM)
# ---------------------------------------------------------------------------
def mask_fund_af(df: Any, col_af: str, col_niveis: str):
    """Mascara booleana de "tem anos finais" para um DataFrame.

    col_af pode estar ausente ou vir como texto (o CSV mesclado preenche coluna
    faltante com ""), entao a conversao e tolerante: o que nao vira numero cai
    no ramo "desconhecido" e e decidido pelo texto do nivel — nunca descartado
    por ser ilegivel.
    """
    import pandas as pd

    tem_texto = (df[col_niveis].astype(str).str.contains("Fundamental", case=False, na=False)
                 if col_niveis in df.columns else pd.Series(False, index=df.index))
    if col_af not in df.columns:
        return tem_texto  # sem a coluna de matricula, so resta o texto

    af = pd.to_numeric(df[col_af], errors="coerce")
    return (af > 0) | (af.isna() & tem_texto)


def mask_medio(df: Any, col_niveis: str):
    """Mascara de "tem Ensino Medio" — pelo texto, que aqui e confiavel."""
    import pandas as pd

    if col_niveis not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col_niveis].astype(str).str.contains("M.dio", case=False, na=False, regex=True)


# ---------------------------------------------------------------------------
# Rotulo da UI — o checkbox tem que dizer o que faz
# ---------------------------------------------------------------------------
LABEL_FUND_AF = "Fundamental — Anos Finais (6º ao 9º)"
HELP_FUND_AF = (
    "Traz apenas escolas com matrícula registrada no 6º–9º ano. "
    "Escolas só de anos iniciais (1º–5º) ficam de fora, mesmo que a base "
    "diga 'Fundamental'. Escolas sem dado de matrícula no Censo entram pelo "
    "nível declarado."
)
