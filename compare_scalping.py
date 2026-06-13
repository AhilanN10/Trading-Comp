import backtest
import config
import pandas as pd
import matplotlib.pyplot as plt

def compare_strategies():
    symbol = 'ARBK'
    print(f"Comparing Strategies on {symbol}...")
    
    # Fetch Data
    data = backtest.fetch_data(symbol=symbol)
    if data.empty:
        print("No data found.")
        return
        
    # Calculate Indicators (Window=5 for Mean Rev, RSI for Scalping)
    data = backtest.calculate_indicators(data, window=5)
    
    # --- Strategy 1: Optimized Mean Reversion ---
    print("\nRunning Optimized Mean Reversion...")
    vals_mr, trades_mr = backtest.run_backtest(
        data, 
        backtest.strategy_mean_reversion, 
        "Mean Reversion", 
        strategy_params={'stop_loss_pct': None}
    )
    
    # --- Strategy 2: Scalping (RSI) ---
    print("\nRunning Scalping (RSI < 30 / > 70)...")
    vals_sc, trades_sc = backtest.run_backtest(
        data, 
        backtest.strategy_scalping, 
        "Scalping", 
        strategy_params={'stop_loss_pct': 0.005, 'take_profit_pct': 0.01}
    )
    
    # --- Results ---
    def get_stats(vals, trades):
        if not vals: return 0, 0, 0
        ret = ((vals[-1] - config.START_CAPITAL) / config.START_CAPITAL) * 100
        count = len(trades)
        wins = 0
        for i in range(0, len(trades)-1, 2):
            if trades[i+1]['price'] > trades[i]['price']:
                wins += 1
        wr = (wins / (count/2) * 100) if count > 0 else 0
        return ret, count, wr

    ret_mr, count_mr, wr_mr = get_stats(vals_mr, trades_mr)
    ret_sc, count_sc, wr_sc = get_stats(vals_sc, trades_sc)
    
    print("\n--- COMPARISON RESULTS ---")
    print(f"{'Metric':<20} | {'Mean Reversion':<20} | {'Scalping':<20}")
    print("-" * 66)
    print(f"{'Total Return':<20} | {ret_mr:>19.2f}% | {ret_sc:>19.2f}%")
    print(f"{'Trade Count':<20} | {count_mr:>20} | {count_sc:>20}")
    print(f"{'Win Rate':<20} | {wr_mr:>19.2f}% | {wr_sc:>19.2f}%")
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(vals_mr, label=f'Mean Reversion (+{ret_mr:.0f}%)', color='#00C805')
    plt.plot(vals_sc, label=f'Scalping (+{ret_sc:.0f}%)', color='orange')
    plt.title(f'Strategy Comparison: Mean Reversion vs Scalping ({symbol})')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    output_path = '/Users/ahilannayani/.gemini/antigravity/brain/e1722e60-7bf5-4969-922b-a2f9396acbc6/scalping_vs_mr.png'
    plt.savefig(output_path)
    print(f"\nPlot saved to {output_path}")

if __name__ == "__main__":
    compare_strategies()
