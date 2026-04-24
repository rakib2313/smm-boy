# -*- coding: utf-8 -*-
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import aiosqlite

BOT_TOKEN = "8789633562:AAGPH8EPQn399zE7iyPZohm8zWmUgD5jL0A"
ADMIN_ID = 6792180455

# ★★★ আপনার চ্যানেলের পাবলিক ইউজারনেম বসান (যেমন: "my_channel_name") ★★★
CHANNEL_USERNAME = "demo_chanel12"   # <-- এটা পরিবর্তন করুন
CHANNEL_INVITE_LINK = f"https://t.me/{CHANNEL_USERNAME}"

PRICES = {
    "tiktok_likes":    {"min": 100, "price": 0.02, "unit": "like"},
    "tiktok_views":    {"min": 100, "price": 0.01, "unit": "view"},
    "tiktok_shares":   {"min": 10,  "price": 0.5,  "unit": "share"},
    "youtube_subs":    {"min": 10,  "price": 1.5,  "unit": "subscriber"},
    "youtube_views":   {"min": 100, "price": 0.005,"unit": "view"},
    "youtube_likes":   {"min": 50,  "price": 0.08, "unit": "like"},
    "instagram_followers":{"min": 50, "price": 0.3, "unit": "follower"},
    "instagram_likes": {"min": 50,  "price": 0.05, "unit": "like"},
    "instagram_views": {"min": 100, "price": 0.02, "unit": "view"},
    "facebook_followers":{"min": 50, "price": 0.25, "unit": "follower"},
    "facebook_reacts": {"min": 50,  "price": 0.1,  "unit": "react"},
}

GET_LINK, GET_QUANTITY, CONFIRM = range(3)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
DB_PATH = "smm_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, balance REAL DEFAULT 0, joined_channel INTEGER DEFAULT 0, join_date TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS orders (order_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT, link TEXT, quantity INTEGER, cost REAL, status TEXT DEFAULT 'completed', timestamp TEXT)''')
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c:
            r = await c.fetchone()
            if r:
                return {"user_id": r[0], "username": r[1], "full_name": r[2], "balance": r[3], "joined_channel": r[4], "join_date": r[5]}
    return None

async def create_user(user_id, username, full_name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)", (user_id, username, full_name, datetime.now().isoformat()))
        await db.commit()

async def set_joined(user_id, joined=True):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET joined_channel = ? WHERE user_id = ?", (1 if joined else 0, user_id))
        await db.commit()

async def update_balance(user_id, delta):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        await db.commit()
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as c:
            row = await c.fetchone()
            return row[0] if row else 0

async def add_order(user_id, service, link, quantity, cost):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO orders (user_id, service, link, quantity, cost, timestamp) VALUES (?, ?, ?, ?, ?, ?)", (user_id, service, link, quantity, cost, datetime.now().isoformat()))
        await db.commit()

async def is_user_member(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"membership check error: {e}")
        return False

def main_menu():
    kb = [[InlineKeyboardButton("💰 Balance", callback_data="balance"), InlineKeyboardButton("👤 Profile", callback_data="profile")],
           [InlineKeyboardButton("➕ Add Money", callback_data="add_money")],
           [InlineKeyboardButton("📱 TikTok", callback_data="menu_tiktok"), InlineKeyboardButton("▶️ YouTube", callback_data="menu_youtube")],
           [InlineKeyboardButton("📘 Facebook", callback_data="menu_facebook"), InlineKeyboardButton("📸 Instagram", callback_data="menu_instagram")]]
    return InlineKeyboardMarkup(kb)

