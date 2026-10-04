# 🐔 Chicken Money Mini App

Telegram Mini App uchun GitHub/Render starter.

## GitHub
Bu papkaning ichidagi barcha fayllarni repository root'iga yuklang.

`.env` va bot tokenni GitHub'ga yuklamang.

## Render
Web:
`pip install -r requirements.txt`
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

Worker:
`pip install -r requirements.txt`
`python bot.py`

## Environment
`BOT_TOKEN`
`WEBAPP_URL`
`ADMIN_IDS`
`DATABASE_PATH`

Admin Telegram ID `ADMIN_IDS` ga yoziladi.

## Eslatma
Deposit screenshot saqlanadi va deposit admin tomonidan approve/reject qilinadi.
Withdrawal yuborilganda summa balansdan ushlab turiladi; reject qilinsa qaytariladi.
Haqiqiy blockchain avtomatik tekshiruvi keyingi bosqichda ulanadi.
