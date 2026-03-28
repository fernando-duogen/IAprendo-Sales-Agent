"""
EmailDeducer - Deducao inteligente de emails pessoais.

Quando encontramos 1 email pessoal de uma escola (ex: fernanda.radajeski@joaoxxiii.com),
deduzimos o padrao e aplicamos para outros contatos da mesma escola.

Padroes comuns em escolas brasileiras:
  - nome.sobrenome@dominio (mais comum)
  - nome@dominio
  - primeironome.ultimosobrenome@dominio
  - iniciais@dominio (raro)
"""
import re
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from unidecode import unidecode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.supabase_client import db
from utils.logger import logger


# Emails que NAO sao pessoais (departamentos)
GENERIC_PREFIXES = {
    "contato", "falecom", "faleconosco", "atendimento", "sac",
    "secretaria", "secretariaescolar", "financeiro", "financeira",
    "comunicacao", "comunicacoes", "marketing", "rh", "curriculos",
    "direcao", "coordenacao", "pedagogico", "pedagogica",
    "ti", "suporte", "info", "adm", "administrativo",
    "bolsas", "filantropia", "fundacao", "sec", "admin",
    "noreply", "no-reply", "naoresponda", "eventos",
    "matricula", "matriculas", "inscricao", "inscricoes",
    "talentos", "vagas", "trabalhe", "ouvidoria",
    "compras", "comercial", "vendas", "biblioteca",
    "descontosolidario", "desconto",
}


def is_personal_email(email: str) -> bool:
    """Verifica se um email parece ser pessoal (nao de departamento)."""
    if not email or "@" not in email:
        return False
    prefix = email.split("@")[0].lower().replace(".", "").replace("_", "").replace("-", "")
    # Checar se e generico
    for gp in GENERIC_PREFIXES:
        if prefix == gp or prefix.startswith(gp):
            return False
    # Checar se tem pelo menos 2 caracteres e parece nome
    if len(prefix) < 3:
        return False
    # Se tem numeros no meio, provavelmente nao e pessoal
    if re.search(r"\d{3,}", prefix):
        return False
    return True


def extract_domain(email: str) -> str:
    """Extrai dominio de um email."""
    if "@" in email:
        return email.split("@")[1].lower()
    return ""


def detect_pattern(name: str, email: str) -> Optional[str]:
    """
    Detecta o padrao usado para gerar o email a partir do nome.
    Retorna o padrao ou None se nao conseguir detectar.

    Padroes possiveis:
    - 'nome.sobrenome' -> fernanda.radajeski@...
    - 'nome_sobrenome' -> fernanda_radajeski@...
    - 'nome-sobrenome' -> fernanda-radajeski@...
    - 'nome' -> fernanda@...
    - 'nsobrenome' -> fradajeski@...
    - 'nomesobrenome' -> fernandaradajeski@...
    - 'sobrenome.nome' -> radajeski.fernanda@...
    """
    if not name or not email or "@" not in email:
        return None

    prefix = email.split("@")[0].lower()
    name_clean = unidecode(name.lower().strip())
    parts = name_clean.split()

    if len(parts) < 2:
        return None

    first = parts[0]
    last = parts[-1]
    # Remover preposicoes comuns
    middle_parts = [p for p in parts[1:-1] if p not in ("de", "da", "do", "das", "dos", "e")]

    # Testar padroes
    patterns = [
        ("nome.sobrenome", f"{first}.{last}"),
        ("nome_sobrenome", f"{first}_{last}"),
        ("nome-sobrenome", f"{first}-{last}"),
        ("nome", first),
        ("nomesobrenome", f"{first}{last}"),
        ("sobrenome.nome", f"{last}.{first}"),
        ("inicial.sobrenome", f"{first[0]}.{last}"),
        ("inicialsobrenome", f"{first[0]}{last}"),
    ]

    # Se tem nome do meio, testar tambem com ele
    if middle_parts:
        patterns.extend([
            ("nome.meio.sobrenome", f"{first}.{middle_parts[0]}.{last}"),
            ("nome.meiosobrenome", f"{first}.{''.join(middle_parts)}{last}"),
        ])

    for pattern_name, expected in patterns:
        if prefix == expected:
            return pattern_name

    # Tentar match parcial (ex: carol = carolina)
    if last in prefix and len(prefix) > len(last):
        # O prefixo contem o sobrenome + algo mais (provavelmente apelido)
        return "apelido.sobrenome"

    return None


