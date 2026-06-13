import alpaca_trade_api as tradeapi
import pandas as pd
import matplotlib.pyplot as plt
import config
from datetime import datetime, timedelta
import random

def fetch_one_month_2025(symbol):
    """Fetch data for a random month in 2025"""
    api = tradeapi.REST(config.API_KEY, config.SECRET_KEY, config.BASE_URL, api_version='v2')
    
    # Pick a random month in 2025
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October')
    ]
    
    month_num, month_name = random.choice(months)
    start_date = datetime(2025, month_num, 1)
    
    # Calculate end date (last day of month)
    if month_num == 12:
        end_date = datetime(2025, 12, 31)
    else:
        end_date = datetime(2025, month_num + 1, 1) - timedelta(days=1)
    
    start_str = start_date.strftime('%Y-%m-%dT00:00:00Z')
    end_str = end_date.strftime('%Y-%m-%dT23:59:59Z')
    
    print(f"Fetching {symbol} for {month_name} 2025...")
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    
    bars = api.get_bars(symbol, '1Min', start=start_str, end=end_str, adjustment='raw').df
    
    if bars.empty:
        return pd.DataFrame(), start_date, end_date, month_name
        
    if bars.index.tz is None:
        bars.index = bars.index.tz_localize('UTC')
    bars.index = bars.index.tz_convert('America/New_York')
    
    return bars, start_date, end_date, month_name

def calculate_indicators(df, window=5):
    df['avg_low'] = df['low'].rolling(window=window).mean()
    df['avg_high'] = df['high'].rolling(window=window).mean()
    return df

def run_realistic_backtest(df, start_capital=1000):
    cash = start_capital
    position = 0
    portfolio_values = []
    trades = []
    daily_values = []
    
    SLIPPAGE = 0.001
    FILL_RATE = 0.80
    
    current_date = None
    
    for index, row in df.iterrows():
        price = row['close']
        avg_low = row['avg_low']
        avg_high = row['avg_high']
        
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
        
        # Track daily closing values
        trade_date = index.date()
        if trade_date != current_date:
            daily_values.append({'date': trade_date, 'value': current_val})
            current_date = trade_date
    
    return portfolio_values, trades, daily_values

def analyze_and_plot(values, trades, daily_values, start_capital, month_name):
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
    
    # Calculate max drawdown
    peak = start_capital
    max_dd = 0
    for val in values:
        if val > peak:
            peak = val
        dd = ((peak - val) / peak) * 100
        if dd > max_dd:
            max_dd = dd
    
    print("\n" + "="*70)
    print(f"REALISTIC 1-MONTH BACKTEST RESULTS ({month_name} 2025)")
    print("="*70)
    print(f"Starting Capital:    ${start_capital:.2f}")
    print(f"Ending Capital:      ${final_val:.2f}")
    print(f"Profit:              ${profit:.2f}")
    print(f"Total Return:        {total_return:.2f}%")
    print(f"Max Drawdown:        {max_dd:.2f}%")
    print(f"Total Trades:        {len(trades)}")
    print(f"Win Rate:            {win_rate:.2f}%")
    print(f"Avg Profit/Trade:    ${profit/total_trades:.2f}" if total_trades > 0 else "N/A")
    print("="*70)
    
    # Create visualization
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    # Main portfolio chart
    ax1 = fig.add_subplot(gs[0:2, :])
    ax1.plot(values, color='#00C805', linewidth=2, label='Portfolio Value')
    ax1.axhline(y=start_capital, color='gray', linestyle='--', alpha=0.5, label='Starting Capital')
    ax1.fill_between(range(len(values)), start_capital, values, 
                      where=[v >= start_capital for v in values], 
                      color='green', alpha=0.1)
    ax1.fill_between(range(len(values)), start_capital, values, 
                      where=[v < start_capital for v in values], 
                      color='red', alpha=0.1)
    ax1.set_title(f'Realistic 1-Month Backtest: ARBK ({month_name} 2025)\nStarting: ${start_capital:,.0f} → Ending: ${final_val:,.2f} ({total_return:+.2f}%)', 
                  fontsize=14, fontweight='bold')
    ax1.set_ylabel('Portfolio Value ($)', fontsize=12)
    ax1.set_xlabel('Minutes', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # Daily performance
    ax2 = fig.add_subplot(gs[2, 0])
    if daily_values:
        df_daily = pd.DataFrame(daily_values)
        daily_returns = [(df_daily.iloc[i]['value'] - start_capital) for i in range(len(df_daily))]
        colors = ['green' if r >= 0 else 'red' for r in daily_returns]
        ax2.bar(range(len(daily_returns)), daily_returns, color=colors, alpha=0.6)
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax2.set_title('Daily P&L', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Profit/Loss ($)', fontsize=10)
        ax2.set_xlabel('Trading Days', fontsize=10)
        ax2.grid(True, alpha=0.3, axis='y')
    
    # Trade statistics
    ax3 = fig.add_subplot(gs[2, 1])
    ax3.axis('off')
    stats_text = f"""
    PERFORMANCE METRICS
    
    Total Return:     {total_return:+.2f}%
    Total Profit:     ${profit:+.2f}
    
    Total Trades:     {len(trades)}
    Win Rate:         {win_rate:.1f}%
    Max Drawdown:     {max_dd:.2f}%
    
    Avg/Trade:        ${profit/total_trades:.2f}
    """ if total_trades > 0 else "No trades executed"
    
    ax3.text(0.1, 0.5, stats_text, fontsize=11, family='monospace',
             verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    output_path = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/realistic_1month_1000.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: {output_path}")

if __name__ == "__main__":
    symbol = 'ARBK'
    
    data, start_date, end_date, month_name = fetch_one_month_2025(symbol)
    
    if data.empty:
        print("No data found for this period.")
    else:
        print(f"Fetched {len(data)} bars")
        
        # Calculate indicators
        data = calculate_indicators(data, window=5)
        
        # Run realistic backtest with $1000
        values, trades, daily_values = run_realistic_backtest(data, start_capital=1000)
        
        # Analyze and plot
        analyze_and_plot(values, trades, daily_values, start_capital=1000, month_name=month_name)
