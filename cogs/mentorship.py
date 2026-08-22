import os
import discord
from discord.ext import commands

MENTORSHIP_FORUM_ID = int(os.getenv("MENTORSHIP_FORUM_ID", "0") or 0)


class Mentorship(commands.Cog):
    """Kayıt olan üyeler için mentorluk forum sayfası açma."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_mentorship_post(
        self,
        guild: discord.Guild,
        uye: discord.Member,
        isim: str,
        nick: str,
        kaydeden: discord.Member,
    ):
        if not MENTORSHIP_FORUM_ID:
            return

        forum = guild.get_channel(MENTORSHIP_FORUM_ID)
        if not forum or not isinstance(forum, discord.ForumChannel):
            return

        baslik = f"{isim} ({nick})"

        embed = discord.Embed(
            title=f"{isim} — Recruit Takip",
            color=discord.Color.from_rgb(88, 101, 242),
        )
        embed.add_field(name="Üye", value=uye.mention, inline=False)
        embed.add_field(name="Gerçek isim", value=isim, inline=True)
        embed.add_field(name="Oyun nicki", value=nick, inline=True)
        embed.add_field(name="Kabul eden", value=kaydeden.mention, inline=False)
        embed.description = (
            "Mentor değerlendirmesi bekleniyor. "
            "Ana kadroya hazır olunca `?terfi` kullanılır."
        )

        await forum.create_thread(
            name=baslik,
            embed=embed,
            reason=f"Kayıt: {uye} — {kaydeden}",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Mentorship(bot))
