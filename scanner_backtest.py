import backtest
import config
import pandas as pd
import numpy as np
import random
from datetime import timedelta
import time

def scanner_backtest():
    # Universe of High Volatility / Volume Stocks
    universe = [
        'NVDA', 'TSLA', 'AMD', 'MSTR', 'COIN', 'MARA', 'RIOT', 'PLTR', 
        'SOFI', 'OPEN', 'DKNG', 'HOOD', 'GME', 'AMC', 'UPST', 'AI', 
        'CVNA', 'AFRM', 'RIVN', 'CLSK'
    ]
    
    print(f"Initializing Market Scanner with {len(universe)} stocks...")
    
    data_map = {}
    
    # 1. Fetch Data for all stocks (Full history)
    for ticker in universe:
        try:
            print(f"Fetching {ticker}...")
            df = backtest.fetch_data(symbol=ticker, random_slice=False)
            if not df.empty:
                # Calculate Indicators upfront
                df = backtest.calculate_indicators(df, window=5) # Optimized Window
                data_map[ticker] = df
            else:
                print(f"Warning: No data for {ticker}")
            
            # Sleep to avoid rate limits
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            
    if not data_map:
        print("No data available for simulation.")
        return

    # 2. Align Data to a Common Random Week
    # Find a range where we have data for most stocks
    # Let's pick a random end date from the *first* stock and try to use that week
    first_ticker = list(data_map.keys())[0]
    ref_df = data_map[first_ticker]
    
    if len(ref_df) < 2000:
        print("Not enough data history.")
        return
        
    max_start = len(ref_df) - 2000
    start_idx = random.randint(0, max_start)
    ref_start_date = ref_df.index[start_idx]
    ref_end_date = ref_start_date + timedelta(days=7)
    
    print(f"\nSelected Simulation Week: {ref_start_date.date()} to {ref_end_date.date()}")
    
    # Slice all dataframes to this range
    aligned_data = {}
    for ticker, df in data_map.items():
        mask = (df.index >= ref_start_date) & (df.index <= ref_end_date)
        slice_df = df.loc[mask].copy()
        if not slice_df.empty:
            aligned_data[ticker] = slice_df
            
    print(f"Aligned {len(aligned_data)} stocks for simulation.")
    
    # 3. Run Simulation
    # We need to iterate minute by minute.
    # Create a union of all indices to ensure we step through every minute
    all_indices = sorted(list(set().union(*[df.index for df in aligned_data.values()])))
    
    cash = config.START_CAPITAL
    positions = {} # {ticker: shares}
    entry_prices = {} # {ticker: price}
    trades_log = []
    portfolio_values = []
    
    max_positions = 3
    
    print(f"Running Scanner Simulation ({len(all_indices)} steps)...")
    
    for current_time in all_indices:
        # 1. Update Portfolio Value
        current_equity = 0
        for ticker, shares in positions.items():
            if current_time in aligned_data[ticker].index:
                price = aligned_data[ticker].loc[current_time]['close']
                current_equity += shares * price
            else:
                # Use last known price if missing (simplified)
                # In reality, we'd need forward fill, but let's assume 0 change or skip
                pass 
                
        total_val = cash + current_equity
        portfolio_values.append(total_val)
        
        # 2. Scanner: Rank Stocks by Volatility (Std Dev / Price)
        # We look at the row for 'current_time'
        candidates = []
        
        for ticker, df in aligned_data.items():
            if current_time in df.index:
                row = df.loc[current_time]
                # Volatility Score: (Upper Band - Lower Band) / Mid Band (Bandwidth) is a good proxy
                # Or just std_low / price
                # Let's use 'bandwidth' calculated in indicators
                vol_score = row['bandwidth'] if not pd.isna(row['bandwidth']) else 0
                candidates.append((ticker, vol_score, row))
                
        # Sort by Volatility (Highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Top 3 Volatile Stocks
        top_picks = candidates[:5] # Look at top 5
        
        # 3. Execute Strategy on Top Picks
        # Buy Logic
        if len(positions) < max_positions:
            for ticker, vol, row in top_picks:
                if ticker in positions:
                    continue # Already own it
                
                # Check Mean Reversion Entry
                # Optimized: Window=5, No Z-Score, No RSI
                # Buy: Price < Avg Low
                if not pd.isna(row['avg_low']) and row['low'] < row['avg_low']:
                    price = row['close']
                    # Size position: Split remaining cash / (max_positions - current_positions) ?
                    # Or fixed size? Let's do 1/3 of Start Capital to keep it simple/aggressive
                    # Or use available cash / remaining slots
                    slots_left = max_positions - len(positions)
                    amount_to_invest = cash / slots_left
                    
                    shares = int(amount_to_invest / price)
                    if shares > 0:
                        cash -= shares * price
                        positions[ticker] = shares
                        entry_prices[ticker] = price
                        trades_log.append({
                            'time': current_time,
                            'type': 'buy',
                            'ticker': ticker,
                            'price': price,
                            'shares': shares,
                            'vol_rank': vol
                        })
                        
                if len(positions) >= max_positions:
                    break
                    
        # Sell Logic (Check ALL held positions, not just top picks)
        # We need to iterate a copy of keys because we might delete
        for ticker in list(positions.keys()):
            if ticker in aligned_data and current_time in aligned_data[ticker].index:
                row = aligned_data[ticker].loc[current_time]
                price = row['close']
                shares = positions[ticker]
                
                # Sell: Price >= Avg High
                if not pd.isna(row['avg_high']) and row['high'] >= row['avg_high']:
                    revenue = shares * price
                    cash += revenue
                    profit = revenue - (shares * entry_prices[ticker])
                    
                    trades_log.append({
                        'time': current_time,
                        'type': 'sell',
                        'ticker': ticker,
                        'price': price,
                        'shares': shares,
                        'profit': profit
                    })
                    
                    del positions[ticker]
                    del entry_prices[ticker]

    # Final Report
    final_val = portfolio_values[-1]
    total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
    
    print("\nScanner Simulation Results:")
    print(f"Final Value: ${final_val:,.2f}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Total Trades: {len(trades_log)}")
    
    # Trade Analysis
    wins = len([t for t in trades_log if t['type'] == 'sell' and t['profit'] > 0])
    losses = len([t for t in trades_log if t['type'] == 'sell' and t['profit'] <= 0])
    win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    print(f"Win Rate: {win_rate:.2f}%")
    
    # Top Traded Stocks
    ticker_counts = {}
    for t in trades_log:
        tk = t['ticker']
        ticker_counts[tk] = ticker_counts.get(tk, 0) + 1
        
    print("\nActivity by Ticker:")
    sorted_tickers = sorted(ticker_counts.items(), key=lambda x: x[1], reverse=True)
    for tk, count in sorted_tickers[:10]:
        print(f"{tk}: {count} trades")

    # Save Log
    pd.DataFrame(trades_log).to_csv('scanner_trades.csv', index=False)

if __name__ == "__main__":
    scanner_backtest()
