# Painel 24/7 na Oracle Cloud (Always Free) — Runbook (Fase A)

Objetivo: rodar o **painel (Streamlit) 24/7, que NUNCA dorme**, no seu domínio
`https://vendasiaprendo.duogen.com.br` com HTTPS, **de graça** (tier *Always Free*
da Oracle, permanente). Depois, a **Fase B** (`docs/DEPLOY_IALEX_ORACLE.md`)
coloca o IAlex na mesma VM.

## Arquitetura
```
VM Ubuntu (Oracle ARM, sempre ligada)
 ├─ Caddy (:80/:443)  → HTTPS automatico (Let's Encrypt)
 │     └─ reverse_proxy → Streamlit 127.0.0.1:8501   [systemd: dashboard.service]
 └─ (Fase B) IAlex: Evolution(Docker) + webhook + scheduler [systemd: ialex.service]
```
Os DADOS ficam no Supabase (fora da VM) → a VM é "descartável"/recriável por este
runbook. Custo: **R$0**.

---

## Fase 0 — Antes de começar (no seu PC)
Tenha à mão (são **gitignored**, secretos — nunca comite):
- `C:\Dev\IAprendo_Sales_Agent\.env`
- `C:\Dev\IAprendo_Sales_Agent\config\users.yaml`

E acesso ao **Cloudflare** (DNS do `duogen.com.br`) para criar 1 registro.

## Fase 1 — Criar a VM (Oracle Console)
1. `cloud.oracle.com` → **Compute → Instances → Create instance**.
   - **Image**: Canonical **Ubuntu 22.04**.
   - **Shape**: **Ampere (ARM) → VM.Standard.A1.Flex**, **2–4 OCPU / 12–24 GB** (Always Free).
   - **SSH keys**: "Generate a key pair" → **baixe a private key** (.key).
   - Crie. Anote o **IP público**.
   > ⚠️ "Out of capacity" no A1 free é comum: tente outra Availability Domain,
   > reduza p/ 2 OCPU/12 GB, ou tente mais tarde.
2. **Security List** (rede da VM): abra as portas de entrada **80** e **443**
   (TCP, origem 0.0.0.0/0), além da **22** que já vem aberta. (A 8080 do
   Evolution NÃO — fica interna.)

## Fase 2 — Conectar na VM (no seu PC, PowerShell)
```
icacls "C:\caminho\sua-key.key" /inheritance:r /grant:r "%USERNAME%:R"
ssh -i "C:\caminho\sua-key.key" ubuntu@<IP-DA-VM>
```

## Fase 3 — Bootstrap (na VM)
```
curl -fsSL https://raw.githubusercontent.com/fernando-duogen/IAprendo-Sales-Agent/main/scripts/setup_vm.sh | bash
exec sudo su -l $USER      # aplica o grupo 'docker'
```
Instala Docker + venv + deps do painel (Streamlit + kaleido) + Caddy +
unattended-upgrades, clona o repo em `~/IAprendo_Sales_Agent`, cria os serviços
`dashboard.service` e `ialex.service` (habilitados, ainda **não** iniciados) e o
`Caddyfile` em `/etc/caddy/Caddyfile`.

## Fase 3.1 — Abrir 80/443 no firewall do SO (gotcha da imagem Ubuntu da Oracle)
A imagem Ubuntu da Oracle **bloqueia** tudo além da 22 por iptables. Libere 80/443:
```
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save      # persiste no boot
```
(Não mexe na 22 — o SSH continua.)

## Fase 4 — Copiar os segredos (do seu PC → VM)
No seu PC (PowerShell):
```
scp -i "C:\caminho\sua-key.key" "C:\Dev\IAprendo_Sales_Agent\.env" ubuntu@<IP>:~/IAprendo_Sales_Agent/.env
scp -i "C:\caminho\sua-key.key" "C:\Dev\IAprendo_Sales_Agent\config\users.yaml" ubuntu@<IP>:~/IAprendo_Sales_Agent/config/users.yaml
```

