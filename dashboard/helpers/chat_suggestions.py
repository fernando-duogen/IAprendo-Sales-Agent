"""Sugestoes proativas do Chat IAlex (operador v1, F3).

Chips deterministicos calculados dos dados reais (ZERO chamada de LLM/API paga)
que viram um turno de conversa quando clicados. O IAlex entao executa com as
tools — sempre sob o gate de aprovacao para qualquer acao de escrita.

Fontes (todas guardadas — falha silenciosa remove o chip):
  1. Emails pendentes de aprovacao (approval_queue status=pending)
  2. Emails aprovados aguardando envio (status=approved)
  3. Atividades atrasadas do usuario (db.list_activities open + due_before=now)
  4. Fallback: "O que devo fazer agora?" quando nada acima existir.
"""
from datetime import datetime, timezone
from typing import Dict, List

import streamlit as st

from database.supabase_client import db


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_suggestions(username: str) -> List[Dict[str, str]]:
    """Lista de chips {texto, prompt}. Cache 2 min por usuario."""
    chips: List[Dict[str, str]] = []

    # 1) Pendentes de aprovacao
    try:
        r = (db.client.table("approval_queue").select("id", count="exact")
             .eq("status", "pending").limit(1).execute())
        n = r.count or 0
        if n:
            chips.append({
                "texto": f"✉️ Aprovar {n} email(s) pendente(s)",
                "prompt": "mostra a fila de aprovacao pendente",
            })
    except Exception:
        pass

    # 2) Aprovados aguardando envio
    try:
        r = (db.client.table("approval_queue").select("id", count="exact")
             .eq("status", "approved").limit(1).execute())
        n = r.count or 0
        if n:
            chips.append({
                "texto": f"📤 {n} aprovado(s) aguardando envio",
                "prompt": "quais emails estao aprovados aguardando envio? posso enviar agora?",
            })
    except Exception:
        pass

    # 3) Atividades atrasadas do usuario
    try:
        now = datetime.now(timezone.utc).isoformat()
        acts = db.list_activities(owner=username, status=["open"],
                                  due_before=now, limit=50) or []
        if acts:
            chips.append({
                "texto": f"⏰ {len(acts)} atividade(s) atrasada(s)",
                "prompt": "quais sao minhas atividades atrasadas? me ajuda a resolver",
            })
    except Exception:
        pass

    # 4) Fallback util quando esta tudo em dia
    if not chips:
        chips.append({
            "texto": "🧭 O que devo fazer agora?",
            "prompt": "com base nos meus leads e na agenda, quais as 3 proximas acoes mais importantes agora?",
        })
    return chips[:4]


def render_suggestions(username: str) -> None:
    """Linha de chips clicaveis. Clique injeta o prompt como turno do usuario.

    Nunca levanta: qualquer erro esconde os chips (chat segue normal).
    """
    try:
        chips = _fetch_suggestions(username)
        if not chips:
            return
        st.caption("💡 Sugestoes de agora:")
        cols = st.columns(len(chips))
        for i, chip in enumerate(chips):
            with cols[i]:
                if st.button(chip["texto"], key=f"chat_sug_{i}", use_container_width=True):
                    st.session_state["chat_injected_msg"] = chip["prompt"]
                    st.rerun()
    except Exception:
        pass
