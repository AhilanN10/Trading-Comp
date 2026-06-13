import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import shutil

# Make sure we can import optimize_safe and backtest_realistic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from optimize_safe import run_safe_backtest, strategy_generic, resample_data
from backtest_realistic import calculate_atr, calculate_rsi, strategy_buy_and_hold, plot_comparison_curves
import config

def test_ticker_strategy(ticker, api, initial_capital=1000.0, position_size_pct=0.90):
    start_str = "2025-05-01T00:00:00Z"
    end_str = "2026-06-12T21:00:00Z"
    
    print(f"\nFetching raw 5m data for {ticker} from {start_str} to {end_str}...")
    try:
        bars = api.get_bars(
            ticker,
            '5Min',
            start=start_str,
            end=end_str,
            feed='iex',
            adjustment='raw'
        ).df
        
        if bars.empty:
            print(f"[ERROR] Failed to fetch data for {ticker}.")
            return None
            
        # Standardize columns
        bars.columns = [col.lower() for col in bars.columns]
        bars = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        bars.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        if bars.index.tz is None:
            bars.index = bars.index.tz_localize('UTC')
        bars.index = bars.index.tz_convert('America/New_York')
        
    except Exception as e:
        print(f"[ERROR] Fetch failed for {ticker}: {e}")
        return None
        
    # Resample to 30m
    df_30m = resample_data(bars, '30m')
    print(f"Resampled {ticker} to {len(df_30m)} 30-minute bars.")
    
    # Define strategy parameters
    fast = 8
    slow = 25
    macro_ema = 250
    rsi_lim = 65
    
    # Calculate indicators
    df_30m['atr_14'] = calculate_atr(df_30m, 14)
    df_30m['rsi_14'] = calculate_rsi(df_30m['Close'], 14)
    df_30m['ema_200'] = df_30m['Close'].ewm(span=macro_ema, adjust=False).mean()  # mapped to 'ema_200' for strategy check
    df_30m[f'ema_{fast}'] = df_30m['Close'].ewm(span=fast, adjust=False).mean()
    df_30m[f'ema_{slow}'] = df_30m['Close'].ewm(span=slow, adjust=False).mean()
    
    # Cutoff date to split OOS and IS
    cutoff_date = pd.Timestamp("2025-12-15", tz="America/New_York")
    
    # Split into OOS and IS
    df_oos = df_30m[df_30m.index < cutoff_date].copy()
    df_is = df_30m[df_30m.index >= cutoff_date].copy()
    
    # Strategy function closure
    strat_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_generic(
        df_ref, i, pos, cash, ep, mp, fast_period=fast, slow_period=slow, rsi_buy_max=rsi_lim
    )
    
    # Benchmark function closure (warmup 250)
    bench_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_buy_and_hold(df_ref, i, pos, cash, ep, mp, warmup=250)
    
    # Run OOS Backtests
    res_oos_strat = run_safe_backtest(ticker, strat_fn, df_oos, initial_capital, position_size_pct, atr_mult=None)
    res_oos_bench = run_safe_backtest(ticker, bench_fn, df_oos, initial_capital, position_size_pct=1.00, atr_mult=None)
    
    # Run IS Backtests
    res_is_strat = run_safe_backtest(ticker, strat_fn, df_is, initial_capital, position_size_pct, atr_mult=None)
    res_is_bench = run_safe_backtest(ticker, bench_fn, df_is, initial_capital, position_size_pct=1.00, atr_mult=None)
    
    if not res_oos_strat or not res_is_strat:
        print(f"[ERROR] Simulation failed for {ticker}")
        return None
        
    return {
        'oos_strat': res_oos_strat['metrics'],
        'oos_bench': res_oos_bench['metrics'],
        'is_strat': res_is_strat['metrics'],
        'is_bench': res_is_bench['metrics'],
        'df_oos_strat': res_oos_strat['portfolio_values'],
        'df_oos_bench': res_oos_bench['portfolio_values'],
        'df_is_strat': res_is_strat['portfolio_values'],
        'df_is_bench': res_is_bench['portfolio_values']
    }

def main():
    tickers = ['AAPL', 'META', 'MSFT']
    import alpaca_trade_api as tradeapi
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    results = {}
    
    for ticker in tickers:
        res = test_ticker_strategy(ticker, api)
        if res:
            results[ticker] = res
            
    print("\n" + "="*80)
    print("                 MULTI-TICKER VERIFICATION METRICS")
    print("="*80)
    
    for ticker, res in results.items():
        print(f"\n--- {ticker} ---")
        m_oos_strat = res['oos_strat']
        m_oos_bench = res['oos_bench']
        m_is_strat = res['is_strat']
        m_is_bench = res['is_bench']
        
        print(f"  Out-of-Sample (OOS) Period: May 1, 2025 to Dec 15, 2025")
        print(f"    Strategy:  Return {m_oos_strat['total_return_pct']:+.2f}% | Sharpe {m_oos_strat['sharpe_ratio']:.2f} | Max DD {m_oos_strat['max_drawdown_pct']:.2f}% | Trades {m_oos_strat['total_trades']}")
        print(f"    Benchmark: Return {m_oos_bench['total_return_pct']:+.2f}% | Sharpe {m_oos_bench['sharpe_ratio']:.2f} | Max DD {m_oos_bench['max_drawdown_pct']:.2f}%")
        
        print(f"  In-Sample (IS) Period: Dec 15, 2025 to June 12, 2026")
        print(f"    Strategy:  Return {m_is_strat['total_return_pct']:+.2f}% | Sharpe {m_is_strat['sharpe_ratio']:.2f} | Max DD {m_is_strat['max_drawdown_pct']:.2f}% | Trades {m_is_strat['total_trades']}")
        print(f"    Benchmark: Return {m_is_bench['total_return_pct']:+.2f}% | Sharpe {m_is_bench['sharpe_ratio']:.2f} | Max DD {m_is_bench['max_drawdown_pct']:.2f}%")
        
        # Save plots
        workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
        
        plot_comparison_curves(
            portfolio_series=res['df_oos_strat'],
            benchmark_series=res['df_oos_bench'],
            strat_metrics=m_oos_strat,
            bench_metrics=m_oos_bench,
            ticker=ticker,
            strategy_name=f"{ticker} EMA 8/25 Strategy",
            source="Alpaca OOS (May-Dec 2025)",
            initial_capital=1000.0,
            output_path=os.path.join(workspace_dir, f"{ticker}_OOS_curve.png")
        )
        print(f"  Saved OOS curve to {ticker}_OOS_curve.png")
        
        plot_comparison_curves(
            portfolio_series=res['df_is_strat'],
            benchmark_series=res['df_is_bench'],
            strat_metrics=m_is_strat,
            bench_metrics=m_is_bench,
            ticker=ticker,
            strategy_name=f"{ticker} EMA 8/25 Strategy",
            source="Alpaca IS (Dec 2025-Jun 2026)",
            initial_capital=1000.0,
            output_path=os.path.join(workspace_dir, f"{ticker}_IS_curve.png")
        )
        print(f"  Saved IS curve to {ticker}_IS_curve.png")

if __name__ == '__main__':
    main()
