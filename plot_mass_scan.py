import pandas as pd
import matplotlib.pyplot as plt

def plot_results():
    try:
        df = pd.read_csv('mass_scan_results.csv')
        if df.empty:
            print("No results to plot.")
            return
            
        # Sort and take top 10
        df = df.sort_values(by='Return (%)', ascending=False).head(10)
        
        plt.figure(figsize=(12, 6))
        bars = plt.bar(df['Stock'], df['Return (%)'], color='green')
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}%',
                    ha='center', va='bottom')
                    
        plt.title('Top 10 High-Beta Performers (1-Week Simulation)')
        plt.xlabel('Stock')
        plt.ylabel('Return (%)')
        plt.grid(axis='y', alpha=0.3)
        
        plt.savefig('mass_scan_results.png')
        print("Chart saved to mass_scan_results.png")
        
    except Exception as e:
        print(f"Error plotting: {e}")

if __name__ == "__main__":
    plot_results()
