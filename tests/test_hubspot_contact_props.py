# -*- coding: utf-8 -*-
"""Props do contato no HubSpot: so valor aceito, e telefone so quando existe.

Contexto (04/09/2026). `decision_maker_type` ia cru pro HubSpot, mas a
propriedade la aceita um conjunto fechado. E `phone` era sempre enviado, mesmo
como "" — o que APAGA um telefone ja existente no HubSpot (283 dos 342 contatos
do CRM estao sem telefone).

Os nomes nao batem entre os dois lados: `utils/role_classifier` produz
`vice_diretor` e `coordenador_pedagogico`; o HubSpot tem `vice` e `coordenador`.
Sao o mesmo papel — traduzir, nao jogar em "outro" (seriam 36 contatos reais).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.hubspot_sync import (  # noqa: E402
    HubSpotSync, _HS_DECISION_MAKER_TYPES, _hubspot_decision_maker_type,
)


def _props(**contato):
    base = {"full_name": "Maria Silva", "email": "maria@colegio.com.br"}
    base.update(contato)
    return HubSpotSync.__new__(HubSpotSync)._contact_to_hubspot_props(base)


# ---------------------------------------------------------------------------
# decision_maker_type
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("valor", sorted(_HS_DECISION_MAKER_TYPES))
def test_valor_ja_aceito_passa_intacto(valor):
    assert _hubspot_decision_maker_type(valor) == valor


@pytest.mark.parametrize("local,esperado", [
    ("vice_diretor", "vice"),
    ("coordenador_pedagogico", "coordenador"),
])
def test_papel_conhecido_com_outro_nome_e_traduzido(local, esperado):
    """34 coordenadores + 2 vices reais dependem disto pra nao virar 'outro'."""
    assert _hubspot_decision_maker_type(local) == esperado


@pytest.mark.parametrize("local", ["administrativo", "secretaria", "porteiro", "xyz"])
def test_papel_desconhecido_vira_outro(local):
    assert _hubspot_decision_maker_type(local) == "outro"


@pytest.mark.parametrize("vazio", [None, "", "   "])
def test_vazio_nao_envia_a_propriedade(vazio):
    assert _hubspot_decision_maker_type(vazio) is None
    assert "decision_maker_type" not in _props(decision_maker_type=vazio)


def test_caixa_e_espacos_nao_criam_valor_invalido():
    assert _hubspot_decision_maker_type("  Vice_Diretor  ") == "vice"
    assert _hubspot_decision_maker_type("DIRETOR") == "diretor"


def test_nada_fora_do_conjunto_chega_no_hubspot():
    """O invariante: qualquer entrada vira um valor aceito ou nada."""
    for entrada in ("diretor", "vice_diretor", "coordenador_pedagogico",
                    "secretaria", "administrativo", "outro", "invento", None, ""):
        saida = _hubspot_decision_maker_type(entrada)
        assert saida is None or saida in _HS_DECISION_MAKER_TYPES, entrada


# ---------------------------------------------------------------------------
# phone
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("vazio", [None, "", "   "])
def test_phone_vazio_nao_e_enviado(vazio):
    """Enviar "" nao e no-op: apaga o telefone que ja estiver no HubSpot."""
    assert "phone" not in _props(phone=vazio)


def test_phone_ausente_no_dict_nao_e_enviado():
    assert "phone" not in _props()


def test_phone_real_e_enviado():
    assert _props(phone="51999998888")["phone"] == "51999998888"


# ---------------------------------------------------------------------------
# o resto do mapeamento nao muda
# ---------------------------------------------------------------------------
def test_demais_campos_intactos():
    p = _props(role="Diretora Pedagogica", linkedin_url="https://lnkd.in/x",
               outreach_priority=1, decision_maker_type="diretor")
    assert p["email"] == "maria@colegio.com.br"
    assert p["firstname"] == "Maria" and p["lastname"] == "Silva"
    assert p["jobtitle"] == "Diretora Pedagogica"
    assert p["hs_linkedinid"] == "https://lnkd.in/x"
    assert p["outreach_priority"] == "1"