def tiktok_menu():
    kb = [[InlineKeyboardButton("❤️ Likes", callback_data="buy_tiktok_likes"), InlineKeyboardButton("👁️ Views", callback_data="buy_tiktok_views")],
          [InlineKeyboardButton("🔁 Shares", callback_data="buy_tiktok_shares")],
          [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(kb)

def youtube_menu():
    kb = [[InlineKeyboardButton("📢 Subscribers", callback_data="buy_youtube_subs"), InlineKeyboardButton("👁️ Views", callback_data="buy_youtube_views")],
          [InlineKeyboardButton("👍 Likes", callback_data="buy_youtube_likes")],
          [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(kb)

def instagram_menu():
    kb = [[InlineKeyboardButton("👥 Followers", callback_data="buy_instagram_followers"), InlineKeyboardButton("❤️ Likes", callback_data="buy_instagram_likes")],
          [InlineKeyboardButton("👁️ Views", callback_data="buy_instagram_views")],
          [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(kb)

def facebook_menu():
    kb = [[InlineKeyboardButton("👍 Followers", callback_data="buy_facebook_followers"), InlineKeyboardButton("😊 Reacts", callback_data="buy_facebook_reacts")],
          [InlineKeyboardButton("◀️ Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(kb)

def confirm_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes", callback_data="confirm_yes"), InlineKeyboardButton("❌ No", callback_data="confirm_no")]])

async def start(update, context):
    user = update.effective_user
    await create_user(user.id, user.username, user.full_name)
    db_user = await get_user(user.id)
    if db_user and db_user["joined_channel"]:
        await update.message.reply_text(f"স্বাগতম {user.first_name}! নিচের মেনু থেকে বেছে নিন:", reply_markup=main_menu())
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 চ্যানেল জয়েন করুন", url=CHANNEL_INVITE_LINK)],
                               [InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")]])
    await update.message.reply_text(f"🚫 অ্যাক্সেস denied!\n\nআপনাকে আমাদের চ্যানেল জয়েন করতে হবে:\n{CHANNEL_INVITE_LINK}\n\nজয়েন করে ভেরিফাই বাটন চাপুন।", reply_markup=kb)

async def verify(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if await is_user_member(user_id, context):
        await set_joined(user_id, True)
        await q.edit_message_text("✅ ভেরিফিকেশন সফল! আপনি এখন বট ব্যবহার করতে পারেন।", reply_markup=main_menu())
    else:
        await q.edit_message_text(f"❌ আপনি এখনো চ্যানেল জয়েন করেননি। জয়েন করে আবার ভেরিফাই করুন।\nলিংক: {CHANNEL_INVITE_LINK}", reply_markup=q.message.reply_markup)

async def balance(update, context):
    q = update.callback_query
    await q.answer()
    user = await get_user(q.from_user.id)
    if user:
        await q.edit_message_text(f"💰 আপনার ব্যালেন্স: {user['balance']:.2f} TK", reply_markup=main_menu())
    else:
        await q.edit_message_text("ত্রুটি, আবার চেষ্টা করুন", reply_markup=main_menu())

async def profile(update, context):
    q = update.callback_query
    await q.answer()
    user = await get_user(q.from_user.id)
    if user:
        txt = f"👤 প্রোফাইল\n🆔 আইডি: `{user['user_id']}`\nনাম: {user['full_name']}\nব্যালেন্স: {user['balance']:.2f} TK\n✅ভেরিফাইড: {'হ্যাঁ' if user['joined_channel'] else 'না'}"
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu())
    else:
        await q.edit_message_text("প্রোফাইল পাওয়া যায়নি", reply_markup=main_menu())

async def add_money_info(update, context):
    q = update.callback_query
    await q.answer()
    txt = "💸 টাকা যোগ করুন:\nঅ্যাডমিনের সাথে যোগাযোগ করুন। অ্যাডমিন কমান্ড: `/addmoney <user_id> <amount>`\n\nউদাহরণ: `/addmoney 6792180455 100`"
    await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=main_menu())

async def admin_add_money(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("অনুমতি নেই")
        return
    try:
        uid = int(context.args[0])
        amt = float(context.args[1])
        nb = await update_balance(uid, amt)
        await update.message.reply_text(f"✅ {amt} TK যোগ করা হয়েছে {uid} নং ইউজারের অ্যাকাউন্টে। নতুন ব্যালেন্স: {nb:.2f} TK")
        try:
            await context.bot.send_message(uid, f"আপনার অ্যাকাউন্টে {amt} TK যোগ করা হয়েছে। ব্যালেন্স: {nb:.2f} TK")
        except:
            pass
    except:
        await update.message.reply_text("ভুল ফরম্যাট: /addmoney user_id amount")

async def menu_tiktok(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📱 টিকটক সেবা:", reply_markup=tiktok_menu())
async def menu_youtube(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("▶️ ইউটিউব সেবা:", reply_markup=youtube_menu())
async def menu_instagram(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📸 ইনস্টাগ্রাম সেবা:", reply_markup=instagram_menu())
async def menu_facebook(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📘 ফেসবুক সেবা:", reply_markup=facebook_menu())
async def back_main(update, context):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("মূল মেনু", reply_markup=main_menu())

# ক্রয় কনভারসেশন
async def start_purchase(update, context):
    q = update.callback_query
    await q.answer()
    context.user_data['product'] = q.data
    await q.edit_message_text("লিংক পাঠান:")
    return GET_LINK
async def get_link(update, context):
    context.user_data['link'] = update.message.text
    prod = context.user_data['product'].replace("buy_", "")
    info = PRICES.get(prod)
    if not info:
        await update.message.reply_text("ত্রুটি, মেনু থেকে শুরু করুন")
        return ConversationHandler.END
    context.user_data['price_info'] = info
    await update.message.reply_text(f"কত {info['unit']} চান? (ন্যূনতম {info['min']}, প্রতি ইউনিট {info['price']} TK)")
    return GET_QUANTITY
async def get_quantity(update, context):
    try:
        qty = int(update.message.text)
        info = context.user_data['price_info']
        if qty < info['min']:
            await update.message.reply_text(f"ন্যূনতম {info['min']} দিন")
            return GET_QUANTITY
        cost = qty * info['price']
        context.user_data['qty'] = qty
        context.user_data['cost'] = cost
        await update.message.reply_text(f"অর্ডার: {qty} {info['unit']}\nমোট খরচ: {cost:.2f} TK\nনিশ্চিত?", reply_markup=confirm_kb())
        return CONFIRM
    except:
        await update.message.reply_text("একটি সংখ্যা দিন")
        return GET_QUANTITY
async def confirm_purchase(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "confirm_no":
        await q.edit_message_text("❌ বাতিল করা হয়েছে", reply_markup=main_menu())
        return ConversationHandler.END
    user_id = q.from_user.id
    user = await get_user(user_id)
    cost = context.user_data['cost']
    if user['balance'] < cost:
        await q.edit_message_text("❌ ব্যালেন্স কম", reply_markup=main_menu())
        return ConversationHandler.END
    nb = await update_balance(user_id, -cost)
    await add_order(user_id, context.user_data['product'].replace("buy_",""), context.user_data['link'], context.user_data['qty'], cost)
    await q.edit_message_text(f"✅ ক্রয় সফল! খরচ: {cost:.2f} TK, বাকি: {nb:.2f} TK", reply_markup=main_menu())
    return ConversationHandler.END
async def cancel(update, context):
    await update.message.reply_text("বাতিল")

def main():
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addmoney", admin_add_money))
    app.add_handler(CallbackQueryHandler(verify, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(add_money_info, pattern="^add_money$"))
    app.add_handler(CallbackQueryHandler(menu_tiktok, pattern="^menu_tiktok$"))
    app.add_handler(CallbackQueryHandler(menu_youtube, pattern="^menu_youtube$"))
    app.add_handler(CallbackQueryHandler(menu_instagram, pattern="^menu_instagram$"))
    app.add_handler(CallbackQueryHandler(menu_facebook, pattern="^menu_facebook$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^main_menu$"))
    conv = ConversationHandler(entry_points=[CallbackQueryHandler(start_purchase, pattern="^buy_")], states={GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)], GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quantity)], CONFIRM: [CallbackQueryHandler(confirm_purchase, pattern="^(confirm_yes|confirm_no)$")]}, fallbacks=[CommandHandler("cancel", cancel)])
    app.add_handler(conv)
    print(f"✅ বট চালু হয়েছে। চ্যানেল: @{CHANNEL_USERNAME}")
    app.run_polling()

if __name__ == "__main__":
    main()