def apply_pattern(name: str, pattern: str, domain: str) -> Optional[str]:
    """Aplica um padrao detectado a um nome para gerar email."""
    if not name or not pattern or not domain:
        return None

    name_clean = unidecode(name.lower().strip())
    parts = name_clean.split()

    if len(parts) < 2:
        return None

    first = parts[0]
    last = parts[-1]
    middle_parts = [p for p in parts[1:-1] if p not in ("de", "da", "do", "das", "dos", "e")]

    generators = {
        "nome.sobrenome": lambda: f"{first}.{last}",
        "nome_sobrenome": lambda: f"{first}_{last}",
        "nome-sobrenome": lambda: f"{first}-{last}",
        "nome": lambda: first,
        "nomesobrenome": lambda: f"{first}{last}",
        "sobrenome.nome": lambda: f"{last}.{first}",
        "inicial.sobrenome": lambda: f"{first[0]}.{last}",
        "inicialsobrenome": lambda: f"{first[0]}{last}",
        "nome.meio.sobrenome": lambda: f"{first}.{middle_parts[0]}.{last}" if middle_parts else f"{first}.{last}",
    }

    gen = generators.get(pattern)
    if gen:
        prefix = gen()
        return f"{prefix}@{domain}"
    return None


def analyze_company_emails(company_id: str) -> Dict[str, Any]:
    """
    Analisa os emails existentes de uma empresa para detectar padroes.
    Retorna o padrao detectado e dominio.
    """
    try:
        contacts = db.client.table("contacts").select("*").eq("company_id", company_id).execute().data or []
    except Exception:
        return {"pattern": None, "domain": None, "personal_emails": 0}

    personal_emails = []
    domains = {}

    for ct in contacts:
        email = ct.get("email", "")
        if email and is_personal_email(email):
            domain = extract_domain(email)
            domains[domain] = domains.get(domain, 0) + 1
            personal_emails.append({
                "name": ct.get("full_name", ""),
                "email": email,
                "domain": domain,
            })

    if not personal_emails:
        # Tentar extrair dominio dos emails genericos
        for ct in contacts:
            email = ct.get("email", "")
            if email and "@" in email:
                domain = extract_domain(email)
                # Ignorar dominios genericos (gmail, hotmail, etc)
                if domain and not any(g in domain for g in ["gmail", "hotmail", "outlook", "yahoo", "live"]):
                    domains[domain] = domains.get(domain, 0) + 1

        main_domain = max(domains, key=domains.get) if domains else None
        return {
            "pattern": None,
            "domain": main_domain,
            "personal_emails": 0,
            "suggested_patterns": ["nome.sobrenome"] if main_domain else [],
        }

    # Detectar padrao mais comum
    main_domain = max(domains, key=domains.get)
    patterns_found = {}

    for pe in personal_emails:
        if pe["domain"] == main_domain:
            pattern = detect_pattern(pe["name"], pe["email"])
            if pattern:
                patterns_found[pattern] = patterns_found.get(pattern, 0) + 1

    main_pattern = max(patterns_found, key=patterns_found.get) if patterns_found else "nome.sobrenome"

    return {
        "pattern": main_pattern,
        "domain": main_domain,
        "personal_emails": len(personal_emails),
        "patterns_found": patterns_found,
    }


