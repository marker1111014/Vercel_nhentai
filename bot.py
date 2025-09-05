# bot.py
import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

# 取得環境變數
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
IPB_MEMBER_ID = os.getenv('IPB_MEMBER_ID')
IPB_PASS_HASH = os.getenv('IPB_PASS_HASH')
IGNEOUS = os.getenv('IGNEOUS')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # 例如：https://your-project.vercel.app/webhook

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
        logger.error(f"過濾標題時發生錯誤: {e}")
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
            caption = gallery.find('div', class_='caption')
            if caption and '[Chinese]' in caption.get_text():
                link = gallery.find('a')
                if link:
                    href = link.get('href')
                    full_url = f"https://nhentai.net{href}" if href.startswith('/') else f"https://nhentai.net/g/{href}"
                    logger.info(f"找到 nhentai 連結: {full_url}")
                    return full_url
        logger.info("未找到包含 [Chinese] 的結果")
        return None
    except Exception as e:
        logger.error(f"搜索 nhentai 時發生錯誤: {e}")
        return None

# 獲取標題
def get_gallery_title(url):
    try:
        logger.info(f"正在獲取標題: {url}")
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
            logger.info("使用 exhentai cookies")
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找標題元素
        title_element = soup.find('h1', id='gn')
        if title_element:
            original = title_element.get_text().strip()
            logger.info(f"找到原始標題: {original}")
            return {'original': original, 'filtered': filter_title(original)}
        
        # 備用方案
        title_element = soup.find('title')
        if title_element:
            original = title_element.get_text().strip()
            for suffix in [' - E-Hentai Galleries', ' - ExHentai.org']:
                original = original.replace(suffix, '')
            logger.info(f"備用方案找到標題: {original}")
            return {'original': original, 'filtered': filter_title(original)}
            
        logger.warning("無法獲取標題")
        return {'original': "無法獲取標題", 'filtered': "無法獲取標題"}
    except Exception as e:
        logger.error(f"獲取標題時發生錯誤: {e}")
        return {'original': "獲取標題失敗", 'filtered': "獲取標題失敗"}

# 處理訊息
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"收到訊息: {update.message.text}")
        message_text = update.message.text
        gallery_url = is_valid_gallery_url(message_text)
        
        if gallery_url:
            logger.info(f"偵測到有效連結: {gallery_url}")
            processing_message = await update.message.reply_text("正在獲取漫畫標題...")
            
            # 獲取標題
            title_info = get_gallery_title(gallery_url)
            response_text = f"🇯🇵 原始標題：\n{title_info['original']}\n\n"
            response_text += f"🎯 過濾後標題：\n{title_info['filtered']}\n\n"
            
            # 搜索 nhentai
            await processing_message.edit_text("正在搜索 nhentai（中文版）...")
            nhentai_link = search_nhentai_chinese(title_info['filtered'])
            
            if nhentai_link:
                response_text += f"🔗 nhentai 中文版：\n{nhentai_link}"
            else:
                response_text += "❌ 在 nhentai 找不到中文版結果"
            
            await processing_message.edit_text(response_text)
        else:
            logger.info("未偵測到有效連結")
            # 可以選擇是否回覆提示訊息
            # await update.message.reply_text("請傳送有效的 e-hentai 或 exhentai 連結")
            
    except Exception as e:
        logger.error(f"處理訊息時發生錯誤: {e}")
        try:
            await update.message.reply_text("處理訊息時發生錯誤，請稍後再試。")
        except:
            pass

# 初始化 Telegram Bot
def init_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app

# FastAPI App
app = FastAPI()
bot_app = init_bot()

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"收到 webhook 資料: {data}")
        update = Update.de_json(data, bot_app.bot)
        await bot_app.initialize()
        await bot_app.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"處理 webhook 時發生錯誤: {e}")
        return {"status": "error"}

@app.get("/")
def root():
    return PlainTextResponse("Telegram Bot is running here")

@app.get("/set_webhook")
async def set_webhook_endpoint():
    try:
        await bot_app.bot.set_webhook(WEBHOOK_URL)
        return {"status": "webhook set successfully"}
    except Exception as e:
        logger.error(f"設定 webhook 時發生錯誤: {e}")
        return {"status": "error", "message": str(e)}

# 啟動時設定 webhook
@app.on_event("startup")
async def startup_event():
    try:
        logger.info("正在設定 webhook...")
        await bot_app.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook 設定完成: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"啟動時設定 webhook 失敗: {e}")
