import os
import re
import datetime
import discord
from discord import app_commands
from discord.ext import commands

TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0") or 0)
KLAN_BASVURU_ROLE_ID = int(os.getenv("KLAN_BASVURU_ROLE_ID", "0") or 0)
DIGER_TICKET_ROLE_ID = int(os.getenv("DIGER_TICKET_ROLE_ID", "0") or 0)

# Buton id -> (görünen ad, kanal öneki, o türü görecek rol id'si)
TICKET_TYPES = {
    "ticket_klan_basvuru": ("Klan Başvuru", "klan", KLAN_BASVURU_ROLE_ID),
    "ticket_merc": ("Merc Application", "merc", DIGER_TICKET_ROLE_ID),
    "ticket_temsilci": ("Clan Representative", "temsilci", DIGER_TICKET_ROLE_ID),
    "ticket_mac": ("Match Application", "mac", DIGER_TICKET_ROLE_ID),
}


def slugify(name: str) -> str:
    """Discord kanal adı için kullanıcı adını sadeleştirir."""
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "", name.replace(" ", "-"))
    return name[:20] or "kullanici"


class CloseTicketView(discord.ui.View):
    """Ticket kanalı içindeki 'Kapat' butonu. Bot yeniden başlasa da persistent çalışsın diye timeout=None."""

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
        is_opener = interaction.channel.topic and str(member.id) in interaction.channel.topic
        has_role = any(r.id in (KLAN_BASVURU_ROLE_ID, DIGER_TICKET_ROLE_ID) for r in getattr(member, "roles", []))

        if not (has_role or is_opener or member.guild_permissions.administrator):
            await interaction.response.send_message(
                "You don't have permission to close this ticket.", ephemeral=True
            )
            return

        await interaction.response.send_message("Closing this ticket in 5 seconds...")
        await interaction.channel.edit(name=f"closed-{interaction.channel.name}"[:100])
        await discord.utils.sleep_until(discord.utils.utcnow() + datetime.timedelta(seconds=5))
        await interaction.channel.delete(reason=f"Ticket closed by: {member}")


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
    """Başvuru/Support ticket sistemi (Klan Başvuru, Merc, Temsilci, Maç Başvurusu)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(CloseTicketView())

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
