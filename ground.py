"""Validate quotations and comparison periods before publishing research."""
import json
from urllib.parse import urlencode
import math
import re
import sys
from datetime import date
from financial_metrics import guidance_history, number_in_quotes, target_kind
from config import DATA_DIR, ROOT_DIR, PUBLIC_DATA_DIR, normalize_text
from scope_evidence import apply_scope, load_evidence

PUBLIC_PULL_DIR = PUBLIC_DATA_DIR / 'pull'

def verify_citation(citation, documents, index):
    if not isinstance(citation.get('quote'), str) or not citation['quote'].strip():
        return {**citation, 'verified': False}
    matching = [d for d in index if d['quarter'] == citation['document'] and not d.get('is_duplicate')]
    for meta in matching:
        for page in documents.get(meta['filename'], []):
            if page['page'] == citation['page'] and any(normalize_text(citation['quote']) in normalize_text(page.get(key, '')) for key in ('text', 'layout_text')):
                return {**citation, 'verified': True, 'source_path': "/api/source?" + urlencode({"symbol": meta["symbol"], "file": meta["filename"]}), 'source_url': meta.get('source_url')}
    return {**citation, 'verified': False}

def guard_comparison(metric):
    delivery = metric['delivery']
    # Legacy payloads have no structured delivery period. Fail closed.
    target = metric['promise']['period'].strip().upper()
    actual = delivery.get('period', '').strip().upper()
    promise = metric['promise']
    future = period_end(target)
    reasons = []
    if not future:
        reasons.append('The target reporting period is not recognised.')
    if actual != target:
        reasons.append('The reported observation does not cover the complete target period.')
    comparable = bool(future and actual and target == actual and delivery.get('comparable') is True
                      and not (future and future > date.today()))
    for key in ('metric_key', 'basis', 'unit', 'scope'):
        left, right = normalize_text(promise.get(key, '')), normalize_text(delivery.get(key, ''))
        comparable = comparable and bool(left and left not in ('unknown', 'unspecified') and left == right)
        if not left or not right or left in ('unknown', 'unspecified') or right in ('unknown', 'unspecified'):
            reasons.append(f'The {key.replace("_", " ")} is not established on both sides.')
        elif left != right:
            reasons.append(f'The {key.replace("_", " ")} differs between guidance and actual.')
    low, high, value = promise.get('target_low'), promise.get('target_high'), delivery.get('actual_value')
    kind = target_kind(promise)
    required = [value] + ([low] if kind in ('minimum', 'exact') else [high] if kind == 'maximum' else [low, high])
    numeric = all(isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number) for number in required)
    delivery.pop('observation', None)
    observation_fields = ('metric_key', 'basis', 'unit')
    observation_match = (future and future <= date.today() and target == actual and numeric and kind == 'range'
                         and all(normalize_text(promise.get(key, '')) not in ('', 'unknown', 'unspecified')
                                 and normalize_text(promise.get(key, '')) == normalize_text(delivery.get(key, '')) for key in observation_fields))
    if observation_match and not comparable and low <= high and all(number_in_quotes(number, promise.get('citations', [])) for number in (low, high)) and number_in_quotes(value, delivery.get('citations', [])):
        position = 'within' if low <= value <= high else 'above' if value > high else 'below'
        delivery['observation'] = f'The reported {value:g}{promise["unit"]} is numerically {position} the stated {low:g}–{high:g}{promise["unit"]} range. This observation does not establish matching consolidation scope.'
    comparable = comparable and numeric
    if not numeric:
        reasons.append('The numerical target and actual are incomplete.')
    if comparable:
        bounds = [low] if kind in ('minimum', 'exact') else [high] if kind == 'maximum' else [low, high]
        comparable = all(number_in_quotes(number, promise.get('citations', [])) for number in bounds) and number_in_quotes(value, delivery.get('citations', []))
        if not comparable:
            reasons.append('One or more numerical values are absent from their cited quotations.')
    if comparable and kind == 'range' and low > high:
        comparable = False
        reasons.append('The target range is reversed.')
    if comparable:
        direction = promise.get('direction', 'range')
        floor = low if kind != 'maximum' else None
        ceiling = high if kind in ('range', 'maximum') else low if kind == 'exact' else None
        within = (floor is None or value >= floor) and (ceiling is None or value <= ceiling)
        if within:
            delivery['status'] = 'MET'
        elif kind in ('minimum', 'maximum'):
            delivery['status'] = 'MISSED'
        elif direction == 'higher':
            delivery['status'] = 'BEAT' if ceiling is not None and value > ceiling else 'MISSED'
        elif direction == 'lower':
            delivery['status'] = 'BEAT' if floor is not None and value < floor else 'MISSED'
        else:
            delivery['status'] = 'ABOVE_RANGE' if ceiling is not None and value > ceiling else 'BELOW_RANGE'
        delivery['reason'] = 'The complete reporting period, metric, unit, accounting basis and consolidation scope match. Values are present in the cited evidence.'
    if not comparable:
        delivery['status'] = 'PENDING' if future and future > date.today() else 'NOT_COMPARABLE'
        delivery['statement'] = re.sub(r',?\s*(?:surpassing|meeting|successfully landing|within the guided).*', '.', delivery['statement'], flags=re.I)
        delivery['reason'] = ('The target reporting period has not ended. Interim results are not a final delivery verdict.'
                              if delivery['status'] == 'PENDING' else
                              ' '.join(reasons[:3]) or 'The evidence does not establish a comparable target and actual.')
    delivery['comparable'] = bool(comparable)
    return metric

