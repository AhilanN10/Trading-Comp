import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import alpaca_trade_api as tradeapi

# Add directory to path to ensure config is imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config

def fetch_data(symbol, start=None, end=None, source='alpaca'):
    """
    Fetches historical 5-minute bar data for the given symbol from either yfinance or Alpaca.
    Automatically standardizes column names and localizes to America/New_York.
    """
    print(f"\n--- Data Fetching: {symbol} via {source.upper()} ---")
    today = datetime.now()
    
    if source == 'alpaca':
        # Setup Alpaca REST API
        api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
        ny_tz = pytz.timezone('America/New_York')
        end_dt = datetime.now(ny_tz)
        
        # 180 days default lookup window
        if start is None:
            start_dt = end_dt - timedelta(days=180)
        else:
            start_dt = datetime.strptime(start, '%Y-%m-%d')
            
        start_str = start_dt.astimezone(pytz.utc).isoformat().replace('+00:00', 'Z')
        
        print(f"Fetching 5-minute bars from Alpaca starting {start_str}...")
        try:
            # We omit end parameter to get all data up to latest available delayed data
            # and explicitly request feed='iex' to bypass the SIP subscription error
            bars = api.get_bars(
                symbol,
                '5Min',
                start=start_str,
                feed='iex',
                adjustment='raw'
            ).df
            
            if bars.empty:
                print(f"[WARNING] No data returned from Alpaca for {symbol}.")
                return pd.DataFrame()
                
            # Clean columns and index
            bars.columns = [col.lower() for col in bars.columns]
            bars = bars[['open', 'high', 'low', 'close', 'volume']].copy()
            bars.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            if bars.index.tz is None:
                bars.index = bars.index.tz_localize('UTC')
            bars.index = bars.index.tz_convert('America/New_York')
            
            print(f"Successfully fetched {len(bars)} bars from Alpaca.")
            print(f"Data range: {bars.index[0]} to {bars.index[-1]}")
            return bars
            
        except Exception as e:
            print(f"[ERROR] Alpaca fetch failed: {e}")
            return pd.DataFrame()
            
    elif source == 'yfinance':
        fallback_start = (today - timedelta(days=59)).strftime('%Y-%m-%d')
        fallback_end = today.strftime('%Y-%m-%d')
        
        if start is None:
            start = fallback_start
            
        print(f"Downloading 5-minute bars from yfinance from {start}...")
        try:
            data = yf.download(symbol, start=start, interval='5m', progress=False)
        except Exception as e:
            print(f"[ERROR] yfinance fetch failed: {e}")
            return pd.DataFrame()
            
        if data.empty:
            print(f"[WARNING] No data returned from yfinance for {symbol}.")
            return pd.DataFrame()
            
        # Flatten MultiIndex if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        data.columns = [col.capitalize() for col in data.columns]
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        if data.index.tz is None:
            data.index = data.index.tz_localize('UTC')
        data.index = data.index.tz_convert('America/New_York')
        
        print(f"Successfully fetched {len(data)} bars from yfinance.")
        print(f"Data range: {data.index[0]} to {data.index[-1]}")
        return data
        
    else:
        raise ValueError(f"Invalid data source: {source}")

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df, period=14):
    high = df['High']
    low = df['Low']
    close_prev = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def calculate_metrics(portfolio_series, trades):
    initial_val = portfolio_series.iloc[0]
    final_val = portfolio_series.iloc[-1]
    
    # Total Return %
    total_return = ((final_val - initial_val) / initial_val) * 100
    
    # Sharpe Ratio (annualized, 0% risk-free rate, grouped by trading day to avoid weekend bias)
    daily_values = portfolio_series.groupby(portfolio_series.index.date).last()
    daily_returns = daily_values.pct_change().dropna()
    if len(daily_returns) >= 2 and daily_returns.std() > 0:
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    # Max Drawdown %
    peaks = portfolio_series.cummax()
    drawdowns = (portfolio_series - peaks) / peaks
    max_dd = abs(drawdowns.min() * 100)
    
    # Win Rate % and Trade Count
    total_trades = len(trades)
    if total_trades > 0:
        wins = sum(1 for t in trades if t['profit'] > 0)
        win_rate = (wins / total_trades) * 100
        avg_duration = sum(t['duration_minutes'] for t in trades) / total_trades
    else:
        win_rate = 0.0
        avg_duration = 0.0

    return {
        'total_return_pct': float(total_return),
        'sharpe_ratio': float(sharpe),
        'max_drawdown_pct': float(max_dd),
        'win_rate_pct': float(win_rate),
        'total_trades': total_trades,
        'avg_trade_duration_min': float(avg_duration)
    }

