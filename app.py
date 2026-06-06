"""
app.py
------
O "coração" do bot: é o servidor web (FastAPI) que recebe as mensagens do
WhatsApp e responde. Também tem endpoints de administração e de pagamento.

Como rodar localmente (Windows):
    py -m uvicorn app:app --reload

Endereços (endpoints) deste servidor:
    GET  /                 -> verifica se o bot está no ar (health check)
    GET  /webhook          -> a Meta usa pra "verificar" o webhook (uma vez só)
    POST /webhook          -> a Meta envia aqui as mensagens das pessoas
    POST /payment-webhook  -> o gateway de pagamento avisa quem virou assinante
    POST /admin/assinante  -> você adiciona/remove assinante manualmente (testes)
"""

import logging
import time

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, Response

import db
import ia
import whatsapp
from assinaturas import checar_acesso
from config import (
    ADMIN_TOKEN,
    AUDIO_ORACAO_URL,
    FREE_MESSAGES,
    LINK_ASSINATURA,
    PAYMENT_WEBHOOK_SECRET,
    WHATSAPP_VERIFY_TOKEN,
)

# Configura o log pra você ver no terminal/painel o que está acontecendo.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("davi.app")

app = FastAPI(title="Davi Bot")


@app.on_event("startup")
def ao_iniciar():
    """Quando o servidor sobe, garante que as tabelas do banco existem."""
    db.init_db()
    logger.info("Davi iniciou. Banco de dados pronto.")


# ----------------------------------------------------------------------
# Health check — abrir esta URL no navegador deve mostrar a mensagem.
# ----------------------------------------------------------------------
@app.get("/")
def home():
    return {"status": "Davi está no ar 🙏"}


# ----------------------------------------------------------------------
# Verificação do webhook (a Meta chama isso UMA vez, ao configurar).
# ----------------------------------------------------------------------
@app.get("/webhook")
def verificar_webhook(request: Request):
    """
    A Meta manda três parâmetros na URL:
      hub.mode, hub.verify_token e hub.challenge.
    Se o verify_token bater com o nosso, devolvemos o challenge em TEXTO PURO.
    Se não bater, devolvemos 403 (proibido).
    """
    parametros = request.query_params
    modo = parametros.get("hub.mode")
    token = parametros.get("hub.verify_token")
    challenge = parametros.get("hub.challenge")

    if modo == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verificado pela Meta com sucesso.")
        # Tem que responder o challenge como texto puro (não JSON).
        return Response(content=challenge or "", media_type="text/plain")

    logger.warning("Tentativa de verificação de webhook com token inválido.")
    raise HTTPException(status_code=403, detail="Token de verificação inválido.")


