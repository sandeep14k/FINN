"""Conservative financial metric matching and evidence-backed guidance history."""
import re
import math


def number_in_quotes(number, citations):
    if not isinstance(number, (int, float)) or isinstance(number, bool) or not math.isfinite(number):
        return False
    for citation in citations:
        text = citation.get('quote', '').replace(',', '').replace('−', '-')
        text = re.sub(r'\((\d+(?:\.\d+)?)\)', r'-\1', text)
        text = re.sub(r'(?<=\d)\s*[-–—]\s*(?=\d)', ' ', text)
        values = [float(value) for value in re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?', text)]
        if any(math.isclose(number, value, rel_tol=1e-9, abs_tol=1e-9) for value in values):
            return True
    return False


def metric_key(name):
    text = re.sub(r'[^a-z0-9]+', ' ', name.lower())
    if 'margin' in text:
        if 'ebitda' in text:
            return 'ebitda_margin'
        if 'operating' in text or re.search(r'\bebit\b', text):
            return 'adjusted_operating_margin' if 'adjusted' in text else 'operating_margin'
        if 'net' in text or 'pat' in text:
            return 'net_margin'
    if 'revenue' in text or 'sales' in text:
        if 'growth' not in text:
            return 'revenue'
        if 'qoq' in text or 'sequential' in text:
            return 'revenue_growth_qoq'
        if 'cagr' in text or 'compound' in text:
            return 'revenue_growth_cagr'
        return 'revenue_growth'
    if 'capex' in text or 'capital expenditure' in text:
        return 'capex'
    if 'profit after tax' in text or re.search(r'\bpat\b', text):
        return 'pat'
    return text.strip().replace(' ', '_')


def quarter_key(period):
    match = re.fullmatch(r'Q([1-4])\s+FY(\d{2}|\d{4})', period.strip().upper())
    if not match:
        return (0, 0)
    year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
    return year, int(match[1])


def canonical_unit(value):
    text = value.strip().lower()
    return '%' if text in ('%', 'percent', 'percentage') else text


def canonical_basis(value):
    text = re.sub(r'[-_]+', ' ', value.lower())
    text = ' '.join(text.split())
    if 'constant currency' in text:
        return 'constant currency'
    return text


def canonical_scope(value):
    text = value.strip().lower()
    return text if text in ('consolidated', 'standalone') else 'unknown'


def target_kind(item):
    if item.get('target_type') in ('range', 'minimum', 'maximum', 'exact'):
        return item['target_type']
    quote = item.get('quote', item.get('statement', '')).lower()
    if re.search(r'at least|minimum|no less than', quote):
        return 'minimum'
    if re.search(r'at most|maximum|no more than|not exceed|up to', quote):
        return 'maximum'
    low, high = item.get('target_low'), item.get('target_high')
    return 'exact' if low is not None and low == high else 'range'


def metric_direction(key):
    return 'higher' if key in ('revenue', 'revenue_growth', 'revenue_growth_qoq', 'operating_margin',
                                'adjusted_operating_margin', 'ebitda_margin', 'pat', 'net_margin') else 'range'


def guidance_history(extracted, documents, index, verify):
    """Only group verified guidance with an explicit matching basis and unit."""
    groups = {}
    for document in sorted(extracted, key=lambda item: quarter_key(item['document'])):
        for item in document.get('guidance', []):
            basis = ' '.join(item.get('basis', '').lower().split())
            if 'constant currency' in basis:
                basis = 'constant currency'
            elif basis in ('reported', 'operating', 'operating margin'):
                basis = 'reported'
            scope = ' '.join(item.get('scope', 'unspecified').lower().split())
            low, high = item.get('target_low'), item.get('target_high')
            if low is None or high is None or low > high or not basis:
                continue
            citation = verify({'document': document['document'], 'page': item['page'],
                               'quote': item['quote']}, documents, index)
            if not citation['verified']:
                continue
            if not all(number_in_quotes(number, [citation]) for number in (low, high)):
                continue
            key = (metric_key(item['metric']), item['period_covered'].upper(), item['unit'], basis, scope)
            group = groups.setdefault(key, {'metric': item['metric'], 'period': key[1],
                                           'unit': key[2], 'basis': basis, 'scope': scope, 'entries': []})
            if any(entry['document'] == document['document'] for entry in group['entries']):
                continue
            group['entries'].append({'document': document['document'], 'low': low, 'high': high,
                                     'period_inferred': item.get('period_inferred_from_call', False),
                                     'citation': citation})
    output = []
    for group in groups.values():
        if len(group['entries']) < 2:
            continue
        first, last = group['entries'][0], group['entries'][-1]
        if first['low'] == last['low'] and first['high'] == last['high']:
            group['change'] = 'unchanged'
        elif last['low'] <= first['low'] and last['high'] <= first['high']:
            group['change'] = 'lowered'
        elif last['low'] >= first['low'] and last['high'] >= first['high']:
            group['change'] = 'raised'
        else:
            group['change'] = 'revised'
        output.append(group)
    return output
