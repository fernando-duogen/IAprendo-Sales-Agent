"""
WriterAgent - Gera mensagens hiperpersonalizadas usando Claude Sonnet
ou aplica template padrao com substituicao de variaveis.

CRITICO: Toda mensagem vai para approval_queue antes de qualquer envio.
Nunca envia diretamente.

Modos:
  ai       - Claude Sonnet gera mensagem do zero (custo API)
  template - Mensagem padrao do usuario, so variaveis substituidas (custo zero)
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from database.supabase_client import db
from config.settings import settings
from utils.logger import logger
from utils.template_renderer import render_template

NEWLINE = chr(10)
TRIPLE_BACKTICK = chr(96) * 3

# Ranking de confiabilidade de source
_SOURCE_RANK = {"manual": 0, "apollo": 1, "hunter": 2, "snov": 3, "web_scraping": 4, "email_pattern": 5, "placeholder": 6}

class WriterAgent(BaseAgent):
    """Gera mensagens hiperpersonalizadas ou aplica template padrao.
    CRITICO: Toda mensagem vai para approval_queue.
    NUNCA envia diretamente sem aprovacao humana.
    """

    def __init__(self) -> None:
        super().__init__(agent_name="writer")
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "email_writer_prompt.txt"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("Prompt de escrita nao encontrado", extra={"path": str(prompt_path)})
            raise

    # =========================================================================
    # Selecao inteligente de contato (Mapa de Poder)
    # =========================================================================

    def _select_best_contact(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Seleciona o melhor contato por prioridade de decisor.

        Ordem: com email primeiro, depois por outreach_priority (1=diretor),
        depois por confiabilidade da source.
        """
        if not contacts:
            return self._create_placeholder_contact_dict()

        def sort_key(c: Dict[str, Any]) -> tuple:
            has_email = 0 if c.get("email") else 1
            priority = c.get("outreach_priority", 99)
            source_rank = _SOURCE_RANK.get(c.get("source", ""), 5)
            return (has_email, priority, source_rank)

        return sorted(contacts, key=sort_key)[0]

    def _create_placeholder_contact_dict(self) -> Dict[str, Any]:
        """Cria dict de contato placeholder (sem salvar no banco)."""
        return {"id": None, "full_name": None, "role": "Diretor(a)", "email": None,
                "linkedin_url": None, "source": "placeholder",
                "decision_maker_type": "diretor", "outreach_priority": 1}

    # =========================================================================
    # Execute: modo IA ou template
    # =========================================================================

    def execute(self, companies: List[Dict[str, Any]], mode: str = "ai",
                template_id: Optional[str] = None, **kwargs: Any) -> List[Dict[str, Any]]:
        """Gera mensagens. Coloca na approval_queue (NUNCA envia direto).

        Args:
            companies: Lista de escolas.
            mode: "ai" para Claude Sonnet, "template" para mensagem padrao.
            template_id: UUID do template (se mode=template). Se None, usa default.
        """
        if mode == "ai" and not self._check_rate_limit("anthropic"):
            logger.warning("Rate limit Anthropic atingido, abortando escrita")
            return []

        # Carregar template se modo template
        template_data = None
        if mode == "template":
            template_data = self._load_message_template(template_id)
            if not template_data:
                logger.error("Template nao encontrado, abortando")
                return []

        results: List[Dict[str, Any]] = []
        skipped = 0
        for company in companies:
            try:
                company_id = company.get("id")

                # Anti-duplicata: pular se ja tem mensagem pendente ou aprovada na fila
                if company_id and self._has_pending_message(company_id):
                    skipped += 1
                    logger.info("Pulando escola (ja tem mensagem pendente/aprovada)",
                        extra={"company_id": company_id, "school_name": company.get("name")})
                    continue

                contacts = db.get_contacts_by_company(company_id) if company_id else []
                contact = self._select_best_contact(contacts)

                if mode == "ai":
                    result = self.write_message(company, contact, all_contacts=contacts)
                else:
                    result = self._apply_template(template_data, company, contact)

                if result:
                    results.append(result)
            except Exception as e:
                logger.error("Erro ao gerar mensagem",
                    extra={"company_id": company.get("id"), "school_name": company.get("name"), "error": str(e)})
        if skipped:
            logger.info("Escolas puladas (anti-duplicata)", extra={"skipped": skipped})
        logger.info("Geracao concluida",
            extra={"total": len(companies), "generated": len(results), "mode": mode})
        return results

    # =========================================================================
    # Modo IA (Claude Sonnet)
    # =========================================================================

    def _get_rag_examples_section(self, company: Dict[str, Any], contact: Optional[Dict[str, Any]]) -> str:
        """Busca emails bem-sucedidos passados e formata como exemplos para o prompt."""
        try:
            from integrations.email_rag import email_rag
            context = {
                "school_size": company.get("school_size"),
                "admin_category": company.get("admin_category"),
                "city": company.get("city"),
                "state": company.get("state"),
            }
            if contact:
                context["decision_maker_type"] = contact.get("decision_maker_type")
            examples = email_rag.get_successful_examples(
                limit=3,
                company_context=context,
                exclude_company_id=company.get("id"),
            )
            if examples:
                logger.info(
                    "RAG: usando exemplos no writer",
                    extra={"n_examples": len(examples), "school": company.get("name")},
                )
                return email_rag.format_for_prompt(examples)
            return ""
        except Exception as e:
            logger.debug(f"RAG writer skip: {e}")
            return ""

    def write_message(self, company: Dict[str, Any], contact: Optional[Dict[str, Any]] = None,
                      all_contacts: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """Gera mensagem personalizada via Claude. Resultado vai para approval_queue."""
        company_id = company.get("id")
        school_name = company.get("name", "Desconhecida")
        logger.info("Gerando mensagem (IA)", extra={"company_id": company_id, "school_name": school_name})

        # RAG: buscar exemplos de emails que funcionaram
        examples_section = self._get_rag_examples_section(company, contact)

        # Remetente ativo (multi-user): dashboard logado OU IAlex thread-local OU fallback YOUR_*
        from utils.sender_profile import get_active_sender
        _sender = get_active_sender()
        prompt = (
            self.prompt_template
            .replace("{examples}", examples_section)
            .replace("{school_data}", self._format_school_section(company))
            .replace("{contact_data}", self._format_contact_section(contact, all_contacts))
            .replace("{qualification_data}", self._format_qualification_section(company))
            .replace("{sender_info}", self._format_sender_section())
            .replace("{sender_name}", _sender.get("name") or settings.YOUR_NAME)
            .replace("{sender_email}", _sender.get("email") or settings.YOUR_EMAIL)
            .replace("{company_name}", getattr(settings, "COMPANY_NAME", "IAprendo"))
            .replace("{website}", getattr(settings, "COMPANY_WEBSITE", ""))
            .replace("{meeting_link}", getattr(settings, "HUBSPOT_MEETING_LINK", ""))
        )
        response_text = self._call_claude(prompt=prompt, model="quality", max_tokens=1024)
        parsed = self._parse_response(response_text, company_id)
        if not parsed:
            return None
        queue_id = self._add_to_approval_queue(
            company_id=company_id,
            contact_id=contact.get("id") if contact else None,
            subject=parsed["subject"], body=parsed["body"])
        if not queue_id:
            return None
        logger.info("Mensagem na fila (IA)", extra={"company_id": company_id, "queue_id": queue_id})
        return {"company_id": company_id, "company_name": school_name, "queue_id": queue_id,
            "subject": parsed["subject"],
            "body_preview": parsed["body"][:150]+"..." if len(parsed["body"])>150 else parsed["body"],
            "reasoning": parsed.get("reasoning", ""), "mode": "ai"}

    # =========================================================================
    # Modo Template (mensagem padrao)
    # =========================================================================

    def _load_message_template(self, template_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Carrega template do banco. Se template_id=None, usa o default ativo."""
        try:
            if template_id:
                result = db.client.table("message_templates").select("*").eq("id", template_id).single().execute()
                return result.data if result.data else None
            else:
                # Buscar default ativo
                result = db.client.table("message_templates").select("*").eq("is_active", True).eq("is_default", True).limit(1).execute()
                if result.data:
                    return result.data[0]
                # Fallback: primeiro ativo
                result = db.client.table("message_templates").select("*").eq("is_active", True).limit(1).execute()
                return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Erro ao carregar template", extra={"template_id": template_id, "error": str(e)})
            return None

    def _apply_template(self, template_data: Dict[str, Any], company: Dict[str, Any],
                        contact: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Aplica template padrao com substituicao de variaveis.

        Se o template usa variaveis de graficos ({chart_radar}, {chart_gap},
        {chart_trend}, {report_link}), gera os graficos e report automaticamente
        antes de substituir. Custo zero de API (sem LLM), mas pode demorar
        ~30s por escola se precisar gerar graficos (Plotly + upload Supabase).
        """
        import json as _json

        company_id = company.get("id")
        school_name = company.get("name", "Desconhecida")
        logger.info("Aplicando template", extra={"company_id": company_id, "template": template_data.get("name")})

        body_tpl = template_data.get("body_template") or ""
        chart_vars = ["{chart_radar}", "{chart_gap}", "{chart_trend}", "{report_link}"]
        needs_charts = any(v in body_tpl for v in chart_vars)

        # Gerar graficos e report se template usa variaveis (best-effort)
        extra_vars: Dict[str, str] = {}
        chart_urls_list: List[Dict[str, str]] = []
        if needs_charts:
            inep = company.get("inep_code")
            if inep:
                # Graficos
                try:
                    from tools.insight_charts import generate_all_relevant_charts
                    from database.supabase_client import db as _db
                    charts = generate_all_relevant_charts(str(inep))
                    for ch in charts:
                        url = _db.upload_chart(ch["filename"], ch["bytes"])
                        if url:
                            chart_urls_list.append({"type": ch["type"], "url": url, "alt": ch.get("alt", "")})
                            _img_style = ('style="width:100%;max-width:560px;display:block;'
                                         'margin:0 auto;border-radius:8px"')
                            _src_tag = (f'<div style="text-align:center;margin:16px 0">'
                                        f'<img src="{url}" alt="{ch.get("alt", "")}" {_img_style} />'
                                        f'<p style="color:#999;font-size:11px;margin-top:4px">'
                                        f'Fonte: ENEM 2024 / Censo Escolar (INEP)</p></div>')
                            if ch["type"] == "radar":
                                extra_vars["chart_radar"] = _src_tag
                            elif ch["type"] == "gap":
                                extra_vars["chart_gap"] = _src_tag
                            elif ch["type"] == "trend":
                                extra_vars["chart_trend"] = _src_tag
                except Exception as e:
                    logger.debug(f"Template charts generation failed: {e}")

                # Report
                try:
                    from tools.report_generator import generate_and_upload_report
                    report_result = generate_and_upload_report(str(inep))
                    if report_result:
                        _rurl = report_result["html_url"]
                        extra_vars["report_link"] = (
                            f'<a href="{_rurl}" style="color:#3BB8C4;font-weight:bold">'
                            f'Ver diagnostico completo da {school_name}</a>'
                        )
                except Exception as e:
                    logger.debug(f"Template report generation failed: {e}")

        rendered = render_template(
            subject_template=template_data["subject_template"],
            body_template=body_tpl,
            company=company,
            contact=contact or {},
            extra_variables=extra_vars if extra_vars else None,
        )

        subject = rendered["subject"]
        body = rendered["body"]

        # Fallback: se report_link nao foi usado no template, anexar ao final
        if extra_vars.get("report_link") and "{report_link}" not in body_tpl:
            body += f"\n\nVeja o diagnostico completo da {school_name}: {extra_vars['report_link']}"

        # Se charts foram usados inline no template, nao duplicar no final (Brevo)
        _charts_inline = any(v in body_tpl for v in ["{chart_radar}", "{chart_gap}", "{chart_trend}"])
        _queue_charts = [] if _charts_inline else chart_urls_list

        if len(subject) > 60:
            subject = subject[:57] + "..."

        queue_id = self._add_to_approval_queue(
            company_id=company_id,
            contact_id=contact.get("id") if contact else None,
            subject=subject, body=body,
            chart_urls=_queue_charts if _queue_charts else None)
        if not queue_id:
            return None
        logger.info("Mensagem na fila (template)", extra={
            "company_id": company_id, "queue_id": queue_id,
            "charts": len(chart_urls_list), "has_report": bool(extra_vars.get("report_link")),
        })
        return {"company_id": company_id, "company_name": school_name, "queue_id": queue_id,
            "subject": subject,
            "body_preview": body[:150]+"..." if len(body)>150 else body,
            "reasoning": f"Template: {template_data.get('name', '?')}", "mode": "template",
            "charts_incluidos": len(chart_urls_list)}

    # =========================================================================
    # Formatacao de dados para prompt (modo IA)
    # =========================================================================

    def _format_school_section(self, company: Dict[str, Any]) -> str:
        """Formata dados da escola para o prompt (inclui dados MEC 2025)."""
        nl = chr(10)
        lines: List[str] = []

        # Aviso se for escola do Catalogo (sem dados ricos)
        fonte = company.get("fonte_dados", "")
        if fonte == "catalogo_inep":
            lines.append("**AVISO**: escola do Catalogo INEP — nao participou do Censo 2025.")
            lines.append("NAO invente numeros (matriculas, docentes, etc.) — use argumentacao generica.")
            lines.append("")

        # Identificacao
        for label, key in [
            ("Nome", "name"), ("Cidade", "city"), ("UF", "state"),
            ("Regiao", "regiao"), ("Bairro", "bairro"),
            ("Perfil de Ensino", "perfil_ensino"),
            ("Categoria", "admin_category"),
            ("Dependencia", "admin_dependency"),
            ("Categoria Privada", "categoria_privada"),
            ("Porte", "school_size"),
            ("Website", "website"),
            ("Score Qualificacao", "qualification_score"),
            ("Raciocinio Qualificacao", "qualification_reasoning"),
        ]:
            v = company.get(key)
            if v is not None and v != "":
                lines.append(f"- **{label}**: {v}")

        # Escala (matriculas) — dados concretos para personalizar
        total_mat = company.get("total_matriculas")
        if total_mat:
            lines.append(f"- **Total de alunos**: {total_mat}")
            for label, key in [
                ("Fund. Anos Finais (6-9)", "matriculas_fund_af"),
                ("Ensino Medio", "matriculas_medio"),
                ("Integral", "matriculas_integral"),
            ]:
                v = company.get(key)
                if v:
                    lines.append(f"  - {label}: {v}")

        # Equipe — ajuda a escolher linguagem e identificar decisores
        for label, key in [
            ("Docentes", "total_docentes"),
            ("Coordenadores pedagogicos", "qt_coordenadores"),
            ("Turmas", "total_turmas"),
        ]:
            v = company.get(key)
            if v:
                lines.append(f"- **{label}**: {v}")

        # Tecnologia — fundamental para argumentacao
        nivel_tech = company.get("nivel_tecnologico")
        if nivel_tech:
            lines.append(f"- **Nivel Tecnologico**: {nivel_tech}")
        tech_flags = []
        for label, key in [
            ("Banda larga", "banda_larga"),
            ("Lab. de informatica", "lab_informatica"),
            ("Internet p/ aprendizagem", "internet_aprendizagem"),
        ]:
            v = company.get(key)
            if v is True:
                tech_flags.append(label)
        if tech_flags:
            lines.append(f"- **Tecnologia disponivel**: {', '.join(tech_flags)}")

        return nl.join(lines) if lines else "Dados nao disponiveis"

    def _format_contact_section(self, contact: Optional[Dict[str, Any]],
                                all_contacts: Optional[List[Dict[str, Any]]] = None) -> str:
        """Formata contato principal + outros decisores conhecidos."""
        if not contact:
            return "Contato nao identificado - use tratamento generico (Prezado(a) Diretor(a))"
        # Contato principal (destinatario)
        fields = [("Nome","full_name"),("Cargo","role"),("Email","email"),("LinkedIn","linkedin_url")]
        lines = ["**Destinatario:**"]
        for label, key in fields:
            value = contact.get(key)
            if value:
                lines.append(f"- **{label}**: {value}")
        # Outros decisores conhecidos (contexto para personalizacao)
        if all_contacts and len(all_contacts) > 1:
            lines.append("")
            lines.append("**Outros decisores conhecidos na escola:**")
            contact_id = contact.get("id")
            for c in all_contacts:
                if c.get("id") != contact_id:
                    name = c.get("full_name", "?")
                    role = c.get("role", "?")
                    lines.append(f"- {name} ({role})")
        return chr(10).join(lines) if lines else "Contato sem dados completos"

    def _format_qualification_section(self, company: Dict[str, Any]) -> str:
        score = company.get("qualification_score", "N/A")
        reasoning = company.get("qualification_reasoning", "Nao disponivel")
        notes = company.get("notes", "")
        lines = [f"- **Score**: {score}/100", f"- **Raciocinio**: {reasoning}"]
        if notes:
            lines.append(f"- **Notas adicionais**: {notes}")
        return chr(10).join(lines)

    def _format_sender_section(self) -> str:
        from config.settings import settings
        from utils.sender_profile import get_active_sender
        _sender = get_active_sender()
        nl = chr(10)
        name = _sender.get("name") or settings.YOUR_NAME
        email = _sender.get("email") or settings.YOUR_EMAIL
        phone = _sender.get("phone") or getattr(settings, "YOUR_PHONE", "")
        return (
            f"- **Nome**: {name}" + nl
            + f"- **Email**: {email}" + nl
            + f"- **Empresa**: {getattr(settings, 'COMPANY_NAME', 'IAprendo')}" + nl
            + f"- **Telefone**: {phone}"
        )

    # =========================================================================
    # Anti-duplicata
    # =========================================================================

    def _has_pending_message(self, company_id: str) -> bool:
        """Verifica se a escola ja tem mensagem pendente ou aprovada na fila."""
        try:
            result = db.client.table("approval_queue").select("id").eq(
                "company_id", company_id
            ).in_("status", ["pending", "approved"]).limit(1).execute()
            return bool(result.data)
        except Exception as e:
            logger.warning("Erro ao verificar fila (continuando)", extra={"error": str(e)})
            return False

    # =========================================================================
    # Approval Queue + Parse
    # =========================================================================

    def _add_to_approval_queue(self, company_id: str, contact_id, subject: str, body: str,
                               chart_urls: Optional[List[Dict[str, str]]] = None):
        """Adiciona na fila de aprovacao humana. NUNCA envia diretamente."""
        try:
            import json as _json
            queue_data = {
                "company_id": company_id, "subject": subject, "body": body,
                "channel": "email", "status": "pending",
                "original_subject": subject, "original_body": body,}
            if contact_id:
                queue_data["contact_id"] = contact_id
            if chart_urls:
                queue_data["chart_urls"] = _json.dumps(chart_urls)
            result = db.client.table("approval_queue").insert(queue_data).execute()
            if result.data:
                queue_id = result.data[0]["id"]
                logger.info("Mensagem na approval_queue", extra={"queue_id": queue_id, "company_id": company_id})
                return queue_id
            return None
        except Exception as e:
            logger.error("Erro ao adicionar na approval_queue",
                extra={"company_id": company_id, "error": str(e)}, exc_info=True)
            return None

    def _parse_response(self, response_text: str, company_id: str):
        """Faz parse do JSON retornado pelo Claude."""
        try:
            cleaned = response_text.strip()
            if cleaned.startswith(TRIPLE_BACKTICK):
                cleaned = cleaned.split(chr(10),1)[1] if chr(10) in cleaned else cleaned[3:]
                if cleaned.endswith(TRIPLE_BACKTICK):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            data = json.loads(cleaned)
            subject = data.get("subject","").strip()
            body = data.get("body","").strip()
            if not subject or not body:
                logger.warning("Resposta sem subject ou body", extra={"company_id": company_id})
                return None
            if len(subject) > 60:
                subject = subject[:57]+"..."
            return {"subject": subject, "body": body, "reasoning": data.get("reasoning","")}
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error("Falha ao parsear resposta do writer",
                extra={"company_id": company_id, "error": str(e), "response_preview": response_text[:200]})
            return None
