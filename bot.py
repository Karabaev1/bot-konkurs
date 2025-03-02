import os
import logging
import asyncio
import sqlite3
import pandas as pd
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

load_dotenv()

# Bot konfiguratsiyasi
TOKEN = os.getenv("TOKEN")
INSTAGRAM_LINK = "https://www.instagram.com/senior.collection?igsh=dnRjdTBpNzhmbTB3" 
TIKTOK_LINK = "https://www.tiktok.com/@senior.collection?_t=ZN-8ts9iyt4Aly&_r=1" 
TELEGRAM_LINK = "https://t.me/seniorcollection" 
TELEGRAM_CHAT_ID = "@seniorcollection"  # Kanal yoki guruh username si 
SUPER_ADMIN_ID = [5498104054, 5034987604]  # Super Admin ID (o'zingizning ID-ingizni qo'ying)

# Bot va dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# SQL ma'lumotlar bazasi
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    nice_name TEXT
)""")
conn.commit()

def add_user(user_id, username, nice_name):
    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, username, nice_name)
    VALUES (?, ?, ?)""", (user_id, username, nice_name))
    conn.commit()

def remove_user(user_id):
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()

def get_all_users():
    cursor.execute("SELECT user_id, nice_name FROM users")
    return cursor.fetchall()

def save_users_to_excel():
    users = get_all_users()
    df = pd.DataFrame(users, columns=["User ID", "Nice Name"])
    df.to_excel("users.xlsx", index=False)

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(TELEGRAM_CHAT_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except TelegramBadRequest:
        return False

def get_subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Instagramga obuna bo‘lish", url=INSTAGRAM_LINK)],
        [InlineKeyboardButton(text="📌 TikTokga obuna bo‘lish", url=TIKTOK_LINK)],
        [InlineKeyboardButton(text="📌 Telegram kanalga obuna bo‘lish", url=TELEGRAM_LINK)],
        [InlineKeyboardButton(text="✅ Obunani tasdiqlash", callback_data="confirm_subscription")]
    ])

@router.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    nice_name = message.from_user.full_name
    
    if await is_subscribed(user_id):
        add_user(user_id, username, nice_name)
        await message.answer("🎉 Siz allaqachon konkurs ishtirokchisiz! Omad!", reply_markup=get_subscription_keyboard())
    else:
        await message.answer("Iltimos barcha ijtimoiy tarmoqlarga qo‘shiling", reply_markup=get_subscription_keyboard())

@router.callback_query(lambda c: c.data == "confirm_subscription")
async def confirm_subscription(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username or "No Username"
    nice_name = callback_query.from_user.full_name
    
    if await is_subscribed(user_id):
        add_user(user_id, username, nice_name)
        await callback_query.message.answer("Tabriklaymiz! Siz konkurs ishtirokchisiz!")
    else:
        await callback_query.answer("Siz barcha havolalarga obuna bo‘lishingiz kerak!", show_alert=True)

@router.message(Command("all_users"))
async def all_users(message: types.Message):
    if message.from_user.id not in SUPER_ADMIN_ID:
        await message.answer("⛔ Siz bu kommandani ishlata olmaysiz!")
        return
    
    users = get_all_users()
    if not users:
        await message.answer("📭 Hali hech kim ro‘yxatga qo‘shilmagan!")
        return
    
    users_list = "\n".join([
    f"👤 [{nice_name if nice_name else 'Ism yo‘q'}](tg://user?id={user_id}) | 🆔 `{user_id}`" 
    for user_id, nice_name in users
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Random G‘olib Tanlash", callback_data="random_user")]
    ])
    save_users_to_excel()
    
    await message.answer(f"📜 **Barcha foydalanuvchilar:**\n\n{users_list}", parse_mode="Markdown", reply_markup=keyboard)
    await message.answer_document(types.FSInputFile("users.xlsx"), caption="📂 Barcha foydalanuvchilar faylda!")

@router.callback_query(lambda c: c.data == "random_user")
async def random_user(callback_query: CallbackQuery):
    if callback_query.from_user.id not in SUPER_ADMIN_ID:
        await callback_query.answer("⛔ Sizga bu imkoniyat mavjud emas!", show_alert=True)
        return
    
    users = get_all_users()
    if not users:
        await callback_query.answer("📭 Ro‘yxatda hech kim yo‘q!", show_alert=True)
        return
    
    selected_user = random.choice(users)
    await callback_query.message.answer(f"🎉 Tasodifiy g‘olib:\n\n👤 [{selected_user[1]}](tg://user?id={selected_user[0]}) | 🆔 `{selected_user[0]}`", parse_mode="Markdown")

@router.message(Command("ads"))
async def send_ad_command(message: types.Message, state: FSMContext):
    if message.from_user.id not in SUPER_ADMIN_ID:
        await message.answer("⛔ Siz bu kommandani ishlata olmaysiz!")
        return
    
    await message.answer("📢 Reklamani yuboring. Yuborgan xabaringiz barcha foydalanuvchilarga forward qilinadi.")
    await state.set_state(AdState.waiting_for_ad)

class AdState(StatesGroup):
    waiting_for_ad = State()

@router.message(AdState.waiting_for_ad)
async def forward_advertisement(message: types.Message, state: FSMContext):
    users = get_all_users()
    
    for user_id, _ in users:
        try:
            await bot.forward_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except Exception as e:
            logging.error(f"Xatolik {user_id} ga yuborishda: {e}")
    
    await state.clear()
    await message.answer("✅ Reklama barcha foydalanuvchilarga muvaffaqiyatli yuborildi!")

async def check_users_subscription():
    users = get_all_users()
    for user_id, _ in users:
        if not await is_subscribed(user_id):
            remove_user(user_id)

async def main():
    asyncio.create_task(check_users_subscription())  # Asinxron tekshirishni boshlaymiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
