"""
db.py
-----
Tudo que mexe no banco de dados (SQLite) fica aqui, isolado do resto.

Por que isolar? Pra você poder, no futuro, trocar o SQLite por um banco maior
(ex.: Postgres) mexendo SÓ neste arquivo, sem bagunçar o resto do bot.

SQLite é um banco que vive num único arquivo (ex.: davi.db). É simples e perfeito
pra começar. Cada função abre uma conexão, faz o que precisa e fecha — assim
funciona bem mesmo com várias mensagens chegando ao mesmo tempo.
"""

import sqlite3
from datetime import datetime, timezone

from config import DATABASE_PATH


def _conectar():
    """Abre uma conexão com o banco. Uso interno (o "_" indica isso)."""
    conexao = sqlite3.connect(DATABASE_PATH)
    # row_factory faz cada linha vir como um dicionário-like (acesso por nome de coluna).
    conexao.row_factory = sqlite3.Row
    return conexao


def _agora_iso():
    """Retorna a data/hora atual em texto padrão ISO (ex.: 2026-06-03T15:30:00+00:00)."""
    return datetime.now(timezone.utc).isoformat()


def init_db():
    """
    Cria as tabelas se elas ainda não existirem.
    É seguro chamar quantas vezes quiser — só cria o que falta.
    Chamado quando o app sobe e no início dos scripts (ex.: devocional).
    """
    conexao = _conectar()
    cursor = conexao.cursor()

    # Pessoas que conversam com o Davi.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            telefone TEXT PRIMARY KEY,
            nome TEXT,
            mensagens_gratis_usadas INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT
        )
        """
    )

    # Quem é assinante e até quando.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS assinantes (
            telefone TEXT PRIMARY KEY,
            ativo INTEGER NOT NULL DEFAULT 0,
            expira_em TEXT,
            atualizado_em TEXT
        )
        """
    )

    # Histórico de conversa (pra dar "memória" ao Davi).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefone TEXT,
            papel TEXT,        -- "user" (pessoa) ou "model" (Davi)
            texto TEXT,
            criado_em TEXT
        )
        """
    )

    conexao.commit()
    conexao.close()


# -------------------- Usuários --------------------

def upsert_usuario(telefone, nome):
    """
    Cria o usuário se ele não existir; se já existir, atualiza o nome.
    ("upsert" = update + insert.)
    """
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute(
        """
        INSERT INTO usuarios (telefone, nome, mensagens_gratis_usadas, criado_em)
        VALUES (?, ?, 0, ?)
        ON CONFLICT(telefone) DO UPDATE SET nome = excluded.nome
        """,
        (telefone, nome, _agora_iso()),
    )
    conexao.commit()
    conexao.close()


def get_usuario(telefone):
    """Retorna os dados do usuário como dicionário, ou None se não existir."""
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE telefone = ?", (telefone,))
    linha = cursor.fetchone()
    conexao.close()
    return dict(linha) if linha else None


def incrementar_gratis(telefone):
    """Soma 1 no contador de mensagens grátis já usadas pela pessoa."""
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "UPDATE usuarios SET mensagens_gratis_usadas = mensagens_gratis_usadas + 1 WHERE telefone = ?",
        (telefone,),
    )
    conexao.commit()
    conexao.close()


# -------------------- Mensagens (histórico) --------------------

def salvar_mensagem(telefone, papel, texto):
    """
    Guarda uma mensagem no histórico.
    papel = "user" pra mensagem da pessoa, "model" pra resposta do Davi.
    """
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute(
        "INSERT INTO mensagens (telefone, papel, texto, criado_em) VALUES (?, ?, ?, ?)",
        (telefone, papel, texto, _agora_iso()),
    )
    conexao.commit()
    conexao.close()


def ultimas_mensagens(telefone, limite=12):
    """
    Retorna as últimas mensagens da pessoa, em ORDEM CRONOLÓGICA (mais antiga
    primeiro), que é o formato que a IA espera pra entender a conversa.

    Retorna uma lista de dicionários: [{"role": "user"/"model", "text": "..."}, ...]
    """
    conexao = _conectar()
    cursor = conexao.cursor()
    # Pegamos as N mais recentes (DESC) e depois invertemos pra ficar em ordem.
    cursor.execute(
        "SELECT papel, texto FROM mensagens WHERE telefone = ? ORDER BY id DESC LIMIT ?",
        (telefone, limite),
    )
    linhas = cursor.fetchall()
    conexao.close()

    linhas = list(reversed(linhas))  # mais antiga primeiro
    return [{"role": linha["papel"], "text": linha["texto"]} for linha in linhas]


# -------------------- Assinantes --------------------

def set_assinante(telefone, ativo, expira_em=None):
    """
    Marca (ou desmarca) alguém como assinante.
    ativo = True/False; expira_em = texto ISO da data de expiração (ou None).
    """
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute(
        """
        INSERT INTO assinantes (telefone, ativo, expira_em, atualizado_em)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telefone) DO UPDATE SET
            ativo = excluded.ativo,
            expira_em = excluded.expira_em,
            atualizado_em = excluded.atualizado_em
        """,
        (telefone, 1 if ativo else 0, expira_em, _agora_iso()),
    )
    conexao.commit()
    conexao.close()


def get_assinante(telefone):
    """Retorna o registro de assinante como dicionário, ou None se não existir."""
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute("SELECT * FROM assinantes WHERE telefone = ?", (telefone,))
    linha = cursor.fetchone()
    conexao.close()
    return dict(linha) if linha else None


def listar_assinantes_ativos():
    """
    Retorna a lista de telefones de TODOS os assinantes ativos.
    Usado pelo devocional diário pra saber pra quem enviar.
    Considera ativo = 1 e (sem data de expiração OU ainda não expirou).
    """
    agora = _agora_iso()
    conexao = _conectar()
    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT telefone FROM assinantes
        WHERE ativo = 1 AND (expira_em IS NULL OR expira_em > ?)
        """,
        (agora,),
    )
    linhas = cursor.fetchall()
    conexao.close()
    return [linha["telefone"] for linha in linhas]
