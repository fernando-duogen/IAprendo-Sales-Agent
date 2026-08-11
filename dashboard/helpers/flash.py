"""flash.py — mensagem de resultado que SOBREVIVE ao st.rerun().

st.success/info/warning/error sao elementos do CORPO da pagina. Quando o codigo
chama st.rerun() logo em seguida, o run atual e abortado e a pagina e
reconstruida do zero: a mensagem nunca chega a ser vista. No dashboard isso
deixava as acoes mais importantes sem retorno nenhum — aprovar uma mensagem
fazia ela sumir da fila e mais nada, sem confirmar se aprovou ou se deu erro.

O padrao correto ja existia no repo em dois lugares, e este modulo apenas
generaliza:
    dashboard/pages/6_Comunicacao.py:118-128
    dashboard/pages/5_Pipeline.py:902-910
        ("Persistir em vez de toast (que some no proximo rerun)")

NAO cobre st.toast: o toast e uma notificacao em overlay com duracao propria e
nao foi verificado que ele se perde no rerun — os call sites de toast ficaram
como estao de proposito.

USO:
    from dashboard.helpers.flash import flash_success, render_flash

    render_flash()                      # uma vez, no topo da pagina/secao
    ...
    flash_success("Mensagem aprovada.")
    st.rerun()
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple

import streamlit as st

_QUEUE = "_flash_queue"
_RENDERERS = {
    "success": lambda t: st.success(t),
    "error": lambda t: st.error(t),
    "warning": lambda t: st.warning(t),
    "info": lambda t: st.info(t),
}


def _state(state: Optional[Any] = None) -> Any:
    """session_state real, ou um mapping injetado (usado nos testes)."""
    return st.session_state if state is None else state


def flash(kind: str, text: str, state: Optional[Any] = None) -> None:
    """Enfileira uma mensagem para ser exibida DEPOIS do proximo rerun."""
    if kind not in _RENDERERS:
        kind = "info"
    ss = _state(state)
    fila: List[Tuple[str, str]] = list(ss.get(_QUEUE) or [])
    fila.append((kind, str(text)))
    # Teto defensivo: uma acao em lote nao pode empilhar 300 banners.
    ss[_QUEUE] = fila[-10:]


def flash_success(text: str, state: Optional[Any] = None) -> None:
    flash("success", text, state)


def flash_error(text: str, state: Optional[Any] = None) -> None:
    flash("error", text, state)


def flash_warning(text: str, state: Optional[Any] = None) -> None:
    flash("warning", text, state)


def flash_info(text: str, state: Optional[Any] = None) -> None:
    flash("info", text, state)


def pending(state: Optional[Any] = None) -> List[Tuple[str, str]]:
    """Mensagens ainda nao exibidas (introspeccao/testes)."""
    return list(_state(state).get(_QUEUE) or [])


def render_flash(state: Optional[Any] = None) -> None:
    """Exibe e consome as mensagens pendentes. Chamar no topo da pagina."""
    ss = _state(state)
    fila = ss.get(_QUEUE) or []
    if not fila:
        return
    ss[_QUEUE] = []
    for kind, text in fila:
        try:
            _RENDERERS.get(kind, _RENDERERS["info"])(text)
        except Exception:
            pass
