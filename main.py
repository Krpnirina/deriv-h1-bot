# main.py
import websocket
import json
import time
import numpy as np
from statistics import mean
from datetime import datetime
import os

# --- Configuration from Environment ---
API_TOKEN = os.getenv('API_TOKEN', 'REzKac9b5BR7DmF')
APP_ID = os.getenv('APP_ID', '71130')
SYMBOL = os.getenv('SYMBOL', 'R_100')

# Paramètres de durée
DURATION_PROFILES = {
    'SHORT': {'duration': 5, 'volume_ratio': 3.0},
    'MEDIUM': {'duration': 60, 'volume_ratio': 2.5},
    'LONG': {'duration': 1440, 'volume_ratio': 2.0}
}

STAKE_AMOUNT = float(os.getenv('STAKE_AMOUNT', '0.35'))
MAX_TRADES = int(os.getenv('MAX_TRADES', '2'))
MIN_WAIT = int(os.getenv('MIN_WAIT', '60'))

# Timeframes
GRANULARITIES = {
    'H1': 3600,
    'H4': 14400,
    'M30': 1800
}

class DerivBot:
    def __init__(self):
        self.ws = None
        self.data = {tf: [] for tf in GRANULARITIES}
        self.trades_today = 0
        self.last_trade_time = 0
        self.active_trades = {}

    def start(self):
        """Lance la connexion WebSocket"""
        ws_url = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
        self.ws = websocket.WebSocketApp(ws_url,
                                      on_open=self._on_open,
                                      on_message=self._on_message,
                                      on_error=self._on_error,
                                      on_close=self._on_close)
        print(f"[{self._ts()}] Starting Deriv Bot...")
        self.ws.run_forever()

    def _on_open(self, ws):
        """Callback d'ouverture de connexion"""
        print(f"[{self._ts()}] Connected")
        self._auth()
        time.sleep(1)
        self._subscribe()

    def _auth(self):
        """Authentification"""
        self._send({"authorize": API_TOKEN})

    def _subscribe(self):
        """Abonnement aux données"""
        # Historical data
        for tf in GRANULARITIES:
            self._send({
                "ticks_history": SYMBOL,
                "end": "latest",
                "count": 100,
                "granularity": GRANULARITIES[tf],
                "style": "candles"
            })
        
        # Real-time ticks
        self._send({"ticks": SYMBOL})
        
        # Contract updates
        self._send({"proposal_open_contract": 1})

    def _on_message(self, ws, message):
        """Traitement des messages"""
        data = json.loads(message)
        
        if "error" in data:
            print(f"[{self._ts()}] ERROR: {data['error']['message']}")
            return
            
        if "candles" in data:
            self._process_candles(data)
        elif "tick" in data:
            self._process_tick(data['tick'])
        elif "proposal_open_contract" in data:
            self._process_contract(data['proposal_open_contract'])
        elif "buy" in data:
            self._process_trade(data['buy'])

    def _process_candles(self, data):
        """Traite les données de chandeliers"""
        tf = self._get_timeframe(data.get("granularity"))
        if tf:
            self.data[tf] = data.get("candles", [])
            print(f"[{self._ts()}] {tf} data updated: {len(self.data[tf])} candles")
            self._analyze()

    def _process_tick(self, tick):
        """Traite les ticks en temps réel"""
        print(f"[{self._ts()}] Tick: {tick['quote']}")
        self._analyze()

    def _process_contract(self, contract):
        """Traite les mises à jour de contrat"""
        if contract.get("contract_id"):
            self.active_trades[contract['contract_id']] = contract
            print(f"[{self._ts()}] Contract update: {contract['status']}")

    def _process_trade(self, trade):
        """Traite les résultats de trade"""
        if trade.get("error"):
            print(f"[{self._ts()}] Trade error: {trade['error']['message']}")
            return
            
        self.trades_today += 1
        self.last_trade_time = time.time()
        print(f"[{self._ts()}] Trade opened: {trade['longcode']}")

    def _analyze(self):
        """Analyse le marché et prend des décisions"""
        if not self._ready_to_trade():
            return

        # Analyse des volumes
        h1_volumes = [float(c['volume']) for c in self.data['H1'][-24:]]
        current_vol = h1_volumes[-1]
        avg_vol = mean(h1_volumes[:-1])
        vol_ratio = current_vol / avg_vol

        # Analyse de tendance
        trend = self._check_trend()
        
        # Sélection de la durée
        duration = self._select_duration(vol_ratio, trend['strength'])
        if not duration:
            return

        # Exécution du trade
        self._place_trade(trend['direction'], duration)

    def _check_trend(self):
        """Analyse la tendance multi-timeframe"""
        scores = []
        for tf in ['H4', 'H1']:
            candles = self.data.get(tf, [])
            if len(candles) >= 3:
                closes = [float(c['close']) for c in candles[-3:]]
                scores.append(1 if closes[-1] > closes[-2] else -1)
        
        strength = abs(mean(scores)) if scores else 0
        direction = "CALL" if mean(scores) > 0 else "PUT"
        
        return {'strength': strength, 'direction': direction}

    def _select_duration(self, vol_ratio, trend_str):
        """Sélectionne la durée optimale"""
        if trend_str > 0.8 and vol_ratio > 3.0:
            return DURATION_PROFILES['SHORT']['duration']
        elif trend_str > 0.7 and vol_ratio > 2.5:
            return DURATION_PROFILES['MEDIUM']['duration']
        elif trend_str > 0.6 and vol_ratio > 2.0:
            return DURATION_PROFILES['LONG']['duration']
        return None

    def _place_trade(self, direction, duration):
        """Place un trade"""
        proposal = {
            "proposal": 1,
            "amount": STAKE_AMOUNT,
            "basis": "stake",
            "contract_type": direction,
            "currency": "USD",
            "duration": duration,
            "duration_unit": "m",
            "symbol": SYMBOL
        }
        self._send(proposal)

    def _ready_to_trade(self):
        """Vérifie si on peut trader"""
        if self.trades_today >= MAX_TRADES:
            print(f"[{self._ts()}] Max trades reached")
            return False
            
        if time.time() - self.last_trade_time < MIN_WAIT:
            print(f"[{self._ts()}] Waiting between trades")
            return False
            
        return all(len(candles) > 0 for candles in self.data.values())

    def _get_timeframe(self, granularity):
        """Convertit la granularité en timeframe"""
        for tf, g in GRANULARITIES.items():
            if g == granularity:
                return tf
        return None

    def _send(self, message):
        """Envoie un message via WebSocket"""
        if self.ws and self.ws.sock and self.ws.sock.connected:
            self.ws.send(json.dumps(message))

    def _on_error(self, ws, error):
        print(f"[{self._ts()}] Error: {error}")

    def _on_close(self, ws, code, reason):
        print(f"[{self._ts()}] Closed. Reconnecting in 30s...")
        time.sleep(30)
        self.start()

    def _ts(self):
        """Retourne le timestamp formaté"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    bot = DerivBot()
    bot.start()