def period_end(period):
    """Indian March-ending fiscal periods only; unknown periods remain unscored."""
    match = re.fullmatch(r'(?:Q([1-4])\s+)?FY(\d{2}|\d{4})', period.strip().upper())
    if not match:
        return None
    year = int(match[2]) + (2000 if len(match[2]) == 2 else 0)
    quarter = int(match[1] or 4)
    month, day = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}[quarter]
    return date(year if quarter == 4 else year - 1, month, day)

def ground_data(symbol):
    doc_dir = DATA_DIR / 'docs' / symbol
    comparison = json.loads((doc_dir / 'comparison.json').read_text())
    index = json.loads((doc_dir / 'index.json').read_text())
    sources_path = doc_dir / 'sources.json'
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    for meta in index:
        meta['symbol'] = symbol
        meta['source_url'] = sources.get(meta['filename'])
    documents = {m['filename']: json.loads((doc_dir / m['filename']).read_text()) for m in index}
    evidence = load_evidence(symbol)
    metrics = []
    for metric in comparison.get('metrics', []):
        metric = apply_scope(metric, evidence, documents, index, verify_citation)
        metric = guard_comparison(metric)
        citations = []
        for side in ('promise', 'delivery'):
            metric[side]['citations'] = [verify_citation(c, documents, index) for c in metric[side]['citations']]
            citations.extend(metric[side]['citations'])
        required_sides = ('promise',) if metric['delivery']['status'] == 'PENDING' else ('promise', 'delivery')
        if not all(metric[side]['citations'] for side in required_sides) or not all(c['verified'] for c in citations):
            metric['delivery']['status'] = 'UNVERIFIED'
            metric['delivery']['reason'] = 'One or more quotations could not be verified against the cited page.'
            metric['delivery'].pop('observation', None)
        metrics.append(metric)
    verified = sum(m['delivery']['status'] in ('BEAT', 'MET', 'MISSED', 'ABOVE_RANGE', 'BELOW_RANGE') for m in metrics)
    snapshot_path = doc_dir / 'snapshot.json'
    facts = json.loads(snapshot_path.read_text()).get('facts', []) if snapshot_path.exists() else []
    verified_facts = []
    for fact in facts:
        citation = verify_citation(fact, documents, index)
        if citation['verified']:
            verified_facts.append({'statement': fact['statement'], 'citation': citation})
    histories = guidance_history(json.loads((doc_dir / 'extracted_metrics.json').read_text()),
                                 documents, index, verify_citation)
    pending = sum(metric['delivery']['status'] == 'PENDING' for metric in metrics)
    observations = sum(bool(metric['delivery'].get('observation')) for metric in metrics)
    summary = f'{verified} verified delivery verdict{"s" if verified != 1 else ""}; {pending} pending targets; {len(histories)} guidance histories.'
    if observations:
        summary = f'{observations} numerical observations; ' + summary
    if not verified:
        summary += ' No complete, matched-period delivery verdict is established by this evidence set.'
    payload = {
        'business_snapshot': verified_facts,
        'symbol': symbol,
        'executive_summary': summary,
        'metrics': metrics,
        'guidance_history': histories,
        'coverage': {'transcripts': sum(m['doc_kind'] == 'earnings_call' for m in index),
                     'annual_reports': sum(m['doc_kind'] == 'annual_report' for m in index)},
    }
    brief_path = doc_dir / 'brief.json'
    if brief_path.exists():
        brief = json.loads(brief_path.read_text())
        payload['sections'] = brief.get('sections', [])
        payload['generated_at'] = brief.get('generated_at')
        payload['business_snapshot'] = next((section['facts'] for section in payload['sections'] if section['key'] == 'business'), [])
        payload['evidence'] = [fact for section in payload['sections'] if section['key'] != 'business' for fact in section['facts']]
        if brief.get('model_calls'):
            payload['mode'] = 'source_grounded'
    # Publish page extracts for source inspection, including newly ingested tickers.
    dest = PUBLIC_DATA_DIR / 'docs' / symbol
    dest.mkdir(parents=True, exist_ok=True)
    for name, pages in documents.items():
        (dest / name).write_text(json.dumps(pages))
    PUBLIC_PULL_DIR.mkdir(parents=True, exist_ok=True)
    path = PUBLIC_PULL_DIR / f'{symbol}.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(path)
    print(f'Published verified research: {path}')

if __name__ == '__main__':
    ground_data(sys.argv[1] if len(sys.argv) > 1 else 'INFY')
