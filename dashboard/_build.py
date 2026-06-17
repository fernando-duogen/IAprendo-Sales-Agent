"""Carimbo de build — fonte unica da versao publicada.

Bump a cada deploy relevante. Aparece na sidebar (via theme._add_sidebar_home)
pra confirmar num relance se o Streamlit Cloud esta rodando a versao nova.

Diagnostico de deploy obsoleto: se, apos um push, a sidebar online mostra um
BUILD ANTIGO, o app esta rodando processo velho (modulo cacheado em sys.modules)
-> de Reboot em Manage app (Clear cache NAO basta).
"""

# Formato: AAAA-MM-DD · descricao curta do que mudou
BUILD = "2026-06-17 - fix-escolas-nan-stage"
