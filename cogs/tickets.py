import os
import re
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0") or 0)
KLAN_BASVURU_ROLE_ID = int(os.getenv("KLAN_BASVURU_ROLE_ID", "0") or 0)
DIGER_TICKET_ROLE_ID = int(os.getenv("DIGER_TICKET_ROLE_ID", "0") or 0)
TRANSCRIPT_CATEGORY_ID = int(os.getenv("TRANSCRIPT_CATEGORY_ID", "0") or 0)

# Arşivlenmiş ticket'ı görebilecek yönetim rolleri
ARCHIVE_ROLE_IDS = [999997810546065468, 1410015083131572354, 1529625416724250734]

TICKET_TYPES = {
    "ticket_klan_basvuru": ("Klan Başvuru", "klan", KLAN_BASVURU_ROLE_ID),
    "ticket_merc": ("Merc Application", "merc", DIGER_TICKET_ROLE_ID),
    "ticket_temsilci": ("Clan Representative", "temsilci", DIGER_TICKET_ROLE_ID),
    "ticket_mac": ("Match Application", "mac", DIGER_TICKET_ROLE_ID),
}


def slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "", name.replace(" ", "-"))
    return name[:20] or "kullanici"


class TicketArchiveView(discord.ui.View):
    """Ticket kapatılınca gelen Transcript / Open / Delete butonları."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="archive_transcript")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        messages = []
        async for msg in channel.history(limit=500, oldest_first=True):
            if msg.author.bot and not msg.embeds:
                continue
            ts = msg.created_at.strftime("%d.%m.%Y %H:%M")
            content = msg.content or ""
            if msg.embeds:
                for e in msg.embeds:
                    content += f"[EMBED: {e.title or ''} — {e.description or ''}]"
            messages.append(f"[{ts}] {msg.author.display_name}: {content}")

        text = "\n".join(messages) or "Mesaj bulunamadı."
        file = discord.File(
            fp=__import__("io").BytesIO(text.encode("utf-8")),
            filename=f"transcript-{channel.name}.txt"
        )
        await interaction.response.send_message(file=file, ephemeral=True)

    @discord.ui.button(label="Open", style=discord.ButtonStyle.success, emoji="🔓", custom_id="archive_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        has_role = any(r.id in ARCHIVE_ROLE_IDS for r in getattr(member, "roles", []))
        if not (has_role or member.guild_permissions.administrator):
            await interaction.response.send_message("Bu işlem için yetkin yok.", ephemeral=True)
            return

        guild = interaction.guild
        channel = interaction.channel

        # Orijinal kategoriyi bul ve geri taşı
        ticket_category = guild.get_channel(TICKET_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        # Topic'ten açan kişiyi bul ve iznini geri ver
        if channel.topic:
            m = re.search(r"Açan: .+ \((\d+)\)", channel.topic)
            if m:
                opener = guild.get_member(int(m.group(1)))
                if opener:
                    overwrites[opener] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        new_name = channel.name.removeprefix("closed-")
        await channel.edit(
            name=new_name,
            category=ticket_category,
            overwrites=overwrites,
            reason=f"Ticket yeniden açıldı: {member}"
        )
        await interaction.response.send_message(f"✅ Ticket yeniden açıldı: {channel.mention}", ephemeral=True)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="archive_delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        has_role = any(r.id in ARCHIVE_ROLE_IDS for r in getattr(member, "roles", []))
        if not (has_role or member.guild_permissions.administrator):
            await interaction.response.send_message("Bu işlem için yetkin yok.", ephemeral=True)
            return

        await interaction.response.send_message("🗑️ Kanal 3 saniye içinde siliniyor...", ephemeral=True)
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=3))
        await interaction.channel.delete(reason=f"Ticket silindi: {member}")


class CloseTicketView(discord.ui.View):
    """Ticket kanalı içindeki Close Ticket butonu."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="ticket_close",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        channel = interaction.channel
        guild = interaction.guild

        is_opener = channel.topic and str(member.id) in channel.topic
        has_role = any(r.id in (KLAN_BASVURU_ROLE_ID, DIGER_TICKET_ROLE_ID) for r in getattr(member, "roles", []))

        if not (has_role or is_opener or member.guild_permissions.administrator):
            await interaction.response.send_message(
                "You don't have permission to close this ticket.", ephemeral=True
            )
            return

        await interaction.response.defer()

        # Ticket türü ve açan kişiyi topic'ten çek
        ticket_type = "Bilinmiyor"
        opener_mention = "Bilinmiyor"
        opener_id = None
        if channel.topic:
            m1 = re.search(r"Ticket türü: (.+?) \|", channel.topic)
            if m1:
                ticket_type = m1.group(1)
            m2 = re.search(r"Açan: .+ \((\d+)\)", channel.topic)
            if m2:
                opener_id = int(m2.group(1))
                opener_mention = f"<@{opener_id}>"

        # Transkript kategorisine taşı + kilitle
        transcript_category = guild.get_channel(TRANSCRIPT_CATEGORY_ID)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        for role_id in ARCHIVE_ROLE_IDS:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=False, read_message_history=True
                )

        new_name = f"closed-{channel.name}"[:100]
        await channel.edit(
            name=new_name,
            category=transcript_category,
            overwrites=overwrites,
            reason=f"Ticket kapatıldı: {member}"
        )

        # Kanal içine kapanma mesajı + butonlar
        close_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"**Ticket Closed by** {member.mention}",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        await channel.send(embed=close_embed, view=TicketArchiveView())




