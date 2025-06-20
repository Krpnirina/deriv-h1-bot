import json
import websocket
import time
from datetime import datetime, timedelta, timezone
from collections import deque
import threading
import os
from dotenv import load_dotenv

# === Configuration ===
load_dotenv()
TOKEN = os.getenv("DERIV_TOKEN") or "REzKac9b5BR7DmF"  # Secure token
APP_ID = 71130
STAKE_AMOUNT = 0.35
ACCOUNT_ID = "VRTC1597457"

# Symbols: classic + 1s
SYMBOLS = [
    "R_10", "R_25", "R_50", "R_75", "R_100",
    "1HZ10V", "1HZ25V", "1HZ50V", "1HZ75V", "1HZ100V", "1HZ150V"
]

LOG_FILE = "trading.log"

class DerivBot:
    def __init__(self):
        self.ws = None
        self.candles = {s: [] for s in SYMBOLS}
        self.current_ticks = {s: [] for s in SYMBOLS}
        self.last_trade_time = {s: None for s in SYMBOLS}
        self.setup_logging()
        self.lock = threading.Lock()

    def setup_logging(self):
        if not os.path.exists(LOG_FILE):
            open(LOG_FILE, 'w').close()

    def log(self, message):
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry + "\n")

    def connect_websocket(self):
        self.log("🔗 Connexion au WebSocket Deriv...")
        self.ws = websocket.WebSocketApp(
            f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    def on_open(self, ws):
        self.log("✅ Connecté au WebSocket")
        ws.send(json.dumps({"authorize": TOKEN}))
        time.sleep(1)
        for symbol in SYMBOLS:
            ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
            self.log(f"🔔 Abonné à {symbol}")

    def on_message(self, ws, message):
        data = json.loads(message)
        if "error" in data:
            self.log(f"❌ Erreur API: {data['error']['message']}")
        elif "tick" in data:
            self.process_tick(data["tick"])

    def process_tick(self, tick):
        symbol = tick["symbol"]
        epoch = tick["epoch"]
        quote = tick["quote"]

        with self.lock:
            self.current_ticks[symbol].append({"time": epoch, "quote": quote})
            self.build_candle(symbol)

    def build_candle(self, symbol):
        now = datetime.now(timezone.utc)
        rounded = now.replace(minute=0, second=0, microsecond=0)
        ticks = self.current_ticks[symbol]
        recent = [t for t in ticks if datetime.fromtimestamp(t["time"], timezone.utc) >= rounded]

        if len(recent) < 3:
            return

        opens = recent[0]["quote"]
        highs = max(t["quote"] for t in recent)
        lows = min(t["quote"] for t in recent)
        closes = recent[-1]["quote"]
        volume = len(recent)

        self.candles[symbol].append({
            "time": rounded.isoformat(),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volume
        })

        if len(self.candles[symbol]) > 50:
            self.candles[symbol] = self.candles[symbol][-50:]

        self.current_ticks[symbol] = []
        self.analyze_strategy(symbol)

    def analyze_strategy(self, symbol):
        candles = self.candles[symbol]
        if len(candles) < 10:
            return

        lows = [c["low"] for c in candles[-20:]]
        highs = [c["high"] for c in candles[-20:]]
        support = min(lows)
        resistance = max(highs)

        last = candles[-1]
        price = last["close"]
        volume = last["volume"]
        prev = candles[-2]

        volume_div = volume > prev["volume"] * 1.2
        price_down = price < prev["close"]
        price_up = price > prev["close"]

        proximity_threshold = 0.002

        if abs(price - support) / support < proximity_threshold and volume_div and price_down:
            self.log(f"📊 Signal CALL on {symbol}")
            self.open_position(symbol, "CALL")

        elif abs(price - resistance) / resistance < proximity_threshold and volume_div and price_up:
            self.log(f"📊 Signal PUT on {symbol}")
            self.open_position(symbol, "PUT")

    def open_position(self, symbol, direction):
        now = datetime.now(timezone.utc)
        if self.last_trade_time[symbol] and (now - self.last_trade_time[symbol]).total_seconds() < 3600:
            return  # Already traded within the past hour

        proposal = {
            "buy": 1,
            "price": STAKE_AMOUNT,
            "parameters": {
                "amount": STAKE_AMOUNT,
                "basis": "stake",
                "contract_type": direction,
                "currency": "USD",
                "duration": 60,
                "duration_unit": "m",
                "symbol": symbol
            }
        }
        self.ws.send(json.dumps(proposal))
        self.last_trade_time[symbol] = now
        self.log(f"📥 Trade sent: {direction} on {symbol} for 1h")

    def on_error(self, ws, error):
        self.log(f"❌ WebSocket Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        self.log(f"🔌 Déconnecté: {close_status_code} - {close_msg}")
        time.sleep(5)
        self.connect_websocket()

    def run(self):
        self.log("🚀 Démarrage du Bot de Trading Deriv")
        threading.Thread(target=self.connect_websocket).start()

if __name__ == "__main__":
    bot = DerivBot()
    bot.run()
