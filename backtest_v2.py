import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

def fetch_data(ticker, start=None, end=None):
    """
    Fetches 5-minute bar data for the given ticker symbol using yfinance.
    Yahoo Finance limits 5-minute historical data to the last 60 days.
    If the requested range is older or exceeds this limit, this function
    will log a warning and automatically fall back to downloading the maximum 
    allowable period (the last 59 days).

    Parameters:
    - ticker: str, the stock ticker symbol (e.g. 'NVDA').
    - start: str, start date in 'YYYY-MM-DD' format (default: 6 months ago, subject to limit).
    - end: str, end date in 'YYYY-MM-DD' format (default: today).

    Returns:
    - pd.DataFrame with columns ['Close', 'High', 'Low', 'Open', 'Volume'] indexed by datetime
    """
    print(f"\n--- Data Fetching: {ticker} ---")
    
    # Calculate fallback dates (last 59 days)
    today = datetime.now()
    fallback_start = (today - timedelta(days=59)).strftime('%Y-%m-%d')
    fallback_end = today.strftime('%Y-%m-%d')

    # Parse inputs or set defaults (6 months ago to today)
    if start is None:
        start_dt = today - timedelta(days=180)
        start = start_dt.strftime('%Y-%m-%d')
    else:
        start_dt = datetime.strptime(start, '%Y-%m-%d')

    if end is None:
        end = today.strftime('%Y-%m-%d')
        end_dt = today
    else:
        end_dt = datetime.strptime(end, '%Y-%m-%d')

    # Check the 60-day limit for 5-minute data
    limit_cutoff = today - timedelta(days=60)
    
    # If the range start is older than 60 days, we must fall back
    if start_dt < limit_cutoff:
        print(f"[WARNING] Yahoo Finance restricts 5-minute data to the last 60 days.")
        print(f"          Requested start: {start} (cutoff is {limit_cutoff.strftime('%Y-%m-%d')}).")
        print(f"          Falling back to downloading the last 59 days: {fallback_start} to {fallback_end}.")
        start = fallback_start
        end = fallback_end

    print(f"Downloading 5-minute bars for {ticker} from {start} to {end}...")
    
    # yfinance download
    try:
        data = yf.download(ticker, start=start, end=end, interval='5m', progress=False)
    except Exception as e:
        print(f"[ERROR] Failed to download data for {ticker}: {e}")
        return pd.DataFrame()

    if data.empty:
        print(f"[WARNING] No data returned for {ticker} between {start} and {end}.")
        # If the failure might be due to a strict boundary error, try fallback explicitly
        if start != fallback_start:
            print(f"          Retrying with fallback range: {fallback_start} to {fallback_end}...")
            data = yf.download(ticker, start=fallback_start, end=fallback_end, interval='5m', progress=False)
            if data.empty:
                print(f"[ERROR] Fallback download also returned empty.")
                return pd.DataFrame()
        else:
            return pd.DataFrame()

    # Flatten MultiIndex columns if present (recent yfinance versions return MultiIndex columns)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Clean column names just in case
    data.columns = [col.capitalize() for col in data.columns]

    # Convert/localize index to Eastern Time (America/New_York) to match market hours
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    data.index = data.index.tz_convert('America/New_York')

    print(f"Successfully fetched {len(data)} bars.")
    print(f"Data range: {data.index[0]} to {data.index[-1]}")
    return data

def calculate_rsi(series, period=14):
    """
    Calculates standard Wilder's RSI using exponential moving average.
    """
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_atr(df, period=14):
    """
    Calculates 14-period Average True Range (ATR) using Wilder's EMA.
    """
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
    """
    Calculates key performance metrics for the backtest.
    - Total return %
    - Sharpe ratio (use 0% risk-free rate, annualized based on trading day returns)
    - Max drawdown %
    - Win rate %
    - Total number of trades
    - Average trade duration (in minutes)
    """
    initial_val = portfolio_series.iloc[0]
    final_val = portfolio_series.iloc[-1]
    
    # Total Return %
    total_return = ((final_val - initial_val) / initial_val) * 100
    
    # Sharpe Ratio (annualized, 0% risk-free rate, grouped by trading day to avoid weekend bias)
    daily_values = portfolio_series.groupby(portfolio_series.index.date).last()
    daily_returns = daily_values.pct_change().dropna()
    if len(daily_returns) >= 2 and daily_returns.std() > 0:
        # Annualized Sharpe = (mean_daily / std_daily) * sqrt(252)
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

