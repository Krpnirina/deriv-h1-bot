# gold_volume_strategy.py
import websocket
import json
import time
import threading
from datetime import datetime
from statistics import mean

# --- Configuration ---
API_TOKEN = "REzKac9b5BR7DmF"
APP_ID = "71130"
SYMBOL = "XAUUSD"  # Gold
GRANULARITIES = {"H1": 3600, "M30": 1800, "M15": 900}
DURATION_SECONDS = 3600  # intervalle dynamique H1

# Trade rules
STAKE_AMOUNT = 1.00
MIN_TRADE_INTERVAL = 60 * 60  # At most 1 trade/hour

class GoldRiseFallBot:
    def __init__(self):
        self.ws = None
        self.last_trade_time = 0
        self.candle_data = {tf: [] for tf in GRANULARITIES}
        self.tick_volume = []  # List of ticks in current 1-hour window
        self.transaction_volume = []  # Simulated transaction volume
        self.lock = threading.Lock()

    def start(self):
        self.ws = websocket.WebSocketApp(
            f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        print(f"[{self.timestamp()}] Starting bot...")
        self.ws.run_forever()

    def on_open(self, ws):
        self.send({"authorize": API_TOKEN})
        time.sleep(1)
        for tf, gran in GRANULARITIES.items():
            self.send({
                "ticks_history": SYMBOL,
                "end": "latest",
                "count": 100,
                "granularity": gran,
                "style": "candles"
            })
        self.send({"ticks": SYMBOL})

    def on_message(self, ws, message):
        data = json.loads(message)
        if "error" in data:
            print("ERROR:", data["error"])
            return

        if "candles" in data:
            gran = data.get("echo_req", {}).get("granularity")
            tf = self.get_tf_from_granularity(gran)
            if tf:
                with self.lock:
                    self.candle_data[tf] = data["candles"]
                print(f"[{self.timestamp()}] Updated {tf} candles: {len(data['candles'])}")
                self.try_trade()

        elif "tick" in data:
            tick = data["tick"]
            with self.lock:
                self.tick_volume.append(tick)
                self.transaction_volume.append(self.simulate_transaction(tick))
            self.cleanup_tick_data()

    def try_trade(self):
        if time.time() - self.last_trade_time < MIN_TRADE_INTERVAL:
            return

        with self.lock:
            directions = []
            for tf in GRANULARITIES:
                if len(self.candle_data[tf]) >= 2:
                    c0, c1 = self.candle_data[tf][-2], self.candle_data[tf][-1]
                    dir_tf = self.analyze_direction(c1, self.tick_volume, self.transaction_volume)
                    if dir_tf:
                        directions.append(dir_tf)

            if len(set(directions)) == 1:
                direction = directions[0]
                print(f"[{self.timestamp()}] Consensus direction: {direction}")
                self.place_trade(direction)
                self.last_trade_time = time.time()

    def analyze_direction(self, last_candle, tick_vol, trans_vol):
        if not tick_vol or not trans_vol:
            return None

        tick_count = len(tick_vol)
        total_trans = sum(trans_vol)
        trans_stronger = total_trans > tick_count

        is_bullish = last_candle['close'] > last_candle['open']
        is_bearish = last_candle['close'] < last_candle['open']

        if trans_stronger and is_bearish:
            return "PUT"
        elif trans_stronger and is_bullish:
            return "CALL"
        elif not trans_stronger and is_bearish:
            return "CALL"
        elif not trans_stronger and is_bullish:
            return "PUT"
        return None

    def simulate_transaction(self, tick):
        # Placeholder simulation for transaction volume
        return 1.0  # or random.gauss(1, 0.1)

    def place_trade(self, direction):
        proposal = {
            "proposal": 1,
            "amount": STAKE_AMOUNT,
            "basis": "stake",
            "contract_type": direction,
            "currency": "USD",
            "duration": 60,
            "duration_unit": "m",
            "symbol": SYMBOL
        }
        self.send(proposal)

    def cleanup_tick_data(self):
        cutoff = time.time() - DURATION_SECONDS
        self.tick_volume = [t for t in self.tick_volume if t['epoch'] > cutoff]
        self.transaction_volume = self.transaction_volume[-len(self.tick_volume):]

    def get_tf_from_granularity(self, gran):
        for tf, g in GRANULARITIES.items():
            if g == gran:
                return tf
        return None

    def send(self, msg):
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(msg))

    def on_error(self, ws, error):
        print(f"[{self.timestamp()}] Error:", error)

    def on_close(self, ws, code, reason):
        print(f"[{self.timestamp()}] Connection closed: {reason}. Reconnecting...")
        time.sleep(10)
        self.start()

    def timestamp(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    bot = GoldRiseFallBot()
    bot.start()
