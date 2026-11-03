"""Extract source-verifiable quarterly tables and incoming-leader profiles."""
import argparse
import calendar
import json
import re
from datetime import date
from typing import Literal
from pydantic import BaseModel
from config import DATA_DIR, ROOT_DIR, AI_FAST_MODEL, cache_and_retry, normalize_text
from download_screener import download_single_document
from extract_pdf import extract_pdf_to_json
from research_chunks import page_chunks
from financial_metrics import number_in_quotes


class ResultRow(BaseModel):
    metric: Literal['Revenue', 'EBITDA', 'PBT', 'PAT']
    current: float | None
    previous: float | None
    year_ago: float | None
    quote: str
    page: int


class Results(BaseModel):
    scope: Literal['consolidated', 'standalone', 'unknown']
    unit: str
    current_period: str
    previous_period: str
    year_ago_period: str
    header_quote: str
    header_page: int
    rows: list[ResultRow]


class Leader(BaseModel):
    name: str
    role: str
    effective_date: str
    change: Literal['appointment', 'resignation', 'retirement', 'other']
    background: str
    quote: str
    page: int
    background_quote: str
    background_page: int | None


class Management(BaseModel):
    people: list[Leader]


def person_key(name):
    return re.sub(r'^(?:mr|ms|mrs|dr|shri|smt)\.?\s+', '', normalize_text(name)).strip()


def clean_person(person, pages):
    person = dict(person)
    if re.search(r'superannuation|retirement|retiring', person['quote'], re.I):
        person['change'] = 'retirement'
    if person['background'] and not verified(person['background_quote'], person['background_page'], pages):
        person['background'] = ''
        person['background_quote'] = ''
        person['background_page'] = None
    if not person['background'] and person['change'] == 'appointment':
        # Recover one complete disclosed bio sentence when a model truncates a long annexure.
        for page in pages:
            text = ' '.join(page['text'].split())
            match = re.search(re.escape(person['name']) + r'\s+(?:is|has|holds|was)\b', text, re.I)
            if not match:
                continue
            tail = text[match.start():match.start() + 700]
            end = re.search(r'\.(?=\s|$)', tail[len(person['name']):])
            if end:
                sentence = tail[:len(person['name']) + end.end()]
                if 8 <= len(sentence.split()) <= 65:
                    person.update(background=sentence, background_quote=sentence, background_page=page['page'])
                    break
    return person


def verified(quote, page_number, pages):
    return bool(quote) and any(page['page'] == page_number and any(normalize_text(quote) in normalize_text(page.get(key, '')) for key in ('text', 'layout_text')) for page in pages)


def change_percent(current, prior):
    # Negative and zero comparison bases do not yield meaningful growth percentages.
    return round((current - prior) / prior * 100, 2) if current is not None and prior is not None and prior > 0 else None


def period_dates(current, previous, year_ago):
    try:
        now, prior, year = [date.fromisoformat(value) for value in (current, previous, year_ago)]
        if now.month not in (3, 6, 9, 12) or now.day != calendar.monthrange(now.year, now.month)[1]:
            return False
        month = now.month - 3 or 12
        expected = date(now.year - (now.month == 3), month, calendar.monthrange(now.year - (now.month == 3), month)[1])
        return prior == expected and year == now.replace(year=now.year - 1)
    except ValueError:
        return False


def date_in_text(value, text):
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return False
    text = re.sub(r'(\d)(?:st|nd|rd|th)\b', r'\1', text, flags=re.I)
    compact = re.sub(r'[^a-z0-9]', '', text.lower())
    return any(re.sub(r'[^a-z0-9]', '', day.strftime(pattern).lower()) in compact for pattern in
               ('%d.%m.%Y', '%d.%m.%y', '%d %B %Y', '%B %d %Y', '%d %b %Y', '%b %d %Y', '%d %b %y', '%b %d %y'))


