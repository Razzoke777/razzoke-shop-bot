import asyncio
import os
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "7579990560").split(",") if x.strip()}
REQUIRED_CHANNELS = [x.strip() for x in os.getenv("REQUIRED_CHANNELS", "@Razzoke_eFootball,@RazzokeShop").split(",") if x.strip()]
PUBLIC_CHANNEL = os.getenv("PUBLIC_CHANNEL", "@RazzokeShop")
DB_PATH = os.getenv("DB_PATH", "razzoke.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            photo_id TEXT,
            price TEXT,
            google_play TEXT,
            game_center TEXT,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )""")

class Sell(StatesGroup):
    photo = State()
    price = State()
    google = State()
    gamecenter = State()
    description = State()
    confirm = State()

class Buy(StatesGroup):
    budget = State()
    description = State()
    note = State()
    confirm = State()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Akkaunt sotish"), KeyboardButton(text="🔵 Akkaunt sotib olish")],
            [KeyboardButton(text="📋 Mening e'lonlarim"), KeyboardButton(text="ℹ️ Yordam")]
        ], resize_keyboard=True
    )

def join_kb():
    rows = [[InlineKeyboardButton(text=f"➕ {ch} kanaliga a'zo bo'lish", url=f"https://t.me/{ch.lstrip('@')}")] for ch in REQUIRED_CHANNELS]
    rows.append([InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def joined(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            return False
    return True

async def gate_message(message: Message) -> bool:
    if not await joined(message.from_user.id):
        await message.answer(
            "Botdan foydalanish uchun avval quyidagi kanallarga a'zo bo'ling:",
            reply_markup=join_kb()
        )
        return False
    return True

async def gate_callback(call: CallbackQuery) -> bool:
    if not await joined(call.from_user.id):
        await call.answer("Avval ikkala kanalga ham a'zo bo'ling.", show_alert=True)
        await call.message.answer("A'zolikni tekshiring:", reply_markup=join_kb())
        return False
    return True

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    if not await gate_message(message):
        return
    await message.answer(
        "Assalomu alaykum! <b>RAZZOKE SHOP</b> e'lon botiga xush kelibsiz.\nKerakli bo'limni tanlang:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "check_join")
async def check_join(call: CallbackQuery):
    if await joined(call.from_user.id):
        await call.message.answer("✅ A'zolik tasdiqlandi. Botdan foydalanishingiz mumkin.", reply_markup=main_menu())
        await call.answer("Tasdiqlandi")
    else:
        await call.answer("Ikkala kanalga ham a'zo bo'ling, so'ng qayta tekshiring.", show_alert=True)

@dp.message(F.text == "🟢 Akkaunt sotish")
async def sell_start(message: Message, state: FSMContext):
    if not await gate_message(message): return
    await state.set_state(Sell.photo)
    await message.answer("Akkaunt rasmini yuboring (foto ko'rinishida).")

@dp.message(Sell.photo, F.photo)
async def sell_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(Sell.price)
    await message.answer("Akkaunt narxini so'mda kiriting. Masalan: 250000")

@dp.message(Sell.price)
async def sell_price(message: Message, state: FSMContext):
    price = (message.text or "").strip()
    if not price.isdigit() or int(price) <= 0:
        await message.answer("Narxni faqat raqam bilan kiriting. Masalan: 250000")
        return
    await state.update_data(price=f"{int(price):,}".replace(",", " ") + " so'm")
    await state.set_state(Sell.google)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha", callback_data="sell_google_yes"),
        InlineKeyboardButton(text="Yo'q", callback_data="sell_google_no")
    ]])
    await message.answer("Google Play akkauntga ulanganmi?", reply_markup=kb)

@dp.callback_query(F.data.startswith("sell_google_"))
async def sell_google(call: CallbackQuery, state: FSMContext):
    if not await gate_callback(call): return
    await state.update_data(google_play="Ha" if call.data.endswith("yes") else "Yo'q")
    await state.set_state(Sell.gamecenter)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Ha", callback_data="sell_gc_yes"),
        InlineKeyboardButton(text="Yo'q", callback_data="sell_gc_no")
    ]])
    await call.message.answer("Game Center akkauntga ulanganmi?", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data.startswith("sell_gc_"))
async def sell_gc(call: CallbackQuery, state: FSMContext):
    if not await gate_callback(call): return
    await state.update_data(game_center="Ha" if call.data.endswith("yes") else "Yo'q")
    await state.set_state(Sell.description)
    await call.message.answer("Akkaunt haqida qo'shimcha ma'lumot yozing.")
    await call.answer()

@dp.message(Sell.description)
async def sell_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text or "Izoh yo'q")
    data = await state.get_data()
    await state.set_state(Sell.confirm)
    text = (
        "<b>📌 Sotuv e'loni ko'rinishi</b>\n"
        f"💰 Narx: {data['price']}\n"
        f"Google Play: {data['google_play']}\n"
        f"Game Center: {data['game_center']}\n"
        f"📝 Izoh: {data['description']}\n\n"
        "E'lonni adminga yuboraymi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yuborish", callback_data="sell_submit"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")
    ]])
    await message.answer_photo(data["photo_id"], caption=text, reply_markup=kb)

@dp.callback_query(F.data == "sell_submit")
async def sell_submit(call: CallbackQuery, state: FSMContext):
    if not await gate_callback(call): return
    data = await state.get_data()
    with db() as con:
        cur = con.execute(
            "INSERT INTO listings(user_id,kind,photo_id,price,google_play,game_center,description,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (call.from_user.id, "sell", data["photo_id"], data["price"], data["google_play"], data["game_center"], data["description"], "pending", datetime.utcnow().isoformat())
        )
        listing_id = cur.lastrowid
    await state.clear()
    await call.message.answer("✅ E'loningiz adminga yuborildi. Tekshiruvdan so'ng javob beramiz.", reply_markup=main_menu())
    await send_admin_listing(listing_id)
    await call.answer("Yuborildi")

@dp.message(F.text == "🔵 Akkaunt sotib olish")
async def buy_start(message: Message, state: FSMContext):
    if not await gate_message(message): return
    await state.set_state(Buy.budget)
    await message.answer("Budjetingiz qancha? So'mda yozing. Masalan: 500000")

@dp.message(Buy.budget)
async def buy_budget(message: Message, state: FSMContext):
    await state.update_data(budget=message.text or "")
    await state.set_state(Buy.description)
    await message.answer("Qanday akkaunt kerakligini batafsil yozing.")

@dp.message(Buy.description)
async def buy_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text or "")
    await state.set_state(Buy.note)
    await message.answer("Qo'shimcha talab yoki izoh bo'lsa yozing. Bo'lmasa “Yo'q” deb yuboring.")

@dp.message(Buy.note)
async def buy_note(message: Message, state: FSMContext):
    await state.update_data(note=message.text or "")
    data = await state.get_data()
    await state.set_state(Buy.confirm)
    text = (
        "<b>📌 Xarid so'rovi</b>\n"
        f"💰 Budjet: {data['budget']}\n"
        f"🎮 Kerakli akkaunt: {data['description']}\n"
        f"📝 Qo'shimcha: {data['note']}\n\n"
        "So'rovni adminga yuboraymi?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yuborish", callback_data="buy_submit"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")
    ]])
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "buy_submit")
async def buy_submit(call: CallbackQuery, state: FSMContext):
    if not await gate_callback(call): return
    data = await state.get_data()
    description = f"Budjet: {data['budget']}\nKerakli akkaunt: {data['description']}\nQo'shimcha: {data['note']}"
    with db() as con:
        cur = con.execute(
            "INSERT INTO listings(user_id,kind,description,status,created_at) VALUES(?,?,?,?,?)",
            (call.from_user.id, "buy", None, description, "pending", datetime.utcnow().isoformat())
        )
        listing_id = cur.lastrowid
    await state.clear()
    await call.message.answer("✅ Xarid so'rovingiz adminga yuborildi.", reply_markup=main_menu())
    await send_admin_listing(listing_id)
    await call.answer("Yuborildi")

async def send_admin_listing(listing_id: int):
    with db() as con:
        item = con.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    user = f"<a href='tg://user?id={item['user_id']}'>Foydalanuvchi</a>"
    if item["kind"] == "sell":
        caption = (
            f"<b>🟠 Yangi sotuv e'loni #{listing_id}</b>\n{user}\n"
            f"💰 Narx: {item['price']}\nGoogle Play: {item['google_play']}\n"
            f"Game Center: {item['game_center']}\n📝 {item['description']}"
        )
        await bot.send_photo(
            next(iter(ADMIN_IDS)), item["photo_id"], caption=caption,
            reply_markup=admin_kb(listing_id)
        )
    else:
        await bot.send_message(
            next(iter(ADMIN_IDS)),
            f"<b>🔵 Yangi xarid so'rovi #{listing_id}</b>\n{user}\n{item['description']}",
            reply_markup=admin_kb(listing_id)
        )

def admin_kb(listing_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{listing_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{listing_id}")
    ]])

@dp.callback_query(F.data.startswith(("approve_", "reject_")))
async def admin_decision(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Bu amal faqat admin uchun.", show_alert=True)
        return
    action, raw_id = call.data.split("_", 1)
    listing_id = int(raw_id)
    with db() as con:
        item = con.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
        if not item or item["status"] != "pending":
            await call.answer("Bu e'lon avval ko'rib chiqilgan.", show_alert=True)
            return
        status = "approved" if action == "approve" else "rejected"
        con.execute("UPDATE listings SET status=? WHERE id=?", (status, listing_id))
    if action == "approve":
        if item["kind"] == "sell":
            caption = (
                f"<b>🟢 AKKAUNT SOTILADI</b>\n"
                f"💰 Narx: {item['price']}\nGoogle Play: {item['google_play']}\n"
                f"Game Center: {item['game_center']}\n📝 {item['description']}\n"
                f"📩 Aloqa: <a href='tg://user?id={item['user_id']}'>Sotuvchi bilan bog'lanish</a>"
            )
            await bot.send_photo(PUBLIC_CHANNEL, item["photo_id"], caption=caption)
        else:
            await bot.send_message(
                PUBLIC_CHANNEL,
                f"<b>🔵 AKKAUNT SOTIB OLISH E'LONI</b>\n{item['description']}\n"
                f"📩 Aloqa: <a href='tg://user?id={item['user_id']}'>Xaridor bilan bog'lanish</a>"
            )
        await bot.send_message(item["user_id"], f"✅ E'loningiz #{listing_id} tasdiqlandi va kanalga joylandi.")
        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Tasdiqlandi va kanalga joylandi")
    else:
        await bot.send_message(item["user_id"], f"❌ E'loningiz #{listing_id} admin tomonidan rad etildi.")
        await call.message.edit_reply_markup(reply_markup=None)
        await call.answer("Rad etildi")

@dp.message(F.text == "📋 Mening e'lonlarim")
async def my_listings(message: Message):
    if not await gate_message(message): return
    with db() as con:
        items = con.execute("SELECT id,kind,status,created_at FROM listings WHERE user_id=? ORDER BY id DESC LIMIT 20", (message.from_user.id,)).fetchall()
    if not items:
        await message.answer("Sizda hali e'lonlar yo'q.")
        return
    labels = {"pending": "⏳ Kutilmoqda", "approved": "✅ Tasdiqlangan", "rejected": "❌ Rad etilgan"}
    lines = ["<b>📋 Sizning e'lonlaringiz:</b>"]
    for item in items:
        kind = "Sotuv" if item["kind"] == "sell" else "Xarid"
        lines.append(f"#{item['id']} — {kind} — {labels.get(item['status'], item['status'])}")
    await message.answer("\n".join(lines))

@dp.message(F.text == "ℹ️ Yordam")
async def help_msg(message: Message):
    if not await gate_message(message): return
    await message.answer("E'lon joylash uchun kerakli bo'limni tanlang. E'lonlar admin tekshiruvidan keyin @RazzokeShop kanaliga chiqariladi.\nSavollar bo'lsa admin bilan bog'laning: @Razzoke_eFootball", reply_markup=main_menu())

@dp.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("Amal bekor qilindi.", reply_markup=main_menu())
    await call.answer()

@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi.", reply_markup=main_menu())

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
