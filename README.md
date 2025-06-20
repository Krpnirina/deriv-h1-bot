# 🤖 DerivBot - Trading Automatique sur Deriv

Ce bot connecte à la plateforme **Deriv** via WebSocket et exécute des positions CALL/PUT d'une heure automatiquement selon une stratégie basée sur les niveaux de **support/résistance** et la **divergence volume/prix**.

---

## ⚙️ Fonctionnalités

- 📈 Abonnement automatique aux ticks en temps réel
- 🕐 Construction de chandeliers H1 (OHLC + volume)
- 🧠 Détection automatique des supports/résistances
- 🔍 Analyse de divergence volume/prix
- 📤 Envoi de trades CALL/PUT de 1 heure
- 📝 Système de journalisation (fichier `trading.log`)

---

## 🧪 Stratégie utilisée

> Lorsqu’un prix se rapproche d’un support ou d’une résistance, le bot:
- Vérifie s’il y a divergence haussière ou baissière sur le volume
- Si oui, il place un **trade CALL (vers le haut)** ou **PUT (vers le bas)**

---

## 📦 Installation

```bash
git clone https://github.com/votre-utilisateur/deriv-bot.git
cd deriv-bot
pip install -r requirements.txt
