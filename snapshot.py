"""Extract a small business snapshot strictly from an annual report."""
import json
import re
import sys
from pydantic import BaseModel
from research_chunks import page_chunks
from config import ModelAPIError, DATA_DIR, cache_and_retry, AI_FAST_MODEL

class Fact(BaseModel):
    statement: str
    document: str
    page: int
    quote: str

class Snapshot(BaseModel):
    facts: list[Fact]

def extractive_snapshot(pages):
    facts = []
    for page in pages:
        text = ' '.join(page['text'].split())
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            if 8 <= len(sentence.split()) <= 38 and re.search(r'cash flow|business operations|debt.free|business segments|capital allocation', sentence, re.I):
                facts.append({'statement': sentence, 'document': 'Annual report', 'page': page['page'], 'quote': sentence})
                break
        if len(facts) == 3:
            break
    return {'facts': facts, 'mode': 'extractive'}

def extract_snapshot(symbol, extractive=False):
    directory = DATA_DIR / 'docs' / symbol
    index = json.loads((directory / 'index.json').read_text())
    reports = [item for item in index if item['doc_kind'] == 'annual_report']
    if not reports:
        (directory / 'snapshot.json').write_text('{"facts": []}')
        return
    pages = json.loads((directory / reports[0]['filename']).read_text())
    # Keep bounded primary-source context. Missing coverage is not filled from model memory.
    if extractive:
        result = extractive_snapshot(pages)
    else:
        facts = []
        try:
            for chunk in page_chunks(pages, relevant=True)[:3]:
                partial = cache_and_retry(AI_FAST_MODEL,
                    f'Annual report for {symbol}. Extract up to 2 concise facts about business segments, cash flow or leverage. Every statement must be directly supported by a verbatim quote under 40 words. Use document="Annual report". Omit unsupported claims.\n{chunk}',
                    Snapshot, 'Use only supplied primary-source text. No outside knowledge.')
                facts.extend(partial['facts'])
            result = {'facts': facts[:3]}
        except ModelAPIError as error:
            if error.code != 429:
                raise
            print('Model quota unavailable; using verbatim annual-report excerpts.')
            result = extractive_snapshot(pages)
    (directory / 'snapshot.json').write_text(json.dumps(result, indent=2))

if __name__ == '__main__':
    extract_snapshot(sys.argv[1] if len(sys.argv) > 1 else 'INFY', '--extractive' in sys.argv)