def run_realistic_backtest(ticker, strategy_fn, initial_capital=1000.0, position_size_pct=0.70,
                           slippage_pct=0.0005, fee_per_share=0.002, plot_equity=True, df=None,
                           atr_mult=2.0, strategy_name="Strategy"):
    """
    Hyperrealistic backtester modeling slippage, share fees, next-bar Open execution,
    and intraday trailing stop-loss triggers.
    """
    if df is None:
        raise ValueError("DataFrame must be pre-provided to run_realistic_backtest")
        
    df = df.copy()
    
    # Ensure EMA & ATR indicators are present
    if 'ema_3' not in df.columns:
        df['ema_3'] = df['Close'].ewm(span=3, adjust=False).mean()
    if 'ema_30' not in df.columns:
        df['ema_30'] = df['Close'].ewm(span=30, adjust=False).mean()
    if 'ema_200' not in df.columns:
        df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
    if 'atr_14' not in df.columns:
        df['atr_14'] = calculate_atr(df, 14)
        
    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    max_price_since_entry = 0.0
    
    portfolio_values = []
    trades_log = []
    active_trade = None
    
    pending_buy = False
    pending_sell = False
    
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
        
        # 1. Execute any pending signals from previous bar at Open of current bar
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
            
        elif pending_sell and position > 0:
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
            
        # 2. Check stop-loss on current bar (intraday low execution)
        if position > 0 and atr_mult is not None and atr_mult > 0.0:
            stop_price = max_price_since_entry - atr_mult * atr
            if low_price <= stop_price:
                # Triggered stop loss
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
                
        # 3. Evaluate signals for next-bar Open execution
        if position > 0 and not pending_sell:
            signal = strategy_fn(df, i, position, cash, entry_price, max_price_since_entry)
            if signal == 'sell':
                pending_sell = True
        elif position == 0 and not pending_buy and not stopped_out_this_bar:
            signal = strategy_fn(df, i, position, cash, entry_price, max_price_since_entry)
            if signal == 'buy':
                pending_buy = True
                
        # Track portfolio value at the end of the bar
        current_val = cash + (position * close_price)
        portfolio_values.append(current_val)
        
    # 4. Final closeout: liquidate any open position at final bar's Close price
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

def strategy_option_c(df, i, position, cash, entry_price, max_price_since_entry, 
                      fast_period=3, slow_period=30, use_ema_200=True):
    """
    Option C: EMA Crossover 3/30 with 200 EMA Filter.
    """
    fast_col = f'ema_{fast_period}'
    slow_col = f'ema_{slow_period}'
    
    # Needs warmup for 200 EMA
    if i < 200 or i < 1:
        return None
        
    price = float(df['Close'].iloc[i])
    fast_curr = float(df[fast_col].iloc[i])
    slow_curr = float(df[slow_col].iloc[i])
    fast_prev = float(df[fast_col].iloc[i-1])
    slow_prev = float(df[slow_col].iloc[i-1])
    
    if position > 0:
        # Bearish crossover exit
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            return 'sell'
    else:
        # Bullish crossover entry
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            if use_ema_200:
                ema_200 = float(df['ema_200'].iloc[i])
                if price > ema_200:
                    return 'buy'
            else:
                return 'buy'
                
    return None

