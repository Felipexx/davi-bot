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


def _variantes_telefone(telefone):
    """
    Lida com o "nono dígito" dos celulares brasileiros: o WhatsApp pode entregar
    o número COM ou SEM o 9 depois do DDD. Aqui geramos as duas formas possíveis,
    pra reconhecer o assinante não importa em qual formato o número chegou.

    Ex.: "5545991382241" (com 9, 13 díg.) <-> "554591382241" (sem 9, 12 díg.)
    """
    tel = "".join(c for c in (telefone or "") if c.isdigit())
    variantes = [tel]
    if tel.startswith("55") and len(tel) == 13 and tel[4] == "9":
        variantes.append(tel[:4] + tel[5:])        # remove o 9 -> 12 dígitos
    elif tel.startswith("55") and len(tel) == 12:
        variantes.append(tel[:4] + "9" + tel[4:])  # adiciona o 9 -> 13 dígitos
    return variantes


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
    # 1) É assinante ativo? (checa as variações do número por causa do 9º dígito)
    for variante in _variantes_telefone(telefone):
        if _assinatura_valida(get_assinante(variante)):
            return {"liberado": True, "motivo": "assinante"}

    # 2) Não é assinante: ainda tem mensagem grátis sobrando?
    usuario = get_usuario(telefone)
    usadas = usuario["mensagens_gratis_usadas"] if usuario else 0

    if usadas < FREE_MESSAGES:
        return {"liberado": True, "motivo": "gratis"}

    # 3) Acabaram as grátis.
    return {"liberado": False, "motivo": "limite"}
