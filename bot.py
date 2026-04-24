# -*- coding: utf-8 -*-
import os
import logging
import asyncio
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes, TypeHandler
from telegram.error import Conflict
import aiosqlite
from http.server import HTTPServer, BaseHTTPRequestHandler

# ========= কনফিগারেশন =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "demo_chanel12")
CHANNEL_INVITE_LINK = f"https://t.me/{CHANNEL_USERNAME}"
IS_RENDER = os.getenv("RENDER") == "true"  # Render automatically sets this

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

# ডামি HTTP সার্ভার (শুধু Render-এর জন্য পোর্ট খোলা রাখতে)
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# ডাটাবেস ফাংশন (আগের মতো)
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

# কীবোর্ড
def main_menu_keyboard():
    buttons = [
        [KeyboardButton("💰 Balance"), KeyboardButton("👤 Profile")],
        [KeyboardButton("➕ Add Money")],
        [KeyboardButton("📱 TikTok"), KeyboardButton("▶️ YouTube")],
        [KeyboardButton("📘 Facebook"), KeyboardButton("📸 Instagram")]
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

# হ্যান্ডলার (আগের মতোই, সংক্ষেপে লিখছি)
async def start(update, context):
    user = update.effective_user
    await create_user(user.id, user.username, user.full_name)
    db_user = await get_user(user.id)
    if db_user and db_user["joined_channel"]:
        await update.message.reply_text(f"স্বাগতম {user.first_name}!", reply_markup=main_menu_keyboard())
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 চ্যানেল জয়েন করুন", url=CHANNEL_INVITE_LINK)],
        [InlineKeyboardButton("✅ ভেরিফাই করুন", callback_data="verify_join")]
    ])
    await update.message.reply_text(f"🚫 অ্যাক্সেস denied!\n\nচ্যানেল জয়েন করুন: {CHANNEL_INVITE_LINK}", reply_markup=kb)

async def verify(update, context):
    q = update.callback_query
    await q.answer()
    if await is_user_member(q.from_user.id, context):
        await set_joined(q.from_user.id, True)
        await q.edit_message_text("✅ ভেরিফিকেশন সফল!", reply_markup=main_menu_keyboard())
    else:
        await q.edit_message_text(f"❌ জয়েন করেননি: {CHANNEL_INVITE_LINK}", reply_markup=q.message.reply_markup)

async def balance_command(update, context):
    user = await get_user(update.effective_user.id)
    await update.message.reply_text(f"💰 ব্যালেন্স: {user['balance']:.2f} TK" if user else "ত্রুটি", reply_markup=main_menu_keyboard())
async def profile_command(update, context):
    user = await get_user(update.effective_user.id)
    if user:
        txt = f"👤 প্রোফাইল\n🆔 {user['user_id']}\nনাম: {user['full_name']}\nব্যালেন্স: {user['balance']:.2f} TK\n✅ ভেরিফাই: {'হ্যাঁ' if user['joined_channel'] else 'না'}"
        await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("ত্রুটি", reply_markup=main_menu_keyboard())
async def add_money_info_command(update, context):
    await update.message.reply_text("💸 টাকা যোগ করতে অ্যাডমিন /addmoney ব্যবহার করুন।", reply_markup=main_menu_keyboard())
async def admin_add_money(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("অনুমতি নেই")
        return
    try:
        uid = int(context.args[0]); amt = float(context.args[1])
        nb = await update_balance(uid, amt)
        await update.message.reply_text(f"✅ {amt} TK যোগ হয়েছে {uid} নং ইউজারে। নতুন ব্যালেন্স: {nb:.2f} TK")
        try: await context.bot.send_message(uid, f"আপনার অ্যাকাউন্টে {amt} TK যোগ হয়েছে। ব্যালেন্স: {nb:.2f} TK")
        except: pass
    except: await update.message.reply_text("/addmoney user_id amount")
async def menu_tiktok(update, context):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❤️ Likes", callback_data="buy_tiktok_likes"), InlineKeyboardButton("👁️ Views", callback_data="buy_tiktok_views")],[InlineKeyboardButton("🔁 Shares", callback_data="buy_tiktok_shares")],[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]])
    await update.message.reply_text("📱 টিকটক সেবা:", reply_markup=kb)
async def menu_youtube(update, context):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Subscribers", callback_data="buy_youtube_subs"), InlineKeyboardButton("👁️ Views", callback_data="buy_youtube_views")],[InlineKeyboardButton("👍 Likes", callback_data="buy_youtube_likes")],[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]])
    await update.message.reply_text("▶️ ইউটিউব সেবা:", reply_markup=kb)
async def menu_instagram(update, context):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👥 Followers", callback_data="buy_instagram_followers"), InlineKeyboardButton("❤️ Likes", callback_data="buy_instagram_likes")],[InlineKeyboardButton("👁️ Views", callback_data="buy_instagram_views")],[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]])
    await update.message.reply_text("📸 ইনস্টাগ্রাম সেবা:", reply_markup=kb)
async def menu_facebook(update, context):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("👍 Followers", callback_data="buy_facebook_followers"), InlineKeyboardButton("😊 Reacts", callback_data="buy_facebook_reacts")],[InlineKeyboardButton("◀️ Back", callback_data="main_menu")]])
    await update.message.reply_text("📘 ফেসবুক সেবা:", reply_markup=kb)
