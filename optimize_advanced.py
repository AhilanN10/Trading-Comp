import backtest
import config
import pandas as pd
import random

def optimize_advanced():
    symbol = 'OPEN'
    print(f"Starting Advanced Optimization for {symbol}...")
    
    # Fetch data (Random Slice = False to get full dataset, then we pick a random week for consistency or multiple weeks?)
    # Let's pick ONE random week to optimize on, then maybe verify later.
    # Or better, optimize on a specific week we know is good (or random).
    # Let's stick to the "Random Week" methodology but maybe try to pick a volatile one if possible?
    # For now, just standard fetch (which does random slice if we don't pass False, wait, I changed fetch_data to default random_slice=True).
    # Let's use a FIXED random week for all iterations to be fair.
    
    data_full = backtest.fetch_data(symbol=symbol, random_slice=False)
    
    if data_full.empty:
        print("No data.")
        return

    # Select a random week ONCE
    if len(data_full) > 2000:
        max_start = len(data_full) - 2000
        start_idx = random.randint(0, max_start)
        end_idx = start_idx + 1950
        data_week = data_full.iloc[start_idx:end_idx].copy()
        print(f"Optimization Period: {data_week.index[0].date()} to {data_week.index[-1].date()}")
    else:
        data_week = data_full.copy()
        print("Using full available data (short history).")

    # Parameter Grid
    windows = [3, 5, 8]
    z_scores = [0.0, 1.0, 2.0]
    rsi_thresholds = [None, 30, 40]
    take_profits = [None, 0.03, 0.05, 0.10]
    # Stop Loss: Keep it simple, maybe just None or 0.05? Previous opt showed None was best.
    # Let's add 0.05 just in case.
    stop_losses = [None, 0.05]
    
    results = []
    total_combos = len(windows) * len(z_scores) * len(rsi_thresholds) * len(take_profits) * len(stop_losses)
    print(f"Testing {total_combos} combinations...")
    
    count = 0
    for window in windows:
        # Pre-calculate indicators for this window
        df_run = backtest.calculate_indicators(data_week.copy(), window=window)
        
        for z in z_scores:
            for rsi in rsi_thresholds:
                for tp in take_profits:
                    for sl in stop_losses:
                        count += 1
                        if count % 50 == 0:
                            print(f"Progress: {count}/{total_combos}...")
                            
                        params = {
                            'entry_z_score': z,
                            'rsi_threshold': rsi,
                            'take_profit_pct': tp,
                            'stop_loss_pct': sl
                        }
                        
                        name = f"W={window} Z={z} RSI={rsi} TP={tp} SL={sl}"
                        
                        values, trades = backtest.run_backtest(
                            df_run, 
                            backtest.strategy_mean_reversion_advanced, 
                            "Opt", 
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
                            'Window': window,
                            'Z-Score': z,
                            'RSI Thresh': rsi,
                            'Take Profit': tp,
                            'Stop Loss': sl,
                            'Return (%)': total_return,
                            'Win Rate (%)': win_rate,
                            'Trades': trade_count
                        })
                        
    # Sort and Report
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Return (%)', ascending=False)
    
    print("\nTop 20 Advanced Strategies:")
    print(results_df.head(20).to_string(index=False))
    
    results_df.to_csv('advanced_optimization_results.csv', index=False)
    print("Results saved to advanced_optimization_results.csv")

if __name__ == "__main__":
    optimize_advanced()
