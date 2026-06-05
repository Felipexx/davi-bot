"""
db.py
-----
Tudo que mexe no banco de dados fica aqui, isolado do resto.

Suporta DOIS bancos, escolhido automaticamente:
- Se existir a variável de ambiente DATABASE_URL  -> usa PostgreSQL (recomendado em
  produção: os dados ficam num banco externo e NUNCA se perdem quando o servidor reinicia).
- Se NÃO existir DATABASE_URL                     -> usa SQLite (arquivo local davi.db),
  bom para testar na sua máquina.

As funções têm a mesma "cara" nos dois casos, então o resto do bot não muda nada.
"""

import os
from datetime import datetime, timezone

from config import DATABASE_PATH

# Decide qual banco usar com base na presença da DATABASE_URL.
DATABASE_URL = os.getenv("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

# Marcador de parâmetro: Postgres usa %s, SQLite usa ?.
PH = "%s" if USE_PG else "?"


def _conectar():
    """Abre uma conexão com o banco escolhido. Uso interno (o "_" indica isso)."""
    if USE_PG:
        return psycopg2.connect(DATABASE_URL)
    conexao = sqlite3.connect(DATABASE_PATH)
    # row_factory faz cada linha vir como um dicionário-like (acesso por nome de coluna).
    conexao.row_factory = sqlite3.Row
    return conexao


def _cursor(conexao):
    """Cria um cursor que devolve linhas acessíveis por nome de coluna nos dois bancos."""
    if USE_PG:
        return conexao.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conexao.cursor()


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
    cursor = _cursor(conexao)

    # Tipo da coluna de id autoincremental muda entre os bancos.
    id_auto = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

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
        f"""
        CREATE TABLE IF NOT EXISTS mensagens (
            id {id_auto},
            telefone TEXT,
            papel TEXT,
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
    cursor = _cursor(conexao)
    cursor.execute(
        f"""
        INSERT INTO usuarios (telefone, nome, mensagens_gratis_usadas, criado_em)
        VALUES ({PH}, {PH}, 0, {PH})
        ON CONFLICT(telefone) DO UPDATE SET nome = excluded.nome
        """,
        (telefone, nome, _agora_iso()),
    )
    conexao.commit()
    conexao.close()


def get_usuario(telefone):
    """Retorna os dados do usuário como dicionário, ou None se não existir."""
    conexao = _conectar()
    cursor = _cursor(conexao)
    cursor.execute(f"SELECT * FROM usuarios WHERE telefone = {PH}", (telefone,))
    linha = cursor.fetchone()
    conexao.close()
    return dict(linha) if linha else None


def incrementar_gratis(telefone):
    """Soma 1 no contador de mensagens grátis já usadas pela pessoa."""
    conexao = _conectar()
    cursor = _cursor(conexao)
    cursor.execute(
        f"UPDATE usuarios SET mensagens_gratis_usadas = mensagens_gratis_usadas + 1 WHERE telefone = {PH}",
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
    cursor = _cursor(conexao)
    cursor.execute(
        f"INSERT INTO mensagens (telefone, papel, texto, criado_em) VALUES ({PH}, {PH}, {PH}, {PH})",
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
    cursor = _cursor(conexao)
    cursor.execute(
        f"SELECT papel, texto FROM mensagens WHERE telefone = {PH} ORDER BY id DESC LIMIT {PH}",
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
    cursor = _cursor(conexao)
    cursor.execute(
        f"""
        INSERT INTO assinantes (telefone, ativo, expira_em, atualizado_em)
        VALUES ({PH}, {PH}, {PH}, {PH})
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
    cursor = _cursor(conexao)
    cursor.execute(f"SELECT * FROM assinantes WHERE telefone = {PH}", (telefone,))
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
    cursor = _cursor(conexao)
    cursor.execute(
        f"""
        SELECT telefone FROM assinantes
        WHERE ativo = 1 AND (expira_em IS NULL OR expira_em > {PH})
        """,
        (agora,),
    )
    linhas = cursor.fetchall()
    conexao.close()
    return [linha["telefone"] for linha in linhas]
