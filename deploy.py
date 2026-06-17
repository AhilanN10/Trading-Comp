import alpaca_trade_api as tradeapi
import config
import pandas as pd
import time
import json
import os
from datetime import datetime, timedelta
import math

# --- Configuration ---
SYMBOL = 'AMD'
TIMEFRAME = '30Min'
POSITION_SIZE_PCT = 0.90
STATE_FILE = 'bot_state.json'

# --- Alpaca Connection ---
api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')

def get_account():
    return api.get_account()

def get_position(symbol):
    try:
        return api.get_position(symbol)
    except:
        return None

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'max_price_since_entry': 0.0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def fetch_data(symbol):
    """
    Fetches the last 400 30-minute bars of history to ensure stable calculations
    for EMAs (8/25) and Macro EMA (250).
    """
    try:
        # Calculate start date (45 days ago) to get sufficient historical bars for EMA warmup
        start_dt = datetime.now() - timedelta(days=45)
        start_str = start_dt.strftime('%Y-%m-%d')
        
        bars = api.get_bars(symbol, TIMEFRAME, start=start_str, feed='iex').df
        if bars.empty:
            return None
        # Clean column names to lowercase
        bars.columns = [col.lower() for col in bars.columns]
        # Keep only the last 400 bars
        if len(bars) > 400:
            bars = bars.tail(400)
        return bars
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def calculate_indicators(df):
    """
    Calculates 8-period Fast EMA, 25-period Slow EMA, 250-period Macro EMA, and 14-period Wilder's RSI.
    """
    df['ema_fast'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=25, adjust=False).mean()
    df['ema_macro'] = df['close'].ewm(span=250, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).copy()
    loss = (-delta.where(delta < 0, 0)).copy()
    
    avg_gain = gain.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def run_bot():
    print(f"--- Starting Live Bot for {SYMBOL} ---")
    print(f"Strategy: EMA Crossover Momentum (8/25) with 250 EMA Trend Filter & RSI < 65")
    print(f"Safety: No Trailing Stop (Crossover Exit) | Size: {POSITION_SIZE_PCT*100}%")
    
    state = load_state()
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Checking market...")
            
            # Get Data
            df = fetch_data(SYMBOL)
            if df is None or len(df) < 250:
                print("Not enough data yet (need at least 250 bars).")
                time.sleep(30)
                continue
                
            df = calculate_indicators(df)
            
            # Extract latest completed and previous bars to check crossovers
            current_bar = df.iloc[-1]
            prev_bar = df.iloc[-2]
            
            fast_curr = current_bar['ema_fast']
            slow_curr = current_bar['ema_slow']
            macro_curr = current_bar['ema_macro']
            rsi_curr = current_bar['rsi']
            
            fast_prev = prev_bar['ema_fast']
            slow_prev = prev_bar['ema_slow']
            
            # Guard against NaNs
            if pd.isna(fast_curr) or pd.isna(slow_curr) or pd.isna(macro_curr) or pd.isna(rsi_curr):
                print(f"Indicators not ready yet (Fast: {fast_curr}, Slow: {slow_curr}, Macro: {macro_curr}, RSI: {rsi_curr}).")
                time.sleep(30)
                continue
            
            latest_trade = api.get_latest_trade(SYMBOL)
            current_price = latest_trade.price
            
            print(f"Price: ${current_price:.2f} | Fast EMA: ${fast_curr:.2f} | Slow EMA: ${slow_curr:.2f} | Macro: ${macro_curr:.2f} | RSI: {rsi_curr:.1f}")
            
            # Check Position
            position = get_position(SYMBOL)
            
            if position is None:
                # --- NO POSITION: Look for BUY ---
                # Reset state if flat
                if state['max_price_since_entry'] > 0:
                    state['max_price_since_entry'] = 0.0
                    save_state(state)
                
                # BUY Conditions:
                # 1. Bullish crossover (8 crosses above 25)
                # 2. Price > 250 EMA
                # 3. RSI < 65
                crossover_buy = fast_prev <= slow_prev and fast_curr > slow_curr
                trend_ok = current_price > macro_curr
                rsi_ok = rsi_curr < 65.0
                
                if crossover_buy:
                    print(f"Crossover signal detected. Checking filters -> Trend OK: {trend_ok}, RSI OK: {rsi_ok}")
                    
                if crossover_buy and trend_ok and rsi_ok:
                    print(f"SIGNAL: BUY (EMA crossover, Trend Bullish, RSI oversold/moderate)")
                    
                    # Calculate Size (90% of Buying Power) using fractional shares rounded to 4 decimals
                    account = get_account()
                    buying_power = float(account.buying_power)
                    target_amt = buying_power * POSITION_SIZE_PCT
                    qty = round(target_amt / current_price, 4)
                    
                    if qty > 0.0:
                        print(f"Submitting BUY order for {qty} shares...")
                        api.submit_order(
                            symbol=SYMBOL,
                            qty=qty,
                            side='buy',
                            type='market',
                            time_in_force='day'
                        )
                        state['max_price_since_entry'] = current_price
                        save_state(state)
                        print("Order Submitted.")
                    else:
                        print("Insufficient funds to buy.")
                else:
                    print("No buy signal: conditions not met.")
            
            else:
                # --- HAVE POSITION: Look for SELL ---
                qty = float(position.qty)
                entry_price = float(position.avg_entry_price)
                
                print(f"Position: {qty} shares @ ${entry_price:.2f}")
                
                # Check exit condition: Bearish crossover (8 crosses below 25)
                if fast_prev >= slow_prev and fast_curr < slow_curr:
                    print(f"SIGNAL: SELL (Bearish Crossover: Fast EMA {fast_curr:.2f} < Slow EMA {slow_curr:.2f})")
                    print(f"Submitting SELL order for {qty} shares...")
                    api.submit_order(
                        symbol=SYMBOL,
                        qty=qty,
                        side='sell',
                        type='market',
                        time_in_force='day'
                    )
                    state['max_price_since_entry'] = 0.0
                    save_state(state)
                    print("Order Submitted.")
                else:
                    print("Holding position.")
            
            # Sleep for 30 seconds
            print("Waiting 30 seconds for next check...")
            time.sleep(30)
            
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            time.sleep(30)

if __name__ == "__main__":
    run_bot()
