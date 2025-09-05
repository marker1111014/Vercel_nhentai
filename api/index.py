# api/index.py
from fastapi import FastAPI, Request
import os
from bot import handle_message, BOT_TOKEN
from telegram import Update
from telegram.ext import Application

app = FastAPI()

# 初始化 bot application（只初始化一次）
application = Application.builder().token(BOT_TOKEN).build()

@app.get("/")
def read_root():
    return {"message": "Telegram Bot is running on Vercel!"}

@app.post(f"/webhook/{BOT_TOKEN}")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.initialize()  # 初始化（如果還沒有）
    await application.process_update(update)
    return {"status": "ok"}
