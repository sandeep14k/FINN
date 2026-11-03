"""Refresh failures must not silently erase previously available holdings."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

from fetch_prices import fetch_prices
from fetch_announcements import parse_screener_announcements
from config import normalize_text
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from fetch_announcements import parse_screener_date, publication_date, ExchangeFeed
from generate_push import generate_digest, classify


class RefreshTests(unittest.TestCase):
    def test_single_ticker_multiindex(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            frame = pd.DataFrame({('INFY.NS', 'Close'): [100 + i for i in range(22)], ('INFY.NS', 'Volume'): [100] * 21 + [300]}, index=pd.date_range('2026-10-01', periods=22))
            with patch('fetch_prices.DATA_DIR', directory), patch('fetch_prices.yf.download', return_value=frame):
                fetch_prices(['INFY.NS'])
            latest = json.loads((directory / 'eod_latest.json').read_text())
            self.assertEqual(latest['data']['INFY.NS']['vol_multiple'], 3)

    def test_relative_dates_use_each_collection_clock(self):
        for day in (2, 3):
            now = datetime(2026, 11, day, 12, tzinfo=ZoneInfo('Asia/Kolkata'))
            value, _ = parse_screener_date('1 hour ago', now, now)
            self.assertEqual(value, f'2026-11-{day:02d}T11:00:00+05:30')

    def test_fallback_date_excludes_event_date_in_headline(self):
        row = BeautifulSoup('<li><a>Meeting on 05 Nov 2026</a><span>02 Nov 2026</span></li>', 'html.parser').li
        value, _ = publication_date(row, row.a, datetime(2026, 11, 2), datetime(2026, 11, 2))
        self.assertEqual(value, '2026-11-02')

    def test_material_results_override_auditor_token(self):
        self.assertEqual(classify('Financial Results and Auditor Report'), ('results', 5))
        self.assertEqual(classify('Appointment of statutory auditor'), ('routine', 1))

    def test_digest_preserves_event_title_publication_time_and_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, public = root / 'data', root / 'public'
            data.mkdir(); public.mkdir()
            ann = {'headline': 'Board meeting on 05 Nov 2026', 'date': '2026-11-02T12:00:00+05:30', 'url': 'https://example.com/filing.pdf'}
            (data / 'announcements.json').write_text(json.dumps({'INFY.NS': [ann]}))
            (data / 'eod_latest.json').write_text('{"data": {}, "as_of": "2026-10-30"}')
            (data / 'eod_history.json').write_text('{}')
            (public / 'push_digest.json').write_text(json.dumps([{'ticker': 'INFY', 'source_url': ann['url'], 'id': 'reviewed-id'}]))
            with patch('generate_push.DATA_DIR', data), patch('generate_push.PUBLIC_DATA_DIR', public):
                generate_digest()
            snapshot = json.loads((public / 'snapshot.json').read_text())
            result = snapshot['feed'][0]
            self.assertEqual(result['timestamp'], ann['date'])
            self.assertEqual(result['headline'], ann['headline'])
            self.assertEqual(result['id'], 'reviewed-id')
            self.assertEqual(snapshot['as_of'], '2026-11-02')

    def test_successful_empty_exchange_feed_is_not_failed(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch('fetch_announcements.DATA_DIR', directory), patch('fetch_announcements.ALL_TICKERS', {'INFY.NS': '1'}), patch('fetch_announcements.fetch_bse_fallback', return_value=ExchangeFeed([], 'ready')), patch('fetch_announcements.requests.get') as fallback:
                parse_screener_announcements()
            fallback.assert_not_called()
            self.assertEqual(json.loads((directory / 'announcement_health.json').read_text())['stale_tickers'], [])

    def test_partial_price_failure_retains_previous_holding(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            previous = {'date': '2026-10-19', 'close': 100, 'volume': 50}
            (directory / 'eod_latest.json').write_text(json.dumps({'data': {'BAD.NS': previous}}))
            (directory / 'eod_history.json').write_text(json.dumps({'BAD.NS': [previous]}))
            frame = pd.DataFrame({('GOOD.NS', 'Close'): [100 + i for i in range(22)],
                                  ('GOOD.NS', 'Volume'): [100] * 21 + [300]},
                                 index=pd.date_range('2026-10-01', periods=22))
            with patch('fetch_prices.DATA_DIR', directory), patch('fetch_prices.yf.download', return_value=frame):
                fetch_prices(['GOOD.NS', 'BAD.NS'])
            latest = json.loads((directory / 'eod_latest.json').read_text())
            self.assertEqual(latest['data']['BAD.NS'], previous)
            self.assertEqual(latest['stale_tickers'], ['BAD.NS'])
            self.assertEqual(latest['data']['GOOD.NS']['vol_multiple'], 3)

    def test_total_price_failure_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = '{"data": {"BAD.NS": {"close": 100}}}'
            (directory / 'eod_latest.json').write_text(original)
            with patch('fetch_prices.DATA_DIR', directory), patch('fetch_prices.yf.download', return_value=pd.DataFrame()):
                with self.assertRaises(RuntimeError):
                    fetch_prices(['BAD.NS'])
            self.assertEqual((directory / 'eod_latest.json').read_text(), original)

    def test_partial_announcement_failure_retains_previous_holding(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            previous = [{'ticker': 'BAD.NS', 'headline': 'Existing filing', 'date': '2026-10-29', 'url': 'https://example.com/old.pdf'}]
            (directory / 'announcements.json').write_text(json.dumps({'BAD.NS': previous}))
            good = Mock(status_code=200, text='<section id="announcements"><li><a href="https://example.com/new.pdf">Financial results</a> 30 Oct 2026</li></section>')
            def request(url, **kwargs):
                if '/GOOD/' in url:
                    return good
                raise requests.ConnectionError('Source unavailable')
            with patch('fetch_announcements.DATA_DIR', directory), patch('fetch_announcements.ALL_TICKERS', {'GOOD.NS': '1', 'BAD.NS': '2'}), patch('fetch_announcements.requests.get', side_effect=request), patch('fetch_announcements.fetch_bse_fallback', return_value=[]), patch('fetch_announcements.time.sleep'):
                parse_screener_announcements()
            self.assertEqual(json.loads((directory / 'announcements.json').read_text())['BAD.NS'], previous)
            self.assertEqual(json.loads((directory / 'announcement_health.json').read_text())['stale_tickers'], ['BAD.NS'])

    def test_filing_previews_are_verbatim_on_their_stated_pages(self):
        evidence = json.loads(Path('data/filing_evidence.json').read_text())
        self.assertGreaterEqual(len(evidence), 5)
        for identifier, excerpt in evidence.items():
            pages = json.loads(Path(f'data/filings/{identifier}.json').read_text())
            page = next(page for page in pages if page['page'] == excerpt['page'])
            self.assertIn(normalize_text(excerpt['quote']), normalize_text(page['text']))


if __name__ == '__main__':
    unittest.main()
