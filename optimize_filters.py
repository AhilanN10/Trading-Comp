import backtest
import config
import pandas as pd
import itertools

def optimize_filters():
    ticker = 'ARBK'
    print(f"Fetching data for {ticker}...")
    
    # Fetch data (using a fixed random week for consistency if possible, or just a random one)
    # To make it comparable, we should ideally use the same week as the mass scan, but we don't know which one it was.
    # So we'll just fetch a new random week and optimize on that.
    data = backtest.fetch_data(symbol=ticker)
    
    if data.empty:
        print("No data found.")
        return

    # Calculate Indicators
    data = backtest.calculate_indicators(data, window=5)
    
    # Parameter Grid
    trend_emas = [None, 50, 200]
    volume_multipliers = [None, 1.5, 2.0]
    trailing_stops = [None, 0.03, 0.05, 0.10]
    
    results = []
    
    print(f"Starting Grid Search on {ticker}...")
    
    for trend in trend_emas:
        for vol in volume_multipliers:
            for trail in trailing_stops:
                params = {
                    'trend_ema': trend,
                    'volume_multiplier': vol,
                    'trailing_stop_pct': trail
                }
                
                values, trades = backtest.run_backtest(
                    data, 
                    backtest.strategy_mean_reversion_filtered, 
                    "Filtered", 
                    strategy_params=params
                )
                
                if not values:
                    continue
                    
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
                
                results.append({
                    'Trend EMA': trend,
                    'Vol Mult': vol,
                    'Trail Stop': trail,
                    'Return (%)': total_return,
                    'Win Rate (%)': win_rate,
                    'Trades': trade_count
                })
                
    # Sort and Report
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Return (%)', ascending=False)
    
    print("\nTop 5 Filter Combinations:")
    print(results_df.head(5).to_string(index=False))
    
    results_df.to_csv('filter_optimization_results.csv', index=False)

if __name__ == "__main__":
    optimize_filters()
