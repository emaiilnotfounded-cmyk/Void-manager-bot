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
welcome_col = db["welcome"]
warns_col = db["warns"]

# ================= MEMORY =================
user_messages = defaultdict(list)
captcha_users = {}

# ================= AI WORD LIST =================
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
        [InlineKeyboardButton("📚 Help", callback_data="help")],
        [InlineKeyboardButton("🌐 VOID COMMUNITY", callback_data="community")]
    ]

    text = """Hey there! My name is MANAGER VOID - I'm here to help you manage your groups.

Use /help to explore features.

Join:
Link 1: https://t.me/pwchatcommunityx1
Link 2: https://t.me/voidcommuio

Add me to group for full power."""

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= HELP UI =================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        keyboard = [
            [InlineKeyboardButton("🔇 Mute", callback_data="help_mute")],
            [InlineKeyboardButton("🔨 Ban", callback_data="help_ban")],
            [InlineKeyboardButton("🚫 BanWords", callback_data="help_banwords")],
            [InlineKeyboardButton("⚡ Anti Flood", callback_data="help_flood")],
            [InlineKeyboardButton("🛡 Anti Raid", callback_data="help_raid")],
            [InlineKeyboardButton("🎉 Welcome", callback_data="help_welcome")],
            [InlineKeyboardButton("⬅ Back", callback_data="start")]
        ]
        await query.edit_message_text("Choose category:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "help_mute":
        await back(query,
"""🔇 MUTE COMMANDS

1. /muteusername <username> - mute user with username  
2. /mute (reply) - mute user using message""")

    elif query.data == "help_ban":
        await back(query,
"""🔨 BAN COMMANDS

1. /banusername <username> - ban user  
2. /ban (reply) - ban via message""")

    elif query.data == "help_banwords":
        await back(query,
"""🚫 BANWORDS

1. /addbanword <word>  
2. /removebanword <word>  
3. /listbanwords""")

    elif query.data == "help_flood":
        await back(query,
"""⚡ ANTI FLOOD

5 msgs / 5 sec = warn  
3 warns = ban""")

    elif query.data == "help_raid":
        await back(query,
"""🛡 ANTI RAID

Spam activity = instant ban""")

    elif query.data == "help_welcome":
        await back(query,
"""🎉 WELCOME

/setwelcome <msg>  
Reply photo + /setwelcome  

Variables:
{first_name} {id} {username}""")

    elif query.data == "community":
        keyboard = [
            [InlineKeyboardButton("CHAT GROUP 1", url="https://t.me/pwchatcommunityx1")],
            [InlineKeyboardButton("CHAT COMMUNITY 2", url="https://t.me/voidcommuio")],
            [InlineKeyboardButton("⬅ Back", callback_data="start")]
        ]
        await query.edit_message_text("Join:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("approve_") or query.data.startswith("reject_"):
        user_id = int(query.data.split("_")[1])

        admins = await context.bot.get_chat_administrators(query.message.chat.id)
        if query.from_user.id not in [a.user.id for a in admins]:
            return await query.answer("Admins only ❌", show_alert=True)

        if query.data.startswith("approve_"):
            await context.bot.approve_chat_join_request(query.message.chat.id, user_id)
            await query.edit_message_text("Approved ✅")
        else:
            await context.bot.decline_chat_join_request(query.message.chat.id, user_id)
            await query.edit_message_text("Rejected ❌")

    elif query.data.startswith("verify_"):
        uid = int(query.data.split("_")[1])

        if query.from_user.id != uid:
            return await query.answer("Not for you ❌", show_alert=True)

        await context.bot.restrict_chat_member(
            query.message.chat.id,
            uid,
            permissions=ChatPermissions(can_send_messages=True)
        )
        captcha_users.pop(uid, None)
        await query.edit_message_text("Verified ✅")

    elif query.data == "start":
        await start(update, context)

async def back(query, text):
    keyboard = [[InlineKeyboardButton("⬅ Back", callback_data="help")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================= ID =================
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        u = update.message.reply_to_message.from_user
        return await update.message.reply_text(f"{u.first_name}\nID: {u.id}\n@{u.username}")

    if context.args:
        uid = get_user_id(context.args[0].replace("@", ""))
        return await update.message.reply_text(str(uid) if uid else "Not found")

    await update.message.reply_text(f"Your ID: {update.effective_user.id}")

# ================= MUTE =================
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        await context.bot.restrict_chat_member(update.effective_chat.id, uid, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text("Muted 🔇")

async def mute_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    uid = get_user_id(context.args[0].replace("@", "")) if context.args else None
    if uid:
        await context.bot.restrict_chat_member(update.effective_chat.id, uid, permissions=ChatPermissions(can_send_messages=False))
        await update.message.reply_text("Muted 🔇")
    else:
        await update.message.reply_text("User not found")

# ================= BAN =================
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    if update.message.reply_to_message:
        uid = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("Banned 🔨")

async def ban_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    uid = get_user_id(context.args[0].replace("@", "")) if context.args else None
    if uid:
        await context.bot.ban_chat_member(update.effective_chat.id, uid)
        await update.message.reply_text("Banned 🔨")
    else:
        await update.message.reply_text("User not found")

# ================= BANWORDS =================
async def add_banword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")
    banwords_col.update_one({"word": context.args[0]}, {"$set": {"word": context.args[0]}}, upsert=True)
    await update.message.reply_text("Added")

async def remove_banword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")
    banwords_col.delete_one({"word": context.args[0]})
    await update.message.reply_text("Removed")

async def list_banwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = [w["word"] for w in banwords_col.find()]
    await update.message.reply_text("\n".join(words) or "No words")

# ================= WELCOME =================
async def set_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return await update.message.reply_text("Admins only")

    chat_id = update.effective_chat.id

    if update.message.reply_to_message and update.message.reply_to_message.photo:
        photo = update.message.reply_to_message.photo[-1].file_id
        caption = " ".join(context.args)
        welcome_col.update_one({"chat_id": chat_id}, {"$set": {"photo": photo, "caption": caption}}, upsert=True)
        return await update.message.reply_text("Photo welcome set")

    if context.args:
        caption = " ".join(context.args)
        welcome_col.update_one({"chat_id": chat_id}, {"$set": {"photo": None, "caption": caption}}, upsert=True)
        return await update.message.reply_text("Text welcome set")

# ================= CAPTCHA JOIN =================
async def captcha_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        uid = m.id

        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            uid,
            permissions=ChatPermissions(can_send_messages=False)
        )

        captcha_users[uid] = time.time()

        keyboard = [[InlineKeyboardButton("✅ I AM HUMAN", callback_data=f"verify_{uid}")]]
        await update.message.reply_text(f"{m.first_name}, verify within 60 sec", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= CAPTCHA CHECK =================
async def captcha_checker(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    for uid, t in list(captcha_users.items()):
        if now - t > 60:
            try:
                await context.bot.ban_chat_member(context.job.chat_id, uid)
                captcha_users.pop(uid)
            except:
                pass

# ================= JOIN REQUEST =================
async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = update.chat_join_request
    keyboard = [[
        InlineKeyboardButton("✅ Accept", callback_data=f"approve_{r.from_user.id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{r.from_user.id}")
    ]]
    await context.bot.send_message(r.chat.id, f"Join request: {r.from_user.first_name}", reply_markup=InlineKeyboardMarkup(keyboard))

# ================= WARN SYSTEM =================
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
        await warn_user(update.effective_chat.id, update.message.reply_to_message.from_user.id, context)

# ================= AI MODERATION =================
async def ai_moderation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    save_user(user)
    text = update.message.text.lower()
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

    if len(user_messages[uid]) > 5:
        await warn_user(update.effective_chat.id, uid, context)

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("warn", warn))

    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("muteusername", mute_username))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("banusername", ban_username))

    app.add_handler(CommandHandler("addbanword", add_banword))
    app.add_handler(CommandHandler("removebanword", remove_banword))
    app.add_handler(CommandHandler("listbanwords", list_banwords))
    app.add_handler(CommandHandler("setwelcome", set_welcome))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, captcha_join))
    app.add_handler(MessageHandler(filters.ChatJoinRequest(), join_request))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_moderation))

    app.job_queue.run_repeating(captcha_checker, interval=30)

    print("🔥 VOID MANAGER GOD MODE RUNNING...")
    app.run_polling()

if __name__ == "__main__":
    main()
