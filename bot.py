import json import websocket import time from datetime import datetime, timedelta, timezone from collections import deque import threading import os import requests from dotenv import load_dotenv

=== Load environment variables ===

load_dotenv()

TOKEN = os.getenv("TOKEN") APP_ID = os.getenv("APP_ID") ACCOUNT_ID = os.getenv("ACCOUNT_ID")

=== Symbol Config ===

SYMBOLS = [ "R_10", "R_10_1s", "R_25", "R_25_1s", "R_50", "R_50_1s", "R_75", "R_75_1s", "R_100", "R_100_1s" ]

TIMEFRAMES = { "M1": 60, "M5": 300, "M15": 900 }

SYMBOL_CONFIG = { sym: { "stake": 1, "duration": 1 if "1s" in sym else 5, "timeframes": ["M1"] if "1s" in sym else ["M5", "M15"] } for sym in SYMBOLS }

POSITIONS_FILE = "positions.json" LOG_FILE = "trading_log.txt"

candles_data = {symbol: {tf: {} for tf in SYMBOL_CONFIG[symbol]["timeframes"]} for symbol in SYMBOLS} volumes = {symbol: {tf: deque(maxlen=20) for tf in SYMBOL_CONFIG[symbol]["timeframes"]} for symbol in SYMBOLS} TICK_COUNTER = {symbol: 0 for symbol in SYMBOLS} LAST_ACTIVITY = time.time() ACTIVE_POSITIONS = {}

=== Log Function ===

def log_message(message): timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S') log_entry = f"[{timestamp}] {message}" print(log_entry) with open(LOG_FILE, 'a') as f: f.write(log_entry + "\n")

=== Position Handling ===

def load_positions(): if os.path.exists(POSITIONS_FILE): try: with open(POSITIONS_FILE, 'r') as f: data = json.load(f) for symbol in SYMBOLS: if symbol not in data: data[symbol] = { "active": False, "stake": SYMBOL_CONFIG[symbol]["stake"], "history": [] } return data except Exception as e: log_message(f"⚠️ Erreur de chargement des positions: {e}")

return {symbol: {
    "active": False,
    "stake": SYMBOL_CONFIG[symbol]["stake"],
    "history": []
} for symbol in SYMBOLS}

def save_positions(data): with open(POSITIONS_FILE, 'w') as f: json.dump(data, f, indent=2)

positions = load_positions()

=== Candlestick Builder ===

def build_candles(symbol, tf_name, tick): tf_sec = TIMEFRAMES[tf_name] timestamp = tick['epoch'] period = timestamp - (timestamp % tf_sec) price = tick["quote"]

if period not in candles_data[symbol][tf_name]:
    candles_data[symbol][tf_name][period] = {
        "time": datetime.fromtimestamp(period, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": 1
    }
else:
    candle = candles_data[symbol][tf_name][period]
    candle["high"] = max(candle["high"], price)
    candle["low"] = min(candle["low"], price)
    candle["close"] = price
    candle["volume"] += 1

=== Signal Detection ===

def detect_signal(symbol, tf, prev, curr): vol = curr["volume"] avg_vol = sum(volumes[symbol][tf]) / len(volumes[symbol][tf]) if volumes[symbol][tf] else 0 volumes[symbol][tf].append(vol)

is_bullish = curr["close"] > curr["open"] and curr["open"] < prev["close"] and curr["close"] > prev["open"]
is_bearish = curr["close"] < curr["open"] and curr["open"] > prev["close"] and curr["close"] < prev["open"]

if vol > avg_vol * 1.5:
    if is_bullish:
        execute_trade(symbol, "CALL", tf)
    elif is_bearish:
        execute_trade(symbol, "PUT", tf)

=== Execute Trade ===

def execute_trade(symbol, direction, timeframe): pos = positions[symbol] if pos["active"]: return

config = SYMBOL_CONFIG[symbol]
stake = config["stake"]
duration = config["duration"]

payload = {
    "buy": 1,
    "price": stake,
    "parameters": {
        "amount": stake,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD",
        "duration": duration,
        "duration_unit": "m",
        "symbol": symbol
    }
}

response = requests.post(
    "https://api.deriv.com/binary/v3/buy",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json=payload
)

if response.status_code == 200 and "error" not in response.json():
    result = response.json()
    log_message(f"🚀 Trade ouvert: {symbol} | {direction} | ${stake}")
    pos["active"] = True
    pos["entry_time"] = datetime.now().isoformat()
    pos["direction"] = direction
    pos["contract_id"] = result.get("contract_id")
    pos["history"].append({"time": pos["entry_time"], "direction": direction, "stake": stake, "timeframe": timeframe})
    save_positions(positions)
    ACTIVE_POSITIONS[symbol] = pos
else:
    log_message(f"❌ Trade échoué pour {symbol}: {response.text}")

=== Analyze Loop ===

def analyze_market(): while True: for symbol in SYMBOLS: for tf in SYMBOL_CONFIG[symbol]["timeframes"]: cs = list(candles_data[symbol][tf].values()) if len(cs) >= 2: detect_signal(symbol, tf, cs[-2], cs[-1]) time.sleep(5)

=== Tick Management ===

def on_tick(ws, message): data = json.loads(message) if "tick" in data: tick = data["tick"] symbol = tick["symbol"] TICK_COUNTER[symbol] += 1 for tf in SYMBOL_CONFIG[symbol]["timeframes"]: build_candles(symbol, tf, tick)

=== WebSocket Callbacks ===

def on_open(ws): ws.send(json.dumps({"authorize": TOKEN})) time.sleep(1) for sym in SYMBOLS: ws.send(json.dumps({"ticks": sym, "subscribe": 1})) log_message("✅ Abonné aux symboles.") threading.Thread(target=analyze_market, daemon=True).start()

def main(): log_message("🚀 Lancement du bot avec .env") ws = websocket.WebSocketApp( f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}", on_open=on_open, on_message=on_tick, on_error=lambda ws, e: log_message(f"❌ WebSocket erreur: {e}"), on_close=lambda ws, *args: log_message("🔌 WebSocket fermé") ) while True: try: ws.run_forever() except Exception as e: log_message(f"⚠️ Crash WebSocket: {e}") time.sleep(5) log_message("♻️ Reconnexion...")

if name == "main": main()

