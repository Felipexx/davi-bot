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


def _normalizar_destino(telefone):
    """
    Ajusta números de celular do Brasil pro formato que a Meta usa internamente.

    A Meta ENTREGA o número COM o 9º dígito (ex.: 55 15 99121-8769 = 13 dígitos),
    mas REGISTRA a conversa SEM esse 9 extra. Se a gente responde com o 9, a Meta
    trata como outra conversa parada e recusa com o erro 131047 ("fora da janela
    de 24h"), mesmo a pessoa tendo acabado de falar.

    Por isso, pra números do Brasil no formato 55 + DDD + 9 + 8 dígitos (13 no
    total, com o 5º dígito = 9), removemos esse 9. Números de fora do Brasil, ou
    que já vêm sem o 9, não são alterados.
    """
    if not telefone:
        return telefone
    digitos = re.sub(r"\D", "", str(telefone))
    if len(digitos) == 13 and digitos.startswith("55") and digitos[4] == "9":
        return digitos[:4] + digitos[5:]
    return digitos


def enviar_texto(telefone, texto):
    """
    Envia uma mensagem de TEXTO simples pra pessoa.

    telefone: número no formato internacional, só dígitos (ex.: "5511999998888").
    texto: o conteúdo da mensagem.

    Retorna True se a Meta aceitou, False se deu erro (o erro é registrado no log).
    """
    destino = _normalizar_destino(telefone)
    corpo = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"body": texto},
    }

    logger.info("Enviando resposta de texto para o numero: %s", destino)

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


def enviar_audio(telefone, link):
    """
    Envia um ÁUDIO (por link público) pra pessoa — toca dentro do WhatsApp.

    Só funciona dentro da janela de 24h (a pessoa precisa ter te mandado mensagem
    recentemente) — por isso usamos no fluxo "responda pra receber a oração".
    Formatos aceitos pela Meta: mp3 (audio/mpeg), aac, m4a, amr, ogg (codec opus).

    link: URL pública do arquivo de áudio.
    """
    corpo = {
        "messaging_product": "whatsapp",
        "to": _normalizar_destino(telefone),
        "type": "audio",
        "audio": {"link": link},
    }
    try:
        resposta = httpx.post(BASE_URL, headers=_headers(), json=corpo, timeout=30)
        resposta.raise_for_status()
        return True
    except httpx.HTTPError as erro:
        detalhe = getattr(erro, "response", None)
        corpo_erro = detalhe.text if detalhe is not None else str(erro)
        logger.error("Falha ao enviar áudio pelo WhatsApp: %s", corpo_erro)
        return False


def marcar_como_lido(message_id, mostrar_digitando=True):
    """
    Marca a mensagem recebida como LIDA (o "tique azul") e, de quebra, mostra o
    "digitando..." pra pessoa enquanto o Davi prepara a resposta.

    message_id: o identificador da mensagem (campo "id" que vem no webhook).
    mostrar_digitando: se True, exibe o "digitando..." (some sozinho quando o
        Davi envia a resposta, ou depois de uns 25 segundos).
    Retorna True se deu certo, False se deu erro.
    """
    if not message_id:
        return False

    corpo = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    # Pede pra mostrar o "digitando..." junto com o "lido" (mesma chamada).
    if mostrar_digitando:
        corpo["typing_indicator"] = {"type": "text"}

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
        "to": _normalizar_destino(telefone),
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
