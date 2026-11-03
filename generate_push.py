"""Publish portfolio disclosures and EOD observations; thresholds run in the UI."""
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from config import DATA_DIR, ROOT_DIR, PUSH_TICKERS
from storage import atomic_json

PUBLIC_DATA_DIR = ROOT_DIR / 'finn-app/public/data'
# Headlines are "<filing title> <date> - <model summary>". A summary mentioning an
# acquisition must not relabel a results filing, so classification reads the title only.
SUMMARY_SUFFIX = re.compile(r'\s+\d{1,2}\s+[A-Z][a-z]{2}\s+-\s+')
CATEGORIES = [
    ('management_change', r'(?:resign|appointment|cessation|change).*(?:director|ceo|cfo|chief|management)|chief executive|chief financial|managing director', 5),
    ('results_notice', r'board meeting intimation|intimation of board|board meeting.*(?:scheduled|to be held|will be)|intimation.*(?:result|financial)', 2),
    ('results', r'financial results|quarterly results|audited.*results|unaudited.*results', 5),
    ('M&A', r'acquisition|merger|demerger|amalgamation|scheme of arrangement|joint venture', 5),
    ('litigation', r'litigation|penalty|regulatory order|insolvency', 5),
    ('earnings_call', r'earnings call|conference call|transcript', 3),
    ('credit_rating', r'credit rating|downgrade|upgrade', 4),
    ('capex', r'capacity|expansion|new plant', 4),
    ('fund_raise', r'fund rais|qip|preferential|rights issue|buyback', 4),
    ('dividend', r'dividend', 3),
    ('pledging', r'pledge', 4),
    ('press_release', r'order (?:win|received)|(?:wins?|bags?|secures?)\b.*\border|contract award', 4),
    ('routine', r'auditor|newspaper publication', 1),
    ('routine', r'newspaper|compliance|certificate|allotment|investor meet|postal ballot|agm|egm', 1),
]

def classify(headline):
    title = SUMMARY_SUFFIX.split(headline, maxsplit=1)[0]
    for category, pattern, priority in CATEGORIES:
        if re.search(pattern, title, re.I):
            return category, priority
    return 'other', 2

def collapse_result_duplicates(digest):
    """One results event can arrive as several filings; keep the filings, tuck the companions."""
    groups = {}
    for item in digest:
        if item['type'] == 'results':
            groups.setdefault((item['ticker'], (item.get('timestamp') or '')[:10]), []).append(item)
    for items in groups.values():
        if len(items) < 2:
            continue
        def rank(item):
            title = SUMMARY_SUFFIX.split(item['headline'], maxsplit=1)[0].lower()
            canonical = 2 if title.startswith('unaudited financial results') and 'media statement' not in title else 1 if 'board meeting outcome' in title else 0
            return (bool(item.get('enrichment', {}).get('results')), canonical)
        items.sort(key=rank, reverse=True)
        primary = items[0]
        for companion in items[1:]:
            companion['priority'] = 2
            companion['one_line_why'] = f'Companion filing to the results announcement from {primary["ticker"]} shown above.'

def generate_digest(failed_sources=()):
    PUBLIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    announcements = json.loads((DATA_DIR / 'announcements.json').read_text())
    prices = json.loads((DATA_DIR / 'eod_latest.json').read_text())
    health_path = DATA_DIR / 'announcement_health.json'
    health = json.loads(health_path.read_text()) if health_path.exists() else {}
    evidence_path = DATA_DIR / 'filing_evidence.json'
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
    analysis_path = DATA_DIR / 'filing_analysis.json'
    analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else {}
    digest = []
    previous_path = PUBLIC_DATA_DIR / 'push_digest.json'
    previous = json.loads(previous_path.read_text()) if previous_path.exists() else []
    identities = {(item['ticker'], item.get('source_url')): item['id'] for item in previous if item.get('source_url')}
    for ticker, items in announcements.items():
        if ticker not in PUSH_TICKERS:
            continue
        for ann in items:
            date = ann.get('date')
            headline = ' '.join(ann['headline'].split())
            category, priority = classify(headline)
            symbol = ticker.removesuffix('.NS')
            identity = identities.get((symbol, ann.get('url'))) or hashlib.sha256(f"{ticker}|{ann.get('url') or headline}".encode()).hexdigest()[:16]
            digest.append({
                'id': identity,
                'ticker': symbol, 'timestamp': date,
                'date_precision': ann.get('date_precision', 'day' if date and len(date) == 10 else 'time'),
                'type': category, 'priority': priority, 'headline': headline,
                'one_line_why': {
                    'management_change': 'Leadership change: inspect the role, reason and effective date.',
                    'results': 'Published financial results: inspect performance, margins and comparison periods.',
                    'results_notice': 'A results meeting has been announced; this is not the published financial outcome.',
                    'M&A': 'Ownership or business perimeter may change; inspect terms and funding.',
                    'litigation': 'Potential legal or regulatory exposure; inspect amount and next steps.',
                    'earnings_call': 'Management commentary is available in the primary source.',
                    'routine': 'Routine disclosure, kept for completeness.',
                }.get(category, 'Company disclosure available. Open the filing to assess its impact.'),
                'source_url': ann.get('url'), 'enrichment': {},
            })
    digest.sort(key=lambda x: (x['priority'], x.get('timestamp') or ''), reverse=True)
    for item in digest:
        item['filing_evidence'] = evidence.get(item['id'])
        item['enrichment'] = analysis.get(item['id'], {})
    collapse_result_duplicates(digest)
    digest.sort(key=lambda x: (x['priority'], x.get('timestamp') or ''), reverse=True)
    histories = json.loads((DATA_DIR / 'eod_history.json').read_text())
    holdings = {'tickers': [t.removesuffix('.NS') for t in PUSH_TICKERS],
                                           'generated_at': datetime.now().astimezone().isoformat(),
                                           'stale_announcements': list(PUSH_TICKERS) if 'announcements' in failed_sources else health.get('stale_tickers', []),
                                           'stale_prices': list(PUSH_TICKERS) if 'prices' in failed_sources else prices.get('stale_tickers', []),
                                           'limited_feed_holdings': [ticker.removesuffix('.NS') for ticker in health.get('limited_feed_tickers', []) if ticker in PUSH_TICKERS],
                                           'source_coverage': health.get('coverage', {}),
                                           'last_checked': health.get('refreshed_at')}
    dates = [item['timestamp'][:10] for item in digest if item.get('timestamp')] + [prices.get('as_of', '')]
    snapshot = {'generation': uuid4().hex, 'as_of': max(dates, default=''), 'feed': digest, 'eod': prices, 'holdings': holdings, 'histories': histories}
    for name, data in [('push_digest.json', digest), ('eod_latest.json', prices), ('eod_history.json', histories), ('portfolio.json', holdings)]:
        atomic_json(PUBLIC_DATA_DIR / name, data)
    atomic_json(PUBLIC_DATA_DIR / 'snapshot.json', snapshot)
    print(f'Published {len(digest)} portfolio disclosures; no synthetic financial enrichment.')

if __name__ == '__main__':
    generate_digest()
