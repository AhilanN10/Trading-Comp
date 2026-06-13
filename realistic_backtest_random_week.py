import alpaca_trade_api as tradeapi
import pandas as pd
import matplotlib.pyplot as plt
import config
from datetime import datetime, timedelta
import numpy as np
import random

def fetch_random_week_2025(symbol):
    """Fetch data for a random week in 2025"""
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    # Define 2025 date range
    year_start = datetime(2025, 1, 1)
    year_end = datetime(2025, 11, 21)  # Up to today
    
    # Pick random start date
    days_in_range = (year_end - year_start).days - 7
    random_day = random.randint(0, days_in_range)
    start_date = year_start + timedelta(days=random_day)
    end_date = start_date + timedelta(days=7)
    
    start_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
    end_str = end_date.strftime('%Y-%m-%dT23:59:59Z')
    
    print(f"Fetching data for {symbol} from {start_date.date()} to {end_date.date()}...")
    
    bars = api.get_bars(
        symbol,
        '1Min',
        start=start_str,
        end=end_str,
        adjustment='raw'
    ).df
    
    if bars.empty:
        return pd.DataFrame(), start_date, end_date
        
    # Localize/Convert index
    if bars.index.tz is None:
        bars.index = bars.index.tz_localize('UTC')
    bars.index = bars.index.tz_convert('America/New_York')
    
    return bars, start_date, end_date

def calculate_indicators(df, window=5):
    """Calculate Mean Reversion indicators"""
    df['avg_low'] = df['low'].rolling(window=window).mean()
    df['avg_high'] = df['high'].rolling(window=window).mean()
    return df

def run_realistic_backtest(df, start_capital=100):
    """
    Realistic backtest with friction:
    - Slippage: 0.1% per trade
    - Partial fills: Only 80% of desired quantity filled
    """
    cash = start_capital
    position = 0
    entry_price = 0.0
    portfolio_values = []
    trades = []
    
    SLIPPAGE = 0.001  # 0.1%
    FILL_RATE = 0.80  # 80% fill rate
    
    for index, row in df.iterrows():
        price = row['close']
        avg_low = row['avg_low']
        avg_high = row['avg_high']
        
        # Skip if indicators not ready
        if pd.isna(avg_low) or pd.isna(avg_high):
            portfolio_values.append(cash + (position * price))
            continue
        
        # BUY SIGNAL
        if position == 0 and row['low'] < avg_low:
            buy_price = price * (1 + SLIPPAGE)
            target_shares = int((cash * 0.95) / buy_price)
            actual_shares = int(target_shares * FILL_RATE)
            
            if actual_shares > 0:
                cost = actual_shares * buy_price
                cash -= cost
                position = actual_shares
                entry_price = buy_price
                trades.append({
                    'type': 'buy',
                    'price': buy_price,
                    'shares': actual_shares,
                    'time': index
                })
        
        # SELL SIGNAL
        elif position > 0 and row['high'] >= avg_high:
            sell_price = price * (1 - SLIPPAGE)
            actual_shares = int(position * FILL_RATE)
            
            if actual_shares > 0:
                revenue = actual_shares * sell_price
                cash += revenue
                position -= actual_shares
                trades.append({
                    'type': 'sell',
                    'price': sell_price,
                    'shares': actual_shares,
                    'time': index
                })
        
        current_val = cash + (position * price)
        portfolio_values.append(current_val)
    
    return portfolio_values, trades

def analyze_and_plot(values, trades, start_capital, start_date, end_date):
    """Analyze results and create visualization"""
    if not values:
        print("No data to plot.")
        return
    
    final_val = values[-1]
    total_return = ((final_val - start_capital) / start_capital) * 100
    profit = final_val - start_capital
    
    # Calculate win rate
    wins = 0
    total_trades = 0
    for i in range(0, len(trades) - 1, 2):
        if i + 1 < len(trades):
            if trades[i]['type'] == 'buy' and trades[i+1]['type'] == 'sell':
                if trades[i+1]['price'] > trades[i]['price']:
                    wins += 1
                total_trades += 1
    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    
    print("\n" + "="*60)
    print(f"REALISTIC BACKTEST RESULTS ({start_date.date()} to {end_date.date()})")
    print("="*60)
    print(f"Starting Capital:  ${start_capital:.2f}")
    print(f"Ending Capital:    ${final_val:.2f}")
    print(f"Profit:            ${profit:.2f}")
    print(f"Total Return:      {total_return:.2f}%")
    print(f"Total Trades:      {len(trades)}")
    print(f"Win Rate:          {win_rate:.2f}%")
    print("="*60)
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Portfolio Value Chart
    ax1.plot(values, color='#00C805', linewidth=2)
    ax1.axhline(y=start_capital, color='gray', linestyle='--', alpha=0.5, label='Starting Capital')
    ax1.fill_between(range(len(values)), start_capital, values, 
                      where=[v >= start_capital for v in values], 
                      color='green', alpha=0.1, label='Profit')
    ax1.fill_between(range(len(values)), start_capital, values, 
                      where=[v < start_capital for v in values], 
                      color='red', alpha=0.1, label='Loss')
    ax1.set_title(f'Realistic Backtest: ARBK ({start_date.date()} to {end_date.date()})\nStarting: ${start_capital} → Ending: ${final_val:.2f} ({total_return:+.2f}%)', 
                  fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Trade Distribution
    buy_times = [t['time'] for t in trades if t['type'] == 'buy']
    sell_times = [t['time'] for t in trades if t['type'] == 'sell']
    
    ax2.scatter(range(len(buy_times)), [1]*len(buy_times), color='green', marker='^', s=100, label='Buy', alpha=0.6)
    ax2.scatter(range(len(sell_times)), [0]*len(sell_times), color='red', marker='v', s=100, label='Sell', alpha=0.6)
    ax2.set_title(f'Trade Activity (Total: {len(trades)} trades, Win Rate: {win_rate:.1f}%)', fontsize=12)
    ax2.set_ylabel('Trade Type', fontsize=12)
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(['Sell', 'Buy'])
    ax2.grid(True, alpha=0.3, axis='x')
    ax2.legend()
    
    plt.tight_layout()
    output_path = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/realistic_backtest_random_week.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {output_path}")

if __name__ == "__main__":
    symbol = 'ARBK'
    
    data, start_date, end_date = fetch_random_week_2025(symbol)
    
    if data.empty:
        print("No data found for this period.")
    else:
        print(f"Fetched {len(data)} bars")
        
        # Calculate indicators
        data = calculate_indicators(data, window=5)
        
        # Run realistic backtest with $100
        values, trades = run_realistic_backtest(data, start_capital=100)
        
        # Analyze and plot
        analyze_and_plot(values, trades, start_capital=100, start_date=start_date, end_date=end_date)
