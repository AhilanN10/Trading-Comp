import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import shutil

# Make sure we can import backtest_realistic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backtest_realistic import (
    fetch_data,
    calculate_rsi,
    calculate_atr,
    run_realistic_backtest,
    strategy_buy_and_hold,
    plot_comparison_curves
)

def strategy_generic(df, i, position, cash, entry_price, max_price_since_entry, 
                     fast_period, slow_period, use_ema_200, rsi_buy_max):
    """
    Parameterizable strategy signal function.
    """
    fast_col = f'ema_{fast_period}'
    slow_col = f'ema_{slow_period}'
    
    # Warmup buffer
    warmup = max(fast_period, slow_period, 200 if use_ema_200 else 0, 14)
    if i < warmup or i < 1:
        return None
        
    price = float(df['Close'].iloc[i])
    fast_curr = float(df[fast_col].iloc[i])
    slow_curr = float(df[slow_col].iloc[i])
    fast_prev = float(df[fast_col].iloc[i-1])
    slow_prev = float(df[slow_col].iloc[i-1])
    
    if position > 0:
        # Bearish Crossover Exit
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            return 'sell'
    else:
        # Bullish Crossover Entry
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            # Macro Trend Filter
            if use_ema_200:
                ema_200 = float(df['ema_200'].iloc[i])
                if price <= ema_200:
                    return None
            # RSI Filter
            if rsi_buy_max is not None and rsi_buy_max < 100:
                rsi = float(df['rsi_14'].iloc[i])
                if rsi > rsi_buy_max:
                    return None
            return 'buy'
            
    return None

def resample_data(df_5m, timeframe):
    """
    Resamples 5-minute bar data to a larger timeframe.
    """
    if timeframe == '5m':
        return df_5m.copy()
    elif timeframe == '15m':
        ohlc_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        df_15m = df_5m.resample('15Min').agg(ohlc_dict).dropna()
        return df_15m
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

