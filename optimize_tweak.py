import os
import sys
import pandas as pd
import numpy as np
import itertools
from datetime import datetime
import pytz

# Make sure we can import optimize_safe and backtest_realistic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from optimize_safe import run_safe_backtest, strategy_generic, resample_data
from backtest_realistic import calculate_atr, calculate_rsi, fetch_data
import config

def main():
    ticker = 'AMD'
    initial_capital = 1000.0
    position_size_pct = 0.90  # Keep winning 90% sizing
    
    # 1. Fetch entire historical range from May 1, 2025 to June 12, 2026 to ensure overlap
    # We fetch via Alpaca using delayed IEX feed
    import alpaca_trade_api as tradeapi
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    start_str = "2025-05-01T00:00:00Z"
    end_str = "2026-06-12T21:00:00Z"
    
    print(f"Fetching raw 5m data for {ticker} from {start_str} to {end_str}...")
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
            print("[ERROR] Failed to fetch data.")
            return
            
        # Standardize columns
        bars.columns = [col.lower() for col in bars.columns]
        bars = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        bars.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        if bars.index.tz is None:
            bars.index = bars.index.tz_localize('UTC')
        bars.index = bars.index.tz_convert('America/New_York')
        
    except Exception as e:
        print(f"[ERROR] Fetch failed: {e}")
        return
        
    # Resample to 30m
    df_30m_all = resample_data(bars, '30m')
    print(f"Resampled to {len(df_30m_all)} 30-minute bars.")
    
    # 2. Setup tweak grid parameters
    fast_periods = [7, 8, 9]
    slow_periods = [25, 30, 35]
    macro_ema_periods = [150, 200, 250]
    rsi_limits = [65, 70, 75, 100]  # 100 means no filter
    
    combinations = list(itertools.product(fast_periods, slow_periods, macro_ema_periods, rsi_limits))
    results = []
    
    print(f"Testing {len(combinations)} tweak combinations on AMD...")
    
    # We split the resampled dataset into OOS and IS based on datetime index
    cutoff_date = pd.Timestamp("2025-12-15", tz="America/New_York")
    
    count = 0
    for fast, slow, macro_ema, rsi_lim in combinations:
        if fast >= slow:
            continue
            
        count += 1
        if count % 10 == 0:
            print(f"  Processed {count} tweak combinations...")
            
        # Create a deep copy of resampled dataframe to calculate specific indicators
        df_run = df_30m_all.copy()
        
        df_run['atr_14'] = calculate_atr(df_run, 14)
        df_run['rsi_14'] = calculate_rsi(df_run['Close'], 14)
        df_run['ema_200'] = df_run['Close'].ewm(span=macro_ema, adjust=False).mean() # Swap the EMA 200 col to use macro_ema
        df_run[f'ema_{fast}'] = df_run['Close'].ewm(span=fast, adjust=False).mean()
        df_run[f'ema_{slow}'] = df_run['Close'].ewm(span=slow, adjust=False).mean()
        
        # Split into OOS and IS (making sure OOS has enough history before it starts)
        df_oos = df_run[df_run.index < cutoff_date].copy()
        df_is = df_run[df_run.index >= cutoff_date].copy()
        
        # Strategy closure
        strat_fn = lambda df_ref, i, pos, cash, ep, mp, f=fast, s=slow, r=rsi_lim: strategy_generic(
            df_ref, i, pos, cash, ep, mp, fast_period=f, slow_period=s, rsi_buy_max=r
        )
        
        # Run OOS
        res_oos = run_safe_backtest(
            ticker=ticker,
            strategy_fn=strat_fn,
            df=df_oos,
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
            atr_mult=None,
            stop_mode='intraday'
        )
        
        # Run IS
        res_is = run_safe_backtest(
            ticker=ticker,
            strategy_fn=strat_fn,
            df=df_is,
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
            atr_mult=None,
            stop_mode='intraday'
        )
        
        if res_oos and res_is:
            m_oos = res_oos['metrics']
            m_is = res_is['metrics']
            
            results.append({
                'fast_ema': fast,
                'slow_ema': slow,
                'macro_ema': macro_ema,
                'rsi_limit': rsi_lim,
                'IS Return %': m_is['total_return_pct'],
                'IS Sharpe': m_is['sharpe_ratio'],
                'IS Max DD %': m_is['max_drawdown_pct'],
                'IS Trades': m_is['total_trades'],
                'OOS Return %': m_oos['total_return_pct'],
                'OOS Sharpe': m_oos['sharpe_ratio'],
                'OOS Max DD %': m_oos['max_drawdown_pct'],
                'OOS Trades': m_oos['total_trades']
            })
            
    res_df = pd.DataFrame(results)
    
    # Save results to a CSV in workspace
    workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
    csv_path = os.path.join(workspace_dir, 'tweak_optimization_results.csv')
    res_df.to_csv(csv_path, index=False)
    print(f"\nSaved all tweak results to {csv_path}")
    
    # Sort and filter: Find configurations where both IS and OOS max drawdowns are minimized
    # Criteria: OOS Max DD <= 15.0% AND IS Max DD <= 10.0%, sorted by OOS Sharpe descending
    filtered_df = res_df[(res_df['OOS Max DD %'] <= 15.0) & (res_df['IS Max DD %'] <= 10.0)]
    sorted_df = filtered_df.sort_values(by='OOS Sharpe', ascending=False)
    
    print("\n" + "="*125)
    print("                 TOP 15 TWEAKED CONFS (IS Max DD < 10% & OOS Max DD < 15%)            ")
    print("="*125)
    print(sorted_df.head(15).to_string(index=False))
    print("="*125 + "\n")
    
    # Let's print the top 10 sorted by OOS Return %
    sorted_by_ret = filtered_df.sort_values(by='OOS Return %', ascending=False)
    print("\n" + "="*125)
    print("                 TOP 15 TWEAKED CONFS BY OOS RETURN (IS DD < 10% & OOS DD < 15%)      ")
    print("="*125)
    print(sorted_by_ret.head(15).to_string(index=False))
    print("="*125 + "\n")

if __name__ == '__main__':
    main()
