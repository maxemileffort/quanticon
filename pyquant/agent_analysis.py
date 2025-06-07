#!/usr/bin/env python3
import os
import glob
import base64
import datetime
import pandas as pd
import concurrent.futures
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# Configuration
CSV_PATH_PATTERN = r"C:\Users\Max\Desktop\projects\quanticon\pyquant\outputs\*.csv"
SHEET_ID = "15IfaN1fei9P6BXt0Nj7Rdj7SedDoN_Puzgyb6gUboVQ"
SHEET_NAME = "Sheet1"
DEFAULT_MODEL = "gemini-2.5-flash-preview-05-20"
load_dotenv() # Load environment variables from .env file

def get_filtered_csv_files():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    files = glob.glob(CSV_PATH_PATTERN)
    files = [
        f for f in files
        if today in os.path.basename(f) and "qdqu" not in os.path.basename(f)
    ]
    files.sort(key=lambda f: os.path.basename(f), reverse=True)
    return files

def extract_last_60_days(file_path):
    df = pd.read_csv(file_path)
    df.sort_values("Date", inplace=True)
    return df.tail(60)

def csv_to_base64(df):
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    return base64.b64encode(csv_bytes).decode("utf-8")

def call_agent(base64_data):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)

    system_message = '''Role
You are an elite options trader advising small cash accounts that trade only long calls and puts. Your sole input is a CSV file for a single stock symbol that contains at least the columns:
Date, Open, High, Low, Close, Volume
(It may also include extra indicator columns such as EMAs, deltas, or signal flags.)

Objective
From the most recent price action in the CSV, decide whether to recommend a trade or declare “No trade.” When recommending, supply a high-conviction, visually obvious setup expected to overcome theta decay and bid/ask spreads.

Process Checklist

Load & Sort - Read the CSV, sort by Date ascending, focus on the latest 60 trading days.

Visual-Logic Classification - From OHLC data infer one of:
• Bullish breakout • Bearish breakdown • Trend continuation (up/down) • Choppy / Range / Mid-pattern

Trade Type & Timeframe - Choose Scalp (2-5 days) or Swing (3-4 weeks) based on volatility, ATR, and recent candlestick structure.

Confirmation Filter - Approve only if multiple cues align (e.g., higher highs & lows, clean base, flag/wedge resolution, momentum candle, or supporting indicator columns such as bull_entry/bear_entry). Otherwise label “Watch Only.”

Risk Check - Ensure the forecast move comfortably exceeds typical theta loss and bid/ask spread for at-the-money contracts. Skip if doubtful.

Output Format (one block per approved trade, max 3)
<format>
Ticker: $symbol
Trade Type: Scalp | Swing
Bias: Bullish | Bearish
Entry: $price | $breakout_level
Stop-Loss: $price
Target: $price
Option Contract: $Strike $Expiry
Rationale: 1-2 concise sentences grounded in CSV price action/confirmation

If no valid setup: "$symbol : No trade - Rationale: 1-2 concise sentences grounded in CSV price action/confirmation"
If confirmation is forming but not yet triggered: "$symbol : Watch Only - Rationale: 1-2 concise sentences grounded in CSV price action/confirmation"

Rules
• Recommend only long calls or puts (no spreads).
• Never exceed 3 trade ideas per CSV.
• Include strike & expiration that align with the chosen timeframe (near-term weekly for scalps, monthly for swings).
• If price action is messy or mid-range, pass decisively.
</format>
'''
    user_message = f"{base64_data}\n\nBased on the attached base64 encoded data, suggest some options plays."

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])

    chain = prompt | llm
    response = chain.invoke({"base64_data": base64_data})
    return response.content

def append_to_google_sheet(date_str, play_text):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        os.getenv("GOOGLE_SHEET_API_KEY"), scope
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    sheet.append_row([date_str, play_text, "", ""], value_input_option="RAW")

def process_file(file_path):
    try:
        df_last60 = extract_last_60_days(file_path)
        base64_data = csv_to_base64(df_last60)
        ai_output = call_agent(base64_data)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        append_to_google_sheet(date_str, ai_output)
        print(f"Successfully processed {os.path.basename(file_path)}")
    except Exception as e:
        print(f"Error processing {os.path.basename(file_path)}: {e}")

def main():
    files = get_filtered_csv_files()
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        executor.map(process_file, files)

if __name__ == "__main__":
    main()
