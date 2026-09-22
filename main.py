import os
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality
from gtts import gTTS
import google.generativeai as genai

# Çevresel değişkenleri yükle
load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION = os.getenv("STRING_SESSION", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")

# Gemini AI Ayarları
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
chat_sessions = {} # Grup hafızası için

# Pyrogram İstemcileri
app = Client("oscar_voice_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_app = Client("oscar_voice_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION) if SESSION else None
call_py = PyTgCalls(user_app) if user_app else None

def get_ai_response(chat_id, prompt):
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = model.start_chat(history=[
            {"role": "user", "parts": "Senin adın Oscar. Kısa, öz ve doğal konuşan bir sesli asistan gibi cevap ver. Destan yazma, en fazla 2-3 cümle kullan. İnsan gibi konuş."},
            {"role": "model", "parts": "Tamam, ben Oscar. Size nasıl yardımcı olabilirim?"}
        ])
    
    response = chat_sessions[chat_id].send_message(prompt)
    return response.text

async def play_tts(chat_id, text):
    if not call_py:
        return
    
    # Metni sese çevir (gTTS)
    tts = gTTS(text=text, lang='tr')
    audio_file = f"response_{chat_id}.mp3"
    tts.save(audio_file)
    
    # Sesi sohbette çal
    try:
        await call_py.play(
            chat_id,
            MediaStream(
                audio_file,
                AudioQuality.HIGH
            )
        )
    except Exception as e:
        print(f"Oynatma hatası: {e}")

@app.on_message(filters.command("seskat"))
async def join_vc(client, message):
    if not call_py:
        await message.reply("⚠️ Asistan hesabı (STRING_SESSION) ayarlanmamış!")
        return
    
    try:
        await call_py.join_group_call(message.chat.id, MediaStream("silence.mp3")) # Başlangıçta sessizlik çalabilir veya hazırda bekler
        await message.reply("🎙️ Sesli sohbete katıldım! 'oskar bot [soru]' yazarak benimle konuşabilirsiniz.")
    except Exception as e:
        await message.reply(f"❌ Katılamadım: {e}")

@app.on_message(filters.command("sesayril"))
async def leave_vc(client, message):
    if call_py:
        try:
            await call_py.leave_group_call(message.chat.id)
            await message.reply("👋 Sesli sohbetten ayrıldım.")
        except:
            pass

@app.on_message(filters.text & filters.group)
async def handle_text(client, message):
    text = message.text.lower()
    chat_id = message.chat.id
    
    if text == "sus":
        if call_py:
            try:
                await call_py.pause_stream(chat_id)
                await message.reply("🤫 Sustum.")
            except:
                pass
        return
        
    if text.startswith("oskar bot"):
        prompt = message.text[9:].strip()
        if not prompt:
            await message.reply("Efendim? Beni dinliyorum, bir şey mi sordunuz?")
            return
            
        wait_msg = await message.reply("🤔 Düşünüyorum...")
        try:
            # AI'dan cevap al
            cevap = get_ai_response(chat_id, prompt)
            await wait_msg.edit_text(f"🗣️ **Oscar:** {cevap}")
            
            # Sesi çal
            await play_tts(chat_id, cevap)
            
        except Exception as e:
            await wait_msg.edit_text(f"❌ Bir hata oluştu: {e}")

@app.on_message(filters.command("sifirla"))
async def reset_memory(client, message):
    chat_id = message.chat.id
    if chat_id in chat_sessions:
        del chat_sessions[chat_id]
        await message.reply("🧠 Hafızamı sildim. Artık yeni bir başlangıç yapabiliriz!")
    else:
        await message.reply("Zaten bu grup için bir hafızam yoktu.")

async def main():
    await app.start()
    if user_app and call_py:
        await user_app.start()
        await call_py.start()
    print("🤖 Oscar Sesli AI Bot Başladı!")
    await idle()

if __name__ == "__main__":
    # Gerekli sessizlik dosyasını oluştur (PyTgCalls ilk katılım için bir dosya isteyebilir)
    if not os.path.exists("silence.mp3"):
        tts = gTTS("Merhaba, ben geldim.", lang='tr')
        tts.save("silence.mp3")
        
    asyncio.run(main())