def strategy_buy_and_hold(df, i, position, cash, entry_price, max_price_since_entry, warmup=200):
    """
    Benchmark: Buys at first bar post-warmup and holds.
    """
    if i == warmup and position == 0:
        return 'buy'
    return None

def plot_comparison_curves(portfolio_series, benchmark_series, strat_metrics, bench_metrics, 
                           ticker, strategy_name, source, initial_capital, output_path):
    plt.style.use('dark_background')
    
    # Theme colors
    bg_color = '#0F172A'       # Slate 900
    panel_color = '#1E293B'    # Slate 800
    accent_strategy = '#38BDF8' # Sky 400 (electric blue)
    accent_benchmark = '#94A3B8' # Slate 400 (muted grey)
    text_light = '#F8FAFC'     # Slate 50
    text_muted = '#94A3B8'     # Slate 400
    grid_color = '#334155'     # Slate 700
    
    fig, ax = plt.subplots(figsize=(14, 7), facecolor=bg_color)
    ax.set_facecolor(panel_color)
    
    # Plot Strategy
    ax.plot(portfolio_series.index, portfolio_series.values, color=accent_strategy, linewidth=2.5, 
            label=f"Option C: EMA 3/30 (Return: {strat_metrics['total_return_pct']:+.2f}%)")
    ax.fill_between(portfolio_series.index, portfolio_series.values, portfolio_series.iloc[0], color=accent_strategy, alpha=0.10)
    
    # Plot Benchmark
    ax.plot(benchmark_series.index, benchmark_series.values, color=accent_benchmark, linewidth=1.5, linestyle='--', 
            label=f"Buy & Hold TQQQ (Return: {bench_metrics['total_return_pct']:+.2f}%)")
    
    # Title & Labels
    ax.set_title(f"TQQQ Realistic Simulation ({source.upper()}): {strategy_name} vs. Benchmark\n"
                 f"Strategy Sharpe: {strat_metrics['sharpe_ratio']:.2f} (Max DD: {strat_metrics['max_drawdown_pct']:.2f}%) | "
                 f"Benchmark Sharpe: {bench_metrics['sharpe_ratio']:.2f} (Max DD: {bench_metrics['max_drawdown_pct']:.2f}%)", 
                 color=text_light, fontsize=12, fontweight='bold', pad=15)
    
    ax.set_xlabel("Date & Time (EST)", color=text_muted, fontsize=11, labelpad=10)
    ax.set_ylabel("Portfolio Value ($)", color=text_muted, fontsize=11, labelpad=10)
    
    # Format dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    fig.autofmt_xdate()
    
    # Grid and Spines
    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5, alpha=0.6)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
        spine.set_linewidth(1)
        
    ax.tick_params(colors=text_muted, labelsize=9)
    ax.legend(facecolor=panel_color, edgecolor=grid_color, labelcolor=text_light, loc='upper left', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"[PLOT] Comparison curve saved to {output_path}")

