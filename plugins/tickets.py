import discord
from discord.ext import commands
from datetime import datetime, timedelta
import re
import logging

log = logging.getLogger("matbot.tickets")

DURACAO_REGEX = re.compile(
    r"(?:(\d+)\s*(?:s|seg|segundo(?:s)?))?[,\s]*"
    r"(?:(\d+)\s*(?:m|min|minuto(?:s)?))?[,\s]*"
    r"(?:(\d+)\s*(?:h|hr|hora(?:s)?))?[,\s]*"
    r"(?:(\d+)\s*(?:d|dia(?:s)?))?[,\s]*"
    r"(?:(\d+)\s*(?:w|sem|semana(?:s)?))?[,\s]*"
    r"(?:(\d+)\s*(?:M|mes(?:es)?))?[,\s]*"
    r"(?:(\d+)\s*(?:a|ano(?:s)?))?",
    re.IGNORECASE
)

def parsear_duracao(texto: str):
    """Converte string de duracao para timedelta. Retorna None se permanente."""
    texto = texto.strip().lower()
    if texto in ("p", "perm", "permanente", ""):
        return None
    m = DURACAO_REGEX.match(texto)
    if not m or not any(m.groups()):
        return None
    s, mi, h, d, w, mo, a = (int(v) if v else 0 for v in m.groups())
    delta = timedelta(
        seconds=s,
        minutes=mi,
        hours=h,
        days=d + w * 7 + mo * 30 + a * 365
    )
    return delta if delta.total_seconds() > 0 else None

