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
    calculate_metrics,
    strategy_buy_and_hold,
    plot_comparison_curves
)

def strategy_generic(df, i, position, cash, entry_price, max_price_since_entry, 
                     fast_period, slow_period, use_ema_200=True, rsi_buy_max=70):
    """
    Standardized strategy signal function.
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
            if rsi_buy_max is not None:
                rsi = float(df['rsi_14'].iloc[i])
                if rsi > rsi_buy_max:
                    return None
            return 'buy'
            
    return None

def resample_data(df_5m, timeframe):
    if timeframe == '5m':
        return df_5m.copy()
    
    ohlc_dict = {
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }
    
    if timeframe == '15m':
        return df_5m.resample('15Min').agg(ohlc_dict).dropna()
    elif timeframe == '30m':
        return df_5m.resample('30Min').agg(ohlc_dict).dropna()
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

def run_safe_backtest(ticker, strategy_fn, df, initial_capital=1000.0, position_size_pct=0.70,
                      slippage_pct=0.0005, fee_per_share=0.002, atr_mult=2.0, stop_mode='intraday'):
    """
    Simulation engine supporting intraday and close_only stop modes, position sizing,
    next-bar Open execution, and transaction frictions.
    """
    df = df.copy()
    
    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    max_price_since_entry = 0.0
    
    portfolio_values = []
    trades_log = []
    active_trade = None
    
    pending_buy = False
    pending_sell = False
    pending_stop_exit = False
    
    total_bars = len(df)
    
    for i in range(total_bars):
        row = df.iloc[i]
        timestamp = df.index[i]
        
        open_price = float(row['Open'])
        high_price = float(row['High'])
        low_price = float(row['Low'])
        close_price = float(row['Close'])
        atr = float(row['atr_14'])
        
        stopped_out_this_bar = False
        
        # 1. Execute pending order at Open of current bar
        if pending_buy and position == 0:
            exec_price = open_price * (1 + slippage_pct)
            target_cash = initial_capital * position_size_pct
            shares = int(min(cash, target_cash) / (exec_price + fee_per_share))
            if shares > 0:
                cost = shares * exec_price + shares * fee_per_share
                cash -= cost
                position = shares
                entry_price = exec_price
                max_price_since_entry = high_price
                
                active_trade = {
                    'entry_time': timestamp,
                    'entry_price': exec_price,
                    'shares': shares
                }
            pending_buy = False
            
        elif (pending_sell or pending_stop_exit) and position > 0:
            exec_price = open_price * (1 - slippage_pct)
            revenue = position * exec_price - position * fee_per_share
            cash += revenue
            
            if active_trade is not None:
                duration = timestamp - active_trade['entry_time']
                duration_minutes = duration.total_seconds() / 60
                
                entry_cost_total = active_trade['shares'] * active_trade['entry_price'] + active_trade['shares'] * fee_per_share
                exit_revenue_total = position * exec_price - position * fee_per_share
                profit = exit_revenue_total - entry_cost_total
                profit_pct = (profit / entry_cost_total) * 100
                
                completed_trade = {
                    'entry_time': active_trade['entry_time'],
                    'entry_price': active_trade['entry_price'],
                    'exit_time': timestamp,
                    'exit_price': exec_price,
                    'shares': active_trade['shares'],
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'duration_minutes': duration_minutes
                }
                trades_log.append(completed_trade)
                active_trade = None
                
            position = 0.0
            entry_price = 0.0
            max_price_since_entry = 0.0
            pending_sell = False
            pending_stop_exit = False
            
        # 2. Check stop-loss on current bar
        if position > 0 and atr_mult is not None and atr_mult > 0.0:
            stop_price = max_price_since_entry - atr_mult * atr
            
            if stop_mode == 'intraday':
                if low_price <= stop_price:
                    # Intraday hit: execute immediately
                    exec_price = min(open_price, stop_price) * (1 - slippage_pct)
                    revenue = position * exec_price - position * fee_per_share
                    cash += revenue
                    
                    if active_trade is not None:
                        duration = timestamp - active_trade['entry_time']
                        duration_minutes = duration.total_seconds() / 60
                        
                        entry_cost_total = active_trade['shares'] * active_trade['entry_price'] + active_trade['shares'] * fee_per_share
                        exit_revenue_total = position * exec_price - position * fee_per_share
                        profit = exit_revenue_total - entry_cost_total
                        profit_pct = (profit / entry_cost_total) * 100
                        
                        completed_trade = {
                            'entry_time': active_trade['entry_time'],
                            'entry_price': active_trade['entry_price'],
                            'exit_time': timestamp,
                            'exit_price': exec_price,
                            'shares': active_trade['shares'],
                            'profit': profit,
                            'profit_pct': profit_pct,
                            'duration_minutes': duration_minutes
                        }
                        trades_log.append(completed_trade)
                        active_trade = None
                        
                    position = 0.0
                    entry_price = 0.0
                    max_price_since_entry = 0.0
                    stopped_out_this_bar = True
                else:
                    max_price_since_entry = max(max_price_since_entry, high_price)
                    
            elif stop_mode == 'close_only':
                if close_price <= stop_price:
                    # Close hit: trigger sell at next bar's Open
                    pending_stop_exit = True
                else:
                    max_price_since_entry = max(max_price_since_entry, high_price)
                    
        # 3. Evaluate signals for next-bar Open execution
        if position > 0 and not pending_sell and not pending_stop_exit:
            signal = strategy_fn(df, i, position, cash, entry_price, max_price_since_entry)
            if signal == 'sell':
                pending_sell = True
        elif position == 0 and not pending_buy and not stopped_out_this_bar:
            signal = strategy_fn(df, i, position, cash, entry_price, max_price_since_entry)
            if signal == 'buy':
                pending_buy = True
                
        current_val = cash + (position * close_price)
        portfolio_values.append(current_val)
        
    # Final closeout
    if position > 0:
        final_idx = total_bars - 1
        row = df.iloc[final_idx]
        timestamp = df.index[final_idx]
        close_price = float(row['Close'])
        
        exec_price = close_price * (1 - slippage_pct)
        revenue = position * exec_price - position * fee_per_share
        cash += revenue
        
        if active_trade is not None:
            duration = timestamp - active_trade['entry_time']
            duration_minutes = duration.total_seconds() / 60
            
            entry_cost_total = active_trade['shares'] * active_trade['entry_price'] + active_trade['shares'] * fee_per_share
            exit_revenue_total = position * exec_price - position * fee_per_share
            profit = exit_revenue_total - entry_cost_total
            profit_pct = (profit / entry_cost_total) * 100
            
            completed_trade = {
                'entry_time': active_trade['entry_time'],
                'entry_price': active_trade['entry_price'],
                'exit_time': timestamp,
                'exit_price': exec_price,
                'shares': active_trade['shares'],
                'profit': profit,
                'profit_pct': profit_pct,
                'duration_minutes': duration_minutes
            }
            trades_log.append(completed_trade)
            active_trade = None
            
        position = 0.0
        portfolio_values[-1] = cash
        
    portfolio_series = pd.Series(portfolio_values, index=df.index)
    metrics = calculate_metrics(portfolio_series, trades_log)
    
    return {
        'metrics': metrics,
        'portfolio_values': portfolio_series,
        'trades': trades_log
    }

def main():
    tickers = ['TQQQ', 'AMD', 'NVDA']
    timeframes = ['5m', '15m', '30m']
    ema_pairs = [(5, 13), (8, 21), (8, 30)]
    atr_multipliers = [2.5, 3.5, 4.5, None]
    stop_modes = ['intraday', 'close_only']
    position_sizes = [0.50, 0.70, 0.90]
    
    initial_capital = 1000.0
    
    artifact_dir = '/Users/ahilannayani/.gemini/antigravity-ide/brain/1ad9a17b-d11c-49f9-953a-d8e886cd635d'
    workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
    
    # Pre-fetch and cache raw data
    raw_data = {}
    for ticker in tickers:
        df = fetch_data(ticker, source='alpaca')
        if not df.empty:
            raw_data[ticker] = df
            
    results = []
    
    # Calculate combinations
    total_runs = (
        len(raw_data) *
        len(timeframes) *
        len(ema_pairs) *
        len(atr_multipliers) *
        len(stop_modes) *
        len(position_sizes)
    )
    print(f"\nStarting Safe Sweep: Testing {total_runs} combinations on Alpaca 180-day data...")
    
    count = 0
    for ticker, df_raw in raw_data.items():
        # Pre-cache timeframes
        tf_dfs = {}
        for tf in timeframes:
            df_tf = resample_data(df_raw, tf)
            
            # Precompute indicators
            df_tf['atr_14'] = calculate_atr(df_tf, 14)
            df_tf['rsi_14'] = calculate_rsi(df_tf['Close'], 14)
            df_tf['ema_200'] = df_tf['Close'].ewm(span=200, adjust=False).mean()
            
            # Unique EMAs we need
            unique_emas = set()
            for fast, slow in ema_pairs:
                unique_emas.add(fast)
                unique_emas.add(slow)
            for ema_val in unique_emas:
                df_tf[f'ema_{ema_val}'] = df_tf['Close'].ewm(span=ema_val, adjust=False).mean()
                
            tf_dfs[tf] = df_tf
            
        for tf in timeframes:
            df_tf = tf_dfs[tf]
            
            for fast, slow in ema_pairs:
                for atr_m in atr_multipliers:
                    for s_mode in stop_modes:
                        for pos_size in position_sizes:
                            count += 1
                            if count % 50 == 0:
                                print(f"  Processed {count}/{total_runs} runs...")
                                
                            # Crossover strategy
                            strat_fn = lambda df_ref, i, pos, cash, ep, mp, f=fast, s=slow: strategy_generic(
                                df_ref, i, pos, cash, ep, mp, fast_period=f, slow_period=s
                            )
                            
                            # Run backtest
                            res = run_safe_backtest(
                                ticker=ticker,
                                strategy_fn=strat_fn,
                                df=df_tf,
                                initial_capital=initial_capital,
                                position_size_pct=pos_size,
                                atr_mult=atr_m,
                                stop_mode=s_mode
                            )
                            
                            if res and 'metrics' in res:
                                m = res['metrics']
                                
                                # Weekly return metrics
                                portfolio_series = res['portfolio_values']
                                weekly_values = portfolio_series.resample('W').last()
                                weekly_returns = weekly_values.pct_change().dropna() * 100
                                if not weekly_returns.empty:
                                    avg_weekly_ret = weekly_returns.mean()
                                    max_weekly_loss = weekly_returns.min()
                                else:
                                    avg_weekly_ret = 0.0
                                    max_weekly_loss = 0.0
                                    
                                results.append({
                                    'ticker': ticker,
                                    'timeframe': tf,
                                    'ema_fast': fast,
                                    'ema_slow': slow,
                                    'atr_mult': atr_m,
                                    'stop_mode': s_mode,
                                    'position_size': pos_size,
                                    'Return %': m['total_return_pct'],
                                    'Sharpe': m['sharpe_ratio'],
                                    'Max DD %': m['max_drawdown_pct'],
                                    'Trades': m['total_trades'],
                                    'Avg Weekly Return %': avg_weekly_ret,
                                    'Max Weekly Loss %': max_weekly_loss
                                })
                                
    res_df = pd.DataFrame(results)
    
    # Save the raw results
    csv_workspace_path = os.path.join(workspace_dir, 'safe_optimization_results.csv')
    csv_artifact_path = os.path.join(artifact_dir, 'safe_optimization_results.csv')
    res_df.to_csv(csv_workspace_path, index=False)
    try:
        shutil.copy(csv_workspace_path, csv_artifact_path)
    except Exception as e:
        print(f"[WARNING] Copying safe CSV failed: {e}")
        
    print(f"\nSaved all {len(res_df)} combinations to {csv_workspace_path}")
    
    # Filter for Max Drawdown < 10%
    safe_df = res_df[res_df['Max DD %'] < 10.0]
    
    # Sort by Sharpe Ratio descending to find the best risk-adjusted configurations
    sorted_df = safe_df.sort_values(by='Sharpe', ascending=False)
    
    print("\n" + "="*95)
    print("                 TOP 15 RISK-CAPPED STRATEGY CONFS (Max DD < 10.0%)               ")
    print("="*95)
    print(sorted_df.head(15).to_string(index=False))
    print("="*95 + "\n")
    
    if sorted_df.empty:
        print("[WARNING] No configurations met the strict < 10% Drawdown cap. Using raw results.")
        sorted_df = res_df.sort_values(by='Sharpe', ascending=False)
        
    # Get the best safe configuration
    winner = sorted_df.iloc[0]
    print(f"BEST SAFE CONFIGURATION DETECTED:")
    print(f"  Ticker:         {winner['ticker']}")
    print(f"  Timeframe:      {winner['timeframe']}")
    print(f"  EMA Crossover:  {int(winner['ema_fast'])}/{int(winner['ema_slow'])}")
    print(f"  ATR Stop:       {winner['atr_mult']}x ({winner['stop_mode']})")
    print(f"  Pos Sizing:     {int(winner['position_size'] * 100)}%")
    print(f"  Return:         {winner['Return %']:+.2f}%")
    print(f"  Sharpe:         {winner['Sharpe']:.2f}")
    print(f"  Max Drawdown:   {winner['Max DD %']:.2f}%")
    print(f"  Avg Weekly %:   {winner['Avg Weekly Return %']:+.2f}%")
    print(f"  Max Weekly Loss:{winner['Max Weekly Loss %']:+.2f}%")
    print(f"  Trades:         {int(winner['Trades'])}")
    
    # Re-run winner and benchmark to plot
    w_ticker = winner['ticker']
    w_tf = winner['timeframe']
    w_df = resample_data(raw_data[w_ticker], w_tf)
    
    # Compute indicators for winner
    w_df['atr_14'] = calculate_atr(w_df, 14)
    w_df['rsi_14'] = calculate_rsi(w_df['Close'], 14)
    w_df['ema_200'] = w_df['Close'].ewm(span=200, adjust=False).mean()
    w_df[f"ema_{int(winner['ema_fast'])}"] = w_df['Close'].ewm(span=int(winner['ema_fast']), adjust=False).mean()
    w_df[f"ema_{int(winner['ema_slow'])}"] = w_df['Close'].ewm(span=int(winner['ema_slow']), adjust=False).mean()
    
    strat_winner_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_generic(
        df_ref, i, pos, cash, ep, mp,
        fast_period=int(winner['ema_fast']),
        slow_period=int(winner['ema_slow'])
    )
    
    strat_res = run_safe_backtest(
        ticker=w_ticker,
        strategy_fn=strat_winner_fn,
        df=w_df,
        initial_capital=initial_capital,
        position_size_pct=winner['position_size'],
        atr_mult=winner['atr_mult'],
        stop_mode=winner['stop_mode']
    )
    
    bench_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_buy_and_hold(df_ref, i, pos, cash, ep, mp, warmup=200)
    bench_res = run_safe_backtest(
        ticker=w_ticker,
        strategy_fn=bench_fn,
        df=w_df,
        initial_capital=initial_capital,
        position_size_pct=1.00,
        atr_mult=None,
        stop_mode='intraday'
    )
    
    # Plot curves
    plot_name = f"{w_ticker}_safe_opt_winner.png"
    plot_workspace_path = os.path.join(workspace_dir, plot_name)
    plot_artifact_path = os.path.join(artifact_dir, plot_name)
    
    plot_comparison_curves(
        portfolio_series=strat_res['portfolio_values'],
        benchmark_series=bench_res['portfolio_values'],
        strat_metrics=strat_res['metrics'],
        bench_metrics=bench_res['metrics'],
        ticker=w_ticker,
        strategy_name=f"Safe Opt ({w_tf} EMA {int(winner['ema_fast'])}/{int(winner['ema_slow'])} Stop {winner['atr_mult']}x Size {int(winner['position_size']*100)}%)",
        source=f"Alpaca {w_tf}",
        initial_capital=initial_capital,
        output_path=plot_artifact_path
    )
    
    try:
        shutil.copy(plot_artifact_path, plot_workspace_path)
        print(f"[COPY] Copied safe plot to {plot_workspace_path}")
    except Exception as e:
        print(f"[WARNING] Copying safe plot to workspace failed: {e}")

if __name__ == '__main__':
    main()
