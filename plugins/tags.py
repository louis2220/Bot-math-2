import discord
from discord.ext import commands
import logging

log = logging.getLogger("matbot.tags")


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    async def _buscar_tag(self, guild_id: int, nome: str):
        """Busca uma tag pelo nome ou alias."""
        nome = nome.lower().strip()
        # Tenta nome direto
        row = await self.db.fetchone(
            "SELECT * FROM tags WHERE guild_id = ? AND nome = ?", (guild_id, nome)
        )
        if row:
            return row
        # Tenta alias
        alias = await self.db.fetchone(
            "SELECT tag_id FROM tag_aliases WHERE guild_id = ? AND alias = ?", (guild_id, nome)
        )
        if alias:
            row = await self.db.fetchone("SELECT * FROM tags WHERE id = ?", (alias["tag_id"],))
            return row
        return None

    async def tentar_tag(self, ctx):
        """Chamado pelo on_command_error para tentar executar uma tag."""
        if not ctx.guild:
            return
        nome = ctx.invoked_with
        if not nome:
            return
        tag = await self._buscar_tag(ctx.guild.id, nome)
        if tag:
            await self.db.execute("UPDATE tags SET usos = usos + 1 WHERE id = ?", (tag["id"],))
            await ctx.send(tag["conteudo"])

    @commands.group(name="tag", invoke_without_command=True)
    async def tag(self, ctx, *, nome: str = None):
        """Exibe uma tag pelo nome. Use subcomandos para gerenciar."""
        if nome:
            tag = await self._buscar_tag(ctx.guild.id, nome)
            if not tag:
                await ctx.send(f"Tag `{nome}` nao encontrada.")
                return
            await self.db.execute("UPDATE tags SET usos = usos + 1 WHERE id = ?", (tag["id"],))
            await ctx.send(tag["conteudo"])
        else:
            await ctx.send(
                f"Subcomandos: `add`, `edit`, `delete`, `alias`, `unalias`, `info`, `top`, `lista`."
            )

    @tag.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def tag_add(self, ctx, *, nome: str):
        """Adiciona uma nova tag. Voce sera solicitado a enviar o conteudo."""
        nome = nome.lower().strip()
        existente = await self._buscar_tag(ctx.guild.id, nome)
        if existente:
            await ctx.send(f"Ja existe uma tag com o nome `{nome}`.")
            return
        await ctx.send(f"Envie o conteudo da tag `{nome}` (voce tem 60 segundos):")

        def checar(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            resposta = await self.bot.wait_for("message", check=checar, timeout=60)
        except Exception:
            await ctx.send("Tempo esgotado. Tag nao criada.")
            return

        conteudo = resposta.content
        await self.db.execute(
            "INSERT INTO tags (guild_id, nome, conteudo, criado_por, criado_em) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, nome, conteudo, ctx.author.id, self.db.agora())
        )
        await ctx.send(f"Tag `{nome}` criada.")

    @tag.command(name="edit")
    @commands.has_permissions(manage_messages=True)
    async def tag_edit(self, ctx, *, nome: str):
        """Edita o conteudo de uma tag existente."""
        nome = nome.lower().strip()
        tag = await self._buscar_tag(ctx.guild.id, nome)
        if not tag:
            await ctx.send(f"Tag `{nome}` nao encontrada.")
            return
        await ctx.send(f"Envie o novo conteudo da tag `{nome}` (60 segundos):")

        def checar(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            resposta = await self.bot.wait_for("message", check=checar, timeout=60)
        except Exception:
            await ctx.send("Tempo esgotado.")
            return

        await self.db.execute(
            "UPDATE tags SET conteudo = ? WHERE id = ?", (resposta.content, tag["id"])
        )
        await ctx.send(f"Tag `{nome}` atualizada.")

    @tag.command(name="delete")
    @commands.has_permissions(manage_messages=True)
    async def tag_delete(self, ctx, *, nome: str):
        """Deleta uma tag e todos os seus aliases."""
        nome = nome.lower().strip()
        tag = await self._buscar_tag(ctx.guild.id, nome)
        if not tag:
            await ctx.send(f"Tag `{nome}` nao encontrada.")
            return
        await self.db.execute("DELETE FROM tags WHERE id = ?", (tag["id"],))
        await ctx.send(f"Tag `{nome}` deletada.")

    @tag.command(name="alias")
    @commands.has_permissions(manage_messages=True)
    async def tag_alias(self, ctx, nome: str, *, novo_alias: str):
        """Adiciona um alias a uma tag existente."""
        nome = nome.lower().strip()
        novo_alias = novo_alias.lower().strip()
        tag = await self._buscar_tag(ctx.guild.id, nome)
        if not tag:
            await ctx.send(f"Tag `{nome}` nao encontrada.")
            return
        existente = await self._buscar_tag(ctx.guild.id, novo_alias)
        if existente:
            await ctx.send(f"Ja existe uma tag ou alias com o nome `{novo_alias}`.")
            return
        await self.db.execute(
            "INSERT INTO tag_aliases (guild_id, alias, tag_id) VALUES (?, ?, ?)",
            (ctx.guild.id, novo_alias, tag["id"])
        )
        await ctx.send(f"Alias `{novo_alias}` adicionado a tag `{tag['nome']}`.")

    @tag.command(name="unalias")
    @commands.has_permissions(manage_messages=True)
    async def tag_unalias(self, ctx, *, alias: str):
        """Remove um alias de uma tag."""
        alias = alias.lower().strip()
        r = await self.db.fetchone(
            "SELECT * FROM tag_aliases WHERE guild_id = ? AND alias = ?", (ctx.guild.id, alias)
        )
        if not r:
            await ctx.send(f"Alias `{alias}` nao encontrado.")
            return
        await self.db.execute(
            "DELETE FROM tag_aliases WHERE guild_id = ? AND alias = ?", (ctx.guild.id, alias)
        )
        await ctx.send(f"Alias `{alias}` removido.")

    @tag.command(name="info")
    async def tag_info(self, ctx, *, nome: str):
        """Exibe informacoes sobre uma tag."""
        nome = nome.lower().strip()
        tag = await self._buscar_tag(ctx.guild.id, nome)
        if not tag:
            await ctx.send(f"Tag `{nome}` nao encontrada.")
            return
        aliases = await self.db.fetchall(
            "SELECT alias FROM tag_aliases WHERE tag_id = ?", (tag["id"],)
        )
        criador = ctx.guild.get_member(tag["criado_por"]) or f"ID {tag['criado_por']}"
        embed = discord.Embed(title=f"Tag: {tag['nome']}", color=0x2b2d31)
        embed.add_field(name="Criado por", value=str(criador), inline=True)
        embed.add_field(name="Usos", value=str(tag["usos"]), inline=True)
        embed.add_field(name="Criado em", value=tag["criado_em"][:10], inline=True)
        if aliases:
            embed.add_field(
                name="Aliases",
                value=", ".join(f"`{a['alias']}`" for a in aliases),
                inline=False
            )
        embed.add_field(name="Conteudo", value=tag["conteudo"][:500], inline=False)
        await ctx.send(embed=embed)

    @tag.command(name="top")
    async def tag_top(self, ctx):
        """Exibe as 10 tags mais usadas."""
        rows = await self.db.fetchall(
            "SELECT nome, usos FROM tags WHERE guild_id = ? ORDER BY usos DESC LIMIT 10",
            (ctx.guild.id,)
        )
        if not rows:
            await ctx.send("Nenhuma tag cadastrada.")
            return
        linhas = [f"**{i+1}.** `{r['nome']}` — {r['usos']} uso(s)" for i, r in enumerate(rows)]
        embed = discord.Embed(
            title="Tags mais usadas",
            description="\n".join(linhas),
            color=0x2b2d31
        )
        await ctx.send(embed=embed)

    @tag.command(name="lista")
    async def tag_lista(self, ctx):
        """Lista todas as tags do servidor."""
        rows = await self.db.fetchall(
            "SELECT nome FROM tags WHERE guild_id = ? ORDER BY nome ASC", (ctx.guild.id,)
        )
        if not rows:
            await ctx.send("Nenhuma tag cadastrada.")
            return
        nomes = ", ".join(f"`{r['nome']}`" for r in rows)
        embed = discord.Embed(title="Tags disponíveis", description=nomes, color=0x2b2d31)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Tags(bot))
