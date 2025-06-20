# 🤖 Bot de Trading Automatique Deriv

Ce projet est un bot de trading automatique pour les indices Volatility de Deriv.com. Il :

- Analyse 10 symboles en temps réel
- Construit des chandeliers M1, M5, M15
- Détecte des patterns de retournement (engulfing)
- Filtre par volume élevé
- Ouvre un seul trade par symbole à la fois
- Suit l’historique des positions
- Simule la clôture après expiration

---

## 🔧 Technologies

- Python 3.10+
- `websocket-client`
- `requests`
- `dotenv`

---

## ⚙️ Variables d’environnement `.env`

```env
APP_ID=71130
TOKEN=REzKac9b5BR7DmF
ACCOUNT_ID=VRTC1597457
