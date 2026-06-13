import alpaca_trade_api as tradeapi
import pandas as pd
import matplotlib.pyplot as plt
import config
from datetime import datetime, timedelta
import random
import numpy as np

# --- Data Fetching ---
def fetch_data(symbol=None, random_slice=True):
    if symbol is None:
        symbol = config.SYMBOL
        
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    # Fetch data for the last 6 months
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    print(f"Fetching data for {symbol} from {start_date.date()} to {end_date.date()}...")
    
    bars = api.get_bars(
        symbol,
        config.TIMEFRAME,
        start=start_date.isoformat(timespec='seconds') + "Z",
        end=end_date.isoformat(timespec='seconds') + "Z",
        adjustment='raw'
    ).df
    
    if bars.empty:
        return pd.DataFrame()
        
    # Localize/Convert index
    if bars.index.tz is None:
        bars.index = bars.index.tz_localize('UTC')
    bars.index = bars.index.tz_convert('America/New_York')
    
    if not random_slice:
        return bars

    # Select Random Week
    if len(bars) > 0:
        min_date = bars.index[0]
        max_date = bars.index[-1] - timedelta(days=7)
        
        if max_date > min_date:
            random_start = min_date + timedelta(days=random.randint(0, (max_date - min_date).days))
            random_end = random_start + timedelta(days=7)
            
            print(f"Selected Random Week: {random_start.date()} to {random_end.date()}")
            
            df_slice = bars[(bars.index >= random_start) & (bars.index <= random_end)].copy()
            return df_slice
            
    return bars