def plot_equity_curve(portfolio_series, ticker, strategy_name):
    """
    Plots a highly polished, dark-themed equity curve and saves it as a PNG.
    """
    plt.style.use('dark_background')
    
    # Color palette
    bg_color = '#0F172A'       # Slate 900
    panel_color = '#1E293B'    # Slate 800
    accent_color = '#38BDF8'   # Sky 400 (electric blue)
    text_muted = '#94A3B8'     # Slate 400
    text_light = '#F8FAFC'     # Slate 50
    grid_color = '#334155'     # Slate 700
    
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=bg_color)
    ax.set_facecolor(panel_color)
    
    # Plot line and filled area
    ax.plot(portfolio_series.index, portfolio_series.values, color=accent_color, linewidth=2, label='Equity Curve')
    ax.fill_between(portfolio_series.index, portfolio_series.values, portfolio_series.iloc[0], color=accent_color, alpha=0.12)
    
    # Calculate performance metrics for the title
    initial_val = portfolio_series.iloc[0]
    final_val = portfolio_series.iloc[-1]
    total_return = ((final_val - initial_val) / initial_val) * 100
    
    # Labels & Title
    ax.set_title(f"{ticker} - {strategy_name} ({total_return:+.2f}% Return)", color=text_light, fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel("Date & Time (EST)", color=text_muted, fontsize=11, labelpad=10)
    ax.set_ylabel("Portfolio Value ($)", color=text_muted, fontsize=11, labelpad=10)
    
    # Format X Axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    fig.autofmt_xdate()
    
    # Grid and Border (Spine) Styling
    ax.grid(True, color=grid_color, linestyle='--', linewidth=0.5, alpha=0.6)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
        spine.set_linewidth(1)
        
    ax.tick_params(colors=text_muted, labelsize=9)
    
    # Legend
    ax.legend(facecolor=panel_color, edgecolor=grid_color, labelcolor=text_light, loc='upper left')
    
    plt.tight_layout()
    filename = f"{ticker}_{strategy_name}_equity.png"
    plt.savefig(filename, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"[PLOT] Equity curve saved to {filename}")

def run_backtest(ticker, strategy_fn, start=None, end=None, initial_capital=10000.0, strategy_name="Strategy", position_size_pct=1.0, plot_equity=True, df=None):
    """
    Main strategy-agnostic backtesting harness.
    
    Parameters:
    - ticker: str, symbol name
    - strategy_fn: callable, signal function called for each bar.
      Signature: strategy_fn(df, i, position, cash, entry_price, max_price_since_entry) -> str or None
    - start: str, 'YYYY-MM-DD' start date
    - end: str, 'YYYY-MM-DD' end date
    - initial_capital: float, cash starting value
    - strategy_name: str, used in logging and saved filenames
    - position_size_pct: float, percentage of initial capital to allocate to each trade
    - plot_equity: bool, if True, plots the equity curve and prints results summary to terminal
    - df: pd.DataFrame, pre-loaded data (if provided, bypasses yfinance fetch)
    
    Returns:
    - dict containing 'metrics', 'portfolio_values', 'trades'
    """
    # 1. Fetch data if not pre-provided
    if df is None:
        df = fetch_data(ticker, start, end)
        if df.empty:
            print(f"[ERROR] Backtest aborted. No data available.")
            return None
    else:
        # Prevent side effects across iterations by using a deep copy
        df = df.copy()

    if plot_equity:
        print(f"\n--- Starting Backtest: {strategy_name} on {ticker} ---")
    
    # 2. Setup state variables
    cash = initial_capital
    position = 0.0
    entry_price = 0.0
    max_price_since_entry = 0.0
    
    portfolio_values = []
    trades_log = []
    active_trade = None
    
    total_bars = len(df)
    log_interval = max(1, total_bars // 5)  # Log progress roughly 5 times
    
    # 3. Simulation Loop
    for i in range(total_bars):
        row = df.iloc[i]
        timestamp = df.index[i]
        price = float(row['Close'])
        high_price = float(row['High'])
        low_price = float(row['Low'])
        
        # Periodic progress logging
        if plot_equity and ((i + 1) % log_interval == 0 or (i + 1) == total_bars):
            percent_complete = ((i + 1) / total_bars) * 100
            print(f"      Progress: {i+1}/{total_bars} bars simulated ({percent_complete:.1f}%)")
            
        # Update high benchmark if holding a long position (useful for trailing stop simulation)
        if position > 0:
            max_price_since_entry = max(max_price_since_entry, high_price)
            
        # Call the strategy signal function
        signal = strategy_fn(df, i, position, cash, entry_price, max_price_since_entry)
        
        # Process signals
        if signal == 'buy' and position == 0:
            # Sizing: Buy using specified position size percentage of initial capital (capped at available cash)
            target_cash = initial_capital * position_size_pct
            shares_to_buy = int(min(cash, target_cash) / price)
            if shares_to_buy > 0:
                cost = shares_to_buy * price
                cash -= cost
                position = shares_to_buy
                entry_price = price
                max_price_since_entry = high_price
                
                active_trade = {
                    'entry_time': timestamp,
                    'entry_price': price,
                    'shares': shares_to_buy
                }
                
        elif signal == 'sell' and position > 0:
            # Sell: liquidate full position
            revenue = position * price
            cash += revenue
            
            if active_trade is not None:
                duration = timestamp - active_trade['entry_time']
                duration_minutes = duration.total_seconds() / 60
                profit = (price - active_trade['entry_price']) * active_trade['shares']
                profit_pct = ((price - active_trade['entry_price']) / active_trade['entry_price']) * 100
                
                completed_trade = {
                    'entry_time': active_trade['entry_time'],
                    'entry_price': active_trade['entry_price'],
                    'exit_time': timestamp,
                    'exit_price': price,
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
            
        # Track portfolio value at the close of the current bar
        current_val = cash + (position * price)
        portfolio_values.append(current_val)

    # 4. Final closeout: liquidate any open position at the final bar's Close price
    if position > 0:
        final_idx = total_bars - 1
        row = df.iloc[final_idx]
        timestamp = df.index[final_idx]
        price = float(row['Close'])
        
        revenue = position * price
        cash += revenue
        
        if active_trade is not None:
            duration = timestamp - active_trade['entry_time']
            duration_minutes = duration.total_seconds() / 60
            profit = (price - active_trade['entry_price']) * active_trade['shares']
            profit_pct = ((price - active_trade['entry_price']) / active_trade['entry_price']) * 100
            
            completed_trade = {
                'entry_time': active_trade['entry_time'],
                'entry_price': active_trade['entry_price'],
                'exit_time': timestamp,
                'exit_price': price,
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
        portfolio_values[-1] = cash # Final portfolio value is cash after closeout
        
    portfolio_series = pd.Series(portfolio_values, index=df.index)
    
    # 5. Calculate metrics
    metrics = calculate_metrics(portfolio_series, trades_log)
    
    # 6. Plot the equity curve if enabled
    if plot_equity:
        plot_equity_curve(portfolio_series, ticker, strategy_name)
        
        # 7. Print nice summary of results
        print("\n" + "="*50)
        print(f" BACKTEST RESULTS: {ticker} ({strategy_name}) ")
        print("="*50)
        print(f"Total Return:         {metrics['total_return_pct']:+.2f}%")
        print(f"Sharpe Ratio:         {metrics['sharpe_ratio']:.2f}")
        print(f"Max Drawdown:         {metrics['max_drawdown_pct']:.2f}%")
        print(f"Win Rate:             {metrics['win_rate_pct']:.2f}%")
        print(f"Total Trades:         {metrics['total_trades']}")
        print(f"Avg Trade Duration:   {metrics['avg_trade_duration_min']:.1f} minutes")
        print("="*50 + "\n")
    
    return {
        'metrics': metrics,
        'portfolio_values': portfolio_series,
        'trades': trades_log
    }

if __name__ == "__main__":
    # Built-in verification test / demo strategy
    def demo_strategy(df, i, position, cash, entry_price, max_price_since_entry):
        """
        Simple EMA Crossover Demo Strategy:
        - Buy: 5-EMA crosses above 20-EMA
        - Sell: 5-EMA crosses below 20-EMA OR 2% Stop Loss OR 5% Trailing Stop
        """
        # Precompute EMAs on the dataframe first
        if 'ema_5' not in df.columns:
            df['ema_5'] = df['Close'].ewm(span=5, adjust=False).mean()
            df['ema_20'] = df['Close'].ewm(span=20, adjust=False).mean()
            
        # Need enough history to compute indicators
        if i < 20:
            return None
            
        price = float(df['Close'].iloc[i])
        
        # Risk Management: Check if we should exit on Stop Loss/Trailing Stop
        if position > 0:
            # 2% Fixed Stop Loss
            if price <= entry_price * 0.98:
                return 'sell'
            # 5% Trailing Stop from highest high reached
            if price <= max_price_since_entry * 0.95:
                return 'sell'
                
        # Trend indicators
        ema_5_curr = df['ema_5'].iloc[i]
        ema_20_curr = df['ema_20'].iloc[i]
        ema_5_prev = df['ema_5'].iloc[i-1]
        ema_20_prev = df['ema_20'].iloc[i-1]
        
        if position == 0:
            # Buy signal (Golden Cross)
            if ema_5_prev <= ema_20_prev and ema_5_curr > ema_20_curr:
                return 'buy'
        else:
            # Sell signal (Death Cross)
            if ema_5_prev >= ema_20_prev and ema_5_curr < ema_20_curr:
                return 'sell'
                
        return None

    # Test the backtester using 59 days of NVDA
    run_backtest(
        ticker='NVDA',
        strategy_fn=demo_strategy,
        strategy_name='Demo_EMA_Cross'
    )
