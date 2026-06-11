"""Negocios — kanban comercial (redesign v2, mockup negocios.html).

Responde: "como estao minhas negociacoes?" — da primeira conversa ao contrato.
Extraido da aba "Pipeline Comercial" do Pipeline v1 (sem mudanca de logica) +
"Mover para ▸" com higiene de pipeline (motivo de perda obrigatorio; valor na
proposta/fechamento) — blueprint v1.3 §4 Negocios.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import (
    apply_theme_no_config, section_header, alert_banner, metric_card,
    breadcrumb, COLORS, kanban_card_clickable,
)

apply_theme_no_config()

from dashboard._auth_gate import require_auth
require_auth()

from database.supabase_client import db
from dashboard.labels import LOSS_REASONS

breadcrumb(["IAprendo", "Negocios"])
st.markdown("# Negocios")
st.caption("Acompanhe cada escola da primeira conversa ao contrato. "
           "Mova de etapa pelo ▸ de cada card — perder exige motivo (higiene do funil).")

COMMERCIAL_STAGES = [
    {"key": "prospectado", "label": "Prospectado", "color": COLORS["primary"], "desc": "Novo lead"},
    {"key": "contatado", "label": "Contatado", "color": COLORS["info"], "desc": "Email/WhatsApp enviado"},
    {"key": "respondeu", "label": "Respondeu", "color": COLORS["secondary"], "desc": "Lead engajado"},
    {"key": "reuniao", "label": "Reuniao", "color": COLORS["warning"], "desc": "Meeting realizada"},
    {"key": "proposta", "label": "Proposta", "color": COLORS["accent"], "desc": "Orcamento enviado"},
    {"key": "cliente", "label": "Cliente", "color": COLORS["success"], "desc": "Deal fechado"},
]
_STAGE_LABELS = {s["key"]: s["label"] for s in COMMERCIAL_STAGES}
_MOVE_TARGETS = list(_STAGE_LABELS) + ["perdido"]


def _mover_popover(comp: dict, current_stage: str, key_prefix: str):
    """Popover 'Mover para ▸' (mockup): muda o commercial_stage com a higiene
    do blueprint v1.3 — Perdida exige motivo padronizado; Proposta pede valor;
    Cliente pede valor fechado. Usa db.set_commercial_stage (status coerente +
    trigger stage_changed grava o evento imutavel das metas)."""
    with st.popover("▸", help="Mover para outra etapa"):
        st.markdown(f"**{(comp.get('name') or '?')[:40]}**")
        _targets = [t for t in _MOVE_TARGETS if t != current_stage]
        _to = st.selectbox(
            "Mover para", _targets,
            format_func=lambda k: "Perdida" if k == "perdido" else _STAGE_LABELS.get(k, k),
            key=f"{key_prefix}_to")
        extra = {}
        ok = True
        if _to == "perdido":
            _cat = st.selectbox("Motivo da perda (obrigatorio)",
                                list(LOSS_REASONS),
                                format_func=lambda k: LOSS_REASONS[k],
                                key=f"{key_prefix}_cat")
            _txt = st.text_input("Detalhe (opcional)", key=f"{key_prefix}_txt")
            extra = {"motivo_perda_categoria": _cat,
                     "motivo_perda_texto": (_txt or "").strip()[:300] or None,
                     "data_fechamento": datetime.now(timezone.utc).isoformat()}
        elif _to == "proposta":
            _val = st.number_input("Valor proposto (R$/mes)", min_value=0.0,
                                   value=float(comp.get("valor_mensal_proposto") or 0),
                                   step=100.0, key=f"{key_prefix}_vp")
            if not _val:
                st.caption("Informe o valor da proposta.")
                ok = False
            extra = {"valor_mensal_proposto": _val,
                     "data_proposta": datetime.now(timezone.utc).isoformat()}
        elif _to == "cliente":
            _val = st.number_input("Valor fechado (R$/mes)", min_value=0.0,
                                   value=float(comp.get("valor_mensal_proposto") or 0),
                                   step=100.0, key=f"{key_prefix}_vf")
            if not _val:
                st.caption("Informe o valor fechado.")
                ok = False
            extra = {"valor_mensal_fechado": _val,
                     "data_fechamento": datetime.now(timezone.utc).isoformat()}
        if st.button("Confirmar", type="primary", key=f"{key_prefix}_go",
                     disabled=not ok):
            extra = {k: v for k, v in extra.items() if v is not None}
            try:
                db.set_commercial_stage(comp["id"], _to, extra=extra)
                st.rerun()
            except Exception as _e:
                st.error(f"Falha ao mover: {str(_e)[:150]}")


try:
    # Carrega companies com stage + valores comerciais (fallback gracioso
    # se a migration 013 nao foi aplicada).
    try:
        comm_companies = db.client.table("companies").select(
            "id,name,city,qualification_score,commercial_stage,valor_mensal_proposto,"
            "valor_mensal_fechado,motivo_perda_texto,motivo_perda_categoria,data_fechamento,"
            "matriculas_fund_af,matriculas_medio,nivel_tecnologico,status,owner_username"
        ).execute().data or []
        _can_move = True
    except Exception as _migration_err:
        if "commercial_stage" in str(_migration_err) or "42703" in str(_migration_err):
            comm_companies = db.client.table("companies").select(
                "id,name,city,qualification_score,matriculas_fund_af,matriculas_medio,"
                "nivel_tecnologico,status"
            ).execute().data or []
            _can_move = False
            alert_banner(
                "Migration 013 nao aplicada — kanban em modo leitura. Rode "
                "<code>APLICAR-013-COMMERCIAL-STAGES.sql</code> no Supabase.",
                "warning",
            )
        else:
            raise

    # Meetings + emails enviados pra inferencia automatica de stage
    _meetings = db.client.table("meetings").select("company_id").execute().data or []
    _meeting_set = {m["company_id"] for m in _meetings if m.get("company_id")}

    _sent_emails = db.client.table("approval_queue").select(
        "company_id,replied_at"
    ).eq("status", "sent").execute().data or []
    _email_map = {}
    for _e in _sent_emails:
        cid = _e.get("company_id")
        if not cid:
            continue
        entry = _email_map.setdefault(cid, {"sent": False, "replied": False})
        entry["sent"] = True
        if _e.get("replied_at"):
            entry["replied"] = True

    from utils.stage_sync import infer_stage as _shared_infer_stage

    def _infer_stage(comp):
        cid = comp["id"]
        return _shared_infer_stage(
            comp,
            has_email=cid in _email_map,
            has_reply=bool(_email_map.get(cid, {}).get("replied")),
            has_meeting=cid in _meeting_set,
        )

    stage_buckets = {s["key"]: [] for s in COMMERCIAL_STAGES}
    perdidos = []
    for _c in comm_companies:
        stage = _infer_stage(_c)
        if stage == "perdido":
            perdidos.append(_c)
        elif stage in stage_buckets:
            stage_buckets[stage].append(_c)

    # KPI row: MRR + Win rate
    mrr_potencial = sum(
        float(c.get("valor_mensal_proposto") or 0) for c in stage_buckets["proposta"])
    mrr_ativo = sum(
        float(c.get("valor_mensal_fechado") or 0) for c in stage_buckets["cliente"])
    total_fechados = len(stage_buckets["cliente"])
    total_perdidos = len(perdidos)
    win_rate = ((total_fechados / (total_fechados + total_perdidos) * 100)
                if (total_fechados + total_perdidos) > 0 else 0)

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        metric_card("MRR Potencial", f"R$ {mrr_potencial:,.0f}".replace(",", "."),
                    icon="pending", color=COLORS["accent"],
                    delta=f"{len(stage_buckets['proposta'])} proposta(s)")
    with mc2:
        metric_card("MRR Ativo", f"R$ {mrr_ativo:,.0f}".replace(",", "."),
                    icon="payments", color=COLORS["success"],
                    delta=f"{total_fechados} cliente(s)")
    with mc3:
        metric_card("Win Rate", f"{win_rate:.0f}%",
                    icon="emoji_events", color=COLORS["primary"],
                    delta=f"{total_fechados}/{total_fechados + total_perdidos} decisoes")

    # Kanban: header + cards por stage
    st.markdown("")
    kanban_header_cols = st.columns(len(COMMERCIAL_STAGES))
    for i, stage in enumerate(COMMERCIAL_STAGES):
        with kanban_header_cols[i]:
            items = stage_buckets[stage["key"]]
            count = len(items)
            _soma = ""
            if stage["key"] == "proposta" and mrr_potencial:
                _soma = f' · R$ {mrr_potencial:,.0f}/mes'.replace(",", ".")
            elif stage["key"] == "cliente" and mrr_ativo:
                _soma = f' · R$ {mrr_ativo:,.0f}/mes'.replace(",", ".")
            st.markdown(
                f'<p style="background:{stage["color"]}12;border-left:4px solid {stage["color"]};'
                f'padding:10px 12px;border-radius:8px;margin-bottom:8px">'
                f'<strong style="font-size:13px">{stage["label"]}</strong>'
                f' <span style="font-size:11px;color:{stage["color"]};font-weight:700">({count}{_soma})</span><br/>'
                f'<span style="font-size:10px;color:#9E9E9E">{stage["desc"]}</span></p>',
                unsafe_allow_html=True,
            )
            if not items:
                st.caption("—")
                continue

            def _card_meta(comp, stage_key=stage["key"]):
                score = int(comp.get("qualification_score") or 0)
                name = ((comp.get("name") or "?")[:28]).rstrip()
                alvo_ = int((comp.get("matriculas_fund_af") or 0) +
                            (comp.get("matriculas_medio") or 0))
                tech = comp.get("nivel_tecnologico") or ""
                sub = ""
                if stage_key == "proposta" and comp.get("valor_mensal_proposto"):
                    sub = f"R$ {float(comp['valor_mensal_proposto']):,.0f}/mes".replace(",", ".")
                elif stage_key == "cliente" and comp.get("valor_mensal_fechado"):
                    sub = f"R$ {float(comp['valor_mensal_fechado']):,.0f}/mes".replace(",", ".")
                return score, name, alvo_, tech, sub

            sorted_items = sorted(items, key=lambda x: x.get("qualification_score") or 0,
                                  reverse=True)

            def _render_card(comp, key_prefix):
                score, name, alvo_, tech, sub = _card_meta(comp)
                c_card, c_move = st.columns([5, 1])
                with c_card:
                    if kanban_card_clickable(
                        name=name, score=score, alvo=alvo_, nivel_tech=tech,
                        color=stage["color"], key=f"{key_prefix}_{comp['id']}",
                        subtitle=sub,
                    ):
                        st.session_state["escola_detail_id"] = comp["id"]
                        st.switch_page("pages/2_🏫_Escolas.py")
                with c_move:
                    if _can_move:
                        _mover_popover(comp, stage["key"], f"mv_{key_prefix}_{comp['id']}")

            for comp in sorted_items[:6]:
                _render_card(comp, f"kb_{stage['key']}")
            if len(sorted_items) > 6:
                with st.expander(f"Ver mais {len(sorted_items) - 6}", expanded=False):
                    for comp in sorted_items[6:]:
                        _render_card(comp, f"kbx_{stage['key']}")

    # Perdidos (colapsado)
    if perdidos:
        with st.expander(f"Leads perdidos ({len(perdidos)})", expanded=False):
            for p in sorted(perdidos, key=lambda x: (x.get("data_fechamento") or ""),
                            reverse=True)[:15]:
                data_str = (p.get("data_fechamento") or "")[:10]
                categoria = p.get("motivo_perda_categoria") or "—"
                categoria = LOSS_REASONS.get(categoria, categoria)
                motivo_txt = (p.get("motivo_perda_texto") or "")[:120]
                st.markdown(
                    f"**{p.get('name', '?')}** — {data_str} · "
                    f"<span style='background:#FFCDD2;color:#B71C1C;padding:2px 8px;"
                    f"border-radius:10px;font-size:11px;font-weight:600'>{categoria}</span>"
                    f"<br/><span style='color:#757575;font-size:12px'>{motivo_txt}</span>",
                    unsafe_allow_html=True,
                )

    st.caption(
        "💡 Tambem da pra mover pelo IAlex: \"mandei proposta pro Marista, R$ 15k/mes\" · "
        "\"fechei o Anchieta\" · \"perdi o Adventista, foi pra concorrencia\". "
        "Reunioes sem resultado geram atividade automatica na sua agenda."
    )
except Exception as _e:
    st.warning(f"Erro ao carregar o kanban: {_e}")