# ----------------------------------------------------------------------
# Recebimento das mensagens (a Meta chama isso a cada mensagem recebida).
# ----------------------------------------------------------------------
@app.post("/webhook")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    A Meta exige que a gente responda 200 (OK) BEM RÁPIDO. Por isso, aqui só
    lemos o corpo e jogamos o trabalho pesado (IA + envio) pra rodar "depois",
    em segundo plano (background task). Assim a Meta não fica esperando.
    """
    dados = await request.json()

    # Agenda o processamento pra rodar logo após respondermos 200.
    background_tasks.add_task(_processar_evento, dados)

    return {"status": "recebido"}


def _processar_evento(dados):
    """
    Faz o trabalho de verdade: lê a mensagem, decide o acesso, chama a IA e
    responde pela WhatsApp. Roda em segundo plano (não trava o webhook).
    """
    try:
        # Caminho do JSON da Meta até onde ficam as mensagens.
        valor = dados["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError, TypeError):
        # Formato inesperado: ignora com segurança.
        return

    # Se não tem "messages", pode ser uma notificação de STATUS de entrega
    # (enviado / entregue / lido / FALHOU). A gente registra no log o que vier,
    # principalmente as falhas — é aqui que a Meta diz POR QUE uma mensagem não
    # chegou na pessoa (ex.: número não confirmado, fora da janela de 24h, etc.).
    mensagens = valor.get("messages")
    if not mensagens:
        for status in valor.get("statuses", []):
            situacao = status.get("status")          # sent / delivered / read / failed
            destino = status.get("recipient_id")     # pra qual número
            erros = status.get("errors")             # detalhe, quando falha
            if erros:
                logger.error(
                    "ENTREGA FALHOU para %s (status=%s): %s", destino, situacao, erros
                )
            else:
                logger.info("Status de entrega para %s: %s", destino, situacao)
        return

    mensagem = mensagens[0]
    telefone = mensagem.get("from")
    tipo = mensagem.get("type")
    message_id = mensagem.get("id")

    # --- DIAGNOSTICO TEMPORARIO (9o digito BR / mensagem antiga reentregue) ---
    import time as _t
    _wa_id = None
    try:
        _wa_id = valor["contacts"][0].get("wa_id")
    except (KeyError, IndexError, TypeError):
        pass
    _ts = mensagem.get("timestamp")
    try:
        _idade = int(_t.time()) - int(_ts)
    except (TypeError, ValueError):
        _idade = None
    logger.info(
        "DIAG inbound -> from=%s | wa_id=%s | timestamp=%s | idade_segundos=%s | id=%s",
        telefone, _wa_id, _ts, _idade, message_id,
    )
    # --- fim diagnostico ---

    # Marca a mensagem como LIDA (tique azul) e mostra o "digitando..." enquanto
    # o Davi prepara a resposta. O "digitando..." some sozinho quando ele responde.
    if message_id:
        whatsapp.marcar_como_lido(message_id, mostrar_digitando=True)

    # Tenta descobrir o nome da pessoa (vem no perfil do contato).
    nome = "amigo(a)"
    try:
        nome = valor["contacts"][0]["profile"]["name"] or nome
    except (KeyError, IndexError, TypeError):
        pass

    # Salva/atualiza o usuário no banco.
    db.upsert_usuario(telefone, nome)

    # Por enquanto só tratamos TEXTO. Áudio/imagem -> resposta gentil.
    if tipo != "text":
        whatsapp.enviar_texto(
            telefone,
            "Por enquanto eu só consigo ler texto, tudo bem me escrever? 🙂",
        )
        return

    texto_recebido = mensagem["text"]["body"]

    # Guarda a mensagem da pessoa no histórico (papel "user").
    db.salvar_mensagem(telefone, "user", texto_recebido)

    # Verifica se a pessoa pode receber resposta da IA.
    acesso = checar_acesso(telefone)

    if not acesso["liberado"]:
        # Já recebeu o convite completo antes? Então manda só um lembrete curtinho,
        # pra não repetir o pitch inteiro a cada mensagem.
        if db.convite_ja_enviado(telefone):
            whatsapp.enviar_texto(
                telefone,
                "Quando você sentir que é a hora de seguir comigo, é só por aqui, tá? 🙏\n"
                f"{LINK_ASSINATURA}",
            )
            return

        # Primeira vez que bate no limite -> envia o convite pra assinar (SEM chamar a IA),
        # em vários balõezinhos curtos, como numa conversa de verdade.
        intro = [
            "Que bom ter você aqui comigo. 🙏",
            "Esse cantinho é onde a gente pode conversar de perto — sobre o que pesa no coração, sobre a vida e sobre a fé, no seu tempo.",
            "Essa foi a forma que encontrei de manter esse trabalho de pé. Não pense como uma cobrança, e sim como um jeito de cuidar comigo desse espaço — e de levar essa mensagem de fé e de amparo a ainda mais pessoas.",
            "O valor é simbólico perto de tudo que a gente pode viver junto: R$ 19,90 por mês, ou R$ 190,90 no ano todo — que te dá 2 meses de presente pra caminhar comigo por mais tempo.",
            f"Quando sentir que é a hora, é por aqui:\n{LINK_ASSINATURA}\n\nE se não for agora, tudo bem. Você é importante pra mim do mesmo jeito. 💙",
        ]
        for i, parte in enumerate(intro):
            if i > 0:
                time.sleep(1.2)  # pequena pausa pra os balões chegarem em ordem
            whatsapp.enviar_texto(telefone, parte)
        db.marcar_convite_enviado(telefone)  # não repetir o pitch nas próximas
        return

    # A pessoa respondeu ao devocional da manhã? Então manda a oração em áudio
    # agora (fluxo "responda pra receber") e encerra por aqui.
    if db.tem_oracao_pendente(telefone):
        db.limpar_oracao_pendente(telefone)
        if AUDIO_ORACAO_URL:
            whatsapp.enviar_texto(telefone, "Aqui está a oração de hoje, pra você ouvir com calma. 🙏")
            whatsapp.enviar_audio(telefone, AUDIO_ORACAO_URL)
        else:
            whatsapp.enviar_texto(
                telefone,
                "Que a paz de Deus guarde o seu coração hoje. 🙏",
            )
        return

    # Se a liberação foi por "mensagem grátis", conta +1 nas usadas.
    if acesso["motivo"] == "gratis":
        db.incrementar_gratis(telefone)

    # Monta o contexto: últimas ~30 mensagens (a persona entra dentro da ia.py).
    historico = db.ultimas_mensagens(telefone, limite=30)

    # Chama a IA. Se falhar, manda uma mensagem simpática de erro.
    try:
        resposta = ia.gerar_resposta(historico)
    except Exception as erro:  # noqa: BLE001 (queremos pegar qualquer falha da IA)
        logger.error("Erro ao chamar a IA: %s", erro)
        whatsapp.enviar_texto(
            telefone,
            "Tive um probleminha aqui 😅 Me manda de novo daqui a pouquinho?",
        )
        return

    # Guarda a resposta do Davi no histórico (papel "model") e envia.
    # Enviamos como UMA mensagem só (mais natural e sem risco de repetir balões).
    db.salvar_mensagem(telefone, "model", resposta)
    enviou = whatsapp.enviar_texto(telefone, resposta)

    if not enviou:
        logger.error("A resposta foi gerada, mas falhou ao enviar pelo WhatsApp.")


# ----------------------------------------------------------------------
# Webhook de pagamento — o gateway avisa quem pagou/assinou.
# ----------------------------------------------------------------------
@app.post("/payment-webhook")
async def payment_webhook(request: Request, x_webhook_secret: str = Header(default="")):
    """
    Endpoint genérico pra receber a confirmação de pagamento do seu gateway
    (ex.: AbacatePay, Mercado Pago). ADAPTE o trecho de leitura ao formato do
    seu gateway — cada um manda os dados de um jeito.

    Proteção: o gateway deve enviar o cabeçalho "X-Webhook-Secret" igual ao
    PAYMENT_WEBHOOK_SECRET do seu .env. (Alguns gateways usam outro nome de
    cabeçalho ou uma assinatura — ajuste conforme a documentação deles.)
    """
    if not PAYMENT_WEBHOOK_SECRET or x_webhook_secret != PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Segredo inválido.")

    dados = await request.json()

    # ---- ADAPTE AQUI conforme o seu gateway ----
    # A ideia: descobrir o telefone do assinante e até quando a assinatura vale.
    # Exemplo genérico (troque pelos campos reais do seu gateway):
    telefone = dados.get("telefone") or dados.get("phone")
    expira_em = dados.get("expira_em")  # texto ISO, ex.: "2026-07-03T00:00:00+00:00"
    status = dados.get("status", "ativo")
    # --------------------------------------------

    if not telefone:
        raise HTTPException(status_code=400, detail="Telefone não informado.")

    ativo = status in ("ativo", "active", "paid", "approved", "completed")

    # Verifica se a pessoa JÁ era assinante ativa antes de gravar. Assim a
    # mensagem de boas-vindas só é enviada quando ela ACABOU de virar assinante
    # (e não a cada renovação ou webhook repetido do mesmo pagamento).
    registro_atual = db.get_assinante(telefone)
    ja_era_ativo = bool(registro_atual and registro_atual.get("ativo"))

    db.set_assinante(telefone, ativo=ativo, expira_em=expira_em)
    logger.info("Pagamento processado: %s -> ativo=%s", telefone, ativo)

    # Acabou de virar assinante -> manda uma mensagem de boas-vindas no WhatsApp.
    if ativo and not ja_era_ativo:
        boas_vindas = (
            "🎉 Sua assinatura foi confirmada!\n\n"
            "Que alegria ter você comigo nessa caminhada de fé. 🙏 A partir de agora "
            "a gente pode conversar à vontade, sempre que você precisar — pra "
            "desabafar, orar junto ou buscar uma palavra na Bíblia.\n\n"
            "É só me mandar uma mensagem quando quiser. Deus te abençoe! 💙"
        )
        enviado = whatsapp.enviar_texto_em_blocos(telefone, boas_vindas)
        if not enviado:
            logger.warning(
                "Não consegui enviar as boas-vindas para %s (provavelmente fora da "
                "janela de 24h do WhatsApp).",
                telefone,
            )

    return {"status": "ok"}


# ----------------------------------------------------------------------
# Admin — adicionar/remover assinante na mão (útil no começo dos testes).
# ----------------------------------------------------------------------
@app.post("/admin/assinante")
async def admin_assinante(request: Request, x_admin_token: str = Header(default="")):
    """
    Adiciona ou remove um assinante manualmente.

    Proteção: precisa enviar o cabeçalho "X-Admin-Token" igual ao ADMIN_TOKEN
    do seu .env.

    Corpo (JSON) esperado:
        {
          "telefone": "5511999998888",
          "ativo": true,                       (opcional, padrão true)
          "expira_em": "2026-07-03T00:00:00+00:00"   (opcional)
        }
    """
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token de admin inválido.")

    dados = await request.json()
    telefone = dados.get("telefone")
    if not telefone:
        raise HTTPException(status_code=400, detail="Telefone é obrigatório.")

    ativo = dados.get("ativo", True)
    expira_em = dados.get("expira_em")

    db.set_assinante(telefone, ativo=ativo, expira_em=expira_em)
    logger.info("Admin atualizou assinante: %s -> ativo=%s", telefone, ativo)
    return {"status": "ok", "telefone": telefone, "ativo": ativo}


# ----------------------------------------------------------------------
# Tarefa: dispara o devocional do dia (chamado por um agendador externo, ex.:
# cron-job.org). Protegido por token. Aceita GET ou POST pra funcionar com
# qualquer agendador. Roda em segundo plano e responde rápido.
#
# Use a URL:  https://SEU-BOT.onrender.com/tarefas/devocional?token=SEU_ADMIN_TOKEN
# ----------------------------------------------------------------------
@app.api_route("/tarefas/devocional", methods=["GET", "POST"])
async def rodar_devocional(background_tasks: BackgroundTasks, token: str = ""):
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Token inválido.")

    import devocional_diario  # importa aqui pra evitar import circular
    background_tasks.add_task(devocional_diario.main)
    logger.info("Devocional disparado pelo agendador.")
    return {"status": "devocional disparado"}
