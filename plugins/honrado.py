import discord
from discord.ext import commands
import logging

log = logging.getLogger("matbot.honrado")

MENSAGEM_PADRAO = (
    "Voce recebeu o cargo de Honrado no servidor {servidor}. "
    "Isso significa que a equipe reconhece sua contribuicao positiva para a comunidade. "
    "Parabens!"
)


class Honrado(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.command(name="honrado")
    @commands.has_permissions(manage_roles=True)
    async def honrado(self, ctx, membro: discord.Member, *, motivo: str = None):
        """Notifica um usuario por DM que recebeu o cargo de Honrado.

        Uso: .honrado @usuario [motivo opcional]

        O bot envia uma DM ao usuario informando sobre o cargo.
        Se um cargo de Honrado estiver configurado, ele e atribuido automaticamente.
        """
        cargo_id = await self.db.get_config(ctx.guild.id, "honrado_role")
        cargo = None
        if cargo_id:
            cargo = ctx.guild.get_role(int(cargo_id))

        # Atribui o cargo se configurado
        if cargo:
            if cargo in membro.roles:
                await ctx.send(f"{membro.mention} ja possui o cargo {cargo.mention}.")
                return
            try:
                await membro.add_roles(cargo, reason=f"Cargo Honrado concedido por {ctx.author}")
            except discord.Forbidden:
                await ctx.send("Nao tenho permissao para atribuir esse cargo.")
                return

        # Monta mensagem
        mensagem_base = await self.db.get_config(ctx.guild.id, "honrado_mensagem") or MENSAGEM_PADRAO
        mensagem_final = mensagem_base.replace("{servidor}", ctx.guild.name)

        if motivo:
            mensagem_final += f"\n\nMotivo: {motivo}"

        # Envia DM
        enviado = False
        try:
            embed = discord.Embed(
                title="Cargo de Honrado",
                description=mensagem_final,
                color=0xf1c40f
            )
            embed.set_footer(text=f"Servidor: {ctx.guild.name}")
            await membro.send(embed=embed)
            enviado = True
        except discord.Forbidden:
            pass

        # Confirmacao no canal
        partes = [f"{membro.mention} foi notificado sobre o cargo de Honrado."]
        if cargo:
            partes.append(f"Cargo {cargo.mention} atribuido.")
        if not enviado:
            partes.append("(Nao foi possivel enviar DM — o usuario pode ter DMs desativadas.)")

        await ctx.send(" ".join(partes))

        # Log permanente
        canal_perm_id = await self.db.get_config(ctx.guild.id, "log_perm_channel")
        if not canal_perm_id:
            row = await self.db.fetchone(
                "SELECT canal_perm FROM log_config WHERE guild_id = ?", (ctx.guild.id,)
            )
            if row and row["canal_perm"]:
                canal_perm_id = str(row["canal_perm"])

        if canal_perm_id:
            canal_log = ctx.guild.get_channel(int(canal_perm_id))
            if canal_log:
                embed_log = discord.Embed(
                    title="Cargo Honrado Concedido",
                    color=0xf1c40f
                )
                embed_log.add_field(name="Usuario", value=f"{membro} (`{membro.id}`)", inline=True)
                embed_log.add_field(name="Concedido por", value=f"{ctx.author}", inline=True)
                if motivo:
                    embed_log.add_field(name="Motivo", value=motivo, inline=False)
                embed_log.add_field(name="DM enviada", value="Sim" if enviado else "Nao", inline=True)
                await canal_log.send(embed=embed_log)

    @commands.command(name="honradoconfig")
    @commands.has_permissions(administrator=True)
    async def honradoconfig(self, ctx, *, subcomando: str = None):
        """Configura o sistema de cargo Honrado.

        Subcomandos:
          cargo @cargo         — Define o cargo a ser atribuido
          mensagem <texto>     — Define a mensagem de DM (use {servidor} como variavel)
          ver                  — Exibe a configuracao atual
        """
        if not subcomando:
            await ctx.send(
                f"Subcomandos: `{self.bot.command_prefix}honradoconfig cargo @cargo`, "
                f"`{self.bot.command_prefix}honradoconfig mensagem <texto>`, "
                f"`{self.bot.command_prefix}honradoconfig ver`."
            )
            return

        partes = subcomando.split(None, 1)
        acao = partes[0].lower()

        if acao == "cargo":
            if not ctx.message.role_mentions:
                await ctx.send("Mencione um cargo. Ex: `.honradoconfig cargo @Honrado`.")
                return
            cargo = ctx.message.role_mentions[0]
            await self.db.set_config(ctx.guild.id, "honrado_role", str(cargo.id))
            await ctx.send(f"Cargo de Honrado definido: {cargo.mention}.")

        elif acao == "mensagem":
            if len(partes) < 2 or not partes[1].strip():
                await ctx.send("Informe a mensagem. Voce pode usar `{servidor}` como variavel.")
                return
            mensagem = partes[1].strip()
            await self.db.set_config(ctx.guild.id, "honrado_mensagem", mensagem)
            await ctx.send("Mensagem de Honrado atualizada.")

        elif acao == "ver":
            cargo_id = await self.db.get_config(ctx.guild.id, "honrado_role")
            mensagem = await self.db.get_config(ctx.guild.id, "honrado_mensagem") or MENSAGEM_PADRAO
            cargo_str = "Nao definido"
            if cargo_id:
                c = ctx.guild.get_role(int(cargo_id))
                cargo_str = c.mention if c else f"ID {cargo_id}"
            embed = discord.Embed(title="Configuracao — Cargo Honrado", color=0xf1c40f)
            embed.add_field(name="Cargo", value=cargo_str, inline=False)
            embed.add_field(name="Mensagem DM", value=mensagem[:500], inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("Subcomando invalido. Use: `cargo`, `mensagem` ou `ver`.")


async def setup(bot):
    await bot.add_cog(Honrado(bot))
