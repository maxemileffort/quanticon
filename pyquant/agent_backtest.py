#!/usr/bin/env python3
import os, glob, base64
import json
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

import yfinance as yf

today_str = datetime.datetime.today().strftime('%Y-%m-%d')

# Configuration
SHEET_ID = "15IfaN1fei9P6BXt0Nj7Rdj7SedDoN_Puzgyb6gUboVQ"
SHEET_NAME = "Sheet1"
DEFAULT_MODEL = "gemini-2.5-flash-preview-05-20"

# Load environment variables from .env file
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)

# Check if GEMINI_API_KEY is loaded
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY not found in .env file")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_trade_ideas():
    today_minus_day = datetime.datetime.today() - datetime.timedelta(1)
    today_minus_day_str = today_minus_day.strftime('%Y-%m-%d')
    print(today_minus_day)

    f_name1 = f'./outputs/{today_str}/backtest_ideas.csv'
    f_name2 = f'./outputs/{today_minus_day_str}/backtest_ideas.csv'
    if os.path.isfile(f_name1): 
        ideas = pd.read_csv(f_name1)
        # return ideas
    elif os.path.isfile(f_name2):
        ideas = pd.read_csv(f_name2)
        # return ideas
    else:
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
            sheet_values = sheet.get_all_values()
            ideas_raw = pd.DataFrame(sheet_values[1:], columns=sheet_values[0])
            ideas_raw['date'] = pd.to_datetime(ideas_raw['date'])
            ideas = ideas_raw.loc[ideas_raw['date']<today_minus_day]
            ideas = ideas.loc[(ideas['date of outcome'].isna())|(ideas['date of outcome']=='')]
            # print(ideas)
            ideas.to_csv(f'./outputs/{today_str}/backtest_ideas.csv', index=False)
        except Exception as e:
            print(f'Error getting sheet: {e}')
            ideas = pd.DataFrame()
    
    return ideas

def extract_last_60_days(ticker):
    ticker_data = yf.download(ticker, period='1y', interval='1d', group_by='ticker')
    df = ticker_data.tail(60)
    return df

def csv_to_base64(df:pd.DataFrame):
    csv_string = df.to_string()
    return csv_string

def call_idea_parse_agent(idea):
    # print('configuring gemini...')
    # api_key = os.getenv("GEMINI_API_KEY")
    # genai.configure(api_key=api_key)
    # print('gemini configured. init gemini...')
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0, api_key=GEMINI_API_KEY)

    system_message = '''You are a helpful text parsing assistant. Your outputs are always in json, and you never provide any extra commentary beyond '''
    system_message += '''what the user requests. It's critical that your ouput is always json, as it's meant to be consumed later by other APIs.'''
    user_message = f"""{idea}\n\nAnalyze this trade idea and parse the ticker (ticker only, no special characters allowed), the entry, """
    user_message += """the stop loss, and the target. Your output should simply be a json object like so: \n\n"""
    user_message += """{"ticker":<parsed ticker>, "entry":<parsed entry>, "stop loss":<parsed stop loss>, "target":<parsed target>} \n\n"""
    user_message += """There should be absolutely no other commentary, only the requested information."""
    # print('starting messages')
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])

    # print('created messages')
    chain = prompt | llm
    response = chain.invoke({"idea": idea})
    # print('invoked chain')
    return response.content

def call_analysis_agent(idea):

    idea_obj_raw = call_idea_parse_agent(idea)
    idea_obj = idea_obj_raw.replace('```json','').replace('```','')
    json_idea = json.loads(idea_obj)

    price_history = extract_last_60_days(json_idea['ticker'])
    price_history_str = csv_to_base64(price_history)

    # print('configuring gemini...')
    
    # genai.configure(api_key=api_key)
    # print('gemini configured. init gemini...')
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0, api_key=GEMINI_API_KEY)

    system_message = '''You are a helpful stock backtest analysis assistant. Your outputs are always in json, and you never provide any extra commentary beyond '''
    system_message += '''what the user requests. It's critical that your ouput is always json, as it's meant to be consumed later by other APIs.'''
    user_message = f"""{price_history_str}\n\nAnalyze this trade idea and tell me if 1 of the following occurred: - TP was hit\n- SL """
    user_message += """was hit\n- the trade is still going\n- never entered trade\n\n"""
    user_message += """There should be absolutely no other commentary, only the requested information."""
    user_message += """Your output should be in the following json format: \n\n"""
    user_message += """{"response":<simple response>} """
    # print('starting messages')
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        ("user", user_message)
    ])

    # print('created messages')
    chain = prompt | llm
    response = chain.invoke({"price_history": price_history})
    # print('invoked chain')
    return response.content

def update_google_sheet(date_str, play_text):
    return

def process_ideas(df):
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
    ideas = get_trade_ideas()
    
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
    method = 'loop' # 'loop' or 'threads'
    main(method)
