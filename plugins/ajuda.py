import discord
from discord.ext import commands

class Ajuda(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ajuda", aliases=["help"])
    async def ajuda(self, ctx, *, comando: str = None):
        """Exibe a lista de comandos ou informacoes sobre um comando especifico."""
        prefixo = self.bot.command_prefix

        if comando:
            cmd = self.bot.get_command(comando)
            if not cmd:
                await ctx.send(f"Comando `{comando}` nao encontrado.")
                return
            embed = discord.Embed(
                title=f"Comando: {prefixo}{cmd.name}",
                description=cmd.help or "Sem descricao.",
                color=0x2b2d31
            )
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(f"`{a}`" for a in cmd.aliases))
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="Comandos do MatBot",
            description=f"Use `{prefixo}ajuda <comando>` para mais detalhes.",
            color=0x2b2d31
        )

        categorias = {
            "Moderacao": [
                ("nota", "Adiciona uma nota a um usuario"),
                ("ticket", "Gerencia tickets de infracoes"),
                ("honrado", "Notifica um usuario sobre cargo de honrado"),
            ],
            "Automod": [
                ("automod lista", "Lista os padroes de automod"),
                ("automod add", "Adiciona um padrao de automod"),
                ("automod remove", "Remove um padrao de automod"),
            ],
            "Canais de Ajuda": [
                ("fechar", "Fecha um canal de ajuda"),
                ("reabrir", "Reabre um canal de ajuda"),
                ("clopen_sync", "Sincroniza o estado dos canais"),
            ],
            "Lembretes": [
                ("lembrete", "Cria um lembrete"),
                ("lembretes", "Lista seus lembretes ativos"),
            ],
            "Tags": [
                ("tag add", "Adiciona uma tag"),
                ("tag edit", "Edita uma tag"),
                ("tag delete", "Deleta uma tag"),
                ("tag info", "Informacoes sobre uma tag"),
                ("tag top", "Tags mais usadas"),
            ],
            "Cargos por Reacao": [
                ("rolereact new", "Cria role-react em uma mensagem"),
                ("rolereact add", "Adiciona emoji/cargo a uma mensagem"),
                ("rolereact remove", "Remove um role-react"),
                ("rolereact list", "Lista mensagens com role-react"),
            ],
            "Logs": [
                ("logconfig temp", "Define canal de logs temporarios"),
                ("logconfig perm", "Define canal de logs permanentes"),
            ],
        }

        for categoria, cmds in categorias.items():
            valor = "\n".join(f"`{prefixo}{nome}` — {desc}" for nome, desc in cmds)
            embed.add_field(name=categoria, value=valor, inline=False)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Ajuda(bot))
