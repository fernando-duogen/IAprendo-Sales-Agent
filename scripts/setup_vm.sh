#!/usr/bin/env bash
# =====================================================================
# setup_vm.sh — Bootstrap da PLATAFORMA numa VM Ubuntu (Oracle Always Free ARM).
# =====================================================================
# Sobe o PAINEL (Streamlit 24/7 atras do Caddy/HTTPS) e prepara o IAlex.
# Rode 1x na VM (NAO no seu PC):
#   curl -fsSL https://raw.githubusercontent.com/fernando-duogen/IAprendo-Sales-Agent/main/scripts/setup_vm.sh | bash
# ou: git clone ... && bash scripts/setup_vm.sh
#
# Instala Docker + Python venv + deps + Caddy + kaleido/libs + unattended-upgrades,
# clona o repo e cria os servicos systemd (dashboard + ialex). NAO inicia nada que
# dependa de segredos (falta copiar .env/users.yaml e apontar o DNS —
# ver docs/DEPLOY_DASHBOARD_ORACLE.md e docs/DEPLOY_IALEX_ORACLE.md).
# Idempotente: pode rodar de novo.
# =====================================================================
set -euo pipefail

REPO="https://github.com/fernando-duogen/IAprendo-Sales-Agent.git"
DIR="$HOME/IAprendo_Sales_Agent"

# VM nova roda auto-update no 1o boot e "trava" o apt. Faz o apt ESPERAR o lock
# (ate 10 min) em vez de falhar com "Could not get lock".
echo 'DPkg::Lock::Timeout "600";' | sudo tee /etc/apt/apt.conf.d/99lock-timeout >/dev/null 2>&1 || true

echo "== [1/7] Sistema + deps base + patches automaticos + libs de grafico =="
# Fuso horario do NEGOCIO (Porto Alegre). A imagem Oracle vem em UTC e o
# scheduler do IAlex usa horario LOCAL — em UTC os briefings/digests
# disparariam 3h mais cedo (bom dia as 05:00).
sudo timedatectl set-timezone America/Sao_Paulo || true
sudo apt-get update -y
sudo apt-get install -y git python3-venv python3-pip ca-certificates curl gnupg \
  unattended-upgrades apt-transport-https debian-keyring debian-archive-keyring
# Libs de sistema p/ o kaleido (render de PNG do Plotly via Chromium headless):
sudo apt-get install -y libgbm1 libnss3 libasound2 libxshmfence1 || true
# Patches de seguranca automaticos (baixa manutencao):
sudo dpkg-reconfigure -f noninteractive unattended-upgrades || true

echo "== [2/7] Docker (engine + compose plugin) — usado na Fase B (IAlex); nao-fatal =="
install_docker() {
  if command -v docker >/dev/null 2>&1; then echo "   Docker ja instalado."; return 0; fi
  sudo install -m 0755 -d /etc/apt/keyrings
  # --batch --yes: gpg sem terminal (evita 'cannot open /dev/tty' quando roda detached)
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "   Docker instalado. (faca logout/login pra usar 'docker' sem sudo)"
}
# Nao-fatal: Docker so e necessario na Fase B (IAlex). Se falhar, o PAINEL segue.
install_docker || echo "   [aviso] Docker falhou — segue o painel normalmente (Docker e so p/ Fase B/IAlex)."

echo "== [3/7] Clonar/atualizar repo =="
if [ ! -d "$DIR/.git" ]; then
  git clone "$REPO" "$DIR"
else
  (cd "$DIR" && git pull --ff-only || true)
fi
cd "$DIR"

echo "== [4/7] venv + deps Python (painel primeiro; extras do IAlex best-effort) =="
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
# 4a) Dashboard (pinado, inclui kaleido) — ESSENCIAL pro painel:
if ! ./venv/bin/pip install -q -r requirements.txt; then
  echo "   requirements.txt parcial (provavel kaleido em ARM). Instalando essenciais do painel..."
  ./venv/bin/pip install -q "streamlit>=1.56,<1.57" streamlit-authenticator==0.4.2 bcrypt pyyaml \
    supabase pandas plotly pydeck python-dotenv requests schedule python-dateutil \
    python-json-logger beautifulsoup4 lxml unidecode anthropic openai hubspot-api-client \
    phonenumbers openpyxl
  ./venv/bin/pip install -q kaleido || echo "   [aviso] kaleido nao instalou (ARM) — graficos podem nao renderizar; ver Fase 9 do runbook do IAlex"
fi
# 4b) Extras do IAlex (flask, playwright, etc.) — best-effort (usados na Fase B):
./venv/bin/pip install -q -r requirements-full.txt 2>/dev/null || echo "   [info] extras do IAlex parciais em ARM (ok — instalam na Fase B se preciso)"
# 4c) Garante o pin do streamlit do dashboard (o full pode ter afrouxado):
./venv/bin/pip install -q "streamlit>=1.56,<1.57"

echo "== [5/7] systemd: dashboard.service (Streamlit 24/7 em 127.0.0.1:8501) =="
sudo tee /etc/systemd/system/dashboard.service >/dev/null <<UNIT
[Unit]
Description=IAprendo Dashboard (Streamlit) - painel de vendas
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
Environment=PYTHONIOENCODING=utf-8
ExecStart=$DIR/venv/bin/streamlit run $DIR/dashboard/main.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

echo "== [6/7] systemd: ialex.service (webhook + scheduler; iniciado na Fase B) =="
sudo tee /etc/systemd/system/ialex.service >/dev/null <<UNIT
[Unit]
Description=IAlex - webhook + scheduler (IAprendo Sales Agent)
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$DIR
Environment=PYTHONIOENCODING=utf-8
ExecStart=$DIR/venv/bin/python $DIR/agent/start_ialex.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

echo "== [7/7] Caddy (HTTPS automatico p/ o painel) =="
if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y caddy
else
  echo "   Caddy ja instalado."
fi
# Instala o Caddyfile do repo (dominio + reverse_proxy p/ o Streamlit):
if [ -f "$DIR/deploy/Caddyfile" ]; then
  sudo cp "$DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
  echo "   Caddyfile instalado em /etc/caddy/Caddyfile"
fi

sudo systemctl daemon-reload
sudo systemctl enable dashboard.service ialex.service >/dev/null 2>&1 || true

echo ""
echo "====================================================================="
echo " OK — base instalada. PROXIMOS PASSOS:"
echo ""
echo " PAINEL (Fase A — ver docs/DEPLOY_DASHBOARD_ORACLE.md):"
echo "  1) Copiar .env e config/users.yaml pra $DIR (do seu PC, via scp)"
echo "  2) Apontar o DNS: registro A vendasiaprendo.duogen.com.br -> IP publico da VM"
echo "     (Cloudflare em 'DNS only'/nuvem cinza p/ emitir o certificado)"
echo "  3) sudo systemctl start dashboard"
echo "  4) sudo systemctl reload caddy   (Caddy pega o cert HTTPS automatico)"
echo "  5) Abrir https://vendasiaprendo.duogen.com.br -> login do painel"
echo ""
echo " IALEX (Fase B — ver docs/DEPLOY_IALEX_ORACLE.md):"
echo "  6) cd $DIR && sudo docker compose up -d   (Evolution+postgres+redis)"
echo "  7) PARAR o IAlex no PC, escanear o QR (tunel SSH -L 8080), depois:"
echo "  8) sudo systemctl start ialex"
echo "====================================================================="
