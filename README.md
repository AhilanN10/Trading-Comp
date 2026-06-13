# EMA Crossover Momentum Trading Bot (Private)

This is a private algorithmic trading bot optimized for **AMD**.

## 🚨 IMPORTANT: Security Warning
- **NEVER** upload `config.py` to GitHub. It contains your real API keys.
- A `.gitignore` file is configured to prevent this, but always double-check.
- If you ever accidentally expose your keys, **regenerate them immediately** on the Alpaca dashboard.

## 🚀 Quick Start (For You)

### 1. Setup Your Keys
You need to create a `config.py` file that holds your private credentials.
1.  Copy the template:
    ```bash
    cp config_example.py config.py
    ```
2.  Open `config.py` and paste your **Alpaca API Key** and **Secret Key**.
3.  **Paper vs. Live**:
    - Default is **Paper Trading** (`https://paper-api.alpaca.markets`).
    - To trade **Real Money**, change `BASE_URL` to `https://api.alpaca.markets`.

### 2. Run the Bot
To start the bot in your terminal:
```bash
python3 alpaca_sim/deploy.py
```

The bot will:
1.  Connect to your Alpaca account.
2.  Check the price of **AMD** every 30 seconds.
3.  **Buy** when:
    - Fast EMA (8-period) crosses **above** Slow EMA (25-period) on 30-minute bars.
    - Price is above the Macro Trend Filter (250-period EMA).
    - Current RSI(14) is below 65 (preventing buying when overbought).
4.  **Sell** when:
    - Fast EMA (8-period) crosses **below** Slow EMA (25-period) on 30-minute bars.

### 3. Monitoring
- The bot will print every action to the terminal.
- It saves its state (trailing stop levels) to `bot_state.json`. **Do not delete this file** while a trade is open, or the bot will lose track of your stop loss.

---

## Strategy Details
- **Asset**: AMD (Advanced Micro Devices)
- **Logic**: EMA Crossover Momentum (8/25 Golden Cross to buy, Death Cross to sell)
- **Filters**: Macro Trend Filter (250 EMA) & Volatility Filter (RSI < 65)
- **Safety**: Capital protection via trend-only trading (No Trailing Stop)
- **Position Sizing**: 90% of available buying power per trade

## Files
- `deploy.py`: The main live execution bot.
- `backtest_realistic.py`: The hyperrealistic simulation engine.
- `optimize_safe.py`: The safety-first parameter sweep optimizer.
- `verify_oos.py`: The out-of-sample dynamic verification engine.
- `optimize_tweak.py`: The final minor parameter tweaking sweep.