def run_flow():
    ticker = 'TQQQ'
    initial_capital = 1000.0
    position_size_pct = 0.70
    
    # Output directories
    artifact_dir = '/Users/ahilannayani/.gemini/antigravity-ide/brain/1ad9a17b-d11c-49f9-953a-d8e886cd635d'
    workspace_dir = '/Users/ahilannayani/Personal Python Projects/Trading Comp/alpaca_sim'
    
    # Create directories if they do not exist
    os.makedirs(artifact_dir, exist_ok=True)
    os.makedirs(workspace_dir, exist_ok=True)
    
    # Storage for comparison table
    summary_results = []
    
    for source in ['yfinance', 'alpaca']:
        df = fetch_data(ticker, source=source)
        if df.empty:
            print(f"[ERROR] Could not fetch data from {source}. Skipping.")
            continue
            
        # Precompute indicators to ensure both strategy and benchmark use the same pre-computed df
        df['ema_3'] = df['Close'].ewm(span=3, adjust=False).mean()
        df['ema_30'] = df['Close'].ewm(span=30, adjust=False).mean()
        df['ema_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['atr_14'] = calculate_atr(df, 14)
        df['rsi_14'] = calculate_rsi(df['Close'], 14)
        
        # Run Option C
        strat_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_option_c(
            df_ref, i, pos, cash, ep, mp, fast_period=3, slow_period=30, use_ema_200=True
        )
        strat_res = run_realistic_backtest(
            ticker=ticker,
            strategy_fn=strat_fn,
            initial_capital=initial_capital,
            position_size_pct=position_size_pct,
            plot_equity=False,
            df=df,
            atr_mult=2.0,
            strategy_name="EMA_Crossover_3_30_OptionC"
        )
        
        # Run Buy & Hold Benchmark
        bench_fn = lambda df_ref, i, pos, cash, ep, mp: strategy_buy_and_hold(df_ref, i, pos, cash, ep, mp, warmup=200)
        bench_res = run_realistic_backtest(
            ticker=ticker,
            strategy_fn=bench_fn,
            initial_capital=initial_capital,
            position_size_pct=1.00,  # 100% position size for Buy & Hold
            plot_equity=False,
            df=df,
            atr_mult=None,
            strategy_name="Buy_and_Hold"
        )
        
        if not strat_res or not bench_res:
            print(f"[ERROR] Simulation failed on {source}.")
            continue
            
        strat_metrics = strat_res['metrics']
        bench_metrics = bench_res['metrics']
        
        # Plot and save curves
        plot_name = f"TQQQ_EMA_3_30_realistic_{source}.png"
        artifact_path = os.path.join(artifact_dir, plot_name)
        workspace_path = os.path.join(workspace_dir, plot_name)
        
        plot_comparison_curves(
            portfolio_series=strat_res['portfolio_values'],
            benchmark_series=bench_res['portfolio_values'],
            strat_metrics=strat_metrics,
            bench_metrics=bench_metrics,
            ticker=ticker,
            strategy_name="EMA Crossover (3/30) + 200 EMA Filter",
            source=source,
            initial_capital=initial_capital,
            output_path=artifact_path
        )
        
        # Copy to workspace
        import shutil
        try:
            shutil.copy(artifact_path, workspace_path)
            print(f"[COPY] Copied plot to {workspace_path}")
        except Exception as e:
            print(f"[WARNING] Copy failed: {e}")
            
        summary_results.append({
            'source': source,
            'strat_ret': strat_metrics['total_return_pct'],
            'strat_sharpe': strat_metrics['sharpe_ratio'],
            'strat_dd': strat_metrics['max_drawdown_pct'],
            'strat_win': strat_metrics['win_rate_pct'],
            'strat_trades': strat_metrics['total_trades'],
            'bench_ret': bench_metrics['total_return_pct'],
            'bench_sharpe': bench_metrics['sharpe_ratio'],
            'bench_dd': bench_metrics['max_drawdown_pct']
        })
        
    print("\n" + "="*80)
    print("                HYPERREALISTIC COMPARISON SUMMARY TABLE")
    print("="*80)
    print(f"{'Source':<10} | {'Strategy Return':<15} | {'Strat Sharpe':<12} | {'Strat DD':<10} | {'Trades':<8} | {'Bench Return':<12} | {'Bench DD':<8}")
    print("-"*80)
    for res in summary_results:
        print(f"{res['source'].upper():<10} | {res['strat_ret']:+14.2f}% | {res['strat_sharpe']:12.2f} | {res['strat_dd']:8.2f}% | {res['strat_trades']:<8} | {res['bench_ret']:+11.2f}% | {res['bench_dd']:7.2f}%")
    print("="*80 + "\n")

if __name__ == '__main__':
    run_flow()
