import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime, timezone, timedelta

# 設定台灣時間
TW_TZ = timezone(timedelta(hours=8))
DATA_FILE = 'data.json'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def get_rates():
    # 台銀
    bot_res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        soup = BeautifulSoup(requests.get("https://rate.bot.com.tw/xrt?Lang=zh-TW", headers=HEADERS).text, 'html.parser')
        for row in soup.find_all('tr'):
            if "美金" in row.text:
                bot_res["USD"] = [row.find('td', {'data-table': '本行即期買入'}).text.strip(), row.find('td', {'data-table': '本行即期賣出'}).text.strip()]
            if "人民幣" in row.text:
                bot_res["CNY"] = [row.find('td', {'data-table': '本行即期買入'}).text.strip(), row.find('td', {'data-table': '本行即期賣出'}).text.strip()]
    except: pass

    # 陽信
    sunny_res = {"USD": ["-","-"], "CNY": ["-","-"]}
    try:
        soup = BeautifulSoup(requests.get("https://www.sunnybank.com.tw/net/Rate/RateQuery", headers=HEADERS).text, 'html.parser')
        for row in soup.find_all('tr'):
            tds = row.find_all('td')
            if len(tds) > 4:
                if "美元" in row.text: sunny_res["USD"] = [tds[3].text.strip(), tds[4].text.strip()]
                if "人民幣" in row.text: sunny_res["CNY"] = [tds[3].text.strip(), tds[4].text.strip()]
    except: pass
    
    return bot_res, sunny_res

def main():
    today = datetime.now(TW_TZ)
    # 週末不抓
    if today.weekday() >= 5: 
        print("Weekend, skipping.")
        return

    date_str = today.strftime('%Y-%m-%d')
    bot, sunny = get_rates()
    
    new_data = {
        "date": date_str,
        "sunny_usd_buy": sunny["USD"][0], "sunny_usd_sell": sunny["USD"][1],
        "sunny_cny_buy": sunny["CNY"][0], "sunny_cny_sell": sunny["CNY"][1],
        "bot_usd_buy": bot["USD"][0], "bot_usd_sell": bot["USD"][1],
        "bot_cny_buy": bot["CNY"][0], "bot_cny_sell": bot["CNY"][1]
    }

    history = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: history = json.load(f)
        except: pass
    
    history = [d for d in history if d['date'] != date_str]
    history.append(new_data)
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    print("Update success")

if __name__ == "__main__":
    main()
