import discord
from discord.ext import commands


class Tickets(commands.Cog):
    """Başvuru/Support ticket sistemi (Klan Başvuru, Merc, Temsilci, Maç Başvurusu)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # TODO: ticket açma butonları, kanal oluşturma, kapama mantığı buraya gelecek


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
