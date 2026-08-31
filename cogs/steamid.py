import os
import re
import sqlite3
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

STEAMID_LIST_CHANNEL_ID = int(os.getenv("STEAMID_LIST_CHANNEL_ID", "0") or 0)
MEMBER_ROLE_ID = int(os.getenv("UYE_ROLE_ID_2", "0") or 0)  # 999999508136071268
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

STEAMID64_RE = re.compile(r"7656\d{13}")
STEAM_URL_RE = re.compile(r"steamcommunity\.com/(id|profiles)/([^\s/]+)")
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


def remove_member_by_steamid(steamid: str) -> bool:
    conn = get_db()
    cur = conn.execute('DELETE FROM members WHERE steamid = ?', (steamid,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_all_members():
    conn = get_db()
    rows = conn.execute('SELECT * FROM members ORDER BY isim').fetchall()
    conn.close()
    return rows


async def resolve_steam_url(url: str) -> str | None:
    """Steam profil linkinden SteamID64 çözer."""
    m = STEAM_URL_RE.search(url)
    if not m:
        return None

    url_type, value = m.group(1), m.group(2)

    # Zaten SteamID64 ise direkt döndür
    if url_type == "profiles" and STEAMID64_RE.fullmatch(value):
        return value

    # Vanity URL'yi resolve et
    api_url = (
        f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
        f"?key={STEAM_API_KEY}&vanityurl={value}"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()
            if data.get("response", {}).get("success") == 1:
                return data["response"]["steamid"]
    return None


def parse_ticket_content(messages: list[str]) -> dict:
    """Ticket mesajlarından SteamID64, isim, nick çek."""
    full_text = "\n".join(messages)
    result = {"steamid": None, "isim": None, "nick": None, "steam_url": None}

    # Önce direkt SteamID64 ara
    m = STEAMID64_RE.search(full_text)
    if m:
        result["steamid"] = m.group(0)

    # Steam URL ara
    mu = STEAM_URL_RE.search(full_text)
    if mu:
        result["steam_url"] = mu.group(0)

    # Form satırlarını parse et
    for line in full_text.split("\n"):
        line_lower = line.lower()
        if any(k in line_lower for k in ["isim", "gerçek", "ad:"]):
            val = re.sub(r".*?[:：]\s*", "", line).strip()
            if val and not result["isim"]:
                result["isim"] = val
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

    satir_aktif = [f"`{m['steamid']}`  {m['isim']}" for m in aktif]
    satir_bekleyen = [f"⏳  {m['isim']}" for m in bekleyen]
    tum_satirlar = satir_aktif + satir_bekleyen

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
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(UpdateListView())
        init_db()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Üye rolü alınınca DB'den sil."""
        if MEMBER_ROLE_ID == 0:
            return
        before_ids = {r.id for r in before.roles}
        after_ids = {r.id for r in after.roles}

        # Rol alındıysa (öncede vardı, şimdi yok)
        if MEMBER_ROLE_ID in before_ids and MEMBER_ROLE_ID not in after_ids:
            # Discord ID'ye göre DB'de eşleşen steamid'i bul (şimdilik isimle ara)
            conn = get_db()
            # Üyenin nick'inden isim çıkar (EG-R | İsim / Nick formatı)
            nick = after.display_name
            m = re.search(r"EG-R?\s*\|\s*(.+)", nick)
            isim_ara = m.group(1).strip() if m else nick.strip()

            row = conn.execute(
                'SELECT steamid FROM members WHERE isim LIKE ?',
                (f"%{isim_ara.split('/')[0].strip()}%",)
            ).fetchone()
            conn.close()

            if row:
                remove_member_by_steamid(row["steamid"])
                await self.refresh_list_embed()

    async def extract_from_ticket(self, channel: discord.TextChannel) -> dict | None:
        if not channel.topic or "Klan Başvuru" not in channel.topic:
            return None
        messages = []
        async for msg in channel.history(limit=100, oldest_first=True):
            if not msg.author.bot:
                messages.append(msg.content)
        return parse_ticket_content(messages)

    async def add_from_ticket(self, channel: discord.TextChannel):
        data = await self.extract_from_ticket(channel)
        if not data:
            return

        steamid = data["steamid"]

        # SteamID yoksa URL'den resolve etmeyi dene
        if not steamid and data.get("steam_url"):
            steamid = await resolve_steam_url(data["steam_url"])

        if not steamid:
            return

        isim = data["isim"] or "Bilinmiyor"
        nick = data["nick"]
        isim_str = f"{isim} / {nick}" if nick else isim

        eklendi = add_member(steamid, isim_str)
        await self.refresh_list_embed()
        return eklendi, steamid, isim_str

    async def refresh_list_embed(self):
        if not STEAMID_LIST_CHANNEL_ID:
            return
        channel = self.bot.get_channel(STEAMID_LIST_CHANNEL_ID)
        if not channel:
            return
        members = get_all_members()
        embed = build_embed(members)
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
    @app_commands.describe(steamid="SteamID64 veya Steam profil linki", isim="Üye ismi / nick")
    @app_commands.checks.has_permissions(administrator=True)
    async def steamid_ekle(self, interaction: discord.Interaction, steamid: str, isim: str):
        await interaction.response.defer(ephemeral=True)

        # URL ise resolve et
        if "steamcommunity.com" in steamid:
            resolved = await resolve_steam_url(steamid)
            if not resolved:
                await interaction.followup.send("Steam profil linki çözümlenemedi.", ephemeral=True)
                return
            steamid = resolved

        if not STEAMID64_RE.fullmatch(steamid):
            await interaction.followup.send("Geçersiz SteamID64 formatı.", ephemeral=True)
            return

        eklendi = add_member(steamid, isim)
        if eklendi:
            await self.refresh_list_embed()
            await interaction.followup.send(f"✅ Eklendi: `{steamid}` — {isim}", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Bu SteamID zaten listede.", ephemeral=True)

    @app_commands.command(name="steamid-sil", description="SteamID listesinden üye sil")
    @app_commands.describe(steamid="Silinecek SteamID64")
    @app_commands.checks.has_permissions(administrator=True)
    async def steamid_sil(self, interaction: discord.Interaction, steamid: str):
        silindi = remove_member_by_steamid(steamid)
        if silindi:
            await self.refresh_list_embed()
            await interaction.response.send_message(f"✅ Silindi: `{steamid}`", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Bu SteamID listede bulunamadı.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SteamID(bot))
