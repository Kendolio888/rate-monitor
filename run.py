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

# 強力偽裝：讓程式看起來像真的 Chrome 瀏覽器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

def clean_number(text):
    """
    小工具：把 '即期買入31.5' 這種字串洗成 '31.5'
    """
    if not text: return "-"
    # 透過正則表達式只抓取數字和小數點
    match = re.search(r'\d+\.\d+', text)
    if match:
        return match.group(0)
    return text.strip()

def get_bot_rates():
    """抓取台銀 (即期)"""
    print("正在抓取台銀...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        resp = requests.get("https://rate.bot.com.tw/xrt?Lang=zh-TW", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for row in soup.find_all('tr'):
            text = row.text.strip()
            # 台銀直接找 data-table 屬性，最準確
            if "美金" in text:
                buy = row.find('td', {'data-table': '本行即期買入'}).text.strip()
                sell = row.find('td', {'data-table': '本行即期賣出'}).text.strip()
                res["USD"] = [buy, sell]
            if "人民幣" in text:
                buy = row.find('td', {'data-table': '本行即期買入'}).text.strip()
                sell = row.find('td', {'data-table': '本行即期賣出'}).text.strip()
                res["CNY"] = [buy, sell]
        print(f"✅ 台銀抓取成功: {res}")
    except Exception as e:
        print(f"❌ 台銀失敗: {e}")
    return res

def get_sunny_rates():
    """抓取陽信 (鎖定即期 + 清洗文字)"""
    print("正在抓取陽信...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        url = "https://www.sunnybank.com.tw/net/Rate/RateQuery"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8' # 強制編碼避免亂碼
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr')
        
        for row in rows:
            # 移除所有空白，方便比對
            raw_text = row.get_text(strip=True)
            tds = row.find_all('td')
            
            # 陽信表格順序通常是：幣別(0) | 現金買(1) | 現金賣(2) | 即期買(3) | 即期賣(4)
            if len(tds) >= 5:
                # 抓美金
                if ("美元" in raw_text or "USD" in raw_text):
                    # 鎖定 index 3 和 4 (即期)
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    # 雙重確認：如果抓到的數字是空的，試試看有沒有可能是切換了版型? 
                    # (暫時維持鎖定3/4，因為這是最標準的結構)
                    if buy and sell:
                        res["USD"] = [buy, sell]
                
                # 抓人民幣
                if ("人民幣" in raw_text or "CNY" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy and sell:
                        res["CNY"] = [buy, sell]

        # 簡單檢查有沒有抓到
        if res["USD"][0] != "-":
            print(f"✅ 陽信抓取成功 (已確認為即期): {res}")
        else:
            print(f"⚠️ 陽信連線正常但沒抓到數值，可能網頁改版。Raw data length: {len(resp.text)}")

    except Exception as e:
        print(f"❌ 陽信失敗: {e}")
    
    return res

def main():
    # 取得台灣時間
    today = datetime.now(TW_TZ)
    date_str = today.strftime('%Y-%m-%d')
    print(f"📅 執行日期: {date_str}")

    # 執行抓取
    bot_res = get_bot_rates()
    time.sleep(2) # 休息2秒，模擬真人操作速度
    sunny_res = get_sunny_rates()
    
    new_data = {
        "date": date_str,
        "sunny_usd_buy": sunny_res["USD"][0], 
        "sunny_usd_sell": sunny_res["USD"][1],
        "sunny_cny_buy": sunny_res["CNY"][0], 
        "sunny_cny_sell": sunny_res["CNY"][1],
        "bot_usd_buy": bot_res["USD"][0], 
        "bot_usd_sell": bot_res["USD"][1],
        "bot_cny_buy": bot_res["CNY"][0], 
        "bot_cny_sell": bot_res["CNY"][1]
    }

    # 讀取舊檔
    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content: history = json.load(f)
        except: pass
    
    # 更新今天的資料
    history = [d for d in history if d['date'] != date_str]
    history.append(new_data)
    
    # 存檔
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("🚀 資料更新完畢！")

if __name__ == "__main__":
    main()
