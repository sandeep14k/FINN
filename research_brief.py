"""Produce concise research sections with page-verified primary-source evidence."""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from pydantic import BaseModel
from bs4 import BeautifulSoup
from config import DATA_DIR, ROOT_DIR, PUBLIC_DATA_DIR, AI_FAST_MODEL, cache_and_retry, normalize_text
from evidence_quality import SECTION_TITLES, TERMS, ranked_pages, business_pages, business_descriptions, select_facts, useful_statement, content_tokens, repeats_earlier
from research_chunks import page_chunks
from financial_metrics import number_in_quotes


class Insight(BaseModel):
    section: Literal['business', 'financials', 'trajectory', 'balance_sheet', 'cash_quality', 'narrative', 'guidance', 'bull_bear']
    statement: str
    quote: str
    page: int


class Brief(BaseModel):
    insights: list[Insight]


def issuer_aliases(symbol):
    raw = DATA_DIR / 'raw' / f'screener_{symbol}.html'
    if not raw.exists():
        return [symbol]
    heading = BeautifulSoup(raw.read_text(), 'html.parser').find('h1')
    name = re.sub(r'\s+(?:Ltd\.?|Limited)$', '', heading.get_text(' ', strip=True), flags=re.I) if heading else symbol
    return [name, symbol]


def build_sections(symbol, use_model=False):
    directory = DATA_DIR / 'docs' / symbol
    sources_path = directory / 'sources.json'
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    files = []
    for file in directory.glob('*.json'):
        if file.name in ('sources.json', 'index.json', 'comparison.json', 'extracted_metrics.json', 'snapshot.json', 'brief.json'):
            continue
        pages = json.loads(file.read_text())
        if isinstance(pages, list) and pages and isinstance(pages[0], dict) and 'text' in pages[0]:
            files.append((file, pages))
    grouped = {key: [] for key in SECTION_TITLES}
    section_tokens = {key: [] for key in SECTION_TITLES}
    seen = set()
    destination = PUBLIC_DATA_DIR / 'docs' / symbol
    destination.mkdir(parents=True, exist_ok=True)
    model_calls = 0
    def chronology(item):
        text = item[1][0]['text'][:2000]
        match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})', text, re.I)
        if match:
            return int(match[3]) * 10000 + datetime.strptime(match[1].title(), '%B').month * 100 + int(match[2])
        return 0
    for file, pages in sorted(files, key=lambda item: (not item[0].name.startswith('ar_'), -chronology(item))):
        report = file.name.startswith('ar_')
        label = 'Annual report' if report else pages[0].get('document', file.stem).partition('|')[2].strip() or file.stem
        def retain(section, statement, quote, page_number):
            page = next((page for page in pages if page['page'] == page_number), None)
            if not page or not quote or normalize_text(quote) not in normalize_text(page['text']):
                return
            if not useful_statement(statement) or '?' in quote:
                return
            if section == 'guidance' and not re.search(TERMS['guidance'], statement + ' ' + quote, re.I):
                return
            if section == 'bull_bear' and not re.search(TERMS['bull_bear'], statement + ' ' + quote, re.I):
                return
            # A summary may not introduce numerical facts absent from its supporting quote.
            numbers = re.findall(r'\d+(?:\.\d+)?', statement.replace(',', ''))
            if any(not number_in_quotes(float(number), [{'quote': quote}]) for number in numbers):
                return
            identity = normalize_text(quote)
            if identity in seen or len(grouped[section]) >= 2:
                return
            if repeats_earlier(statement, section_tokens[section]):
                return
            seen.add(identity)
            section_tokens[section].append(content_tokens(statement))
            grouped[section].append({'statement': statement, 'citation': {
                'document': label, 'page': page_number, 'quote': quote, 'verified': True,
                'source_url': sources.get(file.name),
                'source_path': '/api/source?' + urlencode({'symbol': symbol, 'file': file.name}),
            }})
        if report:
            for fact in business_descriptions(pages, issuer_aliases(symbol)):
                retain('business', fact['statement'], fact['quote'], fact['page'])
        if use_model and model_calls < 4:
            chunks = ([page_chunks(business_pages(pages))[0]] + page_chunks(ranked_pages(pages, report=True))[:1]) if report else page_chunks(ranked_pages(pages))
            for chunk in chunks[:2 if report else 1]:
                if model_calls >= 4:
                    break
                try:
                    result = cache_and_retry(AI_FAST_MODEL,
                        f'Company {symbol}; document {label}. Extract up to 5 useful investor research facts. '
                        'Choose the fitting section: business (products, segments, revenue mix), financials (headline numbers), '
                        'trajectory (comparable growth), balance_sheet (debt, liquidity, working capital), cash_quality '
                        '(operating cash, cash conversion), narrative (specific management claims), guidance (explicit targets), '
                        'bull_bear (specific opportunities or risks). Use only supplied text. No analyst questions, '
                        'accounting-policy definitions, boilerplate, duplicate facts or incomplete sentences. '
                        'Statements must be complete sentences of 10–45 words. Include a verbatim supporting quote '
                        'and the actual PAGE number. Do not calculate ratios or infer unspecified reporting periods.\n' + chunk,
                        Brief, 'You extract company-specific research from primary sources. No outside knowledge.')
                    model_calls += 1
                    for fact in result['insights']:
                        retain(fact['section'], fact['statement'], fact['quote'], fact['page'])
                except Exception as error:
                    print(f'Model brief unavailable: {type(error).__name__}; retaining verified source facts.', flush=True)
                    use_model = False
                    break
        for section in SECTION_TITLES:
            if section == 'narrative':
                continue
            for fact in select_facts(pages, limit=2, section=section):
                retain(section, fact['statement'], fact['quote'], fact['page'])
        (destination / file.name).write_text(json.dumps(pages))
    sections = [{'key': key, 'title': title, 'facts': grouped[key]} for key, title in SECTION_TITLES.items() if grouped[key]]
    result = {'sections': sections, 'generated_at': datetime.now(timezone.utc).isoformat(), 'model_calls': model_calls}
    (directory / 'brief.json').write_text(json.dumps(result, indent=2))
    print(f'{symbol}: {sum(len(section["facts"]) for section in sections)} verified facts across {len(sections)} research sections.', flush=True)
    return result


def publish_brief(symbol, use_model=False):
    result = build_sections(symbol, use_model=use_model)
    output = PUBLIC_DATA_DIR / 'pull' / f'{symbol}.json'
    payload = json.loads(output.read_text()) if output.exists() else {'symbol': symbol, 'metrics': []}
    payload['sections'] = result['sections']
    payload['generated_at'] = result['generated_at']
    business = next((section['facts'] for section in result['sections'] if section['key'] == 'business'), [])
    payload['business_snapshot'] = business
    evidence, seen = [], set()
    for section in result['sections']:
        if section['key'] == 'business':
            continue
        for fact in section['facts']:
            key = normalize_text(fact['citation']['quote'])
            if key not in seen:
                evidence.append(fact)
                seen.add(key)
    payload['evidence'] = evidence
    if result['model_calls']:
        payload['mode'] = 'source_grounded'
    if not payload.get('metrics'):
        payload['executive_summary'] = f'{len(result["sections"])} research sections grounded in company reports and earnings calls. No complete promise-to-outcome verdict has been established.'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2))
    temporary.replace(output)


if __name__ == '__main__':
    for symbol in [arg for arg in sys.argv[1:] if not arg.startswith('--')] or ['INFY']:
        publish_brief(symbol, '--model' in sys.argv)