async def back_to_main(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("মূল মেনু", reply_markup=main_menu_keyboard())
    await query.message.delete()

# ক্রয় কনভারসেশন (আগের মতো, সংক্ষেপে)
async def start_purchase(update, context):
    q = update.callback_query; await q.answer()
    context.user_data['product'] = q.data
    await q.edit_message_text("লিংক পাঠান:"); return GET_LINK
async def get_link(update, context):
    context.user_data['link'] = update.message.text
    prod = context.user_data['product'].replace("buy_", "")
    info = PRICES.get(prod)
    if not info: await update.message.reply_text("ত্রুটি"); return ConversationHandler.END
    context.user_data['price_info'] = info
    await update.message.reply_text(f"সংখ্যা দিন (ন্যূনতম {info['min']}):"); return GET_QUANTITY
async def get_quantity(update, context):
    try:
        qty = int(update.message.text); info = context.user_data['price_info']
        if qty < info['min']: await update.message.reply_text(f"ন্যূনতম {info['min']} দিন"); return GET_QUANTITY
        cost = qty * info['price']; context.user_data['qty'] = qty; context.user_data['cost'] = cost
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ হ্যাঁ", callback_data="confirm_yes"), InlineKeyboardButton("❌ না", callback_data="confirm_no")]])
        await update.message.reply_text(f"অর্ডার: {qty} {info['unit']}\nমোট: {cost:.2f} TK\nনিশ্চিত?", reply_markup=kb); return CONFIRM
    except: await update.message.reply_text("শুধু সংখ্যা দিন"); return GET_QUANTITY
async def confirm_purchase(update, context):
    q = update.callback_query; await q.answer()
    if q.data == "confirm_no": await q.edit_message_text("বাতিল", reply_markup=main_menu_keyboard()); return ConversationHandler.END
    user_id = q.from_user.id; user = await get_user(user_id); cost = context.user_data['cost']
    if user['balance'] < cost: await q.edit_message_text("ব্যালেন্স কম"); return ConversationHandler.END
    nb = await update_balance(user_id, -cost)
    await add_order(user_id, context.user_data['product'].replace("buy_",""), context.user_data['link'], context.user_data['qty'], cost)
    await q.edit_message_text(f"✅ ক্রয় সফল! খরচ: {cost:.2f} TK, বাকি: {nb:.2f} TK", reply_markup=main_menu_keyboard()); return ConversationHandler.END
async def cancel(update, context): await update.message.reply_text("বাতিল", reply_markup=main_menu_keyboard()); return ConversationHandler.END

# মেইন ফাংশন
def main():
    if not BOT_TOKEN or not ADMIN_ID:
        raise Exception("BOT_TOKEN, ADMIN_ID environment variables required")
    asyncio.run(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addmoney", admin_add_money))
    app.add_handler(CallbackQueryHandler(verify, pattern="^verify_join$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^main_menu$"))
    app.add_handler(MessageHandler(filters.Regex('^💰 Balance$'), balance_command))
    app.add_handler(MessageHandler(filters.Regex('^👤 Profile$'), profile_command))
    app.add_handler(MessageHandler(filters.Regex('^➕ Add Money$'), add_money_info_command))
    app.add_handler(MessageHandler(filters.Regex('^📱 TikTok$'), menu_tiktok))
    app.add_handler(MessageHandler(filters.Regex('^▶️ YouTube$'), menu_youtube))
    app.add_handler(MessageHandler(filters.Regex('^📘 Facebook$'), menu_facebook))
    app.add_handler(MessageHandler(filters.Regex('^📸 Instagram$'), menu_instagram))
    conv = ConversationHandler(entry_points=[CallbackQueryHandler(start_purchase, pattern="^buy_")], states={GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link)], GET_QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quantity)], CONFIRM: [CallbackQueryHandler(confirm_purchase, pattern="^(confirm_yes|confirm_no)$")]}, fallbacks=[CommandHandler("cancel", cancel)])
    app.add_handler(conv)

    # ডামি HTTP সার্ভার চালু (শুধু Render-এর জন্য)
    if IS_RENDER:
        threading.Thread(target=run_dummy_server, daemon=True).start()
        print("Dummy HTTP server started on port", os.environ.get("PORT", 10000))
        # Webhook সেট করতে চাইলে নিচের অংশ আনকমেন্ট করুন এবং আপনার Render URL দিন
        # webhook_url = "https://smm-boy.onrender.com"
        # asyncio.run(app.bot.set_webhook(webhook_url))
        # app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
        # কিন্তু সহজ উপায়: Polling চালাবেন, কিন্তু ডামি সার্ভার থাকায় Render খুশি থাকবে
        print("Starting polling (with dummy HTTP server to satisfy Render)...")
    else:
        print("Starting polling on Termux...")
    app.run_polling()

if __name__ == "__main__":
    main()
