# Discord-Bot-Elite-Guards (Squad Advisor)

Elite Guards klanı için asistan Discord botu.

## Özellikler (planlanan)
- Başvuru/Support ticket sistemi
- Ticket'lardan otomatik SteamID64 çekme ve klan listesi güncelleme
- `/kayit` komutu ile üye kaydı
- Kayıt olan üyeler için otomatik mentorluk sayfası

## Kurulum
1. `python -m venv venv && source venv/bin/activate` (Windows: `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. `.env.example` dosyasını `.env` olarak kopyala, `DISCORD_TOKEN` ve `GUILD_ID` değerlerini doldur
4. `python bot.py`

## Proje yapısı
```
bot.py                 # giriş noktası, cog yükleyici
cogs/
  tickets.py            # başvuru/support ticket sistemi
  steamid.py             # SteamID64 çekme ve liste güncelleme
  registration.py       # /kayit komutu
  mentorship.py          # mentorluk sayfası oluşturma
```
