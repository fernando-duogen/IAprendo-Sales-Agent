# Runbook — Mudanca de Local do Projeto

Guia para mover a pasta do IAprendo Sales Agent de um caminho para outro
(mesma maquina) preservando venv, sessao WhatsApp, memoria IAlex, hist�rico
Claude Code e configuracoes locais.

**Ultima execucao**: 2026-04-21, de
`C:\Users\Fernando Nienaber\LAUFEN PARTICIPACOES LTDA\...\agente-de-vendas`
para `C:\Dev\IAprendo_Sales_Agent`.

---

## TL;DR (checklist de 7 passos)

1. `docker compose down` (sem `-v` para preservar volumes)
2. Mover/copiar a pasta para o novo local
3. Garantir `name: agente-de-vendas` no topo do `docker-compose.yml`
4. Deletar `venv/` e recriar: `python -m venv venv` + `pip install -r requirements-full.txt`
5. Atualizar paths antigos em `.claude/settings.local.json` e `scripts/create-shortcuts.ps1`
6. Copiar `*.jsonl` de `~/.claude/projects/<pasta-antiga>/` para `~/.claude/projects/<pasta-nova>/`
7. `docker compose up -d` e testar dashboard, IAlex, conexao WhatsApp

---

## O que NAO precisa ser ajustado

- Codigo Python — usa `Path(__file__).parent.parent` (paths relativos)
- `.env` — contem apenas chaves e paths relativos (`data/raw/...`)
- `config/settings.py` — carrega via `python-dotenv`
- `.streamlit/config.toml`, `.claude/launch.json` — paths relativos
- Memoria do IAlex (tabela `conversation_memory` no Supabase) — cloud-native
- Dados do CRM (companies, contacts, approval_queue, interactions) — Supabase
- Scripts `start-*.bat` — usam `%~dp0` (diretorio do proprio script)
- Volumes Docker nomeados (`evolution_pgdata`, `evolution_redis`, `evolution_instances`)
  desde que o project name do compose seja preservado (ver passo 3)

---

## Passo a Passo detalhado

### 1. Pre-mudanca — parar servicos

Antes de mover a pasta:

```bash
# Parar IAlex webhook e dashboard (se rodando)
# Fechar janelas dos start-*.bat

# Parar containers preservando volumes
cd <caminho-antigo>
docker compose down
# CRITICO: nunca passe -v aqui senao voce perde a sessao WhatsApp
```

Opcional — snapshot das dependencias atuais:
```bash
venv\Scripts\pip freeze > requirements-snapshot.txt
```

### 2. Mover a pasta

No Explorer do Windows ou via shell: recorte a pasta inteira e cole no novo local.

### 3. Preservar sessao WhatsApp (volumes Docker)

Volumes Docker vivem no daemon (nao na pasta do projeto), mas o compose
prefixa os nomes dos volumes com o nome do diretorio. Se voce moveu de
`agente-de-vendas\` para `IAprendo_Sales_Agent\`, o compose tentaria criar
novos volumes `iaprendo_sales_agent_*` em vez de reutilizar os existentes
`agente-de-vendas_*`.

Solucao — fixar o project name. Abra `docker-compose.yml` e garanta que
a linha 1 seja:

```yaml
name: agente-de-vendas

services:
  postgres:
    ...
```

Para verificar:
```bash
docker compose config | grep "^name:"
# deve retornar: name: agente-de-vendas

docker volume ls | grep agente-de-vendas
# deve listar: agente-de-vendas_evolution_pgdata
#              agente-de-vendas_evolution_redis
#              agente-de-vendas_evolution_instances
```

### 4. Recriar virtualenv

O venv tem paths absolutos em `Scripts\activate`, `pyvenv.cfg` e shebangs.
Mover a pasta quebra isso.

```cmd
cd C:\novo\caminho\do\projeto
rmdir /s /q venv
python -m venv venv
venv\Scripts\pip install --upgrade pip
venv\Scripts\pip install -r requirements-full.txt
```

Verificar:
```cmd
venv\Scripts\python.exe --version
venv\Scripts\python.exe -c "from config.settings import settings; print('Settings OK')"
```

### 5. Corrigir paths antigos em configs locais

Arquivos que contem paths absolutos:

#### `.claude/settings.local.json`
Tem permissoes regex com o path antigo. Use Find & Replace no editor.
Variantes a substituir (todas apontam para o caminho antigo):

- `/c/Users/.../agente-de-vendas` (forward slash, msys-style)
- `C:\\Users\\...\\agente-de-vendas` (Windows JSON-escaped)
- `C:/Users/.../agente-de-vendas` (forward slash Windows)
- `C:\\\\Users\\\\...\\\\agente-de-vendas` (duplo escape para `bash -c`)

Todas devem ir para o novo path na variante correspondente.

#### `scripts/create-shortcuts.ps1`
Linha 2 (`$ProjectPath = '...'`) — trocar para o novo caminho absoluto.

### 6. Preservar historico de sessoes Claude Code

Claude Code indexa conversas por path do projeto em
`C:\Users\<usuario>\.claude\projects\`. O nome da pasta e o path normalizado
(separadores `\` e `/` viram `-`, espacos viram `-`).

- Pasta antiga: `C--Users-...-agente-de-vendas`
- Pasta nova: `C--Dev-IAprendo-Sales-Agent`

Copiar `.jsonl` (sessoes) da antiga para a nova:

```bash
cp -n "/c/Users/Fernando Nienaber/.claude/projects/C--Users-...-agente-de-vendas/"*.jsonl \
      "/c/Users/Fernando Nienaber/.claude/projects/C--Dev-IAprendo-Sales-Agent/"
