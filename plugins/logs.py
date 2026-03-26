import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import logging

log = logging.getLogger("matbot.logs")


class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task: asyncio.Task = None

    @property
    def db(self):
        return self.bot.db

    async def cog_load(self):
        self._task = self.bot.loop.create_task(self._limpar_loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()

    async def _limpar_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._limpar_logs_temporarios()
            except Exception as e:
                log.error(f"Erro no loop de limpeza de logs: {e}")
            await asyncio.sleep(3600)

    async def _limpar_logs_temporarios(self):
        """Apaga mensagens antigas do canal de log temporario."""
        guilds = await self.db.fetchall("SELECT guild_id, canal_temp, manter_dias FROM log_config")
        for g in guilds:
            if not g["canal_temp"]:
                continue
            canal = self.bot.get_channel(g["canal_temp"])
            if not canal:
                continue
            limite = datetime.utcnow().timestamp() - (g["manter_dias"] * 86400)
            try:
                async for msg in canal.history(limit=500, oldest_first=True):
                    if msg.created_at.timestamp() < limite:
                        try:
                            await msg.delete()
                            await asyncio.sleep(0.5)
                        except discord.HTTPException:
                            pass
            except Exception as e:
                log.error(f"Erro ao limpar log temporario: {e}")

    async def _canal_temp(self, guild_id: int):
        row = await self.db.fetchone(
            "SELECT canal_temp FROM log_config WHERE guild_id = ?", (guild_id,)
        )
        if row and row["canal_temp"]:
            return self.bot.get_channel(row["canal_temp"])
        return None

    async def _canal_perm(self, guild_id: int):
        row = await self.db.fetchone(
            "SELECT canal_perm FROM log_config WHERE guild_id = ?", (guild_id,)
        )
        if row and row["canal_perm"]:
            return self.bot.get_channel(row["canal_perm"])
        return None

    # --- Eventos de mensagem ---

    @commands.Cog.listener()
    async def on_message_edit(self, antes: discord.Message, depois: discord.Message):
        if not antes.guild or antes.author.bot:
            return
        if antes.content == depois.content:
            return
        canal = await self._canal_temp(antes.guild.id)
        if not canal:
            return
        embed = discord.Embed(
            title="Mensagem Editada",
            color=0xf39c12,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Autor", value=f"{antes.author} (`{antes.author.id}`)", inline=True)
        embed.add_field(name="Canal", value=antes.channel.mention, inline=True)
        embed.add_field(name="Antes", value=antes.content[:500] or "Sem texto", inline=False)
        embed.add_field(name="Depois", value=depois.content[:500] or "Sem texto", inline=False)
        embed.add_field(name="Link", value=f"[Ir para mensagem]({depois.jump_url})", inline=False)
        await canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, mensagem: discord.Message):
        if not mensagem.guild or mensagem.author.bot:
            return
        canal = await self._canal_temp(mensagem.guild.id)
        if not canal:
            return
        embed = discord.Embed(
            title="Mensagem Deletada",
            color=0xe74c3c,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Autor", value=f"{mensagem.author} (`{mensagem.author.id}`)", inline=True)
        embed.add_field(name="Canal", value=mensagem.channel.mention, inline=True)
        embed.add_field(name="Conteudo", value=mensagem.content[:500] or "Sem texto / Midia", inline=False)
        await canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, mensagens: list):
        if not mensagens or not mensagens[0].guild:
            return
        canal = await self._canal_perm(mensagens[0].guild.id)
        if not canal:
            return
        embed = discord.Embed(
            title="Mensagens Deletadas em Massa",
            description=f"{len(mensagens)} mensagens deletadas em {mensagens[0].channel.mention}",
            color=0xe74c3c,
            timestamp=datetime.utcnow()
        )
        await canal.send(embed=embed)

    # --- Eventos de membro ---

    @commands.Cog.listener()
    async def on_member_join(self, membro: discord.Member):
        canal = await self._canal_perm(membro.guild.id)
        if not canal:
            return
        embed = discord.Embed(
            title="Membro Entrou",
            description=f"{membro.mention} (`{membro.id}`)",
            color=0x2ecc71,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        embed.add_field(
            name="Conta criada em",
            value=membro.created_at.strftime("%d/%m/%Y %H:%M UTC")
        )
        await canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, membro: discord.Member):
        canal = await self._canal_perm(membro.guild.id)
        if not canal:
            return
        cargos = [r.mention for r in membro.roles if r.name != "@everyone"]
        embed = discord.Embed(
            title="Membro Saiu",
            description=f"{membro} (`{membro.id}`)",
            color=0xe74c3c,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=membro.display_avatar.url)
        if cargos:
            embed.add_field(name="Cargos", value=", ".join(cargos)[:500], inline=False)
        await canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, antes: discord.Member, depois: discord.Member):
        if antes.nick == depois.nick and antes.roles == depois.roles:
            return
        canal = await self._canal_temp(antes.guild.id)
        if not canal:
            return

        if antes.nick != depois.nick:
            embed = discord.Embed(
                title="Apelido Alterado",
                color=0x3498db,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Membro", value=f"{depois} (`{depois.id}`)", inline=False)
            embed.add_field(name="Antes", value=antes.nick or "Sem apelido", inline=True)
            embed.add_field(name="Depois", value=depois.nick or "Sem apelido", inline=True)
            await canal.send(embed=embed)

        if antes.roles != depois.roles:
            adicionados = [r for r in depois.roles if r not in antes.roles]
            removidos = [r for r in antes.roles if r not in depois.roles]
            if not adicionados and not removidos:
                return
            embed = discord.Embed(
                title="Cargos Alterados",
                color=0x9b59b6,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Membro", value=f"{depois} (`{depois.id}`)", inline=False)
            if adicionados:
                embed.add_field(name="Adicionados", value=", ".join(r.mention for r in adicionados), inline=True)
            if removidos:
                embed.add_field(name="Removidos", value=", ".join(r.mention for r in removidos), inline=True)
            await canal.send(embed=embed)

    # --- Configuracao ---

    @commands.group(name="logconfig", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def logconfig(self, ctx):
        """Configura os canais de log."""
        row = await self.db.fetchone(
            "SELECT * FROM log_config WHERE guild_id = ?", (ctx.guild.id,)
        )
        if not row:
            await ctx.send("Logs nao configurados. Use `logconfig temp <canal>` e `logconfig perm <canal>`.")
            return
        ct = ctx.guild.get_channel(row["canal_temp"]) if row["canal_temp"] else None
        cp = ctx.guild.get_channel(row["canal_perm"]) if row["canal_perm"] else None
        embed = discord.Embed(title="Configuracao de Logs", color=0x2b2d31)
        embed.add_field(name="Log Temporario", value=ct.mention if ct else "Nao definido")
        embed.add_field(name="Log Permanente", value=cp.mention if cp else "Nao definido")
        embed.add_field(name="Manter por", value=f"{row['manter_dias']} dias")
        await ctx.send(embed=embed)

    @logconfig.command(name="temp")
    @commands.has_permissions(administrator=True)
    async def logconfig_temp(self, ctx, canal: discord.TextChannel):
        """Define o canal de log temporario (edicoes, deletes)."""
        await self.db.execute(
            "INSERT OR IGNORE INTO log_config (guild_id, manter_dias) VALUES (?, 7)",
            (ctx.guild.id,)
        )
        await self.db.execute(
            "UPDATE log_config SET canal_temp = ? WHERE guild_id = ?",
            (canal.id, ctx.guild.id)
        )
        await self.bot.db.set_config(ctx.guild.id, "log_temp_channel", str(canal.id))
        await ctx.send(f"Canal de log temporario definido: {canal.mention}.")

    @logconfig.command(name="perm")
    @commands.has_permissions(administrator=True)
    async def logconfig_perm(self, ctx, canal: discord.TextChannel):
        """Define o canal de log permanente (entradas, saidas, banimentos)."""
        await self.db.execute(
            "INSERT OR IGNORE INTO log_config (guild_id, manter_dias) VALUES (?, 7)",
            (ctx.guild.id,)
        )
        await self.db.execute(
            "UPDATE log_config SET canal_perm = ? WHERE guild_id = ?",
            (canal.id, ctx.guild.id)
        )
        await ctx.send(f"Canal de log permanente definido: {canal.mention}.")

    @logconfig.command(name="manter")
    @commands.has_permissions(administrator=True)
    async def logconfig_manter(self, ctx, dias: int):
        """Define quantos dias o log temporario e mantido."""
        if dias < 1 or dias > 90:
            await ctx.send("Informe um valor entre 1 e 90 dias.")
            return
        await self.db.execute(
            "UPDATE log_config SET manter_dias = ? WHERE guild_id = ?",
            (dias, ctx.guild.id)
        )
        await ctx.send(f"Logs temporarios serao mantidos por {dias} dias.")


async def setup(bot):
    await bot.add_cog(Logs(bot))
