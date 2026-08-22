import discord
from discord import app_commands
from discord.ext import commands


class Registration(commands.Cog):
    """/kayit komutu ile üye kaydı."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="kayit", description="Kendini Elite Guards üyesi olarak kaydet")
    @app_commands.describe(steamid="SteamID64 veya Steam profil linkin")
    async def kayit(self, interaction: discord.Interaction, steamid: str):
        # TODO: SteamID64 doğrulama, DB'ye kaydetme
        # TODO: kayıt tamamlanınca mentorship cog'unu tetikleyip sayfa açtırma
        await interaction.response.send_message(
            f"Kayıt alındı: {steamid} (işleniyor...)", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
