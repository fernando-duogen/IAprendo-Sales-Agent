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
