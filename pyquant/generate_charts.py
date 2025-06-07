# This script will find the most recent CSV in pyquant/outputs,
# read the symbols, download historical data, generate candlestick charts,
# and save them to a single PDF.

from datetime import datetime
import os
import glob
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_pdf import PdfPages
import ta

def compute_qdqu_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Calculate EMAs
    week_ema_indicator = ta.trend.EMAIndicator(close=df['Close'], window=7)
    line_ema_indicator = ta.trend.EMAIndicator(close=df['Close'], window=20)
    qtr_ema_indicator = ta.trend.EMAIndicator(close=df['Close'], window=90)
    half_ema_indicator = ta.trend.EMAIndicator(close=df['Close'], window=180)

    df['week_ema'] = week_ema_indicator.ema_indicator()
    df['line_ema'] = line_ema_indicator.ema_indicator()
    df['qtr_ema'] = qtr_ema_indicator.ema_indicator()
    df['half_ema'] = half_ema_indicator.ema_indicator()

    # EMA deltas
    df['week_delta'] = df['week_ema'] - df['week_ema'].shift(1)
    df['qtr_delta'] = df['qtr_ema'] - df['qtr_ema'].shift(1)

    # Direction flags
    df['week_up'] = df['week_delta'] > 0
    df['week_down'] = df['week_delta'] < 0
    df['qtr_up'] = df['qtr_delta'] > 0
    df['qtr_down'] = df['qtr_delta'] < 0

    # Entry signals
    df['bull_entry'] = df['week_down'].shift(1) & df['week_up'] & df['qtr_up']
    df['bear_entry'] = df['week_up'].shift(1) & df['week_down'] & df['qtr_down']

    return df

# 1. Find the most recent CSV file in pyquant/outputs
output_dir = './outputs'
csv_files = glob.glob(os.path.join(output_dir, '*.csv'))
csv_files = [f for f in csv_files if 'qdqu&' in f]

if not csv_files:
    print("No CSV files found in the outputs directory.")

most_recent_csvs = sorted(csv_files, key=os.path.getmtime, reverse=True)[:2]
print(f"Using the most recent CSV file: {most_recent_csvs}")

# 2. Read the CSV
df = pd.DataFrame()
for f in most_recent_csvs:
    try:
        df = pd.concat([df, pd.read_csv(f, sep='|')])
    except Exception as e:
        print(f"Error reading CSV file: {e}")

# 3. Get all of the data in the column called 'symbol'
if 'symbol' not in df.columns:
    print("CSV file does not contain a 'symbol' column.")
print(df.columns)

symbols = set(df['symbol'].tolist())
print(f"Found {len(symbols)} symbols: {symbols}")

# 4. Create candlestick charts for each symbol


today_str = datetime.today().strftime('%Y-%m-%d')
pdf_output_path = os.path.join(output_dir, f'{today_str}_charts_quqd.pdf')

with PdfPages(pdf_output_path) as pdf:
    for symbol in symbols:
        
        try:
            # Download historical data
            ticker = yf.Ticker(symbol)
            hist_data = ticker.history(period="1y", interval="1d")

            if hist_data.empty:
                print(f"No data found for {symbol}. Skipping.")
                continue
            
            hist_data = compute_qdqu_signals(hist_data)
            hist_data['symbol'] = symbol

            entry = hist_data.tail(5)[['bull_entry', 'bear_entry']].any().any()

            if not entry:
                continue

            print(f"Generating chart for {symbol}...")

            # Prepare additional plots
            apds = [
                mpf.make_addplot(hist_data['week_ema'], color='aqua', width=1.0),
                mpf.make_addplot(hist_data['line_ema'], color='green', width=1.1),
                mpf.make_addplot(hist_data['qtr_ema'], color='orange', width=1.0),
                mpf.make_addplot(hist_data['half_ema'], color='red', width=1.0),
                mpf.make_addplot(hist_data['Low'].where(hist_data['bull_entry']), type='scatter', markersize=50, marker='^', color='lime'),
                mpf.make_addplot(hist_data['High'].where(hist_data['bear_entry']), type='scatter', markersize=50, marker='v', color='red'),
            ]

            # Plot with overlays
            fig, axes = mpf.plot(
                hist_data,
                type='candle',
                style='binancedark',
                title=f'{symbol}',
                ylabel='Price',
                addplot=apds,
                figscale=1.5,
                returnfig=True
            )

            # Add the figure to the PDF
            pdf.savefig(fig)
            plt.close(fig) # Close the figure to free up memory

            csv_path = os.path.join(output_dir, f'{today_str}_{symbol}_data.csv')
            hist_data = hist_data.reset_index()
            hist_data['Date'] = hist_data['Date'].apply(lambda x: datetime.date(x))
            hist_data = hist_data.set_index('Date')
            hist_data.to_csv(csv_path)

        except Exception as e:
            print(f"Error generating chart for {symbol}: {e}")
            continue

print(f"Candlestick charts saved to {pdf_output_path}")