import discord
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import re
import logging

log = logging.getLogger("matbot.lembretes")

DURACAO_RE = re.compile(
    r"(\d+)\s*(s|seg|segundo(?:s)?|m|min|minuto(?:s)?|h|hr|hora(?:s)?|d|dia(?:s)?|w|sem|semana(?:s)?)",
    re.IGNORECASE
)

def parsear_intervalo(texto: str) -> timedelta:
    """Converte '10m 30s' -> timedelta."""
    total = 0
    for qtd, unidade in DURACAO_RE.findall(texto):
        qtd = int(qtd)
        u = unidade.lower()
        if u.startswith("s"):
            total += qtd
        elif u.startswith("m"):
            total += qtd * 60
        elif u.startswith("h"):
            total += qtd * 3600
        elif u.startswith("d"):
            total += qtd * 86400
        elif u.startswith("w") or u.startswith("sem"):
            total += qtd * 604800
    return timedelta(seconds=total)

def formatar_tempo(dt: datetime) -> str:
    delta = dt - datetime.utcnow()
    total = int(delta.total_seconds())
    if total <= 0:
        return "agora"
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
    return " ".join(partes)


class Lembretes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task: asyncio.Task = None

    @property
    def db(self):
        return self.bot.db

    async def cog_load(self):
        self._task = self.bot.loop.create_task(self._loop())

    async def cog_unload(self):
        if self._task:
            self._task.cancel()

    async def _loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._disparar_lembretes()
            except Exception as e:
                log.error(f"Erro no loop de lembretes: {e}")
            await asyncio.sleep(30)

    async def _disparar_lembretes(self):
        agora = datetime.utcnow().isoformat()
        rows = await self.db.fetchall(
            "SELECT * FROM lembretes WHERE expira_em <= ?", (agora,)
        )
        for row in rows:
            try:
                canal = self.bot.get_channel(row["channel_id"])
                if canal:
                    user = self.bot.get_user(row["user_id"])
                    mencao = user.mention if user else f"<@{row['user_id']}>"
                    await canal.send(f"{mencao}, lembrete: {row['mensagem']}")
            except Exception as e:
                log.error(f"Erro ao disparar lembrete {row['id']}: {e}")
            await self.db.execute("DELETE FROM lembretes WHERE id = ?", (row["id"],))

    @commands.command(name="lembrete", aliases=["remindme", "remind"])
    async def lembrete(self, ctx, intervalo: str, *, mensagem: str):
        """Cria um lembrete. Ex: .lembrete 10m Verificar exercicios"""
        delta = parsear_intervalo(intervalo)
        if delta.total_seconds() <= 0:
            await ctx.send(
                "Intervalo invalido. Exemplos: `10m`, `2h`, `1d`, `30s`, `1h 30m`."
            )
            return
        if delta.total_seconds() > 60 * 60 * 24 * 365:
            await ctx.send("Intervalo maximo e de 1 ano.")
            return

        expira = datetime.utcnow() + delta
        await self.db.execute(
            """INSERT INTO lembretes (user_id, guild_id, channel_id, mensagem, expira_em, criado_em)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ctx.author.id,
             ctx.guild.id if ctx.guild else None,
             ctx.channel.id,
             mensagem,
             expira.isoformat(),
             self.db.agora())
        )
        await ctx.send(
            f"Lembrete definido para daqui a {formatar_tempo(expira)}."
        )

    @commands.command(name="lembretes", aliases=["reminders"])
    async def lembretes(self, ctx):
        """Lista seus lembretes ativos."""
        rows = await self.db.fetchall(
            "SELECT * FROM lembretes WHERE user_id = ? ORDER BY expira_em ASC",
            (ctx.author.id,)
        )
        if not rows:
            await ctx.send("Voce nao tem lembretes ativos.")
            return
        linhas = []
        for r in rows:
            expira = datetime.fromisoformat(r["expira_em"])
            linhas.append(f"**#{r['id']}** — em {formatar_tempo(expira)} — {r['mensagem'][:60]}")
        embed = discord.Embed(
            title=f"Lembretes de {ctx.author.display_name}",
            description="\n".join(linhas),
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @commands.command(name="lembrete_remove", aliases=["reminder_remove"])
    async def lembrete_remove(self, ctx, id_lembrete: int):
        """Remove um lembrete pelo ID."""
        r = await self.db.fetchone(
            "SELECT id FROM lembretes WHERE id = ? AND user_id = ?",
            (id_lembrete, ctx.author.id)
        )
        if not r:
            await ctx.send("Lembrete nao encontrado ou nao e seu.")
            return
        await self.db.execute("DELETE FROM lembretes WHERE id = ?", (id_lembrete,))
        await ctx.send(f"Lembrete #{id_lembrete} removido.")


async def setup(bot):
    await bot.add_cog(Lembretes(bot))
