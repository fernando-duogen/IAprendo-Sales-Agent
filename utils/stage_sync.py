"""utils/stage_sync.py — fonte UNICA de verdade da relacao entre os dois
modelos de progresso de uma escola:

- companies.status           : status TECNICO do pipeline
                               (raw -> filtered -> qualified -> enriched ->
                                contacted -> responded -> converted / rejected)
- companies.commercial_stage : estagio do funil COMERCIAL (Kanban)
                               (prospectado -> contatado -> respondeu ->
                                reuniao -> proposta -> cliente / perdido;
                                NULL = inferir a partir do status + sinais)

Antes, o mapa status->stage vivia solto no Pipeline e nada gravava o status
quando o commercial_stage avancava (ex: fechar cliente pelo IAlex deixava o
status "contacted"). Este modulo centraliza os mapas e oferece a logica de
coerencia (advance-only) usada pelo setter em database/supabase_client.py.
"""
from typing import Dict, Optional, Any, List

# Ordem do status tecnico — usada na logica advance-only (nunca regride).
STATUS_RANK: Dict[str, int] = {
    "raw": 0,
    "filtered": 1,
    "qualified": 2,
    "enriched": 3,
    "contacted": 4,
    "responded": 5,
    "converted": 6,
    "rejected": 6,
    "descartado": 6,
}

# commercial_stage -> status tecnico MINIMO coerente.
# None = nao forca status (ex: 'prospectado' eh so preparo, nao houve contato).
STAGE_TO_STATUS: Dict[str, Optional[str]] = {
    "prospectado": None,
    "contatado": "contacted",
    "respondeu": "responded",
    "reuniao": "responded",   # houve reuniao => no minimo engajou (responded)
    "proposta": "responded",  # proposta => engajado
    "cliente": "converted",
    "perdido": "rejected",
}

# status tecnico -> commercial_stage (fallback de inferencia na leitura).
STATUS_TO_STAGE: Dict[str, str] = {
    "contacted": "contatado",
    "responded": "respondeu",
    "converted": "cliente",
    "rejected": "perdido",
    "descartado": "perdido",
}

# Estagios do funil em ordem (Kanban). 'perdido' fica fora do fluxo linear.
COMMERCIAL_STAGE_ORDER: List[str] = [
    "prospectado", "contatado", "respondeu", "reuniao", "proposta", "cliente",
]

# =============================================================================
# Mapeamento commercial_stage <-> label do stage no pipeline HubSpot
# ("IAprendo Sales", labels em PT). FONTE UNICA: o push (integrations/
# hubspot_sync.py) e o pull (integrations/hubspot_pull.py) leem daqui, entao
# os dois sentidos nunca divergem.
#
# IMPORTANTE: o pipeline de Deals no HubSpot precisa ter EXATAMENTE esses 8
# stage labels criados (ver scripts/setup_hubspot_properties.py):
#   Prospectado, Email Enviado, Email Aberto, Respondeu, Reuniao Agendada,
#   Proposta Enviada, Convertido, Perdido
# =============================================================================

# commercial_stage -> label do stage no HubSpot (push).
# Inclui aliases retrocompat (email_enviado, reuniao_agendada, convertido) que
# apontam pro mesmo label do canonico — uteis na entrada, ignorados no inverso.
STAGE_MAP: Dict[str, str] = {
    # Stages automaticos (inferidos pelo sistema)
    "prospectado": "Prospectado",
    "contatado": "Email Enviado",
    "email_enviado": "Email Enviado",        # alias retrocompat
    "email_aberto": "Email Aberto",
    "respondeu": "Respondeu",
    "reuniao": "Reuniao Agendada",
    "reuniao_agendada": "Reuniao Agendada",  # alias retrocompat
    # Stages manuais (setados via IAlex)
    "proposta": "Proposta Enviada",
    "cliente": "Convertido",
    "convertido": "Convertido",              # alias retrocompat
    "perdido": "Perdido",
}

