"""
devocional_diario.py
--------------------
Script que ENVIA o devocional do dia pra todos os assinantes ativos.

Ele NÃO faz parte do servidor web: é pra rodar uma vez por dia, sozinho,
chamado por um agendador (ex.: Cron Job do Render). Veja o README, seção do
devocional, pra configurar o agendamento.

Como rodar manualmente (pra testar):
    py devocional_diario.py

Por que o devocional vai como TEMPLATE e não como texto?
Porque ele é enviado "do nada" pra pessoa (ela não te mandou mensagem agora).
Fora da janela de 24h, a Meta só permite template aprovado. O template precisa
ter UMA variável no corpo ({{1}}), que é onde colocamos o texto do dia.
"""

import logging

import db
import ia
import whatsapp
from config import DEVOTIONAL_TEMPLATE_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("davi.devocional")


# Lista de reserva: se a IA falhar, usamos um destes (rotativo). Você pode
# editar/aumentar esta lista à vontade — é só texto.
DEVOCIONAIS_RESERVA = [
    "“O Senhor é o meu pastor; nada me faltará.” (Salmos 23:1) "
    "Hoje, respire fundo e lembre: você é cuidado(a). Mesmo no que falta, Ele "
    "supre o essencial — paz pro seu coração. Você não está só. 🙏",

    "“Posso todas as coisas naquele que me fortalece.” (Filipenses 4:13) "
    "Seja qual for o seu dia, há força disponível pra você. Um passo de cada "
    "vez. Deus caminha com você hoje. 💙",

    "“Lancem sobre Ele toda a sua ansiedade, porque Ele tem cuidado de vocês.” "
    "(1 Pedro 5:7) Entregue hoje aquilo que pesa. Você não precisa carregar "
    "tudo sozinho(a). Descanse nesse cuidado. 🙏",

    "“O choro pode durar uma noite, mas a alegria vem pela manhã.” (Salmos 30:5) "
    "Se hoje está difícil, isso não é o fim da sua história. Tem esperança a "
    "caminho. Segure firme. 💙",

    "“Não temas, porque eu sou contigo.” (Isaías 41:10) "
    "Onde você estiver hoje, não está sozinho(a). Vá com calma e confiança — "
    "Deus está bem perto de você. 🙏",

    "“Vinde a mim, todos os que estais cansados e sobrecarregados, e eu vos "
    "aliviarei.” (Mateus 11:28) Pode chegar do jeito que você está. Aqui tem "
    "descanso pra alma. Respira. 💙",

    "“A tua palavra é lâmpada para os meus pés e luz para o meu caminho.” "
    "(Salmos 119:105) Mesmo sem ver tudo, dá pra dar o próximo passo. Hoje, "
    "confie na luz que ilumina o agora. 🙏",
]


def obter_texto_do_dia(indice_reserva=0):
    """
    Tenta gerar o devocional com a IA. Se falhar (erro de rede, cota etc.),
    usa um texto da lista de reserva, escolhido pelo 'indice_reserva'.
    """
    try:
        return ia.gerar_devocional()
    except Exception as erro:  # noqa: BLE001
        logger.warning("IA falhou no devocional, usando texto de reserva: %s", erro)
        return DEVOCIONAIS_RESERVA[indice_reserva % len(DEVOCIONAIS_RESERVA)]


def main():
    """Envia o devocional do dia pra todos os assinantes ativos."""
    db.init_db()

    assinantes = db.listar_assinantes_ativos()
    if not assinantes:
        logger.info("Nenhum assinante ativo. Nada a enviar hoje.")
        return

    # Gera UM texto do dia e envia o mesmo pra todo mundo (mais barato e coerente).
    texto = obter_texto_do_dia()
    logger.info("Devocional do dia: %s", texto)

    enviados = 0
    falhas = 0
    for telefone in assinantes:
        ok = whatsapp.enviar_template(
            telefone,
            DEVOTIONAL_TEMPLATE_NAME,
            variaveis=[texto],   # preenche o {{1}} do template
            idioma="pt_BR",
        )
        if ok:
            enviados += 1
            # Também guarda no histórico, pra manter a memória da conversa.
            db.salvar_mensagem(telefone, "model", texto)
        else:
            falhas += 1

    logger.info("Devocional enviado. Sucesso: %s | Falhas: %s", enviados, falhas)


# Quando você roda "py devocional_diario.py", isto aqui é executado.
if __name__ == "__main__":
    main()
