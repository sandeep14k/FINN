"""Publish inspectable primary-source excerpts when model analysis is unavailable."""
import json
from urllib.parse import urlencode
import re
import shutil
from config import DATA_DIR, ROOT_DIR, PUBLIC_DATA_DIR
from snapshot import extractive_snapshot


def publish_evidence(symbol):
    directory = DATA_DIR / 'docs' / symbol
    sources_path = directory / 'sources.json'
    sources = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    evidence, annual, transcripts = [], [], 0
    dest = PUBLIC_DATA_DIR / 'docs' / symbol
    dest.mkdir(parents=True, exist_ok=True)
    files = [p for p in directory.glob('*.json') if p.name.startswith(('transcript_', 'ar_'))]
    for file in sorted(files):
        pages = json.loads(file.read_text())
        if not pages:
            continue
        shutil.copyfile(file, dest / file.name)
        is_report = file.name.startswith('ar_')
        if not is_report:
            transcripts += 1
        label = 'Annual report' if is_report else file.stem.removeprefix('transcript_').replace('_', ' ')
        excerpts = extractive_snapshot(pages)['facts'] if is_report else []
        if not is_report:
            for page in pages:
                for sentence in re.split(r'(?<=[.!?])\s+', ' '.join(page['text'].split())):
                    if 8 <= len(sentence.split()) <= 38 and re.search(r'guidance|operating margin|revenue growth|cash flow', sentence, re.I):
                        excerpts.append({'statement': sentence, 'quote': sentence, 'page': page['page']})
                        break
                if len(excerpts) == 2:
                    break
        for excerpt in excerpts:
            item = {'statement': excerpt['statement'], 'citation': {
                'document': label, 'page': excerpt['page'], 'quote': excerpt['quote'], 'verified': True,
                'source_url': sources.get(file.name),
                'source_path': '/api/source?' + urlencode({'symbol': symbol, 'file': file.name}),
            }}
            (annual if is_report else evidence).append(item)
    if not evidence and not annual:
        raise RuntimeError(f'No readable primary-source excerpts found for {symbol}')
    payload = {
        'symbol': symbol, 'mode': 'evidence_only',
        'executive_summary': 'Model analysis is unavailable. These are verbatim primary-source excerpts, not a management delivery verdict. No promise comparisons have been generated.',
        'coverage': {'transcripts': transcripts, 'annual_reports': sum(p.name.startswith('ar_') for p in files)},
        'business_snapshot': annual, 'evidence': evidence, 'metrics': [],
    }
    out = PUBLIC_DATA_DIR / 'pull' / f'{symbol}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix('.tmp')
    temporary.write_text(json.dumps(payload, indent=2))
    temporary.replace(out)
    from research_brief import publish_brief
    publish_brief(symbol, use_model=False)
    print(f'Published primary-source evidence for {symbol}; model analysis unavailable.')