def formatar_delta(delta: timedelta) -> str:
    if delta is None:
        return "Permanente"
    total = int(delta.total_seconds())
    partes = []
    if total >= 86400:
        partes.append(f"{total // 86400}d")
        total %= 86400
    if total >= 3600:
        partes.append(f"{total // 3600}h")
        total %= 3600
    if total >= 60:
        partes.append(f"{total // 60}m")
        total %= 60
    if total > 0:
        partes.append(f"{total}s")
    return " ".join(partes) if partes else "0s"


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    async def _criar_ticket(self, guild_id, user_id, mod_id, tipo, comentario=None, duracao=None):
        expira_em = None
        if duracao:
            expira_em = (datetime.utcnow() + duracao).isoformat()
        cursor = await self.db.execute(
            """INSERT INTO tickets (guild_id, user_id, moderador_id, tipo, comentario, duracao, expira_em, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, mod_id, tipo, comentario,
             formatar_delta(duracao), expira_em, self.db.agora())
        )
        return cursor.lastrowid

    async def _checar_canal_tickets(self, ctx):
        canal_id = await self.db.get_config(ctx.guild.id, "ticket_list_channel")
        if canal_id:
            return ctx.guild.get_channel(int(canal_id))
        return None

    async def _postar_ticket_log(self, ctx, ticket_id, membro, tipo, comentario, duracao):
        canal = await self._checar_canal_tickets(ctx)
        if not canal:
            return
        embed = discord.Embed(
            title=f"Ticket #{ticket_id} — {tipo.upper()}",
            color=0xc0392b,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Usuario", value=f"{membro} (`{membro.id}`)", inline=True)
        embed.add_field(name="Moderador", value=f"{ctx.author} (`{ctx.author.id}`)", inline=True)
        embed.add_field(name="Duracao", value=formatar_delta(duracao), inline=True)
        if comentario:
            embed.add_field(name="Comentario", value=comentario, inline=False)
        await canal.send(embed=embed)

    # --- Comandos ---

    @commands.command(name="nota")
    @commands.has_permissions(manage_messages=True)
    async def nota(self, ctx, membro: discord.Member, *, comentario: str = None):
        """Adiciona uma nota a um usuario (sem acao punitiva)."""
        ticket_id = await self._criar_ticket(
            ctx.guild.id, membro.id, ctx.author.id, "nota", comentario
        )
        await ctx.send(f"Nota #{ticket_id} registrada para {membro.mention}.")
        await self._postar_ticket_log(ctx, ticket_id, membro, "nota", comentario, None)

    @commands.group(name="ticket", aliases=["tickets"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def ticket(self, ctx):
        """Gerencia tickets de infracoes. Use subcomandos: show, hide, set, take, queue."""
        await ctx.send(f"Subcomandos: `show`, `hide`, `set`, `append`, `take`, `assign`, `queue`, `approve`. Use `{self.bot.command_prefix}ajuda ticket`.")

    @ticket.command(name="show")
    @commands.has_permissions(manage_messages=True)
    async def ticket_show(self, ctx, alvo: str):
        """Mostra tickets de um usuario ou um ticket especifico por ID."""
        # Tentar como ID de ticket
        if alvo.isdigit():
            row = await self.db.fetchone(
                "SELECT * FROM tickets WHERE id = ? AND guild_id = ? AND oculto = 0",
                (int(alvo), ctx.guild.id)
            )
            if not row:
                await ctx.send("Ticket nao encontrado.")
                return
            await self._enviar_embed_ticket(ctx, row)
            return

        # Tentar como mencao/ID de usuario
        try:
            membro_id = int(alvo.strip("<@!>"))
        except ValueError:
            await ctx.send("Informe um ID de ticket ou mencione um usuario.")
            return

        rows = await self.db.fetchall(
            "SELECT * FROM tickets WHERE guild_id = ? AND user_id = ? AND oculto = 0 ORDER BY id DESC LIMIT 10",
            (ctx.guild.id, membro_id)
        )
        if not rows:
            await ctx.send("Nenhum ticket encontrado para este usuario.")
            return
        for row in rows:
            await self._enviar_embed_ticket(ctx, row)

    async def _enviar_embed_ticket(self, ctx, row):
        membro = ctx.guild.get_member(row["user_id"]) or f"ID {row['user_id']}"
        mod = ctx.guild.get_member(row["moderador_id"]) or f"ID {row['moderador_id']}"
        cor = 0xc0392b if row["tipo"] not in ("nota",) else 0x3498db
        embed = discord.Embed(
            title=f"Ticket #{row['id']} — {row['tipo'].upper()}",
            color=cor
        )
        embed.add_field(name="Usuario", value=str(membro), inline=True)
        embed.add_field(name="Moderador", value=str(mod), inline=True)
        embed.add_field(name="Duracao", value=row["duracao"] or "Permanente", inline=True)
        embed.add_field(name="Comentario", value=row["comentario"] or "Sem comentario", inline=False)
        embed.set_footer(text=f"Criado em {row['criado_em'][:10]}")
        await ctx.send(embed=embed)

    @ticket.command(name="hide")
    @commands.has_permissions(manage_messages=True)
    async def ticket_hide(self, ctx, ticket_id: int):
        """Oculta um ticket da listagem."""
        r = await self.db.fetchone("SELECT id FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        await self.db.execute("UPDATE tickets SET oculto = 1 WHERE id = ?", (ticket_id,))
        await ctx.send(f"Ticket #{ticket_id} ocultado.")

    @ticket.command(name="set")
    @commands.has_permissions(manage_messages=True)
    async def ticket_set(self, ctx, ticket_id: int, duracao: str, *, comentario: str = None):
        """Define duracao e comentario de um ticket."""
        r = await self.db.fetchone("SELECT id FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        delta = parsear_duracao(duracao)
        expira = (datetime.utcnow() + delta).isoformat() if delta else None
        await self.db.execute(
            "UPDATE tickets SET duracao = ?, expira_em = ?, comentario = ? WHERE id = ?",
            (formatar_delta(delta), expira, comentario, ticket_id)
        )
        await ctx.send(f"Ticket #{ticket_id} atualizado.")

    @ticket.command(name="append")
    @commands.has_permissions(manage_messages=True)
    async def ticket_append(self, ctx, ticket_id: int, *, adicional: str):
        """Adiciona texto ao comentario de um ticket."""
        r = await self.db.fetchone("SELECT comentario FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        novo = (r["comentario"] or "") + "\n" + adicional
        await self.db.execute("UPDATE tickets SET comentario = ? WHERE id = ?", (novo, ticket_id))
        await ctx.send(f"Comentario do ticket #{ticket_id} atualizado.")

    @ticket.command(name="take")
    @commands.has_permissions(manage_messages=True)
    async def ticket_take(self, ctx, ticket_id: int):
        """Atribui um ticket a voce mesmo."""
        r = await self.db.fetchone("SELECT id FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        await self.db.execute("UPDATE tickets SET moderador_id = ? WHERE id = ?", (ctx.author.id, ticket_id))
        await ctx.send(f"Ticket #{ticket_id} atribuido a voce.")

    @ticket.command(name="assign")
    @commands.has_permissions(manage_messages=True)
    async def ticket_assign(self, ctx, ticket_id: int, moderador: discord.Member):
        """Atribui um ticket a outro moderador."""
        r = await self.db.fetchone("SELECT id FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        await self.db.execute("UPDATE tickets SET moderador_id = ? WHERE id = ?", (moderador.id, ticket_id))
        await ctx.send(f"Ticket #{ticket_id} atribuido a {moderador.mention}.")

    @ticket.command(name="queue")
    @commands.has_permissions(manage_messages=True)
    async def ticket_queue(self, ctx, moderador: discord.Member = None):
        """Exibe tickets de um moderador (ou seu proprio)."""
        mod = moderador or ctx.author
        rows = await self.db.fetchall(
            "SELECT * FROM tickets WHERE guild_id = ? AND moderador_id = ? AND oculto = 0 ORDER BY id DESC LIMIT 10",
            (ctx.guild.id, mod.id)
        )
        if not rows:
            await ctx.send(f"Nenhum ticket para {mod.display_name}.")
            return
        linhas = [f"**#{r['id']}** — {r['tipo'].upper()} — `{r['criado_em'][:10]}`" for r in rows]
        embed = discord.Embed(
            title=f"Tickets de {mod.display_name}",
            description="\n".join(linhas),
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @ticket.command(name="approve")
    @commands.has_permissions(manage_messages=True)
    async def ticket_approve(self, ctx, ticket_id: int):
        """Aprova um ticket pendente."""
        r = await self.db.fetchone("SELECT id FROM tickets WHERE id = ? AND guild_id = ?", (ticket_id, ctx.guild.id))
        if not r:
            await ctx.send("Ticket nao encontrado.")
            return
        await self.db.execute("UPDATE tickets SET aprovado = 1 WHERE id = ?", (ticket_id,))
        await ctx.send(f"Ticket #{ticket_id} aprovado.")

    # --- Configuracao ---

    @commands.command(name="ticketconfig")
    @commands.has_permissions(administrator=True)
    async def ticketconfig(self, ctx, canal: discord.TextChannel):
        """Define o canal onde os tickets sao registrados."""
        await self.db.set_config(ctx.guild.id, "ticket_list_channel", str(canal.id))
        await ctx.send(f"Canal de tickets definido para {canal.mention}.")


async def setup(bot):
    await bot.add_cog(Tickets(bot))
