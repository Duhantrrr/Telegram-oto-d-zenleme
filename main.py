import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = 16896485
API_HASH = "29b5bb9351b4cb3738d73abaf5eb28ca"
SESSION_STRING = os.environ.get("SESSION_STRING", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

app = FastAPI(title="Telegram Web Kontrol Paneli")


@app.on_event("startup")
async def startup_event():
  await client.start()
  print("Web Panel ve Userbot aktif!")


# 1. ARKA PLAN: Telegram'da "done" veya "ads" yazınca otomatik düzenleme
@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event):
  mesaj = event.raw_text.strip()
  mesaj_kucuk = mesaj.lower()

  if mesaj_kucuk == "done":
    hedef_mesaj = (
        "I shared your post here\n"
        "t.me/ratlogscloud\n\n"
        "https://t.me/+vbR5re1Xa-VkOWE0"
    )
    await event.edit(hedef_mesaj)

  elif mesaj_kucuk == "ads":
    hedef_mesaj = (
        "Ads to ads @tgciyim\n\n"
        "https://t.me/+vbR5re1Xa-VkOWE0"
    )
    await event.edit(hedef_mesaj)


# 2. WEB PANELİ (Arayüz)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
  return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Telegram Kontrol Paneli</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f9; text-align: center; padding: 20px; }
            .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); display: inline-block; width: 100%; max-width: 400px; box-sizing: border-box; margin-bottom: 20px; }
            input, select, textarea { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
            button { background: #0088cc; color: white; border: none; padding: 12px; width: 100%; border-radius: 5px; cursor: pointer; font-size: 16px; }
            button:hover { background: #006699; }
            h2 { color: #333; font-size: 20px; }
        </style>
    </head>
    <body>

        <!-- MESAJ GÖNDERME KARTI -->
        <div class="card">
            <h2>🚀 Telegram'dan Mesaj Gönder</h2>
            <form action="/send-message" method="post">
                <input type="text" name="chat_id" placeholder="Kime (@kullaniciadi veya ID)" required>
                <textarea name="message" rows="3" placeholder="Göndermek istediğin mesaj..." required></textarea>
                <button type="submit">Mesajı Gönder</button>
            </form>
        </div>

        <!-- MESAJ DÜZENLEME KARTI -->
        <div class="card">
            <h2>✏️ Gönderilen Mesajı Değiştir</h2>
            <form action="/edit-message" method="post">
                <input type="text" name="chat_id" placeholder="Sohbet (@kullaniciadi veya ID)" required>
                <input type="text" name="message_id" placeholder="Mesaj ID numarası" required>
                <select name="secim">
                    <option value="done">Done Şablonu (İngilizce)</option>
                    <option value="ads">Ads Şablonu (Reklam)</option>
                </select>
                <button type="submit">Mesajı Güncelle</button>
            </form>
        </div>

    </body>
    </html>
    """


# WEB SİTESİ: Mesaj Gönderme İşlemi
@app.post("/send-message", response_class=HTMLResponse)
async def send_message(chat_id: str, message: str):
  try:
    try:
      target = int(chat_id)
    except ValueError:
      target = chat_id

    await client.send_message(target, message)
    return """
        <h3>✅ Başarılı! Mesaj Gönderildi.</h3>
        <a href="/">Geri Dön</a>
        """
  except Exception as e:
    return f"""
        <h3>❌ Hata Oluştu:</h3>
        <p>{str(e)}</p>
        <a href="/">Geri Dön</a>
        """


# WEB SİTESİ: Mesaj Düzenleme İşlemi
@app.post("/edit-message", response_class=HTMLResponse)
async def edit_message(chat_id: str, message_id: int, secim: str):
  try:
    try:
      target = int(chat_id)
    except ValueError:
      target = chat_id

    if secim == "done":
      yeni_metin = (
          "I shared your post here\n"
          "t.me/ratlogscloud\n\n"
          "https://t.me/+vbR5re1Xa-VkOWE0"
      )
    else:
      yeni_metin = (
          "Ads to ads @tgciyim\n\n"
          "https://t.me/+vbR5re1Xa-VkOWE0"
      )

    await client.edit_message(target, message_id, yeni_metin)
    return """
        <h3>✅ Başarılı! Mesaj Güncellendi.</h3>
        <a href="/">Geri Dön</a>
        """
  except Exception as e:
    return f"""
        <h3>❌ Hata Oluştu:</h3>
        <p>{str(e)}</p>
        <a href="/">Geri Dön</a>
        """