def deduce_emails_for_company(company_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Deduz emails para contatos sem email de uma empresa.
    Usa o padrao detectado dos emails existentes.

    Args:
        company_id: ID da empresa
        dry_run: Se True, nao salva no banco (apenas mostra o que faria)

    Returns:
        Dict com resultados: deduced (lista), pattern, domain
    """
    analysis = analyze_company_emails(company_id)

    pattern = analysis.get("pattern")
    domain = analysis.get("domain")

    if not domain:
        return {"deduced": [], "error": "Nenhum dominio encontrado", "pattern": None}

    if not pattern:
        # Usar padrao mais comum como fallback
        pattern = "nome.sobrenome"

    # Buscar contatos sem email
    try:
        contacts = db.client.table("contacts").select("*").eq("company_id", company_id).execute().data or []
    except Exception as e:
        return {"deduced": [], "error": str(e), "pattern": pattern}

    deduced = []
    for ct in contacts:
        # Pular contatos que ja tem email ou sao departamentos
        if ct.get("email"):
            continue
        name = ct.get("full_name", "")
        if not name or len(name.split()) < 2:
            continue
        # Pular nomes que sao cargos/departamentos
        lower_name = name.lower()
        if any(kw in lower_name for kw in ["secretaria", "financeiro", "comunicacao", "departamento", "setor", "ti ", "rh "]):
            continue

        email = apply_pattern(name, pattern, domain)
        if email:
            deduced.append({
                "contact_id": ct["id"],
                "name": name,
                "role": ct.get("role", ""),
                "deduced_email": email,
                "pattern": pattern,
                "confidence": 65,  # Deduzido, nao confirmado
            })

    # Salvar no banco se nao for dry_run
    if not dry_run and deduced:
        saved = 0
        for d in deduced:
            try:
                db.client.table("contacts").update({
                    "email": d["deduced_email"],
                    "email_deduced": True,
                    "email_verified": False,
                    "confidence_score": d["confidence"],
                    "source": f"deduced:{pattern}",
                }).eq("id", d["contact_id"]).execute()
                saved += 1
                logger.info("Email deduzido", extra={
                    "contact": d["name"],
                    "email": d["deduced_email"],
                    "pattern": pattern,
                })
            except Exception as e:
                logger.error("Erro ao salvar email deduzido", extra={"error": str(e)})
        deduced_result = {"saved": saved}
    else:
        deduced_result = {"saved": 0}

    # Salvar padrao e dominio na empresa
    if not dry_run:
        try:
            db.client.table("companies").update({
                "email_pattern": pattern,
                "email_domain": domain,
            }).eq("id", company_id).execute()
        except Exception:
            pass

    return {
        "deduced": deduced,
        "pattern": pattern,
        "domain": domain,
        "personal_emails_found": analysis.get("personal_emails", 0),
        **deduced_result,
    }


def deduce_all_pending(dry_run: bool = False) -> Dict[str, Any]:
    """
    Deduz emails para TODAS as empresas que tem contatos sem email
    mas tem pelo menos 1 email pessoal (para detectar o padrao).
    """
    try:
        companies = db.client.table("companies").select("id,name").execute().data or []
    except Exception as e:
        return {"error": str(e)}

    results = {"total_companies": 0, "total_deduced": 0, "details": []}

    for comp in companies:
        result = deduce_emails_for_company(comp["id"], dry_run=dry_run)
        if result.get("deduced"):
            results["total_companies"] += 1
            results["total_deduced"] += len(result["deduced"])
            results["details"].append({
                "company": comp.get("name", comp["id"]),
                "pattern": result["pattern"],
                "domain": result["domain"],
                "deduced_count": len(result["deduced"]),
                "emails": [d["deduced_email"] for d in result["deduced"]],
            })

    return results


# Singleton-like
email_deducer = type("EmailDeducer", (), {
    "analyze": staticmethod(analyze_company_emails),
    "deduce_for_company": staticmethod(deduce_emails_for_company),
    "deduce_all": staticmethod(deduce_all_pending),
    "detect_pattern": staticmethod(detect_pattern),
    "apply_pattern": staticmethod(apply_pattern),
    "is_personal": staticmethod(is_personal_email),
})()
