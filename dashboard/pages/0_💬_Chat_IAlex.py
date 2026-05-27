"""0_Chat_IAlex - Chat conversacional com o IAlex direto no dashboard.

Reusa 100% do Brain (agent/brain.py) que ja serve o IAlex no WhatsApp.
Cada usuario logado tem historico proprio em session_state.

Cuidado importante: Brain eh singleton com state mutavel
(conversation_history). Pra multi-user simultaneo no Cloud, snapshot/
restore: carregamos historico do user ANTES de cada chamada e salvamos
DEPOIS. Brain controla a estrutura (intercala user/assistant/tool).
"""
import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.theme import apply_theme_no_config, breadcrumb, COLORS

apply_theme_no_config()

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
        # Limpar tambem o conversation_history do brain singleton
        try:
            from agent.brain import brain as _b
            _b.conversation_history = []
        except Exception:
            pass
        st.toast("Historico limpo")
        st.rerun()

st.divider()


# ========================================================================
# LAZY LOAD DO BRAIN (cacheado, carrega 1x por sessao Streamlit)
# ========================================================================
@st.cache_resource(show_spinner="🧠 Carregando IAlex (primeira vez demora ~10s)...")
def _get_brain():
    """Importa e retorna o brain singleton. Cacheado pra nao reimportar."""
    from agent.brain import brain
    return brain


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
# RENDER DO HISTORICO
# ========================================================================
_hist = st.session_state[_history_key]
for _msg in _hist:
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
                if _tool_calls and _show_tools:
                    with st.expander(f"🔧 {len(_tool_calls)} tool(s) chamada(s)", expanded=False):
                        for _tc in _tool_calls:
                            _fn = _tc.get("function", {}).get("name", "?") if isinstance(_tc.get("function"), dict) else "?"
                            _args = _tc.get("function", {}).get("arguments", "{}") if isinstance(_tc.get("function"), dict) else "{}"
                            st.code(f"{_fn}({_args})", language="python")
    # role=tool: nao renderizar (poluiria o chat)


# ========================================================================
# CHAT INPUT
# ========================================================================
_placeholder = (
    "Pergunte ou peca uma acao... "
    "(ex: 'liste as 5 escolas com maior fit no RS' / "
    "'enriqueça as escolas selecionadas' / 'gera email pra Colegio Anchieta')"
)
_user_msg = st.chat_input(_placeholder)

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

    # Processar com feedback visual
    with st.chat_message("assistant", avatar="🤖"):
        with st.status("🧠 Pensando...", expanded=False) as _status:
            try:
                _result = brain.process_message(_user_msg, sender=_username)
                _reply = (_result or {}).get("reply", "(sem resposta)")
                _status.update(label="✅ Concluido", state="complete", expanded=False)
            except Exception as _e_brain_call:
                _reply = f"❌ Erro ao processar: {str(_e_brain_call)[:300]}"
                _status.update(label="❌ Erro", state="error", expanded=True)
        st.markdown(_reply)

    # Salvar historico atualizado (Brain incluiu user + tool_calls + assistant)
    st.session_state[_history_key] = list(brain.conversation_history)

    # Rerun pra re-renderizar o historico de forma limpa (sem duplicacao
    # entre o inline render acima e o loop de historico no proximo run)
    st.rerun()
