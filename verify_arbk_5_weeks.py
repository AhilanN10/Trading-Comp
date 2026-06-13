import backtest
import config
import pandas as pd
import random
from datetime import timedelta

def verify_arbk():
    symbol = 'ARBK'
    print(f"Verifying {symbol} consistency over 5 random weeks...")
    
    # Fetch full available data
    data = backtest.fetch_data(symbol=symbol, random_slice=False)
    if data.empty:
        print("No data found.")
        return

    # Calculate indicators once for the whole dataset (Optimized Window = 5)
    data = backtest.calculate_indicators(data, window=5)
    
    results = []
    
    # 5 Random Runs
    for i in range(5):
        # Select random week (approx 5 trading days * 390 minutes = 1950 bars)
        # Ensure we don't go out of bounds
        if len(data) < 2000:
            print("Not enough data for multiple weeks.")
            break
            
        max_start = len(data) - 2000
        start_idx = random.randint(0, max_start)
        end_idx = start_idx + 1950 # Approx 1 week
        
        df_slice = data.iloc[start_idx:end_idx].copy()
        
        start_date = df_slice.index[0].date()
        end_date = df_slice.index[-1].date()
        
        print(f"Run {i+1}: {start_date} to {end_date}...")
        
        values, trades = backtest.run_backtest(
            df_slice, 
            backtest.strategy_mean_reversion, 
            f"Run {i+1}", 
            strategy_params={'stop_loss_pct': None}
        )
        
        if not values:
            print("No trades.")
            continue
            
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
            'Run': i+1,
            'Start Date': start_date,
            'Return (%)': total_return,
            'Final Value': final_val,
            'Trades': trade_count,
            'Win Rate (%)': win_rate
        })
        
    # Report
    results_df = pd.DataFrame(results)
    print("\nVerification Results for ARBK:")
    print(results_df.to_string(index=False))
    
    avg_return = results_df['Return (%)'].mean()
    print(f"\nAverage Return over 5 runs: {avg_return:.2f}%")
    
    results_df.to_csv('arbk_verification.csv', index=False)

if __name__ == "__main__":
    verify_arbk()
