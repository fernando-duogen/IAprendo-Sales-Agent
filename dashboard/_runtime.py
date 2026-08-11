"""
_runtime - Deteccao de ambiente de execucao do dashboard.

Usado para esconder funcionalidades que so funcionam localmente (i.e. que
dependem do venv Windows via subprocess). NOTA (Ago/2026): o antigo botao de
Perplexity — o principal motivo deste gate — foi aposentado; a busca web hoje
e API pura (tools/web_search.py) e roda em qualquer ambiente, sem gate.
"""
import os
from pathlib import Path


def is_streamlit_cloud() -> bool:
    """Retorna True se o dashboard esta rodando no Streamlit Cloud.

    Heuristicas:
    1. Variavel STREAMLIT_SHARING_MODE/STREAMLIT_SERVER_RUN_ON_SAVE setada pelo Cloud
    2. Path /mount/src existe (mount tipico do Cloud)
    3. venv/Scripts/python.exe NAO existe (no Linux do Cloud nao tem)
    """
    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud":
        return True
    if Path("/mount/src").exists():
        return True
    # Sem o venv local do Windows -> provavelmente Cloud (ou outro Linux)
    venv_python = Path(__file__).parent.parent / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return True
    return False


def runtime_label() -> str:
    """Retorna 'cloud' ou 'local' (para exibir em UI)."""
    return "cloud" if is_streamlit_cloud() else "local"
