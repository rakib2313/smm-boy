# -*- coding: utf-8 -*-
import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import aiosqlite

# ========= কনফিগারেশন (এনভায়রনমেন্ট ভেরিয়েবল থেকে) =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "demo_chanel12")
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
logging.basicConfig(level=logging.INFO)
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
            if r: return {"user_id": r[0], "username": r[1], "full_name": r[2], "balance": r[3], "joined_channel": r[4], "join_date": r[5]}
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

# =============== রিপ্লাই কিবোর্ড মেনু (নিচের দিকে থাকবে) ===============
def main_menu_keyboard():
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("👤 Profile")],
        [KeyboardButton("➕ Add Money")],
        [KeyboardButton("📱 TikTok"), KeyboardButton("▶️ YouTube")],
        [KeyboardButton("📘 Facebook"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

# =============== হ্যান্ডলার ===============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await create_user(user.id, user.username, user.full_name)
    db_user = await get_user(user.id)
    if db_user and db_user["joined_channel"]:
        await update.message.reply_text(f"স্বাগতম {user.first_name}! নিচের মেনু ব্যবহার করুন:", reply_markup=main_menu_keyboard())
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 চ্যানেল জয়েন করুন", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")]
    ])
    await update.message.reply_text(f"🚫 অ্যাক্সেস denied!\n\nচ্যানেল জয়েন করুন: {CHANNEL_INVITE_LINK}\nজয়েন করে ভেরিফাই বাটন চাপুন।", reply_markup=kb)

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await is_user_member(q.from_user.id, context):
        await set_joined(q.from_user.id, True)
        await q.edit_message_text("✅ ভেরিফিকেশন সফল! নিচের মেনু ব্যবহার করুন:", reply_markup=main_menu_keyboard())
    else:
        await q.edit_message_text(f"❌ আপনি এখনো চ্যানেল জয়েন করেননি। লিংক: {CHANNEL_INVITE_LINK}", reply_markup=q.message.reply_markup)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(f"💰 আপনার ব্যালেন্স: {user['balance']:.2f} TK", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("ত্রুটি!", reply_markup=main_menu_keyboard())

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    if user:
        txt = f"👤 প্রোফাইল\n🆔 আইডি: `{user['user_id']}`\nনাম: {user['full_name']}\nব্যালেন্স: {user['balance']:.2f} TK\n✅ চ্যানেল ভেরিফাই: {'হ্যাঁ' if user['joined_channel'] else 'না'}"
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("ত্রুটি!", reply_markup=main_menu_keyboard())

async def add_money_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = "💸 টাকা যোগ করতে অ্যাডমিনের সাথে যোগাযোগ করুন। অ্যাডমিন কমান্ড: `/addmoney <user_id> <amount>`\nউদাহরণ: `/addmoney 6792180455 100`"
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def admin_add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("অনুমতি নেই")
        return
    try:
        uid = int(context.args[0]); amt = float(context.args[1])
        nb = await update_balance(uid, amt)
        await update.message.reply_text(f"✅ {amt} TK যোগ হয়েছে {uid} নং ইউজারে। নতুন ব্যালেন্স: {nb:.2f} TK")
        try:
            await context.bot.send_message(uid, f"আপনার অ্যাকাউন্টে {amt} TK যোগ হয়েছে। ব্যালেন্স: {nb:.2f} TK")
        except: pass
    except:
        await update.message.reply_text("সঠিক ব্যবহার: /addmoney user_id amount")

async def menu_tiktok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❤️ Buy Likes", callback_data="buy_tiktok_likes"), InlineKeyboardButton("👁️ Buy Views", callback_data="buy_tiktok_views")],
        [InlineKeyboardButton("🔁 Buy Shares", callback_data="buy_tiktok_shares")],
        [InlineKeyboardButton("◀️ Back to Main", callback_data="main_menu")]
    ])
    await update.message.reply_text("📱 টিকটক সেবা বেছে নিন:", reply_markup=kb)

async def menu_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Buy Subscribers", callback_data="buy_youtube_subs"), InlineKeyboardButton("👁️ Buy Views", callback_data="buy_youtube_views")],
        [InlineKeyboardButton("👍 Buy Likes", callback_data="buy_youtube_likes")],
        [InlineKeyboardButton("◀️ Back to Main", callback_data="main_menu")]
    ])
    await update.message.reply_text("▶️ ইউটিউব সেবা বেছে নিন:", reply_markup=kb)

async def menu_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Buy Followers", callback_data="buy_instagram_followers"), InlineKeyboardButton("❤️ Buy Likes", callback_data="buy_instagram_likes")],
        [InlineKeyboardButton("👁️ Buy Views", callback_data="buy_instagram_views")],
        [InlineKeyboardButton("◀️ Back to Main", callback_data="main_menu")]
    ])
    await update.message.reply_text("📸 ইনস্টাগ্রাম সেবা বেছে নিন:", reply_markup=kb)

