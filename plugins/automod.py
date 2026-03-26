import discord
from discord.ext import commands
import re
import logging

log = logging.getLogger("matbot.automod")

DOMINIOS_PHISHING = {
    "discord-nitro.gift", "discordnitro.gift", "free-nitro.ru",
    "steamcommunity.ru", "discord.gift.ru", "discordapp.io",
    "dlscord.io", "disсord.com",
}

class Automod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache: dict[int, list] = {}

    @property
    def db(self):
        return self.bot.db

    async def _carregar_padroes(self, guild_id: int):
        rows = await self.db.fetchall(
            "SELECT * FROM automod_padroes WHERE guild_id = ?", (guild_id,)
        )
        self._cache[guild_id] = list(rows)

    async def _padroes(self, guild_id: int):
        if guild_id not in self._cache:
            await self._carregar_padroes(guild_id)
        return self._cache[guild_id]

    async def _isentos(self, guild_id: int):
        rows = await self.db.fetchall(
            "SELECT role_id FROM automod_isentos WHERE guild_id = ?", (guild_id,)
        )
        return {r["role_id"] for r in rows}

    def _membro_isento(self, membro: discord.Member, isentos: set) -> bool:
        if membro.guild_permissions.manage_messages:
            return True
        return any(r.id in isentos for r in membro.roles)

    def _checar_phishing(self, conteudo: str) -> bool:
        urls = re.findall(r"https?://([^\s/]+)", conteudo)
        for dominio in urls:
            dominio_clean = dominio.lower().strip("www.")
            if dominio_clean in DOMINIOS_PHISHING:
                return True
        return False

    async def _aplicar_acao(self, mensagem: discord.Message, acao: str):
        try:
            await mensagem.delete()
        except discord.HTTPException:
            pass
        membro = mensagem.author
        canal = mensagem.channel

        if acao == "deletar":
            pass
        elif acao == "mute":
            mute_role_id = await self.db.get_config(mensagem.guild.id, "mute_role")
            if mute_role_id:
                role = mensagem.guild.get_role(int(mute_role_id))
                if role:
                    try:
                        await membro.add_roles(role, reason="Automod: padrao detectado")
                    except discord.HTTPException:
                        pass
        elif acao == "kick":
            try:
                await membro.kick(reason="Automod: padrao detectado")
            except discord.HTTPException:
                pass
        elif acao == "ban":
            try:
                await membro.ban(reason="Automod: phishing ou padrao grave detectado", delete_message_days=1)
            except discord.HTTPException:
                pass

        log_canal_id = await self.db.get_config(mensagem.guild.id, "log_temp_channel")
        if log_canal_id:
            log_canal = mensagem.guild.get_channel(int(log_canal_id))
            if log_canal:
                embed = discord.Embed(
                    title="Automod — Mensagem Removida",
                    color=0xe74c3c
                )
                embed.add_field(name="Usuario", value=f"{membro} (`{membro.id}`)", inline=True)
                embed.add_field(name="Canal", value=canal.mention, inline=True)
                embed.add_field(name="Acao", value=acao, inline=True)
                embed.add_field(name="Conteudo", value=mensagem.content[:500] or "Sem texto", inline=False)
                await log_canal.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, mensagem: discord.Message):
        if not mensagem.guild or mensagem.author.bot:
            return

        isentos = await self._isentos(mensagem.guild.id)
        if self._membro_isento(mensagem.author, isentos):
            return

        conteudo = mensagem.content

        # Phishing tem prioridade maxima
        if self._checar_phishing(conteudo):
            log.info(f"Phishing detectado de {mensagem.author} em {mensagem.guild}")
            await self._aplicar_acao(mensagem, "ban")
            return

        padroes = await self._padroes(mensagem.guild.id)
        for padrao in padroes:
            tipo = padrao["tipo"]
            valor = padrao["valor"]
            acao = padrao["acao"]
            correspondeu = False

            if tipo == "substring":
                correspondeu = valor.lower() in conteudo.lower()
            elif tipo == "palavra":
                correspondeu = bool(re.search(rf"\b{re.escape(valor)}\b", conteudo, re.IGNORECASE))
            elif tipo == "regex":
                try:
                    correspondeu = bool(re.search(valor, conteudo, re.IGNORECASE))
                except re.error:
                    pass

            if correspondeu:
                await self._aplicar_acao(mensagem, acao)
                return

    # --- Comandos ---

    @commands.group(name="automod", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        """Gerencia o sistema de moderacao automatica."""
        await ctx.send(f"Subcomandos: `lista`, `add`, `remove`, `acao`, `isento`. Use `{self.bot.command_prefix}ajuda automod`.")

    @automod.command(name="lista")
    @commands.has_permissions(manage_guild=True)
    async def automod_lista(self, ctx):
        """Lista todos os padroes de automod."""
        rows = await self.db.fetchall(
            "SELECT * FROM automod_padroes WHERE guild_id = ? ORDER BY id", (ctx.guild.id,)
        )
        if not rows:
            await ctx.send("Nenhum padrao configurado.")
            return
        linhas = [f"**#{r['id']}** `[{r['tipo']}]` `{r['valor']}` — Acao: `{r['acao']}`" for r in rows]
        embed = discord.Embed(title="Padroes de Automod", description="\n".join(linhas), color=0x2b2d31)
        await ctx.send(embed=embed)

    @automod.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def automod_add(self, ctx, tipo: str, *, valor: str):
        """Adiciona um padrao. Tipos: substring, palavra, regex."""
        tipo = tipo.lower()
        if tipo not in ("substring", "palavra", "regex"):
            await ctx.send("Tipo invalido. Use: `substring`, `palavra` ou `regex`.")
            return
        if tipo == "regex":
            try:
                re.compile(valor)
            except re.error as e:
                await ctx.send(f"Regex invalida: {e}")
                return
        await self.db.execute(
            "INSERT INTO automod_padroes (guild_id, tipo, valor, acao, criado_em) VALUES (?, ?, ?, 'deletar', ?)",
            (ctx.guild.id, tipo, valor, self.db.agora())
        )
        self._cache.pop(ctx.guild.id, None)
        await ctx.send(f"Padrao `{valor}` do tipo `{tipo}` adicionado. Acao padrao: deletar.")

    @automod.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def automod_remove(self, ctx, id_padrao: int):
        """Remove um padrao pelo ID."""
        r = await self.db.fetchone(
            "SELECT id FROM automod_padroes WHERE id = ? AND guild_id = ?", (id_padrao, ctx.guild.id)
        )
        if not r:
            await ctx.send("Padrao nao encontrado.")
            return
        await self.db.execute("DELETE FROM automod_padroes WHERE id = ?", (id_padrao,))
        self._cache.pop(ctx.guild.id, None)
        await ctx.send(f"Padrao #{id_padrao} removido.")

    @automod.command(name="acao")
    @commands.has_permissions(manage_guild=True)
    async def automod_acao(self, ctx, id_padrao: int, acao: str):
        """Define a acao de um padrao: deletar, mute, kick, ban."""
        acao = acao.lower()
        if acao not in ("deletar", "mute", "kick", "ban"):
            await ctx.send("Acao invalida. Use: `deletar`, `mute`, `kick` ou `ban`.")
            return
        r = await self.db.fetchone(
            "SELECT id FROM automod_padroes WHERE id = ? AND guild_id = ?", (id_padrao, ctx.guild.id)
        )
        if not r:
            await ctx.send("Padrao nao encontrado.")
            return
        await self.db.execute("UPDATE automod_padroes SET acao = ? WHERE id = ?", (acao, id_padrao))
        self._cache.pop(ctx.guild.id, None)
        await ctx.send(f"Acao do padrao #{id_padrao} definida para `{acao}`.")

    @automod.group(name="isento", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod_isento(self, ctx):
        """Gerencia cargos isentos do automod."""
        rows = await self.db.fetchall(
            "SELECT role_id FROM automod_isentos WHERE guild_id = ?", (ctx.guild.id,)
        )
        if not rows:
            await ctx.send("Nenhum cargo isento.")
            return
        cargos = []
        for r in rows:
            role = ctx.guild.get_role(r["role_id"])
            cargos.append(role.mention if role else f"ID {r['role_id']}")
        await ctx.send("Cargos isentos: " + ", ".join(cargos))

    @automod_isento.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def automod_isento_add(self, ctx, cargo: discord.Role):
        """Adiciona um cargo a lista de isentos."""
        await self.db.execute(
            "INSERT OR IGNORE INTO automod_isentos (guild_id, role_id) VALUES (?, ?)",
            (ctx.guild.id, cargo.id)
        )
        await ctx.send(f"{cargo.mention} adicionado aos isentos.")

    @automod_isento.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def automod_isento_remove(self, ctx, cargo: discord.Role):
        """Remove um cargo da lista de isentos."""
        await self.db.execute(
            "DELETE FROM automod_isentos WHERE guild_id = ? AND role_id = ?",
            (ctx.guild.id, cargo.id)
        )
        await ctx.send(f"{cargo.mention} removido dos isentos.")

    @commands.command(name="muterole")
    @commands.has_permissions(administrator=True)
    async def muterole(self, ctx, cargo: discord.Role):
        """Define o cargo usado para mute no automod."""
        await self.db.set_config(ctx.guild.id, "mute_role", str(cargo.id))
        await ctx.send(f"Cargo de mute definido: {cargo.mention}.")


async def setup(bot):
    await bot.add_cog(Automod(bot))