class TicketPanelView(discord.ui.View):
    """Ana panel: Klan Başvuru / Merc / Temsilci / Maç Başvurusu butonları."""

    def __init__(self):
        super().__init__(timeout=None)

    async def _open_ticket(self, interaction: discord.Interaction, custom_id: str):
        label, prefix, role_id = TICKET_TYPES[custom_id]
        guild = interaction.guild
        member = interaction.user

        if not TICKET_CATEGORY_ID:
            await interaction.response.send_message(
                "Ticket category is not configured (TICKET_CATEGORY_ID missing).", ephemeral=True
            )
            return

        category = guild.get_channel(TICKET_CATEGORY_ID)
        if category is None:
            await interaction.response.send_message(
                "Ticket category not found, please notify an admin.", ephemeral=True
            )
            return

        channel_name = f"{prefix}-{slugify(member.name)}"

        existing = discord.utils.get(category.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(
                f"You already have an open ticket: {existing.mention}", ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        if role_id:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

        channel = await category.create_text_channel(
            name=channel_name,
            overwrites=overwrites,
            topic=f"Ticket türü: {label} | Açan: {member} ({member.id})",
            reason=f"{label} ticket'ı - {member}",
        )

        if custom_id == "ticket_klan_basvuru":
            ping_msg = f"<@&{KLAN_BASVURU_ROLE_ID}> {member.mention}"
            await channel.send(ping_msg)

            embed = discord.Embed(
                title="🛡️ Klan Başvurusu",
                description=(
                    f"Hoş geldin {member.mention}! Başvurunu değerlendirebilmemiz için "
                    f"aşağıdaki bilgileri eksiksiz doldurmanı rica ediyoruz.\n\n"
                    f"**Lütfen sırasıyla yanıtla:**\n\n"
                    f"🔢 **SteamID64**\n"
                    f"👤 **İsim** *(gerçek adın veya bilinen adın)*\n"
                    f"🎮 **Oyun İçi Nick**\n"
                    f"⏱️ **Squad Oyun Saati** *(kaç saat?)*\n"
                    f"📅 **Günlük Aktiflik Süresi** *(ortalama kaç saat/gün?)*\n"
                    f"🏴 **Daha Önce Katıldığın Klanlar** *(yoksa 'Yok' yaz)*\n"
                    f"🔗 **Steam Profil Linki**\n\n"
                    f"Başvurun incelenecek ve en kısa sürede geri dönüş yapılacaktır. "
                    f"Ticket'ı kapatmak için aşağıdaki butonu kullanabilirsin."
                ),
                color=discord.Color.from_rgb(34, 139, 34),
            )
            embed.set_footer(text="Elite Guards • Klan Başvurusu")
            await channel.send(embed=embed, view=CloseTicketView())
        else:
            embed = discord.Embed(
                title=f"{label}",
                description=(
                    f"Welcome {member.mention}! You can write your request here.\n"
                    f"The relevant staff will respond as soon as possible. You can close this ticket "
                    f"with the button below once you're done."
                ),
                color=discord.Color.blurple(),
            )
            await channel.send(embed=embed, view=CloseTicketView())

        await interaction.response.send_message(
            f"Your ticket has been created: {channel.mention}", ephemeral=True
        )

    @discord.ui.button(label="Klan Başvuru", style=discord.ButtonStyle.success, emoji="📝", custom_id="ticket_klan_basvuru")
    async def klan_basvuru(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_ticket(interaction, "ticket_klan_basvuru")

    @discord.ui.button(label="Merc Application", style=discord.ButtonStyle.primary, emoji="🎯", custom_id="ticket_merc")
    async def merc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_ticket(interaction, "ticket_merc")

    @discord.ui.button(label="Clan Representative", style=discord.ButtonStyle.primary, emoji="🤝", custom_id="ticket_temsilci")
    async def temsilci(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_ticket(interaction, "ticket_temsilci")

    @discord.ui.button(label="Match Application", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="ticket_mac")
    async def mac(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._open_ticket(interaction, "ticket_mac")


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(CloseTicketView())
        self.bot.add_view(TicketArchiveView())

    @app_commands.command(name="ticket-panel", description="Ticket açma panelini bu kanala gönder")
    @app_commands.checks.has_permissions(administrator=True)
    async def ticket_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Elite Guards — Applications & Support",
            description=(
                "Select the button below that fits you to open a ticket. Only you and the "
                "relevant staff can see your ticket.\n\n"
                "📝 **Klan Başvuru** — To join the clan\n"
                "🎯 **Merc Application** — Request a merc for scrims/matches\n"
                "🤝 **Clan Representative** — Representative application\n"
                "⚔️ **Match Application** — To arrange a match"
            ),
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(text="Elite Guards")
        await interaction.channel.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message("Panel sent.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
