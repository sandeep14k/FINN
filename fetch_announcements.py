import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin
from storage import atomic_json
from config import ALL_TICKERS, DATA_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)

IST = ZoneInfo('Asia/Kolkata')


def collection_time():
    return datetime.now(IST)


class ExchangeFeed(list):
    def __init__(self, items=(), status='failed', reason=None):
        super().__init__(items)
        self.status = status
        self.reason = reason


def parse_screener_date(date_str: str, current_tracker: datetime, collected_at=None) -> tuple:
    text = date_str.lower().strip()
    relative = re.search(r"(\d+)\s*(hour|minute|min|second|sec|day)s?\b", text)
    if relative:
        count, unit = int(relative[1]), relative[2]
        delta = timedelta(**{("days" if unit == "day" else "hours" if unit == "hour" else "minutes" if unit in ("min", "minute") else "seconds"): count})
        date = (collected_at or collection_time()) - delta
        return date.isoformat(), date
    match = re.search(r"\b(\d{1,2}\s+[a-z]{3})(?:\s+(20\d{2}))?\b", text)
    if match:
        try:
            year = int(match[2]) if match[2] else current_tracker.year
            date = datetime.strptime(f"{match[1]} {year}", "%d %b %Y")
            if not match[2] and date.date() > (current_tracker + timedelta(days=5)).date():
                date = date.replace(year=year - 1)
            return date.strftime("%Y-%m-%d"), date
        except ValueError:
            pass
    return None, current_tracker

