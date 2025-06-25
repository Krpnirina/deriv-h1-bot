import json
import websocket
import time
from datetime import datetime, timedelta, timezone
from collections import deque
import threading
import os
from dotenv import load_dotenv
import random

# === Enhanced Configuration ===
load_dotenv()
TOKEN = os.getenv("DERIV_TOKEN") or "REzKac9b5BR7DmF"
APP_ID = 71130
STAKE_AMOUNT = 0.35
ACCOUNT_ID = "VRTC1597457"

# Selected symbols for better stability
SYMBOLS = [
    "R_50", "R_75", "R_100",
    "1HZ50V", "1HZ100V"
]

LOG_FILE = "trading_v2.log"
MAX_RECONNECT_ATTEMPTS = 10
PING_INTERVAL = 25  # seconds

class EnhancedDerivBot:
    def __init__(self):
        self.ws = None
        self.candles = {s: deque(maxlen=100) for s in SYMBOLS}
        self.current_ticks = {s: [] for s in SYMBOLS}
        self.last_trade_time = {s: None for s in SYMBOLS}
        self.reconnect_attempts = 0
        self.last_message_time = time.time()
        self.connection_active = False
        self.lock = threading.Lock()
        self.setup_logging()
        
    def setup_logging(self):
        """Enhanced logging setup with rotation"""
        if not os.path.exists(LOG_FILE):
            open(LOG_FILE, 'w').close()
        else:
            # Simple log rotation
            if os.path.getsize(LOG_FILE) > 5 * 1024 * 1024:  # 5MB
                os.rename(LOG_FILE, f"{LOG_FILE}.bak")

    def log(self, message):
        """Thread-safe logging with timestamp"""
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        with open(LOG_FILE, "a") as f:
            f.write(log_entry + "\n")

    def connect_websocket(self):
        """Enhanced connection method with retry logic"""
        self.log("🔗 Connecting to Deriv WebSocket (v2)...")
        
        # Reset connection state
        self.connection_active = False
        self.reconnect_attempts += 1
        
        websocket.enableTrace(False)  # Disable verbose logging
        self.ws = websocket.WebSocketApp(
            f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Start connection monitor
        if not hasattr(self, 'monitor_thread') or not self.monitor_thread.is_alive():
            self.monitor_thread = threading.Thread(target=self.monitor_connection)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
        self.ws.run_forever(
            ping_interval=PING_INTERVAL,
            ping_timeout=10,
            reconnect=5  # Automatic reconnection attempts
        )

    def monitor_connection(self):
        """Monitor connection health"""
        while True:
            time.sleep(30)
            if not self.connection_active:
                continue
                
            inactive_time = time.time() - self.last_message_time
            if inactive_time > 90:  # No messages for 90 seconds
                self.log(f"⚠️ Connection inactive for {inactive_time:.0f}s - Reconnecting...")
                self.safe_reconnect()
            elif inactive_time > 45:
                self.log(f"ℹ️ Connection inactive for {inactive_time:.0f}s - Sending ping...")
                self.send_ping()

    def send_ping(self):
        """Send ping to keep connection alive"""
        try:
            if self.ws and self.connection_active:
                self.ws.send(json.dumps({"ping": 1}))
        except Exception as e:
            self.log(f"❌ Ping failed: {str(e)}")

    def safe_reconnect(self):
        """Graceful reconnection"""
        try:
            if self.ws:
                self.ws.close()
            time.sleep(5 + random.randint(0, 5))  # Random delay to avoid thundering herd
            self.connect_websocket()
        except Exception as e:
            self.log(f"❌ Reconnect failed: {str(e)}")

    def on_open(self, ws):
        """Enhanced on_open with connection tracking"""
        self.log("✅ WebSocket Connected (v2)")
        self.connection_active = True
        self.reconnect_attempts = 0
        self.last_message_time = time.time()
        
        # Authenticate
        ws.send(json.dumps({"authorize": TOKEN}))
        time.sleep(1)  # Small delay for auth
        
        # Subscribe to symbols with staggered start
        for i, symbol in enumerate(SYMBOLS):
            time.sleep(0.3)  # Reduce connection load
            ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
            self.log(f"🔔 Subscribed to {symbol}")

    def on_message(self, ws, message):
        """Enhanced message handling"""
        self.last_message_time = time.time()
        
        try:
            data = json.loads(message)
            
            if "error" in data:
                self.log(f"❌ API Error: {data['error']['message']}")
                if data['error'].get('code') == 'AuthorizationFailed':
                    self.log("🛑 Critical auth error - stopping bot")
                    os._exit(1)
                    
            elif "tick" in data:
                self.process_tick(data["tick"])
                
            elif data.get("msg_type") == "ping":
                self.log("🏓 Ping received")
                
        except Exception as e:
            self.log(f"❌ Message processing error: {str(e)}")

    def process_tick(self, tick):
        """Thread-safe tick processing"""
        try:
            symbol = tick["symbol"]
            if symbol not in SYMBOLS:
                return
                
            with self.lock:
                self.current_ticks[symbol].append({
                    "time": tick["epoch"],
                    "quote": tick["quote"]
                })
                
                # Process candle if we have enough ticks
                if len(self.current_ticks[symbol]) >= 5:
                    self.build_candle(symbol)
                    
        except Exception as e:
            self.log(f"❌ Tick processing error for {symbol}: {str(e)}")

    def build_candle(self, symbol):
        """Improved candle building with error handling"""
        try:
            now = datetime.now(timezone.utc)
            rounded = now.replace(minute=0, second=0, microsecond=0)
            ticks = self.current_ticks[symbol]
            
            if not ticks:
                return
                
            # Get ticks for current hour
            recent = [t for t in ticks 
                     if datetime.fromtimestamp(t["time"], timezone.utc) >= rounded]
            
            if len(recent) < 3:
                return
                
            opens = recent[0]["quote"]
            highs = max(t["quote"] for t in recent)
            lows = min(t["quote"] for t in recent)
            closes = recent[-1]["quote"]
            volume = len(recent)
            
            new_candle = {
                "time": rounded.isoformat(),
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volume
            }
            
            self.candles[symbol].append(new_candle)
            self.current_ticks[symbol] = []
            
            # Analyze strategy if we have enough candles
            if len(self.candles[symbol]) >= 10:
                self.analyze_strategy(symbol)
                
        except Exception as e:
            self.log(f"❌ Candle build error for {symbol}: {str(e)}")
            self.current_ticks[symbol] = []

    def analyze_strategy(self, symbol):
        """Enhanced strategy analysis"""
        try:
            candles = list(self.candles[symbol])
            last = candles[-1]
            prev = candles[-2]
            
            # Calculate dynamic support/resistance
            lookback = min(20, len(candles))
            lows = [c["low"] for c in candles[-lookback:]]
            highs = [c["high"] for c in candles[-lookback:]]
            support = min(lows)
            resistance = max(highs)
            
            current_price = last["close"]
            volume_condition = last["volume"] > prev["volume"] * 1.2
            proximity_threshold = 0.002
            
            # Support test with volume confirmation
            if (abs(current_price - support)/support < proximity_threshold 
                and volume_condition 
                and current_price < prev["close"]):
                
                self.log(f"📊 Strong CALL signal on {symbol} (Support: {support:.5f})")
                self.open_position(symbol, "CALL")
            
            # Resistance test with volume confirmation
            elif (abs(current_price - resistance)/resistance < proximity_threshold 
                  and volume_condition 
                  and current_price > prev["close"]):
                
                self.log(f"📊 Strong PUT signal on {symbol} (Resistance: {resistance:.5f})")
                self.open_position(symbol, "PUT")
                
        except Exception as e:
            self.log(f"❌ Strategy analysis error for {symbol}: {str(e)}")

    def open_position(self, symbol, direction):
        """Enhanced trade execution with cooldown"""
        try:
            now = datetime.now(timezone.utc)
            
            # Check cooldown period
            if (self.last_trade_time[symbol] and 
                (now - self.last_trade_time[symbol]).total_seconds() < 3600):
                self.log(f"⏳ Trade skipped: {symbol} in cooldown")
                return
                
            # Prepare trade
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
            
            # Execute trade
            self.ws.send(json.dumps(proposal))
            self.last_trade_time[symbol] = now
            self.log(f"📥 Trade sent: {direction} on {symbol} for 1h (${STAKE_AMOUNT})")
            
        except Exception as e:
            self.log(f"❌ Trade execution failed for {symbol}: {str(e)}")

    def on_error(self, ws, error):
        """Enhanced error handling"""
        self.log(f"❌ WebSocket Error: {str(error)}")
        self.connection_active = False
        
    def on_close(self, ws, close_status_code, close_msg):
        """Enhanced close handling"""
        self.log(f"🔌 Disconnected: {close_status_code} - {close_msg}")
        self.connection_active = False
        
        # Exponential backoff for reconnection
        delay = min(5 * (2 ** self.reconnect_attempts), 60)
        delay += random.uniform(0, 5)  # Add jitter
        self.log(f"⏳ Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts})")
        
        time.sleep(delay)
        self.safe_reconnect()

    def run(self):
        """Start the enhanced bot"""
        self.log("🚀 Starting Enhanced Deriv Trading Bot v2.0")
        self.log(f"📊 Monitoring {len(SYMBOLS)} symbols: {', '.join(SYMBOLS)}")
        self.connect_websocket()

if __name__ == "__main__":
    bot = EnhancedDerivBot()
    bot.run()
