"""
plugins/cores.py
Sistema de Nick Color — cores normais e degradê.
Adaptado para o MatBot (usa self.bot.db via Database).
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging

log = logging.getLogger("matbot.cores")

BOT_COLOR = 0x9B59B6

# ── Helpers de embed ──────────────────────────────────────────────────────────

def embed_success(title: str, desc: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=desc, color=0x2ECC71)

def embed_error(title: str, desc: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=desc, color=0xE74C3C)

def embed_info(title: str, desc: str = "") -> discord.Embed:
    return discord.Embed(title=f"ℹ️ {title}", description=desc, color=BOT_COLOR)

# ── Cores disponíveis ─────────────────────────────────────────────────────────

CORES_NORMAIS = [
    ("vermelho", "Vermelho", "<:1000010231:1482084219814416464>", 0xE74C3C),
    ("laranja",  "Laranja",  "<:1000010232:1482092477946134579>", 0xE67E22),
    ("amarelo",  "Amarelo",  "<:1000010233:1482092507755188244>", 0xF1C40F),
    ("verde",    "Verde",    "<:1000010234:1482092539195424768>", 0x2ECC71),
    ("azul",     "Azul",     "<:1000010235:1482092570023825591>", 0x3498DB),
    ("rosa",     "Rosa",     "<:1000010236:1482092600172351589>", 0xFF69B4),
    ("marrom",   "Marrom",   "<:1000010263:1482103964215279706>", 0x8B4513),
    ("branco",   "Branco",   "<:1000010273:1482103994913525892>", 0xFFFFFF),
]

CORES_DEGRADE = [
    ("grad_1", "Degradê 1", "<:1000010250:1482092724428603412>", "Degradê"),
    ("grad_2", "Degradê 2", "<:1000010264:1482104044699779173>", "Degradê"),
    ("grad_3", "Degradê 3", "<:1000010265:1482104072898347028>", "Degradê"),
    ("grad_4", "Degradê 4", "<:1000010266:1482104100320710778>", "Degradê"),
    ("grad_5", "Degradê 5", "<:1000010267:1482104126753079498>", "Degradê"),
    ("grad_6", "Degradê 6", "<:1000010268:1482104151751004421>", "Degradê"),
    ("grad_7", "Degradê 7", "<:1000010269:1482104177302966342>", "Degradê"),
    ("grad_8", "Degradê 8", "<:1000010270:1482104213315260466>", "Degradê"),
]

BTN_PAD = "\u2000" * 10


# ═══════════════════════════════════════════════════════════════
# MODAL EDITOR DE EMBED
# ═══════════════════════════════════════════════════════════════

class EmbedEditorModal(discord.ui.Modal):
    titulo    = discord.ui.TextInput(label="Título", max_length=256)
    descricao = discord.ui.TextInput(label="Descrição / Mensagem",
                                     style=discord.TextStyle.paragraph, max_length=2000)
    cor       = discord.ui.TextInput(label="Cor hex (ex: #9B59B6)", max_length=9, required=False)
    thumbnail = discord.ui.TextInput(label="URL da miniatura",
                                     placeholder="https://i.imgur.com/exemplo.png — deixe vazio para não usar",
                                     required=False, max_length=500)
    banner    = discord.ui.TextInput(label="URL do banner",
                                     placeholder="https://i.imgur.com/exemplo.png — deixe vazio para não usar",
                                     required=False, max_length=500)

    def __init__(self, canal: discord.TextChannel, view_cls,
                 title: str = "Personalizar Painel",
                 default_title: str = "", default_desc: str = "",
                 default_color: str = "#9B59B6"):
        super().__init__(title=title)
        self.canal     = canal
        self.view_cls  = view_cls
        self.titulo.default    = default_title
        self.descricao.default = default_desc
        self.cor.default       = default_color

    async def on_submit(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        try:
            cor_str = (self.cor.value or "").strip().lstrip("#")
            color   = int(cor_str, 16) if cor_str else BOT_COLOR
        except ValueError:
            color = BOT_COLOR

        emb = discord.Embed(
            title=self.titulo.value or "\u200b",
            description=self.descricao.value or "\u200b",
            color=color,
        )
        thumb = (self.thumbnail.value or "").strip()
        if thumb:
            emb.set_thumbnail(url=thumb)
        img = (self.banner.value or "").strip()
        if img:
            emb.set_image(url=img)
        emb.set_footer(text="Nick Color — apenas uma cor por vez")

        await self.canal.send(embed=emb, view=self.view_cls())
        await inter.followup.send(
            embed=embed_success("Painel enviado!", f"Painel enviado em {self.canal.mention}."),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════════════
# VIEW DE CONFIRMAÇÃO
# ═══════════════════════════════════════════════════════════════

class PainelConfirmView(discord.ui.View):
    def __init__(self, canal, view_cls, default_title, default_desc, default_color):
        super().__init__(timeout=120)
        self.canal         = canal
        self.view_cls      = view_cls
        self.default_title = default_title
        self.default_desc  = default_desc
        self.default_color = default_color

    @discord.ui.button(label="Enviar padrão", style=discord.ButtonStyle.success, emoji="✅")
    async def enviar_padrao(self, inter: discord.Interaction, button: discord.ui.Button):
        emb = discord.Embed(
            title=self.default_title,
            description=self.default_desc,
            color=self.default_color,
        )
        emb.set_footer(text="Nick Color — apenas uma cor por vez")
        await self.canal.send(embed=emb, view=self.view_cls())
        await inter.response.edit_message(
            embed=embed_success("Painel enviado!", f"Painel enviado em {self.canal.mention}."),
            view=None,
        )

    @discord.ui.button(label="Personalizar embed", style=discord.ButtonStyle.primary, emoji="🎨")
    async def personalizar(self, inter: discord.Interaction, button: discord.ui.Button):
        modal = EmbedEditorModal(
            canal=self.canal,
            view_cls=self.view_cls,
            title="Personalizar Painel",
            default_title=self.default_title,
            default_desc=self.default_desc,
            default_color=f"#{self.default_color:06X}",
        )
        await inter.response.send_modal(modal)


# ═══════════════════════════════════════════════════════════════
# BOTÕES DE COR
# ═══════════════════════════════════════════════════════════════

class ColorButton(discord.ui.Button):
    def __init__(self, key, label, emoji_str, color_hex, row):
        super().__init__(
            label=BTN_PAD,
            emoji=discord.PartialEmoji.from_str(emoji_str),
            style=discord.ButtonStyle.secondary,
            custom_id=f"cores:normal:{key}",
            row=row,
        )
        self.key = key

    async def callback(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Cores")
        if cog:
            await cog.toggle_color_role(inter, self.key, degrade=False)


class ColorDegradeButton(discord.ui.Button):
    def __init__(self, key, label, emoji_str, row):
        super().__init__(
            label=BTN_PAD,
            emoji=discord.PartialEmoji.from_str(emoji_str),
            style=discord.ButtonStyle.secondary,
            custom_id=f"cores:degrade:{key}",
            row=row,
        )
        self.key = key

    async def callback(self, inter: discord.Interaction):
        cog = inter.client.cogs.get("Cores")
        if cog:
            await cog.toggle_color_role(inter, self.key, degrade=True)


class ColorNormalView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, hex_c) in enumerate(CORES_NORMAIS):
            self.add_item(ColorButton(key, label, emoji_str, hex_c, row=i // 3))


class ColorDegradeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i, (key, label, emoji_str, _) in enumerate(CORES_DEGRADE):
            self.add_item(ColorDegradeButton(key, label, emoji_str, row=i // 3))


# ═══════════════════════════════════════════════════════════════
# COG PRINCIPAL
# ═══════════════════════════════════════════════════════════════

class Cores(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.add_view(ColorNormalView())
        bot.add_view(ColorDegradeView())

    @property
    def db(self):
        return self.bot.db

    # ── Helpers de DB ─────────────────────────────────────────

    async def _ensure_table(self):
        await self.db.pool.execute("""
            CREATE TABLE IF NOT EXISTS cores_config (
                guild_id BIGINT NOT NULL,
                key      TEXT   NOT NULL,
                value    TEXT   NOT NULL,
                PRIMARY KEY (guild_id, key)
            )
        """)

    async def _cfg(self, guild_id: int, key: str) -> str | None:
        row = await self.db.pool.fetchrow(
            "SELECT value FROM cores_config WHERE guild_id = $1 AND key = $2",
            guild_id, key
        )
        return row["value"] if row else None

    async def _set(self, guild_id: int, key: str, value: str):
        await self.db.pool.execute("""
            INSERT INTO cores_config (guild_id, key, value)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, key) DO UPDATE SET value = $3
        """, guild_id, key, value)

    async def _role_id(self, guild_id: int, key: str) -> int | None:
        val = await self._cfg(guild_id, f"role_{key}")
        return int(val) if val else None

    async def _all_color_role_ids(self, guild_id: int) -> set[int]:
        ids = set()
        for key, *_ in CORES_NORMAIS + CORES_DEGRADE:
            rid = await self._role_id(guild_id, key)
            if rid:
                ids.add(rid)
        return ids

    async def toggle_color_role(self, inter: discord.Interaction, key: str, degrade: bool):
        await inter.response.defer(ephemeral=True)
        member = inter.guild.get_member(inter.user.id)

        if degrade:
            vip_ch_id = await self._cfg(inter.guild.id, "vip_channel")
            if vip_ch_id:
                vip_ch = inter.guild.get_channel(int(vip_ch_id))
                if vip_ch and not vip_ch.permissions_for(member).read_messages:
                    await inter.followup.send(
                        embed=embed_error("Acesso negado", "Esta cor é exclusiva para membros VIP."),
                        ephemeral=True,
                    )
                    return

        role_id = await self._role_id(inter.guild.id, key)
        if not role_id:
            await inter.followup.send(
                embed=embed_error("Cor não configurada", "Esta cor ainda não foi configurada pelo admin."),
                ephemeral=True,
            )
            return

        role = inter.guild.get_role(role_id)
        if not role:
            await inter.followup.send(
                embed=embed_error("Cargo não encontrado", "O cargo desta cor foi deletado. Avise um admin."),
                ephemeral=True,
            )
            return

        all_ids = await self._all_color_role_ids(inter.guild.id)
        roles_to_remove = [r for r in member.roles if r.id in all_ids and r.id != role.id]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason="Nick Color: troca de cor")

        label = next((l for k, l, *_ in (CORES_DEGRADE if degrade else CORES_NORMAIS) if k == key), key)
        if role in member.roles:
            await member.remove_roles(role, reason="Nick Color: removida pelo usuário")
            await inter.followup.send(
                embed=embed_info("Cor removida", f"A cor **{label}** foi removida do seu nick."),
                ephemeral=True,
            )
        else:
            await member.add_roles(role, reason="Nick Color: adicionada pelo usuário")
            await inter.followup.send(
                embed=embed_success("Cor aplicada!", f"A cor **{label}** foi aplicada ao seu nick."),
                ephemeral=True,
            )

    # ── Grupo de comandos ─────────────────────────────────────

    cores_group = app_commands.Group(name="cores", description="Sistema de Nick Color")

    @cores_group.command(name="setup_normal", description="Vincula um cargo a uma cor normal")
    @app_commands.describe(cor="Cor normal a configurar", cargo="Cargo do Discord")
    @app_commands.choices(cor=[
        app_commands.Choice(name="Vermelho", value="vermelho"),
        app_commands.Choice(name="Laranja",  value="laranja"),
        app_commands.Choice(name="Amarelo",  value="amarelo"),
        app_commands.Choice(name="Verde",    value="verde"),
        app_commands.Choice(name="Azul",     value="azul"),
        app_commands.Choice(name="Rosa",     value="rosa"),
        app_commands.Choice(name="Marrom",   value="marrom"),
        app_commands.Choice(name="Branco",   value="branco"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def cores_setup_normal(self, inter: discord.Interaction, cor: str, cargo: discord.Role):
        await self._set(inter.guild.id, f"role_{cor}", str(cargo.id))
        label = next((l for k, l, *_ in CORES_NORMAIS if k == cor), cor)
        emoji = next((e for k, l, e, *_ in CORES_NORMAIS if k == cor), "🎨")
        await inter.response.send_message(
            embed=embed_success("Cor normal configurada!", f"{emoji} **{label}** → {cargo.mention}"),
            ephemeral=True,
        )

    @cores_group.command(name="setup_degrade", description="Vincula um cargo a uma cor degradê")
    @app_commands.describe(cor="Cor degradê a configurar", cargo="Cargo com gradiente")
    @app_commands.choices(cor=[
        app_commands.Choice(name="Degradê 1", value="grad_1"),
        app_commands.Choice(name="Degradê 2", value="grad_2"),
        app_commands.Choice(name="Degradê 3", value="grad_3"),
        app_commands.Choice(name="Degradê 4", value="grad_4"),
        app_commands.Choice(name="Degradê 5", value="grad_5"),
        app_commands.Choice(name="Degradê 6", value="grad_6"),
        app_commands.Choice(name="Degradê 7", value="grad_7"),
        app_commands.Choice(name="Degradê 8", value="grad_8"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def cores_setup_degrade(self, inter: discord.Interaction, cor: str, cargo: discord.Role):
        await self._set(inter.guild.id, f"role_{cor}", str(cargo.id))
        label = next((l for k, l, *_ in CORES_DEGRADE if k == cor), cor)
        emoji = next((e for k, l, e, *_ in CORES_DEGRADE if k == cor), "✨")
        await inter.response.send_message(
            embed=embed_success("Cor degradê configurada!",
                f"{emoji} **{label}** → {cargo.mention}\n\n"
                f"💡 Configure o gradiente em **Cargos → {cargo.name} → Cor → Gradiente**"),
            ephemeral=True,
        )

    @cores_group.command(name="setup_vip", description="Define o canal VIP para acesso às cores degradê")
    @app_commands.describe(canal="Canal privado de boosters/VIPs")
    @app_commands.default_permissions(administrator=True)
    async def cores_setup_vip(self, inter: discord.Interaction, canal: discord.TextChannel):
        await self._set(inter.guild.id, "vip_channel", str(canal.id))
        await inter.response.send_message(
            embed=embed_success("Canal VIP definido",
                f"⭐ Apenas membros com acesso a {canal.mention} poderão pegar cores degradê."),
            ephemeral=True,
        )

    @cores_group.command(name="painel", description="Envia o painel de cores normais")
    @app_commands.describe(canal="Canal onde enviar (padrão: canal atual)")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel
        linhas = []
        for key, label, emoji_str, hex_c in CORES_NORMAIS:
            rid  = await self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        default_title = "🎨 | Nick Color"
        default_desc  = (
            "⭐ Cansou da cor do seu apelido? Deixe seu perfil mais colorido!\n\n"
            + "\n".join(linhas)
            + "\n\n**Como usar:**\n"
              "1. Clique no pincel da cor desejada\n"
              "2. Seu apelido receberá a nova cor\n"
              "3. Clique novamente para remover"
        )
        confirm = discord.Embed(
            title="💡 Painel de Cores Normais",
            description=f"Canal: {ch.mention}\n\n➡️ **Enviar padrão** — envia a embed pronta\n📌 **Personalizar embed** — edite título, descrição, cor, miniatura e banner",
            color=BOT_COLOR,
        )
        view = PainelConfirmView(ch, ColorNormalView, default_title, default_desc, BOT_COLOR)
        await inter.response.send_message(embed=confirm, view=view, ephemeral=True)

    @cores_group.command(name="painel_vip", description="Envia o painel de cores degradê")
    @app_commands.describe(canal="Canal privado onde enviar")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_painel_vip(self, inter: discord.Interaction, canal: discord.TextChannel = None):
        ch = canal or inter.channel
        linhas = []
        for key, label, emoji_str, _ in CORES_DEGRADE:
            rid  = await self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            linhas.append(f"{emoji_str} **{label}** → {role.mention if role else '*não configurada*'}")

        default_title = "✨ | Nick Color — Degradê Exclusivo"
        default_desc  = (
            "🏆 Benefício exclusivo para membros especiais!\n\n"
            "🔵 **Cores com gradiente disponíveis:**\n"
            + "\n".join(linhas)
            + "\n\n💡 Configure o gradiente em **Cargos → [cargo] → Cor → Gradiente**.\n\n"
              "**Como usar:**\n"
              "1. Clique no pincel da cor desejada\n"
              "2. Seu nome receberá o gradiente\n"
              "3. Clique novamente para remover"
        )
        confirm = discord.Embed(
            title="🏆 Painel de Cores Degradê",
            description=f"Canal: {ch.mention}\n\n➡️ **Enviar padrão** — envia a embed pronta\n📌 **Personalizar embed** — edite título, descrição, cor, miniatura e banner",
            color=0x9B59B6,
        )
        view = PainelConfirmView(ch, ColorDegradeView, default_title, default_desc, 0x9B59B6)
        await inter.response.send_message(embed=confirm, view=view, ephemeral=True)

    @cores_group.command(name="lista", description="Lista todos os cargos de cor configurados")
    @app_commands.default_permissions(manage_guild=True)
    async def cores_lista(self, inter: discord.Interaction):
        emb = discord.Embed(title="💡 Nick Color — Configuração", color=BOT_COLOR)
        normais_txt = []
        for key, label, emoji_str, _ in CORES_NORMAIS:
            rid  = await self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            normais_txt.append(f"{emoji_str} {label}: {role.mention if role else '`não configurado`'}")
        emb.add_field(name="🎨 Cores Normais", value="\n".join(normais_txt), inline=False)

        degrade_txt = []
        for key, label, emoji_str, _ in CORES_DEGRADE:
            rid  = await self._role_id(inter.guild.id, key)
            role = inter.guild.get_role(rid) if rid else None
            degrade_txt.append(f"{emoji_str} {label}: {role.mention if role else '`não configurado`'}")
        emb.add_field(name="✨ Cores Degradê", value="\n".join(degrade_txt), inline=False)

        vip_ch_id = await self._cfg(inter.guild.id, "vip_channel")
        vip_ch    = inter.guild.get_channel(int(vip_ch_id)) if vip_ch_id else None
        emb.add_field(name="⭐ Canal VIP", value=vip_ch.mention if vip_ch else "`não configurado`", inline=False)
        emb.set_footer(text="/cores lista")
        await inter.response.send_message(embed=emb, ephemeral=True)

    @cores_group.command(name="remover", description="Remove todas as cores de nick de um membro")
    @app_commands.describe(membro="Membro alvo")
    @app_commands.default_permissions(manage_roles=True)
    async def cores_remover(self, inter: discord.Interaction, membro: discord.Member):
        await inter.response.defer(ephemeral=True)
        all_ids   = await self._all_color_role_ids(inter.guild.id)
        to_remove = [r for r in membro.roles if r.id in all_ids]
        if to_remove:
            await membro.remove_roles(*to_remove, reason=f"Nick Color: remoção por {inter.user}")
        await inter.followup.send(
            embed=embed_success("Cores removidas", f"Todas as cores de {membro.mention} foram removidas."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Cores(bot))
    # Cria a tabela ao carregar o cog
    cog = bot.cogs.get("Cores")
    if cog:
        await cog._ensure_table()
