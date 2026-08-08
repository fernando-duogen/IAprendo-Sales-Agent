# -*- coding: utf-8 -*-
"""chat_store (F4): NUNCA levanta — com ou sem a migration APLICAR-022 aplicada.

Antes da migration: load retorna None e save retorna False (chat segue em
memoria). Depois: retorna dados reais. Os testes cobrem o contrato "nao
levanta e retorna o tipo certo" nos dois cenarios.
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.helpers.chat_store import (  # noqa: E402
    load_latest_thread, new_thread_id, save_thread,
)


def test_new_thread_id_e_uuid():
    tid = new_thread_id()
    assert str(uuid.UUID(tid)) == tid


def test_load_nunca_levanta():
    out = load_latest_thread("usuario-inexistente-[E2E-TEST]")
    assert out is None or (isinstance(out, tuple) and len(out) == 3)


def test_save_nunca_levanta():
    ok = save_thread(
        "usuario-inexistente-[E2E-TEST]",
        new_thread_id(),
        [{"role": "user", "content": "oi [E2E-TEST]"}],
        {},
    )
    assert isinstance(ok, bool)
    # Se salvou (migration aplicada), limpa o rastro
    if ok:
        from database.supabase_client import db
        db.client.table("chat_threads").delete().eq(
            "username", "usuario-inexistente-[E2E-TEST]"
        ).execute()
