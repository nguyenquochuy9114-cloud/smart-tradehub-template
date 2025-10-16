import os, time, requests, threading
import pandas as pd
from binance.client import Client
from telegram import Bot

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
INTERVAL = os.getenv("INTERVAL", "15m")
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", 0.8))
TOP_N = int(os.getenv("TOP_N", 300))

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
bot = Bot(BOT_TOKEN)

def fetch_top_symbols(limit=TOP_N):
    tickers = client.get_ticker()
    df = pd.DataFrame(tickers)
    df["quoteVolume"] = df["quoteVolume"].astype(float)
    df = df[df["symbol"].str.endswith("USDT")]
    df = df.sort_values("quoteVolume", ascending=False).head(limit)
    return df["symbol"].tolist()

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def analyze_coin(symbol):
    klines = client.get_klines(symbol=symbol, interval=INTERVAL, limit=100)
    closes = pd.Series([float(x[4]) for x in klines])
    volume = pd.Series([float(x[5]) for x in klines])

    rsi = calc_rsi(closes).iloc[-1]
    ema_short = closes.ewm(span=20).mean().iloc[-1]
    ema_long = closes.ewm(span=50).mean().iloc[-1]

    ema_signal = 1 if ema_short > ema_long else -1
    rsi_signal = 1 if rsi < 70 and rsi > 30 else 0
    volume_signal = 1 if volume.iloc[-1] > volume.mean() else 0

    score = (rsi_signal * 0.2 + ema_signal * 0.5 + volume_signal * 0.3 + 1) / 2
    return score, rsi, ema_signal, volume_signal

def send_alert(symbol, score, rsi, ema_signal, vol):
    msg = (
        f"📊 *{symbol}* Alert\n"
        f"RSI: {rsi:.1f}\n"
        f"EMA Trend: {'Tăng' if ema_signal>0 else 'Giảm'}\n"
        f"Volume: {'Tăng' if vol>0 else 'Thấp'}\n"
        f"Xác suất: {score*100:.1f}%"
    )
    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

def main():
    symbols = fetch_top_symbols()
    while True:
        for sym in symbols:
            try:
                score, rsi, ema, vol = analyze_coin(sym)
                if score >= SCORE_THRESHOLD:
                    send_alert(sym, score, rsi, ema, vol)
            except Exception as e:
                print(f"Lỗi {sym}: {e}")
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=main).start()
