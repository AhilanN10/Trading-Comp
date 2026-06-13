import pandas as pd
import numpy as np
from backtest_v2 import run_backtest, calculate_rsi, calculate_atr, fetch_data

def strategy_ema_momentum(df, i, position, cash, entry_price, max_price_since_entry, 
                          fast_period=12, slow_period=26, atr_mult=2.0):
    """
    Strategy: EMA Crossover Momentum
    
    Rules:
    - BUY when: Fast EMA crosses above Slow EMA
    - SELL when: Fast EMA crosses below Slow EMA OR ATR trailing stop hits
    - Trailing stop: 14-period ATR, 2.0x multiplier below highest price since entry
    """
    fast_col = f'ema_{fast_period}'
    slow_col = f'ema_{slow_period}'
    
    # Precompute indicators once on the full DataFrame if not present
    if fast_col not in df.columns:
        df[fast_col] = df['Close'].ewm(span=fast_period, adjust=False).mean()
    if slow_col not in df.columns:
        df[slow_col] = df['Close'].ewm(span=slow_period, adjust=False).mean()
    if 'atr_14' not in df.columns:
        df['atr_14'] = calculate_atr(df, 14)
        
    # Ensure we have enough history to evaluate crossovers
    warmup = max(fast_period, slow_period, 14)
    if i < warmup or i < 1:
        return None
        
    price = float(df['Close'].iloc[i])
    atr = float(df['atr_14'].iloc[i])
    
    fast_curr = float(df[fast_col].iloc[i])
    slow_curr = float(df[slow_col].iloc[i])
    fast_prev = float(df[fast_col].iloc[i-1])
    slow_prev = float(df[slow_col].iloc[i-1])
    
    # Sell / Exit Logic
    if position > 0:
        # Check ATR Trailing Stop
        stop_price = max_price_since_entry - atr_mult * atr
        if price <= stop_price:
            return 'sell'
            
        # Check Bearish crossover (Fast EMA crosses below Slow EMA)
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            return 'sell'
            
    # Buy / Entry Logic
    else:
        # Check Bullish crossover (Fast EMA crosses above Slow EMA)
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            return 'buy'
            
    return None

def strategy_buy_and_hold(df, i, position, cash, entry_price, max_price_since_entry, warmup=26):
    """
    Benchmark: Buy & Hold
    Buys at the first available trade bar (warmup index) and holds until the final bar closeout.
    """
    if i == warmup and position == 0:
        return 'buy'
    return None

