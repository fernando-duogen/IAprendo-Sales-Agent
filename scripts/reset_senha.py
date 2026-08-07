#!/usr/bin/env python
"""Reseta a senha de login do PAINEL (streamlit-authenticator), de forma segura.

A senha nova e digitada AQUI, no seu terminal, OCULTA — nunca sai da sua maquina
e nunca aparece em texto. As senhas ficam guardadas como HASH (irreversivel), por
isso nao da pra "lembrar" a antiga; o jeito certo e resetar.

Uso (na pasta do projeto C:\\Dev\\IAprendo_Sales_Agent):

    venv\\Scripts\\python.exe scripts\\reset_senha.py

Atualiza o login LOCAL (config/users.yaml) e imprime o bloco pra colar nos
Secrets do Streamlit Cloud (login do painel ONLINE).
"""
import getpass
import shutil
import sys
from pathlib import Path

import yaml
import streamlit_authenticator as stauth

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "users.yaml"


def _hash(pw: str) -> str:
    h = stauth.Hasher.hash(pw)
    return h[0] if isinstance(h, list) else h


def main() -> int:
    if not CFG.exists():
        print(f"[ERRO] Nao encontrei {CFG}")
        return 1

    data = yaml.safe_load(CFG.read_text(encoding="utf-8"))
    users = (data.get("credentials") or {}).get("usernames") or {}
    if not users:
        print("[ERRO] users.yaml sem usuarios.")
        return 1

    print("Usuarios disponiveis:", ", ".join(users.keys()))
    u = input("Qual usuario resetar? (ex: fernando) ").strip().lower()
    if u not in users:
        print(f"[ERRO] '{u}' nao existe. Opcoes: {list(users.keys())}")
        return 1

    p1 = getpass.getpass("Nova senha (nao aparece na tela): ")
    p2 = getpass.getpass("Repita a nova senha: ")
    if p1 != p2:
        print("[ERRO] As senhas nao batem. Rode de novo.")
        return 1
    if len(p1) < 6:
        print("[ERRO] Use pelo menos 6 caracteres.")
        return 1

    new_hash = _hash(p1)

    # Backup antes de escrever
    shutil.copy2(CFG, CFG.with_suffix(".yaml.bak"))
    users[u]["password"] = new_hash
    users[u]["failed_login_attempts"] = 0   # destrava se tinha bloqueado
    users[u]["logged_in"] = False
    CFG.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")

    print(f"\n[OK] Senha de '{u}' atualizada em config/users.yaml "
          f"(backup salvo em users.yaml.bak).")
    print("     -> O login LOCAL (streamlit run) ja funciona com a senha nova.")
    print("\n================= PAINEL ONLINE (Streamlit Cloud) =================")
    print("O painel online NAO usa o users.yaml — usa os Secrets do Cloud.")
    print("Passos:")
    print("  1. Abra seu app em share.streamlit.io -> Settings -> Secrets")
    print(f"  2. Ache o bloco [auth.credentials.usernames.{u}]")
    print("  3. Troque SO a linha 'password' por esta (mantenha o resto):\n")
    print(f'      password = "{new_hash}"\n')
    print("  4. Salve. O login online passa a valer a senha nova.")
    print("===================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
