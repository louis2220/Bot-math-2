import discord
from discord.ext import commands
import logging

log = logging.getLogger("matbot.rolereact")


class RoleReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        await self._processar_reacao(payload, adicionar=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        await self._processar_reacao(payload, adicionar=False)

    async def _processar_reacao(self, payload: discord.RawReactionActionEvent, adicionar: bool):
        emoji = str(payload.emoji)
        row = await self.db.fetchone(
            "SELECT role_id FROM rolereact WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (payload.guild_id, payload.message_id, emoji)
        )
        if not row:
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        role = guild.get_role(row["role_id"])
        if not role:
            return
        membro = guild.get_member(payload.user_id)
        if not membro:
            return
        try:
            if adicionar:
                await membro.add_roles(role, reason="Role-react")
            else:
                await membro.remove_roles(role, reason="Role-react")
        except discord.HTTPException as e:
            log.error(f"Erro ao {'adicionar' if adicionar else 'remover'} cargo: {e}")

    @commands.group(name="rolereact", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def rolereact(self, ctx):
        """Gerencia cargos por reacao. Subcomandos: new, add, remove, list, show."""
        await ctx.send(f"Subcomandos: `new`, `add`, `remove`, `list`, `show`.")

    @rolereact.command(name="new")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_new(self, ctx, mensagem_id: int, canal: discord.TextChannel = None):
        """Registra uma mensagem para ter role-react. Informe o ID da mensagem."""
        canal = canal or ctx.channel
        try:
            msg = await canal.fetch_message(mensagem_id)
        except discord.NotFound:
            await ctx.send("Mensagem nao encontrada.")
            return
        # Verifica se ja existe algum rolereact nessa mensagem
        existe = await self.db.fetchone(
            "SELECT id FROM rolereact WHERE guild_id = ? AND message_id = ?",
            (ctx.guild.id, mensagem_id)
        )
        if existe:
            await ctx.send("Esta mensagem ja tem role-reacts configurados. Use `rolereact add` para adicionar mais.")
            return
        await ctx.send(
            f"Mensagem `{mensagem_id}` registrada. Use `rolereact add {mensagem_id} <emoji> <cargo>` para adicionar."
        )

    @rolereact.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_add(self, ctx, mensagem_id: int, emoji: str, cargo: discord.Role, canal: discord.TextChannel = None):
        """Adiciona um par emoji/cargo a uma mensagem."""
        canal = canal or ctx.channel
        try:
            msg = await canal.fetch_message(mensagem_id)
        except discord.NotFound:
            await ctx.send("Mensagem nao encontrada.")
            return
        existe = await self.db.fetchone(
            "SELECT id FROM rolereact WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (ctx.guild.id, mensagem_id, emoji)
        )
        if existe:
            await ctx.send("Ja existe um role-react com esse emoji nessa mensagem.")
            return
        await self.db.execute(
            "INSERT INTO rolereact (guild_id, message_id, channel_id, emoji, role_id) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, mensagem_id, canal.id, emoji, cargo.id)
        )
        try:
            await msg.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.send("Role-react registrado, mas nao consegui reagir (emoji invalido ou sem permissao).")
            return
        await ctx.send(f"Role-react adicionado: {emoji} -> {cargo.mention}.")

    @rolereact.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_remove(self, ctx, mensagem_id: int, emoji: str):
        """Remove um role-react de uma mensagem."""
        r = await self.db.fetchone(
            "SELECT id, channel_id FROM rolereact WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (ctx.guild.id, mensagem_id, emoji)
        )
        if not r:
            await ctx.send("Role-react nao encontrado.")
            return
        await self.db.execute(
            "DELETE FROM rolereact WHERE guild_id = ? AND message_id = ? AND emoji = ?",
            (ctx.guild.id, mensagem_id, emoji)
        )
        canal = ctx.guild.get_channel(r["channel_id"])
        if canal:
            try:
                msg = await canal.fetch_message(mensagem_id)
                await msg.clear_reaction(emoji)
            except discord.HTTPException:
                pass
        await ctx.send(f"Role-react {emoji} removido da mensagem `{mensagem_id}`.")

    @rolereact.command(name="list")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_list(self, ctx):
        """Lista todas as mensagens com role-react."""
        rows = await self.db.fetchall(
            "SELECT DISTINCT message_id, channel_id FROM rolereact WHERE guild_id = ?",
            (ctx.guild.id,)
        )
        if not rows:
            await ctx.send("Nenhuma mensagem com role-react configurada.")
            return
        linhas = []
        for r in rows:
            canal = ctx.guild.get_channel(r["channel_id"])
            canal_str = canal.mention if canal else f"Canal {r['channel_id']}"
            linhas.append(f"Mensagem `{r['message_id']}` em {canal_str}")
        embed = discord.Embed(
            title="Mensagens com Role-React",
            description="\n".join(linhas),
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @rolereact.command(name="show")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_show(self, ctx, mensagem_id: int):
        """Mostra os role-reacts de uma mensagem especifica."""
        rows = await self.db.fetchall(
            "SELECT emoji, role_id FROM rolereact WHERE guild_id = ? AND message_id = ?",
            (ctx.guild.id, mensagem_id)
        )
        if not rows:
            await ctx.send("Nenhum role-react nessa mensagem.")
            return
        linhas = []
        for r in rows:
            cargo = ctx.guild.get_role(r["role_id"])
            cargo_str = cargo.mention if cargo else f"Cargo {r['role_id']}"
            linhas.append(f"{r['emoji']} -> {cargo_str}")
        embed = discord.Embed(
            title=f"Role-Reacts da mensagem {mensagem_id}",
            description="\n".join(linhas),
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @rolereact.command(name="delete")
    @commands.has_permissions(manage_roles=True)
    async def rolereact_delete(self, ctx, mensagem_id: int):
        """Remove todos os role-reacts de uma mensagem."""
        rows = await self.db.fetchall(
            "SELECT emoji, channel_id FROM rolereact WHERE guild_id = ? AND message_id = ?",
            (ctx.guild.id, mensagem_id)
        )
        if not rows:
            await ctx.send("Nenhum role-react nessa mensagem.")
            return
        canal_id = rows[0]["channel_id"]
        canal = ctx.guild.get_channel(canal_id)
        await self.db.execute(
            "DELETE FROM rolereact WHERE guild_id = ? AND message_id = ?",
            (ctx.guild.id, mensagem_id)
        )
        if canal:
            try:
                msg = await canal.fetch_message(mensagem_id)
                await msg.clear_reactions()
            except discord.HTTPException:
                pass
        await ctx.send(f"Todos os role-reacts da mensagem `{mensagem_id}` foram removidos.")


async def setup(bot):
    await bot.add_cog(RoleReact(bot))
