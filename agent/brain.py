"""
IAlex Brain - Cerebro do agente com Tool Use (function calling).

Usa OpenAI GPT-4.1-mini com ferramentas para consultar o banco Supabase
diretamente, gerando respostas naturais e ricas baseadas em dados reais.

Usage:
    from agent.brain import Brain
    brain = Brain()
    result = brain.process_message("quantas escolas temos em Porto Alegre?")
    # result = {"reply": "Temos 78 escolas cadastradas em Porto Alegre..."}
"""

import json
import math
import os
import unicodedata
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

import pandas as pd
from openai import OpenAI

from config.settings import settings
from database.supabase_client import db
from utils.logger import logger

# Cache do CSV para fallback (carregado na primeira busca)
_csv_df: Optional[pd.DataFrame] = None


def _get_csv_df() -> Optional[pd.DataFrame]:
    """Carrega e cacheia o CSV do MEC com colunas pre-computadas."""
    global _csv_df
    if _csv_df is not None:
        return _csv_df
    csv_path = Path(settings.CSV_PATH)
    if not csv_path.exists():
        return None
    try:
        _csv_df = pd.read_csv(csv_path, encoding=settings.CSV_ENCODING, low_memory=False)
        col_map = settings.get_csv_column_mapping()

        # Pre-computar coordenadas limpas (float, sem espaços)
        for coord_key in ['latitude', 'longitude']:
            col_name = col_map.get(coord_key)
            if col_name and col_name in _csv_df.columns:
                _csv_df[f"_clean_{coord_key}"] = pd.to_numeric(
                    _csv_df[col_name].astype(str).str.strip(), errors='coerce'
                )

        # Pre-computar colunas normalizadas (sem acentos, lowercase) para busca
        name_col = col_map.get('name')
        if name_col and name_col in _csv_df.columns:
            _csv_df["_name_lower"] = _csv_df[name_col].astype(str).str.lower()
            _csv_df["_name_norm"] = _csv_df[name_col].astype(str).apply(_normalize)

        # Normalizar colunas de texto usadas em filtros
        for key, col_name in [
            ('education_levels', col_map.get('education_levels')),
            ('admin_category', col_map.get('admin_category')),
            ('admin_dependency', col_map.get('admin_dependency')),
            ('city', col_map.get('city')),
            ('size', col_map.get('size')),
        ]:
            if col_name and col_name in _csv_df.columns:
                _csv_df[f"_norm_{key}"] = _csv_df[col_name].astype(str).apply(_normalize)

        # Normalizar localização se existir
        if "Localização" in _csv_df.columns:
            _csv_df["_norm_localizacao"] = _csv_df["Localização"].astype(str).apply(_normalize)

        logger.info("CSV MEC carregado em cache", extra={"rows": len(_csv_df)})
    except Exception as e:
        logger.error(f"Falha ao carregar CSV: {e}")
        return None
    return _csv_df


def _normalize(text: str) -> str:
    """Remove acentos e converte para lowercase para busca."""
    if not isinstance(text, str):
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return nfkd.encode('ASCII', 'ignore').decode('ASCII').lower()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia em km entre dois pontos (formula Haversine)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ===========================================================================
# TOOLS - Ferramentas que o Claude pode chamar
# ===========================================================================

