import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from evidence_quality import useful_statement, business_descriptions
from extract_pdf import layout_text
from filing_analysis import period_dates, change_percent, date_in_text, verified
from financial_metrics import number_in_quotes
from promised_vs_delivered import build_comparisons
from ground import verify_citation
from ground import guard_comparison
from monitor import evaluate_alerts, run_once, DEFAULT_RULES


class ResearchQualityTests(unittest.TestCase):
    def test_empty_quote_is_never_verified(self):
        for quote in ('', '  '):
            self.assertFalse(verify_citation({'document': 'Q1 FY26', 'page': 1, 'quote': quote}, {'call.json': [{'page': 1, 'text': 'Evidence'}]}, [{'quarter': 'Q1 FY26', 'filename': 'call.json', 'symbol': 'TEST'}])['verified'])

    def test_matching_actual_prefers_guidance_scope(self):
        guidance = {'metric': 'Revenue growth', 'period_covered': 'FY26', 'basis': 'reported', 'scope': 'consolidated', 'unit': '%', 'target_low': 10, 'target_high': 12, 'quote': 'Guidance 10% to 12%.', 'page': 1}
        actual = {'metric': 'Revenue growth', 'period': 'FY26', 'basis': 'reported', 'scope': 'consolidated', 'unit': '%', 'value': 11, 'quote': 'Growth 11%.', 'page': 2}
        for candidates in ([{**actual, 'scope': 'standalone'}, actual], [actual, {**actual, 'scope': 'standalone'}]):
            result = build_comparisons([{'document': 'Q1 FY26', 'guidance': [guidance]}, {'document': 'Q4 FY26', 'actuals': candidates}])
            self.assertEqual(result[0]['delivery']['scope'], 'consolidated')

    def test_saved_question_and_accounting_noise_rejected(self):
        for sentence in ['One last question - that comment on EBIT margin of 4% and Adjusted EBITDA margin of close to 6%.', 'Items that will not be reclassified to profit or loss (i) Items that will not be reclassified to profit or loss 37 84.87 (29.87) (ii) Income tax on items that will not be reclassified to profit or loss 39 (28.55) 10.44 B.', 'Key Audit Matter Auditor’s Response 1 Revenue Recognition – Refer note 2.2 of the standalone financial statements.']:
            self.assertFalse(useful_statement(sentence), sentence)

    def metric(self, low=20, high=22, actual=23, kind='range', direction='range'):
        shared = {'metric_key': 'capex', 'basis': 'reported', 'unit': '%', 'scope': 'consolidated'}
        return {'promise': {**shared, 'period': 'FY26', 'target_low': low, 'target_high': high, 'target_type': kind, 'direction': direction, 'citations': [{'quote': 'Target 20% to 22%.'}]},
                'delivery': {**shared, 'period': 'FY26', 'actual_value': actual, 'comparable': True, 'statement': 'Actual was 23%.', 'citations': [{'quote': f'Actual was {actual}%.'}]}}

    def test_neutral_metric_above_range_is_not_a_miss(self):
        result = guard_comparison(self.metric())
        self.assertEqual(result['delivery']['status'], 'ABOVE_RANGE')

    def test_higher_better_metric_can_beat(self):
        self.assertEqual(guard_comparison(self.metric(direction='higher'))['delivery']['status'], 'BEAT')

    def test_minimum_target_has_no_fabricated_upper_bound(self):
        self.assertEqual(guard_comparison(self.metric(high=None, kind='minimum'))['delivery']['status'], 'MET')

    def test_maximum_target_has_no_fabricated_lower_bound(self):
        self.assertEqual(guard_comparison(self.metric(low=None, high=22, actual=21, kind='maximum'))['delivery']['status'], 'MET')

    def test_accounting_parentheses_mean_negative(self):
        self.assertTrue(number_in_quotes(-123, [{'quote': 'Profit (123).'}]))
        self.assertFalse(number_in_quotes(123, [{'quote': 'Profit (123).'}]))
        self.assertTrue(number_in_quotes(22, [{'quote': 'Guidance 20-22%.'}]))

    def test_questions_and_boilerplate_do_not_become_research(self):
        rejected = [
            'Could you discuss the revenue growth outlook for the next financial year.',
            'The auditor conducted the review in accordance with the Guidance Note on audit of internal controls.',
            'Fair value financial assets are recognised under the applicable accounting policy.',
            'We provide onsite childcare support options for our employees in India.',
            'The company has raised its capital expenditure guidance from 100 crore to',
        ]
        for sentence in rejected:
            self.assertFalse(useful_statement(sentence), sentence)

    def test_business_description_is_a_literal_company_sentence(self):
        sentence = 'Example Limited provides engineering and consulting services to customers across the automotive industry.'
        facts = business_descriptions([{'page': 4, 'text': 'Company overview. ' + sentence}], ['Example'])
        self.assertEqual(facts[0]['quote'], sentence)
        self.assertEqual(facts[0]['page'], 4)

    def test_layout_extraction_reassembles_columns_into_rows(self):
        page = Mock()
        page.get_text.return_value = [(10, 10, 40, 18, 'Revenue'), (10, 30, 40, 38, 'PAT'), (100, 10, 120, 18, '100'), (100, 30, 120, 38, '20'), (170, 10, 190, 18, '90'), (170, 30, 190, 38, '18')]
        self.assertEqual(layout_text(page).splitlines(), ['Revenue  100  90', 'PAT  20  18'])

    def test_layout_quotes_remain_page_verifiable(self):
        pages = [{'page': 10, 'text': 'Revenue 100 PAT 20 90 18', 'layout_text': 'Revenue 100 90\nPAT 20 18'}]
        self.assertTrue(verified('Revenue 100 90', 10, pages))
        self.assertFalse(verified('Revenue 100 90', 11, pages))

    def test_quarterly_comparisons_reject_half_year_steps(self):
        self.assertTrue(period_dates('2026-09-30', '2026-06-30', '2025-09-30'))
        self.assertFalse(period_dates('2026-09-30', '2026-03-31', '2025-09-30'))
        self.assertTrue(date_in_text('2026-09-30', "Quarter ended 30th Sep'26"))
        self.assertIsNone(change_percent(100, 0))
        self.assertIsNone(change_percent(100, -50))
        self.assertEqual(change_percent(120, 100), 20)

    def test_server_alerts_obey_custom_thresholds(self):
        prices = {'INFY.NS': {'date': '2026-10-30', 'pct_change': 4, 'vol_multiple': 2.1}}
        rules = {**DEFAULT_RULES, 'price': 5, 'volume': 2}
        alerts = evaluate_alerts([], prices, rules)
        self.assertEqual([alert['type'] for alert in alerts], ['volume'])

    def test_alert_ledger_deduplicates_refreshes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data, public = root / 'data', root / 'finn-app/public/data'
            data.mkdir(); public.mkdir(parents=True)
            digest = [{'id': 'event-1', 'ticker': 'INFY', 'headline': 'Leadership changed', 'type': 'management_change', 'priority': 5, 'timestamp': '2026-10-30'}]
            (public / 'push_digest.json').write_text(json.dumps(digest))
            (public / 'eod_latest.json').write_text(json.dumps({'data': {'INFY.NS': {'date': '2026-10-30', 'pct_change': 4, 'vol_multiple': 1}}}))
            with patch('monitor.DATA_DIR', data), patch('monitor.ROOT_DIR', root), patch('monitor.fetch_prices'), patch('monitor.parse_screener_announcements'), patch('monitor.generate_digest'):
                run_once(); run_once()
            ledger = json.loads((data / 'alerts.json').read_text())
            self.assertEqual(len(ledger), 2)
            self.assertEqual(len({alert['id'] for alert in ledger}), 2)


if __name__ == '__main__':
    unittest.main()
