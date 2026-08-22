import re
import discord
from discord.ext import commands

# 17 haneli SteamID64 formatı (76561198... ile başlar)
STEAMID64_RE = re.compile(r"7656\d{13}")


def extract_steamid64(text: str) -> str | None:
    match = STEAMID64_RE.search(text)
    return match.group(0) if match else None


class SteamID(commands.Cog):
    """Ticket mesajlarından SteamID64 çekme ve klan listesini güncelleme."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # TODO: ticket kapanınca mesajları tarayıp SteamID64 çekme
    # TODO: liste embed'ini güncelleme (toplam / doğrulanmış / bekleyen sayaçları)


async def setup(bot: commands.Bot):
    await bot.add_cog(SteamID(bot))
