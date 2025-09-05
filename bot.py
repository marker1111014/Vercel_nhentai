import os
import re
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ContextTypes
from dotenv import load_dotenv
import urllib.parse
# 載入環境變數
load_dotenv()
# 取得 Telegram Bot Token
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# exhentai cookies
IPB_MEMBER_ID = os.getenv('IPB_MEMBER_ID')
IPB_PASS_HASH = os.getenv('IPB_PASS_HASH')
IGNEOUS = os.getenv('IGNEOUS')

# 檢查是否為有效的 e-hentai 或 exhentai 連結
def is_valid_gallery_url(text):
    pattern = r'https?://(?:e-hentai\.org|exhentai\.org)/g/[\w\-]+/\w+/?'
    match = re.search(pattern, text)
    return match.group(0) if match else None

# 過濾標題，移除方括號內容（如作者、語言等資訊）
def filter_title(title):
    """
    過濾標題，移除方括號中的內容
    例如："[SigMart (SigMa)] Cool-kei Tenin-san o Omochikaeri Shichatta Hanashi 3 [Chinese] [酸菜魚ゅ°]"
    變成："Cool-kei Tenin-san o Omochikaeri Shichatta Hanashi 3"
    """
    if not title:
        return ""
    
    # 儲存原始標題
    original_title = title
    
    try:
        # 逐步移除各種括號內容
        # 1. 移除 [內容] 格式
        title = re.sub(r'\[[^\]]*\]', '', title)
        
        # 2. 移除 【內容】 格式
        title = re.sub(r'【[^】]*】', '', title)
        
        # 3. 移除 (內容) 格式
        title = re.sub(r'\([^\)]*\)', '', title)
        
        # 4. 移除 （內容）格式（全形括號）
        title = re.sub(r'（[^）]*）', '', title)
        
        # 5. 移除多餘的空格和特殊字元
        title = re.sub(r'\s+', ' ', title).strip()
        
        # 6. 移除開頭和結尾可能殘留的特殊字元
        title = re.sub(r'^[\[\]【】\(\)（）\s]+', '', title)
        title = re.sub(r'[\[\]【】\(\)（）\s]+$', '', title)
        
        # 如果過濾後為空，則返回原始標題
        return title if title else original_title
        
    except Exception as e:
        print(f"過濾標題時發生錯誤: {e}")
        return original_title

# 在 nhentai 搜索標題，只返回包含 [Chinese] 的結果
def search_nhentai_chinese(title):
    """
    在 nhentai 搜索標題並返回第一個包含 [Chinese] 的結果連結
    """
    try:
        if not title:
            return None
            
        # URL 編碼搜索關鍵字
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://nhentai.net/search/?q={encoded_title}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找搜索結果中的漫畫項目
        galleries = soup.find_all('div', class_='gallery')
        
        # 遍歷搜索結果，尋找包含 [Chinese] 的項目
        for gallery in galleries:
            # 獲取標題（caption）
            caption_element = gallery.find('div', class_='caption')
            if caption_element:
                caption_text = caption_element.get_text().strip()
                # 檢查標題是否包含 [Chinese]
                if '[Chinese]' in caption_text:
                    # 獲取連結
                    link_element = gallery.find('a')
                    if link_element:
                        href = link_element.get('href')
                        if href:
                            # 確保連結是完整的 URL
                            if href.startswith('/'):
                                return f"https://nhentai.net{href}"
                            else:
                                return f"https://nhentai.net/g/{href}"
        
        # 如果沒有找到包含 [Chinese] 的結果，返回 None
        return None
        
    except Exception as e:
        print(f"搜索 nhentai 時發生錯誤: {e}")
        return None

# 獲取漫畫標題（支持 e-hentai 和 exhentai）
def get_gallery_title(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 根據網域設置不同的 cookies
        cookies = {}
        if 'exhentai.org' in url:
            cookies = {
                'ipb_member_id': IPB_MEMBER_ID,
                'ipb_pass_hash': IPB_PASS_HASH,
                'igneous': IGNEOUS
            }
            print("使用 exhentai cookies")
        else:
            print("使用 e-hentai（無需 cookies）")
        
        response = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 尋找標題元素
        title_element = soup.find('h1', id='gn')
        if title_element:
            original_title = title_element.get_text().strip()
            filtered_title = filter_title(original_title)
            return {
                'original': original_title,
                'filtered': filtered_title
            }
        
        # 如果找不到，嘗試其他可能的標題位置
        title_element = soup.find('title')
        if title_element:
            original_title = title_element.get_text().strip()
            # 移除網站名稱後綴
            if ' - E-Hentai Galleries' in original_title:
                original_title = original_title.replace(' - E-Hentai Galleries', '')
            elif ' - ExHentai.org' in original_title:
                original_title = original_title.replace(' - ExHentai.org', '')
            
            filtered_title = filter_title(original_title)
            return {
                'original': original_title,
                'filtered': filtered_title
            }
            
        return {
            'original': "無法獲取標題",
            'filtered': "無法獲取標題"
        }
        
    except Exception as e:
        print(f"獲取標題時發生錯誤: {e}")
        return {
            'original': "獲取標題失敗",
            'filtered': "獲取標題失敗"
        }

# 處理訊息的函數
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    # 檢查是否包含 e-hentai 或 exhentai 連結
    gallery_url = is_valid_gallery_url(message_text)
    
    if gallery_url:
        # 傳送處理中訊息
        processing_message = await update.message.reply_text("正在獲取漫畫標題...")
        
        try:
            # 獲取標題
            title_info = get_gallery_title(gallery_url)
            
            # 準備回覆訊息
            response_text = f"🇯🇵 原始標題：\n{title_info['original']}\n\n"
            response_text += f"🎯 過濾後標題：\n{title_info['filtered']}\n\n"
            
            # 搜索 nhentai（只找包含 [Chinese] 的結果）
            await processing_message.edit_text("正在搜索 nhentai（中文版）...")
            nhentai_link = search_nhentai_chinese(title_info['filtered'])
            
            if nhentai_link:
                response_text += f"🔗 nhentai 中文版：\n{nhentai_link}"
            else:
                response_text += "❌ 在 nhentai 找不到中文版結果"
            
            # 回覆完整訊息
            await processing_message.edit_text(response_text)
            
        except Exception as e:
            await processing_message.edit_text("獲取標題時發生錯誤，請稍後再試。")

# 主函數
def main():
    if not BOT_TOKEN:
        print("錯誤：請在 .env 檔案中設定 TELEGRAM_BOT_TOKEN")
        return
    
    # 建立應用程式
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 加入訊息處理器（只處理文字訊息）
    message_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    application.add_handler(message_handler)
    
    print("Bot 已啟動，正在監聽訊息...")
    print("支援網域：e-hentai.org, exhentai.org")
    
    # 啟動機器人
    application.run_polling()

if __name__ == '__main__':
    main()
