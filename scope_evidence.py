"""Resolve an unknown consolidation scope only from a verified contextual citation."""
import json

from config import DATA_DIR, normalize_text
from financial_metrics import canonical_scope, number_in_quotes

FIELDS = ('document', 'page', 'quote')


def load_evidence(symbol):
    path = DATA_DIR / 'docs' / symbol / 'scope_evidence.json'
    if not path.exists():
        return []
    records = json.loads(path.read_text())
    return [record for record in records if isinstance(record, dict)]


def _citation(record):
    return {field: record.get(field) for field in FIELDS}


def apply_scope(metric, records, documents, index, verify):
    """Attach a scope that a verified quote states; never guess or overwrite."""
    promise, delivery = metric.get('promise', {}), metric.get('delivery', {})
    key, period = promise.get('metric_key'), promise.get('period', '').strip().upper()
    for record in records:
        if record.get('metric_key') != key or str(record.get('period', '')).strip().upper() != period:
            continue
        scope = canonical_scope(record.get('scope', ''))
        if scope == 'unknown':
            continue
        citation = verify(_citation(record), documents, index)
        if not citation['verified']:
            continue
        if scope not in normalize_text(record.get('quote', '')):
            continue
        sides = [side for side, item in (('promise', promise), ('delivery', delivery))
                 if canonical_scope(item.get('scope', 'unknown')) == 'unknown']
        value = delivery.get('actual_value')
        if 'delivery' in sides and isinstance(value, (int, float)) and not isinstance(value, bool):
            if not number_in_quotes(value, [citation]):
                continue
        if not sides:
            continue
        for side in sides:
            metric[side]['scope'] = scope
            known = metric[side].setdefault('citations', [])
            if all(known_item.get('quote') != citation.get('quote') for known_item in known):
                known.append(_citation(record))
        metric['scope_evidence'] = {
            'scope': scope,
            'quote': record.get('quote'),
            'document': record.get('document'),
            'page': record.get('page'),
            'note': record.get('note', ''),
        }
    return metric


if __name__ == '__main__':
    import sys
    from config import ROOT_DIR
    from ground import verify_citation

    symbol = sys.argv[1] if len(sys.argv) > 1 else 'INFY'
    doc_dir = DATA_DIR / 'docs' / symbol
    comparison = json.loads((doc_dir / 'comparison.json').read_text())
    index = json.loads((doc_dir / 'index.json').read_text())
    documents = {m['filename']: json.loads((doc_dir / m['filename']).read_text()) for m in index}
    for meta in index:
        meta['symbol'] = symbol
    resolved = 0
    for metric in comparison.get('metrics', []):
        before = metric['delivery'].get('scope')
        apply_scope(metric, load_evidence(symbol), documents, index, verify_citation)
        after = metric['delivery'].get('scope')
        resolved += before != after
        print(f"{metric['promise']['metric_key']} {metric['promise']['period']}: {before} -> {after}")
    print(f'Resolved scope for {resolved} comparison(s) in {symbol}.')