async def menu_facebook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍 Buy Followers", callback_data="buy_facebook_followers"), InlineKeyboardButton("😊 Buy Reacts", callback_data="buy_facebook_reacts")],
        [InlineKeyboardButton("◀️ Back to Main", callback_data="main_menu")]
    ])
    await update.message.reply_text("📘 ফেসবুক সেবা বেছে নিন:", reply_markup=kb)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("মূল মেনু:", reply_markup=main_menu_keyboard())
    await query.message.delete()

# ক্রয় কনভারসেশন (ইনলাইন কিবোর্ডের জন্য থাকছে)
async def start_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['product'] = query.data
    await query.edit_message_text("📎 লিংক পাঠান (যে পোস্ট/ভিডিওতে এনগেজমেন্ট চান):\nবাতিল করতে /cancel লিখুন।")
    return GET_LINK
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['link'] = update.message.text
    prod = context.user_data['product'].replace("buy_", "")
    info = PRICES.get(prod)
    if not info:
        await update.message.reply_text("ত্রুটি, মেনু থেকে শুরু করুন", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    context.user_data['price_info'] = info
    await update.message.reply_text(f"🔢 সংখ্যা দিন (ন্যূনতম {info['min']} {info['unit']}, প্রতি ইউনিট {info['price']} TK):")
    return GET_QUANTITY
async def get_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
        info = context.user_data['price_info']
        if qty < info['min']:
            await update.message.reply_text(f"ন্যূনতম {info['min']} দিন। আবার সংখ্যা দিন:")
            return GET_QUANTITY
        cost = qty * info['price']
        context.user_data['qty'] = qty
        context.user_data['cost'] = cost
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_yes"), InlineKeyboardButton("❌ না", callback_data="confirm_no")]])
        await update.message.reply_text(f"📝 অর্ডার: {qty} {info['unit']}\n💸 মোট খরচ: {cost:.2f} TK\nনিশ্চিত?", reply_markup=kb)
        return CONFIRM
    except:
        await update.message.reply_text("শুধু সংখ্যা দিন (যেমন 100):")
        return GET_QUANTITY
async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_no":
        await query.edit_message_text("❌ অর্ডার বাতিল করা হয়েছে।", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    user_id = query.from_user.id
    user = await get_user(user_id)
    cost = context.user_data['cost']
    if user['balance'] < cost:
        await query.edit_message_text("❌ পর্যাপ্ত ব্যালেন্স নেই। টাকা যোগ করুন।", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    nb = await update_balance(user_id, -cost)
    await add_order(user_id, context.user_data['product'].replace("buy_",""), context.user_data['link'], context.user_data['qty'], cost)
    await query.edit_message_text(f"✅ ক্রয় সফল!\nখরচ: {cost:.2f} TK\nঅবশিষ্ট ব্যালেন্স: {nb:.2f} TK", reply_markup=main_menu_keyboard())
    return ConversationHandler.END
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 ক্রয় বাতিল।", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

def main():
    if not BOT_TOKEN or not ADMIN_ID:
        raise Exception("BOT_TOKEN, ADMIN_ID environment variables required")
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addmoney", admin_add_money))
    app.add_handler(CallbackQueryHandler(verify, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^main_menu$"))
    
    # রিপ্লাই কিবোর্ডের বাটন হ্যান্ডলার
    app.add_handler(MessageHandler(filters.Regex('^💰 Balance$'), balance_command))
    app.add_handler(MessageHandler(filters.Regex('^👤 Profile$'), profile_command))
    app.add_handler(MessageHandler(filters.Regex('^➕ Add Money$'), add_money_info_command))
    app.add_handler(MessageHandler(filters.Regex('^📱 TikTok$'), menu_tiktok))
    app.add_handler(MessageHandler(filters.Regex('^▶️ YouTube$'), menu_youtube))
    app.add_handler(MessageHandler(filters.Regex('^📘 Facebook$'), menu_facebook))
    app.add_handler(MessageHandler(filters.Regex('^📸 Instagram$'), menu_instagram))
    
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_purchase, pattern="^buy_")],
        states={
            GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)],
            GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quantity)],
            CONFIRM: [CallbackQueryHandler(confirm_purchase, pattern="^(confirm_yes|confirm_no)$")],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    app.add_handler(conv)
    print("✅ বট চালু হয়েছে। মেনু নিচের দিকে ReplyKeyboard আকারে দেখা যাবে।")
    app.run_polling()

if __name__ == "__main__":
    main()