def fetch_bse_fallback(ticker: str, scrip_code: str, collected_at=None) -> list:
    collected_at = collected_at or collection_time()
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        session.get("https://www.bseindia.com", headers=headers, timeout=10)
        bse_api = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
        headers.update({"Referer": "https://www.bseindia.com/corporates/ann.html", "Origin": "https://www.bseindia.com"})
        
        end = collected_at.strftime("%Y%m%d")
        start = (collected_at - timedelta(days=90)).strftime("%Y%m%d") 
        
        params = {
            "strCat": "-1", "strPrevDate": start, "strScrip": scrip_code, 
            "strSearch": "P", "strToDate": end, "strType": "C"
        }
        collected, seen = [], set()
        for page in range(1, 21):
            resp = session.get(bse_api, params={**params, 'pageno': page}, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rows = data.get('Table')
            if not isinstance(rows, list):
                return ExchangeFeed(collected, 'partial' if collected else 'failed', 'Invalid exchange response')
            if not rows:
                return ExchangeFeed(collected, 'ready')
            fresh = [item for item in rows if item.get('NEWSID', item.get('ATTACHMENTNAME', item.get('NEWSSUB'))) not in seen]
            if not fresh:
                return ExchangeFeed(collected, 'partial', 'Exchange repeated a page')
            seen.update(item.get('NEWSID', item.get('ATTACHMENTNAME', item.get('NEWSSUB'))) for item in fresh)
            collected.extend([{
                    "ticker": ticker,
                    "headline": item.get('NEWSSUB', ''),
                    "date": exchange_timestamp(item["NEWS_DT"]),
                    "url": f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{item.get('ATTACHMENTNAME')}" if item.get('ATTACHMENTNAME') else None,
                    "source": "BSE_API", "date_precision": "time"
                } for item in fresh])
            time.sleep(0.3)
        return ExchangeFeed(collected, 'partial', 'Exchange page limit reached')
    except (requests.RequestException, ValueError, KeyError, TypeError) as error:
        return ExchangeFeed(locals().get('collected', []), 'partial' if locals().get('collected') else 'failed', type(error).__name__)
    finally:
        session.close()

def exchange_timestamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return (stamp.replace(tzinfo=IST) if stamp.tzinfo is None else stamp).isoformat()


def publication_date(li, anchor, tracker, collected_at):
    metadata = li.find('time')
    if metadata and metadata.get('datetime'):
        raw = metadata['datetime']
        try:
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            return (raw if len(raw) == 10 else exchange_timestamp(raw)), stamp
        except ValueError:
            pass
    # Headline dates describe events, not necessarily the publication date.
    remainder = BeautifulSoup(str(li), 'html.parser')
    for link in remainder.find_all('a'):
        link.decompose()
    return parse_screener_date(remainder.get_text(' ', strip=True), tracker, collected_at)


def parse_screener_announcements():
    collected_at = collection_time()
    results = {}
    coverage = {}
    successful = []
    previous_path = DATA_DIR / 'announcements.json'
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    empty_tickers = []
    exchange_tickers = []
    
    for ticker, scrip in ALL_TICKERS.items():
        base_sym = ticker.replace(".NS", "")
        print(f"Fetching {ticker} (Screener: {base_sym})...")
        
        urls_to_try = [
            f"https://www.screener.in/company/{base_sym}/consolidated/",
            f"https://www.screener.in/company/{base_sym}/"
        ]
        
        exchange = fetch_bse_fallback(ticker, scrip, collected_at)
        extracted = list(exchange)
        exchange_status = getattr(exchange, 'status', 'failed')
        coverage[ticker] = {'status': exchange_status, 'source': 'BSE', 'reason': getattr(exchange, 'reason', None)}
        if exchange_status == 'ready':
            exchange_tickers.append(ticker)
            successful.append(ticker)
        for url in ([] if exchange_status == 'ready' else urls_to_try):
            time.sleep(1.5)
            try:
                resp = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as exc:
                print(f"Fetch failed: {exc}")
                continue
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                ann_section = soup.find(id='announcements')
                
                if not ann_section:
                    for h_tag in soup.find_all(['h2', 'h3']):
                        if 'Announcement' in h_tag.text:
                            ann_section = h_tag.find_next('ul')
                            break
                            
                if ann_section:
                    links = ann_section.find_all('li')
                    current_tracker = collected_at
                    successful.append(ticker)
                    coverage[ticker] = {'status': 'partial', 'source': 'Screener', 'reason': 'Limited latest-announcement list'}
                    for li in links:
                        a_tag = li.find('a')
                        if not a_tag: continue
                        
                        headline = a_tag.get_text(" ", strip=True)
                        url_val = urljoin(url, a_tag.get('href', ''))
                        
                        iso_date, current_tracker = publication_date(li, a_tag, current_tracker, collected_at)
                        
                        extracted.append({
                            "ticker": ticker,
                            "headline": headline,
                            "date": iso_date,
                            "url": url_val,
                            "source": "screener/BSE",
                            "date_precision": "day" if iso_date and len(iso_date) == 10 else "time"
                        })
                
                if extracted:
                    break 
                    
        if ticker not in successful and exchange_status != 'partial':
            empty_tickers.append(ticker)
            
        print(f"  -> Found {len(extracted)} announcements.")
        results[ticker] = extracted

    if empty_tickers:
        print(f"\nWARNING: 0 announcements found (404/Empty) for: {', '.join(empty_tickers)}")
        
    if not successful and not any(results.values()):
        raise RuntimeError("No announcements returned; preserving the previous snapshot.")
    for ticker in empty_tickers:
        results[ticker] = previous.get(ticker, [])
    # Accumulate collection history; a short upstream feed must not erase older windows.
    for ticker, items in results.items():
        merged = {item.get('url') or item['headline']: item for item in previous.get(ticker, [])}
        for item in items:
            key = item.get('url') or item['headline']
            if not item.get('date') and key in merged:
                item['date'] = merged[key].get('date')
            merged[key] = item
        results[ticker] = list(merged.values())
    atomic_json(DATA_DIR / 'announcement_health.json', {
        'refreshed_at': collected_at.isoformat(), 'stale_tickers': empty_tickers,
        'coverage': coverage,
        'direct_exchange_tickers': exchange_tickers,
        'limited_feed_tickers': [ticker for ticker in ALL_TICKERS if ticker not in exchange_tickers],
    })
    out_path = DATA_DIR / "announcements.json"
    atomic_json(out_path, results)

if __name__ == "__main__":
    parse_screener_announcements()
