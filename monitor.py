"""Persistent refresh loop and deduplicated portfolio alert ledger."""
import argparse
import fcntl
import json
import time
import os
from datetime import datetime, timezone
from config import DATA_DIR, ROOT_DIR, PUSH_TICKERS
from fetch_prices import fetch_prices
from fetch_announcements import parse_screener_announcements
from generate_push import generate_digest
from storage import atomic_json

DEFAULT_RULES = {'price': 3, 'volume': 2.5, 'categories': ['results', 'management_change', 'M&A', 'litigation', 'credit_rating', 'capex', 'fund_raise', 'earnings_call', 'dividend', 'pledging']}


def evaluate_alerts(digest, prices, rules):
    alerts = [{'id': item['id'], 'ticker': item['ticker'], 'headline': item['headline'], 'type': item['type'], 'timestamp': item['timestamp']}
              for item in digest if item['priority'] >= 3 and item['type'] in rules['categories']]
    for ticker in PUSH_TICKERS:
        price = prices.get(ticker)
        if not price:
            continue
        symbol = ticker.removesuffix('.NS')
        for kind, triggered, headline in [
            ('price', price.get('pct_change') is not None and abs(price['pct_change']) >= rules['price'], f"Daily move {price.get('pct_change')}%"),
            ('volume', price.get('vol_multiple') is not None and price['vol_multiple'] >= rules['volume'], f"Volume {price.get('vol_multiple')}× the previous 20 sessions"),
        ]:
            if triggered:
                alerts.append({'id': f'{kind}-{symbol}-{price["date"]}', 'ticker': symbol, 'type': kind, 'headline': headline, 'timestamp': f'{price["date"]}T15:30:00+05:30'})
    return alerts


def run_once():
    jobs = DATA_DIR / '.jobs'
    jobs.mkdir(parents=True, exist_ok=True)
    with open(jobs / 'monitor.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'running', 'message': 'A source refresh is already running.'}
        status_path = jobs / 'monitor.json'
        started = datetime.now(timezone.utc).isoformat()
        atomic_json(status_path, {'status': 'running', 'started': started})
        failures = []
        for name, function in [('prices', lambda: fetch_prices(list(PUSH_TICKERS))), ('announcements', parse_screener_announcements)]:
            try:
                function()
            except Exception as error:
                failures.append(name)
                print(f'{name} refresh unavailable: {type(error).__name__}; saved data retained.', flush=True)
        generate_digest(failed_sources=failures)
        if os.getenv('FINN_ENRICH_FILINGS') == '1':
            try:
                from enrich_push import enrich
                from filing_analysis import analyse
                enrich(limit=3)
                analyse(limit=2)
            except Exception as error:
                print(f'Optional filing enrichment unavailable: {type(error).__name__}', flush=True)
        public = ROOT_DIR / 'finn-app/public/data'
        if failures:
            portfolio_path = public / 'portfolio.json'
            portfolio = json.loads(portfolio_path.read_text())
            for source, field in [('prices', 'stale_prices'), ('announcements', 'stale_announcements')]:
                if source in failures:
                    portfolio[field] = list(PUSH_TICKERS)
            atomic_json(portfolio_path, portfolio)
        rules_path = DATA_DIR / 'alert_rules.json'
        rules = json.loads(rules_path.read_text()) if rules_path.exists() else DEFAULT_RULES
        digest = json.loads((public / 'push_digest.json').read_text())
        prices = json.loads((public / 'eod_latest.json').read_text())['data']
        ledger_path = DATA_DIR / 'alerts.json'
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
        existing = {item['id'] for item in ledger}
        for alert in evaluate_alerts(digest, prices, rules):
            if alert['id'] not in existing:
                ledger.append({**alert, 'observed_at': datetime.now(timezone.utc).isoformat()})
                existing.add(alert['id'])
        atomic_json(ledger_path, ledger[-2000:])
        atomic_json(public / 'alerts.json', ledger[-2000:])
        result = {'status': 'partial' if failures else 'ready', 'started': started,
                  'completed': datetime.now(timezone.utc).isoformat(), 'failed_sources': failures,
                  'alert_count': len(ledger)}
        atomic_json(status_path, result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=int, default=900)
    arguments = parser.parse_args()
    while True:
        try:
            print(json.dumps(run_once()), flush=True)
        except Exception as error:
            print(f'Monitor error: {type(error).__name__}', flush=True)
        if arguments.once:
            break
        # Stay responsive to termination; this is an application worker, not a tool wait.
        remaining = max(60, arguments.interval)
        while remaining:
            pause = min(30, remaining)
            time.sleep(pause)
            remaining -= pause
