"""
ia.py
-----
Aqui — e SÓ aqui — a gente conversa com a inteligência artificial (Gemini).

Por que isolar? Se um dia você quiser trocar o Gemini por outra IA (OpenAI,
Claude etc.), você mexe SÓ neste arquivo. O resto do bot nem fica sabendo.

Usamos o SDK oficial do Google "google-genai".
(Atenção: NÃO é o antigo "google-generativeai", que foi descontinuado.)
"""

import logging

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
from davi_persona import DAVI_PERSONA

logger = logging.getLogger("davi.ia")

# Guardamos o "cliente" do Gemini aqui. Ele é criado só na primeira vez que for
# usado (e não quando o arquivo é importado). Assim o bot sobe normalmente mesmo
# que a chave ainda não esteja preenchida — o erro só aparece na hora de usar a IA.
_client = None


def _get_client():
    """Cria (uma vez) e devolve o cliente do Gemini."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def gerar_resposta(historico):
    """
    Recebe o histórico da conversa e devolve a resposta do Davi (texto).

    historico: lista de dicionários no formato
        [{"role": "user"|"model", "text": "..."}, ...]
        IMPORTANTE: no Gemini os papéis são "user" e "model" (NÃO "assistant").

    Se algo der errado na IA, levanta um erro pra quem chamou tratar
    (o app vai enviar uma mensagem simpática pra pessoa nesse caso).
    """
    # Converte o nosso formato simples pro formato que o Gemini espera.
    contents = [
        {"role": item["role"], "parts": [{"text": item["text"]}]}
        for item in historico
    ]

    resposta = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=DAVI_PERSONA,  # a personalidade do Davi
            temperature=0.8,                  # quão "criativa"/variada é a resposta
            max_output_tokens=500,            # tamanho máximo da resposta
        ),
    )

    texto = (resposta.text or "").strip()
    if not texto:
        # Em casos raros a IA pode devolver vazio (ex.: filtro de segurança).
        # Damos uma resposta gentil de fallback em vez de mandar nada.
        logger.warning("Gemini retornou resposta vazia.")
        texto = "Estou aqui com você. Quer me contar um pouco mais do que está sentindo?"

    return texto


def gerar_devocional():
    """
    Gera o texto do devocional do dia (um versículo + uma reflexão curta).
    Usado pelo script devocional_diario.py.

    Não recebe histórico: é um pedido único e independente. Se a IA falhar,
    levanta erro — o script do devocional tem uma lista de reserva pra esse caso.
    """
    pedido = (
        "Escreva um devocional curto para enviar por WhatsApp a um cristão. "
        "Comece com um versículo bíblico real (com a referência: livro, capítulo "
        "e versículo), seguido de uma reflexão calorosa de 2 a 4 frases e uma "
        "frase final de incentivo. Tom acolhedor, simples e esperançoso. "
        "No máximo cerca de 60 palavras no total. Não use asteriscos nem títulos."
    )

    resposta = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=pedido,
        config=types.GenerateContentConfig(
            system_instruction=DAVI_PERSONA,
            temperature=0.9,
            max_output_tokens=300,
        ),
    )

    texto = (resposta.text or "").strip()
    if not texto:
        raise ValueError("Gemini retornou devocional vazio.")
    return texto
