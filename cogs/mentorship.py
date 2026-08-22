import discord
from discord.ext import commands


class Mentorship(commands.Cog):
    """Kayıt olan üyeler için mentorluk forum sayfası açma."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_mentorship_post(self, member: discord.Member):
        # TODO: mentorluk forum kanalında üye için otomatik thread/post açma
        pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Mentorship(bot))