TOOLS = [
    {
        "name": "consultar_escolas",
        "description": "Consulta escolas no BANCO DE DADOS (leads ja importados e qualificados, com score, pipeline e contatos). Para buscar na base completa do MEC (212k escolas de todo o Brasil), use buscar_escola_brasil.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Filtrar por nome da escola (busca parcial)"},
                "cidade": {"type": "string", "description": "Filtrar por cidade"},
                "estado": {"type": "string", "description": "Filtrar por UF (ex: RS)"},
                "status": {"type": "string", "description": "Filtrar por status: raw, filtered, qualified, enriched, contacted, sent, opened, replied"},
                "score_minimo": {"type": "integer", "description": "Score minimo de qualificacao (0-100)"},
                "categoria": {"type": "string", "description": "Categoria administrativa: Publica, Privada, Municipal, Estadual, Federal"},
                "limite": {"type": "integer", "description": "Maximo de resultados (default 10, max 50)"},
                "ordenar_por": {"type": "string", "description": "Campo para ordenar: qualification_score, name, created_at, updated_at"},
                "ordem": {"type": "string", "enum": ["asc", "desc"], "description": "Ordem: asc ou desc"}
            }
        }
    },
    {
        "name": "buscar_contatos",
        "description": "Busca contatos (decisores) de uma escola. Retorna nome, cargo, email, telefone, linkedin, fonte e score de confianca.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola para buscar contatos"},
                "escola_id": {"type": "string", "description": "ID da escola (UUID)"}
            }
        }
    },
    {
        "name": "estatisticas_gerais",
        "description": "Retorna estatisticas completas do CRM: total de escolas por status, contatos, fila de aprovacao, interacoes.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fila_aprovacao",
        "description": "Lista mensagens na fila de aprovacao (emails/whatsapp pendentes de revisao). Mostra assunto, canal, escola destinataria e status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filtrar por status: pending, approved, rejected, sent (default: todos)"},
                "limite": {"type": "integer", "description": "Maximo de resultados (default 10)"}
            }
        }
    },
    {
        "name": "aprovar_mensagem",
        "description": "Aprova uma mensagem na fila de aprovacao para envio. ACAO SENSIVEL: sempre confirme com Fernando antes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "queue_id": {"type": "string", "description": "ID da mensagem na fila"},
                "aprovar_todas": {"type": "boolean", "description": "Se true, aprova TODAS as pendentes"}
            }
        }
    },
    {
        "name": "consultar_interacoes",
        "description": "Consulta historico de interacoes com uma escola (emails enviados, abertos, respondidos, reunioes, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_id": {"type": "string", "description": "ID da escola"},
                "escola_nome": {"type": "string", "description": "Nome da escola (busca parcial)"},
                "tipo": {"type": "string", "description": "Tipo: email_sent, email_opened, email_replied, whatsapp_sent, meeting_scheduled, etc"}
            }
        }
    },
    {
        "name": "uso_apis",
        "description": "Mostra uso de APIs externas (Apollo, Snov, Hunter, Anthropic) com creditos gastos e limites mensais.",
        "input_schema": {
            "type": "object",
            "properties": {
                "api_name": {"type": "string", "description": "Filtrar por API: anthropic, apollo, snov, hunter, google_maps, brevo, hubspot"}
            }
        }
    },
    {
        "name": "detalhes_escola",
        "description": "Retorna TODOS os detalhes de uma escola especifica: dados cadastrais, score, contatos, interacoes, fila de aprovacao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola (busca parcial)"},
                "inep": {"type": "string", "description": "Codigo INEP da escola"}
            },
            "required": []
        }
    },
    {
        "name": "gerar_email",
        "description": "Gera um email personalizado de prospecção para uma escola. O email é criado com base nos dados da escola (porte, niveis de ensino, categoria) e do contato (nome, cargo). O email vai para a fila de aprovação — Fernando revisa antes de enviar. Retorna o email gerado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola"},
                "contato_nome": {"type": "string", "description": "Nome do decisor/contato"},
                "contato_cargo": {"type": "string", "description": "Cargo do contato (ex: Diretor, Coordenador)"},
                "contato_email": {"type": "string", "description": "Email do contato"},
                "tom": {"type": "string", "description": "Tom do email: formal, amigavel, direto (default: amigavel)"},
                "foco": {"type": "string", "description": "Foco do email: apresentacao, demo, case de sucesso, convite evento (default: apresentacao)"}
            },
            "required": ["escola_nome"]
        }
    },
    {
        "name": "rejeitar_mensagem",
        "description": "Rejeita uma mensagem na fila de aprovacao. Registra o motivo da rejeicao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "queue_id": {"type": "string", "description": "ID da mensagem na fila"},
                "motivo": {"type": "string", "description": "Motivo da rejeicao"}
            },
            "required": ["queue_id"]
        }
    },
    {
        "name": "atualizar_escola",
        "description": "Atualiza dados de uma escola: status, notas, telefone, website, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola para buscar"},
                "escola_id": {"type": "string", "description": "ID da escola (UUID)"},
                "status": {"type": "string", "description": "Novo status: raw, filtered, qualified, enriched, contacted"},
                "notas": {"type": "string", "description": "Notas/observacoes sobre a escola"},
                "telefone": {"type": "string", "description": "Telefone atualizado"},
                "website": {"type": "string", "description": "Website da escola"}
            }
        }
    },
    {
        "name": "rodar_pipeline",
        "description": "Roda etapas do pipeline de prospecção: qualificar escolas com IA (score 0-100), enriquecer com dados de contato, etc. ACAO SENSIVEL: confirme com Fernando antes de executar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "etapa": {"type": "string", "description": "Etapa: qualify (qualificar com IA), enrich (buscar contatos), write (gerar emails), all (tudo)"},
                "limite": {"type": "integer", "description": "Maximo de escolas para processar (default 5, max 50)"},
                "status_origem": {"type": "string", "description": "Processar escolas com este status (default: raw para qualify, qualified para enrich)"}
            }
        }
    },
    {
        "name": "consulta_livre",
        "description": "Executa uma consulta flexivel ao banco de dados para perguntas complexas que as outras ferramentas nao cobrem. Pode contar, agrupar, filtrar por qualquer campo. Use esta ferramenta quando nenhuma outra for adequada.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tabela": {"type": "string", "description": "Tabela: companies, contacts, approval_queue, interactions, meetings, api_usage"},
                "campos": {"type": "string", "description": "Campos para retornar (separados por virgula). Use * para todos."},
                "filtros": {
                    "type": "array",
                    "description": "Lista de filtros. Cada filtro: {campo, operador, valor}",
                    "items": {
                        "type": "object",
                        "properties": {
                            "campo": {"type": "string"},
                            "operador": {"type": "string", "description": "eq, neq, gt, gte, lt, lte, like, ilike, in"},
                            "valor": {"type": "string"}
                        }
                    }
                },
                "ordenar": {"type": "string", "description": "Campo para ordenar"},
                "ordem": {"type": "string", "enum": ["asc", "desc"]},
                "limite": {"type": "integer", "description": "Max resultados (default 20)"},
                "contar": {"type": "boolean", "description": "Se true, retorna apenas contagem"}
            },
            "required": ["tabela"]
        }
    },
    {
        "name": "enriquecer_contatos",
        "description": "Busca contatos/decisores de uma escola usando cascade de fontes: web scraping, Apollo, Hunter, Snov e Perplexity. Encontra diretores, coordenadores e gestores com email e telefone. Pode demorar 30-60 segundos por escola. ACAO SENSIVEL: consome creditos de APIs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola para buscar contatos"},
                "escola_id": {"type": "string", "description": "ID da escola (UUID)"},
                "fonte": {"type": "string", "description": "Forcar uma fonte especifica: scraping, apollo, hunter, snov, perplexity. Se nao informado, usa cascade completa."}
            }
        }
    },
    {
        "name": "buscar_escola_brasil",
        "description": "Busca escolas na base COMPLETA do MEC com 212 mil escolas de todo o Brasil. "
                       "Use esta ferramenta para encontrar QUALQUER escola do pais por qualquer combinacao "
                       "de criterios: nome, cidade, estado, porte, niveis de ensino, tipo (publica/privada), "
                       "localizacao (urbana/rural). Busca parcial por nome. "
                       "Ideal quando o Fernando pergunta sobre uma escola especifica ou quer explorar escolas de uma regiao.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome da escola (busca parcial, case-insensitive)"},
                "cidade": {"type": "string", "description": "Municipio (busca parcial)"},
                "uf": {"type": "string", "description": "Sigla do estado (ex: RS, SP, MG)"},
                "porte": {"type": "string", "description": "Porte: 'Ate 50', 'Entre 51 e 200', 'Entre 201 e 500', 'Entre 501 e 1000', 'Mais de 1000'"},
                "niveis_ensino": {"type": "string", "description": "Nivel de ensino (busca parcial): 'Fundamental', 'Medio', 'Infantil', 'Jovens Adultos'"},
                "tipo": {"type": "string", "description": "Tipo: 'Publica' ou 'Privada'"},
                "dependencia": {"type": "string", "description": "Dependencia: 'Municipal', 'Estadual', 'Federal', 'Privada'"},
                "localizacao": {"type": "string", "description": "Localizacao: 'Urbana' ou 'Rural'"},
                "limite": {"type": "integer", "description": "Max resultados (default 10, max 20)"}
            }
        }
    },
    {
        "name": "escolas_proximas",
        "description": "Busca escolas proximas a uma coordenada (latitude/longitude) em um raio. "
                       "Usa formula Haversine para distancia real. Busca no banco E na base MEC (212k escolas). "
                       "Ideal para quando Fernando esta em campo visitando escolas e quer saber o que tem por perto. "
                       "IMPORTANTE: ~40%% das escolas na base MEC nao possuem coordenadas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitude do ponto central (ex: -30.0346)"},
                "longitude": {"type": "number", "description": "Longitude do ponto central (ex: -51.2177)"},
                "raio_km": {"type": "number", "description": "Raio de busca em km (default 2, max 50)"},
                "tipo": {"type": "string", "description": "Filtrar: 'Publica' ou 'Privada' (opcional)"},
                "niveis_ensino": {"type": "string", "description": "Filtrar por nivel: 'Fundamental', 'Medio' (opcional)"},
                "limite": {"type": "integer", "description": "Max resultados (default 10, max 20)"},
                "fonte": {"type": "string", "description": "Fonte: 'db' (apenas banco), 'mec' (apenas CSV), 'ambos' (default)"}
            },
            "required": ["latitude", "longitude"]
        }
    },
    {
        "name": "importar_escola",
        "description": "Importa uma escola da base MEC para o banco de dados CRM. "
                       "Busca a escola pelo codigo INEP ou por nome+cidade na base MEC e insere no banco. "
                       "Depois de importada, a escola pode ser qualificada, enriquecida e contatada pelo pipeline. "
                       "Use apos encontrar uma escola interessante via buscar_escola_brasil ou consultar_escolas.",
        "input_schema": {
            "type": "object",
            "properties": {
                "inep": {"type": "string", "description": "Codigo INEP da escola (preferencial — garante unicidade)"},
                "nome": {"type": "string", "description": "Nome da escola (usado se INEP nao informado)"},
                "cidade": {"type": "string", "description": "Cidade (ajuda a localizar se buscar por nome)"}
            }
        }
    },
    {
        "name": "enviar_aprovados",
        "description": "Envia todos os emails que ja foram aprovados na fila de aprovacao. "
                       "So envia mensagens com status 'approved'. Seguro — nada e enviado sem aprovacao previa.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Max emails para enviar (default 50)"}
            }
        }
    },
    {
        "name": "gerar_followups",
        "description": "Verifica escolas que nao responderam e gera follow-ups automaticos. "
                       "Sequencia: dia 3 (lembrete), dia 7 (valor extra), dia 14 (ultima tentativa). "
                       "Follow-ups vao para a fila de aprovacao — nunca sao enviados direto. "
                       "ACAO SENSIVEL: consome creditos de IA para gerar mensagens.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Max follow-ups para gerar (default 20)"}
            }
        }
    },
    {
        "name": "tracking_emails",
        "description": "Mostra resultados dos emails enviados: taxa de abertura, cliques, respostas, bounces. "
                       "Pode mostrar stats gerais (ultimos N dias) ou timeline de uma escola especifica. "
                       "Tambem sincroniza eventos do Brevo para atualizar status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dias": {"type": "integer", "description": "Periodo em dias para stats gerais (default 30)"},
                "escola_id": {"type": "string", "description": "ID da escola para ver timeline especifica (opcional)"},
                "sincronizar": {"type": "boolean", "description": "Se true, sincroniza eventos do Brevo antes de mostrar stats (default false)"}
            }
        }
    },
    {
        "name": "editar_e_aprovar",
        "description": "Edita o assunto e/ou corpo de um email na fila de aprovacao e aprova em seguida. "
                       "Use quando Fernando quiser ajustar um email antes de aprovar, sem precisar rejeitar e recriar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "queue_id": {"type": "string", "description": "ID da mensagem na fila"},
                "novo_assunto": {"type": "string", "description": "Novo assunto (opcional — mantem o atual se nao informado)"},
                "novo_corpo": {"type": "string", "description": "Novo corpo do email (opcional — mantem o atual se nao informado)"}
            },
            "required": ["queue_id"]
        }
    },
    {
        "name": "relatorio_pipeline",
        "description": "Gera relatorio completo do pipeline de vendas sob demanda. "
                       "Inclui: escolas por status, taxa de conversao, emails enviados/abertos/respondidos, "
                       "follow-ups pendentes, top oportunidades, e proximas acoes recomendadas.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "atualizar_scores",
        "description": "Recalcula scores de qualificacao com base em engajamento real. "
                       "Regras: email aberto +10, click +15, reply +30, reuniao +50, bounce -30. "
                       "Pode atualizar todas as escolas ou ver breakdown de uma especifica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_id": {"type": "string", "description": "ID da escola para ver breakdown (opcional). Se nao informado, atualiza TODAS."}
            }
        }
    },
    {
        "name": "registrar_reuniao",
        "description": "Registra uma visita ou reuniao com uma escola. "
                       "Use quando Fernando visitar uma escola, fizer uma call ou agendar um encontro.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola"},
                "escola_id": {"type": "string", "description": "ID da escola (UUID)"},
                "tipo": {"type": "string", "description": "Tipo: presencial, online, telefone (default presencial)"},
                "notas": {"type": "string", "description": "Notas sobre a reuniao/visita"},
                "resultado": {"type": "string", "description": "Resultado: interessado, nao_interessado, follow_up, fechado"},
                "data": {"type": "string", "description": "Data da reuniao (formato YYYY-MM-DD). Default: hoje"}
            }
        }
    },
    {
        "name": "operacao_lote",
        "description": "Executa operacoes em lote em multiplas escolas de uma vez. "
                       "Pode: importar N escolas de uma cidade, qualificar todas as raw, gerar emails em lote.",
        "input_schema": {
            "type": "object",
            "properties": {
                "acao": {"type": "string", "description": "Acao: 'importar' (da base MEC), 'qualificar' (raw->scored), 'gerar_emails' (qualified->emails)"},
                "cidade": {"type": "string", "description": "Cidade para filtrar (obrigatorio para importar)"},
                "uf": {"type": "string", "description": "Estado para filtrar"},
                "tipo": {"type": "string", "description": "Tipo: Publica, Privada"},
                "porte": {"type": "string", "description": "Porte minimo: 'Mais de 1000', 'Entre 501 e 1000', etc."},
                "limite": {"type": "integer", "description": "Max escolas para processar (default 5, max 20)"}
            },
            "required": ["acao"]
        }
    },
    {
        "name": "melhor_horario",
        "description": "Analisa dados historicos de abertura de emails e sugere o melhor horario e dia da semana para enviar.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "funil_vendas",
        "description": "Mostra o funil de conversao completo: quantas escolas em cada etapa do pipeline "
                       "(raw -> qualified -> enriched -> contacted -> replied -> meeting -> closed). "
                       "Identifica gargalos e sugere acoes.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sincronizar_hubspot",
        "description": "Sincroniza escolas, contatos e deals com o HubSpot CRM (Agente -> HubSpot). "
                       "Pode sincronizar uma escola especifica ou todas as que mudaram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_id": {"type": "string", "description": "ID da escola para sincronizar (opcional). Se nao informado, sincroniza todas com status enriched+."},
                "limite": {"type": "integer", "description": "Max escolas para sincronizar (default 10)"}
            }
        }
    },
    {
        "name": "sincronizar_hubspot_puxar",
        "description": "Puxa mudancas do HubSpot para o banco do agente (HubSpot -> Agente). "
                       "Use quando alguem alterou dados direto no HubSpot (deal stage, contatos, etc.) e voce quer que o IAlex saiba disso. "
                       "Roda automaticamente a cada 15 min, mas pode ser chamado manualmente para sincronizacao imediata.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "lembrar_fato",
        "description": "Grava um fato importante na MEMORIA PERSISTENTE do IAlex. Use SEMPRE que Fernando "
                       "mencionar algo que voce precisa lembrar depois: preferencias ('prefere WhatsApp'), "
                       "fatos ('tem 1200 alunos'), insights ('reagiu bem a case BNCC'), avisos ('diretor "
                       "de licenca ate agosto'), lembretes ('retornar em setembro'). NUNCA deixe de gravar "
                       "informacoes uteis — a memoria e crucial para construir relacionamento de longo prazo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "conteudo": {
                    "type": "string",
                    "description": "O fato/preferencia/insight em UMA frase clara. Ex: 'Diretora prefere ser contatada de manha.'"
                },
                "escopo": {
                    "type": "string",
                    "enum": ["global", "escola", "contato"],
                    "description": "global = sobre Fernando/negocio; escola = sobre uma escola especifica; contato = sobre uma pessoa"
                },
                "escola_id": {
                    "type": "string",
                    "description": "ID da escola (quando escopo=escola). Voce pode passar o nome tambem e eu busco."
                },
                "escola_nome": {
                    "type": "string",
                    "description": "Nome da escola (alternativa ao escola_id)"
                },
                "contato_id": {
                    "type": "string",
                    "description": "ID do contato (quando escopo=contato)"
                },
                "categoria": {
                    "type": "string",
                    "enum": ["fact", "preference", "insight", "warning", "reminder"],
                    "description": "Tipo de memoria. Default: fact"
                },
                "importancia": {
                    "type": "integer",
                    "description": "1 (baixa) ate 10 (critica). Default: 5"
                }
            },
            "required": ["conteudo", "escopo"]
        }
    },
    {
        "name": "buscar_memorias",
        "description": "Busca memorias guardadas anteriormente. Use para recuperar fatos, preferencias "
                       "e insights sobre uma escola, contato ou topico. Se houver escola/contato "
                       "na conversa atual, as memorias ja sao injetadas automaticamente no contexto, "
                       "mas voce pode forcar uma busca especifica.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escopo": {
                    "type": "string",
                    "enum": ["global", "escola", "contato", "texto"],
                    "description": "Onde buscar. 'texto' busca em todas as memorias pelo conteudo."
                },
                "escola_id": {"type": "string", "description": "ID da escola (escopo=escola)"},
                "escola_nome": {"type": "string", "description": "Nome da escola"},
                "contato_id": {"type": "string", "description": "ID do contato (escopo=contato)"},
                "texto": {"type": "string", "description": "Texto para buscar (escopo=texto)"},
                "limite": {"type": "integer", "description": "Max resultados (default 10)"}
            },
            "required": ["escopo"]
        }
    },
    {
        "name": "esquecer_memoria",
        "description": "Remove uma memoria especifica (quando Fernando pedir para esquecer algo).",
        "input_schema": {
            "type": "object",
            "properties": {
                "memoria_id": {"type": "string", "description": "ID da memoria a remover"}
            },
            "required": ["memoria_id"]
        }
    },
    {
        "name": "listar_campanhas",
        "description": "Lista campanhas de prospecacao ativas, pausadas ou concluidas. "
                       "Mostra nome, status, canal, metricas (enviados/abertos/respondidos).",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filtrar: draft, active, paused, completed (opcional)"}
            }
        }
    },
    {
        "name": "criar_campanha",
        "description": "Cria uma nova campanha de prospecacao para agrupar envios. "
                       "Exemplo: 'Privadas POA Março', 'Publicas Interior RS'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome da campanha"},
                "descricao": {"type": "string", "description": "Descricao/objetivo"},
                "canal": {"type": "string", "description": "Canal: email, whatsapp (default email)"},
                "filtros": {"type": "string", "description": "Filtros alvo em texto: 'Privadas em POA com mais de 500 alunos'"}
            },
            "required": ["nome"]
        }
    },
    {
        "name": "listar_templates",
        "description": "Lista templates de email disponiveis para prospecacao. "
                       "Mostra nome, assunto, se esta ativo, e qual e o default.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "criar_template",
        "description": "Cria um novo template de email. Use variaveis entre chaves: "
                       "{contact_name}, {school_name}, {city}, {sender_name}, {meeting_link}.",
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome do template (ex: pos_visita, demo, reativacao)"},
                "assunto": {"type": "string", "description": "Assunto do email com variaveis"},
                "corpo": {"type": "string", "description": "Corpo do email com variaveis"},
                "ativo": {"type": "boolean", "description": "Se o template esta ativo (default true)"}
            },
            "required": ["nome", "assunto", "corpo"]
        }
    },
    {
        "name": "enviar_whatsapp_escola",
        "description": "Envia mensagem WhatsApp para uma escola. A mensagem vai para a fila de aprovacao "
                       "com canal 'whatsapp'. Apos aprovacao, e enviada via WhatsApp. "
                       "A escola precisa ter telefone cadastrado.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escola_nome": {"type": "string", "description": "Nome da escola"},
                "escola_id": {"type": "string", "description": "ID da escola"},
                "mensagem": {"type": "string", "description": "Texto da mensagem WhatsApp"},
                "contato_nome": {"type": "string", "description": "Nome do contato (opcional)"}
            },
            "required": ["mensagem"]
        }
    },
    {
        "name": "score_preditivo",
        "description": "Analisa escolas com MACHINE LEARNING e preve quais tem mais chance de fechar negocio. "
                       "Usa Logistic Regression treinado com dados reais de fechamento + 11 features "
                       "(score IA, taxa de abertura, resposta, porte, tipo, contatos, etc.). "
                       "Se ainda nao ha dados suficientes, usa pesos heuristicos como fallback.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limite": {"type": "integer", "description": "Top N escolas com maior probabilidade (default 10)"},
                "score_minimo": {"type": "integer", "description": "Filtrar escolas com score preditivo >= X (0-100, default 0)"},
                "escola_id": {"type": "string", "description": "Se informado, retorna predicao detalhada de UMA escola (com fatores)"}
            }
        }
    },
    {
        "name": "treinar_modelo_preditivo",
        "description": "Retreina o modelo preditivo de fechamento de vendas usando os dados atuais do banco. "
                       "Requer pelo menos 10 escolas e 3 positivos (respostas ou reunioes). "
                       "Roda automaticamente 1x por semana, mas pode ser chamado manualmente para reavaliar "
                       "apos receber novas respostas.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "info_modelo_preditivo",
        "description": "Mostra informacoes sobre o modelo preditivo atual: se esta treinado, quantas amostras, "
                       "taxa de acerto, features mais importantes, quando foi o ultimo treino.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
]


