"""conftest.py (raiz) — garante que a raiz do projeto esteja no sys.path para
os testes em tests/ importarem utils/, tools/, database/ etc. sob o pytest.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
