"""
whatsapp.py
-----------
Funções pra ENVIAR mensagens pelo WhatsApp usando a API oficial da Meta
(WhatsApp Cloud API). Tudo que fala com a Meta pra mandar mensagem mora aqui.

Dois tipos de envio:
1) Texto livre  -> só funciona dentro da "janela de 24h" (veja observação abaixo).
2) Template     -> mensagem pré-aprovada pela Meta; única forma de iniciar
                   conversa fora da janela de 24h (usado no devocional diário).

Observação sobre a janela de 24h:
A Meta só deixa você mandar texto livre se a pessoa te enviou alguma mensagem
nas últimas 24 horas. Passou disso, só template aprovado. Por isso o devocional
(que vai pra pessoa "do nada") precisa ser template.
"""

import logging
import re
import time

import httpx

from config import (
    GRAPH_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_TOKEN,
)

logger = logging.getLogger("davi.whatsapp")

# Endereço base da API da Meta pra enviar mensagens deste número.
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"


def _headers():
    """Cabeçalhos de autenticação exigidos pela Meta."""
    return {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def enviar_texto(telefone, texto):
    """
    Envia uma mensagem de TEXTO simples pra pessoa.

    telefone: número no formato internacional, só dígitos (ex.: "5511999998888").
    texto: o conteúdo da mensagem.

    Retorna True se a Meta aceitou, False se deu erro (o erro é registrado no log).
    """
    corpo = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "text",
        "text": {"body": texto},
    }

    logger.info("Enviando resposta de texto para o numero: %s", telefone)

    try:
        resposta = httpx.post(BASE_URL, headers=_headers(), json=corpo, timeout=30)
        resposta.raise_for_status()
        return True
    except httpx.HTTPError as erro:
        # Mostra no log o que a Meta respondeu, pra facilitar achar o problema.
        detalhe = getattr(erro, "response", None)
        corpo_erro = detalhe.text if detalhe is not None else str(erro)
        logger.error("Falha ao enviar texto pelo WhatsApp: %s", corpo_erro)
        return False


def marcar_como_lido(message_id):
    """
    Marca a mensagem recebida como LIDA — é o "tique azul" que aparece no
    WhatsApp da pessoa, mostrando que o Davi viu a mensagem dela.

    message_id: o identificador da mensagem (campo "id" que vem no webhook).
    Retorna True se deu certo, False se deu erro.
    """
    if not message_id:
        return False

    corpo = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    try:
        resposta = httpx.post(BASE_URL, headers=_headers(), json=corpo, timeout=30)
        resposta.raise_for_status()
        return True
    except httpx.HTTPError as erro:
        detalhe = getattr(erro, "response", None)
        corpo_erro = detalhe.text if detalhe is not None else str(erro)
        logger.error("Falha ao marcar mensagem como lida: %s", corpo_erro)
        return False


def _dividir_em_blocos(texto, maximo=4):
    """
    Divide a resposta do Davi em "balões" curtos, separados por linha em branco.
    Assim ele manda várias mensagens curtinhas (como no WhatsApp), em vez de um textão.
    """
    if not texto:
        return []
    # Separa onde houver uma linha em branco (uma ou mais quebras de linha vazias).
    partes = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]
    if not partes:
        return [texto.strip()]
    # Se vier mais blocos que o máximo, junta o excedente no último (não perde texto).
    if len(partes) > maximo:
        partes = partes[: maximo - 1] + ["\n\n".join(partes[maximo - 1:])]
    return partes


def enviar_texto_em_blocos(telefone, texto, pausa=1.5):
    """
    Envia a resposta dividida em várias mensagens curtas (vários balões), com uma
    pequena pausa entre elas pra chegarem em ordem e parecer mais natural.
    Retorna True se todos os blocos foram enviados com sucesso.
    """
    blocos = _dividir_em_blocos(texto)
    if not blocos:
        return False

    todos_ok = True
    for i, bloco in enumerate(blocos):
        if i > 0:
            time.sleep(pausa)  # pequena pausa entre uma mensagem e outra
        ok = enviar_texto(telefone, bloco)
        todos_ok = todos_ok and ok
    return todos_ok


def enviar_template(telefone, nome_template, variaveis=None, idioma="pt_BR"):
    """
    Envia uma mensagem de TEMPLATE (pré-aprovada na Meta).

    telefone: número internacional só com dígitos.
    nome_template: o nome exato do template aprovado (ex.: "devocional_diario").
    variaveis: lista de textos que preenchem as variáveis do corpo, na ordem
               ({{1}}, {{2}}, ...). Pro devocional, é uma lista com um texto só.
    idioma: código do idioma do template (o nosso é "pt_BR").

    Retorna True se aceitou, False se deu erro.
    """
    variaveis = variaveis or []

    # Monta os "components" só se houver variáveis no corpo do template.
    components = []
    if variaveis:
        components.append(
            {
                "type": "body",
                "parameters": [{"type": "text", "text": v} for v in variaveis],
            }
        )

    corpo = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "template",
        "template": {
            "name": nome_template,
            "language": {"code": idioma},
            "components": components,
        },
    }

    try:
        resposta = httpx.post(BASE_URL, headers=_headers(), json=corpo, timeout=30)
        resposta.raise_for_status()
        return True
    except httpx.HTTPError as erro:
        detalhe = getattr(erro, "response", None)
        corpo_erro = detalhe.text if detalhe is not None else str(erro)
        logger.error("Falha ao enviar template pelo WhatsApp: %s", corpo_erro)
        return False
