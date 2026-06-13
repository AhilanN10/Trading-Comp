import backtest
import config
import pandas as pd
import matplotlib.pyplot as plt

def compare_stocks():
    tickers = ['WULF', 'HUT', 'BITF', 'LCID', 'NKLA', 'SPCE', 'FUBO', 'PLUG', 'SOUN', 'IONQ']
    results = []
    
    print(f"Starting comparison for: {tickers}")
    
    for ticker in tickers:
        try:
            # Fetch data for specific ticker
            data = backtest.fetch_data(symbol=ticker)
            
            if data.empty:
                print(f"No data for {ticker}")
                continue
                
            # Calculate indicators (Optimized Window = 5)
            data = backtest.calculate_indicators(data, window=5)
            
            # Run Backtest (Optimized: No Stop Loss)
            values, trades = backtest.run_backtest(
                data, 
                backtest.strategy_mean_reversion, 
                ticker, 
                strategy_params={'stop_loss_pct': None}
            )
            
            final_val = values[-1]
            total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
            trade_count = len(trades)
            
            # Calculate Win Rate
            wins = 0
            for i in range(0, len(trades) - 1, 2):
                if trades[i]['type'] == 'buy' and trades[i+1]['type'] == 'sell':
                    if trades[i+1]['price'] > trades[i]['price']:
                        wins += 1
            win_rate = (wins / (trade_count / 2)) * 100 if trade_count > 0 else 0
            
            results.append({
                'Stock': ticker,
                'Return (%)': total_return,
                'Final Value': final_val,
                'Trades': trade_count,
                'Win Rate (%)': win_rate
            })
            
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Return (%)', ascending=False)
    
    print("\nStock Comparison Results:")
    print(results_df.to_string(index=False))
    
    results_df.to_csv('stock_comparison.csv', index=False)
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.bar(results_df['Stock'], results_df['Return (%)'], color=['green' if x > 0 else 'red' for x in results_df['Return (%)']])
    plt.title('Mean Reversion Return by Stock (Optimized Strategy)')
    plt.xlabel('Stock')
    plt.ylabel('Return (%)')
    plt.grid(axis='y')
    plt.savefig('stock_comparison.png')
    print("Chart saved to stock_comparison.png")

if __name__ == "__main__":
    compare_stocks()
