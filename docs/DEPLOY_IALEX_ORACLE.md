# Deploy do IAlex 24/7 na Oracle Cloud (Always Free) — Runbook

Objetivo: rodar o **IAlex (WhatsApp) 24/7 de graça**, numa VM da Oracle que fica
sempre ligada — **independente do seu PC**. Custo: R$0 (tier *Always Free* da
Oracle, permanente).

> O dashboard (Streamlit) NÃO muda — continua no Streamlit Cloud. Aqui é só o
> IAlex (Evolution/WhatsApp + webhook + scheduler).

## Arquitetura na VM
```
VM Ubuntu (Oracle ARM, sempre ligada)
 ├─ Docker: Evolution API + Postgres + Redis   (restart: always)
 └─ Python (venv) via systemd: start_ialex.py  (Restart=always)
        ↳ webhook Flask :5001  ←  Evolution chama via host.docker.internal
```
Tudo já está pronto pra Linux (o `docker-compose.yml` tem `extra_hosts` + o Flask
faz bind em `0.0.0.0`). Keep-alive nativo: `restart: always` (Docker) + systemd
`Restart=always` + a VM 24/7. Sem GitHub Action/cron pra isso.

---

## Fase 0 — Antes de começar (no seu PC)
Você vai precisar copiar 2 arquivos **secretos** (gitignored) pra VM depois:
- `.env` (chaves: Supabase, OpenAI, Brevo, Evolution, IALEX_*…)
- `config/users.yaml` (logins + números de WhatsApp dos 3)

Deixe-os à mão. **Não comite** esses arquivos.

## Fase 1 — Criar conta + VM (Oracle Cloud)
1. Crie conta em **cloud.oracle.com** (pede cartão p/ verificação; o *Always Free*
   não cobra). Escolha uma Home Region perto (ex: Brazil East / São Paulo).
2. Console → **Compute → Instances → Create instance**:
   - **Image**: Canonical **Ubuntu 22.04**.
   - **Shape**: **Ampere (ARM) → VM.Standard.A1.Flex**, 2-4 OCPU e 12-24 GB RAM
     (tudo dentro do Always Free). *(O shape AMD micro de 1 GB é pequeno demais.)*
   - **SSH keys**: "Generate a key pair" → **baixe a private key** (.key).
   - Crie. Anote o **IP público**.
   > ⚠️ Se der "Out of capacity" no A1 (comum no free ARM): tente outra
   > Availability Domain, reduza p/ 2 OCPU/12GB, ou tente em outro horário.
3. **Firewall (Security List)**: por padrão só a porta **22 (SSH)** fica aberta —
   **deixe assim** (mais seguro). O QR a gente acessa por túnel SSH, não expondo a 8080.

## Fase 2 — Conectar na VM
No seu PC (PowerShell), com a private key baixada:
```
icacls "C:\caminho\sua-key.key" /inheritance:r /grant:r "%USERNAME%:R"   # corrige permissao no Windows
ssh -i "C:\caminho\sua-key.key" ubuntu@<IP-DA-VM>
```

## Fase 3 — Bootstrap (na VM)
```
curl -fsSL https://raw.githubusercontent.com/fernando-duogen/IAprendo-Sales-Agent/main/scripts/setup_vm.sh | bash
exec sudo su -l $USER   # ou logout/login: aplica o grupo 'docker'
```
Isso instala Docker + Python venv + deps, clona o repo em `~/IAprendo_Sales_Agent`
e cria o serviço systemd `ialex` (habilitado, ainda **não** iniciado).

## Fase 4 — Copiar os segredos (do seu PC → VM)
No seu PC (PowerShell), envie `.env` e `users.yaml`:
```
scp -i "C:\caminho\sua-key.key" "C:\Dev\IAprendo_Sales_Agent\.env" ubuntu@<IP>:~/IAprendo_Sales_Agent/.env
scp -i "C:\caminho\sua-key.key" "C:\Dev\IAprendo_Sales_Agent\config\users.yaml" ubuntu@<IP>:~/IAprendo_Sales_Agent/config/users.yaml
```
> No `.env` da VM, confirme `EVOLUTION_URL=http://localhost:8080` (Evolution roda
> em Docker, porta publicada no host). O resto das chaves é igual ao do PC.

