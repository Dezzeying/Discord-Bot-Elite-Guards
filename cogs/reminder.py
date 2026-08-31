import os
import asyncio
import discord
from discord.ext import commands, tasks

OWNER_ID = int(os.getenv("OWNER_ID", "0") or 0)
REMINDER_INTERVAL_DAYS = 2


class Reminder(commands.Cog):
    """Bot hosting yenileme hatırlatıcısı."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.hosting_reminder.start()

    def cog_unload(self):
        self.hosting_reminder.cancel()

    @tasks.loop(hours=REMINDER_INTERVAL_DAYS * 24)
    async def hosting_reminder(self):
        if not OWNER_ID:
            return
        user = await self.bot.fetch_user(OWNER_ID)
        if user:
            embed = discord.Embed(
                title="⚠️ Hosting Hatırlatıcısı",
                description="Bot hosting planını yenilemeyi unutma!",
                color=discord.Color.orange(),
            )
            embed.set_footer(text="Elite Guards • Squad Advisor")
            try:
                await user.send(embed=embed)
            except discord.Forbidden:
                pass

    @hosting_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
