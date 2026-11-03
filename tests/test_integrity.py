import json
import unittest
import tempfile
from unittest.mock import patch
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from fetch_announcements import parse_screener_date
from generate_push import classify
from ground import guard_comparison, verify_citation
from label_docs import explicit_quarter
from financial_metrics import metric_key
from ingest_ticker import ingest
from explicit_guidance import extract_explicit_guidance
from promised_vs_delivered import build_comparisons
from scope_evidence import apply_scope

class IntegrityTests(unittest.TestCase):
    def test_embedded_date_not_today(self):
        value, _ = parse_screener_date('29 Oct - a filing summary', datetime(2026, 10, 31))
        self.assertEqual(value, '2026-10-29')

    def test_unknown_date_stays_unknown(self):
        value, _ = parse_screener_date('No valid date', datetime(2026, 10, 31))
        self.assertIsNone(value)

    def test_new_year_rollover(self):
        value, _ = parse_screener_date('31 Dec', datetime(2026, 1, 2))
        self.assertEqual(value, '2025-12-31')

    def test_financial_name_is_not_results(self):
        self.assertEqual(classify('UNI Financial launches branch software')[0], 'other')
        self.assertEqual(classify('Unaudited financial results for quarter ended')[0], 'results')

    def test_annual_vs_quarter_never_beat(self):
        metric = {'promise': {'period': 'FY26'}, 'delivery': {'period': 'Q4 FY26', 'status': 'BEAT', 'statement': 'Quarterly growth 4.1%.', 'comparable': True}}
        self.assertEqual(guard_comparison(metric)['delivery']['status'], 'NOT_COMPARABLE')

    def test_missing_period_fails_closed(self):
        metric = {'promise': {'period': 'FY26'}, 'delivery': {'status': 'MET', 'statement': '20.9%'}}
        self.assertEqual(guard_comparison(metric)['delivery']['status'], 'NOT_COMPARABLE')

    def test_matching_period_can_be_compared(self):
        metric = {'promise': {'period': 'FY26', 'target_low': 20, 'target_high': 22, 'direction': 'higher'}, 'delivery': {'period': 'FY26', 'status': 'BEAT', 'statement': '21%', 'actual_value': 21, 'comparable': True}}
        for side in ('promise', 'delivery'):
            metric[side].update(metric_key='margin', basis='reported', unit='%', scope='consolidated')
        metric['promise']['citations'] = [{'quote': 'Guidance is 20% to 22%.'}]
        metric['delivery']['citations'] = [{'quote': 'Operating margin was 21%.'}]
        self.assertEqual(guard_comparison(metric)['delivery']['status'], 'MET')

    def test_matching_period_different_basis_rejected(self):
        metric = {'promise': {'period': 'FY26', 'metric_key': 'revenue_growth', 'basis': 'constant currency', 'unit': '%', 'scope': 'consolidated', 'target_low': 3, 'target_high': 4}, 'delivery': {'period': 'FY26', 'metric_key': 'revenue_growth', 'basis': 'reported currency', 'unit': '%', 'scope': 'consolidated', 'actual_value': 5, 'comparable': True, 'statement': 'Growth was 5%.', 'status': 'BEAT'}}
        self.assertEqual(guard_comparison(metric)['delivery']['status'], 'NOT_COMPARABLE')

    def test_invented_actual_value_rejected(self):
        metric = {'promise': {'period': 'FY26', 'metric_key': 'margin', 'basis': 'reported', 'unit': '%', 'scope': 'consolidated', 'target_low': 20, 'target_high': 22, 'citations': [{'quote': '20% to 22%'}]}, 'delivery': {'period': 'FY26', 'metric_key': 'margin', 'basis': 'reported', 'unit': '%', 'scope': 'consolidated', 'actual_value': 50, 'comparable': True, 'statement': 'Margin was 50%.', 'status': 'BEAT', 'citations': [{'quote': 'Margin was 21%.'}]}}
        self.assertEqual(guard_comparison(metric)['delivery']['status'], 'NOT_COMPARABLE')

    def test_wrong_page_quote_rejected(self):
        citation = {'document': 'Q1 FY27', 'page': 2, 'quote': 'Revenue rose.'}
        index = [{'quarter': 'Q1 FY27', 'filename': 'call.json', 'symbol': 'TEST'}]
        docs = {'call.json': [{'page': 1, 'text': 'Revenue rose.'}]}
        self.assertFalse(verify_citation(citation, docs, index)['verified'])

    def test_additional_demo_excerpts_match_source_pages(self):
        for symbol in ('ETERNAL', 'LAURUSLABS'):
            payload = json.loads(Path(f'finn-app/public/data/pull/{symbol}.json').read_text())
            self.assertIn(payload['mode'], ('evidence_only', 'source_grounded'))
            self.assertEqual(payload['metrics'], [])
            self.assertGreater(len(payload['evidence']), 0)
            for fact in payload['evidence'] + payload['business_snapshot']:
                citation = fact['citation']
                params = parse_qs(urlparse(citation['source_path']).query)
                pages = json.loads(Path(f"finn-app/public/data/docs/{symbol}/{params['file'][0]}").read_text())
                text = next(p['text'] for p in pages if p['page'] == citation['page'])
                self.assertIn(' '.join(citation['quote'].split()), ' '.join(text.split()))

    def test_quarter_ended_overrides_call_month(self):
        self.assertEqual(explicit_quarter('Transcript for the quarter ended March 31, 2026, conducted on May 7'), 'Q4 FY26')
        self.assertEqual(explicit_quarter('quarter ended September 30, 2026'), 'Q2 FY27')

    def test_financial_metrics_remain_distinct(self):
        self.assertEqual(metric_key('Revenue growth (constant currency)'), metric_key('Sales growth'))
        self.assertNotEqual(metric_key('EBITDA margin'), metric_key('Operating margin'))
        self.assertNotEqual(metric_key('Revenue growth QoQ'), metric_key('Revenue growth YoY'))
        self.assertNotEqual(metric_key('Adjusted operating margin'), metric_key('Operating margin'))

    def test_explicit_guidance_keeps_real_quote_and_annual_period(self):
        quote = 'Our revenue growth guidance for the financial year 2027 is 1.5% to 3.5% growth year-on-year in constant currency terms.'
        items = extract_explicit_guidance([{'page': 7, 'text': quote}], 'Q4 FY26')
        self.assertEqual(items[0]['period_covered'], 'FY27')
        self.assertEqual(items[0]['quote'], quote)
        self.assertEqual(items[0]['scope'], 'unknown')
        self.assertFalse(items[0]['period_inferred_from_call'])

    def test_q4_does_not_guess_ambiguous_guidance_year(self):
        self.assertEqual(extract_explicit_guidance([{'page': 1, 'text': 'Our operating margin guidance is 20% to 22%.'}], 'Q4 FY26'), [])

    def test_matching_prefers_full_year_to_interim_observation(self):
        guidance = {'metric': 'Revenue growth', 'target_low': 3, 'target_high': 3.5, 'unit': '%', 'period_covered': 'FY26', 'basis': 'constant currency', 'quote': 'Guidance 3% to 3.5%.', 'page': 1}
        actual = {'metric': 'revenue_growth', 'value': 3.1, 'unit': 'percent', 'period': 'FY26', 'basis': 'constant-currency', 'quote': 'Full year growth 3.1%.', 'page': 2}
        docs = [{'document': 'Q3 FY26', 'guidance': [guidance], 'actuals': []}, {'document': 'Q4 FY26', 'guidance': [], 'actuals': [{**actual, 'period': 'Q4 FY26', 'value': 4.1}, actual]}]
        comparison = build_comparisons(docs)[0]
        self.assertEqual(comparison['delivery']['actual_value'], 3.1)
        self.assertEqual(comparison['delivery']['period'], 'FY26')
        self.assertEqual(guard_comparison(comparison)['delivery']['status'], 'NOT_COMPARABLE')

    def test_same_title_documents_keep_distinct_sources(self):
        documents = [{'type': 'TRANSCRIPT', 'period': 'Jul 2026 Transcript', 'url': f'https://example.com/{i}.pdf'} for i in range(2)]
        with tempfile.TemporaryDirectory() as directory, patch('ingest_ticker.DATA_DIR', Path(directory)), patch('ingest_ticker.search_screener_documents', return_value=documents), patch('ingest_ticker.download_single_document', return_value='source.pdf'), patch('ingest_ticker.time.sleep'):
            def extract(*args, **kwargs):
                Path(kwargs['out_path']).write_text('[{"page": 1, "text": "Source evidence"}]')
            with patch('ingest_ticker.extract_pdf_to_json', side_effect=extract):
                ingest('TEST')
            sources = json.loads((Path(directory) / 'docs/TEST/sources.json').read_text())
            self.assertEqual(len(sources), 2)
            self.assertEqual(set(sources.values()), {doc['url'] for doc in documents})

    def test_pending_target_is_not_rejected_as_mismatched(self):
        metric = {'promise': {'period': 'FY99'}, 'delivery': {'period': 'Q1 FY99', 'status': 'PENDING', 'statement': 'Awaiting full year.'}}
        result = guard_comparison(metric)['delivery']
        self.assertEqual(result['status'], 'PENDING')
        self.assertFalse(result['comparable'])

    def test_guidance_history_quotes_verify_and_revisions_are_preserved(self):
        payload = json.loads(Path('finn-app/public/data/pull/INFY.json').read_text())
        history = next(h for h in payload['guidance_history'] if h['period'] == 'FY27' and h['metric'].startswith('Revenue'))
        self.assertEqual(history['change'], 'lowered')
        self.assertGreaterEqual(len(history['entries']), 3)
        for entry in history['entries']:
            citation = entry['citation']
            params = parse_qs(urlparse(citation['source_path']).query)
            pages = json.loads(Path(f"finn-app/public/data/docs/INFY/{params['file'][0]}").read_text())
            text = next(p['text'] for p in pages if p['page'] == citation['page'])
            self.assertIn(' '.join(citation['quote'].split()), ' '.join(text.split()))

    def test_published_verdicts_are_scoped_and_verified(self):
        payload = json.loads(Path('finn-app/public/data/pull/INFY.json').read_text())
        ranked = [m for m in payload['metrics'] if m['promise']['metric_key'] == 'revenue_growth' and m['promise']['period'] == 'FY26']
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]['delivery']['status'], 'MET')
        self.assertEqual(ranked[0]['scope_evidence']['scope'], 'consolidated')
        for metric in payload['metrics']:
            if metric is not ranked[0]:
                self.assertIn(metric['delivery']['status'], ('NOT_COMPARABLE', 'PENDING', 'UNVERIFIED'))
            for side in ('promise', 'delivery'):
                self.assertTrue(metric[side]['citations'])
                self.assertTrue(all(c['verified'] for c in metric[side]['citations']))

    def test_scope_evidence_upgrades_only_when_quote_is_verified(self):
        promise = {'metric_key': 'revenue_growth', 'period': 'FY26', 'scope': 'unknown', 'basis': 'constant currency', 'unit': '%',
                   'target_low': 3.0, 'target_high': 3.5, 'citations': [{'document': 'Q3 FY26', 'page': 1, 'quote': 'Guidance 3% to 3.5% in constant currency.'}]}
        delivery = {'metric_key': 'revenue_growth', 'period': 'FY26', 'scope': 'unknown', 'basis': 'constant currency', 'unit': '%',
                    'actual_value': 3.1, 'comparable': True, 'statement': 'Growth was 3.1%.',
                    'citations': [{'document': 'Q4 FY26', 'page': 2, 'quote': 'Growth was 3.1% in constant currency.'}]}
        metric = {'promise': promise, 'delivery': delivery}
        index = [{'quarter': 'Q3 FY26', 'filename': 'a.json', 'symbol': 'TEST'}, {'quarter': 'Q4 FY26', 'filename': 'b.json', 'symbol': 'TEST'}]
        documents = {'a.json': [{'page': 1, 'text': promise['citations'][0]['quote']}],
                     'b.json': [{'page': 2, 'text': delivery['citations'][0]['quote']}, {'page': 3, 'text': 'Consolidated revenue grew 3.1%.'}]}
        record = {'metric_key': 'revenue_growth', 'period': 'FY26', 'scope': 'consolidated', 'document': 'Q4 FY26', 'page': 3,
                  'quote': 'Consolidated revenue grew 3.1%.'}
        verified = apply_scope(metric, [record], documents, index, verify_citation)
        self.assertEqual(verified['promise']['scope'], 'consolidated')
        self.assertEqual(verified['delivery']['scope'], 'consolidated')
        self.assertEqual(guard_comparison(verified)['delivery']['status'], 'MET')

        invented = {'promise': {**promise, 'scope': 'unknown'}, 'delivery': {**delivery, 'scope': 'unknown'}}
        wrong_page = {**record, 'page': 1}
        self.assertEqual(apply_scope(invented, [wrong_page], documents, index, verify_citation)['delivery']['scope'], 'unknown')
        self.assertEqual(guard_comparison(invented)['delivery']['status'], 'NOT_COMPARABLE')

        unmatched_value = {'promise': {**promise, 'scope': 'unknown'}, 'delivery': {**delivery, 'scope': 'unknown', 'actual_value': 9.9}}
        self.assertEqual(apply_scope(unmatched_value, [record], documents, index, verify_citation)['delivery']['scope'], 'unknown')

if __name__ == '__main__':
    unittest.main()
