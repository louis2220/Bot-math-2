import aiosqlite
import logging
from datetime import datetime

log = logging.getLogger("matbot.database")

class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: aiosqlite.Connection = None

    async def init(self):
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self._criar_tabelas()
        log.info("Banco de dados inicializado.")

    async def _criar_tabelas(self):
        await self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderador_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                comentario TEXT,
                duracao TEXT,
                expira_em TEXT,
                oculto INTEGER DEFAULT 0,
                aprovado INTEGER DEFAULT 1,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automod_padroes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                valor TEXT NOT NULL,
                acao TEXT NOT NULL DEFAULT 'deletar',
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS automod_isentos (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,
                PRIMARY KEY (guild_id, role_id)
            );

            CREATE TABLE IF NOT EXISTS clopen_canais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                dono_id INTEGER,
                estado TEXT NOT NULL DEFAULT 'disponivel',
                ultima_msg TEXT,
                aberto_em TEXT
            );

            CREATE TABLE IF NOT EXISTS clopen_config (
                guild_id INTEGER PRIMARY KEY,
                categoria_disponivel INTEGER,
                categoria_ocupado INTEGER,
                categoria_fechado INTEGER,
                timeout_dono INTEGER DEFAULT 1800,
                timeout_geral INTEGER DEFAULT 3600,
                min_disponivel INTEGER DEFAULT 2,
                max_disponivel INTEGER DEFAULT 5,
                max_canais INTEGER DEFAULT 20
            );

            CREATE TABLE IF NOT EXISTS lembretes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER,
                channel_id INTEGER NOT NULL,
                mensagem TEXT NOT NULL,
                expira_em TEXT NOT NULL,
                criado_em TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                nome TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                criado_por INTEGER NOT NULL,
                usos INTEGER DEFAULT 0,
                criado_em TEXT NOT NULL,
                UNIQUE(guild_id, nome)
            );

            CREATE TABLE IF NOT EXISTS tag_aliases (
                guild_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (guild_id, alias)
            );

            CREATE TABLE IF NOT EXISTS rolereact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                emoji TEXT NOT NULL,
                role_id INTEGER NOT NULL,
                UNIQUE(guild_id, message_id, emoji)
            );

            CREATE TABLE IF NOT EXISTS log_config (
                guild_id INTEGER PRIMARY KEY,
                canal_temp INTEGER,
                canal_perm INTEGER,
                manter_dias INTEGER DEFAULT 7
            );

            CREATE TABLE IF NOT EXISTS config (
                guild_id INTEGER NOT NULL,
                chave TEXT NOT NULL,
                valor TEXT NOT NULL,
                PRIMARY KEY (guild_id, chave)
            );
        """)
        await self.conn.commit()

    async def execute(self, query: str, params=()) -> aiosqlite.Cursor:
        cursor = await self.conn.execute(query, params)
        await self.conn.commit()
        return cursor

    async def fetchone(self, query: str, params=()):
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(self, query: str, params=()):
        cursor = await self.conn.execute(query, params)
        return await cursor.fetchall()

    async def get_config(self, guild_id: int, chave: str, padrao=None):
        row = await self.fetchone(
            "SELECT valor FROM config WHERE guild_id = ? AND chave = ?",
            (guild_id, chave)
        )
        return row["valor"] if row else padrao

    async def set_config(self, guild_id: int, chave: str, valor: str):
        await self.execute(
            "INSERT OR REPLACE INTO config (guild_id, chave, valor) VALUES (?, ?, ?)",
            (guild_id, chave, valor)
        )

    def agora(self) -> str:
        return datetime.utcnow().isoformat()