def analyse(limit=6, refresh_layout=False):
    public = ROOT_DIR / 'finn-app/public/data'
    digest = json.loads((public / 'push_digest.json').read_text())
    target = DATA_DIR / 'filing_analysis.json'
    saved = json.loads(target.read_text()) if target.exists() else {}
    candidates = [item for item in digest if item['type'] in ('results', 'management_change') and item.get('source_url') and item['id'] not in saved]
    for item in candidates[:limit]:
        if item['id'] in saved:
            continue
        try:
            path = DATA_DIR / 'filings' / f"{item['id']}.json"
            path.parent.mkdir(exist_ok=True)
            if not path.exists() or (refresh_layout and item['type'] == 'results'):
                pdf = download_single_document(item['source_url'], prefix='material_filing')
                extract_pdf_to_json(pdf, item['headline'], 'TRANSCRIPT', str(path))
            pages = json.loads(path.read_text())
            enrichment = {}
            if item['type'] == 'results':
                def score(page):
                    text = ' '.join(page['text'].split())
                    return len(re.findall(r'revenue from operations|profit before tax|consolidated financial results', text, re.I)) * 4 - len(re.findall(r'auditor|review report|reviewed', text, re.I)) * 8
                selected = sorted(pages, key=lambda page: -score(page))[:2]
                selected = [{**page, 'text': page.get('layout_text', page['text'])} for page in selected]
                rows, metadata = [], None
                for chunk in page_chunks(selected)[:2]:
                    result = cache_and_retry(AI_FAST_MODEL,
                        'Read this actual results filing. Extract the QUARTERLY (never half-year/YTD) Revenue from operations, EBITDA if explicitly disclosed, PBT after exceptional items, and PAT after share of associates but before attribution to owners/non-controlling interests. Prefer consolidated results. '
                        'Use three quarter-end dates YYYY-MM-DD: current, immediately previous quarter, same quarter last year. All amounts must have the same scope and unit. '
                        'Do not calculate EBITDA. If absent leave its values null. header_quote must be verbatim with scope, quarter/date headings and units; retain page. '
                        'Each row quote must be verbatim and contain all extracted row values. Do not invent or repair numbers.\n' + chunk,
                        Results, 'Extract only the supplied company filing; no external financial knowledge.')
                    if result['scope'] == 'unknown' or not period_dates(result['current_period'], result['previous_period'], result['year_ago_period']):
                        continue
                    if not verified(result['header_quote'], result['header_page'], pages):
                        continue
                    header_page = next(page.get('layout_text', page['text']) for page in pages if page['page'] == result['header_page'])
                    if not all(date_in_text(result[key], header_page) for key in ('current_period', 'previous_period', 'year_ago_period')):
                        continue
                    identity = tuple(result[key] for key in ('scope', 'unit', 'current_period', 'previous_period', 'year_ago_period'))
                    if metadata and identity != tuple(metadata[key] for key in ('scope', 'unit', 'current_period', 'previous_period', 'year_ago_period')):
                        continue
                    for row in result['rows']:
                        values = [row[key] for key in ('current', 'previous', 'year_ago')]
                        if not any(value is not None for value in values) or not verified(row['quote'], row['page'], pages):
                            continue
                        if not all(number_in_quotes(value, [row]) for value in values if value is not None):
                            continue
                        if any(existing['metric'] == row['metric'] for existing in rows):
                            continue
                        rows.append({**row, 'qoq': change_percent(row['current'], row['previous']), 'yoy': change_percent(row['current'], row['year_ago'])})
                    if rows and metadata is None:
                        metadata = {key: result[key] for key in ('scope', 'unit', 'current_period', 'previous_period', 'year_ago_period', 'header_quote', 'header_page')}
                if metadata and rows:
                    enrichment['results'] = {**metadata, 'rows': rows}
            else:
                selected = sorted(pages, key=lambda page: -len(re.findall(r'brief profile|experience|qualification|appointment|resignation|expertise', page['text'], re.I)))[:3]
                people = []
                for chunk in page_chunks(selected)[:2]:
                    result = cache_and_retry(AI_FAST_MODEL,
                        'Extract people joining or leaving management. Name, role, effective date, change type. '
                        'For incoming people add a short professional background ONLY if disclosed here, with a separate verbatim quote and page. '
                        'The main quote must establish the name and role. Use empty strings/null for unknown fields, never outside knowledge. '
                        'Return at most 2 people, exact quotes and real page numbers.\n' + chunk,
                        Management, 'Use only supplied primary-source disclosures.')
                    for person in result['people']:
                        if not verified(person['quote'], person['page'], pages):
                            continue
                        page_text = next(page['text'] for page in pages if page['page'] == person['page'])
                        if normalize_text(person['name']) not in normalize_text(page_text) or normalize_text(person['role']) not in normalize_text(page_text):
                            continue
                        person = clean_person(person, pages)
                        if person_key(person['name']) not in [person_key(entry['name']) for entry in people]:
                            people.append(person)
                if people:
                    enrichment['management'] = people
            if enrichment:
                saved[item['id']] = enrichment
                target.write_text(json.dumps(saved, indent=2))
                print(f"{item['ticker']}: verified {', '.join(enrichment)} enrichment.", flush=True)
            else:
                print(f"{item['ticker']}: no fully supported enrichment; original filing remains available.", flush=True)
        except Exception as error:
            print(f"{item['ticker']}: enrichment unavailable ({type(error).__name__}: {str(error)[:400]}).", flush=True)
    from generate_push import generate_digest
    generate_digest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=6)
    parser.add_argument('--refresh-layout', action='store_true')
    arguments = parser.parse_args()
    analyse(max(1, min(12, arguments.limit)), arguments.refresh_layout)
