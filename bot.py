import json import websocket import time from datetime import datetime, timedelta, timezone from collections import deque import threading import os import requests from dotenv import load_dotenv

=== Charger les variables d'environnement ===

load_dotenv() APP_ID = os.getenv("APP_ID") TOKEN = os.getenv("TOKEN") ACCOUNT_ID = os.getenv("ACCOUNT_ID")

=== Configuration générale ===

SYMBOLS = [ "R_10", "R_10_1s", "R_25", "R_25_1s", "R_50", "R_50_1s", "R_75", "R_75_1s", "R_100", "R_100_1s" ]

TIMEFRAMES = { "M1": 60, "M5": 300, "M15": 900 }

SYMBOL_CONFIG = { "R_10": {"stake": 1, "duration": 5, "timeframes": ["M5", "M15"]}, "R_10_1s": {"stake": 1, "duration": 1, "timeframes": ["M1"]}, "R_25": {"stake": 1, "duration": 5, "timeframes": ["M5", "M15"]}, "R_25_1s": {"stake": 1, "duration": 1, "timeframes": ["M1"]}, "R_50": {"stake": 1, "duration": 5, "timeframes": ["M5", "M15"]}, "R_50_1s": {"stake": 1, "duration": 1, "timeframes": ["M1"]}, "R_75": {"stake": 1, "duration": 5, "timeframes": ["M5", "M15"]}, "R_75_1s": {"stake": 1, "duration": 1, "timeframes": ["M1"]}, "R_100": {"stake": 1, "duration": 5, "timeframes": ["M5", "M15"]}, "R_100_1s": {"stake": 1, "duration": 1, "timeframes": ["M1"]} }

POSITIONS_FILE = "positions.json" LOG_FILE = "trading_log.txt"

candles_data = {symbol: {tf: {} for tf in TIMEFRAMES if tf in SYMBOL_CONFIG[symbol]["timeframes"]} for symbol in SYMBOLS} volumes = {symbol: {tf: deque(maxlen=20) for tf in TIMEFRAMES if tf in SYMBOL_CONFIG[symbol]["timeframes"]} for symbol in SYMBOLS} TICK_COUNTER = {symbol: 0 for symbol in SYMBOLS} ACTIVE_POSITIONS = {}

=== Fonctions auxiliaires ===

def log_message(msg): timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") message = f"[{timestamp}] {msg}" print(message) with open(LOG_FILE, "a") as f: f.write(message + "\n")

def timestamp_to_str(epoch): return datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

def load_positions(): if os.path.exists(POSITIONS_FILE): with open(POSITIONS_FILE, 'r') as f: return json.load(f) return {symbol: {"active": False, "stake": SYMBOL_CONFIG[symbol]["stake"], "history": []} for symbol in SYMBOLS}

def save_positions(data): with open(POSITIONS_FILE, 'w') as f: json.dump(data, f, indent=2)

positions = load_positions()

=== Construction chandelier + Volume ===

def build_candles(symbol, tf, tick): try: tf_sec = TIMEFRAMES[tf] ts = tick['epoch'] price = tick['quote'] period = ts - (ts % tf_sec)

if period not in candles_data[symbol][tf]:
        candles_data[symbol][tf][period] = {
            "time": timestamp_to_str(period),
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1
        }
    else:
        c = candles_data[symbol][tf][period]
        c["high"] = max(c["high"], price)
        c["low"] = min(c["low"], price)
        c["close"] = price
        c["volume"] += 1
except Exception as e:
    log_message(f"Erreur build_candles {symbol}/{tf}: {e}")

=== Détection de signaux ===

def detect_signal(symbol, tf, prev, curr): try: vol = curr["volume"] avg_vol = sum(volumes[symbol][tf]) / len(volumes[symbol][tf]) if volumes[symbol][tf] else 0 volumes[symbol][tf].append(vol)

is_bullish = curr["close"] > curr["open"] and curr["open"] < prev["close"] and curr["close"] > prev["open"]
    is_bearish = curr["close"] < curr["open"] and curr["open"] > prev["close"] and curr["close"] < prev["open"]

    if vol > avg_vol * 1.5:
        if is_bullish:
            execute_trade(symbol, "CALL", tf)
        elif is_bearish:
            execute_trade(symbol, "PUT", tf)
except Exception as e:
    log_message(f"Erreur détect. {symbol}/{tf}: {e}")

=== Exécution trade ===

def execute_trade(symbol, direction, tf): pos = positions[symbol] if pos["active"]: return

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

try:
    response = requests.post(
        "https://api.deriv.com/binary/v3/buy",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json=payload
    )
    if response.status_code == 200:
        result = response.json()
        log_message(f"Trade envoyé: {symbol} {direction} stake={stake}")
        pos["active"] = True
        pos["entry"] = datetime.now().isoformat()
        pos["history"].append({"tf": tf, "direction": direction, "stake": stake})
        save_positions(positions)
    else:
        log_message(f"Erreur API: {response.status_code}")
except Exception as e:
    log_message(f"Erreur execution trade {symbol}: {e}")

=== Analyse de marché ===

def analyze(): while True: try: for symbol in SYMBOLS: for tf in SYMBOL_CONFIG[symbol]["timeframes"]: cs = list(candles_data[symbol][tf].values()) if len(cs) < 2: continue detect_signal(symbol, tf, cs[-2], cs[-1]) time.sleep(5) except Exception as e: log_message(f"Erreur analyse: {e}") time.sleep(10)

=== Tick handler ===

def on_tick(ws, msg): data = json.loads(msg) if "tick" in data: tick = data["tick"] symbol = tick["symbol"] for tf in SYMBOL_CONFIG[symbol]["timeframes"]: build_candles(symbol, tf, tick)

=== WebSocket Handlers ===

def on_open(ws): ws.send(json.dumps({"authorize": TOKEN})) time.sleep(1) for s in SYMBOLS: ws.send(json.dumps({"ticks": s, "subscribe": 1})) log_message("✅ Connexion & souscriptions établies.") threading.Thread(target=analyze, daemon=True).start()

def main(): log_message("🚀 Bot lancé (Railway Ready)") url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}" ws = websocket.WebSocketApp( url, on_open=on_open, on_message=on_tick, on_error=lambda ws, e: log_message(f"Erreur WebSocket: {e}"), on_close=lambda ws, *args: log_message("🔌 WS Fermé") ) while True: try: ws.run_forever() except Exception as e: log_message(f"Crash WS: {e}") time.sleep(5) log_message("🔁 Reconnexion...")

if name == "main": main()