def main():
    ticker = 'TQQQ'
    initial_capital = 1000.0
    position_size_pct = 0.70
    
    artifact_dir = '/Users/ahilannayani/.gemini/antigravity-ide/brain/1ad9a17b-d11c-49f9-953a-d8e886cd635d'
    workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
    
    # Fetch 180 days raw 5-minute Alpaca data
    df_raw = fetch_data(ticker, source='alpaca')
    if df_raw.empty:
        print("[ERROR] Failed to fetch TQQQ data from Alpaca. Aborting optimization.")
        return
        
    # Parameter grid definition
    timeframes = ['5m', '15m']
    fast_periods = [3, 5, 8]
    slow_periods = [13, 21, 30]
    atr_multipliers = [2.5, 3.5, 4.5, None]
    use_ema_200_options = [True, False]
    rsi_buy_max_options = [70, 100]  # 100 means no RSI buy filter
    
    results = []
    
    # Calculate totals
    total_combos = (
        len(timeframes) *
        len(fast_periods) *
        len(slow_periods) *
        len(atr_multipliers) *
        len(use_ema_200_options) *
        len(rsi_buy_max_options)
    )
    print(f"\nStarting Grid Search: Testing {total_combos} combinations on 180-day Alpaca data...")
    
    # We cache resampled datasets to avoid redundant work
    cached_dfs = {
        '5m': resample_data(df_raw, '5m'),
        '15m': resample_data(df_raw, '15m')
    }
    
    count = 0
    
    for tf in timeframes:
        df_tf = cached_dfs[tf]
        
        # Precompute indicators for this timeframe to speed up runs
        df_tf['atr_14'] = calculate_atr(df_tf, 14)
        df_tf['rsi_14'] = calculate_rsi(df_tf['Close'], 14)
        df_tf['ema_3'] = df_tf['Close'].ewm(span=3, adjust=False).mean()
        df_tf['ema_5'] = df_tf['Close'].ewm(span=5, adjust=False).mean()
        df_tf['ema_8'] = df_tf['Close'].ewm(span=8, adjust=False).mean()
        df_tf['ema_13'] = df_tf['Close'].ewm(span=13, adjust=False).mean()
        df_tf['ema_21'] = df_tf['Close'].ewm(span=21, adjust=False).mean()
        df_tf['ema_30'] = df_tf['Close'].ewm(span=30, adjust=False).mean()
        df_tf['ema_200'] = df_tf['Close'].ewm(span=200, adjust=False).mean()
        
        for fast in fast_periods:
            for slow in slow_periods:
                if fast >= slow:
                    continue  # Crossovers require fast < slow
                for atr_m in atr_multipliers:
                    for use_200 in use_ema_200_options:
                        for rsi_max in rsi_buy_max_options:
                            count += 1
                            if count % 20 == 0:
                                print(f"  Processed {count}/{total_combos} combinations...")
                                
                            # Wrap the generic strategy signal
                            strat_fn = lambda df_ref, i, pos, cash, ep, mp, f=fast, s=slow, u=use_200, r=rsi_max: strategy_generic(
                                df_ref, i, pos, cash, ep, mp, fast_period=f, slow_period=s, use_ema_200=u, rsi_buy_max=r
                            )
                            
                            # Run backtest
                            res = run_realistic_backtest(
                                ticker=ticker,
                                strategy_fn=strat_fn,
                                initial_capital=initial_capital,
                                position_size_pct=position_size_pct,
                                plot_equity=False,
                                df=df_tf,
                                atr_mult=atr_m,
                                strategy_name=f"EMA_{fast}_{slow}"
                            )
                            
                            if res and 'metrics' in res:
                                m = res['metrics']
                                results.append({
                                    'timeframe': tf,
                                    'fast_ema': fast,
                                    'slow_ema': slow,
                                    'atr_mult': atr_m,
                                    'ema_200': use_200,
                                    'rsi_max': rsi_max,
                                    'Return %': m['total_return_pct'],
                                    'Sharpe': m['sharpe_ratio'],
                                    'Max DD %': m['max_drawdown_pct'],
                                    'Win Rate %': m['win_rate_pct'],
                                    'Trades': m['total_trades'],
                                    'Avg Duration (min)': m['avg_trade_duration_min']
                                })
                                
    # Create DataFrame of all results
    res_df = pd.DataFrame(results)
    
    # Save the full raw results first
    csv_workspace_path = os.path.join(workspace_dir, 'realistic_optimization_results.csv')
    csv_artifact_path = os.path.join(artifact_dir, 'realistic_optimization_results.csv')
    res_df.to_csv(csv_workspace_path, index=False)
    try:
        shutil.copy(csv_workspace_path, csv_artifact_path)
    except Exception as e:
        print(f"[WARNING] Copying CSV to artifacts failed: {e}")
        
    print(f"\nSaved all {len(res_df)} combinations to {csv_workspace_path}")
    
    # Filter for Drawdown <= 15% and sort by Sharpe descending
    filtered_df = res_df[res_df['Max DD %'] <= 15.0]
    sorted_df = filtered_df.sort_values(by='Sharpe', ascending=False)
    
    print("\n" + "="*95)
    print("                 TOP 15 REALISTIC OPTIMIZATION RUNS (Max DD <= 15%)               ")
    print("="*95)
    print(sorted_df.head(15).to_string(index=False))
    print("="*95 + "\n")
    
    # Get the winning configuration details
    if sorted_df.empty:
        print("[WARNING] No configurations satisfied Drawdown <= 15.0%. Ranking by Sharpe anyway.")
        sorted_df = res_df.sort_values(by='Sharpe', ascending=False)
        
    winner = sorted_df.iloc[0]
    print(f"WINNING CONFIGURATION DETECTED:")
    print(f"  Timeframe:  {winner['timeframe']}")
    print(f"  Fast EMA:   {winner['fast_ema']}")
    print(f"  Slow EMA:   {winner['slow_ema']}")
    print(f"  ATR Stop:   {winner['atr_mult']}x")
    print(f"  EMA 200:    {winner['ema_200']}")
    print(f"  RSI Limit:  {winner['rsi_max']}")
    print(f"  Return:     {winner['Return %']:+.2f}%")
    print(f"  Sharpe:     {winner['Sharpe']:.2f}")
    print(f"  Max DD:     {winner['Max DD %']:.2f}%")
    print(f"  Trades:     {int(winner['Trades'])}")
    
    # Run the winner and buy & hold on its resampled timeframe to plot curves
    winner_tf = winner['timeframe']
    winner_df = cached_dfs[winner_tf]
    
    # Ensure indicators pre-computed
    winner_df['atr_14'] = calculate_atr(winner_df, 14)
    winner_df['rsi_14'] = calculate_rsi(winner_df['Close'], 14)
    winner_df[f"ema_{winner['fast_ema']}"] = winner_df['Close'].ewm(span=winner['fast_ema'], adjust=False).mean()
    winner_df[f"ema_{winner['slow_ema']}"] = winner_df['Close'].ewm(span=winner['slow_ema'], adjust=False).mean()
    winner_df['ema_200'] = winner_df['Close'].ewm(span=200, adjust=False).mean()
    
    strat_winner_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_generic(
        df_ref, i, pos, cash, ep, mp,
        fast_period=int(winner['fast_ema']),
        slow_period=int(winner['slow_ema']),
        use_ema_200=bool(winner['ema_200']),
        rsi_buy_max=float(winner['rsi_max'])
    )
    
    strat_res = run_realistic_backtest(
        ticker=ticker,
        strategy_fn=strat_winner_fn,
        initial_capital=initial_capital,
        position_size_pct=position_size_pct,
        plot_equity=False,
        df=winner_df,
        atr_mult=winner['atr_mult'],
        strategy_name="Optimal_Strategy"
    )
    
    bench_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_buy_and_hold(df_ref, i, pos, cash, ep, mp, warmup=200)
    bench_res = run_realistic_backtest(
        ticker=ticker,
        strategy_fn=bench_fn,
        initial_capital=initial_capital,
        position_size_pct=1.00,
        plot_equity=False,
        df=winner_df,
        atr_mult=None,
        strategy_name="Buy_and_Hold"
    )
    
    # Plot winner vs benchmark
    plot_name = 'TQQQ_EMA_realistic_opt_winner.png'
    plot_workspace_path = os.path.join(workspace_dir, plot_name)
    plot_artifact_path = os.path.join(artifact_dir, plot_name)
    
    plot_comparison_curves(
        portfolio_series=strat_res['portfolio_values'],
        benchmark_series=bench_res['portfolio_values'],
        strat_metrics=strat_res['metrics'],
        bench_metrics=bench_res['metrics'],
        ticker=ticker,
        strategy_name=f"Opt {winner_tf} EMA {int(winner['fast_ema'])}/{int(winner['slow_ema'])} (ATR {winner['atr_mult']}x)",
        source=f"Alpaca {winner_tf}",
        initial_capital=initial_capital,
        output_path=plot_artifact_path
    )
    
    try:
        shutil.copy(plot_artifact_path, plot_workspace_path)
        print(f"[COPY] Copied winning plot to {plot_workspace_path}")
    except Exception as e:
        print(f"[WARNING] Copying winning plot to workspace failed: {e}")

if __name__ == '__main__':
    main()
