"""
assinaturas.py
--------------
Regras de QUEM PODE conversar com o Davi.

A ideia é simples:
- Assinante ativo  -> pode conversar à vontade.
- Não assinante    -> ganha algumas mensagens grátis pra experimentar (FREE_MESSAGES).
- Acabaram as grátis -> recebe um convite carinhoso pra assinar (e a IA não é chamada).

Tudo que decide "libera ou não" passa por aqui, pra ficar fácil de ajustar a regra.
"""

from datetime import datetime, timezone

from config import FREE_MESSAGES
from db import get_assinante, get_usuario


def _assinatura_valida(registro):
    """
    Diz se um registro de assinante está realmente válido agora
    (ativo e, se tiver data de expiração, ainda não expirou).
    """
    if not registro or not registro.get("ativo"):
        return False

    expira_em = registro.get("expira_em")
    if not expira_em:
        # Sem data de expiração = considerado válido enquanto estiver ativo.
        return True

    try:
        data_expira = datetime.fromisoformat(expira_em)
        # Garante comparação correta mesmo se a data vier "sem fuso".
        if data_expira.tzinfo is None:
            data_expira = data_expira.replace(tzinfo=timezone.utc)
        return data_expira > datetime.now(timezone.utc)
    except ValueError:
        # Se a data estiver num formato estranho, por segurança considera inválida.
        return False


def checar_acesso(telefone):
    """
    Decide se a pessoa pode receber resposta da IA agora.

    Retorna um dicionário:
        {"liberado": True,  "motivo": "assinante"}  -> é assinante ativo
        {"liberado": True,  "motivo": "gratis"}     -> usando mensagens grátis
        {"liberado": False, "motivo": "limite"}     -> acabaram as grátis (convidar a assinar)

    Importante: esta função só CONSULTA. Quem soma +1 nas mensagens grátis usadas
    é o app, depois de confirmar que a mensagem foi de fato uma "grátis".
    """
    # 1) É assinante ativo?
    if _assinatura_valida(get_assinante(telefone)):
        return {"liberado": True, "motivo": "assinante"}

    # 2) Não é assinante: ainda tem mensagem grátis sobrando?
    usuario = get_usuario(telefone)
    usadas = usuario["mensagens_gratis_usadas"] if usuario else 0

    if usadas < FREE_MESSAGES:
        return {"liberado": True, "motivo": "gratis"}

    # 3) Acabaram as grátis.
    return {"liberado": False, "motivo": "limite"}
