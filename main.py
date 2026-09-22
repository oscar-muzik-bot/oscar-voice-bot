import os
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import google.generativeai as genai
from gtts import gTTS

logging.basicConfig(level=logging.INFO)

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
STRING_SESSION = os.getenv("STRING_SESSION", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini API Yapılandırması
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
else:
    model = None
    logging.warning("GEMINI_API_KEY bulunamadı!")

# Bot İstemcisi (Mesajlara cevap veren)
app = Client(
    "oscar_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Sesli Sohbete Katılacak Asistan İstemcisi (Kullanıcı hesabı)
if STRING_SESSION:
    user_app = Client(
        "oscar_user",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=STRING_SESSION
    )
    call_py = PyTgCalls(user_app)
else:
    user_app = None
    call_py = None
    logging.error("STRING_SESSION bulunamadı, sese katılamayacak!")

chat_sessions = {}

def get_ai_response(chat_id: int, prompt: str) -> str:
    """Gemini AI kullanarak Türkçe ve insansı yanıt üretir."""
    if not model:
        return "Yapay zeka anahtarım henüz tanımlanmadı."

    system_instruction = (
        "Sen 'Oskar Bot' adında cana yakın, samimi ve bilgili bir sesli asistansın. "
        "Sorulara Türkçe, kısa, öz ve sohbet havasında canlı bir insan gibi cevap ver. "
        "Yazım işaretlerini karmaşıklaştırma çünkü cevabın sese dönüştürülecek."
    )

    try:
        if chat_id not in chat_sessions:
            chat_sessions[chat_id] = model.start_chat(history=[])
        
        full_prompt = f"{system_instruction}\n\nKullanıcı: {prompt}"
        response = chat_sessions[chat_id].send_message(full_prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini hatası: {e}")
        return "Üzgünüm, şu an bilgiye ulaşamadım."

def text_to_speech(text: str, filename: str = "response.mp3"):
    """Metni Türkçe ses dosyasına dönüştürür."""
    tts = gTTS(text=text, lang="tr")
    tts.save(filename)
    return filename

@app.on_message(filters.command(["start", "yardim"]))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        "👋 **Merhaba! Ben Oskar Voice AI Bot.**\n\n"
        "🎙️ Sesli sohbete katılmak için: `/katil`\n"
        "🚪 Sesli sohbetten ayrılmak için: `/ayril`\n"
        "🗣️ Benimle konuşmak için mesajınızda **'oskar bot'** deyin!\n"
        "🤫 Beni susturmak için: **'sus'** yazın."
    )

@app.on_message(filters.command("katil"))
async def join_vc(client: Client, message: Message):
    if not call_py:
        return await message.reply_text("❌ STRING_SESSION yok. Sesli sohbete katılamam.")
    
    chat_id = message.chat.id
    if user_app:
        try:
            await user_app.get_chat(chat_id)
        except Exception:
            pass
    try:
        # Önce boş ses dosyası çalarak gruba girelim
        await call_py.play(
            chat_id,
            MediaStream("blank.mp3") if os.path.exists("blank.mp3") else None
        )
        await message.reply_text("🎙️ Sesli sohbete katıldım! 'oskar bot' diyerek benimle konuşabilirsiniz.")
    except Exception as e:
        await message.reply_text(f"❌ Sesli sohbete katılırken hata oluştu: {e}")

@app.on_message(filters.command("ayril"))
async def leave_vc(client: Client, message: Message):
    if not call_py:
        return
    chat_id = message.chat.id
    try:
        await call_py.leave_call(chat_id)
        await message.reply_text("👋 Sesli sohbetten ayrıldım.")
    except Exception as e:
        await message.reply_text(f"❌ Ayrılırken hata: {e}")

@app.on_message(filters.text & ~filters.private)
async def handle_voice_ai(client: Client, message: Message):
    text = message.text.lower().strip()
    chat_id = message.chat.id
    
    if user_app:
        try:
            await user_app.get_chat(chat_id)
        except Exception:
            pass

    if text == "sus":
        if call_py:
            try:
                await call_py.leave_call(chat_id)
                await message.reply_text("🤫 Tamam, sustum!")
            except Exception:
                pass
        return

    if "oskar bot" in text or "oskar" in text:
        prompt = text.replace("oskar bot", "").replace("oskar", "").strip()
        if not prompt:
            prompt = "Efendim! Nasıl yardımcı olabilirim?"

        reply_msg = await message.reply_text("🎙️ Düşünüyorum ve yanıtlıyorum...")

        ai_reply = get_ai_response(chat_id, prompt)
        audio_file = text_to_speech(ai_reply, f"speech_{chat_id}.mp3")

        if call_py:
            try:
                await call_py.play(
                    chat_id,
                    MediaStream(audio_file)
                )
                await reply_msg.edit_text(f"🗣️ **Oskar:** {ai_reply}")
            except Exception:
                try:
                    await call_py.play(
                        chat_id,
                        MediaStream(audio_file)
                    )
                    await reply_msg.edit_text(f"🗣️ **Oskar:** {ai_reply}")
                except Exception as join_err:
                    await reply_msg.edit_text(f"❌ Seste yayınlanamadı: {join_err}\n\n**Oskar:** {ai_reply}")
        else:
            await reply_msg.edit_text(f"🗣️ **Oskar:** {ai_reply}\n\n*(Sesli sohbete katılamıyorum çünkü userbot aktif değil)*")

async def main():
    await app.start()
    if user_app:
        await user_app.start()
        await call_py.start()
    logging.info("Oskar Voice AI Bot çalışıyor...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
