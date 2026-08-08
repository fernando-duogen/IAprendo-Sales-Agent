"""0_Chat_IAlex - Chat conversacional com o IAlex direto no dashboard.

Reusa 100% do Brain (agent/brain.py) que ja serve o IAlex no WhatsApp.
Cada usuario logado tem historico proprio em session_state.

Cuidado importante: Brain eh singleton com state mutavel
(conversation_history). Pra multi-user simultaneo no Cloud, snapshot/
restore: carregamos historico do user ANTES de cada chamada e salvamos
DEPOIS. Brain controla a estrutura (intercala user/assistant/tool).

Operador v1 (F1): alem do texto, o Brain devolve `blocks` (tabelas, graficos,
downloads, previews de email) que renderizamos inline via chat_blocks_view.
Os blocks ficam num mapa PARALELO por hash do conteudo da resposta — NUNCA
dentro do conversation_history (que e enviado a API OpenAI).
"""
import hashlib
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import apply_theme_no_config, breadcrumb, COLORS

apply_theme_no_config()

# Renderer dos blocos ricos — defensivo: sem ele o chat segue 100% em texto.
try:
    from dashboard.helpers.chat_blocks_view import render_blocks as _render_blocks
except Exception:
    _render_blocks = None


def _bkey(content: str) -> str:
    """Chave estavel de blocks por conteudo da resposta (sobrevive a trim)."""
    return hashlib.md5((content or "").encode("utf-8", "ignore")).hexdigest()[:16]

from dashboard._auth_gate import require_auth
require_auth()


# ========================================================================
# HEADER
# ========================================================================
breadcrumb(["IAprendo", "Chat IAlex"])
st.markdown("# 💬 Chat com IAlex")
st.caption(
    "Pergunte qualquer coisa sobre suas escolas, peca acoes, ou execute fluxos. "
    "O IAlex tem acesso ao banco, ENEM, Censo, pipeline de emails — tudo que voce "
    "ja usa no WhatsApp, agora aqui."
)


# ========================================================================
# IDENTIDADE DO USUARIO ATIVO
# ========================================================================
_username = st.session_state.get("username", "fernando")
_name = st.session_state.get("name", "Fernando")
_first = (_name or "voce").split()[0] if _name else "voce"

# Setar sender ativo pra Brain (saudacao, signature, multi-user)
try:
    from utils.sender_profile import set_active_sender_for_thread
    set_active_sender_for_thread(_username)
except Exception as _e_sender:
    st.warning(f"⚠️ Nao foi possivel resolver identidade do usuario: {_e_sender}")


# ========================================================================
# HISTORICO POR USUARIO (multi-tenant via session_state)
# ========================================================================
_history_key = f"chat_history_{_username}"
if _history_key not in st.session_state:
    st.session_state[_history_key] = []

# Mapa PARALELO de blocks ricos: {hash(reply) -> [blocks]}. Fora do history!
_blocks_key = f"chat_blocks_{_username}"
if _blocks_key not in st.session_state:
    st.session_state[_blocks_key] = {}


# ========================================================================
# BRAIN POR SESSAO — uma instancia POR USUARIO (nao compartilhada)
# ========================================================================
# IMPORTANTE: NAO usar @st.cache_resource aqui. cache_resource cria 1
# instancia GLOBAL pro processo Streamlit inteiro, compartilhada por TODAS
# as sessoes/usuarios. Como Brain.conversation_history e mutavel, 2 usuarios
# no chat ao mesmo tempo misturariam historico (race no snapshot/restore).
# Instanciando por sessao (st.session_state), cada usuario tem o SEU Brain.
# Brain() eh barato (tools ja carregadas no import do modulo).
def _get_brain():
    """Retorna o Brain DESTA sessao (cria 1x por sessao, guardado em session_state)."""
    if "_brain_instance" not in st.session_state:
        from agent.brain import Brain
        st.session_state["_brain_instance"] = Brain()
    return st.session_state["_brain_instance"]


try:
    brain = _get_brain()
except Exception as _e_brain:
    st.error(
        f"❌ Erro ao carregar Brain: {_e_brain}\n\n"
        "Possiveis causas: OPENAI_API_KEY/ANTHROPIC_API_KEY nao configurada "
        "nos Secrets do Streamlit Cloud."
    )
    st.stop()


# ========================================================================
# CONTROLES (topo)
# ========================================================================
ctop1, ctop2, ctop3 = st.columns([5, 2, 2])
with ctop1:
    st.caption(
        f"👤 **{_name}** — historico proprio. "
        f"Total de mensagens: **{sum(1 for m in st.session_state[_history_key] if m.get('role') in ('user', 'assistant') and m.get('content'))}**"
    )
with ctop2:
    _show_tools = st.checkbox(
        "🔧 Mostrar tools",
        value=False,
        key="chat_show_tools",
        help="Mostra expander com JSON das tools executadas pelo IAlex. Util pra debug.",
    )
with ctop3:
    if st.button("🗑️ Limpar historico", use_container_width=True, key="chat_clear"):
        st.session_state[_history_key] = []
        st.session_state[_blocks_key] = {}
        # Limpar tambem o conversation_history do brain cacheado
        try:
            brain.conversation_history = []
        except Exception:
            pass
        st.toast("Historico limpo")
        st.rerun()

st.divider()


