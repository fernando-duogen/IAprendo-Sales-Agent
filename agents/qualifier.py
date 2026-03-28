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
        fields = [
            ("Nome","name"),("Cidade","city"),("UF","state"),("Endereco","address"),
            ("Categoria Administrativa","admin_category"),("Dependencia Administrativa","admin_dependency"),
            ("Etapas de Ensino","education_levels"),("Porte","school_size"),
            ("Telefone","phone"),("Website","website"),("Codigo INEP","inep_code"),]
        lines = []
        for label, key in fields:
            value = company.get(key)
            if value:
                lines.append(f"- **{label}**: {value}")
            else:
                lines.append(f"- **{label}**: Nao informado")
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
