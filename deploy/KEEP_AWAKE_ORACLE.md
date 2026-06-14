# Keep-alive do app (Streamlit Cloud) na VM Oracle — Runbook

**Por que:** o app do Streamlit Community Cloud dorme apos um tempo sem uso real.
Um ping HTTP NAO acorda (o Streamlit so reseta o timer quando ha uma sessao de
navegador de verdade). O GitHub Actions tentava isso, mas o agendador dele e
best-effort (dropa a maioria dos disparos) — keep-alive nao confiavel.

**Solucao:** rodar `scripts/keep_awake.py` (Playwright/Chromium headless, abre o
app como navegador real e clica em "acordar" se preciso) na **VM Oracle que ja
roda o IAlex 24/7**, via **systemd timer** (agendador confiavel), a cada 10 min.

---

## Instalacao (1x, na VM via SSH)

```bash
# 1. Conferir o usuario (as units assumem 'ubuntu'; se for outro, edite
#    deploy/keep-awake.service trocando User= e os paths /home/<voce>/...)
whoami

# 2. Atualizar o repo (traz scripts/keep_awake.py + deploy/*)
cd ~/IAprendo_Sales_Agent && git pull

# 3. Playwright + Chromium (ARM) no venv ja existente do IAlex
./venv/bin/pip install playwright
sudo ./venv/bin/playwright install-deps chromium   # libs de sistema (precisa sudo)
./venv/bin/playwright install chromium

# 4. Teste manual (deve imprimir "OK - sessao estabelecida ...")
KEEPALIVE_URL=https://iaprendo-sales-agent.streamlit.app/ \
  ./venv/bin/python scripts/keep_awake.py

# 5. Instalar e ligar o timer
sudo cp deploy/keep-awake.service deploy/keep-awake.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now keep-awake.timer
```

## Conferir

```bash
systemctl list-timers keep-awake.timer        # mostra o proximo disparo
systemctl status keep-awake.service           # ultima execucao (active/success)
journalctl -u keep-awake.service -n 20        # log da ultima rodada
```

## Operacao

| Acao | Comando |
|---|---|
| Ver proximo disparo | `systemctl list-timers keep-awake.timer` |
| Forcar agora | `sudo systemctl start keep-awake.service` |
| Pausar | `sudo systemctl disable --now keep-awake.timer` |
| Religar | `sudo systemctl enable --now keep-awake.timer` |
| Atualizar codigo | `cd ~/IAprendo_Sales_Agent && git pull` (o timer pega na proxima) |

> Depois que este timer estiver confirmado segurando o app acordado, o keep-alive
> do GitHub (`.github/workflows/keep-alive.yml`) tera o `schedule` removido —
> fica so o botao manual (workflow_dispatch). Sem dois keep-alives concorrentes.
