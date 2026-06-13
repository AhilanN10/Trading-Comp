import backtest
import config
import pandas as pd
import random
import matplotlib.pyplot as plt
import os

def verify_arbk_10_weeks():
    symbol = 'ARBK'
    print(f"Verifying {symbol} consistency over 10 random weeks...")
    
    # Fetch full available data
    data = backtest.fetch_data(symbol=symbol, random_slice=False)
    if data.empty:
        print("No data found.")
        return

    # Calculate indicators once for the whole dataset (Optimized Window = 5)
    data = backtest.calculate_indicators(data, window=5)
    
    results = []
    
    # 10 Random Runs
    for i in range(10):
        # Select random week (approx 5 trading days * 390 minutes = 1950 bars)
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
            total_return = 0
        else:
            final_val = values[-1]
            total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
        
        results.append({
            'Run': i+1,
            'Date Range': f"{start_date}\nto\n{end_date}",
            'Return (%)': total_return
        })
        
    # Create DataFrame
    df = pd.DataFrame(results)
    print("\nVerification Results:")
    print(df.to_string(index=False))
    
    avg_return = df['Return (%)'].mean()
    print(f"\nAverage Return: {avg_return:.2f}%")
    
    # Plotting
    plt.figure(figsize=(12, 6))
    bars = plt.bar(df['Run'], df['Return (%)'], color='#00C805') # Robinhood Green
    
    plt.title(f'ARBK Strategy Performance - 10 Random Weeks\nAverage Return: +{avg_return:.2f}%', fontsize=14, fontweight='bold')
    plt.xlabel('Run Number', fontsize=12)
    plt.ylabel('Return (%)', fontsize=12)
    plt.xticks(df['Run'])
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}%',
                ha='center', va='bottom')
                
    # Save plot
    output_path = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/ARBK_10_Weeks.png'
    plt.savefig(output_path, bbox_inches='tight')
    print(f"\nPlot saved to {output_path}")

if __name__ == "__main__":
    verify_arbk_10_weeks()
