import os
import yt_dlp
import asyncio
from collections import defaultdict, deque
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler,
    ChatJoinRequestHandler
)
from pymongo import MongoClient

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

# ================= DB =================
client = MongoClient(MONGO_URL)
db = client["musicbot"]
welcome_col = db["welcome"]

# ================= QUEUE =================
queues = defaultdict(deque)
now_playing = {}

# ================= YT FETCH =================
async def get_audio(query):
    ydl_opts = {
        'format': 'bestaudio',
        'quiet': True,
        'noplaylist': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        return info['url'], info.get('title', 'Unknown')

# ================= PLAY NEXT =================
async def play_next(chat_id, context):
    if queues[chat_id]:
        query = queues[chat_id].popleft()
        audio_url, title = await get_audio(query)

        now_playing[chat_id] = title

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏸", callback_data="pause"),
                InlineKeyboardButton("⏭", callback_data="skip")
            ],
            [
                InlineKeyboardButton("⏹", callback_data="stop"),
                InlineKeyboardButton("❌", callback_data="close")
            ]
        ])

        await context.bot.send_audio(
            chat_id=chat_id,
            audio=audio_url,
            title=title,
            reply_markup=keyboard
        )
    else:
        now_playing.pop(chat_id, None)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎵 Advanced Music Bot Active!")

# ================= PLAY =================
async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id

    if not context.args:
        await update.message.reply_text("❌ Usage: /play song name or link")
        return

    query = " ".join(context.args)
    queues[chat_id].append(query)

    if chat_id not in now_playing:
        await play_next(chat_id, context)
    else:
        await update.message.reply_text("➕ Added to queue!")

# ================= STOP =================
async def stopmusic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    queues[chat_id].clear()
    now_playing.pop(chat_id, None)
    await update.message.reply_text("⏹ Stopped & queue cleared!")

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    await query.answer()

    if query.data == "skip":
        await query.message.reply_text("⏭ Skipping...")
        await play_next(chat_id, context)

    elif query.data == "stop":
        queues[chat_id].clear()
        now_playing.pop(chat_id, None)
        await query.message.reply_text("⏹ Stopped")

    elif query.data == "close":
        await query.message.delete()

    elif query.data == "pause":
        await query.answer("⏸ Pause not supported in audio mode")

# ================= SET WELCOME =================
async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id

    if not context.args:
        await update.message.reply_text("Usage: /setwelcome text")
        return

    text = " ".join(context.args)
    welcome_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"text": text}},
        upsert=True
    )

    await update.message.reply_text("✅ Welcome saved!")

# ================= WELCOME =================
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    data = welcome_col.find_one({"chat_id": chat_id})

    if data:
        await update.message.reply_text(data["text"])

# ================= JOIN REQUEST =================
async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chat_join_request.from_user
    chat_id = update.chat_join_request.chat.id

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}")
        ]
    ])

    await context.bot.send_message(
        chat_id,
        f"👤 Join Request: {user.first_name}",
        reply_markup=keyboard
    )

# ================= APPROVE / REJECT =================
async def approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    user_id = int(data.split("_")[1])
    chat_id = query.message.chat.id

    if "approve" in data:
        await context.bot.approve_chat_join_request(chat_id, user_id)
        await query.edit_message_text("✅ Approved")
    else:
        await context.bot.decline_chat_join_request(chat_id, user_id)
        await query.edit_message_text("❌ Rejected")

# ================= MAIN =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("play", play))
app.add_handler(CommandHandler("stopmusic", stopmusic))
app.add_handler(CommandHandler("setwelcome", setwelcome))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(ChatJoinRequestHandler(join_request))
app.add_handler(CallbackQueryHandler(approve_reject, pattern="approve|reject"))
app.add_handler(CallbackQueryHandler(buttons))

print("🔥 Advanced Bot Running...")
app.run_polling()
