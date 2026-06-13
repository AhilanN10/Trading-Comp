import sys
import os
import pandas as pd
import shutil
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Make sure we can import optimize_safe and backtest_realistic
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from optimize_safe import run_safe_backtest, strategy_generic, resample_data
from backtest_realistic import calculate_atr, calculate_rsi, strategy_buy_and_hold, plot_comparison_curves
import config
import alpaca_trade_api as tradeapi

# Initialize Alpaca client
api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')

# Map of winning configurations from our safe sweep grid
BEST_PARAMS = {
    'AMD': {
        'timeframe': '30m',
        'fast': 8,
        'slow': 30,
        'atr_mult': None,
        'stop_mode': 'intraday', # Since atr_mult is None, stop_mode is redundant but kept
        'pos_size': 0.90
    },
    'TQQQ': {
        'timeframe': '5m',
        'fast': 8,
        'slow': 30,
        'atr_mult': 3.5,
        'stop_mode': 'close_only',
        'pos_size': 0.70  # Swept 70% was highly optimal with Max DD 7.17%
    },
    'NVDA': {
        'timeframe': '30m',
        'fast': 8,
        'slow': 30,
        'atr_mult': 4.5,
        'stop_mode': 'close_only',
        'pos_size': 0.90
    }
}

def fetch_historical_oos(ticker):
    # Unseen period: May 1, 2025 to Dec 15, 2025
    start_str = "2025-05-01T00:00:00Z"
    end_str = "2025-12-15T00:00:00Z"
    
    print(f"\nFetching OOS historical data for {ticker} from {start_str} to {end_str}...")
    try:
        bars = api.get_bars(
            ticker,
            '5Min', # Always fetch 5m, then resample to target timeframe
            start=start_str,
            end=end_str,
            feed='iex',
            adjustment='raw'
        ).df
        
        if bars.empty:
            print(f"[ERROR] No data returned from Alpaca for {ticker}.")
            return pd.DataFrame()
            
        # Standardize columns
        bars.columns = [col.lower() for col in bars.columns]
        bars = bars[['open', 'high', 'low', 'close', 'volume']].copy()
        bars.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        if bars.index.tz is None:
            bars.index = bars.index.tz_localize('UTC')
        bars.index = bars.index.tz_convert('America/New_York')
        
        print(f"Successfully fetched {len(bars)} bars.")
        return bars
    except Exception as e:
        print(f"[ERROR] Alpaca fetch failed for {ticker}: {e}")
        return pd.DataFrame()

def main():
    ticker = 'AMD'
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        
    if ticker not in BEST_PARAMS:
        print(f"[WARNING] Ticker {ticker} not in pre-mapped safe parameters. Defaulting to AMD settings.")
        params = BEST_PARAMS['AMD']
    else:
        params = BEST_PARAMS[ticker]
        
    df_raw = fetch_historical_oos(ticker)
    if df_raw.empty:
        print("[ERROR] Failed to obtain OOS data. Aborting.")
        return
        
    tf = params['timeframe']
    df_tf = resample_data(df_raw, tf)
    
    # Precompute indicators
    df_tf['atr_14'] = calculate_atr(df_tf, 14)
    df_tf['rsi_14'] = calculate_rsi(df_tf['Close'], 14)
    df_tf['ema_200'] = df_tf['Close'].ewm(span=200, adjust=False).mean()
    
    fast = int(params['fast'])
    slow = int(params['slow'])
    df_tf[f'ema_{fast}'] = df_tf['Close'].ewm(span=fast, adjust=False).mean()
    df_tf[f'ema_{slow}'] = df_tf['Close'].ewm(span=slow, adjust=False).mean()
    
    # Define common strategy closure
    strat_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_generic(
        df_ref, i, pos, cash, ep, mp, fast_period=fast, slow_period=slow
    )
    
    # Run optimal strategy
    print(f"Running OOS optimal strategy for {ticker} (TF: {tf}, Crossover: {fast}/{slow}, Stop: {params['atr_mult']}x, Sizing: {int(params['pos_size']*100)}%)...")
    strat_res = run_safe_backtest(
        ticker=ticker,
        strategy_fn=strat_fn,
        df=df_tf,
        initial_capital=1000.0,
        position_size_pct=params['pos_size'],
        atr_mult=params['atr_mult'],
        stop_mode=params['stop_mode']
    )
    
    # Run Buy & Hold Benchmark (uses 100% allocation, warmup 200)
    bench_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_buy_and_hold(df_ref, i, pos, cash, ep, mp, warmup=200)
    bench_res = run_safe_backtest(
        ticker=ticker,
        strategy_fn=bench_fn,
        df=df_tf,
        initial_capital=1000.0,
        position_size_pct=1.00,
        atr_mult=None,
        stop_mode='intraday'
    )
    
    if not strat_res or not bench_res:
        print("[ERROR] Backtest run failed.")
        return
        
    strat_metrics = strat_res['metrics']
    bench_metrics = bench_res['metrics']
    
    # Calculate weekly return metrics
    portfolio_series = strat_res['portfolio_values']
    weekly_values = portfolio_series.resample('W').last()
    weekly_returns = weekly_values.pct_change().dropna() * 100
    avg_weekly = weekly_returns.mean() if not weekly_returns.empty else 0.0
    
    print("\n" + "="*70)
    print(f"        OUT-OF-SAMPLE (OOS) VERIFICATION RESULTS: {ticker} ")
    print("        Period: May 1, 2025 to Dec 15, 2025 ")
    print("="*70)
    print(f"Strategy Return:      {strat_metrics['total_return_pct']:+.2f}%")
    print(f"Strategy Sharpe:      {strat_metrics['sharpe_ratio']:.2f}")
    print(f"Strategy Max DD:      {strat_metrics['max_drawdown_pct']:.2f}%")
    print(f"Avg Weekly Return:    {avg_weekly:+.2f}%")
    print(f"Total Trades:         {strat_metrics['total_trades']}")
    print("-" * 70)
    print(f"Benchmark Return:     {bench_metrics['total_return_pct']:+.2f}%")
    print(f"Benchmark Sharpe:     {bench_metrics['sharpe_ratio']:.2f}")
    print(f"Benchmark Max DD:     {bench_metrics['max_drawdown_pct']:.2f}%")
    print("="*70 + "\n")
    
    # Setup paths and save curve
    plot_name = f"{ticker}_oos_verification.png"
    artifact_dir = '/Users/ahilannayani/.gemini/antigravity-ide/brain/1ad9a17b-d11c-49f9-953a-d8e886cd635d'
    workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
    
    plot_artifact_path = os.path.join(artifact_dir, plot_name)
    plot_workspace_path = os.path.join(workspace_dir, plot_name)
    
    plot_comparison_curves(
        portfolio_series=strat_res['portfolio_values'],
        benchmark_series=bench_res['portfolio_values'],
        strat_metrics=strat_metrics,
        bench_metrics=bench_metrics,
        ticker=ticker,
        strategy_name=f"Safe Opt ({tf} EMA {fast}/{slow} Stop {params['atr_mult']}x Size {int(params['pos_size']*100)}%)",
        source=f"Alpaca OOS (May-Dec 2025)",
        initial_capital=1000.0,
        output_path=plot_artifact_path
    )
    
    try:
        shutil.copy(plot_artifact_path, plot_workspace_path)
        print(f"[COPY] Copied OOS plot to {plot_workspace_path}")
    except Exception as e:
        print(f"[WARNING] Copying OOS plot to workspace failed: {e}")

if __name__ == '__main__':
    main()
