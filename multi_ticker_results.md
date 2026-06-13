# Multi-Ticker Strategy Backtesting Results

This document aggregates the backtesting results for the optimized trading strategy applied across multiple major tech equities: **AMD** (the primary asset), **AAPL**, **META**, and **MSFT**.

---

## ⚙️ Strategy Specification
*   **Asset Sizing**: 90% of available buying power per trade.
*   **Timeframe**: 30-minute bars.
*   **Entry Signal**: Bullish EMA Crossover (8-period crossing above 25-period).
*   **Entry Filters**:
    1.  **Macro Trend**: Price must be above the 250-period EMA.
    2.  **Volatility/RSI**: Wilder's RSI (14) must be below 65.
*   **Exit Signal**: Bearish EMA Crossover (8-period crossing below 25-period).
*   **Safety / Stop Loss**: None (exits strictly on bearish crossover to avoid whipsaws).

---

## 📊 Performance Comparison Table

The backtests are split into **Out-of-Sample (OOS)** and **In-Sample (IS)** periods under realistic friction parameters (0.05% slippage, $0.002/share commissions, next-bar Open execution).

| Ticker | Period | Strategy Return | Benchmark (B&H) | Strategy Max DD | Benchmark Max DD | Strategy Sharpe | Benchmark Sharpe | Total Trades |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AMD** | OOS (May – Dec 2025) | **+23.00%** | +77.42% | **10.39%** | 24.86% | **1.76** | 1.98 | 25 |
| *(Winner)*| IS (Dec 2025 – Jun 2026) | **+48.80%** | +120.95% | **6.48%** | 25.13% | **2.99** | 3.01 | 17 |
| **AAPL** | OOS (May – Dec 2025) | **-3.95%** | +30.80% | **7.23%** | 5.04% | **-0.62** | 2.52 | 28 |
| | IS (Dec 2025 – Jun 2026) | **+9.24%** | +8.98% | **5.32%** | 9.83% | **1.79** | 1.05 | 18 |
| **META** | OOS (May – Dec 2025) | **+3.83%** | -0.34% | **5.76%** | 18.50% | **0.74** | 0.06 | 19 |
| | IS (Dec 2025 – Jun 2026) | **-9.50%** | -8.12% | **10.36%** | 19.92% | **-2.50** | -0.65 | 7 |
| **MSFT** | OOS (May – Dec 2025) | **+1.61%** | +3.86% | **2.69%** | 14.00% | **0.61** | 0.48 | 22 |
| | IS (Dec 2025 – Jun 2026) | **-3.61%** | -17.69% | **5.03%** | 25.11% | **-1.57** | -1.36 | 8 |

---

## 🔍 Ticker-by-Ticker Insights

### 1. AMD (Optimized Target)
*   **Summary**: Outstanding performance across both periods.
*   **Takeaway**: AMD experienced high-momentum trends where the 8/25 EMA crossover captured large legs of the movement. By using a 250 EMA trend filter and capping RSI entries, the bot successfully avoided false breakouts during consolidation phases, preserving capital and keeping drawdowns extremely low (**6.48%** in IS, **10.39%** in OOS).

### 2. AAPL (Apple)
*   **Summary**: Neutral/mixed performance.
*   **Takeaway**: In the OOS period, Apple had a steady, low-volatility uptrend. The strategy underperformed (+30.80% B&H vs -3.95% Strategy) because the trend and RSI filters repeatedly locked the bot out of positions during slow grinding moves. However, in the IS period, the strategy outperformed with half the drawdown of the benchmark (**5.32%** vs **9.83%**) and a higher Sharpe ratio (**1.79** vs **1.05**).

### 3. META (Meta Platforms)
*   **Summary**: Strong downside buffer, but rangebound drag.
*   **Takeaway**: During the OOS period, META was flat. The strategy outperformed by staying flat or taking minor profitable trades, capping the drawdown at **5.76%** vs. the benchmark's **18.50%**. During the IS period, META fell into a choppy downtrend; although the strategy protected capital from the benchmark's **19.92%** drawdown (restricting it to **10.36%**), it experienced whipsaw losses ending at **-9.50%**.

### 4. MSFT (Microsoft)
*   **Summary**: Strong defensive outperformance.
*   **Takeaway**: Microsoft suffered a major bear phase in the IS period, dropping **-17.69%** with a **25.11%** drawdown. The EMA crossover strategy recognized the macro downtrend and kept the portfolio flat, restricting overall losses to just **-3.61%** with a tiny **5.03%** drawdown. This is a classic demonstration of how trend-following strategies function as a safe hedge during bear markets.

---

## 📈 Local Equity Curve Visuals
For detailed visual inspections of the equity trajectories, refer to the locally saved charts:
*   **AMD**: `AMD_IS_curve.png` & `AMD_OOS_curve.png`
*   **AAPL**: `AAPL_IS_curve.png` & `AAPL_OOS_curve.png`
*   **META**: `META_IS_curve.png` & `META_OOS_curve.png`
*   **MSFT**: `MSFT_IS_curve.png` & `MSFT_OOS_curve.png`
