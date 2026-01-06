import pandas as pd

crypto_crosswalk = pd.DataFrame([
    ("AAVEUSD", "AAVE-USD"),    ("ADAUSD", "ADA-USD"),    ("AIXBTUSD", "AIXBT-USD"),
    ("ALGOUSD", "ALGO-USD"),    ("APTUSD", "APT-USD"),    ("ARBUSD", "ARB-USD"),
    ("ATOMUSD", "ATOM-USD"),    ("AVAXUSD", "AVAX-USD"),
    ("BCHUSD", "BCH-USD"),    ("BNBUSD", "BNB-USD"),    ("BONKUSD", "BONK-USD"),
    ("BTCUSD", "BTC-USD"),    ("CRVUSD", "CRV-USD"),    ("DOGEUSD", "DOGE-USD"),
    ("DOTUSD", "DOT-USD"),    ("ETCUSD", "ETC-USD"),    ("ETHUSD", "ETH-USD"),
    ("FARTCOINUSD", "FARTCOIN-USD"),    ("FILUSD", "FIL-USD"),    ("FLOKIUSD", "FLOKI-USD"),
    ("HBARUSD", "HBAR-USD"),    ("HYPEUSD", "HYPE-USD"),
    ("INJUSD", "INJ-USD"),    ("IPUSD", "IP-USD"),    ("JTOUSD", "JTO-USD"),
    ("JUPUSD", "JUP-USD"),    ("KAITOUSD", "KAITO-USD"),    ("LDOUSD", "LDO-USD"),
    ("LINKUSD", "LINK-USD"),    ("LTCUSD", "LTC-USD"),    ("MOODENG", "MOODENG-USD"),
    ("NEARUSD", "NEAR-USD"),    ("ONDOUSD", "ONDO-USD"),    ("OPUSD", "OP-USD"),
    ("ORDIUSD", "ORDI-USD"),
    ("PNUTUSD", "PNUT-USD"),    ("POLUSD", "POL-USD"),
    ("RENDERUSD", "RENDER-USD"),    ("SUSD", "SUSD-USD"),
    ("SHIBUSD", "SHIB-USD"),    ("SOLUSD", "SOL-USD"),    ("STXUSD", "STX-USD"),
    ("SUIUSD", "SUI-USD"),    ("TIAUSD", "TIA-USD"),
    ("TONUSD", "TON-USD"),    ("TRUMPUSD", "TRUMP-USD"),    ("TRXUSD", "TRX-USD"),
    ("UNIUSD", "UNI-USD"),    ("VIRTUALUSD", "VIRTUAL-USD"),    ("WIFUSD", "WIF-USD"),
    ("WLDUSD", "WLD-USD"),    ("XPLUSD", "XPL-USD"),    ("XRPUSD", "XRP-USD"),
], columns=["breakout_symbol", "yfinance_symbol"])

crypto_assets = crypto_crosswalk['yfinance_symbol'].to_list()

forex_crosswalk = pd.DataFrame([
    # Major pairs
    ("EURUSD", "EURUSD=X"),    ("GBPUSD", "GBPUSD=X"),    ("USDJPY", "USDJPY=X"),
    ("USDCHF", "USDCHF=X"),    ("AUDUSD", "AUDUSD=X"),    ("USDCAD", "USDCAD=X"),
    ("NZDUSD", "NZDUSD=X"),

    # Minor (cross) pairs
    ("EURGBP", "EURGBP=X"),    ("EURJPY", "EURJPY=X"),    ("EURCHF", "EURCHF=X"),
    ("EURAUD", "EURAUD=X"),    ("EURCAD", "EURCAD=X"),    ("EURNZD", "EURNZD=X"),

    ("GBPJPY", "GBPJPY=X"),    ("GBPCHF", "GBPCHF=X"),    ("GBPAUD", "GBPAUD=X"),
    ("GBPCAD", "GBPCAD=X"),    ("GBPNZD", "GBPNZD=X"),

    ("AUDJPY", "AUDJPY=X"),    ("AUDCHF", "AUDCHF=X"),    ("AUDCAD", "AUDCAD=X"),
    ("AUDNZD", "AUDNZD=X"),

    ("CADJPY", "CADJPY=X"),    ("CADCHF", "CADCHF=X"),

    ("CHFJPY", "CHFJPY=X"),

    ("NZDJPY", "NZDJPY=X"),    ("NZDCHF", "NZDCHF=X"),    ("NZDCAD", "NZDCAD=X"),
], columns=["breakout_symbol", "yfinance_symbol"])

forex_assets = forex_crosswalk['yfinance_symbol'].to_list()

def get_sp500_crosswalk():
    """
    Scrapes Wikipedia to create a crosswalk of S&P 500 companies.
    Includes Tickers, Security Names, Sectors, and CIK codes.
    """
    # 1. Scrape the constituents table from Wikipedia
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    tables = pd.read_html(url)
    df = tables[0]

    # 2. Standardize Column Names (Refactoring to lowercase for consistency)
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # 3. Clean Ticker Symbols 
    # (Some tickers use '.' instead of '-' which can break certain APIs)
    df['symbol'] = df['symbol'].str.replace('.', '-', regex=False)

    # 4. Filter for relevant "Crosswalk" columns
    crosswalk = df[['symbol', 'security', 'gics_sector', 'gics_sub-industry', 'cik']].copy()
    
    # Rename for clarity and for use the the engine
    crosswalk.columns = ['yfinance_symbol', 'company_name', 'sector', 'sub_industry', 'cik']
    
    return crosswalk

# Execution
sp500_assets = get_sp500_crosswalk()

def get_assets(instrument_type="forex"):
    if instrument_type == "crypto":
        return crypto_assets
    elif instrument_type == "stocks":
        return sp500_assets
    else:
        return forex_assets
