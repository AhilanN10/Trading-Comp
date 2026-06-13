import backtest
import config
import pandas as pd
from datetime import datetime, date

def verify_open_october():
    symbol = 'OPEN'
    print(f"Verifying {symbol} performance for October 2025...")
    
    # Fetch data (enough to cover Oct 2025)
    data = backtest.fetch_data(symbol=symbol, random_slice=False)
    if data.empty:
        print("No data found.")
        return

    # Calculate indicators
    data = backtest.calculate_indicators(data, window=5)
    
    # Define Weeks
    weeks = [
        (date(2025, 10, 1), date(2025, 10, 7)),
        (date(2025, 10, 8), date(2025, 10, 14)),
        (date(2025, 10, 15), date(2025, 10, 21)),
        (date(2025, 10, 22), date(2025, 10, 28)),
        (date(2025, 10, 29), date(2025, 11, 4))
    ]
    
    results = []
    
    for i, (start_date, end_date) in enumerate(weeks):
        # Slice data
        # Convert date to string for slicing if index is datetime
        # Assuming index is timezone aware datetime, we can use string slicing or partial string matching
        # But safer to use boolean mask
        
        mask = (data.index.date >= start_date) & (data.index.date <= end_date)
        df_slice = data.loc[mask].copy()
        
        if df_slice.empty:
            print(f"Week {i+1} ({start_date} to {end_date}): No data.")
            continue
            
        print(f"Week {i+1}: {start_date} to {end_date} ({len(df_slice)} bars)...")
        
        values, trades = backtest.run_backtest(
            df_slice, 
            backtest.strategy_mean_reversion, 
            f"Week {i+1}", 
            strategy_params={'stop_loss_pct': None}
        )
        
        final_val = values[-1]
        total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
        trade_count = len(trades)
        
        # Win Rate
        wins = 0
        for j in range(0, len(trades) - 1, 2):
            if trades[j]['type'] == 'buy' and trades[j+1]['type'] == 'sell':
                if trades[j+1]['price'] > trades[j]['price']:
                    wins += 1
        win_rate = (wins / (trade_count / 2)) * 100 if trade_count > 0 else 0
        
        results.append({
            'Week': f"Week {i+1}",
            'Start Date': start_date,
            'End Date': end_date,
            'Return (%)': total_return,
            'Final Value': final_val,
            'Trades': trade_count,
            'Win Rate (%)': win_rate
        })
        
    # Report
    results_df = pd.DataFrame(results)
    print("\nOctober 2025 Verification Results for OPEN:")
    print(results_df.to_string(index=False))
    
    avg_return = results_df['Return (%)'].mean()
    print(f"\nAverage Weekly Return: {avg_return:.2f}%")
    print(f"Total Cumulative Return (Compounded approx): {((results_df['Final Value'] / config.START_CAPITAL).prod() - 1) * 100:.2f}% (Theoretical if reinvested)")
    
    results_df.to_csv('open_october_verification.csv', index=False)

if __name__ == "__main__":
    verify_open_october()
