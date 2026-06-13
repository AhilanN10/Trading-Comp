import alpaca_trade_api as tradeapi
import pandas as pd
import matplotlib.pyplot as plt
import config
from datetime import datetime, timedelta
import random

def fetch_random_week_2025(symbol):
    """Fetch data for a random week in 2025"""
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    year_start = datetime(2025, 1, 1)
    year_end = datetime(2025, 11, 21)
    
    days_in_range = (year_end - year_start).days - 7
    random_day = random.randint(0, days_in_range)
    start_date = year_start + timedelta(days=random_day)
    end_date = start_date + timedelta(days=7)
    
    start_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
    end_str = end_date.strftime('%Y-%m-%dT23:59:59Z')
    
    print(f"Fetching {symbol}: {start_date.date()} to {end_date.date()}...")
    
    try:
        bars = api.get_bars(symbol, '1Min', start=start_str, end=end_str, adjustment='raw').df
        
        if bars.empty:
            return pd.DataFrame(), start_date, end_date
            
        if bars.index.tz is None:
            bars.index = bars.index.tz_localize('UTC')
        bars.index = bars.index.tz_convert('America/New_York')
        
        return bars, start_date, end_date
    except Exception as e:
        print(f"  Error fetching {symbol}: {e}")
        return pd.DataFrame(), start_date, end_date

def calculate_indicators(df, window=5):
    df['avg_low'] = df['low'].rolling(window=window).mean()
    df['avg_high'] = df['high'].rolling(window=window).mean()
    return df

def run_realistic_backtest(df, start_capital=300):
    cash = start_capital
    position = 0
    portfolio_values = []
    trades = []
    
    SLIPPAGE = 0.001
    FILL_RATE = 0.80
    
    for index, row in df.iterrows():
        price = row['close']
        avg_low = row['avg_low']
        avg_high = row['avg_high']
        
        if pd.isna(avg_low) or pd.isna(avg_high):
            portfolio_values.append(cash + (position * price))
            continue
        
        if position == 0 and row['low'] < avg_low:
            buy_price = price * (1 + SLIPPAGE)
            target_shares = int((cash * 0.95) / buy_price)
            actual_shares = int(target_shares * FILL_RATE)
            
            if actual_shares > 0:
                cost = actual_shares * buy_price
                cash -= cost
                position = actual_shares
                trades.append({'type': 'buy', 'price': buy_price, 'shares': actual_shares, 'time': index})
        
        elif position > 0 and row['high'] >= avg_high:
            sell_price = price * (1 - SLIPPAGE)
            actual_shares = int(position * FILL_RATE)
            
            if actual_shares > 0:
                revenue = actual_shares * sell_price
                cash += revenue
                position -= actual_shares
                trades.append({'type': 'sell', 'price': sell_price, 'shares': actual_shares, 'time': index})
        
        portfolio_values.append(cash + (position * price))
    
    return portfolio_values, trades

def compare_stocks():
    stocks = ['ARBK', 'MIGI', 'PLUG', 'NOVA', 'BITF']
    results = []
    
    for symbol in stocks:
        data, start_date, end_date = fetch_random_week_2025(symbol)
        
        if data.empty:
            print(f"  No data for {symbol}")
            continue
        
        data = calculate_indicators(data, window=5)
        values, trades = run_realistic_backtest(data, start_capital=300)
        
        if not values:
            continue
        
        final_val = values[-1]
        total_return = ((final_val - 300) / 300) * 100
        profit = final_val - 300
        
        # Win rate
        wins = 0
        total_trades = 0
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                if trades[i]['type'] == 'buy' and trades[i+1]['type'] == 'sell':
                    if trades[i+1]['price'] > trades[i]['price']:
                        wins += 1
                    total_trades += 1
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        results.append({
            'Stock': symbol,
            'Week': f"{start_date.date()}",
            'Return (%)': total_return,
            'Profit ($)': profit,
            'Final ($)': final_val,
            'Trades': len(trades),
            'Win Rate (%)': win_rate
        })
        
        print(f"  {symbol}: {total_return:+.2f}% (${final_val:.2f}, Profit: ${profit:+.2f})")
    
    # Create comparison chart
    df = pd.DataFrame(results)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Profit comparison
    colors = ['green' if p > 0 else 'red' for p in df['Profit ($)']]
    ax1.barh(df['Stock'], df['Profit ($)'], color=colors, alpha=0.7)
    ax1.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_xlabel('Profit ($)', fontsize=12)
    ax1.set_title('Realistic Profit by Stock\n($300 Starting Capital, Random Week)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='x')
    
    # Final value comparison
    ax2.bar(df['Stock'], df['Final ($)'], color='#00C805', alpha=0.7)
    ax2.axhline(y=300, color='gray', linestyle='--', alpha=0.5, label='Starting Capital')
    ax2.set_ylabel('Final Value ($)', fontsize=12)
    ax2.set_title('Final Portfolio Value by Stock', fontsize=12, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_path = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/realistic_stock_comparison_300.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {output_path}")
    
    print("\n" + "="*90)
    print("REALISTIC STOCK COMPARISON ($300 Starting Capital)")
    print("="*90)
    print(df.to_string(index=False))
    print("="*90)
    print(f"\nBest Performer: {df.loc[df['Profit ($)'].idxmax(), 'Stock']} with ${df['Profit ($)'].max():.2f} profit")
    print(f"Worst Performer: {df.loc[df['Profit ($)'].idxmin(), 'Stock']} with ${df['Profit ($)'].min():.2f} profit")

if __name__ == "__main__":
    compare_stocks()
