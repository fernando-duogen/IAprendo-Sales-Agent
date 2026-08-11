# -*- coding: utf-8 -*-
"""Regressao dos BOTOES QUE MENTIAM (auditoria Ago/2026).

Classe de bug: a UI afirmava sucesso/acao que nao aconteceu — pior que falhar,
porque o usuario segue confiante (ex.: acha que rejeitou um email que foi
enviado, ou espera um resumo no WhatsApp que nunca vem).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAGES = ROOT / "dashboard" / "pages"


def _codigo(path: Path) -> str:
    """Fonte sem comentarios (os fixes citam o bug antigo de proposito)."""
    return "\n".join(
        re.sub(r"#.*$", "", l) for l in path.read_text(encoding="utf-8").splitlines()
    )


# ---------------------------------------------------------------------------
# "Responder com IA" precisa GERAR de verdade
# ---------------------------------------------------------------------------
def test_responder_com_ia_chama_o_gerador():
    """Bug: gravava 2 chaves de sessao que NINGUEM lia e mostrava um toast
    prometendo resposta em 10s. Nada era gerado."""
    src = _codigo(PAGES / "6_✉️_Comunicacao.py")
    assert "reply_handler" in src, "botao nao chama o gerador de resposta"
    assert "process_reply" in src
    # as chaves mortas nao podem voltar
    assert "inbox_generate_queue_id" not in src
    assert "inbox_generate_company_id" not in src


def test_reply_handler_enfileira_como_pendente():
    """REGRA ZERO: a resposta gerada vai pra fila, nunca e enviada."""
    src = (ROOT / "tools" / "reply_handler.py").read_text(encoding="utf-8")
    assert '"status": "pending"' in src


# ---------------------------------------------------------------------------
# "Executar agora" nao pode dizer OK quando o scheduler bloqueou
# ---------------------------------------------------------------------------
def test_executar_agora_checa_retorno():
    """Bug: em modo MANUAL o scheduler retorna {'ok': False} e nao executa,
    mas o painel mostrava ✅ + promessa de resumo no WhatsApp."""
    src = _codigo(PAGES / "9_⚙️_Configuracoes.py")
    assert "run_pipeline_now()" in src
    # o retorno tem que ser usado
    assert re.search(r"_res_run\s*=\s*ialex_scheduler\.run_pipeline_now", src)
    assert re.search(r"_res_fu\s*=\s*ialex_scheduler\.run_followup_now", src)
    assert '_res_run.get("ok"' in src and '_res_fu.get("ok"' in src


# ---------------------------------------------------------------------------
# "Abrir escola" tem que abrir A escola certa
# ---------------------------------------------------------------------------
def test_home_seta_escola_antes_de_navegar():
    """Bug: sem setar escola_detail_id, abria a ULTIMA ficha vista (o id
    persiste entre paginas) — dado de outra escola."""
    src = _codigo(ROOT / "dashboard" / "app.py")
    for trecho in re.findall(r'st\.switch_page\("pages/2_🏫_Escolas\.py"\)', src):
        pass
    # toda navegacao pra ficha deve ser precedida do set do id
    idxs = [m.start() for m in re.finditer(r'st\.switch_page\("pages/2_🏫_Escolas\.py"\)', src)]
    assert idxs, "nenhuma navegacao para Escolas encontrada"
    for i in idxs:
        janela = src[max(0, i - 300):i]
        assert "escola_detail_id" in janela, \
            "switch_page para a ficha sem definir escola_detail_id antes"


# ---------------------------------------------------------------------------
# Fonte dos contatos: dado novo nao pode entrar rotulado como legado
# ---------------------------------------------------------------------------
def test_contatos_importados_gravam_web_search():
    src = _codigo(PAGES / "2_🏫_Escolas.py")
    assert '"source": "web_search"' in src
    assert '"source": "perplexity"' not in src, \
        "contato novo ainda seria gravado como fonte aposentada"


# ---------------------------------------------------------------------------
# Mensagens de warning nao podem sumir
# ---------------------------------------------------------------------------
def test_warning_e_renderizado():
    """Bug: escola_msg do tipo 'warning' era descartada — o motivo do erro
    (ex.: falha na busca de sinais) sumia e o botao parecia nao fazer nada."""
    src = _codigo(PAGES / "2_🏫_Escolas.py")
    assert 'msg_type == "warning"' in src


# ---------------------------------------------------------------------------
# Keys de widget nao podem colidir quando o campo e None
# ---------------------------------------------------------------------------
def test_keys_de_widget_incluem_indice():
    """Bug: 2 itens sem queue_id/inep geravam a MESMA key ('..._None') e o
    Streamlit derrubava a pagina com DuplicateElementKey."""
    com = _codigo(PAGES / "6_✉️_Comunicacao.py")
    assert 'key=f"inbox_respond_{rep.get(' not in com
    assert "inbox_respond_{idx}" in com

    pipe = _codigo(PAGES / "5_📊_Pipeline.py")
    assert 'key=f"rec_work_{_ld.get(\'inep\')}"' not in pipe
    assert "rec_work_{_i_ld}" in pipe


# ---------------------------------------------------------------------------
# Pagina orfa do Mapa: nao pode manter codigo quebrado
# ---------------------------------------------------------------------------
def test_pagina_mapa_e_casca_sem_codigo_quebrado():
    """A pagina esta FORA do menu; mantinha subprocess com venv\\Scripts\\
    python.exe (Windows) e gate de playwright (removido do requirements)."""
    import ast
    src = (PAGES / "4_🗺️_Mapa.py").read_text(encoding="utf-8")
    assert len(src.splitlines()) < 60, "deveria ser uma casca como as outras 3 orfas"

    # AST: checa CODIGO de verdade (a docstring cita os termos ao explicar o fix)
    arvore = ast.parse(src)
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    for proibido in ("subprocess", "playwright"):
        assert proibido not in importados, f"casca ainda importa {proibido}"

    # nenhuma string do codigo pode carregar o caminho do venv Windows
    literais = [n.value for n in ast.walk(arvore)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    corpo = "\n".join(literais[1:])  # [0] = docstring do modulo
    for proibido in ("Scripts", "perplexity", "playwright"):
        assert proibido.lower() not in corpo.lower(), \
            f"casca ainda referencia {proibido} em codigo"


# ---------------------------------------------------------------------------
# Dedução de email voltou (perdida na migracao do Perplexity)
# ---------------------------------------------------------------------------
def test_web_search_marca_email_institucional_e_deduz():
    import json
    import tools.web_search as ws

    payload = json.dumps([
        {"full_name": None, "role": "Secretaria", "email": "secretaria@escola.com.br"},
        {"full_name": "Maria Silva", "role": "Diretora", "email": None},
    ])
    ws_call = ws._call
    try:
        ws._call = lambda prompt, endpoint, timeout_seconds=60: payload
        out = ws.search_school_contacts("X", "Y", "RS", dominio="escola.com.br")
    finally:
        ws._call = ws_call

    por_nome = {c["full_name"]: c for c in out}
    assert por_nome["Responsavel"]["_is_general_email"] is True   # secretaria@
    assert por_nome["Maria Silva"].get("_suggested_email") == "maria.silva@escola.com.br"