# label do HubSpot -> commercial_stage CANONICO (pull). Inverso de STAGE_MAP,
# mas NAO uma inversao cega: 'Email Aberto' -> 'contatado' (nao existe
# commercial_stage 'email_aberto'), e os aliases colapsam pro canonico. Todos
# os valores respeitam companies_commercial_stage_chk.
LABEL_TO_STAGE: Dict[str, str] = {
    "Prospectado": "prospectado",
    "Email Enviado": "contatado",
    "Email Aberto": "contatado",   # abriu, mas comercialmente ainda 'contatado'
    "Respondeu": "respondeu",
    "Reuniao Agendada": "reuniao",
    "Proposta Enviada": "proposta",
    "Convertido": "cliente",
    "Perdido": "perdido",
}


def coherent_status_for_stage(
    current_status: Optional[str],
    stage: Optional[str],
) -> Optional[str]:
    """Status tecnico que deve ser setado quando o commercial_stage passa a
    `stage`, AVANCANDO apenas (nunca regride). None = manter o status atual.

    Exemplos:
        coherent_status_for_stage("contacted", "cliente")  -> "converted"
        coherent_status_for_stage("converted", "contatado") -> None  (nao regride)
        coherent_status_for_stage("raw", "prospectado")     -> None  (sem contato)
    """
    target = STAGE_TO_STATUS.get((stage or "").lower())
    if not target:
        return None
    cur = (current_status or "raw").lower()
    if STATUS_RANK.get(target, 0) > STATUS_RANK.get(cur, 0):
        return target
    return None


def commercial_stage_rank(stage: Optional[str]) -> int:
    """Posicao do estagio comercial no funil linear (advance-only).

    'perdido' fica fora do fluxo linear e qualquer valor desconhecido/None
    retornam -1 (tratados a parte por should_advance_commercial_stage).
    """
    try:
        return COMMERCIAL_STAGE_ORDER.index((stage or "").lower())
    except ValueError:
        return -1


def should_advance_commercial_stage(
    current: Optional[str],
    incoming: Optional[str],
) -> bool:
    """Decide se `incoming` deve sobrescrever `current` numa sincronizacao
    EXTERNA do estagio comercial (ex.: pull do HubSpot -> Supabase).

    Espelha a filosofia advance-only de coherent_status_for_stage, mas para o
    proprio commercial_stage: nunca regride um lead que ja esta mais avancado
    no Supabase, e protege os estados terminais.

    Regras (nesta ordem):
      - sem `incoming` valido               -> False
      - Supabase sem stage (lacuna)         -> True  (HubSpot preenche)
      - igual ao atual                      -> False
      - atual 'cliente' (ganho)             -> False (nunca regride via pull)
      - atual 'perdido'                     -> True so se incoming == 'cliente'
      - incoming 'perdido'                  -> True  (HubSpot marcou perdido)
      - caso geral (funil linear)           -> rank(incoming) > rank(current)

    Exemplos:
        should_advance_commercial_stage(None, "contatado")        -> True
        should_advance_commercial_stage("proposta", "contatado")  -> False (regrediria)
        should_advance_commercial_stage("contatado", "proposta")  -> True
        should_advance_commercial_stage("cliente", "perdido")     -> False (deal ganho)
        should_advance_commercial_stage("reuniao", "perdido")     -> True
    """
    inc = (incoming or "").lower()
    cur = (current or "").lower()
    if not inc:
        return False
    if not cur:
        return True
    if inc == cur:
        return False
    if cur == "cliente":
        return False
    if cur == "perdido":
        return inc == "cliente"
    if inc == "perdido":
        return True
    return commercial_stage_rank(inc) > commercial_stage_rank(cur)


def infer_stage(
    company: Dict[str, Any],
    *,
    has_email: bool = False,
    has_reply: bool = False,
    has_meeting: bool = False,
) -> Optional[str]:
    """Inferencia de leitura do estagio comercial. Prioridade:
    commercial_stage manual > status tecnico mapeado > sinais
    (reuniao/resposta/email) > 'prospectado' (status inicial) > None.

    Os sinais (has_*) sao opcionais — quem tiver os dados de
    emails/reunioes passa; quem nao tiver, cai no mapeamento por status.
    """
    manual = company.get("commercial_stage")
    if manual:
        return manual
    st = (company.get("status") or "").lower()
    if st in STATUS_TO_STAGE:
        return STATUS_TO_STAGE[st]
    if has_meeting:
        return "reuniao"
    if has_reply:
        return "respondeu"
    if has_email:
        return "contatado"
    if st in ("raw", "qualified", "enriched", "filtered"):
        return "prospectado"
    return None
