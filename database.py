   import asyncpg
import logging
from datetime import datetime

log = logging.getLogger("matbot.database")

class Database:
    def __init__(self, url: str):
        self.url = url
        self.pool: asyncpg.Pool = None

    async def init(self):
        self.pool = await asyncpg.create_pool(self.url, min_size=2, max_size=10)
        await self._criar_tabelas()
        log.info("Banco de dados PostgreSQL inicializado.")

    async def _criar_tabelas(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    moderador_id BIGINT NOT NULL,
                    tipo TEXT NOT NULL,
                    comentario TEXT,
                    duracao TEXT,
                    expira_em TEXT,
                    oculto INTEGER DEFAULT 0,
                    aprovado INTEGER DEFAULT 1,
                    criado_em TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS automod_padroes (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    tipo TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    acao TEXT NOT NULL DEFAULT 'deletar',
                    criado_em TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS automod_isentos (
                    guild_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                );

                CREATE TABLE IF NOT EXISTS clopen_canais (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    dono_id BIGINT,
                    estado TEXT NOT NULL DEFAULT 'disponivel',
                    ultima_msg TEXT,
                    aberto_em TEXT
                );

                CREATE TABLE IF NOT EXISTS clopen_config (
                    guild_id BIGINT PRIMARY KEY,
                    categoria_disponivel BIGINT,
                    categoria_ocupado BIGINT,
                    categoria_fechado BIGINT,
                    timeout_dono INTEGER DEFAULT 1800,
                    timeout_geral INTEGER DEFAULT 3600,
                    min_disponivel INTEGER DEFAULT 2,
                    max_disponivel INTEGER DEFAULT 5,
                    max_canais INTEGER DEFAULT 20
                );

                CREATE TABLE IF NOT EXISTS lembretes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT,
                    channel_id BIGINT NOT NULL,
                    mensagem TEXT NOT NULL,
                    expira_em TEXT NOT NULL,
                    criado_em TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tags (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    nome TEXT NOT NULL,
                    conteudo TEXT NOT NULL,
                    criado_por BIGINT NOT NULL,
                    usos INTEGER DEFAULT 0,
                    criado_em TEXT NOT NULL,
                    UNIQUE(guild_id, nome)
                );

                CREATE TABLE IF NOT EXISTS tag_aliases (
                    guild_id BIGINT NOT NULL,
                    alias TEXT NOT NULL,
                    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (guild_id, alias)
                );

                CREATE TABLE IF NOT EXISTS rolereact (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    emoji TEXT NOT NULL,
                    role_id BIGINT NOT NULL,
                    UNIQUE(guild_id, message_id, emoji)
                );

                CREATE TABLE IF NOT EXISTS log_config (
                    guild_id BIGINT PRIMARY KEY,
                    canal_temp BIGINT,
                    canal_perm BIGINT,
                    manter_dias INTEGER DEFAULT 7
                );

                CREATE TABLE IF NOT EXISTS config (
                    guild_id BIGINT NOT NULL,
                    chave TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    PRIMARY KEY (guild_id, chave)
                );
            """)
        log.info("Tabelas verificadas/criadas.")

    async def execute(self, query: str, params=()):
        query = self._converter_placeholders(query)
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *params)

    async def execute_returning(self, query: str, params=()):
        """Executa INSERT RETURNING id e retorna o valor gerado."""
        query = self._converter_placeholders(query)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *params)

    async def fetchone(self, query: str, params=()):
        query = self._converter_placeholders(query)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *params)

    async def fetchall(self, query: str, params=()):
        query = self._converter_placeholders(query)
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)

    def _converter_placeholders(self, query: str) -> str:
        """Converte ? para $1, $2, $3... compativel com asyncpg."""
        resultado = []
        contador = 1
        for char in query:
            if char == '?':
                resultado.append(f'${contador}')
                contador += 1
            else:
                resultado.append(char)
        return ''.join(resultado)

    async def get_config(self, guild_id: int, chave: str, padrao=None):
        row = await self.fetchone(
            "SELECT valor FROM config WHERE guild_id = ? AND chave = ?",
            (guild_id, chave)
        )
        return row["valor"] if row else padrao

    async def set_config(self, guild_id: int, chave: str, valor: str):
        await self.execute(
            """INSERT INTO config (guild_id, chave, valor) VALUES (?, ?, ?)
               ON CONFLICT (guild_id, chave) DO UPDATE SET valor = EXCLUDED.valor""",
            (guild_id, chave, valor)
        )

    def agora(self) -> str:
        return datetime.utcnow().isoformat()
             