# --- Indicators ---
def calculate_indicators(df, window=20):
    # Mean Reversion
    df['avg_low'] = df['low'].rolling(window=window).mean()
    df['avg_high'] = df['high'].rolling(window=window).mean()
    df['std_low'] = df['low'].rolling(window=window).std() # For Z-Score
    
    # Momentum (MACD + EMA)
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean() # Added for Trend Filter
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema_12'] - df['ema_26']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Volume
    df['avg_volume'] = df['volume'].rolling(window=20).mean() # Added for Volume Filter
    
    # Volatility Breakout (Bollinger)
    df['bb_mid'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_mid'] + (2 * df['bb_std'])
    df['bb_lower'] = df['bb_mid'] - (2 * df['bb_std'])
    df['bandwidth'] = (df['bb_upper'] - df['bb_lower']) / df['bb_mid']
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    return df

# --- Strategies ---

def strategy_mean_reversion(row, position, cash, price, entry_price=0.0, stop_loss_pct=None, **kwargs):
    # Buy: Price < Avg Low
    # Sell: Price >= Avg High OR Stop Loss
    
    avg_low = row['avg_low']
    avg_high = row['avg_high']
    
    if pd.isna(avg_low) or pd.isna(avg_high):
        return None

    if position == 0:
        if row['low'] < avg_low:
            return 'buy'
    elif position > 0:
        # Check Stop Loss first
        if stop_loss_pct is not None and entry_price > 0:
            if price < entry_price * (1 - stop_loss_pct):
                return 'sell'
                
        if row['high'] >= avg_high:
            return 'sell'
            
    return None

def strategy_mean_reversion_advanced(row, position, cash, price, entry_price=0.0, stop_loss_pct=None, take_profit_pct=None, entry_z_score=0.0, rsi_threshold=None, **kwargs):
    # Advanced Mean Reversion
    # Buy: Price < (Avg Low - (Std Low * Z-Score)) AND (RSI < Threshold if set)
    # Sell: Price >= Avg High OR Stop Loss OR Take Profit
    
    avg_low = row['avg_low']
    avg_high = row['avg_high']
    std_low = row.get('std_low', 0)
    rsi = row.get('rsi', 50)
    
    if pd.isna(avg_low) or pd.isna(avg_high):
        return None
        
    # Calculate Buy Threshold
    buy_threshold = avg_low - (std_low * entry_z_score)

    if position == 0:
        # Check RSI Filter
        if rsi_threshold is not None and not pd.isna(rsi):
            if rsi > rsi_threshold:
                return None
                
        if row['low'] < buy_threshold:
            return 'buy'
            
    elif position > 0:
        # Check Stop Loss
        if stop_loss_pct is not None and entry_price > 0:
            if price < entry_price * (1 - stop_loss_pct):
                return 'sell'
        
        # Check Take Profit
        if take_profit_pct is not None and entry_price > 0:
            if price > entry_price * (1 + take_profit_pct):
                return 'sell'
                
        # Standard Exit
        if row['high'] >= avg_high:
            return 'sell'
            
    return None

def strategy_mean_reversion_filtered(row, position, cash, price, entry_price=0.0, stop_loss_pct=None, trend_ema=None, volume_multiplier=None, trailing_stop_pct=None, **kwargs):
    # Filtered Mean Reversion
    # Buy: Price < Avg Low
    # Filters:
    #   - Trend: Price > EMA (if trend_ema set)
    #   - Volume: Volume > Avg Volume * Multiplier (if volume_multiplier set)
    # Sell: Price >= Avg High OR Trailing Stop
    
    avg_low = row['avg_low']
    avg_high = row['avg_high']
    
    if pd.isna(avg_low) or pd.isna(avg_high):
        return None
        
    # Trailing Stop Logic (Requires external state tracking, but simulated here via 'high' since entry)
    # Note: In a real backtest engine, trailing stop needs tick-by-tick high tracking. 
    # Here we approximate: If current price < max_price_since_entry * (1 - trailing_stop_pct) -> Sell.
    # However, 'row' only has current bar. We need to pass 'max_price' in kwargs or track it.
    # For simplicity in this framework: We'll use a fixed stop loss relative to entry for now, 
    # OR we can try to use the current bar's high as a proxy for "recent high" if we were tracking it.
    # Let's stick to the requested logic:
    # If trailing_stop_pct is passed, we need to know the highest price reached since entry.
    # The current engine doesn't support stateful 'max_price' tracking easily without modifying run_backtest.
    # WORKAROUND: We will modify run_backtest to track 'max_price_since_entry'.
    
    max_price = kwargs.get('max_price_since_entry', entry_price)
    
    if position == 0:
        # Trend Filter
        if trend_ema is not None:
            ema_col = f'ema_{trend_ema}'
            if ema_col in row and not pd.isna(row[ema_col]):
                if price < row[ema_col]:
                    return None # Don't buy if below EMA
                    
        # Volume Filter
        if volume_multiplier is not None:
            # We need avg_volume. Let's assume it's calculated in indicators or on the fly.
            # Let's add avg_volume to indicators first.
            if 'avg_volume' in row and not pd.isna(row['avg_volume']):
                if row['volume'] < row['avg_volume'] * volume_multiplier:
                    return None # Don't buy if volume is low
        
        if row['low'] < avg_low:
            return 'buy'
            
    elif position > 0:
        # Trailing Stop
        if trailing_stop_pct is not None and max_price > 0:
            if price < max_price * (1 - trailing_stop_pct):
                return 'sell'
                
        # Standard Exit
        if row['high'] >= avg_high:
            return 'sell'
            
    return None

def strategy_momentum(row, position, cash, price, entry_price=0.0, **kwargs):
    # Buy: MACD > Signal AND Price > 200 EMA
    # Sell: MACD < Signal
    
    if pd.isna(row['macd']) or pd.isna(row['signal']) or pd.isna(row['ema_200']):
        return None
        
    if position == 0:
        if row['macd'] > row['signal'] and row['close'] > row['ema_200']:
            return 'buy'
    elif position > 0:
        if row['macd'] < row['signal']:
            return 'sell'
            
    return None

def strategy_breakout(row, position, cash, price, entry_price=0.0, **kwargs):
    # Buy: Bandwidth < 0.05 (Squeeze - arbitrary threshold, let's say 5th percentile or fixed) 
    # AND Price > Upper Band
    # Let's use a fixed bandwidth threshold or just Price > Upper Band if we want to catch any breakout.
    # Let's add volume confirmation: Volume > 1.5 * Avg Volume (not calculated here, skipping for simplicity)
    
    # Simplified Breakout: Close > Upper Band
    # Sell: Close < Middle Band
    
    if pd.isna(row['bb_upper']):
        return None
        
    if position == 0:
        if row['close'] > row['bb_upper']:
            return 'buy'
    elif position > 0:
        if row['close'] < row['bb_mid']:
            return 'sell'
            
    return None

def strategy_rsi_reversal(row, position, cash, price, entry_price=0.0, **kwargs):
    # Buy: RSI < 30
    # Sell: RSI > 70 OR Stop Loss (handled in engine? No, let's handle here simply)
    
    if pd.isna(row['rsi']):
        return None
        
    if position == 0:
        if row['rsi'] < 30:
            return 'buy'
    elif position > 0:
        if row['rsi'] > 70:
            return 'sell'
            
    return None

def strategy_scalping(row, position, cash, price, entry_price=0.0, stop_loss_pct=0.005, take_profit_pct=0.01, rsi_buy_threshold=30, rsi_sell_threshold=70, **kwargs):
    """
    Scalping Strategy:
    - Buy: RSI < Buy Threshold
    - Sell: RSI > Sell Threshold OR Take Profit OR Stop Loss
    """
    rsi = row.get('rsi', 50)
    
    if pd.isna(rsi):
        return None
        
    if position == 0:
        if rsi < rsi_buy_threshold:
            return 'buy'
            
    elif position > 0:
        # Check Stop Loss
        if stop_loss_pct is not None and entry_price > 0:
            if price < entry_price * (1 - stop_loss_pct):
                return 'sell'
        
        # Check Take Profit
        if take_profit_pct is not None and entry_price > 0:
            if price > entry_price * (1 + take_profit_pct):
                return 'sell'
                
        # RSI Exit
        if rsi > rsi_sell_threshold:
            return 'sell'
            
    return None

def strategy_grid_scalping(row, position, cash, price, entry_price=0.0, **kwargs):
    # Hyper-Active Grid Scalping
    # Logic: Simulate capturing the spread multiple times within the minute based on High-Low range.
    
    grid_step = 0.05 # $0.05 grid
    candle_range = row['high'] - row['low']
    
    if candle_range < grid_step:
        return None
        
    # Number of successful round-trip scalps we could theoretically capture
    # We assume we capture the move both ways or just one way? 
    # Let's assume we capture "crossings". If range is 0.15, we have 3 steps.
    # We assume we buy and sell each step.
    crossings = int(candle_range / grid_step)
    
    if crossings == 0:
        return None
        
    # Calculate profit
    # We use full cash to size the trade (compounding aggressively)
    # In reality, you'd split size, but for "max return" simulation:
    shares = int(cash / price)
    if shares == 0:
        return None
        
    profit_per_scalp = grid_step * shares
    total_profit = profit_per_scalp * crossings
    
    return {'profit': total_profit, 'trades': crossings, 'shares': shares}

# --- Backtest Engine ---

def run_backtest(df, strategy_func, strategy_name, strategy_params=None):
    cash = config.START_CAPITAL
    position = 0
    entry_price = 0.0 # Track average entry price
    max_price_since_entry = 0.0 # Track max price for trailing stop
    portfolio_values = []
    trades = []
    
    if strategy_params is None:
        strategy_params = {}
    
    print(f"Simulating: {strategy_name} (Params: {strategy_params})...")
    
    for index, row in df.iterrows():
        price = row['close']
        
        # Update Max Price if in position
        if position > 0:
            if price > max_price_since_entry:
                max_price_since_entry = price
        
        # Execute Strategy
        # Pass entry_price, max_price_since_entry and params
        signal = strategy_func(row, position, cash, price, entry_price, max_price_since_entry=max_price_since_entry, **strategy_params)
        
        if isinstance(signal, dict):
            # Bulk Trade / Grid Scalping Logic
            profit = signal.get('profit', 0)
            count = signal.get('trades', 0)
            
            if profit > 0:
                cash += profit
                for _ in range(count):
                    trades.append({'type': 'buy', 'price': price, 'time': index, 'strategy': strategy_name})
                    trades.append({'type': 'sell', 'price': price + 0.05, 'time': index, 'strategy': strategy_name})
                    
        elif signal == 'buy' and position == 0:
            shares_to_buy = int(cash / price)
            if shares_to_buy > 0:
                cost = shares_to_buy * price
                cash -= cost
                position += shares_to_buy
                entry_price = price # Set entry price
                max_price_since_entry = price # Reset max price
                trades.append({'type': 'buy', 'price': price, 'time': index, 'strategy': strategy_name})
                
        elif signal == 'sell' and position > 0:
            revenue = position * price
            cash += revenue
            position = 0
            entry_price = 0.0 # Reset
            max_price_since_entry = 0.0 # Reset
            trades.append({'type': 'sell', 'price': price, 'time': index, 'strategy': strategy_name})
            
        # Update Value
        current_val = cash + (position * price)
        portfolio_values.append(current_val)
        
    return portfolio_values, trades

def analyze_results(results_dict):
    summary = []
    
    plt.figure(figsize=(14, 7))
    
    for name, data in results_dict.items():
        values = data['values']
        trades = data['trades']
        df_index = data['index']
        
        final_val = values[-1]
        total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
        trade_count = len(trades)
        
        # Win Rate
        wins = 0
        for i in range(0, len(trades) - 1, 2):
            if trades[i]['type'] == 'buy' and trades[i+1]['type'] == 'sell':
                if trades[i+1]['price'] > trades[i]['price']:
                    wins += 1
        win_rate = (wins / (trade_count / 2)) * 100 if trade_count > 0 else 0
        
        summary.append({
            'Strategy': name,
            'Return (%)': total_return,
            'Final Value ($)': final_val,
            'Trades': trade_count,
            'Win Rate (%)': win_rate
        })
        
        plt.plot(df_index, values, label=f"{name} ({total_return:.1f}%)")
        
    plt.title(f'Strategy Comparison: {config.SYMBOL}')
    plt.xlabel('Time')
    plt.ylabel('Portfolio Value ($)')
    plt.legend()
    plt.grid(True)
    plt.savefig('strategy_comparison.png')
    print("Chart saved to strategy_comparison.png")
    
    return pd.DataFrame(summary)

if __name__ == "__main__":
    try:
        data = fetch_data()
        if data.empty:
            print("No data fetched.")
        else:
            # Calculate Indicators once
            data = calculate_indicators(data)
            
            strategies = {
                "Mean Reversion": strategy_mean_reversion,
                "Momentum (MACD)": strategy_momentum,
                "Breakout (Bollinger)": strategy_breakout,
                "RSI Reversal": strategy_rsi_reversal,
                "Grid Scalping (HFT)": strategy_grid_scalping
            }
            
            results_store = {}
            
            for name, func in strategies.items():
                values, trades = run_backtest(data, func, name)
                results_store[name] = {
                    'values': values,
                    'trades': trades,
                    'index': data.index
                }
                
            # The strategy_scalping function has a different signature and returns portfolio_values, trades directly.
            # It's not designed to be passed to run_backtest in the same way as the other strategies.
            # If you intend to run it, you would call it separately:
            # scalping_values, scalping_trades = strategy_scalping(data)
            # results_store["Scalping"] = {
            #     'values': scalping_values,
            #     'trades': scalping_trades,
            #     'index': data.index
            # }
            
            summary_df = analyze_results(results_store)
            print("\nPerformance Summary:")
            print(summary_df.to_string(index=False))
            
            summary_df.to_csv('strategy_summary.csv', index=False)
            
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
