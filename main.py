import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = 16896485
API_HASH = "29b5bb9351b4cb3738d73abaf5eb28ca"

# Geçici hafıza değişkenleri
phone_hash_global = None
phone_global = None

SESSION_STRING = os.environ.get("SESSION_STRING", "")
client = TelegramClient(
    StringSession(SESSION_STRING) if SESSION_STRING else "temp_session",
    API_ID,
    API_HASH,
)

app = FastAPI(title="Telegram Kontrol Paneli")


@app.on_event("startup")
async def startup_event():
  if SESSION_STRING:
    try:
      await client.start()
      print("Mevcut oturumla bot aktif!")
    except Exception as e:
      print(f"Başlangıç oturum hatası: {e}")


# 1. ARKA PLAN: Telegram'da otomatik düzenleme
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


# 2. WEB PANELİ ARAYÜZÜ
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
  is_connected = False
  try:
    is_connected = client.is_connected() and await client.is_user_authorized()
  except Exception:
    is_connected = False

  if not is_connected:
    return """
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Telegram Giriş</title>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f4f4f9; text-align: center; padding: 40px; }
                .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0px 0px 10px rgba(0,0,0,0.1); display: inline-block; width: 100%; max-width: 350px; }
                input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 5px; box-sizing: border-box; }
                button { background: #0088cc; color: white; border: none; padding: 12px; width: 100%; border-radius: 5px; cursor: pointer; font-size: 16px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h2>🔐 Telegram Giriş Paneli</h2>
                <form action="/send-code" method="post">
                    <input type="text" name="phone" value="905315151419" required>
                    <button type="submit">Kod Gönder</button>
                </form>
            </div>
        </body>
        </html>
        """

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
            .success { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <p class="success">🟢 Bot ve Oturum Aktif!</p>

        <div class="card">
            <h2>🚀 Telegram'dan Mesaj Gönder</h2>
            <form action="/send-message" method="post">
                <input type="text" name="chat_id" placeholder="Kime (@kullaniciadi veya ID)" required>
                <textarea name="message" rows="3" placeholder="Mesajınız..." required></textarea>
                <button type="submit">Mesajı Gönder</button>
            </form>
        </div>

        <div class="card">
            <h2>✏️ Mesajı Değiştir</h2>
            <form action="/edit-message" method="post">
                <input type="text" name="chat_id" placeholder="Sohbet (@kullaniciadi veya ID)" required>
                <input type="text" name="message_id" placeholder="Mesaj ID" required>
                <select name="secim">
                    <option value="done">Done Şablonu (İngilizce)</option>
                    <option value="ads">Ads Şablonu (Reklam)</option>
                </select>
                <button type="submit">Güncelle</button>
            </form>
        </div>
    </body>
    </html>
    """


# TELEGRAM KODU GÖNDERME (Form ile alacak şekilde düzeltildi)
@app.post("/send-code", response_class=HTMLResponse)
async def send_code(phone: str = Form(...)):
  global client, phone_hash_global, phone_global
  phone_global = phone
  try:
    if not client.is_connected():
      await client.connect()

    result = await client.send_code_request(phone)
    phone_hash_global = result.phone_code_hash

    return f"""
        <!DOCTYPE html>
        <html lang="tr">
        <head><meta charset="UTF-8"><title>Kod Gir</title>
        <style>body { font-family: Arial; text-align: center; padding: 40px; background: #f4f4f9; }
        .card { background: white; padding: 20px; border-radius: 10px; display: inline-block; width: 300px; }
        input { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
        button { background: #0088cc; color: white; border: none; padding: 10px; width: 100%; border-radius: 5px; }</style>
        </head>
        <body>
            <div class="card">
                <h2>📲 Telegram Kodunu Gir</h2>
                <p><b>{phone}</b> numarasına gelen kodu yazın:</p>
                <form action="/verify-code" method="post">
                    <input type="text" name="code" placeholder="Örn: 12345" required>
                    <button type="submit">Devam Et</button>
                </form>
            </div>
        </body>
        </html>
        """
  except Exception as e:
    return f"<h3>Hata: {str(e)}</h3><a href='/'>Geri Dön</a>"


# KODU ONAYLAYIP GİRİŞ YAPMA (2FA KONTROLÜ İLE)
@app.post("/verify-code", response_class=HTMLResponse)
async def verify_code(code: str = Form(...)):
  global client, phone_hash_global, phone_global
  try:
    await client.sign_in(
        phone=phone_global, code=code, phone_code_hash=phone_hash_global
    )
    return basarili_sayfa()
  except Exception as e:
    error_msg = str(e)
    # Eğer 2 Adımlı Doğrulama (Cloud Şifresi) varsa buraya düşer
    if "SessionPasswordNeededError" in error_msg or "password" in error_msg.lower():
      return f"""
            <!DOCTYPE html>
            <html lang="tr">
            <head><meta charset="UTF-8"><title>2FA Şifre</title>
            <style>body { font-family: Arial; text-align: center; padding: 40px; background: #f4f4f9; }
            .card { background: white; padding: 20px; border-radius: 10px; display: inline-block; width: 300px; }
            input { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
            button { background: #0088cc; color: white; border: none; padding: 10px; width: 100%; border-radius: 5px; }</style>
            </head>
            <body>
                <div class="card">
                    <h2>🔒 2 Adımlı Doğrulama</h2>
                    <p>Hesabınızda şifre var. Lütfen Telegram bulut şifrenizi girin:</p>
                    <form action="/verify-password" method="post">
                        <input type="password" name="password" placeholder="Bulut Şifreniz" required>
                        <button type="submit">Giriş Yap</button>
                    </form>
                </div>
            </body>
            </html>
            """
    return f"<h3>Giriş Başarısız: {error_msg}</h3><a href='/'>Geri Dön</a>"


# 2FA ŞİFRESİNİ DOĞRULAMA
@app.post("/verify-password", response_class=HTMLResponse)
async def verify_password(password: str = Form(...)):
  global client
  try:
    await client.sign_in(password=password)
    return basarili_sayfa()
  except Exception as e:
    return f"<h3>Şifre Yanlış: {str(e)}</h3><a href='/'>Geri Dön</a>"


def basarili_sayfa():
  session_str = client.session.save()
  return f"""
    <h3>✅ Başarıyla Giriş Yapıldı!</h3>
    <p>Oturumunuz açıldı. Bu uzun kodu kopyalayıp Render'daki <b>SESSION_STRING</b> kısmına yapıştırırsanız bir daha asla kod istemez:</p>
    <textarea rows="4" style="width:100%;">{session_str}</textarea>
    <br><br>
    <a href="/" style="background:#0088cc; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">Panele Git</a>
    """


@app.post("/send-message", response_class=HTMLResponse)
async def send_message(chat_id: str = Form(...), message: str = Form(...)):
  try:
    target = int(chat_id) if chat_id.isdigit() else chat_id
    await client.send_message(target, message)
    return "<h3>✅ Mesaj Gönderildi!</h3><a href='/'>Geri Dön</a>"
  except Exception as e:
    return f"<h3>Hata: {str(e)}</h3><a href='/'>Geri Dön</a>"


@app.post("/edit-message", response_class=HTMLResponse)
async def edit_message(
    chat_id: str = Form(...),
    message_id: int = Form(...),
    secim: str = Form(...),
):
  try:
    target = int(chat_id) if chat_id.isdigit() else chat_id
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
    return "<h3>✅ Mesaj Güncellendi!</h3><a href='/'>Geri Dön</a>"
  except Exception as e:
    return f"<h3>Hata: {str(e)}</h3><a href='/'>Geri Dön</a>"
