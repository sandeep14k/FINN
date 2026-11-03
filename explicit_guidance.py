"""Recover narrowly phrased percentage guidance directly from source text."""
import re
from financial_metrics import metric_key


def extract_explicit_guidance(pages, quarter):
    match = re.fullmatch(r'Q([1-4]) FY(\d{2})', quarter)
    if not match:
        return []
    found, seen = [], set()
    for page in pages:
        text = ' '.join(page['text'].split())
        for start in re.finditer(r'(?:our |the new )(?:(consolidated|standalone) )?(revenue growth|operating margin) guidance', text, re.I):
            tail = text[start.start():start.start() + 500]
            end = re.search(r'[.!?](?=\s|$)', tail)
            if not end:
                continue
            quote = tail[:end.end()]
            bounds = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:to|[-–])\s*(\d+(?:\.\d+)?)\s*%', quote)
            if not bounds or len(quote.split()) > 65:
                continue
            explicit_year = re.search(r"(?:financial year|FY)\s*['’]?\s*(20\d{2}|\d{2})\b", quote, re.I)
            if explicit_year:
                year = int(explicit_year[1]) % 100
            elif match[1] != '4' and not re.search(r'next year|coming year|next financial', quote, re.I):
                year = int(match[2])
            else:
                continue
            metric = start[2].lower()
            period = f'FY{year:02d}'
            identity = metric_key(metric), period
            if identity in seen:
                continue
            if metric == 'revenue growth' and 'constant currency' not in quote.lower():
                continue
            seen.add(identity)
            found.append({'metric': metric.title(), 'target_low': float(bounds[1]),
                          'target_high': float(bounds[2]), 'unit': '%', 'period_covered': period,
                          'basis': 'constant currency' if metric == 'revenue growth' else 'unknown',
                          'scope': (start[1] or 'unknown').lower(), 'quote': quote, 'page': page['page'],
                          'extraction_method': 'explicit_source_pattern',
                          'period_inferred_from_call': explicit_year is None})
    return found
