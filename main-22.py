import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
from database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
log = logging.getLogger("matbot")

PREFIXO = os.getenv("PREFIXO", ".")

intents = discord.Intents.all()

class MatBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIXO,
            intents=intents,
            help_command=None
        )
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            log.critical("DATABASE_URL nao encontrada nas variaveis de ambiente.")
            exit(1)
        # Railway fornece URLs com postgres://, asyncpg exige postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        self.db = Database(database_url)

    async def setup_hook(self):
        await self.db.init()
        plugins = [
            "plugins.ajuda",
            "plugins.tickets",
            "plugins.automod",
            "plugins.clopen",
            "plugins.lembretes",
            "plugins.tags",
            "plugins.rolereact",
            "plugins.logs",
            "plugins.honrado",
            "plugins.cores",
        ]
        for plugin in plugins:
            try:
                await self.load_extension(plugin)
                log.info(f"Plugin carregado: {plugin}")
            except Exception as e:
                log.error(f"Erro ao carregar {plugin}: {e}")

    async def on_ready(self):
        log.info(f"Bot conectado como {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"Matematica | {PREFIXO}ajuda"
            )
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            # Verifica se e uma tag
            tag_cog = self.get_cog("Tags")
            if tag_cog:
                await tag_cog.tentar_tag(ctx)
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("Voce nao tem permissao para usar este comando.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Argumento faltando: `{error.param.name}`. Use `{PREFIXO}ajuda {ctx.command}` para mais informacoes.")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send("Argumento invalido. Verifique o uso do comando.")
            return
        log.error(f"Erro no comando {ctx.command}: {error}", exc_info=True)

bot = MatBot()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.critical("DISCORD_TOKEN nao encontrado nas variaveis de ambiente.")
        exit(1)
    bot.run(token)
