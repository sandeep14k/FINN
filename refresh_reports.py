"""Re-extract full annual-report text so business context is available to retrieval."""
import json
import sys
from config import DATA_DIR
from download_screener import download_single_document
from extract_pdf import extract_pdf_to_json


def refresh_report(symbol):
    directory = DATA_DIR / 'docs' / symbol
    sources = json.loads((directory / 'sources.json').read_text())
    for filename, url in sources.items():
        if not filename.startswith('ar_'):
            continue
        target = directory / filename
        old = json.loads(target.read_text()) if target.exists() else []
        name = old[0]['document'] if old else f'{symbol} | Annual report'
        pdf = download_single_document(url, prefix=f'{symbol}_annual_full')
        extract_pdf_to_json(pdf, name, 'AR', str(target))
        print(f'{symbol}: full annual report is ready.', flush=True)
        return


if __name__ == '__main__':
    for symbol in sys.argv[1:] or ['INFY']:
        try:
            refresh_report(symbol)
        except Exception as error:
            print(f'{symbol}: could not refresh report ({error}); prior text retained.', flush=True)
