"""Conversa do chat dos tecnicos com a IA (fluxo N8N).

O navegador fala so com o nosso servidor; o servidor e quem chama o N8N,
levando o segredo no cabecalho ``x-chat-secret``. Assim o segredo nunca
aparece no navegador do tecnico.
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO_MENSAGEM = 1000

MENSAGEM_DESLIGADO = (
    "O assistente ainda não está ligado. Tente novamente mais tarde ou fale "
    "com o responsável pela plataforma."
)
MENSAGEM_DEMORA = (
    "O assistente demorou demais para responder. Tente de novo em instantes."
)
MENSAGEM_FALHA = (
    "Não consegui falar com o assistente agora. Tente de novo em instantes."
)


class ErroChatIA(Exception):
    """Erro com um texto amigavel para mostrar ao tecnico."""


def chat_ligado():
    return bool(settings.CHAT_IA_URL)


def montar_pedido(mensagem, sessao_id, tecnico, usuario, curso=None):
    """Monta o JSON enviado ao N8N (formato combinado com o responsavel da IA)."""
    dados_tecnico = {
        "id": tecnico.pk if tecnico else None,
        "nome": tecnico.nome if tecnico else (usuario.get_full_name() or usuario.username),
        "matricula": tecnico.matricula if tecnico else "",
        "empresa": tecnico.empresa.nome if tecnico else "",
        "teste_interno": tecnico is None,
    }
    return {
        "mensagem": mensagem,
        "sessao_id": sessao_id,
        "tecnico": dados_tecnico,
        "curso": {"id": curso.pk, "nome": curso.nome} if curso else None,
    }


def extrair_resposta(corpo):
    """Le a resposta do N8N.

    O combinado e ``{"resposta": "..."}``, mas aceitamos tambem os formatos
    mais comuns do N8N (``output``, ``text``, ``message``, lista com um item
    ou texto puro), para o teste nao falhar por um detalhe.
    """
    texto = corpo.decode("utf-8", errors="replace").strip()
    if not texto:
        return ""
    try:
        dados = json.loads(texto)
    except ValueError:
        return texto
    if isinstance(dados, list):
        dados = dados[0] if dados else {}
    if isinstance(dados, str):
        return dados.strip()
    if isinstance(dados, dict):
        for chave in ("resposta", "output", "text", "message", "mensagem"):
            valor = dados.get(chave)
            if isinstance(valor, str) and valor.strip():
                return valor.strip()
    return ""


def perguntar_ia(pedido):
    """Envia o pedido ao N8N e devolve o texto da resposta.

    Levanta ErroChatIA com uma mensagem amigavel em qualquer problema.
    """
    if not chat_ligado():
        raise ErroChatIA(MENSAGEM_DESLIGADO)

    requisicao = urllib.request.Request(
        settings.CHAT_IA_URL,
        data=json.dumps(pedido).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-chat-secret": settings.CHAT_IA_SEGREDO,
        },
    )
    try:
        with urllib.request.urlopen(
            requisicao, timeout=settings.CHAT_IA_TIMEOUT
        ) as resposta:
            corpo = resposta.read(200_000)
    except TimeoutError:
        logger.warning("Chat IA: o N8N nao respondeu a tempo.")
        raise ErroChatIA(MENSAGEM_DEMORA)
    except urllib.error.HTTPError as erro:
        # 403/401 costuma ser segredo errado; 404 costuma ser URL de teste
        # (/webhook-test/) com o fluxo fora do modo de teste.
        logger.warning("Chat IA: o N8N respondeu com erro HTTP %s.", erro.code)
        raise ErroChatIA(MENSAGEM_FALHA)
    except (urllib.error.URLError, OSError) as erro:
        motivo = getattr(erro, "reason", erro)
        if isinstance(motivo, TimeoutError):
            logger.warning("Chat IA: o N8N nao respondeu a tempo.")
            raise ErroChatIA(MENSAGEM_DEMORA)
        logger.warning("Chat IA: falha ao conectar no N8N: %s", motivo)
        raise ErroChatIA(MENSAGEM_FALHA)

    texto = extrair_resposta(corpo)
    if not texto:
        logger.warning("Chat IA: o N8N respondeu sem o campo 'resposta'.")
        raise ErroChatIA(MENSAGEM_FALHA)
    return texto
