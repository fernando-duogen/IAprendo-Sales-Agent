"""
Agents - Agentes de IA do sistema IAprendo Sales Agent.

Cada agente e responsavel por uma etapa do pipeline de prospeccao:
    - QualifierAgent: Qualifica escolas com Claude Haiku (score 0-100)
    - WriterAgent: Gera mensagens personalizadas com Claude Sonnet
    - EnricherAgent: Enriquece dados via APIs e web scraping
    - ContactFinderAgent: Encontra decisores (diretores, coordenadores)
"""
from agents.base_agent import BaseAgent
from agents.qualifier import QualifierAgent
from agents.writer import WriterAgent
from agents.enricher import EnricherAgent
from agents.contact_finder import ContactFinderAgent

__all__ = [
    "BaseAgent", "QualifierAgent", "WriterAgent",
    "EnricherAgent", "ContactFinderAgent",
]