# ===========================================================================
# TOOL HANDLERS - Executam as ferramentas
# ===========================================================================

def _handle_consultar_escolas(params: Dict) -> str:
    """Consulta escolas no banco de dados (leads importados/qualificados)."""
    query = db.client.table("companies").select("*")

    if params.get("nome"):
        query = query.ilike("name", f"%{params['nome']}%")
    if params.get("cidade"):
        query = query.ilike("city", f"%{params['cidade']}%")
    if params.get("estado"):
        query = query.eq("state", params["estado"].upper())
    if params.get("status"):
        query = query.eq("status", params["status"])
    if params.get("score_minimo"):
        query = query.gte("qualification_score", params["score_minimo"])
    if params.get("categoria"):
        query = query.ilike("admin_category", f"%{params['categoria']}%")

    order_field = params.get("ordenar_por", "qualification_score")
    order_desc = params.get("ordem", "desc") == "desc"
    query = query.order(order_field, desc=order_desc, nullsfirst=False)

    limite = min(params.get("limite", 10), 50)
    result = query.limit(limite).execute()

    escolas = []
    for s in result.data:
        escolas.append({
            "id": s["id"],
            "nome": s["name"],
            "inep": s.get("inep_code"),
            "cidade": s.get("city"),
            "estado": s.get("state"),
            "endereco": s.get("address"),
            "telefone": s.get("phone"),
            "website": s.get("website"),
            "categoria": s.get("admin_category"),
            "dependencia": s.get("admin_dependency"),
            "niveis_ensino": s.get("education_levels"),
            "porte": s.get("school_size"),
            "status": s.get("status"),
            "score": s.get("qualification_score"),
            "motivo_score": s.get("qualification_reasoning"),
            "latitude": s.get("latitude"),
            "longitude": s.get("longitude"),
        })

    if escolas:
        return json.dumps({"total": len(escolas), "fonte": "banco_crm", "escolas": escolas}, ensure_ascii=False)

    # --- Fallback automático: buscar na base MEC completa ---
    if params.get("nome") or params.get("cidade"):
        mec_params = {}
        if params.get("nome"):
            mec_params["nome"] = params["nome"]
        if params.get("cidade"):
            mec_params["cidade"] = params["cidade"]
        if params.get("estado"):
            mec_params["uf"] = params["estado"]
        if params.get("categoria"):
            mec_params["tipo"] = params["categoria"]
        mec_params["limite"] = min(params.get("limite", 10), 20)

        mec_result = _handle_buscar_escola_brasil(mec_params)
        mec_data = json.loads(mec_result)

        if mec_data.get("escolas"):
            mec_data["aviso"] = "Escola nao encontrada no banco CRM. Resultados da base completa do MEC (212k escolas)."
            return json.dumps(mec_data, ensure_ascii=False, default=str)

    return json.dumps({
        "total": 0, "escolas": [],
        "mensagem": "Nenhuma escola encontrada no banco nem na base MEC com esses filtros."
    }, ensure_ascii=False)


def _handle_importar_escola(params: Dict) -> str:
    """Importa uma escola da base MEC para o banco CRM."""
    df = _get_csv_df()
    if df is None:
        return json.dumps({"erro": "Base MEC (CSV) nao disponivel."})

    col_map = settings.get_csv_column_mapping()
    inep = params.get("inep")
    row = None

    # Buscar por INEP (prioritário)
    if inep:
        inep_str = str(inep).strip()
        matches = df[df[col_map["inep_code"]].astype(str).str.strip() == inep_str]
        if not matches.empty:
            row = matches.iloc[0]

    # Buscar por nome + cidade se não achou por INEP
    if row is None and params.get("nome"):
        nome_norm = _normalize(params["nome"])
        palavras = [p for p in nome_norm.split() if len(p) >= 2]
        mask = pd.Series(True, index=df.index)
        for palavra in palavras:
            mask &= df["_name_norm"].str.contains(palavra, na=False)
        if params.get("cidade"):
            mask &= df["_norm_city"].str.contains(_normalize(params["cidade"]), na=False)
        matches = df[mask]
        if len(matches) == 1:
            row = matches.iloc[0]
        elif len(matches) > 1:
            nomes = matches[col_map["name"]].head(5).tolist()
            return json.dumps({
                "erro": f"Encontrei {len(matches)} escolas com esse nome. Seja mais especifico ou informe o INEP.",
                "opcoes": nomes
            }, ensure_ascii=False)

    if row is None:
        return json.dumps({"erro": "Escola nao encontrada na base MEC."})

    inep_code = str(row.get(col_map["inep_code"])).strip()

    # Verificar se já existe no banco
    existing = db.get_company_by_inep(inep_code)
    if existing:
        return json.dumps({
            "mensagem": f"Escola '{existing['name']}' ja esta no banco CRM (status: {existing.get('status', 'raw')}).",
            "id": existing["id"],
            "ja_existia": True
        }, ensure_ascii=False)

    # Preparar dados para inserção
    lat = row.get("_clean_latitude")
    lng = row.get("_clean_longitude")

    company_data = {
        "name": str(row.get(col_map["name"])).strip(),
        "inep_code": inep_code,
        "city": row.get(col_map["city"]),
        "state": row.get(col_map["state"]),
        "address": row.get(col_map["address"]),
        "latitude": float(lat) if pd.notna(lat) else None,
        "longitude": float(lng) if pd.notna(lng) else None,
        "admin_category": row.get(col_map["admin_category"]),
        "admin_dependency": row.get(col_map["admin_dependency"]),
        "education_levels": row.get(col_map["education_levels"]),
        "school_size": row.get(col_map["size"]),
        "phone": row.get(col_map["phone"]) if pd.notna(row.get(col_map["phone"])) else None,
        "status": "raw",
        "source": "ialex_import",
    }

    try:
        company_id = db.insert_company(company_data)
        if company_id:
            return json.dumps({
                "sucesso": True,
                "mensagem": f"Escola '{company_data['name']}' importada para o CRM com sucesso!",
                "id": company_id,
                "inep": inep_code,
                "status": "raw",
                "proximo_passo": "Agora voce pode qualificar (rodar_pipeline) ou enriquecer contatos (enriquecer_contatos)."
            }, ensure_ascii=False)
        else:
            return json.dumps({"erro": "Falha ao inserir no banco. Verifique os logs."})
    except Exception as e:
        return json.dumps({"erro": f"Erro ao importar: {str(e)[:200]}"})


def _handle_buscar_escola_brasil(params: Dict) -> str:
    """Busca escolas na base completa do MEC (212k escolas do Brasil)."""
    df = _get_csv_df()
    if df is None:
        return json.dumps({"erro": "Base MEC (CSV) nao disponivel."})

    col_map = settings.get_csv_column_mapping()
    mask = pd.Series(True, index=df.index)

    if params.get("nome"):
        # Busca por TODAS as palavras (AND) — permite encontrar "La Salle - Carmo" com "La Salle Carmo"
        nome_norm = _normalize(params["nome"])
        palavras = [p for p in nome_norm.split() if len(p) >= 2]
        for palavra in palavras:
            mask &= df["_name_norm"].str.contains(palavra, na=False)
    if params.get("cidade"):
        mask &= df["_norm_city"].str.contains(_normalize(params["cidade"]), na=False)
    if params.get("uf"):
        mask &= df[col_map["state"]].str.upper() == params["uf"].upper()
    if params.get("porte"):
        mask &= df["_norm_size"].str.contains(_normalize(params["porte"]), na=False)
    if params.get("niveis_ensino"):
        mask &= df["_norm_education_levels"].str.contains(_normalize(params["niveis_ensino"]), na=False)
    if params.get("tipo"):
        mask &= df["_norm_admin_category"].str.contains(_normalize(params["tipo"]), na=False)
    if params.get("dependencia"):
        mask &= df["_norm_admin_dependency"].str.contains(_normalize(params["dependencia"]), na=False)
    if params.get("localizacao"):
        if "_norm_localizacao" in df.columns:
            mask &= df["_norm_localizacao"].str.contains(_normalize(params["localizacao"]), na=False)

    total_na_base = int(mask.sum())
    limite = min(params.get("limite", 10), 20)
    df_found = df[mask].head(limite)

    if df_found.empty:
        filtros = {k: v for k, v in params.items() if v and k != "limite"}
        return json.dumps({
            "total": 0, "escolas": [],
            "filtros_aplicados": filtros,
            "mensagem": "Nenhuma escola encontrada com esses filtros na base MEC."
        }, ensure_ascii=False)

    escolas = []
    for _, row in df_found.iterrows():
        lat = row.get("_clean_latitude")
        lng = row.get("_clean_longitude")
        lat = float(lat) if pd.notna(lat) else None
        lng = float(lng) if pd.notna(lng) else None

        escolas.append({
            "nome": row.get(col_map["name"]),
            "inep": str(row.get(col_map["inep_code"])),
            "cidade": row.get(col_map["city"]),
            "uf": row.get(col_map["state"]),
            "endereco": row.get(col_map["address"]),
            "telefone": row.get(col_map["phone"]) if pd.notna(row.get(col_map["phone"])) else None,
            "categoria": row.get(col_map["admin_category"]),
            "dependencia": row.get(col_map["admin_dependency"]),
            "niveis_ensino": row.get(col_map["education_levels"]),
            "porte": row.get(col_map["size"]),
            "localizacao": row.get("Localização") if "Localização" in df.columns else None,
            "latitude": lat,
            "longitude": lng,
            "coordenadas_disponiveis": lat is not None and lng is not None,
            "fonte": "base_mec",
            "in_db": False,
        })

    return json.dumps({
        "total_encontradas": total_na_base,
        "mostrando": len(escolas),
        "escolas": escolas,
        "aviso": f"Mostrando {len(escolas)} de {total_na_base} resultados da base MEC." if total_na_base > limite else None,
    }, ensure_ascii=False, default=str)


def _handle_escolas_proximas(params: Dict) -> str:
    """Busca escolas próximas a uma coordenada usando Haversine."""
    lat_center = params.get("latitude")
    lng_center = params.get("longitude")
    if lat_center is None or lng_center is None:
        return json.dumps({"erro": "Informe latitude e longitude."})

    raio_km = min(params.get("raio_km", 2), 50)
    limite = min(params.get("limite", 10), 20)
    fonte = params.get("fonte", "ambos")

    # Bounding box para pré-filtro rápido
    delta_lat = raio_km / 111.0
    delta_lng = raio_km / (111.0 * max(math.cos(math.radians(lat_center)), 0.01))

    resultados = []
    ineps_vistos = set()

    # --- Busca no banco ---
    if fonte in ("db", "ambos"):
        try:
            db_result = db.client.table("companies").select("*") \
                .gte("latitude", lat_center - delta_lat) \
                .lte("latitude", lat_center + delta_lat) \
                .gte("longitude", lng_center - delta_lng) \
                .lte("longitude", lng_center + delta_lng) \
                .limit(200).execute()

            for s in db_result.data:
                if s.get("latitude") is None or s.get("longitude") is None:
                    continue
                dist = _haversine_km(lat_center, lng_center, s["latitude"], s["longitude"])
                if dist <= raio_km:
                    inep = s.get("inep_code")
                    if inep:
                        ineps_vistos.add(str(inep))
                    resultados.append({
                        "nome": s["name"],
                        "inep": inep,
                        "cidade": s.get("city"),
                        "estado": s.get("state"),
                        "endereco": s.get("address"),
                        "telefone": s.get("phone"),
                        "categoria": s.get("admin_category"),
                        "porte": s.get("school_size"),
                        "niveis_ensino": s.get("education_levels"),
                        "status_pipeline": s.get("status"),
                        "score": s.get("qualification_score"),
                        "distancia_km": round(dist, 2),
                        "latitude": s["latitude"],
                        "longitude": s["longitude"],
                        "in_db": True,
                        "fonte": "banco",
                    })
        except Exception as e:
            logger.error(f"Erro buscando escolas proximas no DB: {e}")

    # --- Busca no CSV MEC ---
    if fonte in ("mec", "ambos"):
        df = _get_csv_df()
        if df is not None:
            col_map = settings.get_csv_column_mapping()
            lat_col = "_clean_latitude"
            lng_col = "_clean_longitude"

            if lat_col in df.columns and lng_col in df.columns:
                bbox_mask = (
                    df[lat_col].between(lat_center - delta_lat, lat_center + delta_lat) &
                    df[lng_col].between(lng_center - delta_lng, lng_center + delta_lng)
                )

                if params.get("tipo") and "_norm_admin_category" in df.columns:
                    bbox_mask &= df["_norm_admin_category"].str.contains(_normalize(params["tipo"]), na=False)
                if params.get("niveis_ensino") and "_norm_education_levels" in df.columns:
                    bbox_mask &= df["_norm_education_levels"].str.contains(_normalize(params["niveis_ensino"]), na=False)

                for _, row in df[bbox_mask].iterrows():
                    rlat = row[lat_col]
                    rlng = row[lng_col]
                    if pd.isna(rlat) or pd.isna(rlng):
                        continue
                    inep = str(row.get(col_map["inep_code"]))
                    if inep in ineps_vistos:
                        continue
                    dist = _haversine_km(lat_center, lng_center, float(rlat), float(rlng))
                    if dist <= raio_km:
                        ineps_vistos.add(inep)
                        resultados.append({
                            "nome": row.get(col_map["name"]),
                            "inep": inep,
                            "cidade": row.get(col_map["city"]),
                            "estado": row.get(col_map["state"]),
                            "endereco": row.get(col_map["address"]),
                            "telefone": row.get(col_map["phone"]) if pd.notna(row.get(col_map["phone"])) else None,
                            "categoria": row.get(col_map["admin_category"]),
                            "porte": row.get(col_map["size"]),
                            "niveis_ensino": row.get(col_map["education_levels"]),
                            "distancia_km": round(dist, 2),
                            "latitude": float(rlat),
                            "longitude": float(rlng),
                            "in_db": False,
                            "fonte": "base_mec",
                        })

    resultados.sort(key=lambda x: x["distancia_km"])
    resultados = resultados[:limite]

    return json.dumps({
        "ponto_central": {"latitude": lat_center, "longitude": lng_center},
        "raio_km": raio_km,
        "total_encontradas": len(resultados),
        "escolas": resultados,
        "aviso": "~40% das escolas na base MEC nao possuem coordenadas e nao aparecem nesta busca." if fonte in ("mec", "ambos") else None,
    }, ensure_ascii=False, default=str)


