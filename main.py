import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient, events

# Verdiğin Telegram API Bilgileri
API_ID = 16896485
API_HASH = "29b5bb9351b4cb3738d73abaf5eb28ca"

# Telethon İstemcisi
client = TelegramClient("userbot_session", API_ID, API_HASH)

app = FastAPI(title="Telegram Fast API Userbot")


class EditRequest(BaseModel):
  chat_id: int
  message_id: int
  new_text: str


@app.on_event("startup")
async def startup_event():
  await client.start()
  print("Userbot Render üzerinde aktif ve çalışıyor!")


# Telegram'dan yazdığın mesajları anlık yakalayan kısım
@client.on(events.NewMessage(outgoing=True))
async def handle_outgoing_message(event):
  mesaj = event.raw_text.strip()
  mesaj_kucuk = mesaj.lower()

  # 1. Senaryo: "done" yazılırsa
  if mesaj_kucuk == "done":
    hedef_mesaj = (
        "Of course, I translated it into English, I shared your post here:"
        " t.me/ratlogscloud\n\nhttps://t.me/+vbR5re1Xa-VkOWE0"
    )
    await event.edit(hedef_mesaj)

  # 2. Senaryo: "Ads" yazılırsa
  elif mesaj_kucuk == "ads":
    hedef_mesaj = "Ads to ads @tgciyim"
    await event.edit(hedef_mesaj)


@app.get("/")
def root():
  return {"status": "Bot aktif ve çalışıyor!"}


@app.post("/edit-message")
async def api_edit_message(data: EditRequest):
  try:
    await client.edit_message(data.chat_id, data.message_id, data.new_text)
    return {
        "status": "success",
        "message": "Mesaj başarıyla düzenlendi.",
    }
  except Exception as e:
    raise HTTPException(status_code=400, detail=str(e))