## Fase 5 — Subir o Evolution (na VM)
```
cd ~/IAprendo_Sales_Agent
sudo docker compose up -d
sudo docker compose ps          # postgres/redis/evolution_api "Up (healthy)"
```

## Fase 6 — Conectar o WhatsApp (escanear o QR 1x)
⚠️ **PARE o IAlex no seu PC primeiro** (Ctrl+C / feche o `start-ialex.bat`). O
WhatsApp só aceita **uma** sessão Baileys por vez — escanear na VM desconecta a do PC.

1. No seu PC, abra um **túnel SSH** pra porta 8080 da VM:
   ```
   ssh -i "C:\caminho\sua-key.key" -L 8080:localhost:8080 ubuntu@<IP>
   ```
2. Deixe esse túnel aberto e, **na VM** (outra aba SSH), rode o setup interativo 1x
   pra criar a instância + gerar o QR:
   ```
   cd ~/IAprendo_Sales_Agent
   ./venv/bin/python agent/start_ialex.py
   ```
   Ele imprime um link tipo `http://localhost:8080/instance/connect/ialex`.
3. No **navegador do seu PC** (graças ao túnel) abra esse link → aparece o QR →
   escaneie no celular (WhatsApp → Aparelhos conectados → Conectar aparelho).
4. Quando ele disser **"WhatsApp conectado"** e o IAlex mandar a msg de boot,
   dê **Ctrl+C** (a sessão fica salva no volume Docker do Evolution).

## Fase 7 — Iniciar o IAlex de verdade (systemd, 24/7)
```
sudo systemctl start ialex
sudo systemctl status ialex          # active (running)
journalctl -u ialex -f               # logs ao vivo (Ctrl+C sai do log)
```
Agora ele sobe sozinho no boot e reinicia se cair. Teste mandando uma mensagem no
WhatsApp → deve responder a partir da VM.

## Fase 8 — Desativar o IAlex no PC
Pra não competir pela sessão WhatsApp: no PC, **não rode mais** o `start-ialex.bat`
(e se tiver auto-start/PM2 do IAlex no PC, desative). O dashboard local continua normal.

---

## Manutenção (na VM)
| Tarefa | Comando |
|---|---|
| Ver logs | `journalctl -u ialex -f` |
| Reiniciar IAlex | `sudo systemctl restart ialex` |
| Reiniciar Evolution | `cd ~/IAprendo_Sales_Agent && sudo docker compose restart evolution-api` |
| Atualizar o código | `cd ~/IAprendo_Sales_Agent && git pull && sudo systemctl restart ialex` |
| Status geral | `sudo systemctl status ialex && sudo docker compose ps` |

## Gotchas
- **1 sessão WhatsApp por vez**: nunca rode o IAlex no PC e na VM juntos (um derruba o outro).
- **Capacidade ARM da Oracle**: o A1 free às vezes dá "out of capacity" — insista/retente.
- **ARM (kaleido/playwright)**: se os gráficos de email ou a busca Perplexity derem
  erro na VM, são deps opcionais ARM — instale depois (`pip install kaleido` /
  `playwright install chromium`). O núcleo do IAlex funciona sem.
- **Segurança**: mantenha só a 22 aberta; o QR via túnel SSH; a chave da Evolution
  (`AUTHENTICATION_API_KEY`) protege a 8080 mesmo internamente.
- **Sessão WhatsApp = volume `evolution_instances`**: não apague esse volume Docker
  (perde a conexão e teria que re-escanear o QR).

## Quando NÃO ligar a VM (alternativa)
Se um dia quiser voltar pro PC (grátis também), é só parar a VM e rodar o
`start-ialex.bat` no PC de novo (re-escaneando o QR, pois a sessão volta pro PC).