## Fase 5 — Apontar o domínio (Cloudflare)
No Cloudflare (zona `duogen.com.br`), crie/edite:
- **Tipo A** · **Nome** `vendasiaprendo` · **Conteúdo** `<IP público da VM>`.
- **Proxy status**: comece em **DNS only** (nuvem CINZA) — necessário p/ o Caddy
  emitir o certificado (Let's Encrypt HTTP-01). Depois de o HTTPS funcionar, você
  PODE ligar o proxy (nuvem laranja) com **SSL/TLS → Full (strict)**.

## Fase 6 — Subir o painel + HTTPS (na VM)
```
sudo systemctl start dashboard        # Streamlit em 127.0.0.1:8501
sudo systemctl reload caddy           # Caddy pega o cert HTTPS do dominio
sudo systemctl status dashboard caddy # ambos "active (running)"
```
Abra **https://vendasiaprendo.duogen.com.br** → cadeado válido + tela de login do
painel. (O 1º cert pode levar ~30–60s; se falhar, confira DNS apontado + 80/443
abertas nos DOIS lugares: Security List e iptables.)

Logs úteis:
```
journalctl -u dashboard -f      # log do Streamlit
journalctl -u caddy -f          # log do HTTPS/proxy
```

## Fase 7 — Novos usuários (comerciais, inclusive externos)
Na VM, a fonte única é `config/users.yaml` (o painel recarrega sozinho):
```
cd ~/IAprendo_Sales_Agent
# criar/editar o bloco do novo usuario (copie um existente) e defina a senha:
./venv/bin/python scripts/reset_senha.py     # escolhe o usuario + digita a senha (oculta)
```
Cada comercial acessa pelo domínio e faz login com **usuário + senha**. (Some o
vai-e-vem com os Secrets do Streamlit Cloud.) Use senhas fortes — é um app público
gateado por login.

---

## Manutenção (baixa)
| Tarefa | Comando |
|---|---|
| Ver logs do painel | `journalctl -u dashboard -f` |
| Reiniciar painel | `sudo systemctl restart dashboard` |
| Atualizar o código | `cd ~/IAprendo_Sales_Agent && git pull && sudo systemctl restart dashboard` |
| Recarregar HTTPS/domínio | `sudo systemctl reload caddy` |
| Status geral | `systemctl status dashboard caddy` |

- **Patches automáticos**: `unattended-upgrades` já instalado.
- **Auto-recuperação**: `Restart=always` (systemd) — sobe sozinho no boot/queda.
- **Backup do CRM**: já roda diário (Supabase + `.github/workflows/backup.yml`).

## Fase B — IAlex na mesma VM (tira do PC)
Depois que o painel estiver no ar, siga **`docs/DEPLOY_IALEX_ORACLE.md`**
(Evolution Docker + `ialex.service` + escanear o QR 1x via túnel SSH). O `kaleido`
já foi instalado aqui, então a pré-geração de gráficos/OPR roda na VM (o painel
passa a renderizar os gráficos nativamente — fim da limitação do Streamlit Cloud).

## Depois de tudo no ar — limpeza (Fase C)
- Aposentar o keep-alive frágil: no `.github/workflows/keep-alive.yml` remover o
  `schedule` (deixar só `workflow_dispatch`). Não precisa mais — o painel na VM
  nunca dorme.
- O app do Streamlit Cloud pode ficar como **backup** (auto-deploy do `main`) ou
  ser aposentado — sua escolha.

## Gotchas
- **80/443 em DOIS lugares**: Security List (Oracle) **e** iptables do SO (Fase 3.1).
- **Cloudflare proxy + Let's Encrypt**: emita o cert com "DNS only"; só depois ligue
  o proxy (laranja) com Full (strict).
- **Capacidade ARM**: "out of capacity" no A1 free → retente / outra AD.
- **1 sessão WhatsApp por vez** (Fase B): nunca rode o IAlex no PC e na VM juntos.
