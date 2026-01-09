import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timezone, timedelta
import time
import sys # 引入系統模組，用來強制停止程式

# 設定台灣時間
TW_TZ = timezone(timedelta(hours=8))
DATA_FILE = 'data.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

def clean_number(text):
    if not text: return "-"
    match = re.search(r'\d+(\.\d+)?', text)
    if match: return match.group(0)
    return text.strip()

def get_bot_rates_and_date():
    print("正在抓取台銀資料與日期檢查...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    board_date = None
    try:
        resp = requests.get("https://rate.bot.com.tw/xrt?Lang=zh-TW", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        time_span = soup.find('span', class_='time')
        if time_span:
            board_date = time_span.text.strip().split(' ')[0].replace('/', '-') 
            print(f"🔎 台銀網頁掛牌日期: {board_date}")
        for row in soup.find_all('tr'):
            text = row.text.strip()
            if "美金" in text:
                res["USD"] = [
                    row.find('td', {'data-table': '本行即期買入'}).text.strip(),
                    row.find('td', {'data-table': '本行即期賣出'}).text.strip()
                ]
            if "人民幣" in text:
                res["CNY"] = [
                    row.find('td', {'data-table': '本行即期買入'}).text.strip(),
                    row.find('td', {'data-table': '本行即期賣出'}).text.strip()
                ]
    except Exception as e:
        print(f"❌ 台銀失敗: {e}")
    return res, board_date

def get_sunny_rates():
    print("正在抓取陽信...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        url = "https://www.sunnybank.com.tw/portal/pt/pt02003/PT02003Index.xhtml"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200: return res
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.find_all('tr'):
            raw_text = row.get_text(strip=True)
            tds = row.find_all('td')
            if len(tds) >= 5:
                if ("美元" in raw_text or "美金" in raw_text or "USD" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy != "-": res["USD"] = [buy, sell]
                if ("人民幣" in raw_text or "CNY" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy != "-": res["CNY"] = [buy, sell]
    except Exception as e:
        print(f"❌ 陽信發生錯誤: {e}")
    return res

def main():
    today_obj = datetime.now(TW_TZ)
    today_str = today_obj.strftime('%Y-%m-%d')
    print(f"📅 系統執行日期: {today_str}")

    bot_res, bot_board_date = get_bot_rates_and_date()
    if bot_board_date and bot_board_date != today_str:
        print(f"🛑 停止更新：台銀掛牌日期 ({bot_board_date}) 與今日 ({today_str}) 不符。")
        return

    time.sleep(2)
    sunny_res = get_sunny_rates()
    
    new_data = {
        "date": today_str,
        "sunny_usd_buy": sunny_res["USD"][0], 
        "sunny_usd_sell": sunny_res["USD"][1],
        "sunny_cny_buy": sunny_res["CNY"][0], 
        "sunny_cny_sell": sunny_res["CNY"][1],
        "bot_usd_buy": bot_res["USD"][0], 
        "bot_usd_sell": bot_res["USD"][1],
        "bot_cny_buy": bot_res["CNY"][0], 
        "bot_cny_sell": bot_res["CNY"][1]
    }

    # --- 安全讀檔機制 (修改重點) ---
    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip(): # 確保不是空檔
                    history = json.loads(content) # 使用 loads 來測試格式
        except json.JSONDecodeError as e:
            # 🚨 重大警告：如果格式錯了，程式直接自殺，保護檔案不被覆蓋
            print(f"💥 嚴重錯誤：data.json 格式損毀或語法錯誤！")
            print(f"錯誤訊息：{e}")
            print("🛑 為了保護資料，程式已強制停止，請手動修正 data.json 格式後再試。")
            sys.exit(1) # 強制退出，回報錯誤
        except Exception as e:
            print(f"💥 讀取檔案發生未預期錯誤：{e}")
            sys.exit(1)

    # 移除重複
    history = [d for d in history if d['date'] != today_str]
    history.append(new_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("🚀 資料確認為最新，更新完畢！")

if __name__ == "__main__":
    main()