def _handle_enviar_aprovados(params: Dict) -> str:
    """Envia emails já aprovados na fila."""
    try:
        from workflows.send_approved import send_approved_messages
        limite = min(params.get("limite", 50), 50)
        result = send_approved_messages(limit=limite)
        return json.dumps({
            "enviados": result.get("sent", 0),
            "falharam": result.get("failed", 0),
            "pulados": result.get("skipped", 0),
            "detalhes": result.get("details", [])[:10],
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro ao enviar: {str(e)[:200]}"})


def _handle_gerar_followups(params: Dict) -> str:
    """Gera follow-ups para escolas que não responderam."""
    try:
        from workflows.follow_up_manager import run_follow_up_check
        limite = min(params.get("limite", 20), 50)
        result = run_follow_up_check(limit=limite)
        return json.dumps({
            "follow_ups_devidos": result.get("due_found", 0),
            "gerados": result.get("generated", 0),
            "erros": result.get("errors", 0),
            "detalhes": [
                {
                    "escola": d.get("company_name"),
                    "followup_numero": d.get("follow_up_number"),
                    "assunto": d.get("subject"),
                    "status": d.get("status"),
                }
                for d in result.get("details", [])[:10]
            ],
            "aviso": "Follow-ups gerados foram para a fila de aprovacao. Aprove antes de enviar."
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro nos follow-ups: {str(e)[:200]}"})


def _handle_tracking_emails(params: Dict) -> str:
    """Mostra resultados de emails: opens, clicks, replies."""
    try:
        from tools.email_tracker import email_tracker

        # Sincronizar eventos do Brevo se solicitado
        if params.get("sincronizar"):
            email_tracker.sync_tracking_events()

        # Timeline de escola específica
        if params.get("escola_id"):
            timeline = email_tracker.get_email_timeline(params["escola_id"])
            return json.dumps({
                "escola_id": params["escola_id"],
                "total_eventos": len(timeline),
                "timeline": timeline[:20],
            }, ensure_ascii=False, default=str)

        # Stats gerais
        dias = params.get("dias", 30)
        stats = email_tracker.get_tracking_stats(days=dias)
        return json.dumps({
            "periodo_dias": dias,
            "total_enviados": stats.get("total_sent", 0),
            "total_abertos": stats.get("total_opened", 0),
            "total_clicados": stats.get("total_clicked", 0),
            "total_respondidos": stats.get("total_replied", 0),
            "total_bounced": stats.get("total_bounced", 0),
            "taxa_abertura": f"{stats.get('open_rate', 0):.1f}%",
            "taxa_clique": f"{stats.get('click_rate', 0):.1f}%",
            "taxa_resposta": f"{stats.get('reply_rate', 0):.1f}%",
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro no tracking: {str(e)[:200]}"})


def _handle_editar_e_aprovar(params: Dict) -> str:
    """Edita e aprova um email na fila."""
    queue_id = params.get("queue_id")
    if not queue_id:
        return json.dumps({"erro": "Informe o queue_id da mensagem."})
    try:
        from approval_queue.queue_manager import queue_manager
        novo_assunto = params.get("novo_assunto")
        novo_corpo = params.get("novo_corpo")
        success = queue_manager.approve(queue_id, edited_subject=novo_assunto, edited_body=novo_corpo)
        if success:
            msg = "Email aprovado"
            if novo_assunto or novo_corpo:
                msg += " com edicoes"
            msg += "! Use enviar_aprovados para disparar."
            return json.dumps({"sucesso": True, "mensagem": msg})
        return json.dumps({"erro": "Falha ao aprovar. Verifique o queue_id."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_relatorio_pipeline(params: Dict) -> str:
    """Gera relatório completo do pipeline sob demanda."""
    try:
        # Escolas por status
        statuses = ["raw", "filtered", "qualified", "enriched", "contacted", "sent", "replied"]
        por_status = {}
        total = 0
        for status in statuses:
            result = db.client.table("companies").select("id", count="exact").eq("status", status).execute()
            count = result.count or 0
            por_status[status] = count
            total += count

        # Contatos e fila
        contatos = db.client.table("contacts").select("id", count="exact").execute()
        fila = db.client.table("approval_queue").select("id", count="exact").eq("status", "pending").execute()

        # Tracking (últimos 30 dias)
        tracking = {}
        try:
            from tools.email_tracker import email_tracker
            tracking = email_tracker.get_tracking_stats(days=30)
        except Exception:
            pass

        # Follow-ups pendentes
        followups_pendentes = 0
        try:
            from workflows.follow_up_manager import get_due_follow_ups
            followups_pendentes = len(get_due_follow_ups(limit=100))
        except Exception:
            pass

        return json.dumps({
            "total_escolas": total,
            "por_status": por_status,
            "total_contatos": contatos.count or 0,
            "emails_pendentes_aprovacao": fila.count or 0,
            "followups_pendentes": followups_pendentes,
            "emails_30d": {
                "enviados": tracking.get("total_sent", 0),
                "abertos": tracking.get("total_opened", 0),
                "respondidos": tracking.get("total_replied", 0),
                "taxa_abertura": f"{tracking.get('open_rate', 0):.1f}%",
                "taxa_resposta": f"{tracking.get('reply_rate', 0):.1f}%",
            },
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro no relatorio: {str(e)[:200]}"})


def _handle_atualizar_scores(params: Dict) -> str:
    """Recalcula scores baseado em engajamento."""
    try:
        from tools.dynamic_score import dynamic_scorer

        escola_id = params.get("escola_id")
        if escola_id:
            breakdown = dynamic_scorer.get_score_breakdown(escola_id)
            return json.dumps(breakdown, ensure_ascii=False, default=str)

        result = dynamic_scorer.update_all_scores()
        return json.dumps({
            "total_analisadas": result.get("total", 0),
            "atualizadas": result.get("updated", 0),
            "falharam": result.get("failed", 0),
            "mensagem": "Scores recalculados com base em engajamento (opens, clicks, replies, bounces)."
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro nos scores: {str(e)[:200]}"})


def _handle_registrar_reuniao(params: Dict) -> str:
    """Registra visita/reunião com escola."""
    company_id = params.get("escola_id")
    if not company_id and params.get("escola_nome"):
        r = db.client.table("companies").select("id,name").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            company_id = r.data[0]["id"]
        else:
            return json.dumps({"erro": f"Escola '{params['escola_nome']}' nao encontrada no banco."})

    if not company_id:
        return json.dumps({"erro": "Informe o nome ou ID da escola."})

    try:
        data_reuniao = params.get("data", datetime.now().strftime("%Y-%m-%d"))
        meeting_data = {
            "company_id": company_id,
            "scheduled_at": f"{data_reuniao}T10:00:00",
            "meeting_type": params.get("tipo", "in_person"),
            "status": "completed",
            "outcome": params.get("resultado", "follow_up"),
            "notes": params.get("notas", ""),
            "title": f"Visita - {params.get('escola_nome', 'Escola')}",
            "duration_minutes": 30,
        }

        result = db.client.table("meetings").insert(meeting_data).execute()
        if result.data:
            # Registrar interação
            db.client.table("interactions").insert({
                "company_id": company_id,
                "type": "meeting_scheduled",
                "channel": params.get("tipo", "in_person"),
                "subject": meeting_data["title"],
                "message_snippet": params.get("notas", ""),
            }).execute()

            return json.dumps({
                "sucesso": True,
                "mensagem": "Reuniao registrada com sucesso!",
                "meeting_id": result.data[0]["id"],
                "proximo_passo": "Score da escola sera ajustado (+50 pontos por reuniao) no proximo ciclo de atualizacao."
            }, ensure_ascii=False, default=str)
        return json.dumps({"erro": "Falha ao registrar reuniao."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_operacao_lote(params: Dict) -> str:
    """Operações em lote em múltiplas escolas."""
    acao = params.get("acao")
    limite = min(params.get("limite", 5), 20)

    if acao == "importar":
        if not params.get("cidade") and not params.get("uf"):
            return json.dumps({"erro": "Informe pelo menos cidade ou estado para importar em lote."})

        # Buscar escolas na base MEC
        mec_params = {"limite": limite}
        if params.get("cidade"):
            mec_params["cidade"] = params["cidade"]
        if params.get("uf"):
            mec_params["uf"] = params["uf"]
        if params.get("tipo"):
            mec_params["tipo"] = params["tipo"]
        if params.get("porte"):
            mec_params["niveis_ensino"] = "Fundamental"  # default ICP
            mec_params["porte"] = params["porte"]

        mec_result = json.loads(_handle_buscar_escola_brasil(mec_params))
        escolas = mec_result.get("escolas", [])

        importadas = 0
        ja_existiam = 0
        erros = 0
        for escola in escolas:
            inep = escola.get("inep")
            if inep:
                r = json.loads(_handle_importar_escola({"inep": inep}))
                if r.get("sucesso"):
                    importadas += 1
                elif r.get("ja_existia"):
                    ja_existiam += 1
                else:
                    erros += 1

        return json.dumps({
            "acao": "importar",
            "encontradas_mec": len(escolas),
            "importadas": importadas,
            "ja_existiam": ja_existiam,
            "erros": erros,
        }, ensure_ascii=False, default=str)

    elif acao == "qualificar":
        try:
            from workflows.daily_pipeline import run_pipeline
            result = run_pipeline(steps=["qualify"], qualify_limit=limite)
            return json.dumps({
                "acao": "qualificar",
                "resultado": result,
            }, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"erro": f"Erro na qualificacao: {str(e)[:200]}"})

    elif acao == "gerar_emails":
        try:
            from workflows.daily_pipeline import run_pipeline
            result = run_pipeline(steps=["write"], write_limit=limite)
            return json.dumps({
                "acao": "gerar_emails",
                "resultado": result,
                "aviso": "Emails gerados foram para a fila de aprovacao."
            }, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"erro": f"Erro na geracao: {str(e)[:200]}"})

    else:
        return json.dumps({"erro": f"Acao '{acao}' nao reconhecida. Use: importar, qualificar, gerar_emails"})


def _handle_melhor_horario(params: Dict) -> str:
    """Sugere melhor horário para envio de emails."""
    try:
        from tools.smart_scheduler import smart_scheduler
        analysis = smart_scheduler.get_schedule_analysis()
        return json.dumps({
            "melhores_horarios": analysis.get("best_hours", []),
            "melhores_dias": analysis.get("best_days", []),
            "proximo_envio_sugerido": analysis.get("next_suggested", ""),
            "baseado_em": f"{analysis.get('data_points', 0)} aberturas analisadas",
            "usando_defaults": analysis.get("using_defaults", True),
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_funil_vendas(params: Dict) -> str:
    """Mostra funil de conversão completo com gargalos."""
    try:
        etapas = [
            ("raw", "Importadas"),
            ("qualified", "Qualificadas"),
            ("enriched", "Enriquecidas"),
            ("contacted", "Contatadas"),
            ("sent", "Email enviado"),
            ("opened", "Email aberto"),
            ("replied", "Responderam"),
        ]

        funil = []
        anterior = None
        for status, label in etapas:
            result = db.client.table("companies").select("id", count="exact").eq("status", status).execute()
            count = result.count or 0
            taxa = None
            if anterior is not None and anterior > 0:
                taxa = round((count / anterior) * 100, 1)
            funil.append({
                "etapa": label,
                "status": status,
                "quantidade": count,
                "taxa_conversao": f"{taxa}%" if taxa is not None else None,
            })
            anterior = count if count > 0 else anterior

        # Reuniões
        meetings = db.client.table("meetings").select("id", count="exact").execute()

        # Identificar gargalo (menor taxa de conversão)
        gargalo = None
        menor_taxa = 100
        for item in funil:
            if item["taxa_conversao"] and float(item["taxa_conversao"].replace("%", "")) < menor_taxa:
                menor_taxa = float(item["taxa_conversao"].replace("%", ""))
                gargalo = item["etapa"]

        return json.dumps({
            "funil": funil,
            "reunioes": meetings.count or 0,
            "gargalo": gargalo,
            "recomendacao": f"Gargalo em '{gargalo}' ({menor_taxa}% de conversao). Foque nessa etapa." if gargalo else "Funil saudavel!",
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro no funil: {str(e)[:200]}"})


def _handle_buscar_contatos(params: Dict) -> str:
    company_id = params.get("escola_id")

    if not company_id and params.get("escola_nome"):
        r = db.client.table("companies").select("id,name").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            company_id = r.data[0]["id"]
        else:
            return json.dumps({"erro": f"Escola '{params['escola_nome']}' nao encontrada."})

    if not company_id:
        return json.dumps({"erro": "Informe o nome ou ID da escola."})

    result = db.client.table("contacts").select("*").eq("company_id", company_id).execute()
    contatos = []
    for c in result.data:
        contatos.append({
            "nome": c.get("full_name"),
            "cargo": c.get("role"),
            "email": c.get("email"),
            "telefone": c.get("phone"),
            "linkedin": c.get("linkedin_url"),
            "fonte": c.get("source"),
            "confianca": c.get("confidence_score"),
            "email_verificado": c.get("email_verified"),
        })

    return json.dumps({"total": len(contatos), "contatos": contatos}, ensure_ascii=False)


def _handle_estatisticas_gerais(params: Dict) -> str:
    stats = {}

    # Companies por status
    for status in ["raw", "filtered", "qualified", "enriched", "contacted", "sent", "opened", "replied"]:
        r = db.client.table("companies").select("id", count="exact").eq("status", status).execute()
        if r.count and r.count > 0:
            stats[f"escolas_{status}"] = r.count

    total = db.client.table("companies").select("id", count="exact").execute()
    stats["escolas_total"] = total.count or 0

    # Contacts
    contacts = db.client.table("contacts").select("id", count="exact").execute()
    stats["contatos_total"] = contacts.count or 0

    # Approval queue
    for s in ["pending", "approved", "rejected", "sent"]:
        r = db.client.table("approval_queue").select("id", count="exact").eq("status", s).execute()
        if r.count and r.count > 0:
            stats[f"fila_{s}"] = r.count

    # Interactions
    interactions = db.client.table("interactions").select("id", count="exact").execute()
    stats["interacoes_total"] = interactions.count or 0

    return json.dumps(stats, ensure_ascii=False)


def _handle_fila_aprovacao(params: Dict) -> str:
    query = db.client.table("approval_queue").select("*,companies(name,inep_code),contacts(full_name,email)")

    if params.get("status"):
        query = query.eq("status", params["status"])

    limite = min(params.get("limite", 10), 50)
    result = query.order("created_at", desc=True).limit(limite).execute()

    items = []
    for item in result.data:
        escola = item.get("companies", {}) or {}
        contato = item.get("contacts", {}) or {}
        items.append({
            "id": item["id"],
            "escola": escola.get("name", "?"),
            "contato": contato.get("full_name", "?"),
            "email_contato": contato.get("email", "?"),
            "assunto": item.get("subject"),
            "canal": item.get("channel"),
            "status": item.get("status"),
            "criado_em": item.get("created_at"),
            "corpo_preview": (item.get("body") or "")[:200],
        })

    return json.dumps({"total": len(items), "items": items}, ensure_ascii=False)


def _handle_aprovar_mensagem(params: Dict) -> str:
    if params.get("aprovar_todas"):
        pending = db.client.table("approval_queue").select("id").eq("status", "pending").execute()
        count = 0
        for item in pending.data:
            db.client.table("approval_queue").update({
                "status": "approved",
                "approved_at": datetime.now().isoformat()
            }).eq("id", item["id"]).execute()
            count += 1
        return json.dumps({"aprovadas": count, "mensagem": f"{count} mensagens aprovadas."})

    queue_id = params.get("queue_id")
    if not queue_id:
        return json.dumps({"erro": "Informe o ID da mensagem ou use aprovar_todas=true."})

    db.client.table("approval_queue").update({
        "status": "approved",
        "approved_at": datetime.now().isoformat()
    }).eq("id", queue_id).execute()
    return json.dumps({"aprovada": queue_id, "mensagem": "Mensagem aprovada com sucesso."})


def _handle_consultar_interacoes(params: Dict) -> str:
    company_id = params.get("escola_id")

    if not company_id and params.get("escola_nome"):
        r = db.client.table("companies").select("id,name").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            company_id = r.data[0]["id"]
        else:
            return json.dumps({"erro": f"Escola '{params['escola_nome']}' nao encontrada."})

    query = db.client.table("interactions").select("*")
    if company_id:
        query = query.eq("company_id", company_id)
    if params.get("tipo"):
        query = query.eq("type", params["tipo"])

    result = query.order("created_at", desc=True).limit(20).execute()

    interacoes = []
    for i in result.data:
        interacoes.append({
            "tipo": i.get("type"),
            "assunto": i.get("subject"),
            "preview": (i.get("message_snippet") or "")[:150],
            "data": i.get("created_at"),
            "metadata": i.get("metadata"),
        })

    return json.dumps({"total": len(interacoes), "interacoes": interacoes}, ensure_ascii=False)


def _handle_uso_apis(params: Dict) -> str:
    query = db.client.table("api_usage").select("api_name,credits_used,success,created_at")

    if params.get("api_name"):
        query = query.eq("api_name", params["api_name"])

    result = query.order("created_at", desc=True).limit(100).execute()

    # Agregar por API
    apis = {}
    for row in result.data:
        name = row.get("api_name", "?")
        if name not in apis:
            apis[name] = {"chamadas": 0, "creditos": 0, "sucesso": 0, "erro": 0}
        apis[name]["chamadas"] += 1
        apis[name]["creditos"] += row.get("credits_used", 0) or 0
        if row.get("success"):
            apis[name]["sucesso"] += 1
        else:
            apis[name]["erro"] += 1

    # Limites mensais
    limites = {"apollo": 60, "snov": 50, "hunter": 25, "perplexity": 200}
    for api, data in apis.items():
        if api in limites:
            data["limite_mensal"] = limites[api]
            data["restante"] = limites[api] - data["creditos"]

    return json.dumps(apis, ensure_ascii=False)


def _handle_detalhes_escola(params: Dict) -> str:
    escola = None

    if params.get("inep"):
        r = db.client.table("companies").select("*").eq("inep_code", params["inep"]).limit(1).execute()
        if r.data:
            escola = r.data[0]
    elif params.get("escola_nome"):
        r = db.client.table("companies").select("*").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            escola = r.data[0]

    if not escola:
        return json.dumps({"erro": "Escola nao encontrada."})

    # Buscar contatos
    contatos = db.client.table("contacts").select("full_name,role,email,phone,linkedin_url,source,confidence_score").eq("company_id", escola["id"]).execute()

    # Buscar interacoes recentes
    interacoes = db.client.table("interactions").select("type,subject,created_at").eq("company_id", escola["id"]).order("created_at", desc=True).limit(5).execute()

    # Buscar itens na fila
    fila = db.client.table("approval_queue").select("id,subject,status,channel,created_at").eq("company_id", escola["id"]).order("created_at", desc=True).limit(5).execute()

    return json.dumps({
        "escola": {
            "id": escola["id"],
            "nome": escola["name"],
            "inep": escola.get("inep_code"),
            "cidade": escola.get("city"),
            "estado": escola.get("state"),
            "endereco": escola.get("address"),
            "telefone": escola.get("phone"),
            "website": escola.get("website"),
            "categoria": escola.get("admin_category"),
            "dependencia": escola.get("admin_dependency"),
            "niveis_ensino": escola.get("education_levels"),
            "porte": escola.get("school_size"),
            "status": escola.get("status"),
            "score": escola.get("qualification_score"),
            "motivo_score": escola.get("qualification_reasoning"),
            "lat": escola.get("latitude"),
            "lon": escola.get("longitude"),
            "email_pattern": escola.get("email_pattern"),
            "email_domain": escola.get("email_domain"),
            "hubspot_id": escola.get("hubspot_company_id"),
        },
        "contatos": [{"nome": c.get("full_name"), "cargo": c.get("role"), "email": c.get("email"), "telefone": c.get("phone"), "linkedin": c.get("linkedin_url"), "fonte": c.get("source")} for c in contatos.data],
        "interacoes_recentes": [{"tipo": i.get("type"), "assunto": i.get("subject"), "data": i.get("created_at")} for i in interacoes.data],
        "fila_aprovacao": [{"id": f["id"], "assunto": f.get("subject"), "status": f.get("status"), "canal": f.get("channel")} for f in fila.data],
    }, ensure_ascii=False)


def _handle_gerar_email(params: Dict) -> str:
    escola_nome = params.get("escola_nome", "")
    if not escola_nome:
        return json.dumps({"erro": "Informe o nome da escola."})

    # Buscar dados da escola
    r = db.client.table("companies").select("*").ilike("name", f"%{escola_nome}%").limit(1).execute()
    if not r.data:
        return json.dumps({"erro": f"Escola '{escola_nome}' nao encontrada."})

    escola = r.data[0]
    contato_nome = params.get("contato_nome", "")
    contato_cargo = params.get("contato_cargo", "")
    contato_email = params.get("contato_email", "")

    # Se nao informou contato, buscar o primeiro
    if not contato_nome:
        contatos = db.client.table("contacts").select("*").eq("company_id", escola["id"]).limit(1).execute()
        if contatos.data:
            c = contatos.data[0]
            contato_nome = c.get("full_name", "")
            contato_cargo = contato_cargo or c.get("role", "")
            contato_email = contato_email or c.get("email", "")

    tom = params.get("tom", "amigavel")
    foco = params.get("foco", "apresentacao")

    # Gerar email usando OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")
    prompt = f"""Gere um email de prospecção B2B para a escola abaixo.
Tom: {tom}. Foco: {foco}.
Produto: IAprendo - plataforma de IA educacional alinhada à BNCC.

Escola: {escola.get('name')}
Cidade: {escola.get('city')}/{escola.get('state')}
Categoria: {escola.get('admin_category')}
Porte: {escola.get('school_size')}
Niveis: {escola.get('education_levels')}
Contato: {contato_nome} ({contato_cargo})

Regras:
- Assunto curto e atrativo (max 60 caracteres)
- Corpo do email: 3-4 paragrafos curtos
- Mencione o nome da escola e do contato
- Termine com CTA claro (agendar demo de 15 min)
- Assinatura: Fernando Nienaber, IAprendo

Responda em JSON: {{"assunto": "...", "corpo": "..."}}"""

    resp = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        import re
        raw = resp.choices[0].message.content
        match = re.search(r'\{[\s\S]*"assunto"[\s\S]*"corpo"[\s\S]*\}', raw)
        email_data = json.loads(match.group()) if match else {"assunto": "IAprendo para " + escola.get("name", ""), "corpo": raw}
    except Exception:
        email_data = {"assunto": "IAprendo - IA Educacional", "corpo": resp.choices[0].message.content}

    # Salvar na fila de aprovação
    queue_entry = {
        "company_id": escola["id"],
        "subject": email_data["assunto"],
        "body": email_data["corpo"],
        "channel": "email",
        "status": "pending",
    }
    if contato_email:
        # Buscar contact_id
        c = db.client.table("contacts").select("id").eq("email", contato_email).limit(1).execute()
        if c.data:
            queue_entry["contact_id"] = c.data[0]["id"]

    db.client.table("approval_queue").insert(queue_entry).execute()

    return json.dumps({
        "email_gerado": True,
        "escola": escola.get("name"),
        "contato": contato_nome,
        "email_destino": contato_email,
        "assunto": email_data["assunto"],
        "corpo": email_data["corpo"],
        "status": "Na fila de aprovacao (pending)"
    }, ensure_ascii=False)


def _handle_rejeitar_mensagem(params: Dict) -> str:
    queue_id = params.get("queue_id")
    if not queue_id:
        return json.dumps({"erro": "Informe o ID da mensagem."})

    motivo = params.get("motivo", "Rejeitado pelo Fernando")
    db.client.table("approval_queue").update({
        "status": "rejected",
        "rejection_reason": motivo,
    }).eq("id", queue_id).execute()

    return json.dumps({"rejeitada": queue_id, "motivo": motivo})


def _handle_atualizar_escola(params: Dict) -> str:
    escola_id = params.get("escola_id")

    if not escola_id and params.get("escola_nome"):
        r = db.client.table("companies").select("id,name").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            escola_id = r.data[0]["id"]
        else:
            return json.dumps({"erro": f"Escola '{params['escola_nome']}' nao encontrada."})

    if not escola_id:
        return json.dumps({"erro": "Informe o nome ou ID da escola."})

    updates = {}
    for field in ["status", "phone", "website"]:
        val = params.get(field) or params.get({"phone": "telefone"}.get(field, field))
        if val:
            updates[field] = val
    if params.get("notas"):
        updates["notes"] = params["notas"]

    if not updates:
        return json.dumps({"erro": "Nenhum campo para atualizar."})

    db.client.table("companies").update(updates).eq("id", escola_id).execute()
    return json.dumps({"atualizada": escola_id, "campos": updates}, ensure_ascii=False)


def _handle_rodar_pipeline(params: Dict) -> str:
    etapa = params.get("etapa", "qualify")
    limite = min(params.get("limite", 5), 50)

    if etapa == "qualify":
        # Buscar escolas raw para qualificar
        escolas = db.client.table("companies").select("id,name,education_levels,admin_category,school_size,city").eq("status", "raw").limit(limite).execute()

        if not escolas.data:
            return json.dumps({"mensagem": "Nenhuma escola com status 'raw' para qualificar."})

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        model = os.getenv("IALEX_MODEL", "gpt-4.1-mini")
        resultados = []

        for escola in escolas.data:
            try:
                prompt = f"""Qualifique esta escola como lead para a plataforma IAprendo (IA educacional BNCC).
Score de 0 a 100 (quanto maior, melhor fit).

Escola: {escola.get('name')}
Cidade: {escola.get('city')}
Categoria: {escola.get('admin_category')}
Porte: {escola.get('school_size')}
Niveis: {escola.get('education_levels')}

Criterios de qualificacao:
- Tem ensino fundamental (anos finais) ou medio? (+30 pontos)
- E privada? (+20 pontos, maior poder de compra)
- Porte medio/grande (200+ alunos)? (+20 pontos)
- Localizacao acessivel? (+10 pontos)
- Oferta diversificada de ensino? (+10 pontos)
- Outros fatores relevantes (+10 pontos)

Responda em JSON: {{"score": numero, "reasoning": "explicacao curta em 1-2 frases"}}"""

                resp = client.chat.completions.create(
                    model=model,
                    max_tokens=256,
                    messages=[{"role": "user", "content": prompt}]
                )

                import re
                raw = resp.choices[0].message.content
                match = re.search(r'\{[\s\S]*"score"[\s\S]*\}', raw)
                if match:
                    data = json.loads(match.group())
                    score = max(0, min(100, int(data.get("score", 50))))
                    reasoning = data.get("reasoning", "")
                else:
                    score = 50
                    reasoning = "Qualificacao automatica"

                db.client.table("companies").update({
                    "qualification_score": score,
                    "qualification_reasoning": reasoning,
                    "status": "qualified"
                }).eq("id", escola["id"]).execute()

                resultados.append({"escola": escola["name"], "score": score, "reasoning": reasoning})

            except Exception as e:
                resultados.append({"escola": escola["name"], "erro": str(e)[:100]})

        return json.dumps({"qualificadas": len(resultados), "resultados": resultados}, ensure_ascii=False)

    return json.dumps({"erro": f"Etapa '{etapa}' ainda nao implementada. Disponiveis: qualify"})


def _handle_consulta_livre(params: Dict) -> str:
    tabela = params.get("tabela")
    if not tabela:
        return json.dumps({"erro": "Informe a tabela."})

    tabelas_permitidas = {"companies", "contacts", "approval_queue", "interactions", "meetings", "api_usage", "campaigns"}
    if tabela not in tabelas_permitidas:
        return json.dumps({"erro": f"Tabela '{tabela}' nao permitida. Use: {', '.join(tabelas_permitidas)}"})

    campos = params.get("campos", "*")
    query = db.client.table(tabela).select(campos, count="exact")

    # Aplicar filtros
    for filtro in (params.get("filtros") or []):
        campo = filtro.get("campo")
        operador = filtro.get("operador", "eq")
        valor = filtro.get("valor")
        if not campo or valor is None:
            continue

        if operador == "eq":
            query = query.eq(campo, valor)
        elif operador == "neq":
            query = query.neq(campo, valor)
        elif operador == "gt":
            query = query.gt(campo, valor)
        elif operador == "gte":
            query = query.gte(campo, valor)
        elif operador == "lt":
            query = query.lt(campo, valor)
        elif operador == "lte":
            query = query.lte(campo, valor)
        elif operador == "like":
            query = query.like(campo, valor)
        elif operador == "ilike":
            query = query.ilike(campo, f"%{valor}%")

    if params.get("ordenar"):
        desc = params.get("ordem", "asc") == "desc"
        query = query.order(params["ordenar"], desc=desc)

    limite = min(params.get("limite", 20), 100)
    result = query.limit(limite).execute()

    if params.get("contar"):
        return json.dumps({"tabela": tabela, "total": result.count or 0})

    return json.dumps({"tabela": tabela, "total": result.count, "dados": result.data[:limite]}, ensure_ascii=False, default=str)


def _handle_enriquecer_contatos(params: Dict) -> str:
    escola_id = params.get("escola_id")
    escola_nome = params.get("escola_nome")

    # Buscar escola
    if not escola_id and escola_nome:
        r = db.client.table("companies").select("*").ilike("name", f"%{escola_nome}%").limit(1).execute()
        if r.data:
            escola = r.data[0]
            escola_id = escola["id"]
        else:
            return json.dumps({"erro": f"Escola '{escola_nome}' nao encontrada."})
    elif escola_id:
        r = db.client.table("companies").select("*").eq("id", escola_id).limit(1).execute()
        if r.data:
            escola = r.data[0]
        else:
            return json.dumps({"erro": "Escola nao encontrada com este ID."})
    else:
        return json.dumps({"erro": "Informe o nome ou ID da escola."})

    fonte = params.get("fonte")

    try:
        from agents.contact_finder import ContactFinderAgent
        finder = ContactFinderAgent()

        if fonte == "perplexity":
            # Usar apenas Perplexity
            from tools.perplexity_browser import perplexity_browser
            contatos_raw = perplexity_browser.search_school_contacts(
                escola.get("name", ""), escola.get("city", ""), escola.get("state", "")
            )
            # Salvar no banco
            salvos = 0
            for c in contatos_raw:
                try:
                    db.insert_contact({
                        "company_id": escola_id,
                        "full_name": c.get("full_name", "Desconhecido"),
                        "role": c.get("role", ""),
                        "email": c.get("email", ""),
                        "phone": c.get("phone", ""),
                        "source": "perplexity",
                        "confidence_score": c.get("confidence_score", 30),
                    })
                    salvos += 1
                except Exception:
                    pass
            return json.dumps({
                "fonte": "perplexity",
                "escola": escola.get("name"),
                "contatos_encontrados": len(contatos_raw),
                "salvos_no_banco": salvos,
                "contatos": contatos_raw
            }, ensure_ascii=False, default=str)
        else:
            # Cascade completa
            contatos = finder.find_contacts(escola)
            resultado = []
            for c in contatos:
                resultado.append({
                    "nome": c.get("full_name", "?"),
                    "cargo": c.get("role", "?"),
                    "email": c.get("email", ""),
                    "telefone": c.get("phone", ""),
                    "fonte": c.get("source", "?"),
                    "confianca": c.get("confidence_score", 0),
                })
            return json.dumps({
                "escola": escola.get("name"),
                "contatos_encontrados": len(resultado),
                "contatos": resultado
            }, ensure_ascii=False, default=str)

    except Exception as e:
        logger.error("Erro no enriquecimento", extra={"error": str(e)})
        return json.dumps({"erro": f"Erro ao buscar contatos: {str(e)[:200]}"})


def _handle_sincronizar_hubspot(params: Dict) -> str:
    """Sincroniza dados com HubSpot CRM."""
    try:
        from integrations.hubspot_sync import hubspot_sync
        escola_id = params.get("escola_id")
        limite = min(params.get("limite", 10), 50)

        if escola_id:
            empresa = db.client.table("companies").select("*").eq("id", escola_id).single().execute()
            if not empresa.data:
                return json.dumps({"erro": "Escola nao encontrada no banco."})
            result = hubspot_sync.sync_company(empresa.data)
            return json.dumps({"resultado": result}, ensure_ascii=False, default=str)

        # Sync em lote: escolas com status enriched+
        escolas = db.client.table("companies").select("*").in_(
            "status", ["enriched", "contacted", "sent", "replied"]
        ).limit(limite).execute()

        resultados = {"sincronizadas": 0, "erros": 0}
        for escola in escolas.data:
            try:
                hubspot_sync.sync_company(escola)
                contatos = db.client.table("contacts").select("*").eq("company_id", escola["id"]).execute()
                for contato in contatos.data:
                    hubspot_sync.sync_contact(contato, escola.get("hubspot_id", ""))
                resultados["sincronizadas"] += 1
            except Exception:
                resultados["erros"] += 1

        return json.dumps(resultados, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro HubSpot: {str(e)[:200]}"})


def _handle_sincronizar_hubspot_puxar(params: Dict) -> str:
    """Puxa mudancas do HubSpot para o Supabase (sincronizacao reversa)."""
    try:
        from integrations.hubspot_pull import hubspot_pull
        result = hubspot_pull.pull_changes()
        total = result.get("companies", 0) + result.get("contacts", 0) + result.get("deals", 0)
        return json.dumps({
            "total_atualizados": total,
            "empresas": result.get("companies", 0),
            "contatos": result.get("contacts", 0),
            "deals": result.get("deals", 0),
            "erros": result.get("errors", 0),
            "desde": result.get("since"),
            "mensagem": f"Pull concluido: {total} registros atualizados do HubSpot." if total > 0 else "Nenhuma mudanca nova no HubSpot desde a ultima sincronizacao.",
        }, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro no pull HubSpot: {str(e)[:200]}"})


def _resolve_escola_id(params: Dict) -> Optional[str]:
    """Helper: resolve escola_id a partir de escola_id ou escola_nome."""
    eid = params.get("escola_id")
    if eid:
        return eid
    nome = params.get("escola_nome")
    if nome:
        try:
            r = db.client.table("companies").select("id").ilike("name", f"%{nome}%").limit(1).execute()
            if r.data:
                return r.data[0]["id"]
        except Exception:
            pass
    return None


def _handle_lembrar_fato(params: Dict) -> str:
    """Grava um fato na memoria persistente do IAlex."""
    try:
        from integrations.memory import memory
        if not memory.is_available():
            return json.dumps({
                "erro": "Tabela conversation_memory nao existe. Aplique a migration 005 no Supabase.",
                "sql": "Execute o SQL em database/migrations/005_conversation_memory.py no Supabase SQL Editor."
            })

        conteudo = params.get("conteudo", "").strip()
        if not conteudo:
            return json.dumps({"erro": "Informe o conteudo da memoria."})

        escopo_br = params.get("escopo", "global")
        escopo = {"escola": "company", "contato": "contact", "global": "global"}.get(escopo_br, "global")

        scope_id = None
        if escopo == "company":
            scope_id = _resolve_escola_id(params)
            if not scope_id:
                return json.dumps({"erro": "Escola nao encontrada. Informe escola_id ou escola_nome."})
        elif escopo == "contact":
            scope_id = params.get("contato_id")
            if not scope_id:
                return json.dumps({"erro": "Informe contato_id quando escopo=contato."})

        mem_id = memory.remember(
            content=conteudo,
            scope=escopo,
            scope_id=scope_id,
            category=params.get("categoria", "fact"),
            importance=params.get("importancia", 5),
            source="ialex",
        )
        if mem_id:
            return json.dumps({
                "sucesso": True,
                "memoria_id": mem_id,
                "mensagem": f"Memoria guardada! Vou lembrar disso sempre que falarmos sobre {'essa ' + escopo_br if escopo != 'global' else 'isso'}.",
            }, ensure_ascii=False)
        return json.dumps({"erro": "Falha ao gravar memoria."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_buscar_memorias(params: Dict) -> str:
    """Busca memorias do IAlex."""
    try:
        from integrations.memory import memory
        if not memory.is_available():
            return json.dumps({"erro": "Memoria nao disponivel. Aplique a migration 005."})

        escopo_br = params.get("escopo", "global")
        limite = min(params.get("limite", 10), 50)

        if escopo_br == "texto":
            texto = params.get("texto", "")
            if not texto:
                return json.dumps({"erro": "Informe o texto para buscar."})
            results = memory.search(texto, limit=limite)
        else:
            escopo = {"escola": "company", "contato": "contact", "global": "global"}.get(escopo_br, "global")
            scope_id = None
            if escopo == "company":
                scope_id = _resolve_escola_id(params)
            elif escopo == "contact":
                scope_id = params.get("contato_id")
            results = memory.get_for(escopo, scope_id, limit=limite, include_global=(escopo != "global"))

        if not results:
            return json.dumps({"total": 0, "memorias": [], "mensagem": "Nenhuma memoria encontrada."})

        mems = [
            {
                "id": m.get("id"),
                "conteudo": m.get("content"),
                "categoria": m.get("category"),
                "importancia": m.get("importance"),
                "escopo": m.get("scope"),
                "criada_em": (m.get("created_at") or "")[:10],
            }
            for m in results
        ]
        return json.dumps({"total": len(mems), "memorias": mems}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_esquecer_memoria(params: Dict) -> str:
    """Remove uma memoria especifica."""
    try:
        from integrations.memory import memory
        mem_id = params.get("memoria_id")
        if not mem_id:
            return json.dumps({"erro": "Informe memoria_id."})
        if memory.forget(mem_id):
            return json.dumps({"sucesso": True, "mensagem": "Memoria removida."})
        return json.dumps({"erro": "Falha ao remover memoria."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_listar_campanhas(params: Dict) -> str:
    """Lista campanhas de prospecção."""
    try:
        query = db.client.table("campaigns").select("*")
        if params.get("status"):
            query = query.eq("status", params["status"])
        result = query.order("created_at", desc=True).limit(20).execute()

        campanhas = []
        for c in result.data:
            campanhas.append({
                "id": c["id"],
                "nome": c["name"],
                "status": c.get("status"),
                "canal": c.get("channel"),
                "enviados": c.get("total_sent", 0),
                "abertos": c.get("total_opened", 0),
                "respondidos": c.get("total_replied", 0),
                "criada_em": c.get("created_at"),
            })
        return json.dumps({"total": len(campanhas), "campanhas": campanhas}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_criar_campanha(params: Dict) -> str:
    """Cria nova campanha de prospecção."""
    try:
        campaign_data = {
            "name": params["nome"],
            "description": params.get("descricao", ""),
            "channel": params.get("canal", "email"),
            "target_filters": {"descricao": params.get("filtros", "")},
            "status": "draft",
        }
        result = db.client.table("campaigns").insert(campaign_data).execute()
        if result.data:
            return json.dumps({
                "sucesso": True,
                "campanha_id": result.data[0]["id"],
                "mensagem": f"Campanha '{params['nome']}' criada com status draft. Mude para 'active' quando iniciar."
            }, ensure_ascii=False, default=str)
        return json.dumps({"erro": "Falha ao criar campanha."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_listar_templates(params: Dict) -> str:
    """Lista templates de email."""
    try:
        result = db.client.table("message_templates").select("*").eq("is_active", True).execute()
        templates = []
        for t in result.data:
            templates.append({
                "id": t["id"],
                "nome": t.get("name"),
                "assunto": t.get("subject_template"),
                "ativo": t.get("is_active"),
                "default": t.get("is_default", False),
                "role_alvo": t.get("role_target", "Todos"),
            })
        return json.dumps({"total": len(templates), "templates": templates}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_criar_template(params: Dict) -> str:
    """Cria novo template de email."""
    try:
        template_data = {
            "name": params["nome"],
            "subject_template": params["assunto"],
            "body_template": params["corpo"],
            "is_active": params.get("ativo", True),
            "is_default": False,
            "role_target": "Todos",
        }
        result = db.client.table("message_templates").insert(template_data).execute()
        if result.data:
            return json.dumps({
                "sucesso": True,
                "template_id": result.data[0]["id"],
                "mensagem": f"Template '{params['nome']}' criado! Variaveis disponiveis: {{contact_name}}, {{school_name}}, {{city}}, {{sender_name}}, {{meeting_link}}"
            }, ensure_ascii=False, default=str)
        return json.dumps({"erro": "Falha ao criar template."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_enviar_whatsapp_escola(params: Dict) -> str:
    """Coloca mensagem WhatsApp na fila de aprovação."""
    company_id = params.get("escola_id")
    if not company_id and params.get("escola_nome"):
        r = db.client.table("companies").select("id,name,phone").ilike("name", f"%{params['escola_nome']}%").limit(1).execute()
        if r.data:
            company_id = r.data[0]["id"]
            phone = r.data[0].get("phone")
        else:
            return json.dumps({"erro": f"Escola '{params['escola_nome']}' nao encontrada."})
    else:
        empresa = db.client.table("companies").select("name,phone").eq("id", company_id).single().execute()
        phone = empresa.data.get("phone") if empresa.data else None

    if not phone:
        return json.dumps({"erro": "Escola nao tem telefone cadastrado. Nao e possivel enviar WhatsApp."})

    try:
        queue_data = {
            "company_id": company_id,
            "subject": f"WhatsApp - {params.get('contato_nome', 'Escola')}",
            "body": params["mensagem"],
            "channel": "whatsapp",
            "status": "pending",
        }
        result = db.client.table("approval_queue").insert(queue_data).execute()
        if result.data:
            return json.dumps({
                "sucesso": True,
                "queue_id": result.data[0]["id"],
                "telefone_destino": phone,
                "mensagem": "Mensagem WhatsApp adicionada na fila de aprovacao. Aprove para enviar."
            }, ensure_ascii=False, default=str)
        return json.dumps({"erro": "Falha ao adicionar na fila."})
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_score_preditivo(params: Dict) -> str:
    """Analisa escolas com ML e prevê quais têm mais chance de fechar."""
    try:
        from tools.predictive_scorer import predictive_scorer

        # Se pediu escola especifica, retornar predicao detalhada
        escola_id = params.get("escola_id")
        if escola_id:
            return json.dumps(
                predictive_scorer.predict_company(escola_id),
                ensure_ascii=False, default=str,
            )

        # Senao, retornar ranking
        limite = min(params.get("limite", 10), 30)
        min_score = params.get("score_minimo", 0)
        result = predictive_scorer.rank_companies(limit=limite, min_score=min_score)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


def _handle_treinar_modelo_preditivo(params: Dict) -> str:
    """Treina o modelo preditivo com dados atuais."""
    try:
        from tools.predictive_scorer import predictive_scorer
        result = predictive_scorer.train()
        if result.get("trained"):
            result["mensagem"] = (
                f"Modelo treinado com sucesso! {result['samples']} escolas, "
                f"{result['positives']} positivos, accuracy {result['accuracy']}."
            )
        else:
            result["mensagem"] = result.get("reason", "Treino nao realizado")
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro ao treinar: {str(e)[:200]}"})


def _handle_info_modelo_preditivo(params: Dict) -> str:
    """Retorna informacoes do modelo preditivo."""
    try:
        from tools.predictive_scorer import predictive_scorer
        info = predictive_scorer.model_info()
        if info.get("treinado"):
            info["status"] = f"Modelo treinado com {info['amostras']} amostras ({info['positivos']} positivos). Accuracy: {info['accuracy']}."
        else:
            info["status"] = "Modelo ainda nao foi treinado. Usando pesos heuristicos."
        return json.dumps(info, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"erro": f"Erro: {str(e)[:200]}"})


TOOL_HANDLERS = {
    # Busca e gestão de escolas
    "consultar_escolas": _handle_consultar_escolas,
    "buscar_escola_brasil": _handle_buscar_escola_brasil,
    "escolas_proximas": _handle_escolas_proximas,
    "importar_escola": _handle_importar_escola,
    "detalhes_escola": _handle_detalhes_escola,
    "atualizar_escola": _handle_atualizar_escola,
    # Contatos
    "buscar_contatos": _handle_buscar_contatos,
    "enriquecer_contatos": _handle_enriquecer_contatos,
    # Pipeline e qualificação
    "rodar_pipeline": _handle_rodar_pipeline,
    "operacao_lote": _handle_operacao_lote,
    "atualizar_scores": _handle_atualizar_scores,
    # Emails e comunicação
    "gerar_email": _handle_gerar_email,
    "fila_aprovacao": _handle_fila_aprovacao,
    "aprovar_mensagem": _handle_aprovar_mensagem,
    "rejeitar_mensagem": _handle_rejeitar_mensagem,
    "editar_e_aprovar": _handle_editar_e_aprovar,
    "enviar_aprovados": _handle_enviar_aprovados,
    "gerar_followups": _handle_gerar_followups,
    # Analytics e tracking
    "tracking_emails": _handle_tracking_emails,
    "estatisticas_gerais": _handle_estatisticas_gerais,
    "relatorio_pipeline": _handle_relatorio_pipeline,
    "funil_vendas": _handle_funil_vendas,
    "melhor_horario": _handle_melhor_horario,
    # Reuniões e interações
    "registrar_reuniao": _handle_registrar_reuniao,
    "consultar_interacoes": _handle_consultar_interacoes,
    # HubSpot e integrações
    "sincronizar_hubspot": _handle_sincronizar_hubspot,
    "sincronizar_hubspot_puxar": _handle_sincronizar_hubspot_puxar,
    # Memoria persistente
    "lembrar_fato": _handle_lembrar_fato,
    "buscar_memorias": _handle_buscar_memorias,
    "esquecer_memoria": _handle_esquecer_memoria,
    # Campanhas e templates
    "listar_campanhas": _handle_listar_campanhas,
    "criar_campanha": _handle_criar_campanha,
    "listar_templates": _handle_listar_templates,
    "criar_template": _handle_criar_template,
    # WhatsApp para escolas
    "enviar_whatsapp_escola": _handle_enviar_whatsapp_escola,
    # Score preditivo (ML)
    "score_preditivo": _handle_score_preditivo,
    "treinar_modelo_preditivo": _handle_treinar_modelo_preditivo,
    "info_modelo_preditivo": _handle_info_modelo_preditivo,
    # Utilitários
    "uso_apis": _handle_uso_apis,
    "consulta_livre": _handle_consulta_livre,
}


# ===========================================================================
# SYSTEM PROMPT
# ===========================================================================

SYSTEM_PROMPT = """Voce e o *IAlex*, o especialista #1 em escolas do Brasil e assistente de vendas do Fernando para a plataforma *IAprendo*.

Voce tem acesso a:
- *Banco de dados CRM*: escolas ja importadas, qualificadas, com contatos e pipeline de vendas
- *Base completa do MEC*: 212.386 escolas de TODO o Brasil (nome, endereco, telefone, porte, niveis de ensino, tipo, coordenadas)
- *Busca por proximidade*: encontrar escolas perto de qualquer coordenada em qualquer raio

== SEU PAPEL ==
1. *ESPECIALISTA EM ESCOLAS*: Encontrar qualquer escola do Brasil por nome, cidade, estado, porte, tipo, niveis de ensino, proximidade ou qualquer combinacao
2. *COMPANHEIRO DE CAMPO*: Quando Fernando esta na rua visitando escolas, ajuda-lo a encontrar escolas perto, dar informacoes rapidas, registrar visitas
3. *AGENTE DE VENDAS*: Qualificar leads, enriquecer contatos, gerar emails, acompanhar pipeline, sugerir acoes comerciais

== ESCOLHA DE FERRAMENTAS (27 disponiveis) ==

*Buscar escolas:*
- Escola especifica ou por nome/cidade → *consultar_escolas* (banco + fallback MEC)
- Filtros avancados (porte, tipo, nivel, rural/urbana) → *buscar_escola_brasil*
- Por proximidade/localizacao → *escolas_proximas*
- Importar para o CRM → *importar_escola*
- Importar varias de uma vez → *operacao_lote* (acao: importar)

*Contatos e emails:*
- Ver contatos de escola → *buscar_contatos*
- Buscar novos contatos via APIs → *enriquecer_contatos*
- Criar email personalizado → *gerar_email*
- Ver fila de aprovacao → *fila_aprovacao*
- Aprovar email → *aprovar_mensagem*
- Editar e aprovar → *editar_e_aprovar*
- Rejeitar email → *rejeitar_mensagem*
- Disparar emails aprovados → *enviar_aprovados*
- Gerar follow-ups → *gerar_followups*

*Analytics e relatorios:*
- Resultados de emails (opens, clicks, replies) → *tracking_emails*
- Relatorio completo do pipeline → *relatorio_pipeline*
- Funil de conversao com gargalos → *funil_vendas*
- Melhor horario para enviar → *melhor_horario*
- Recalcular scores de engajamento → *atualizar_scores*

*Reunioes e gestao:*
- Registrar visita/reuniao → *registrar_reuniao*
- Qualificar escolas em lote → *operacao_lote* (acao: qualificar)
- Gerar emails em lote → *operacao_lote* (acao: gerar_emails)

== REGRA CRITICA: FLUXO DE IMPORTACAO ==
Quando Fernando pedir para buscar uma escola e depois quiser adicionar ao banco/CRM:
1. Busque a escola (consultar_escolas ou buscar_escola_brasil)
2. Mostre os dados encontrados
3. Se Fernando disser "sim", "adiciona", "importa", "coloca no banco" ou qualquer confirmacao:
   -> Use IMEDIATAMENTE a ferramenta *importar_escola* passando o INEP da escola que voce acabou de encontrar
   -> NUNCA peca o INEP ao Fernando — voce ja tem o INEP dos resultados da busca anterior
   -> NUNCA peca o ID — voce nao precisa, o INEP e suficiente
   -> NUNCA diga que "nao tem permissao" ou "nao esta disponivel" — voce TEM a ferramenta importar_escola
   -> Faca em UMA UNICA ACAO, sem pedir confirmacoes extras
4. Apos importar, informe e sugira proximos passos (qualificar, enriquecer contatos)

IMPORTAR ESCOLA NAO E ACAO SENSIVEL. Nao peca confirmacao extra. Se o Fernando pediu para importar, FACA.

== REGRA CRITICA: SO ATUE NA ESCOLA DA CONVERSA ATUAL ==
- NUNCA faca acoes em escolas de conversas anteriores sem que Fernando mencione explicitamente
- Cada pedido do Fernando se refere APENAS a escola que acabou de ser discutida
- Se Fernando diz "importa", ele quer importar a escola que ACABOU de ser buscada, nao outra

== COMPORTAMENTO PROATIVO ==
- Quando a busca for vaga (so nome ou so cidade), PERGUNTE para refinar: tipo (publica/privada)? porte? niveis de ensino?
- Quando Fernando mencionar localizacao ou bairro, SUGIRA busca por proximidade e pergunte o raio
- Apos encontrar uma escola na base MEC que NAO esta no CRM, pergunte: "Quer que eu adicione ao nosso banco?"
- Quando encontrar escolas grandes (500+ alunos) ou privadas, DESTAQUE como alvo de alto valor

== MEMORIA PERSISTENTE (CRITICO) ==
Voce tem uma MEMORIA PERSISTENTE que atravessa sessoes. Use-a agressivamente:

*QUANDO GRAVAR (lembrar_fato):*
- Fernando menciona qualquer preferencia de contato ("X prefere WhatsApp") → category=preference
- Fernando compartilha fato sobre escola ("tem 1200 alunos", "usa Google Classroom") → category=fact
- Insight comercial ("reagiu bem ao case BNCC", "prioridade alta em setembro") → category=insight
- Aviso importante ("diretor de licenca", "nao contatar em julho") → category=warning
- Lembrete ("retornar em 3 meses") → category=reminder
- Dados sobre Fernando ou o negocio → escopo=global
- Sempre defina importancia adequada: 1-3 (baixa), 4-6 (media), 7-10 (critica)

*QUANDO USAR (buscar_memorias ou memorias injetadas no contexto):*
- Antes de gerar um email, VERIFIQUE se ha memorias sobre a escola/contato que mudem a abordagem
- Se Fernando pergunta sobre uma escola, CITE memorias relevantes no inicio da resposta
- Memorias globais importantes ja vem injetadas automaticamente no contexto — use-as
- Se Fernando contradiz uma memoria antiga, ATUALIZE (grave nova, esqueca antiga)

*EXEMPLOS:*
- Fernando: "O diretor do La Salle so atende de tarde"
  → CHAMAR lembrar_fato: conteudo="Diretor do La Salle so atende a tarde", escopo=escola, escola_nome="La Salle", categoria=preference, importancia=7
- Fernando: "Lembra algo do Anchieta?"
  → CHAMAR buscar_memorias: escopo=escola, escola_nome="Anchieta"
- Fernando: "Esqueci, qual minha abordagem favorita?"
  → CHAMAR buscar_memorias: escopo=global

NUNCA deixe de gravar um fato importante. A memoria vale mais que qualquer ferramenta — e o que diferencia o IAlex de um bot comum.

== SCORE PREDITIVO COM MACHINE LEARNING ==
Voce tem um modelo de ML (Logistic Regression) que preve probabilidade de fechamento de cada escola.

*Quando usar score_preditivo:*
- "Quais escolas tem mais chance de fechar?" → rank por ML
- "Qual o score preditivo do Colegio X?" → passar escola_id para predicao detalhada
- "Me mostra top 10 oportunidades com score > 70" → usar score_minimo

*Quando usar treinar_modelo_preditivo:*
- Depois de receber respostas/reunioes novas (ensina o modelo)
- Fernando pede explicitamente: "retreine o modelo", "atualiza as previsoes"
- Automaticamente roda todo domingo 03:00

*Quando usar info_modelo_preditivo:*
- Fernando pergunta: "como esta o modelo?", "ja foi treinado?", "qual a accuracy?"

*Explicabilidade:* O modelo retorna `fatores_top` quando analisa uma escola especifica — use esses fatores para explicar POR QUE uma escola tem score alto ou baixo. Ex: "Essa escola tem 85% de chance porque tem *taxa de resposta alta* (+2.3) e *email do diretor* (+1.8)".

== FORMATACAO WHATSAPP (SOFISTICADA) ==
Suas respostas devem ser VISUALMENTE RICAS e bem organizadas. Use TODOS estes recursos:

*Formatacao:*
- *negrito* para titulos, nomes de escolas e destaques (UM asterisco)
- _italico_ para observacoes e dicas
- Monoespaco para codigos e valores: ```texto```
- NUNCA use **duplo**, ## markdown ou [links](url)

*Emojis como icones visuais (USE SEMPRE):*
- 🏫 escola/nome  📍 endereco/localizacao  📞 telefone  📧 email
- 📊 score/metricas  👤 contato/decisor  ✅ sucesso  ❌ erro
- 🔍 busca  📥 importar  📝 email gerado  🎯 qualificacao
- 📈 pipeline/funil  🔄 follow-up  📋 lista  ⚡ acao rapida
- 🏆 destaque/alto valor  📌 importante  💡 dica

*Organizacao de dados (OBRIGATORIO):*
Quando mostrar dados de escola, use este formato:

🏫 *NOME DA ESCOLA*
📍 Endereco completo
📞 Telefone
🎯 Score: XX | Porte: XXX alunos
📋 Tipo: Privada | Niveis: Fundamental, Medio

Quando listar varias escolas, separe com linha em branco e numere:

1️⃣ *Escola A* — Cidade (Score: 85)
2️⃣ *Escola B* — Cidade (Score: 72)
3️⃣ *Escola C* — Cidade (Score: 68)

*Secoes de resposta:*
Use emojis como marcadores de secao quando a resposta tiver multiplas partes:

📊 *Resumo*
(dados aqui)

⚡ *Proximos passos*
(sugestoes aqui)

A resposta deve parecer PROFISSIONAL e ORGANIZADA, como um relatorio de CRM.

== BOTOES DE RESPOSTA RAPIDA (IMPORTANTE) ==
Quando sua resposta envolver uma pergunta ou sugerir proximos passos, ADICIONE botoes no FINAL da mensagem:

Formato: [BOTOES: Opcao 1 | Opcao 2 | Opcao 3]

Maximo 3 botoes. Texto curto (1-4 palavras cada).

Exemplos de quando usar:
- Escola encontrada: [BOTOES: Importar | Ver contatos | Buscar outra]
- Escola importada: [BOTOES: Qualificar | Buscar contatos | Gerar email]
- Email gerado: [BOTOES: Aprovar | Editar | Rejeitar]
- Confirmacao: [BOTOES: Sim | Nao]
- Sugerir acoes: [BOTOES: Qualificar | Enriquecer | Ambos]
- Pipeline: [BOTOES: Enviar aprovados | Follow-ups | Ver funil]

Regras: botoes na ULTIMA LINHA, sem nada depois. Use em TODA resposta com decisao.

== REGRAS GERAIS ==
- Respostas concisas mas COMPLETAS. Max 4000 caracteres.
- Quando consultar dados, MOSTRE resultados organizados (nome, endereco, telefone, porte)
- ACOES SENSIVEIS (requerem confirmacao): aprovar/enviar emails, rodar pipeline completo, enriquecer contatos (consome API)
- ACOES NAO SENSIVEIS (faca direto quando pedido): buscar escolas, importar escola, consultar dados, atualizar notas
- Se encontrar muitos resultados, mostre os mais relevantes e pergunte se quer mais
- Responda SEMPRE em portugues brasileiro
- SEMPRE USE AS FERRAMENTAS quando Fernando pedir algo — nunca diga "nao posso" se existe uma ferramenta que faz isso

== CONTEXTO DO NEGOCIO ==
- *IAprendo*: plataforma de IA educacional alinhada a BNCC
- Publico-alvo: escolas de ensino fundamental (anos finais) e medio
- Foco atual: Porto Alegre/RS, expandindo para todo o Brasil
- Pipeline: Base MEC (212k) -> Importacao -> Qualificacao IA (score 0-100) -> Enriquecimento -> Contato -> Email -> Follow-up
- Score 0-100: qualificacao automatica (quanto maior, melhor fit para IAprendo)
- NUNCA enviar email/mensagem sem aprovacao do Fernando
"""

MAX_HISTORY = 10  # Reduzido para evitar que conversas antigas vazem para novas


# ===========================================================================
# BRAIN
# ===========================================================================

def _convert_tools_to_openai() -> List[Dict]:
    """Converte TOOLS do formato Anthropic para OpenAI function calling."""
    openai_tools = []
    for tool in TOOLS:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            }
        })
    return openai_tools


OPENAI_TOOLS = _convert_tools_to_openai()


class Brain:
    """
    Cerebro do IAlex com Tool Use (OpenAI GPT-4.1-mini).
    Consulta o banco diretamente via ferramentas e gera
    respostas naturais e ricas.
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client: OpenAI = OpenAI(api_key=api_key)
        self.model: str = os.getenv("IALEX_MODEL", "gpt-4.1-mini")
        self.conversation_history: List[Dict[str, Any]] = []
        logger.info("Brain inicializado", extra={"model": self.model})

    def _build_contextual_system_prompt(self, current_message: str) -> str:
        """Constroi system prompt com memorias relevantes injetadas.
        - Sempre inclui memorias globais importantes
        - Se detectar nome de escola na mensagem/historico, inclui memorias dessa escola
        """
        try:
            from integrations.memory import memory
            if not memory.is_available():
                return SYSTEM_PROMPT

            parts = [SYSTEM_PROMPT]

            # 1. Memorias globais importantes (top 5)
            globals_mem = memory.get_for("global", limit=5)
            if globals_mem:
                parts.append("\n== MEMORIAS GLOBAIS (sobre Fernando/negocio) ==")
                parts.append(memory.format_for_context(globals_mem))

            # 2. Detectar escolas mencionadas nas ultimas 3 mensagens + atual
            recent_text = current_message
            for msg in self.conversation_history[-3:]:
                if isinstance(msg.get("content"), str):
                    recent_text += " " + msg["content"]

            # Buscar escolas que existem no banco e cujo nome aparece no texto recente
            try:
                companies = db.client.table("companies").select("id,name").limit(500).execute().data or []
                mentioned = []
                recent_lower = recent_text.lower()
                for c in companies:
                    name = (c.get("name") or "").strip()
                    if len(name) < 4:
                        continue
                    # Match parcial: primeiras 3 palavras-chave do nome
                    words = [w for w in name.lower().split() if len(w) > 3][:3]
                    if words and all(w in recent_lower for w in words):
                        mentioned.append(c)
                        if len(mentioned) >= 3:
                            break

                for comp in mentioned:
                    school_mems = memory.get_for("company", comp["id"], limit=10)
                    if school_mems:
                        parts.append(f"\n== MEMORIAS SOBRE *{comp['name']}* ==")
                        parts.append(memory.format_for_context(school_mems))
            except Exception:
                pass

            return "\n".join(parts)
        except Exception as e:
            logger.debug(f"Erro ao construir system prompt com memoria: {e}")
            return SYSTEM_PROMPT

    def process_message(self, message: str, sender: str = "fernando") -> Dict[str, Any]:
        """
        Processa mensagem usando tool use. O modelo pode chamar
        ferramentas para consultar o banco e gerar respostas ricas.
        """
        try:
            self.conversation_history.append({
                "role": "user",
                "content": message
            })
            self._trim_history()

            # System prompt enriquecido com memorias persistentes
            contextual_prompt = self._build_contextual_system_prompt(message)
            messages = [{"role": "system", "content": contextual_prompt}] + self.conversation_history

            # Loop de tool use
            max_iterations = 5
            for _ in range(max_iterations):
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2048,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    tool_choice="auto",
                )

                choice = response.choices[0]

                if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
                    # Modelo quer usar ferramentas
                    assistant_msg = choice.message
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": assistant_msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                            }
                            for tc in assistant_msg.tool_calls
                        ]
                    })

                    # Executar cada tool call
                    for tc in assistant_msg.tool_calls:
                        handler = TOOL_HANDLERS.get(tc.function.name)
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        if handler:
                            try:
                                result = handler(args)
                            except Exception as e:
                                result = json.dumps({"erro": str(e)[:200]})
                                logger.error("Erro na tool", extra={"tool": tc.function.name, "error": str(e)})
                        else:
                            result = json.dumps({"erro": f"Ferramenta '{tc.function.name}' nao encontrada."})

                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result
                        })

                    # Atualiza messages para proxima iteracao
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history

                else:
                    # Modelo terminou — extrair texto final
                    reply = choice.message.content or ""

                    self.conversation_history.append({
                        "role": "assistant",
                        "content": reply
                    })
                    self._trim_history()

                    logger.info("Mensagem processada", extra={
                        "sender": sender,
                        "reply_length": len(reply),
                        "model": self.model,
                    })

                    return {"reply": reply}

            return {"reply": "Desculpa, a consulta ficou complexa demais. Tenta reformular?"}

        except Exception as e:
            logger.error("Erro ao processar mensagem", extra={"error": str(e)})
            # Se erro 400 (historico corrompido), limpar e tentar de novo
            if "400" in str(e) and "tool" in str(e):
                logger.warning("Historico corrompido detectado, limpando...")
                self.conversation_history = [{"role": "user", "content": message}]
                try:
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.conversation_history
                    response = self.client.chat.completions.create(
                        model=self.model, max_tokens=2048, messages=messages,
                        tools=OPENAI_TOOLS, tool_choice="auto",
                    )
                    reply = response.choices[0].message.content or ""
                    self.conversation_history.append({"role": "assistant", "content": reply})
                    return {"reply": reply}
                except Exception as e2:
                    return {"reply": f"Desculpe, tive um problema. Tente novamente. ({str(e2)[:80]})"}
            return {"reply": "Ops, deu um erro. Tenta de novo?"}

    def _trim_history(self) -> None:
        if len(self.conversation_history) > MAX_HISTORY:
            self.conversation_history = self.conversation_history[-MAX_HISTORY:]

        # Validar integridade: garantir que nao comece com tool ou assistant+tool_calls orfao
        cleaned = []
        for i, msg in enumerate(self.conversation_history):
            role = msg.get("role")
            if role == "tool":
                # Precisa ter assistant com tool_calls IMEDIATAMENTE antes (ou antes na sequencia)
                has_parent = False
                for j in range(len(cleaned) - 1, -1, -1):
                    if cleaned[j].get("role") == "assistant" and cleaned[j].get("tool_calls"):
                        has_parent = True
                        break
                    if cleaned[j].get("role") == "user":
                        break  # Se encontrou user antes de assistant+tool_calls, nao tem parent
                if not has_parent:
                    continue  # Pular tool orfao
            elif role == "assistant" and msg.get("tool_calls"):
                # Assistant com tool_calls precisa ter as respostas tool depois
                # Se for o ultimo, remover (incompleto)
                remaining = self.conversation_history[i+1:]
                has_tool_response = any(r.get("role") == "tool" for r in remaining)
                if not has_tool_response:
                    continue  # Pular assistant+tool_calls sem respostas
            cleaned.append(msg)
        self.conversation_history = cleaned
