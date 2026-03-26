import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import logging

log = logging.getLogger("matbot.clopen")

ESTADOS = ("disponivel", "ocupado", "pendente", "fechado")


class Clopen(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._pendentes: dict[int, asyncio.Task] = {}

    @property
    def db(self):
        return self.bot.db

    async def _get_config(self, guild_id: int):
        return await self.db.fetchone(
            "SELECT * FROM clopen_config WHERE guild_id = ?", (guild_id,)
        )

    async def _get_canal(self, channel_id: int):
        return await self.db.fetchone(
            "SELECT * FROM clopen_canais WHERE channel_id = ?", (channel_id,)
        )

    async def _set_estado(self, channel_id: int, estado: str, dono_id=None):
        agora = self.db.agora()
        if dono_id is not None:
            await self.db.execute(
                "UPDATE clopen_canais SET estado = ?, dono_id = ?, ultima_msg = ?, aberto_em = ? WHERE channel_id = ?",
                (estado, dono_id, agora, agora, channel_id)
            )
        else:
            await self.db.execute(
                "UPDATE clopen_canais SET estado = ?, ultima_msg = ? WHERE channel_id = ?",
                (estado, agora, channel_id)
            )

    @commands.Cog.listener()
    async def on_message(self, mensagem: discord.Message):
        if not mensagem.guild or mensagem.author.bot:
            return
        canal = await self._get_canal(mensagem.channel.id)
        if not canal:
            return

        if canal["estado"] == "disponivel":
            await self._set_estado(mensagem.channel.id, "ocupado", mensagem.author.id)
            await mensagem.channel.send(
                f"{mensagem.author.mention}, seu canal de ajuda foi aberto. "
                f"Use `{self.bot.command_prefix}fechar` quando sua duvida for resolvida."
            )
            try:
                await mensagem.pin()
            except discord.HTTPException:
                pass
        elif canal["estado"] in ("ocupado", "pendente"):
            await self.db.execute(
                "UPDATE clopen_canais SET ultima_msg = ? WHERE channel_id = ?",
                (self.db.agora(), mensagem.channel.id)
            )
            # Cancela pendencia se houver
            if canal["estado"] == "pendente" and mensagem.channel.id in self._pendentes:
                self._pendentes[mensagem.channel.id].cancel()
                await self._set_estado(mensagem.channel.id, "ocupado")

    @commands.command(name="fechar", aliases=["close"])
    async def fechar(self, ctx):
        """Fecha o canal de ajuda atual."""
        canal = await self._get_canal(ctx.channel.id)
        if not canal:
            await ctx.send("Este canal nao faz parte do sistema de ajuda.")
            return
        if canal["estado"] not in ("ocupado", "pendente", "disponivel"):
            await ctx.send("Este canal ja esta fechado.")
            return

        eh_dono = canal["dono_id"] == ctx.author.id
        tem_permissao = ctx.author.guild_permissions.manage_channels

        if not eh_dono and not tem_permissao:
            await ctx.send("Apenas o dono do canal ou um moderador pode fechar.")
            return

        await self._set_estado(ctx.channel.id, "fechado")
        if ctx.channel.id in self._pendentes:
            self._pendentes[ctx.channel.id].cancel()

        await ctx.send("Canal fechado. Obrigado por usar o canal de ajuda.")

        config = await self._get_config(ctx.guild.id)
        if config and config["categoria_fechado"]:
            cat = ctx.guild.get_channel(config["categoria_fechado"])
            if cat:
                try:
                    await ctx.channel.edit(category=cat)
                except discord.HTTPException:
                    pass

        # Apos 10 min, redefine para disponivel
        await asyncio.sleep(600)
        await self._set_estado(ctx.channel.id, "disponivel", None)
        config = await self._get_config(ctx.guild.id)
        if config and config["categoria_disponivel"]:
            cat = ctx.guild.get_channel(config["categoria_disponivel"])
            if cat:
                try:
                    await ctx.channel.edit(category=cat)
                except discord.HTTPException:
                    pass

    @commands.command(name="reabrir", aliases=["reopen"])
    async def reabrir(self, ctx):
        """Reabre um canal de ajuda fechado."""
        canal = await self._get_canal(ctx.channel.id)
        if not canal:
            await ctx.send("Este canal nao faz parte do sistema de ajuda.")
            return
        if canal["estado"] not in ("fechado", "disponivel"):
            await ctx.send("Este canal nao esta fechado.")
            return

        eh_dono = canal["dono_id"] == ctx.author.id
        tem_permissao = ctx.author.guild_permissions.manage_channels

        if not eh_dono and not tem_permissao:
            await ctx.send("Apenas o dono do canal ou um moderador pode reabrir.")
            return

        await self._set_estado(ctx.channel.id, "ocupado", ctx.author.id)
        config = await self._get_config(ctx.guild.id)
        if config and config["categoria_ocupado"]:
            cat = ctx.guild.get_channel(config["categoria_ocupado"])
            if cat:
                try:
                    await ctx.channel.edit(category=cat)
                except discord.HTTPException:
                    pass
        await ctx.send(f"Canal reaberto por {ctx.author.mention}.")

    @commands.command(name="clopen_sync")
    @commands.has_permissions(manage_channels=True)
    async def clopen_sync(self, ctx):
        """Sincroniza o estado de todos os canais do sistema."""
        config = await self._get_config(ctx.guild.id)
        if not config:
            await ctx.send("Sistema clopen nao configurado. Use `clopenconfig`.")
            return
        rows = await self.db.fetchall(
            "SELECT * FROM clopen_canais WHERE guild_id = ?", (ctx.guild.id,)
        )
        atualizados = 0
        for row in rows:
            ch = ctx.guild.get_channel(row["channel_id"])
            if not ch:
                continue
            estado = row["estado"]
            cat_alvo = None
            if estado == "disponivel" and config["categoria_disponivel"]:
                cat_alvo = ctx.guild.get_channel(config["categoria_disponivel"])
            elif estado in ("ocupado", "pendente") and config["categoria_ocupado"]:
                cat_alvo = ctx.guild.get_channel(config["categoria_ocupado"])
            elif estado == "fechado" and config["categoria_fechado"]:
                cat_alvo = ctx.guild.get_channel(config["categoria_fechado"])
            if cat_alvo and ch.category_id != cat_alvo.id:
                try:
                    await ch.edit(category=cat_alvo)
                    atualizados += 1
                except discord.HTTPException:
                    pass
        await ctx.send(f"Sincronizacao concluida. {atualizados} canal(is) movido(s).")

    # --- Configuracao ---

    @commands.group(name="clopenconfig", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def clopenconfig(self, ctx):
        """Configura o sistema de canais de ajuda."""
        config = await self._get_config(ctx.guild.id)
        if not config:
            await ctx.send("Sistema nao configurado. Use os subcomandos: `new`, `disponivel`, `ocupado`, `fechado`.")
            return
        embed = discord.Embed(title="Configuracao Clopen", color=0x2b2d31)
        embed.add_field(name="Cat. Disponivel", value=str(config["categoria_disponivel"] or "Nao definida"))
        embed.add_field(name="Cat. Ocupado", value=str(config["categoria_ocupado"] or "Nao definida"))
        embed.add_field(name="Cat. Fechado", value=str(config["categoria_fechado"] or "Nao definida"))
        await ctx.send(embed=embed)

    @clopenconfig.command(name="new")
    @commands.has_permissions(administrator=True)
    async def clopenconfig_new(self, ctx,
                               cat_disponivel: discord.CategoryChannel,
                               cat_ocupado: discord.CategoryChannel,
                               cat_fechado: discord.CategoryChannel):
        """Configura as tres categorias do sistema clopen."""
        await self.db.execute(
            """INSERT OR REPLACE INTO clopen_config
               (guild_id, categoria_disponivel, categoria_ocupado, categoria_fechado)
               VALUES (?, ?, ?, ?)""",
            (ctx.guild.id, cat_disponivel.id, cat_ocupado.id, cat_fechado.id)
        )
        await ctx.send("Sistema clopen configurado.")

    @clopenconfig.command(name="add")
    @commands.has_permissions(administrator=True)
    async def clopenconfig_add(self, ctx, canal: discord.TextChannel):
        """Registra um canal de texto no sistema clopen."""
        existe = await self.db.fetchone(
            "SELECT id FROM clopen_canais WHERE channel_id = ?", (canal.id,)
        )
        if existe:
            await ctx.send("Canal ja registrado.")
            return
        await self.db.execute(
            "INSERT INTO clopen_canais (guild_id, channel_id, estado, aberto_em) VALUES (?, ?, 'disponivel', ?)",
            (ctx.guild.id, canal.id, self.db.agora())
        )
        await ctx.send(f"{canal.mention} adicionado ao sistema de canais de ajuda.")


async def setup(bot):
    await bot.add_cog(Clopen(bot))
