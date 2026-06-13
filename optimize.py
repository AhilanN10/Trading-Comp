import backtest
import config
import pandas as pd
import matplotlib.pyplot as plt

def optimize():
    print("Fetching data for optimization...")
    data = backtest.fetch_data()
    if data.empty:
        print("No data.")
        return

    # Parameter Grid
    windows = [5, 10, 15, 20, 30, 45, 60]
    stop_losses = [None, 0.01, 0.02, 0.03, 0.05]
    
    results = []
    
    print(f"Starting optimization on {len(windows) * len(stop_losses)} combinations...")
    
    for window in windows:
        # Recalculate indicators for this window
        df_window = data.copy()
        df_window = backtest.calculate_indicators(df_window, window=window)
        
        for sl in stop_losses:
            params = {'stop_loss_pct': sl}
            name = f"Win={window} SL={sl}"
            
            values, trades = backtest.run_backtest(
                df_window, 
                backtest.strategy_mean_reversion, 
                name, 
                strategy_params=params
            )
            
            final_val = values[-1]
            total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
            trade_count = len(trades)
            
            results.append({
                'Window': window,
                'Stop Loss': sl if sl else 'None',
                'Return (%)': total_return,
                'Final Value': final_val,
                'Trades': trade_count
            })
            
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values(by='Return (%)', ascending=False)
    
    print("\nTop 10 Parameter Combinations:")
    print(results_df.head(10).to_string(index=False))
    
    results_df.to_csv('optimization_results.csv', index=False)
    print("Results saved to optimization_results.csv")
    
    # Plot Best
    best = results_df.iloc[0]
    print(f"\nBest Strategy: Window={best['Window']}, SL={best['Stop Loss']}, Return={best['Return (%)']:.2f}%")
    
    # Re-run best for plotting
    df_best = data.copy()
    df_best = backtest.calculate_indicators(df_best, window=int(best['Window']))
    sl_param = None if best['Stop Loss'] == 'None' else float(best['Stop Loss'])
    
    values, trades = backtest.run_backtest(
        df_best, 
        backtest.strategy_mean_reversion, 
        "Best Optimized Strategy", 
        strategy_params={'stop_loss_pct': sl_param}
    )
    
    plt.figure(figsize=(12, 6))
    plt.plot(df_best.index, values, label=f"Best (Win={best['Window']}, SL={best['Stop Loss']})")
    plt.title(f"Best Optimized Strategy: {best['Return (%)']:.2f}% Return")
    plt.xlabel('Time')
    plt.ylabel('Portfolio Value')
    plt.legend()
    plt.grid(True)
    plt.savefig('optimization_chart.png')
    print("Chart saved to optimization_chart.png")

if __name__ == "__main__":
    optimize()
