import os
import re
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands

STEAMID_LIST_CHANNEL_ID = int(os.getenv("STEAMID_LIST_CHANNEL_ID", "0") or 0)
STEAMID64_RE = re.compile(r"7656\d{13}")
DB_PATH = "steamids.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS members (
        steamid TEXT PRIMARY KEY,
        isim TEXT NOT NULL,
        durum TEXT DEFAULT "bekliyor",
        eklenme_tarihi TEXT
    )''')
    conn.commit()
    conn.close()


def add_member(steamid: str, isim: str) -> bool:
    """Üye ekle. Zaten varsa False döner."""
    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO members (steamid, isim, durum, eklenme_tarihi) VALUES (?, ?, "aktif", datetime("now"))',
            (steamid, isim)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_all_members():
    conn = get_db()
    rows = conn.execute('SELECT * FROM members ORDER BY isim').fetchall()
    conn.close()
    return rows


def parse_ticket_content(messages: list[str]) -> dict:
    """Ticket mesajlarından SteamID64 ve form bilgilerini çek."""
    full_text = "\n".join(messages)

    result = {
        "steamid": None,
        "isim": None,
        "nick": None,
    }

    # SteamID64 bul
    m = STEAMID64_RE.search(full_text)
    if m:
        result["steamid"] = m.group(0)

    # Form satırlarını parse et (kullanıcı sırasıyla yazmış olabilir)
    lines = full_text.split("\n")
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # İsim
        if any(k in line_lower for k in ["isim", "gerçek", "ad:"]):
            val = re.sub(r".*?[:：]\s*", "", line).strip()
            if val and not result["isim"]:
                result["isim"] = val
        # Nick
        if any(k in line_lower for k in ["nick", "oyun içi", "oyun ici"]):
            val = re.sub(r".*?[:：]\s*", "", line).strip()
            if val and not result["nick"]:
                result["nick"] = val

    return result


def build_embed(members) -> discord.Embed:
    aktif = [m for m in members if m["durum"] == "aktif"]
    bekleyen = [m for m in members if m["durum"] == "bekliyor"]

    embed = discord.Embed(
        title="⚔️ Elite Guards — SteamID Listesi",
        color=discord.Color.from_rgb(255, 165, 0),
    )
    embed.add_field(
        name=f"👥 Toplam {len(members)}",
        value=f"✅ {len(aktif)} SteamID   ⏳ {len(bekleyen)} bekliyor",
        inline=False,
    )

    # Liste (Discord 1024 karakter limiti nedeniyle böl)
    satir_aktif = [f"`{m['steamid']}`  {m['isim']}" for m in aktif]
    satir_bekleyen = [f"⏳  {m['isim']}" for m in bekleyen]
    tum_satirlar = satir_aktif + satir_bekleyen

    # Max 4096 desc limiti, chunk'a böl
    chunk = ""
    chunks = []
    for s in tum_satirlar:
        if len(chunk) + len(s) + 1 > 1000:
            chunks.append(chunk)
            chunk = s
        else:
            chunk = chunk + "\n" + s if chunk else s
    if chunk:
        chunks.append(chunk)

    for i, ch in enumerate(chunks):
        embed.add_field(name="\u200b" if i > 0 else "Liste", value=ch, inline=False)

    embed.set_footer(text="🔄 Güncelle butonuna bas → liste yenilenir")
    return embed


class UpdateListView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 Güncelle", style=discord.ButtonStyle.primary, custom_id="steamid_guncelle")
    async def guncelle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        members = get_all_members()
        embed = build_embed(members)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.followup.send(f"✅ Liste güncellendi — {len(members)} üye.", ephemeral=True)


class SteamID(commands.Cog):
    """Ticket'lardan SteamID64 çekme ve klan listesi yönetimi."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(UpdateListView())
        init_db()

    async def extract_from_ticket(self, channel: discord.TextChannel) -> dict | None:
        """Klan başvuru ticket kanalından SteamID + isim bilgisini çek."""
        if not channel.topic or "Klan Başvuru" not in channel.topic:
            return None

        messages = []
        async for msg in channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                messages.append(msg.content)

        return parse_ticket_content(messages)

    async def add_from_ticket(self, channel: discord.TextChannel):
        """Ticket kapanınca çağrılır — SteamID ve ismi DB'ye ekler."""
        data = await self.extract_from_ticket(channel)
        if not data or not data["steamid"]:
            return

        isim = data["isim"] or "Bilinmiyor"
        nick = data["nick"]
        isim_str = f"{isim} / {nick}" if nick else isim

        eklendi = add_member(data["steamid"], isim_str)

        # Liste embed'ini güncelle
        await self.refresh_list_embed()
        return eklendi, data["steamid"], isim_str

    async def refresh_list_embed(self):
        """SteamID liste kanalındaki embed'i güncelle."""
        if not STEAMID_LIST_CHANNEL_ID:
            return
        channel = self.bot.get_channel(STEAMID_LIST_CHANNEL_ID)
        if not channel:
            return

        members = get_all_members()
        embed = build_embed(members)

        # Kanalın son mesajını bul — bot mesajı ise güncelle, yoksa yeni gönder
        async for msg in channel.history(limit=10):
            if msg.author == self.bot.user and msg.embeds:
                await msg.edit(embed=embed, view=UpdateListView())
                return

        await channel.send(embed=embed, view=UpdateListView())

    @app_commands.command(name="steamid-listesi", description="SteamID listesini kanala gönder")
    @app_commands.checks.has_permissions(administrator=True)
    async def steamid_listesi(self, interaction: discord.Interaction):
        members = get_all_members()
        embed = build_embed(members)
        await interaction.channel.send(embed=embed, view=UpdateListView())
        await interaction.response.send_message("Liste gönderildi.", ephemeral=True)

    @app_commands.command(name="steamid-ekle", description="Manuel olarak SteamID ekle")
    @app_commands.describe(steamid="SteamID64", isim="Üye ismi")
    @app_commands.checks.has_permissions(administrator=True)
    async def steamid_ekle(self, interaction: discord.Interaction, steamid: str, isim: str):
        if not STEAMID64_RE.fullmatch(steamid):
            await interaction.response.send_message("Geçersiz SteamID64 formatı.", ephemeral=True)
            return
        eklendi = add_member(steamid, isim)
        if eklendi:
            await self.refresh_list_embed()
            await interaction.response.send_message(f"✅ Eklendi: `{steamid}` — {isim}", ephemeral=True)
        else:
            await interaction.response.send_message(f"⚠️ Bu SteamID zaten listede.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SteamID(bot))
