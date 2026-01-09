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

# 偽裝成一般的瀏覽器
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
}

def clean_number(text):
    """
    清洗工具：把 '即期買入匯率31.5280' 變回 '31.5280'
    """
    if not text: return "-"
    # 只抓取「數字」與「小數點」
    match = re.search(r'\d+\.\d+', text)
    if match:
        return match.group(0)
    return text.strip()

def get_bot_rates():
    """抓取台銀"""
    print("正在抓取台銀...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        resp = requests.get("https://rate.bot.com.tw/xrt?Lang=zh-TW", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
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
    return res

def get_sunny_rates():
    """抓取陽信 (新版網址 + 智慧清洗)"""
    print("正在抓取陽信...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        # ✅ 更新：使用公開的即時匯率查詢頁面
        url = "https://www.sunnybank.com.tw/portal/pt/pt02003/PT02003Index.xhtml"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"❌ 陽信連線異常: {resp.status_code}")
            return res

        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr')
        
        for row in rows:
            # 取得整列文字，移除空白
            raw_text = row.get_text(strip=True)
            tds = row.find_all('td')
            
            # 陽信新版表格通常是：幣別 | 現鈔買 | 現鈔賣 | 即期買(Index 3) | 即期賣(Index 4)
            if len(tds) >= 5:
                # 抓美金
                if ("美元" in raw_text or "USD" in raw_text):
                    # 使用 clean_number 去除可能參雜的中文字
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy and sell and buy != "-":
                        res["USD"] = [buy, sell]
                
                # 抓人民幣
                if ("人民幣" in raw_text or "CNY" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy and sell and buy != "-":
                        res["CNY"] = [buy, sell]

        if res["USD"][0] != "-":
            print(f"✅ 陽信抓取成功: {res}")
        else:
            print("⚠️ 陽信連線成功但未找到數值 (可能是網頁改版或無資料)")

    except Exception as e:
        print(f"❌ 陽信發生錯誤: {e}")
    
    return res

def main():
    today = datetime.now(TW_TZ)
    date_str = today.strftime('%Y-%m-%d')
    print(f"📅 執行日期: {date_str}")

    bot_res = get_bot_rates()
    time.sleep(2)
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

    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content: history = json.load(f)
        except: pass
    
    # 更新資料
    history = [d for d in history if d['date'] != date_str]
    history.append(new_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("🚀 資料更新完畢！")

if __name__ == "__main__":
    main()
