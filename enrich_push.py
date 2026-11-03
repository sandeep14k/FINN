"""Attach short, verbatim filing previews without spending model tokens."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from config import DATA_DIR, ROOT_DIR
from download_screener import download_single_document
from extract_pdf import extract_pdf_to_json


def choose_excerpt(pages):
    candidates = []
    for page in pages[:5]:
        text = ' '.join(page['text'].split())
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            words = sentence.split()
            if not 10 <= len(words) <= 65:
                continue
            score = len(re.findall(r'resign|appoint|acquisit|merger|revenue|profit|capacity|investment|expansion|order|penalty|crore|million|billion', sentence, re.I))
            score += 2 if re.search(r'\d.*(?:crore|million|billion|%)', sentence, re.I) else 0
            if score:
                candidates.append((score, -page['page'], sentence, page['page']))
    if not candidates:
        return None
    _, _, quote, page = max(candidates)
    return {'quote': quote, 'page': page, 'verified': True}


def enrich(limit=5):
    digest_path = ROOT_DIR / 'finn-app/public/data/push_digest.json'
    digest = json.loads(digest_path.read_text())
    evidence_path = DATA_DIR / 'filing_evidence.json'
    evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
    directory = DATA_DIR / 'filings'
    directory.mkdir(parents=True, exist_ok=True)
    selected = sorted((item for item in digest if item['priority'] >= 4 and item.get('source_url')),
                      key=lambda item: (item.get('timestamp') or '', item['priority']), reverse=True)[:limit]
    for item in selected:
        url = item['source_url']
        host = urlparse(url).hostname or ''
        if not (host.endswith('.bseindia.com') or host.endswith('.nseindia.com')):
            continue
        if item['id'] in evidence:
            continue
        try:
            output = directory / f"{item['id']}.json"
            if not output.exists():
                pdf = download_single_document(url, prefix='filing')
                extract_pdf_to_json(pdf, item['headline'], 'TRANSCRIPT', str(output))
            excerpt = choose_excerpt(json.loads(output.read_text()))
            if excerpt:
                evidence[item['id']] = {**excerpt, 'source_url': url}
                evidence_path.write_text(json.dumps(evidence, indent=2))
                print(f"Added filing evidence: {item['ticker']} · page {excerpt['page']}", flush=True)
        except Exception as error:
            print(f"Skipped {item['ticker']}: {error}", flush=True)
    from generate_push import generate_digest
    generate_digest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=5)
    enrich(max(1, min(20, parser.parse_args().limit)))
