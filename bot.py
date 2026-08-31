import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # opsiyonel: slash komutları tek sunucuya hızlı sync etmek için

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("elite-guards-bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

INITIAL_COGS = [
    "cogs.tickets",
    "cogs.steamid",
    "cogs.registration",
    "cogs.mentorship",
    "cogs.reminder",
]


@bot.event
async def on_ready():
    log.info(f"Giriş yapıldı: {bot.user} ({bot.user.id})")
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
    else:
        synced = await bot.tree.sync()
    log.info(f"{len(synced)} slash komut senkronize edildi.")


async def main():
    async with bot:
        for cog in INITIAL_COGS:
            try:
                await bot.load_extension(cog)
                log.info(f"Yüklendi: {cog}")
            except Exception as e:
                log.error(f"Yüklenemedi {cog}: {e}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN .env dosyasında bulunamadı.")
    asyncio.run(main())
