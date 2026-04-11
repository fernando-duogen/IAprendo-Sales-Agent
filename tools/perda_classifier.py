"""Classifica motivo de perda livre em categoria enum via Claude Haiku.

Fernando registra no WhatsApp: "perdi o Marista, foi pra concorrencia com
preco menor". O handler marcar_perdido chama este modulo pra classificar
o texto livre em uma categoria curta (preco/timing/concorrente/orcamento/
nao_prioridade/outro). A categoria vai pra `companies.motivo_perda_categoria`
pra relatorios agregaveis. O texto original fica em `motivo_perda_texto`.

Falha silenciosa: qualquer erro (timeout, API, resposta invalida) retorna
'outro' pra nunca bloquear o fluxo principal.
"""
from typing import Literal

from anthropic import Anthropic

from config.settings import settings
from utils.logger import logger


VALID_CATEGORIES = (
    "preco",
    "timing",
    "concorrente",
    "orcamento",
    "nao_prioridade",
    "outro",
)

Categoria = Literal["preco", "timing", "concorrente", "orcamento", "nao_prioridade", "outro"]


def classificar_motivo_perda(texto: str) -> Categoria:
    """Usa Claude Haiku pra classificar motivo livre em enum curto.

    Args:
        texto: Motivo descrito por Fernando em linguagem natural.

    Returns:
        Uma das 6 categorias validas. 'outro' em caso de erro ou texto vazio.
    """
    if not texto or len(texto.strip()) < 3:
        return "outro"
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("classificar_motivo_perda: ANTHROPIC_API_KEY vazio")
        return "outro"

    prompt = (
        "Classifique o motivo de perda de venda abaixo em UMA categoria.\n"
        "Categorias possiveis:\n"
        "- preco: escola achou caro, nao tinha orcamento pro valor\n"
        "- timing: momento ruim, vao decidir depois, ano letivo atrapalhou\n"
        "- concorrente: escolheram outra solucao/fornecedor\n"
        "- orcamento: nao tem verba alocada, aguardando aprovacao financeira\n"
        "- nao_prioridade: nao eh prioridade agora, outros projetos a frente\n"
        "- outro: qualquer outro motivo que nao se encaixe acima\n\n"
        "Responda APENAS com uma dessas 6 palavras exatas. Nada mais.\n\n"
        f"Motivo: {texto}"
    )

    try:
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = resp.content[0].text.strip().lower() if resp.content else ""
        # Remove pontuacao possivel
        answer = answer.rstrip(".,;:!?").strip()
        if answer in VALID_CATEGORIES:
            logger.info(
                "Motivo de perda classificado",
                extra={"texto": texto[:100], "categoria": answer},
            )
            return answer  # type: ignore[return-value]
        logger.warning(
            "classificar_motivo_perda: resposta invalida",
            extra={"answer": answer[:50], "texto": texto[:100]},
        )
        return "outro"
    except Exception as e:
        logger.warning(f"classificar_motivo_perda falhou: {e}")
        return "outro"