# ========================================================================
# RENDER DO HISTORICO
# ========================================================================
_hist = st.session_state[_history_key]
_blocks_map = st.session_state[_blocks_key]
for _idx, _msg in enumerate(_hist):
    _role = _msg.get("role")
    if _role == "user":
        with st.chat_message("user", avatar="🙋"):
            st.markdown(_msg.get("content", ""))
    elif _role == "assistant":
        _content = _msg.get("content", "") or ""
        _tool_calls = _msg.get("tool_calls") or []
        # So renderiza se tem CONTEUDO ou se queremos mostrar tools
        if _content or (_tool_calls and _show_tools):
            with st.chat_message("assistant", avatar="🤖"):
                if _content:
                    st.markdown(_content)
                    # Blocks ricos deste turno (mapa paralelo por hash do reply)
                    _msg_blocks = _blocks_map.get(_bkey(_content)) or []
                    if _msg_blocks and _render_blocks:
                        _render_blocks(_msg_blocks, key=f"h{_idx}")
                    # Fallback legado: URLs .xlsx no texto viram botao — mas SO
                    # se este turno nao trouxe um bloco download (evita duplicar)
                    _has_dl = any(b.get("type") == "download" for b in _msg_blocks)
                    if not _has_dl:
                        import re as _re_xlsx
                        _urls_xlsx = _re_xlsx.findall(r'https?://[^\s)\]<>"\']+\.xlsx[^\s)\]<>"\']*', _content)
                        for _url_x in _urls_xlsx:
                            st.link_button(
                                "📥 Baixar XLSX",
                                _url_x,
                                type="primary",
                                help="Arquivo gerado pelo IAlex. Validade: 24h.",
                            )
                if _tool_calls and _show_tools:
                    with st.expander(f"🔧 {len(_tool_calls)} tool(s) chamada(s)", expanded=False):
                        for _tc in _tool_calls:
                            _fn = _tc.get("function", {}).get("name", "?") if isinstance(_tc.get("function"), dict) else "?"
                            _args = _tc.get("function", {}).get("arguments", "{}") if isinstance(_tc.get("function"), dict) else "{}"
                            st.code(f"{_fn}({_args})", language="python")
    # role=tool: nao renderizar (poluiria o chat)


# ========================================================================
# SUGESTOES PROATIVAS (F3) — chips deterministicos; clique vira turno
# ========================================================================
try:
    from dashboard.helpers.chat_suggestions import render_suggestions
    render_suggestions(_username)
except Exception:
    pass


# ========================================================================
# CHAT INPUT
# ========================================================================
_placeholder = (
    "Pergunte ou peca uma acao... "
    "(ex: 'liste as 5 escolas com maior fit no RS' / "
    "'enriqueça as escolas selecionadas' / 'gera email pra Colegio Anchieta')"
)
_user_msg = st.chat_input(_placeholder)

# Chip clicado no run anterior vira o turno do usuario deste run
_injected = st.session_state.pop("chat_injected_msg", None)
if _injected and not _user_msg:
    _user_msg = _injected

if _user_msg:
    # Renderizar a user msg IMEDIATAMENTE (antes do processamento)
    with st.chat_message("user", avatar="🙋"):
        st.markdown(_user_msg)

    # Re-setar sender (thread pode ter sido reciclada)
    try:
        set_active_sender_for_thread(_username)
    except Exception:
        pass

    # Snapshot: carregar historico DO USUARIO no Brain (singleton compartilhado)
    # Brain vai adicionar a user msg sozinho dentro de process_message.
    brain.conversation_history = list(st.session_state[_history_key])

    # Processar com feedback visual (status vivo via on_event do Brain)
    with st.chat_message("assistant", avatar="🤖"):
        with st.status("🧠 Pensando...", expanded=False) as _status:
            _TOOL_LABELS = {
                "consultar_escolas": "🔎 Consultando escolas...",
                "fila_aprovacao": "✉️ Lendo fila de aprovacao...",
                "gerar_graficos_escola": "📊 Gerando graficos...",
                "gerar_relatorio_escola": "📄 Gerando One Page Report...",
                "exportar_escolas_xlsx": "📥 Exportando XLSX...",
                "gerar_email": "✍️ Escrevendo email...",
            }

            def _on_event(evt):
                if evt.get("type") == "tool_start":
                    _tool = evt.get("tool", "")
                    _status.update(
                        label=_TOOL_LABELS.get(_tool, f"⚙️ {_tool}..."),
                        state="running",
                    )

            try:
                _result = brain.process_message(
                    _user_msg,
                    sender=_username,
                    max_iterations=8,
                    max_tokens=4096,
                    on_event=_on_event,
                )
                _reply = (_result or {}).get("reply", "(sem resposta)")
                _blocks = (_result or {}).get("blocks", []) or []
                _status.update(label="✅ Concluido", state="complete", expanded=False)
            except Exception as _e_brain_call:
                _reply = f"❌ Erro ao processar: {str(_e_brain_call)[:300]}"
                _blocks = []
                _status.update(label="❌ Erro", state="error", expanded=True)
        st.markdown(_reply)
        if _blocks and _render_blocks:
            _render_blocks(_blocks, key="live")

    # Salvar historico atualizado (Brain incluiu user + tool_calls + assistant)
    st.session_state[_history_key] = list(brain.conversation_history)
    # Blocks ricos ficam no mapa PARALELO, chaveados pelo hash do reply
    if _blocks:
        st.session_state[_blocks_key][_bkey(_reply)] = _blocks

    # Rerun pra re-renderizar o historico de forma limpa (sem duplicacao
    # entre o inline render acima e o loop de historico no proximo run)
    st.rerun()
