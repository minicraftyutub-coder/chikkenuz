import os, asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
load_dotenv()
TOKEN=os.getenv("BOT_TOKEN","")
WEBAPP_URL=os.getenv("WEBAPP_URL","")
dp=Dispatcher()
@dp.message(CommandStart())
async def start(m:Message):
    if not WEBAPP_URL:
        await m.answer("WEBAPP_URL sozlanmagan.")
        return
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🐔 Chicken Money ochish",web_app=WebAppInfo(url=WEBAPP_URL))]])
    await m.answer("🐔 Chicken Money Mini App\n\nFerma, tuxum, balans, depozit va pul yechish bo‘limlari shu yerda.",reply_markup=kb)
async def main():
    if not TOKEN: raise RuntimeError("BOT_TOKEN sozlanmagan")
    bot=Bot(TOKEN)
    await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
