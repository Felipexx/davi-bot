"""
config.py
---------
Aqui ficam TODAS as configurações do bot, lidas do arquivo .env.

Por que um arquivo só pra isso? Pra você não precisar mexer em vários lugares
quando quiser trocar uma chave ou um valor. Tudo que é "configurável" mora aqui.

Como funciona: a biblioteca python-dotenv lê o arquivo .env (que você cria a
partir do .env.example) e coloca os valores em "variáveis de ambiente". Aqui a
gente apenas pega esses valores e guarda em variáveis com nomes fáceis.
"""

import os
from dotenv import load_dotenv

# Lê o arquivo .env (se existir) e carrega as variáveis pra memória.
# Em produção (ex.: Square Cloud), as variáveis vêm do painel do serviço e isso aqui
# simplesmente não encontra um .env — o que é normal e esperado.
load_dotenv()


# -------------------- WhatsApp Cloud API (Meta) --------------------
# Token de acesso do WhatsApp (de preferência o permanente, via System User).
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
# Identificador do número de telefone (Phone Number ID) no painel da Meta.
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
# Senha que VOCÊ inventa. Tem que ser igual à que você digita no painel da Meta
# na hora de configurar o webhook.
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
# Versão da Graph API da Meta. Deixe assim, a não ser que a Meta peça pra trocar.
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")


# -------------------- Gemini (IA do Google) --------------------
# Chave da API do Gemini (pegue no Google AI Studio: aistudio.google.com).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Modelo usado. "gemini-2.5-flash" tem bom custo-benefício. Dá pra trocar aqui
# ou pelo .env sem mexer no resto do código.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# -------------------- Regras do produto --------------------
# Quantas mensagens grátis uma pessoa que ainda não assinou pode mandar.
FREE_MESSAGES = int(os.getenv("FREE_MESSAGES", "1"))
# Link pra onde a pessoa vai pra assinar (sua página de pagamento).
LINK_ASSINATURA = os.getenv("LINK_ASSINATURA", "https://seusite.com/assinar")
# Nome do template do devocional aprovado na Meta (categoria Utility, pt_BR).
DEVOTIONAL_TEMPLATE_NAME = os.getenv("DEVOTIONAL_TEMPLATE_NAME", "devocional_diario")
# URL pública do áudio da oração do dia (enviado quando a pessoa responde ao devocional).
AUDIO_ORACAO_URL = os.getenv("AUDIO_ORACAO_URL", "")


# -------------------- Banco de dados e segurança --------------------
# Caminho do arquivo do banco SQLite. Em produção, aponte pra um disco
# persistente (veja o README) pra não perder os dados quando o servidor reinicia.
DATABASE_PATH = os.getenv("DATABASE_PATH", "davi.db")
# Token secreto pra proteger o endpoint de administração (/admin/assinante).
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
# Segredo pra proteger o webhook de pagamento (/payment-webhook).
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
