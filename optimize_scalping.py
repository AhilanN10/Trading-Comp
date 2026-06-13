import backtest
import config
import pandas as pd
import itertools

def optimize_scalping():
    symbol = 'ARBK'
    print(f"Optimizing Scalping Strategy for {symbol}...")
    
    # Fetch Data
    data = backtest.fetch_data(symbol=symbol)
    if data.empty:
        print("No data found.")
        return
        
    # Calculate Indicators
    data = backtest.calculate_indicators(data, window=5)
    
    # Parameter Grid
    rsi_buy_options = [20, 30, 40]
    rsi_sell_options = [60, 70, 80]
    stop_loss_options = [0.005, 0.01, 0.02, None]
    take_profit_options = [0.01, 0.02, 0.05, None]
    
    combinations = list(itertools.product(rsi_buy_options, rsi_sell_options, stop_loss_options, take_profit_options))
    print(f"Testing {len(combinations)} combinations...")
    
    results = []
    
    for i, (rsi_buy, rsi_sell, sl, tp) in enumerate(combinations):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(combinations)}")
            
        params = {
            'rsi_buy_threshold': rsi_buy,
            'rsi_sell_threshold': rsi_sell,
            'stop_loss_pct': sl,
            'take_profit_pct': tp
        }
        
        values, trades = backtest.run_backtest(
            data, 
            backtest.strategy_scalping, 
            "Scalping", 
            strategy_params=params
        )
        
        if not values:
            continue
            
        final_val = values[-1]
        total_return = ((final_val - config.START_CAPITAL) / config.START_CAPITAL) * 100
        trade_count = len(trades)
        
        results.append({
            'RSI Buy': rsi_buy,
            'RSI Sell': rsi_sell,
            'Stop Loss': sl,
            'Take Profit': tp,
            'Return (%)': total_return,
            'Trades': trade_count
        })
        
    # Analysis
    results_df = pd.DataFrame(results)
    if not results_df.empty:
        results_df = results_df.sort_values(by='Return (%)', ascending=False)
        
        print("\nTop 10 Scalping Configurations:")
        print(results_df.head(10).to_string(index=False))
        
        best_return = results_df.iloc[0]['Return (%)']
        print(f"\nBest Scalping Return: {best_return:.2f}%")
        
        results_df.to_csv('scalping_optimization_results.csv', index=False)
    else:
        print("No results.")

if __name__ == "__main__":
    optimize_scalping()
