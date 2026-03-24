import os
import time
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from pymongo import MongoClient

# ================= ENV =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

if not MONGO_URL:
    raise ValueError("MONGO_URL not set")

# ================= DB =================
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
users_col = db["users"]
banwords_col = db["banwords"]
warns_col = db["warns"]

# ================= MEMORY =================
user_messages = defaultdict(list)

# ================= ABUSE =================
AI_ABUSE = ["madarchod","bhosdike","chutiya","randi","fuck","shit"]

# ================= ADMIN CHECK =================
async def is_admin(update, context):
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    return update.effective_user.id in [a.user.id for a in admins]

# ================= SAVE USER =================
def save_user(user):
    if user.username:
        users_col.update_one(
            {"username": user.username.lower()},
            {"$set": {"user_id": user.id}},
            upsert=True
        )

def get_user_id(username):
    data = users_col.find_one({"username": username.lower()})
    return data["user_id"] if data else None

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Me", url="https://t.me/yourbot?startgroup=true")],
        [InlineKeyboardButton("📚 Help", callback_data="help")]
    ]

    text = "Hey! I'm VOID Manager Bot 🚀"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= BUTTONS =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.edit_message_text("Use commands:\n/mute\n/ban\n/warn\n/addbanword")

# ================= ID =================
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        return await update.message.reply_text(f"{u.first_name}\nID: {u.id}")

    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

# ================= MUTE =================
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        await context.bot.restrict_chat_member(
            update.effective_chat.id, uid,
            permissions=ChatPermissions(can_send_messages=False)
        )
        await update.message.reply_text("Muted 🔇")

# ================= BAN =================
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("Banned 🔨")

# ================= WARN =================
async def warn_user(chat_id, uid, context):
    warns_col.update_one({"user": uid}, {"$inc": {"warns": 1}}, upsert=True)
    w = warns_col.find_one({"user": uid})["warns"]

    await context.bot.send_message(chat_id, f"⚠️ Warn {w}/3")

    if w >= 3:
        await context.bot.ban_chat_member(chat_id, uid)
        await context.bot.send_message(chat_id, "❌ Banned (3 warns)")

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    if update.message.reply_to_message:
        await warn_user(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id,
            context
        )

# ================= BANWORDS =================
async def add_banword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    banwords_col.update_one(
        {"word": context.args[0]},
        {"$set": {"word": context.args[0]}},
        upsert=True
    )
    await update.message.reply_text("Added")

async def remove_banword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    banwords_col.delete_one({"word": context.args[0]})
    await update.message.reply_text("Removed")

# ================= AI MODERATION =================
async def ai_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    save_user(user)

    text = (update.message.text or "").lower()
    uid = user.id

    for word in AI_ABUSE:
        if word in text:
            await update.message.delete()
            await warn_user(update.effective_chat.id, uid, context)
            return

    for w in [x["word"] for x in banwords_col.find()]:
        if w in text:
            await update.message.delete()
            await warn_user(update.effective_chat.id, uid, context)
            return

    now = time.time()
    user_messages[uid] = [t for t in user_messages[uid] if now - t < 5]
    user_messages[uid].append(now)

    if len(user_messages[uid]) >= 5:
        await warn_user(update.effective_chat.id, uid, context)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("ban", ban))

    app.add_handler(CommandHandler("addbanword", add_banword))
    app.add_handler(CommandHandler("removebanword", remove_banword))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_moderation))

    print("🔥 VOID BOT RUNNING WITHOUT CAPTCHA...")
    app.run_polling()

if __name__ == "__main__":
    main()
