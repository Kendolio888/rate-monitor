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
    # 升級版：支援整數或小數 (例如 31 或 31.5 都能抓)
    match = re.search(r'\d+(\.\d+)?', text)
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
    """抓取陽信"""
    print("正在抓取陽信...")
    res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        # 使用公開的即時匯率查詢頁面
        url = "https://www.sunnybank.com.tw/portal/pt/pt02003/PT02003Index.xhtml"
        resp = requests.get(url, headers=HEADERS, timeout=20)
        
        if resp.status_code != 200:
            print(f"❌ 陽信連線異常: {resp.status_code}")
            return res

        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.find_all('tr')
        
        for row in rows:
            raw_text = row.get_text(strip=True)
            tds = row.find_all('td')
            
            if len(tds) >= 5:
                # 抓美金 (關鍵字增加：美元、美金、USD)
                if ("美元" in raw_text or "美金" in raw_text or "USD" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    # 只要不是 "-" 就收錄
                    if buy != "-":
                        res["USD"] = [buy, sell]
                
                # 抓人民幣 (關鍵字增加：人民幣、CNY)
                if ("人民幣" in raw_text or "CNY" in raw_text):
                    buy = clean_number(tds[3].text)
                    sell = clean_number(tds[4].text)
                    if buy != "-":
                        res["CNY"] = [buy, sell]

        if res["USD"][0] != "-" or res["CNY"][0] != "-":
            print(f"✅ 陽信抓取結果: {res}")
        else:
            print("⚠️ 陽信抓取但無數值 (請檢查 Log)")

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
    
    history = [d for d in history if d['date'] != date_str]
    history.append(new_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("🚀 資料更新完畢！")

if __name__ == "__main__":
    main()
