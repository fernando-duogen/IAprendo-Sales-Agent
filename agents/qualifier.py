import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from agents.base_agent import BaseAgent
from database.supabase_client import db
from utils.logger import logger

NEWLINE = chr(10)
TRIPLE_BACKTICK = chr(96) * 3


class QualifierAgent(BaseAgent):
    """Qualifica escolas usando Claude Haiku (modelo rapido/barato)."""

    def __init__(self) -> None:
        super().__init__(agent_name="qualifier")
        self.prompt_template = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "qualification_prompt.txt"
        try:
            return prompt_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error("Prompt de qualificacao nao encontrado", extra={"path": str(prompt_path)})
            raise

    def execute(self, companies: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """Qualifica lista de escolas com Claude Haiku."""
        if not self._check_rate_limit("anthropic"):
            logger.warning("Rate limit Anthropic atingido, abortando qualificacao")
            return []
        results: List[Dict[str, Any]] = []
        for company in companies:
            try:
                result = self.qualify_school(company)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error("Erro ao qualificar escola",
                    extra={"company_id": company.get("id"), "school_name": company.get("name"), "error": str(e)})
        logger.info("Qualificacao batch concluida",
            extra={"total": len(companies), "qualified": len(results), "failed": len(companies)-len(results)})
        return results

    def qualify_school(self, company: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Qualifica uma escola individual."""
        company_id = company.get("id")
        school_name = company.get("name", "Desconhecida")
        logger.info("Qualificando escola", extra={"company_id": company_id, "school_name": school_name})
        school_data = self._format_school_data(company)
        prompt = self.prompt_template.replace("{school_data}", school_data)
        response_text = self._call_claude(prompt=prompt, model="fast", max_tokens=512)
        parsed = self._parse_response(response_text, company_id)
        if not parsed:
            return None
        self._update_company(company_id, {
            "status": "qualified",
            "qualification_score": parsed["score"],
            "qualification_reasoning": parsed["reasoning"],})
        parsed["company_id"] = company_id
        parsed["company_name"] = school_name
        logger.info("Escola qualificada",
            extra={"company_id": company_id, "score": parsed["score"], "priority": parsed["priority"]})
        return parsed

    def _format_school_data(self, company: Dict[str, Any]) -> str:
        """Formata dados da escola (inclui colunas ricas da base MEC 2025)."""
        # Cabecalho com fonte dos dados
        fonte = company.get("fonte_dados", "")
        lines = []
        if fonte == "catalogo_inep":
            lines.append("## AVISO: ESCOLA DO CATALOGO INEP")
            lines.append("Esta escola esta ativa mas NAO participou do Censo 2025.")
            lines.append("Dados de matriculas, equipe, nivel tecnologico e infraestrutura NAO estao disponiveis.")
            lines.append("Use APENAS os dados basicos abaixo para qualificar. Score considere o porte declarado e tipo.")
            lines.append("")

        # Dados basicos
        basicos = [
            ("Nome", "name"), ("Cidade", "city"), ("UF", "state"),
            ("Regiao", "regiao"), ("Bairro", "bairro"), ("Endereco", "address"),
            ("Categoria Administrativa", "admin_category"),
            ("Dependencia", "admin_dependency"),
            ("Categoria Privada", "categoria_privada"),
            ("Localizacao", "localizacao"),
            ("Perfil de Ensino", "perfil_ensino"),
            ("Porte", "school_size"),
            ("Telefone", "phone"), ("Website", "website"),
            ("Codigo INEP", "inep_code"),
        ]
        lines.append("## DADOS BASICOS")
        for label, key in basicos:
            value = company.get(key)
            lines.append(f"- **{label}**: {value if value else 'Nao informado'}")

        # Matriculas (escala)
        total_mat = company.get("total_matriculas")
        if total_mat:
            lines.append("")
            lines.append("## ESCALA (MATRICULAS)")
            lines.append(f"- **Total matriculas**: {total_mat}")
            for label, key in [
                ("Infantil", "matriculas_infantil"),
                ("Fundamental (total)", "matriculas_fundamental"),
                ("Fund. Anos Iniciais", "matriculas_fund_ai"),
                ("Fund. Anos Finais", "matriculas_fund_af"),
                ("Ensino Medio", "matriculas_medio"),
                ("Integral", "matriculas_integral"),
                ("EJA", "matriculas_eja"),
            ]:
                v = company.get(key)
                if v:
                    lines.append(f"  - {label}: {v}")
            perc_integral = company.get("perc_integral")
            if perc_integral:
                lines.append(f"- **% Integral**: {perc_integral}%")

            # Por serie (Fund AF)
            series_fund = [("6 ano", "mat_6_ano"), ("7 ano", "mat_7_ano"),
                           ("8 ano", "mat_8_ano"), ("9 ano", "mat_9_ano")]
            fund_af = [f"{label}={company.get(key)}" for label, key in series_fund if company.get(key)]
            if fund_af:
                lines.append(f"- **Por ano (Fund AF)**: {', '.join(fund_af)}")

            # Por serie (Medio)
            series_medio = [("1o", "mat_medio_1"), ("2o", "mat_medio_2"), ("3o", "mat_medio_3")]
            medio = [f"{label}={company.get(key)}" for label, key in series_medio if company.get(key)]
            if medio:
                lines.append(f"- **Por ano (Medio)**: {', '.join(medio)}")

        # Equipe
        equipe_fields = [
            ("Docentes", "total_docentes"),
            ("Gestores", "total_gestores"),
            ("Coordenadores", "qt_coordenadores"),
            ("Administrativos", "qt_administrativos"),
            ("Turmas", "total_turmas"),
            ("Alunos/Docente", "alunos_por_docente"),
        ]
        equipe_vals = [(l, company.get(k)) for l, k in equipe_fields if company.get(k)]
        if equipe_vals:
            lines.append("")
            lines.append("## EQUIPE")
            for label, val in equipe_vals:
                lines.append(f"- **{label}**: {val}")

        # Tecnologia
        nivel_tech = company.get("nivel_tecnologico")
        tech_bool = [
            ("Internet", "tem_internet"),
            ("Internet p/ alunos", "internet_alunos"),
            ("Internet p/ aprendizagem", "internet_aprendizagem"),
            ("Banda Larga", "banda_larga"),
            ("Lab Informatica", "lab_informatica"),
        ]
        tech_int = [
            ("Desktops p/ aluno", "qt_desktop_aluno"),
            ("Notebooks p/ aluno", "qt_notebook_aluno"),
            ("Tablets p/ aluno", "qt_tablet_aluno"),
        ]
        tech_has_data = nivel_tech or any(company.get(k) is not None for _, k in tech_bool + tech_int)
        if tech_has_data:
            lines.append("")
            lines.append("## TECNOLOGIA")
            if nivel_tech:
                lines.append(f"- **Nivel Tecnologico**: {nivel_tech}")
            for label, key in tech_bool:
                v = company.get(key)
                if v is not None:
                    lines.append(f"- **{label}**: {'Sim' if v else 'Nao'}")
            for label, key in tech_int:
                v = company.get(key)
                if v:
                    lines.append(f"- **{label}**: {v}")

        # Infraestrutura
        infra = [
            ("Biblioteca", "tem_biblioteca"),
            ("Quadra de Esportes", "tem_quadra"),
            ("Lab de Ciencias", "tem_lab_ciencias"),
            ("Alimentacao", "tem_alimentacao"),
        ]
        infra_vals = [(l, company.get(k)) for l, k in infra if company.get(k) is not None]
        if infra_vals:
            lines.append("")
            lines.append("## INFRAESTRUTURA")
            for label, val in infra_vals:
                lines.append(f"- **{label}**: {'Sim' if val else 'Nao'}")

        # Etapas oferecidas
        etapas = [
            ("Fund. Anos Finais", "oferece_fund_af"),
            ("Ensino Medio", "oferece_medio"),
            ("EJA", "oferece_eja"),
            ("Profissionalizante", "oferece_profissionalizante"),
        ]
        etapas_vals = [(l, company.get(k)) for l, k in etapas if company.get(k) is not None]
        if etapas_vals:
            lines.append("")
            lines.append("## ETAPAS OFERECIDAS")
            for label, val in etapas_vals:
                lines.append(f"- **{label}**: {'Sim' if val else 'Nao'}")

        return NEWLINE.join(lines)

    def _parse_response(self, response_text: str, company_id: str) -> Optional[Dict[str, Any]]:
        """Faz parse do JSON retornado pelo Claude."""
        try:
            cleaned = response_text.strip()
            if cleaned.startswith(TRIPLE_BACKTICK):
                cleaned = cleaned.split(NEWLINE, 1)[1] if NEWLINE in cleaned else cleaned[3:]
                if cleaned.endswith(TRIPLE_BACKTICK):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            data = json.loads(cleaned)
            score = int(data.get("score", 0))
            score = max(0, min(100, score))
            priority = data.get("priority", "baixa")
            if priority not in ("baixa", "media", "alta"):
                if score >= 70: priority = "alta"
                elif score >= 40: priority = "media"
                else: priority = "baixa"
            return {"score": score, "priority": priority, "reasoning": data.get("reasoning",""),
                "estimated_size": data.get("estimated_size","media"),
                "innovation_signals": data.get("innovation_signals",[]),
                "recommended_approach": data.get("recommended_approach",""),}
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error("Falha ao parsear resposta do Claude",
                extra={"company_id": company_id, "error": str(e), "response_preview": response_text[:200]})
            return None
