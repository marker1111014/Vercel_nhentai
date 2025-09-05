# bot.py
import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import urllib.parse

# 載入環境變數
load_dotenv()

# 取得環境變數
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
IPB_MEMBER_ID = os.getenv('IPB_MEMBER_ID')
IPB_PASS_HASH = os.getenv('IPB_PASS_HASH')
IGNEOUS = os.getenv('IGNEOUS')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # 例如：https://your-bot.vercel.app/webhook

# === 你的原有函數保持不變 ===
# is_valid_gallery_url, filter_title, search_nhentai_chinese, get_gallery_title, handle_message

# 檢查是否為有效的 e-hentai 或 exhentai 連結
def is_valid_gallery_url(text):
    pattern = r'https?://(?:e-hentai\.org|exhentai\.org)/g/[\w\-]+/\w+/?'
    match = re.search(pattern, text)
    return match.group(0) if match else None

# 過濾標題
def filter_title(title):
    if not title:
        return ""
    original_title = title
    try:
        title = re.sub(r'\[[^\]]*\]', '', title)
        title = re.sub(r'【[^】]*】', '', title)
        title = re.sub(r'\([^\)]*\)', '', title)
        title = re.sub(r'（[^）]*）', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[\[\]【】\(\)（）\s]+', '', title)
        title = re.sub(r'[\[\]【】\(\)（）\s]+$', '', title)
        return title if title else original_title
    except Exception as e:
        print(f"過濾標題時發生錯誤: {e}")
        return original_title

# 搜索 nhentai 中文版
def search_nhentai_chinese(title):
    try:
        if not title:
            return None
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://nhentai.net/search/?q={encoded_title}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        galleries = soup.find_all('div', class_='gallery')
        for gallery in galleries:
            caption_element = gallery.find('div', class_='caption')
            if caption_element and '[Chinese]' in caption_element.get_text():
                link_element = gallery.find('a')
                if link_element:
                    href = link_element.get('href')
                    if href.startswith('/'):
                        return f"https://nhentai.net{href}"
                    else:
                        return f"https://nhentai.net/g/{href}"
        return None
    except Exception as e:
        print(f"搜索 nhentai 時發生錯誤: {e}")
        return None

# 獲取標題
def get_gallery_title(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        cookies = {}
        if 'exhentai.org' in url:
            cookies = {
                'ipb_member_id': IPB_MEMBER_ID,
                'ipb_pass_hash': IPB_PASS_HASH,
                'igneous': IGNEOUS
            }
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        title_element = soup.find('h1', id='gn')
        if title_element:
            original_title = title_element.get_text().strip()
            filtered_title = filter_title(original_title)
            return {'original': original_title, 'filtered': filtered_title}
        title_element = soup.find('title')
        if title_element:
            original_title = title_element.get_text().strip()
            if ' - E-Hentai Galleries' in original_title:
                original_title = original_title.replace(' - E-Hentai Galleries', '')
            elif ' - ExHentai.org' in original_title:
                original_title = original_title.replace(' - ExHentai.org', '')
            filtered_title = filter_title(original_title)
            return {'original': original_title, 'filtered': filtered_title}
        return {'original': "無法獲取標題", 'filtered': "無法獲取標題"}
    except Exception as e:
        print(f"獲取標題時發生錯誤: {e}")
        return {'original': "獲取標題失敗", 'filtered': "獲取標題失敗"}

# 處理訊息
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    gallery_url = is_valid_gallery_url(message_text)
    if gallery_url:
        processing_message = await update.message.reply_text("正在獲取漫畫標題...")
        try:
            title_info = get_gallery_title(gallery_url)
            response_text = f"🇯🇵 原始標題：\n{title_info['original']}\n\n"
            response_text += f"🎯 過濾後標題：\n{title_info['filtered']}\n\n"
            await processing_message.edit_text("正在搜索 nhentai（中文版）...")
            nhentai_link = search_nhentai_chinese(title_info['filtered'])
            if nhentai_link:
                response_text += f"🔗 nhentai 中文版：\n{nhentai_link}"
            else:
                response_text += "❌ 在 nhentai 找不到中文版結果"
            await processing_message.edit_text(response_text)
        except Exception as e:
            await processing_message.edit_text("獲取標題時發生錯誤，請稍後再試。")

# === 新增 Webhook 處理函數 ===
from fastapi import FastAPI, Request
from telegram.ext import ApplicationBuilder

app = FastAPI()

# 初始化 Bot Application
application = ApplicationBuilder().token(BOT_TOKEN).build()

# 加入訊息處理器
message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
application.add_handler(message_handler)

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"status": "ok"}

# 設定 Webhook（只在本地或部署時執行一次）
@app.on_event("startup")
async def set_webhook():
    s = await application.bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook 設定結果: {s}")
