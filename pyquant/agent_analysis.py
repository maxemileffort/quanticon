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
from dotenv import find_dotenv, load_dotenv

today_str = datetime.datetime.today().strftime('%Y-%m-%d')

# Configuration
CSV_PATH_PATTERN = fr"C:\Users\Max\Desktop\projects\quanticon\pyquant\outputs\{today_str}\*.csv"
SHEET_ID = "15IfaN1fei9P6BXt0Nj7Rdj7SedDoN_Puzgyb6gUboVQ"
SHEET_NAME = "Sheet1"
DEFAULT_MODEL = "gemini-2.5-flash-preview-05-20"

# Load environment variables from .env file
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Check if GEMINI_API_KEY is loaded
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found in .env file")

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

def csv_to_base64(df:pd.DataFrame):
    csv_string = df.to_string()
    return csv_string

def call_agent(base64_data):
    # print('configuring gemini...')
    api_key = os.getenv("GEMINI_API_KEY")
    # genai.configure(api_key=api_key)
    # print('gemini configured. init gemini...')
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0, api_key=api_key)

    system_message = '''Role
You are an elite options trader advising small cash accounts that trade only long calls and puts. Your sole input is a CSV file for a single stock symbol that contains at least the columns:
Date, Open, High, Low, Close, Volume
(It may also include extra indicator columns such as EMAs, deltas, or signal flags.)

Objective
From the most recent price action in the CSV, decide whether to recommend a trade or declare “No trade.” When recommending, supply a high-conviction, visually obvious setup expected to overcome theta decay and bid/ask spreads.

Process Checklist

Load & Sort - Read the CSV, focusing on the latest 60 trading days.

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
    user_message = f"{base64_data}\n\nBased on the attached data, suggest some options plays."
    # print('starting messages')
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])

    # print('created messages')
    chain = prompt | llm
    response = chain.invoke({"base64_data": base64_data})
    # print('invoked chain')
    return response.content

def append_to_google_sheet(date_str, play_text):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        print("setting creds...")
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            os.getenv("GOOGLE_SHEET_API_KEY"), scope
        )
        print('authorizing...')
        client = gspread.authorize(creds)
        print("opening spreadsheet...")
        # sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        spreadsheet = client.open_by_key(SHEET_ID)
        print("opening sheet...")

        sheet = spreadsheet.worksheet(SHEET_NAME)

        print("appending row...")
        sheet.append_row([date_str, play_text, "", ""], value_input_option="RAW")
    except Exception as e:
        print(f"Error when trying to append to sheet: {e}")

def process_file(file_path):
    ai_output = ""  # Initialize ai_output
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    failure_step = 'last 60'
    try:
        df_last60 = extract_last_60_days(file_path)
        
        failure_step = 'csv conversion'
        base64_data = csv_to_base64(df_last60)
        
        failure_step = 'call agent'
        ai_output = call_agent(base64_data)
        
        failure_step = 'append to sheet'
        append_to_google_sheet(date_str, ai_output)
        print(f"Successfully processed {os.path.basename(file_path)}")
        return ai_output  # No error
    except Exception as e:
        error_message = f"Error processing {os.path.basename(file_path)} on {date_str}: {e}\nAI Output: {ai_output}\n\n"
        print(error_message)
        print(f'step failed: {failure_step}')
        print('=====')
        return error_message

def main(method):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    files = get_filtered_csv_files()
    
    all_error_logs = []
    if method == 'threads':
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            # Use submit and as_completed to get results as they become available
            future_to_file = {executor.submit(process_file, file_path): file_path for file_path in files}
            for future in concurrent.futures.as_completed(future_to_file):
                error_result = future.result()
                if error_result:
                    all_error_logs.append(error_result)
    elif method == 'loop':
        for f in files:
            msg = process_file(f)
            if msg:
                all_error_logs.append(msg)

    output_path = fr'C:\Users\Max\Desktop\projects\quanticon\pyquant\outputs\{date_str}'
    os.makedirs(output_path, exist_ok=True) # Ensure the output directory exists
    error_logs_path = os.path.join(output_path, 'error_logs.txt')
    
    with open(error_logs_path, 'w') as outfile:
        if all_error_logs:
            outfile.write("".join(all_error_logs))
        else:
            outfile.write("No errors logged.\n")

if __name__ == "__main__":
    method = 'threads' # 'loop' or 'threads'
    main(method)
