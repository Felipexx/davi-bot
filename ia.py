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
from datetime import date

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
            temperature=0.6,                  # mais baixa = mais direto, menos repetição
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


# Temas que vão rodando ao longo dos dias, pra o devocional ter variedade e não
# ficar repetitivo. Você pode editar/adicionar temas à vontade.
TEMAS_DEVOCIONAL = [
    "recomeços e novos começos",
    "ansiedade e confiar em Deus",
    "gratidão no dia a dia",
    "perdão — dar e receber",
    "esperança em tempos difíceis",
    "o descanso e a paz que vêm de Deus",
    "medo e coragem na fé",
    "o amor ao próximo",
    "perseverança e uma fé que não desiste",
    "o cuidado de Deus, como um pastor",
    "propósito e direção para a vida",
    "humildade e entregar o controle a Deus",
    "consolo na dor e no luto",
    "a alegria que vem do Senhor",
    "fé enquanto se espera por uma resposta",
    "arrependimento e graça",
    "confiança quando falta clareza",
    "força para recomeçar depois de uma queda",
    "paciência consigo mesmo",
    "a presença de Deus na solidão",
]


def gerar_devocional():
    """
    Gera o devocional do dia: uma reflexão cristã mais profunda (3-4 parágrafos)
    sobre um tema que vai rodando a cada dia, terminando com um versículo real.
    Usado pelo script devocional_diario.py.

    Não recebe histórico: é um pedido único e independente. Se a IA falhar,
    levanta erro — o script do devocional tem uma lista de reserva pra esse caso.
    """
    # Escolhe o tema do dia rodando pela lista (muda todo dia, sem repetir cedo).
    tema = TEMAS_DEVOCIONAL[date.today().toordinal() % len(TEMAS_DEVOCIONAL)]

    pedido = (
        "Escreva o DEVOCIONAL CRISTÃO de hoje para enviar no WhatsApp. "
        f"Tema de hoje: {tema}.\n\n"
        "Como deve ser:\n"
        "- 3 a 4 parágrafos curtos, calorosos e pessoais (fale com 'você').\n"
        "- 1º parágrafo: uma reflexão humana e acolhedora sobre o tema, algo com que a pessoa realmente se identifique.\n"
        "- 2º: o que a Palavra de Deus mostra sobre isso, de forma simples e esperançosa (centrado na Bíblia e em Jesus).\n"
        "- 3º: um incentivo prático e gentil para viver isso hoje.\n"
        "- Na ÚLTIMA linha, cite um versículo bíblico real e relacionado, exatamente neste formato: "
        "Referência: Livro Capítulo:versículo\n\n"
        "Regras: cerca de 150 a 220 palavras. Sem título, sem asteriscos, sem listas, no "
        "máximo 1 emoji. Base evangélica — não cite outras doutrinas. Escreva um texto novo "
        "e original a cada vez (não repita frases prontas)."
    )

    resposta = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=pedido,
        config=types.GenerateContentConfig(
            system_instruction=DAVI_PERSONA,
            temperature=1.0,
            max_output_tokens=700,
        ),
    )

    texto = (resposta.text or "").strip()
    if not texto:
        raise ValueError("Gemini retornou devocional vazio.")
    return texto
