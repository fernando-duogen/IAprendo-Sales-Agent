#!/usr/bin/env bash
# =====================================================================
# setup_vm.sh — Bootstrap do IAlex numa VM Ubuntu (Oracle Always Free ARM).
# =====================================================================
# Rode 1x na VM (NAO no seu PC):
#   curl -fsSL https://raw.githubusercontent.com/fernando-duogen/IAprendo-Sales-Agent/main/scripts/setup_vm.sh | bash
# ou: git clone ... && bash scripts/setup_vm.sh
#
# Instala Docker + Python venv + deps + clona o repo + cria o servico systemd.
# NAO inicia o IAlex (falta voce copiar .env/users.yaml e escanear o QR — ver
# docs/DEPLOY_IALEX_ORACLE.md). Idempotente: pode rodar de novo.
# =====================================================================
set -euo pipefail

REPO="https://github.com/fernando-duogen/IAprendo-Sales-Agent.git"
DIR="$HOME/IAprendo_Sales_Agent"

echo "== [1/5] Sistema + deps base =="
sudo apt-get update -y
sudo apt-get install -y git python3-venv python3-pip ca-certificates curl gnupg

echo "== [2/5] Docker (engine + compose plugin) =="
if ! command -v docker >/dev/null 2>&1; then
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "   Docker instalado. (faca logout/login pra usar 'docker' sem sudo)"
else
  echo "   Docker ja instalado."
fi

echo "== [3/5] Clonar/atualizar repo =="
if [ ! -d "$DIR/.git" ]; then
  git clone "$REPO" "$DIR"
else
  (cd "$DIR" && git pull --ff-only || true)
fi
cd "$DIR"

echo "== [4/5] venv + deps Python =="
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
if ! ./venv/bin/pip install -r requirements-full.txt -q; then
  echo "   requirements-full falhou (provavel kaleido/playwright em ARM). Instalando core do IAlex..."
  ./venv/bin/pip install -q \
    supabase openai anthropic flask schedule requests httpx python-dotenv \
    pydantic pydantic-settings pyyaml bcrypt brevo-python hubspot-api-client \
    python-json-logger python-dateutil pytz beautifulsoup4 lxml googlemaps \
    geopy phonenumbers unidecode pandas numpy plotly
  echo "   (charts/kaleido e perplexity/playwright sao opcionais — instale depois se precisar)"
fi

echo "== [5/5] Servico systemd (ialex) =="
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
sudo systemctl daemon-reload
sudo systemctl enable ialex.service

echo ""
echo "====================================================================="
echo " OK — base instalada. FALTA (ver docs/DEPLOY_IALEX_ORACLE.md):"
echo "  1) Copiar .env e config/users.yaml pra $DIR (do seu PC, via scp)"
echo "  2) cd $DIR && sudo docker compose up -d   (Evolution+postgres+redis)"
echo "  3) PARAR o IAlex no seu PC (1 sessao WhatsApp por vez)"
echo "  4) Escanear o QR (tunel SSH: ssh -L 8080:localhost:8080 ubuntu@<IP-da-VM>"
echo "     -> abrir http://localhost:8080 e conectar a instancia 'ialex')"
echo "  5) sudo systemctl start ialex   (logs: journalctl -u ialex -f)"
echo "====================================================================="
