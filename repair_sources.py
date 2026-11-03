"""Recover legacy source URLs by exact saved document labels, never guessed URLs."""
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup
from config import DATA_DIR, normalize_text


def repair_sources(symbol):
    directory = DATA_DIR / 'docs' / symbol
    raw = DATA_DIR / 'raw' / f'screener_{symbol}.html'
    if not raw.exists():
        return
    soup = BeautifulSoup(raw.read_text(), 'html.parser')
    links = {}
    for anchor in soup.find_all('a', href=True):
        row = anchor.find_parent('li') or anchor.parent
        title = normalize_text(row.get_text(' ', strip=True))
        if 'transcript' in anchor.get_text().lower() or 'annual report' in anchor.get_text().lower():
            links[title] = anchor['href']
    path = directory / 'sources.json'
    sources = json.loads(path.read_text()) if path.exists() else {}
    for file in directory.glob('*.json'):
        content = json.loads(file.read_text())
        if not isinstance(content, list) or not content or 'text' not in content[0]:
            continue
        label = content[0].get('document', '').partition('|')[2].strip()
        if normalize_text(label) in links:
            sources[file.name] = links[normalize_text(label)]
    path.write_text(json.dumps(sources, indent=2))
    return sources


if __name__ == '__main__':
    for symbol in sys.argv[1:] or ['INFY']:
        print(symbol, len(repair_sources(symbol) or {}), 'source URLs recovered or retained')
