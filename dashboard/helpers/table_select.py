"""table_select.py — selecao de linhas que NAO age no registro errado.

PROBLEMA (verificado no fonte do Streamlit 1.56 instalado em venv/):

`st.dataframe(on_select=...)` guarda a selecao como POSICAO de linha, e os dados
NAO entram na identidade do widget:

    streamlit/elements/arrow.py:992-1012
        key_as_main_identity={"selection_mode", "is_selection_activated"}
        # comentario dos proprios devs do Streamlit, no mesmo trecho:
        # "There are some edge cases where selections can become orphaned when
        #  the data changes - e.g. when rows get removed."

E `DataframeSelectionSerde.deserialize` (arrow.py:201-249) devolve os indices
crus, SEM clamp contra o numero de linhas atual.

Consequencia pratica no dashboard: o usuario marca 3 linhas, muda um filtro, e os
mesmos indices passam a apontar para OUTROS registros. A acao em lote (alterar
status, EXCLUIR) roda no alvo errado, em silencio. Se a lista nova for menor que
o maior indice guardado, e IndexError fora de qualquer try — a pagina morre.

Este modulo e a fonte unica para as tres tabelas com selecao (Escolas, Contatos
tabela plana, Contatos agrupada). Nao ha como RE-selecionar linhas por id via
API do Streamlit, entao a unica correcao segura e descartar a selecao quando as
linhas mudam — mesma decisao ja tomada no Pipeline (5_Pipeline.py:183-197).

USO:

    row_ids = df_reset["id"].tolist()
    reset_if_rows_changed("minha_tabela", row_ids)     # ANTES do widget
    ev = st.dataframe(df_reset, key="minha_tabela", on_select="rerun", ...)
    pos = selected_positions(ev, len(row_ids))         # DEPOIS — ja com clamp
    ids = [row_ids[i] for i in pos]                    # ou selected_ids(ev, row_ids)
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import streamlit as st


def _state(state: Optional[Any] = None) -> Any:
    """session_state real, ou um mapping injetado (usado nos testes)."""
    return st.session_state if state is None else state


def rows_signature(row_ids: Sequence[Any]) -> str:
    """Assinatura estavel das linhas exibidas (a ORDEM importa: a selecao e posicional)."""
    joined = "|".join(str(r) for r in row_ids)
    return hashlib.md5(joined.encode("utf-8", "replace")).hexdigest()


def reset_if_rows_changed(widget_key: str, row_ids: Sequence[Any],
                          state: Optional[Any] = None) -> bool:
    """Descarta a selecao guardada quando as linhas mudam. Chamar ANTES do widget.

    Retorna True se descartou (o chamador pode avisar o usuario). No primeiro
    render nao descarta nada — so a partir da segunda assinatura conhecida.
    """
    ss = _state(state)
    sig_key = f"_rowsig_{widget_key}"
    sig = rows_signature(row_ids)
    prev = ss.get(sig_key)
    ss[sig_key] = sig
    if prev is None or prev == sig:
        return False
    # As linhas mudaram: os indices antigos apontam para outros registros.
    # Apagar a chave ANTES do widget renderizar e permitido pelo Streamlit
    # (proibido e mexer DEPOIS da instanciacao).
    try:
        ss.pop(widget_key, None)
    except Exception:
        pass
    return True


def selected_positions(event: Any, n_rows: int) -> List[int]:
    """Indices selecionados, ja limitados ao range atual (nunca estoura .iloc).

    Aceita tanto o objeto do st.dataframe (`event.selection.rows`) quanto o dict
    (`event["selection"]["rows"]`) — as duas formas estao em uso no repo.
    """
    rows: Iterable[Any] = ()
    try:
        rows = event.selection.rows
    except Exception:
        try:
            sel = (event.get("selection") or {}) if event else {}
            rows = sel.get("rows") or []
        except Exception:
            rows = ()
    out: List[int] = []
    for r in rows or ():
        try:
            i = int(r)
        except (TypeError, ValueError):
            continue
        if 0 <= i < n_rows:
            out.append(i)
    return out


def selected_ids(event: Any, row_ids: Sequence[Any]) -> List[Any]:
    """Ids dos registros selecionados. Nunca levanta IndexError."""
    return [row_ids[i] for i in selected_positions(event, len(row_ids))]


def build_label_map(items: Sequence[Any], label_fn: Callable[[Any], str],
                    id_fn: Callable[[Any], Any] = lambda x: x["id"]) -> Dict[str, Any]:
    """{rotulo: id} com rotulo UNICO — colisao ganha sufixo com o id.

    Um dict indexado por rotulo perde silenciosamente registros quando dois
    rotulos coincidem, guardando so o ULTIMO id. Na base do MEC isso e rotina
    (nomes truncados iguais na mesma cidade, ambos com Score 0 e Fit 0). O
    registro perdido nunca conseguia ficar marcado — a rotina de sincronizacao
    nao achava o id entre os rotulos e desfazia a marcacao no mesmo run — e o
    autocomplete devolvia o id do outro.
    """
    out: Dict[str, Any] = {}
    for it in items:
        base = label_fn(it)
        ident = id_fn(it)
        label = base
        if label in out:
            label = f"{base} · #{str(ident)[:8]}"
            n = 2
            while label in out:
                label = f"{base} · #{str(ident)[:8]}~{n}"
                n += 1
        out[label] = ident
    return out