```

A flag `-n` (no-clobber) evita sobrescrever a sessao atual. Manter a pasta
antiga como backup — nao deletar.

### 7. Verificacao end-to-end

Ordem dos testes:

1. **venv**: `venv\Scripts\python.exe --version`
2. **Compose preservou nome**: `docker compose config | grep "^name:"` = `name: agente-de-vendas`
3. **Subir stack**: `docker compose up -d`
4. **Volumes existem e sao reutilizados**: `docker volume ls | grep agente-de-vendas` (3 linhas)
5. **Postgres nao recriou**: `docker logs evolution_postgres 2>&1 | grep "database system is ready"` (nao deve mostrar "initializing" de novo)
6. **Instancia WhatsApp**: abrir http://localhost:8080, login com API key, instancia `ialex` deve estar `CONNECTED` (sem pedir QR)
7. **Dashboard**: `start-dashboard.bat` -> http://localhost:8502 abre a Home com KPIs
8. **IAlex webhook**: `start-ialex.bat` -> log mostra "scheduler OK" + "webhook listening"
9. **Mensagem de teste**: enviar "oi IAlex" no WhatsApp -> resposta chega
10. **Historico Claude**: novo terminal Claude Code no projeto -> `/resume` lista conversas antigas

---

## Troubleshooting

### WhatsApp pede QR code novo
- Causa provavel: `name:` nao fixado no compose -> volumes criados com novo prefixo.
- Remedio: `docker compose down`, adicionar `name: agente-de-vendas` no compose,
  `docker compose up -d`. Se os volumes novos foram criados, voce pode
  delete-los (`docker volume rm iaprendo_sales_agent_*`) antes de subir com o nome certo.

### `venv\Scripts\python.exe` nao funciona (ModuleNotFoundError)
- Causa: venv ainda e o antigo com paths quebrados.
- Remedio: executar passo 4 (deletar e recriar venv).

### Dashboard abre mas "Settings OK" falha
- Causa: `.env` ausente ou chaves de API invalidas.
- Remedio: copiar `.env` da pasta antiga OU rodar `python setup_config.py` para regenerar.

### Claude Code nao lista conversas antigas no `/resume`
- Causa: `.jsonl` nao copiados para a pasta nova em `~/.claude/projects/`.
- Remedio: executar passo 6 (copiar `.jsonl`).

### `docker compose` reclama "volume ja existe mas nao esta em uso"
- Causa: existem dois sets de volumes (antigo nome e novo nome).
- Remedio: escolher um. Para manter sessao -> fixar `name:` no compose e deletar volumes
  do prefixo errado. Se nao liga para historico -> `docker compose down -v` e subir limpo.

### Atalhos do Desktop abrem pasta errada
- Causa: `scripts/create-shortcuts.ps1` tinha path antigo na hora da criacao.
- Remedio: atualizar `$ProjectPath` no script e rodar novamente em PowerShell:
  `powershell -ExecutionPolicy Bypass -File scripts\create-shortcuts.ps1`

---

## Arquivos que contem paths absolutos (auditoria)

Use este grep quando mudar de local, para garantir que nao ficou nada:

```bash
grep -r "C:\\\\" --include=*.json --include=*.ps1 --include=*.py --exclude-dir=venv --exclude-dir=node_modules .
grep -r "/c/Users" --include=*.json --include=*.ps1 --include=*.py --exclude-dir=venv --exclude-dir=node_modules .
```

Expectativa: 0 resultados apos a mudanca (exceto comentarios ou docs).
