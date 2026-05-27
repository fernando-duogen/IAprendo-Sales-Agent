"""export_utils - Exportacao de escolas selecionadas em XLSX/CSV.

Funcoes pra gerar bytes de XLSX (multi-sheet com escolas + contatos)
ou CSV pra usar com st.download_button.

Usage:
    from utils.export_utils import escolas_to_xlsx_bytes

    xlsx_bytes = escolas_to_xlsx_bytes(company_ids=[id1, id2, id3])
    st.download_button("Exportar XLSX", xlsx_bytes, "escolas.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from database.supabase_client import db
from utils.logger import logger


# Colunas exportadas da tabela companies (todas as relevantes pra venda)
_COMPANY_EXPORT_COLS = [
    "id", "inep_code", "name", "city", "state", "regiao",
    "bairro", "address", "phone", "phone_whatsapp", "website",
    "admin_category", "admin_dependency", "categoria_privada",
    "school_size", "fonte_dados",
    "status", "qualification_score", "qualification_reasoning",
    "urgency_score", "urgency_tier",
    "matriculas_fund_af", "matriculas_medio", "total_matriculas",
    "nivel_tecnologico", "qt_coordenadores", "total_docentes",
    "latitude", "longitude",
    "hubspot_company_id", "hubspot_deal_id",
    "last_contacted_at", "created_at", "updated_at",
]

# Colunas exportadas de contacts
_CONTACT_EXPORT_COLS = [
    "id", "company_id", "full_name", "role", "decision_maker_type",
    "outreach_priority", "email", "phone", "phone_whatsapp",
    "linkedin_url", "source", "confidence_score",
    "notes", "created_at",
]


def _select_existing(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Retorna df so com as colunas que existem (evita KeyError em schemas variados)."""
    existing = [c for c in cols if c in df.columns]
    return df[existing] if existing else df


def fetch_companies_with_contacts(company_ids: List[str]) -> Dict[str, pd.DataFrame]:
    """Busca escolas + contatos relacionados. Retorna dict com 2 DataFrames:
    {"companies": df, "contacts": df}.
    """
    if not company_ids:
        return {"companies": pd.DataFrame(), "contacts": pd.DataFrame()}

    try:
        # Buscar escolas (todas as colunas pra ter dados completos)
        cmp_res = (
            db.client.table("companies")
            .select("*")
            .in_("id", company_ids)
            .execute()
        )
        companies_data = cmp_res.data or []
        df_companies = pd.DataFrame(companies_data)

        # Buscar contatos relacionados
        ct_res = (
            db.client.table("contacts")
            .select("*")
            .in_("company_id", company_ids)
            .execute()
        )
        contacts_data = ct_res.data or []
        df_contacts = pd.DataFrame(contacts_data)

        # Selecionar so colunas relevantes (existing only)
        if not df_companies.empty:
            df_companies = _select_existing(df_companies, _COMPANY_EXPORT_COLS)
        if not df_contacts.empty:
            df_contacts = _select_existing(df_contacts, _CONTACT_EXPORT_COLS)

        return {"companies": df_companies, "contacts": df_contacts}
    except Exception as e:
        logger.error(f"Erro ao buscar escolas+contatos pra export: {e}")
        return {"companies": pd.DataFrame(), "contacts": pd.DataFrame()}


def escolas_to_xlsx_bytes(company_ids: List[str]) -> bytes:
    """Gera bytes de XLSX com 2 abas: 'Escolas' e 'Contatos'.

    Args:
        company_ids: lista de UUIDs de escolas a exportar.

    Returns:
        Bytes do XLSX pronto pra st.download_button.
    """
    data = fetch_companies_with_contacts(company_ids)
    df_companies = data["companies"]
    df_contacts = data["contacts"]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if not df_companies.empty:
            df_companies.to_excel(writer, sheet_name="Escolas", index=False)
        else:
            pd.DataFrame([{"info": "Nenhuma escola encontrada"}]).to_excel(
                writer, sheet_name="Escolas", index=False
            )
        if not df_contacts.empty:
            df_contacts.to_excel(writer, sheet_name="Contatos", index=False)
        else:
            pd.DataFrame([{"info": "Nenhum contato encontrado"}]).to_excel(
                writer, sheet_name="Contatos", index=False
            )

        # Aba de metadados
        meta_df = pd.DataFrame([{
            "campo": "Gerado em",
            "valor": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }, {
            "campo": "Total escolas",
            "valor": len(df_companies),
        }, {
            "campo": "Total contatos",
            "valor": len(df_contacts),
        }, {
            "campo": "Origem",
            "valor": "IAprendo Sales Agent",
        }])
        meta_df.to_excel(writer, sheet_name="Info", index=False)

    return buf.getvalue()


def escolas_to_csv_bytes(company_ids: List[str]) -> bytes:
    """Gera bytes de CSV (so escolas, sem contatos). UTF-8 com BOM pra Excel BR."""
    data = fetch_companies_with_contacts(company_ids)
    df = data["companies"]
    if df.empty:
        return b"info\nNenhuma escola encontrada\n"
    return df.to_csv(index=False).encode("utf-8-sig")


def export_filename(prefix: str = "escolas", ext: str = "xlsx") -> str:
    """Gera nome de arquivo com timestamp. Ex: 'escolas_20260525_143012.xlsx'."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{ext}"
