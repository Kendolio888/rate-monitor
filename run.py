import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timezone, timedelta
import time

# 設定台灣時間
TW_TZ = timezone(timedelta(hours=8))
DATA_FILE = 'data.json'

# 偽裝 Header
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

def clean_number(text):
    """清洗數字"""
    if not text: return "-"
    match = re.search(r'\d+(\.\d+)?', text)
    if match: return match.group(0)
    return text.strip()

def get_bot_rates_and_date():
    """
    抓取台銀匯率，並同時抓取網頁上的「掛牌日期」
    回傳: (匯率字典, 掛牌日期字串)
    """
    print("正在抓取台銀資料與日期檢查...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    board_date = None # 網頁上的掛牌日期

    try:
        resp = requests.get("https://rate.bot.com.tw/xrt?Lang=zh-TW", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. 抓取網頁上的掛牌時間 (通常在 class="time" 裡面，格式如 2024/05/23 16:00)
        time_span = soup.find('span', class_='time')
        if time_span:
            full_time_str = time_span.text.strip()
            # 只取日期部分 YYYY/MM/DD
            board_date = full_time_str.split(' ')[0].replace('/', '-') 
            print(f"🔎 台銀網頁掛牌日期: {board_date}")

        # 2. 抓取匯率
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
        print(f"✅ 台銀抓取成功: {res}")
    except Exception as e:
        print(f"❌ 台銀失敗: {e}")
    
    return res, board_date

def get_sunny_rates():
    """抓取陽信 (維持原邏輯)"""
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

        if res["USD"][0] != "-" or res["CNY"][0] != "-":
            print(f"✅ 陽信抓取結果: {res}")
        else:
            print("⚠️ 陽信抓取但無數值")

    except Exception as e:
        print(f"❌ 陽信發生錯誤: {e}")
    
    return res

def main():
    # 取得今天日期 (台灣時間)
    today_obj = datetime.now(TW_TZ)
    today_str = today_obj.strftime('%Y-%m-%d')
    print(f"📅 系統執行日期: {today_str}")

    # 1. 執行台銀抓取 (包含日期檢查)
    bot_res, bot_board_date = get_bot_rates_and_date()
    
    # --- 關鍵修改：嚴格日期核對 ---
    # 如果台銀網頁上的日期，不等於今天的日期，就代表今天沒開市 (可能是國定假日或週末)
    if bot_board_date and bot_board_date != today_str:
        print(f"🛑 停止更新：台銀掛牌日期 ({bot_board_date}) 與今日 ({today_str}) 不符。")
        print("💡 推測原因：今日為假日或尚未開盤。")
        return # 直接結束，不執行後續動作
    
    # 2. 如果日期吻合，才繼續抓陽信
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

    # 3. 讀寫資料庫
    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content: history = json.load(f)
        except: pass
    
    # 移除重複 (保險起見)
    history = [d for d in history if d['date'] != today_str]
    history.append(new_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("🚀 資料確認為最新，更新完畢！")

if __name__ == "__main__":
    main()
