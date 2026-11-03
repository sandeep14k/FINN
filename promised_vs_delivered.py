"""Match extracted financial facts deterministically; grounding assigns verdicts."""
import json
import sys
from config import DATA_DIR
from financial_metrics import canonical_basis, canonical_scope, canonical_unit, metric_key, quarter_key, metric_direction, target_kind


def build_comparisons(extracted_data, limit=4):
    documents = sorted(extracted_data, key=lambda item: quarter_key(item['document']))
    comparisons, seen = [], set()
    for position, document in enumerate(documents):
        for guidance in document.get('guidance', []):
            key = metric_key(guidance['metric'])
            target_period = guidance['period_covered'].strip().upper()
            identity = (key, target_period, canonical_basis(guidance.get('basis', 'unknown')),
                        canonical_unit(guidance['unit']), canonical_scope(guidance.get('scope', 'unknown')))
            if identity in seen:
                continue
            seen.add(identity)
            candidates = []
            for later in documents[position + 1:]:
                for actual in later.get('actuals', []):
                    if key == metric_key(actual['metric']):
                        candidates.append((later, actual))
            candidates.sort(key=lambda pair: (
                pair[1]['period'].strip().upper() == target_period,
                canonical_basis(pair[1].get('basis', 'unknown')) == identity[2],
                canonical_unit(pair[1]['unit']) == canonical_unit(guidance['unit']),
                canonical_scope(pair[1].get('scope', 'unknown')) == identity[4],
            ), reverse=True)
            promise = {
                'metric_key': key, 'basis': identity[2], 'unit': canonical_unit(guidance['unit']),
                'scope': canonical_scope(guidance.get('scope', 'unknown')),
                'target_low': guidance.get('target_low'), 'target_high': guidance.get('target_high'),
                'direction': metric_direction(key), 'target_type': target_kind(guidance), 'period': target_period,
                'statement': guidance['quote'],
                'citations': [{'document': document['document'], 'page': guidance['page'], 'quote': guidance['quote']}],
            }
            delivery = {
                'metric_key': key, 'basis': 'unknown', 'unit': 'unknown', 'scope': 'unknown',
                'actual_value': None, 'period': '', 'comparable': False,
                'status': 'NOT_COMPARABLE', 'statement': 'No matching later reported observation was extracted.',
                'reason': 'A complete target-period result on a matched basis is required.', 'citations': [],
            }
            if candidates:
                later, actual = candidates[0]
                delivery.update({
                    'basis': canonical_basis(actual.get('basis', 'unknown')),
                    'unit': canonical_unit(actual['unit']), 'scope': canonical_scope(actual.get('scope', 'unknown')),
                    'actual_value': actual['value'], 'period': actual['period'].strip().upper(),
                    'comparable': True, 'statement': actual['quote'],
                    'citations': [{'document': later['document'], 'page': actual['page'], 'quote': actual['quote']}],
                })
            comparisons.append({'theme': f"{target_period} · {guidance['metric']}", 'promise': promise, 'delivery': delivery})
            if len(comparisons) >= limit:
                return comparisons
    return comparisons


def compare_promises(symbol):
    directory = DATA_DIR / 'docs' / symbol
    extracted = json.loads((directory / 'extracted_metrics.json').read_text())
    result = {'metrics': build_comparisons(extracted)}
    (directory / 'comparison.json').write_text(json.dumps(result, indent=2))
    print(f"Matched {len(result['metrics'])} promises for {symbol}; grounding validates periods, bases and citations.")


if __name__ == '__main__':
    compare_promises(sys.argv[1] if len(sys.argv) > 1 else 'INFY')
