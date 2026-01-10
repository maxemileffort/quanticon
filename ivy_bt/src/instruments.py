import pandas as pd
import os
import logging
import requests
import io

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
    Retrieves S&P 500 tickers.
    1. Tries to load from local CSV cache.
    2. If missing, scrapes Wikipedia (using requests to avoid 403 Forbidden).
    3. Saves cache for future use.
    4. Fallback to top 10 tickers if everything fails.
    """
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'sp500_tickers.csv')
    
    # 1. Try Cache
    if os.path.exists(cache_path):
        try:
            logging.info(f"Loading S&P 500 tickers from cache: {cache_path}")
            return pd.read_csv(cache_path)
        except Exception as e:
            logging.warning(f"Failed to load S&P 500 cache: {e}")

    # 2. Scrape Wikipedia
    try:
        logging.info("Scraping S&P 500 tickers from Wikipedia...")
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        
        # Use headers to mimic a browser and avoid 403 Forbidden errors
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        
        # Use StringIO to avoid FutureWarning
        tables = pd.read_html(io.StringIO(r.text))
        df = tables[0]

        # Standardize Column Names
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        
        # Clean Ticker Symbols
        df['symbol'] = df['symbol'].str.replace('.', '-', regex=False)

        # Filter and Rename
        crosswalk = df[['symbol', 'security', 'gics_sector', 'gics_sub-industry', 'cik']].copy()
        crosswalk.columns = ['yfinance_symbol', 'company_name', 'sector', 'sub_industry', 'cik']
        
        # 3. Save Cache
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            crosswalk.to_csv(cache_path, index=False)
            logging.info(f"Saved S&P 500 tickers to cache: {cache_path}")
        except Exception as e:
            logging.warning(f"Could not save S&P 500 cache: {e}")
            
        return crosswalk

    except Exception as e:
        logging.error(f"Failed to scrape S&P 500 tickers: {e}")
        
        # 4. Fallback
        logging.warning("Using fallback list of top 10 US stocks.")
        fallback_data = {
            'yfinance_symbol': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'LLY', 'V'],
            'company_name': ['Apple', 'Microsoft', 'Alphabet', 'Amazon', 'Nvidia', 'Meta', 'Tesla', 'Berkshire Hathaway', 'Eli Lilly', 'Visa']
        }
        return pd.DataFrame(fallback_data)

def get_assets(instrument_type="forex"):
    if instrument_type == "crypto":
        return crypto_assets
    elif instrument_type == "spy":
        # Lazy load to avoid import-time network requests/errors
        df = get_sp500_crosswalk()
        return df['yfinance_symbol'].to_list()
    else:
        return forex_assets
