import yfinance as yf
import pandas as pd
import json
import math
import warnings
from datetime import datetime, time
from zoneinfo import ZoneInfo
from config import ALL_TICKERS, DATA_DIR
from storage import atomic_json

# Aggressively suppress all warnings to prevent console spam
warnings.filterwarnings("ignore")

DATA_DIR.mkdir(parents=True, exist_ok=True)

def safe_num(val):
    if pd.isna(val) or math.isinf(val):
        return None
    return round(float(val), 4)

def fetch_prices(tickers: list):
    history_path, latest_path = DATA_DIR / 'eod_history.json', DATA_DIR / 'eod_latest.json'
    history_data = json.loads(history_path.read_text()) if history_path.exists() else {}
    latest_data = json.loads(latest_path.read_text()).get('data', {}) if latest_path.exists() else {}
    refreshed = []
    print(f"Fetching EOD data for {len(tickers)} tickers over 3 months...")
    
    df = yf.download(tickers, period="3mo", group_by="ticker", auto_adjust=False, progress=False)
    
    for ticker in tickers:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                ticker_level = next(level for level in range(df.columns.nlevels) if ticker in df.columns.get_level_values(level))
                ticker_data = df.xs(ticker, axis=1, level=ticker_level).copy()
            else:
                ticker_data = df.copy()
            
            # Non-inplace dropna fixes the Pandas deprecation warning
            ticker_data = ticker_data.replace([float('inf'), -float('inf')], float('nan')).dropna(subset=['Close', 'Volume'])
            ticker_data = ticker_data[(ticker_data['Close'] > 0) & (ticker_data['Volume'] >= 0)].sort_index()
            # yfinance returns an in-progress bar for today while NSE is open; a close is only a close after 15:30 IST.
            now = datetime.now(ZoneInfo('Asia/Kolkata'))
            if now.time() < time(15, 30):
                ticker_data = ticker_data[ticker_data.index.date < now.date()]
            
            if ticker_data.empty:
                print(f"WARNING: No valid price data returned for {ticker}")
                continue
                
            ticker_data['pct_change'] = ticker_data['Close'].pct_change() * 100
            # Rolling window shifted by 1 to exclude current day
            ticker_data['vol_avg_prev20'] = ticker_data['Volume'].shift(1).rolling(20).mean()
            ticker_data['vol_multiple'] = ticker_data['Volume'] / ticker_data['vol_avg_prev20']
            
            history_list = []
            for date, row in ticker_data.iterrows():
                history_list.append({
                    "date": str(date.date()),
                    "close": safe_num(row['Close']),
                    "volume": safe_num(row['Volume']),
                    "pct_change": safe_num(row['pct_change']),
                    "vol_avg_prev20": safe_num(row['vol_avg_prev20']),
                    "vol_multiple": safe_num(row['vol_multiple'])
                })
                
            history_data[ticker] = history_list
            latest_data[ticker] = history_list[-1]
            refreshed.append(ticker)
            
        except Exception as e:
            print(f"Failed to process {ticker}: {e}")
            
    if not refreshed:
        raise RuntimeError("No EOD data returned; preserving the previous snapshot.")
    out_history = DATA_DIR / "eod_history.json"
    atomic_json(out_history, history_data)
        
    out_latest = DATA_DIR / "eod_latest.json"
    latest_payload = {
        "as_of": max(row["date"] for row in latest_data.values()),
        "data": latest_data
    }
    latest_payload['stale_tickers'] = [ticker for ticker in tickers if ticker not in refreshed or latest_data[ticker]['date'] < latest_payload['as_of']]
    latest_payload['refreshed_at'] = datetime.now().astimezone().isoformat()
    atomic_json(out_latest, latest_payload)
        
    print(f"Saved strictly valid JSON to eod_history.json and eod_latest.json")

if __name__ == "__main__":
    fetch_prices(list(ALL_TICKERS.keys()))