if __name__ == "__main__":
    tickers = ['TQQQ', 'SOXL', 'NVDA']
    ema_pairs = [(5, 13), (9, 21), (12, 26), (8, 20)]
    
    print("==================================================")
    print("RUNNING EMA MOMENTUM BACKTEST SWEEP & BENCHMARKS")
    print("==================================================")
    print(f"Tickers: {tickers}")
    print(f"EMA Configurations: {ema_pairs}")
    print("Testing over the maximum available 5-minute data period (~59 days)...")
    
    strategy_results = []
    benchmark_results = []
    cached_dfs = {}
    
    # 1. Run Strategy & Benchmark backtests
    for ticker in tickers:
        # Download and cache DataFrame to reuse across configurations
        df_ticker = fetch_data(ticker)
        if df_ticker.empty:
            print(f"[WARNING] Skipping {ticker} due to empty data.")
            continue
            
        cached_dfs[ticker] = df_ticker
        
        # Run Buy & Hold Benchmark (uses 100% position size)
        print(f"Running Buy & Hold Benchmark for {ticker}...")
        bench_fn = lambda df, i, pos, cash, ep, mp: strategy_buy_and_hold(df, i, pos, cash, ep, mp, warmup=26)
        bench_res = run_backtest(
            ticker=ticker,
            strategy_fn=bench_fn,
            strategy_name="Buy_and_Hold",
            position_size_pct=1.00,
            plot_equity=False,
            df=df_ticker
        )
        
        if bench_res and 'metrics' in bench_res:
            metrics = bench_res['metrics']
            benchmark_results.append({
                'Ticker': ticker,
                'Strategy': 'Buy & Hold',
                'Total Return %': metrics['total_return_pct'],
                'Sharpe Ratio': metrics['sharpe_ratio'],
                'Max Drawdown %': metrics['max_drawdown_pct'],
                'Win Rate %': metrics['win_rate_pct'],
                'Total Trades': metrics['total_trades'],
                'Avg Duration (min)': metrics['avg_trade_duration_min']
            })
            
        # Run EMA crossover momentum sweeps (uses 70% position size)
        for fast, slow in ema_pairs:
            strat_name = f"EMA_{fast}_{slow}"
            print(f"Sweeping {ticker}: Fast={fast}, Slow={slow}...")
            
            # Build strategy closure
            strat_fn = lambda df, i, pos, cash, ep, mp, f=fast, s=slow: strategy_ema_momentum(
                df, i, pos, cash, ep, mp, fast_period=f, slow_period=s, atr_mult=2.0
            )
            
            res = run_backtest(
                ticker=ticker,
                strategy_fn=strat_fn,
                strategy_name=strat_name,
                position_size_pct=0.70,
                plot_equity=False,
                df=df_ticker
            )
            
            if res and 'metrics' in res:
                metrics = res['metrics']
                strategy_results.append({
                    'Ticker': ticker,
                    'Strategy': f"EMA Crossover ({fast}/{slow})",
                    'Total Return %': metrics['total_return_pct'],
                    'Sharpe Ratio': metrics['sharpe_ratio'],
                    'Max Drawdown %': metrics['max_drawdown_pct'],
                    'Win Rate %': metrics['win_rate_pct'],
                    'Total Trades': metrics['total_trades'],
                    'Avg Duration (min)': metrics['avg_trade_duration_min'],
                    'fast': fast,
                    'slow': slow
                })
                
    # 2. Compile and sort the Strategy Results by Total Return descending
    sorted_strategy = sorted(strategy_results, key=lambda x: x['Total Return %'], reverse=True)
    
    # 3. Format Strategy Results for the final table
    table_rows = []
    for item in sorted_strategy:
        table_rows.append({
            'Ticker': item['Ticker'],
            'Strategy': item['Strategy'],
            'Total Return %': f"{item['Total Return %']:+.2f}%",
            'Sharpe Ratio': f"{item['Sharpe Ratio']:.2f}",
            'Max Drawdown %': f"{item['Max Drawdown %']:.2f}%",
            'Win Rate %': f"{item['Win Rate %']:.2f}%",
            'Total Trades': item['Total Trades'],
            'Avg Duration (min)': f"{item['Avg Duration (min)']:.1f}"
        })
        
    # 4. Format Benchmarks and append at the bottom
    for item in benchmark_results:
        table_rows.append({
            'Ticker': item['Ticker'],
            'Strategy': item['Strategy'],
            'Total Return %': f"{item['Total Return %']:+.2f}%",
            'Sharpe Ratio': f"{item['Sharpe Ratio']:.2f}",
            'Max Drawdown %': f"{item['Max Drawdown %']:.2f}%",
            'Win Rate %': f"{item['Win Rate %']:.2f}%",
            'Total Trades': item['Total Trades'],
            'Avg Duration (min)': f"{item['Avg Duration (min)']:.1f}"
        })
        
    # 5. Output Ranked Comparison Table
    summary_df = pd.DataFrame(table_rows)
    print("\n" + "="*95)
    print("                       EMA MOMENTUM SWEEP PERFORMANCE RANKING                     ")
    print("="*95)
    print(summary_df.to_string(index=False))
    print("="*95 + "\n")
    
    # Save results to CSV
    summary_df.to_csv('ema_sweep_results.csv', index=False)
    print("Ranked results saved to ema_sweep_results.csv")
    
    # 6. Plot and save equity curve PNGs for the top 3 overall combinations
    print("\n==================================================")
    print("PLOTTING AND SAVING EQUITY CURVES FOR THE TOP 3 STRATEGY COMBINATIONS")
    print("==================================================")
    
    for idx in range(min(3, len(sorted_strategy))):
        best_run = sorted_strategy[idx]
        ticker = best_run['Ticker']
        fast = best_run['fast']
        slow = best_run['slow']
        
        df_ticker = cached_dfs[ticker]
        
        # Build strategy function
        strat_fn = lambda df, i, pos, cash, ep, mp, f=fast, s=slow: strategy_ema_momentum(
            df, i, pos, cash, ep, mp, fast_period=f, slow_period=s, atr_mult=2.0
        )
        
        strategy_name = f"EMA_Momentum_{fast}_{slow}"
        print(f"Plotting Top #{idx+1}: {ticker} EMA {fast}/{slow}...")
        
        # Run once more with plot_equity=True to save the PNG
        run_backtest(
            ticker=ticker,
            strategy_fn=strat_fn,
            strategy_name=strategy_name,
            position_size_pct=0.70,
            plot_equity=True,
            df=df_ticker
        )
        
    print("\nEMA Momentum backtest and sweep completed successfully.")
