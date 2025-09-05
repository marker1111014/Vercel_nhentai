# bot.py
import os
import re
import requests
import logging
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
import asyncio
import traceback

# 設置日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

# 取得環境變數
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
IPB_MEMBER_ID = os.getenv('IPB_MEMBER_ID')
IPB_PASS_HASH = os.getenv('IPB_PASS_HASH')
IGNEOUS = os.getenv('IGNEOUS')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

def is_valid_gallery_url(text):
    pattern = r'https?://(?:e-hentai\.org|exhentai\.org)/g/[\w\-]+/\w+/?'
    match = re.search(pattern, text)
    return match.group(0) if match else None

def filter_title(title):
    if not title:
        return ""
    try:
        original_title = title
        
        # 移除方括號內容 [xxxxx]
        title = re.sub(r'\[[^\]]*\]', '', title)
        
        # 移除全形方括號內容 【xxxxx】
        title = re.sub(r'【[^】]*】', '', title)
        
        # 移除圓括號內容 (xxxxx)
        title = re.sub(r'\([^\)]*\)', '', title)
        
        # 移除全形圓括號內容 （xxxxx）
        title = re.sub(r'（[^）]*）', '', title)
        
        # 移除尖括號內容 <xxxxx>
        title = re.sub(r'<[^>]*>', '', title)
        
        # 移除全形尖括號內容 《xxxxx》
        title = re.sub(r'《[^》]*》', '', title)
        
        # 移除花括號內容 {xxxxx}
        title = re.sub(r'\{[^}]*\}', '', title)
        
        # 移除全形花括號內容 ｛xxxxx｝
        title = re.sub(r'｛[^｝]*｝', '', title)
        
        # 清理多餘的空白字符
        title = re.sub(r'\s+', ' ', title).strip()
        
        # 移除開頭的標點符號和空白
        title = re.sub(r'^[\[\]【】\(\)（）\<\>《》\{\}｛｝\s\|\-\–—]+', '', title)
        
        # 移除結尾的標點符號和空白
        title = re.sub(r'[\[\]【】\(\)（）\<\>《》\{\}｛｝\s\|\-\–—]+$', '', title)
        
        # 處理 "|" 符號，只保留前面的部分（如果有的話）
        if '|' in title:
            parts = title.split('|')
            # 如果第一部分有內容，使用第一部分；否則使用處理後的完整標題
            if parts[0].strip():
                title = parts[0].strip()
            else:
                title = title.split('|')[0].strip()
        
        # 如果處理後為空，返回原始標題
        if not title:
            return original_title.strip()
            
        return title
    except Exception as e:
        logger.error(f"過濾標題時發生錯誤: {e}")
        return original_title if 'original_title' in locals() else title

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
        for gallery in galleries[:5]:  # 只檢查前5個結果
            caption = gallery.find('div', class_='caption')
            if caption and '[Chinese]' in caption.get_text():
                link = gallery.find('a')
                if link:
                    href = link.get('href')
                    full_url = f"https://nhentai.net{href}" if href.startswith('/') else href
                    return full_url
        return None
    except Exception as e:
        logger.error(f"搜索 nhentai 時發生錯誤: {e}")
        return None

def get_gallery_title(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        cookies = {}
        if 'exhentai.org' in url:
            if IPB_MEMBER_ID and IPB_PASS_HASH:
                cookies = {
                    'ipb_member_id': IPB_MEMBER_ID,
                    'ipb_pass_hash': IPB_PASS_HASH,
                    'igneous': IGNEOUS or ''
                }
            else:
                logger.warning("缺少 ExHentai cookies")
        
        logger.info(f"正在請求: {url}")
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        logger.info(f"請求狀態碼: {response.status_code}")
        
        if response.status_code != 200:
            return {'original': f"無法訪問頁面 (狀態碼: {response.status_code})", 'filtered': "無法獲取標題"}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        title_element = soup.find('h1', id='gn')
        if title_element:
            original = title_element.get_text().strip()
            return {'original': original, 'filtered': filter_title(original)}
        title_element = soup.find('title')
        if title_element:
            original = title_element.get_text().strip()
            for suffix in [' - E-Hentai Galleries', ' - ExHentai.org']:
                original = original.replace(suffix, '')
            return {'original': original, 'filtered': filter_title(original)}
        return {'original': "無法獲取標題", 'filtered': "無法獲取標題"}
    except Exception as e:
        logger.error(f"獲取標題時發生錯誤: {e}")
        logger.error(traceback.format_exc())
        return {'original': f"獲取標題失敗: {str(e)}", 'filtered': "獲取標題失敗"}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info("收到訊息")
        if not update.message or not update.message.text:
            logger.info("訊息為空或沒有文字")
            return
            
        message_text = update.message.text
        logger.info(f"訊息內容: {message_text}")
        gallery_url = is_valid_gallery_url(message_text)
        
        if gallery_url:
            logger.info(f"找到有效連結: {gallery_url}")
            
            try:
                logger.info("開始獲取標題")
                title_info = get_gallery_title(gallery_url)
                logger.info(f"獲取到標題: {title_info}")
                
                response_text = f"🇯🇵 原始標題：\n{title_info['original']}\n\n"
                response_text += f"🎯 過濾後標題：\n{title_info['filtered']}\n\n"
                
                logger.info("開始搜索 nhentai")
                nhentai_link = search_nhentai_chinese(title_info['filtered'])
                if nhentai_link:
                    response_text += f"🔗 nhentai 中文版：\n{nhentai_link}"
                else:
                    response_text += "❌ 在 nhentai 找不到中文版結果"
                
                logger.info("發送最終回覆")
                await update.message.reply_text(response_text)
            except Exception as e:
                logger.error(f"處理訊息時發生錯誤: {e}")
                logger.error(traceback.format_exc())
                await update.message.reply_text("❌ 處理請求時發生錯誤，請稍後再試。")
        else:
            logger.info("不是有效的畫廊連結")
    except Exception as e:
        logger.error(f"handle_message 發生錯誤: {e}")
        logger.error(traceback.format_exc())

# FastAPI App
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    try:
        logger.info("收到 webhook 請求")
        
        # 創建新的應用實例（每次都創建新的）
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # 解析更新數據
        data = await request.json()
        logger.info(f"收到數據: {data}")
        update = Update.de_json(data, application.bot)
        
        # 初始化並處理更新
        await application.initialize()
        await application.process_update(update)
        await application.shutdown()
        
        logger.info("webhook 處理完成")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook 處理錯誤: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error"}

@app.get("/")
def root():
    return PlainTextResponse("Telegram Bot Webhook Server is running")

@app.get("/set_webhook")
async def set_webhook_endpoint():
    try:
        # 創建臨時應用來設定 webhook
        temp_app = Application.builder().token(BOT_TOKEN).build()
        await temp_app.initialize()
        await temp_app.bot.set_webhook(WEBHOOK_URL)
        await temp_app.shutdown()
        logger.info(f"Webhook 設定成功: {WEBHOOK_URL}")
        return {"status": "webhook set successfully"}
    except Exception as e:
        logger.error(f"設定 Webhook 時發生錯誤: {e}")
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(e)}


