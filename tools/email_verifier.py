"""
Email Verifier - Verifica se emails existem antes de enviar.

Usa Hunter.io Verify API (gratuito ate 25/mes) e fallback com SMTP check.

Estrategia em cascata:
1. Hunter.io Email Verifier API (mais confiavel, 25 verificacoes/mes gratis)
2. SMTP check via MX record (fallback gratuito, menos confiavel)

Usage:
    from tools.email_verifier import email_verifier

    # Verificar um email
    result = email_verifier.verify_email("contato@escola.com.br")
    # {"email": "...", "valid": True, "score": 92, "source": "hunter", "details": "deliverable"}

    # Verificar lote
    results = email_verifier.verify_batch(["a@x.com", "b@y.com"])

    # Verificar todos contatos de uma empresa
    summary = email_verifier.verify_company_contacts("company-uuid")

    # Checar cota restante do Hunter
    quota = email_verifier.get_quota()
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import time
import socket
import smtplib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import requests

from database.supabase_client import db
from utils.logger import logger
from config.settings import settings


class EmailVerifier:
    """Verifica se enderecos de email sao validos e entregaveis.

    Usa Hunter.io Verify API como fonte primaria e SMTP check como fallback.
    Atualiza a tabela de contatos no Supabase com resultado da verificacao.
    """

    HUNTER_BASE_URL = "https://api.hunter.io/v2"
    SMTP_TIMEOUT = 10
    RATE_LIMIT_DELAY = 1.0  # segundos entre chamadas Hunter

    def __init__(self) -> None:
        """Inicializa verifier com API key do Hunter.io."""
        self.api_key: str = (
            getattr(settings, "HUNTER_API_KEY", "") or os.getenv("HUNTER_API_KEY", "")
        )
        self._hunter_available: bool = bool(self.api_key)
        if not self._hunter_available:
            logger.info(
                "HUNTER_API_KEY nao configurada - usando apenas SMTP check (menos confiavel)"
            )

    # ========================================================================
    # VALIDACAO DE FORMATO
    # ========================================================================

    @staticmethod
    def _is_valid_format(email: str) -> bool:
        """Verifica se o email tem formato valido (regex basico).

        Args:
            email: Endereco de email para validar.

        Returns:
            True se o formato e valido.
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email.strip()))

    # ========================================================================
    # HUNTER.IO VERIFY API
    # ========================================================================

    def _verify_via_hunter(self, email: str) -> Optional[Dict[str, Any]]:
        """Verifica email usando Hunter.io Email Verifier API.

        Args:
            email: Endereco de email para verificar.

        Returns:
            Resultado da verificacao ou None se indisponivel.
            Formato: {"valid": bool, "score": int, "source": "hunter", "details": str}
        """
        if not self._hunter_available:
            return None

        try:
            resp = requests.get(
                f"{self.HUNTER_BASE_URL}/email-verifier",
                params={
                    "email": email,
                    "api_key": self.api_key,
                },
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                result_status = data.get("result", "unknown")
                score = data.get("score", 0)

                valid = result_status in ("deliverable",)
                details = result_status  # deliverable, undeliverable, risky, unknown

                logger.info(
                    "Hunter Verify: verificacao concluida",
                    extra={
                        "email": email,
                        "result": result_status,
                        "score": score,
                    },
                )

                return {
                    "valid": valid,
                    "score": score,
                    "source": "hunter",
                    "details": details,
                }

            elif resp.status_code == 429:
                logger.warning("Hunter Verify: cota mensal esgotada")
                self._hunter_available = False
            elif resp.status_code == 401:
                logger.warning("Hunter Verify: API key invalida")
                self._hunter_available = False
            else:
                logger.warning(
                    "Hunter Verify: resposta inesperada",
                    extra={"status": resp.status_code, "email": email},
                )

        except requests.exceptions.Timeout:
            logger.warning("Hunter Verify: timeout", extra={"email": email})
        except Exception as e:
            logger.error(
                "Hunter Verify: erro inesperado",
                extra={"error": str(e), "email": email},
            )

        return None

    # ========================================================================
    # SMTP CHECK (FALLBACK)
    # ========================================================================

    def _get_mx_host(self, domain: str) -> Optional[str]:
        """Resolve o MX record de um dominio.

        Args:
            domain: Dominio do email (ex: escola.com.br).

        Returns:
            Hostname do servidor MX ou None.
        """
        try:
            import dns.resolver

            answers = dns.resolver.resolve(domain, "MX")
            # Pega o MX com menor prioridade (maior preferencia)
            mx_records = sorted(answers, key=lambda r: r.preference)
            if mx_records:
                return str(mx_records[0].exchange).rstrip(".")
        except ImportError:
            # dnspython nao instalado - tenta MX via socket
            logger.debug("dnspython nao disponivel - tentando fallback para SMTP check")
        except Exception as e:
            logger.debug(f"Falha ao resolver MX para {domain}: {e}")

        return None

    def _verify_via_smtp(self, email: str) -> Dict[str, Any]:
        """Verifica email via SMTP RCPT TO check.

        Conecta ao servidor MX do dominio e testa se o endereco e aceito.
        Menos confiavel que Hunter pois muitos servidores aceitam qualquer endereco.

        Args:
            email: Endereco de email para verificar.

        Returns:
            Resultado: {"valid": bool, "score": int, "source": "smtp", "details": str}
        """
        domain = email.split("@")[1]

        # Resolve MX
        mx_host = self._get_mx_host(domain)
        if not mx_host:
            # Sem MX, tenta o proprio dominio como fallback
            mx_host = domain

        try:
            smtp = smtplib.SMTP(timeout=self.SMTP_TIMEOUT)
            smtp.connect(mx_host, 25)
            smtp.helo("verify.local")
            smtp.mail("verify@verify.local")
            code, _msg = smtp.rcpt(email)
            smtp.quit()

            if code == 250:
                return {
                    "valid": True,
                    "score": 60,  # Score menor pois SMTP e menos confiavel
                    "source": "smtp",
                    "details": "accepted_by_mx",
                }
            else:
                return {
                    "valid": False,
                    "score": 10,
                    "source": "smtp",
                    "details": f"rejected_code_{code}",
                }

        except smtplib.SMTPServerDisconnected:
            return {
                "valid": False,
                "score": 0,
                "source": "smtp",
                "details": "server_disconnected",
            }
        except (socket.timeout, socket.gaierror, OSError) as e:
            logger.debug(f"SMTP check falhou para {email}: {e}")
            return {
                "valid": False,
                "score": 0,
                "source": "smtp",
                "details": f"connection_failed: {type(e).__name__}",
            }
        except Exception as e:
            logger.debug(f"SMTP check erro inesperado para {email}: {e}")
            return {
                "valid": False,
                "score": 0,
                "source": "smtp",
                "details": f"error: {type(e).__name__}",
            }

    # ========================================================================
    # API PUBLICA
    # ========================================================================

    def verify_email(self, email: str) -> Dict[str, Any]:
        """Verifica se um email existe e e entregavel.

        Tenta Hunter.io primeiro, depois fallback para SMTP check.

        Args:
            email: Endereco de email para verificar.

        Returns:
            Dicionario com resultado:
            {
                "email": str,
                "valid": bool,
                "score": int (0-100),
                "source": str ("hunter" ou "smtp"),
                "details": str (ex: "deliverable", "undeliverable", "risky")
            }
        """
        email = email.strip().lower()

        # Validacao de formato basica
        if not self._is_valid_format(email):
            return {
                "email": email,
                "valid": False,
                "score": 0,
                "source": "format_check",
                "details": "invalid_format",
            }

        # Tentativa 1: Hunter.io Verify API
        hunter_result = self._verify_via_hunter(email)
        if hunter_result is not None:
            return {"email": email, **hunter_result}

        # Tentativa 2: SMTP check (fallback)
        smtp_result = self._verify_via_smtp(email)
        return {"email": email, **smtp_result}

    def verify_batch(self, emails: List[str]) -> List[Dict[str, Any]]:
        """Verifica multiplos emails com rate limiting.

        Aplica delay de 1 segundo entre chamadas Hunter para respeitar rate limit.

        Args:
            emails: Lista de enderecos de email.

        Returns:
            Lista de resultados de verificacao (mesma ordem da entrada).
        """
        results: List[Dict[str, Any]] = []

        for i, email in enumerate(emails):
            result = self.verify_email(email)
            results.append(result)

            # Rate limiting entre chamadas (exceto ultima)
            if i < len(emails) - 1 and result.get("source") == "hunter":
                time.sleep(self.RATE_LIMIT_DELAY)

        valid_count = sum(1 for r in results if r.get("valid"))
        logger.info(
            "Verificacao em lote concluida",
            extra={
                "total": len(emails),
                "valid": valid_count,
                "invalid": len(emails) - valid_count,
            },
        )

        return results

    def verify_company_contacts(self, company_id: str) -> Dict[str, Any]:
        """Verifica todos os contatos nao-verificados de uma empresa.

        Busca contatos com email preenchido mas email_verified=False,
        verifica cada um e atualiza a tabela contacts no Supabase.

        Args:
            company_id: UUID da empresa na tabela companies.

        Returns:
            Resumo: {
                "company_id": str,
                "total": int,
                "verified_valid": int,
                "verified_invalid": int,
                "errors": int
            }
        """
        summary: Dict[str, Any] = {
            "company_id": company_id,
            "total": 0,
            "verified_valid": 0,
            "verified_invalid": 0,
            "errors": 0,
        }

        try:
            # Busca contatos nao verificados com email preenchido
            response = (
                db.client.table("contacts")
                .select("id, email")
                .eq("company_id", company_id)
                .eq("email_verified", False)
                .neq("email", "")
                .not_.is_("email", "null")
                .execute()
            )

            contacts = response.data or []
            summary["total"] = len(contacts)

            if not contacts:
                logger.debug(
                    f"Nenhum contato para verificar na empresa {company_id}"
                )
                return summary

            logger.info(
                f"Verificando {len(contacts)} contatos da empresa {company_id}"
            )

            for contact in contacts:
                contact_id: str = contact["id"]
                email: str = contact["email"]

                try:
                    result = self.verify_email(email)
                    is_valid = result.get("valid", False)

                    # Atualiza contato no Supabase
                    now_iso = datetime.now(timezone.utc).isoformat()
                    db.client.table("contacts").update({
                        "email_verified": is_valid,
                        "email_verified_at": now_iso,
                    }).eq("id", contact_id).execute()

                    if is_valid:
                        summary["verified_valid"] += 1
                    else:
                        summary["verified_invalid"] += 1

                    # Rate limiting
                    if result.get("source") == "hunter":
                        time.sleep(self.RATE_LIMIT_DELAY)

                except Exception as e:
                    logger.error(
                        "Erro ao verificar contato",
                        extra={
                            "contact_id": contact_id,
                            "email": email,
                            "error": str(e),
                        },
                    )
                    summary["errors"] += 1

            logger.info(
                "Verificacao de contatos concluida",
                extra=summary,
            )

        except Exception as e:
            logger.error(
                "Erro ao buscar contatos para verificacao",
                extra={"company_id": company_id, "error": str(e)},
            )
            summary["errors"] += 1

        return summary

    def get_quota(self) -> Dict[str, Any]:
        """Verifica cota restante de verificacoes no Hunter.io.

        Returns:
            Dicionario com informacoes de cota:
            {
                "available": bool,
                "used": int,
                "remaining": int,
                "resets_at": str (ISO date)
            }
        """
        if not self._hunter_available:
            return {
                "available": False,
                "used": 0,
                "remaining": 0,
                "resets_at": "",
            }

        try:
            resp = requests.get(
                f"{self.HUNTER_BASE_URL}/account",
                params={"api_key": self.api_key},
                timeout=10,
            )

            if resp.status_code == 200:
                data = resp.json().get("data", {})
                requests_info = data.get("requests", {})
                verifications = requests_info.get("verifications", {})

                used = verifications.get("used", 0)
                available_total = verifications.get("available", 0)
                remaining = max(0, available_total - used)
                resets_at = data.get("reset_date", "")

                logger.info(
                    "Hunter cota consultada",
                    extra={
                        "used": used,
                        "remaining": remaining,
                        "resets_at": resets_at,
                    },
                )

                return {
                    "available": True,
                    "used": used,
                    "remaining": remaining,
                    "resets_at": resets_at,
                }

            else:
                logger.warning(
                    "Hunter: falha ao consultar cota",
                    extra={"status": resp.status_code},
                )

        except Exception as e:
            logger.error("Hunter: erro ao consultar cota", extra={"error": str(e)})

        return {
            "available": False,
            "used": 0,
            "remaining": 0,
            "resets_at": "",
        }


# Singleton
email_verifier = EmailVerifier()
