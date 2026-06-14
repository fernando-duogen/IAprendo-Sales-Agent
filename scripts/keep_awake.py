"""keep_awake.py - mantem o app do Streamlit Community Cloud REALMENTE acordado.

Por que nao basta um curl/ping HTTP (o que a versao antiga do keep-alive fazia):
o Streamlit so conta o app como "ativo" quando ha uma SESSAO de navegador de
verdade (a conexao websocket que abre quando a pagina carrega e roda o JS). Um
curl pega so a casca HTML e recebe 200, mas NUNCA abre essa sessao -> o timer de
inatividade do Streamlit nao zera e o app dorme mesmo com o "ping" dando 200.

Aqui usamos Playwright (Chromium headless) pra abrir o app como um navegador
real. Isso:
  1. estabelece a sessao websocket (conta como visita -> reseta o timer);
  2. se o app estiver na tela de "app dormindo", clica em "Yes, get this app
     back up!" pra acordar e espera o boot.

Nao faz login (nem precisa): carregar a tela de login JA roda o app Streamlit e
abre a sessao. Sem credenciais aqui de proposito.

Rodado pela GitHub Action .github/workflows/keep-alive.yml. Local:
    python scripts/keep_awake.py
"""
import os
import re
import sys

from playwright.sync_api import sync_playwright

URL = os.environ.get("KEEPALIVE_URL", "https://iaprendo-sales-agent.streamlit.app/")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 keep-awake-bot")
WAKE_RE = re.compile(r"(get this app back up|back up|wake)", re.I)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()

        print(f"Abrindo {URL} ...", flush=True)
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        # Deixa o JS rodar e o websocket conectar.
        try:
            page.wait_for_load_state("networkidle", timeout=45000)
        except Exception:
            pass  # networkidle pode nao ocorrer; seguimos mesmo assim

        woke = False
        # Tela de "app dormindo": procurar o botao de acordar (varias formas).
        try:
            btn = page.get_by_role("button", name=WAKE_RE)
            if btn.count() == 0:
                # fallback: qualquer elemento clicavel com o texto
                btn = page.get_by_text(WAKE_RE)
            if btn.count() > 0:
                btn.first.click(timeout=10000)
                woke = True
                print("App estava dormindo -> cliquei em acordar; aguardando boot...", flush=True)
                try:
                    page.wait_for_load_state("networkidle", timeout=120000)
                except Exception:
                    pass
        except Exception as e:
            print(f"(sem botao de acordar / app ja ativo) {str(e)[:120]}", flush=True)

        # Mantem a sessao aberta um tempo pra a visita "contar" de verdade.
        page.wait_for_timeout(20000)

        try:
            title = page.title()
        except Exception:
            title = "?"
        print(f"OK - sessao estabelecida (acordou={woke}, title={title!r}).", flush=True)
        browser.close()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FALHA: {str(e)[:300]}", file=sys.stderr)
        sys.exit(1)
