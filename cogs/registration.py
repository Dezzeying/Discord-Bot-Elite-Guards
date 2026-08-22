import os
import discord
from discord import app_commands
from discord.ext import commands

KAYIT_ROLE_ID = int(os.getenv("KAYIT_ROLE_ID", "0") or 0)  # komutu kullanabilecek rol
UYE_ROLE_ID_1 = int(os.getenv("UYE_ROLE_ID_1", "0") or 0)  # 1526568818019663953
UYE_ROLE_ID_2 = int(os.getenv("UYE_ROLE_ID_2", "0") or 0)  # 999999508136071268


class Registration(commands.Cog):
    """/kayit komutu ile üye kaydı."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="kayit", description="Üyeyi Elite Guards'a kayıt eder")
    @app_commands.describe(
        uye="Kayıt edilecek üye",
        isim="Gerçek isim (örn: Ekrem)",
        nick="Oyun içi nick (örn: ExZatoon)",
    )
    async def kayit(
        self,
        interaction: discord.Interaction,
        uye: discord.Member,
        isim: str,
        nick: str,
    ):
        # Yetki kontrolü
        has_role = any(r.id == KAYIT_ROLE_ID for r in interaction.user.roles)
        if not (has_role or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                "Bu komutu kullanma yetkin yok.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        yeni_isim = f"EG-R | {isim} / {nick}"

        # İsim değiştir (32 karakter Discord limiti)
        try:
            await uye.edit(nick=yeni_isim[:32], reason=f"Kayıt: {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                f"⚠️ {uye.mention} kullanıcısının ismini değiştiremedim (yetki yok veya sunucu sahibi).",
                ephemeral=True
            )
            return

        # Rolleri ekle
        roller = []
        for role_id in [UYE_ROLE_ID_1, UYE_ROLE_ID_2]:
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role:
                    roller.append(role)

        if roller:
            try:
                await uye.add_roles(*roller, reason=f"Kayıt: {interaction.user}")
            except discord.Forbidden:
                await interaction.followup.send(
                    f"⚠️ Roller eklenemedi (yetki sorunu).", ephemeral=True
                )
                return

        embed = discord.Embed(
            title="✅ Kayıt Başarılı",
            color=discord.Color.green(),
        )
        embed.add_field(name="Üye", value=uye.mention, inline=True)
        embed.add_field(name="Yeni İsim", value=yeni_isim, inline=True)
        embed.add_field(name="Roller", value="\n".join(r.mention for r in roller) or "—", inline=False)
        embed.set_footer(text=f"Kaydeden: {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=False)

        # Mentorluk forum sayfası aç
        mentorship_cog = interaction.client.cogs.get("Mentorship")
        if mentorship_cog:
            await mentorship_cog.create_mentorship_post(
                guild=interaction.guild,
                uye=uye,
                isim=isim,
                nick=nick,
                kaydeden=interaction.user,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
