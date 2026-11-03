# ingest_ticker.py
# Usage: python ingest_ticker.py INFY 5
# Downloads the latest N concall transcripts for ANY Screener symbol, one at a
# time, extracts text per page, and stores data/docs/<SYMBOL>/<n>_<slug>.json.
# Same code serves the demo set and unseen tickers.
import os
import json
import re
import sys
import time
import hashlib

from config import DATA_DIR
from download_screener import download_single_document, search_screener_documents
from extract_pdf import extract_pdf_to_json


def slug(s: str) -> str:
    s = re.sub(r"Announcement under Regulation 30 \(LODR\)-?", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40]


def ingest(symbol: str, n: int = 5):
    out_dir = os.path.join(DATA_DIR, "docs", symbol)
    os.makedirs(out_dir, exist_ok=True)

    docs = search_screener_documents(symbol)
    transcripts = [d for d in docs if d["type"] == "TRANSCRIPT"][:n]
    transcripts += [d for d in docs if d["type"] == "AR"][:1]
    print(f"\n{symbol}: ingesting {len(transcripts)} transcripts")

    source_path = os.path.join(out_dir, "sources.json")
    sources = json.load(open(source_path)) if os.path.exists(source_path) else {}
    ok = 0
    for idx, d in enumerate(transcripts):  # idx 0 = most recent
        existing = next((name for name, url in sources.items()
                         if url == d['url'] and os.path.exists(os.path.join(out_dir, name))), None)
        if existing:
            print('Cached:', existing)
            ok += 1
            continue
        name = f"{d['type'].lower()}_{slug(d['period'])}_{hashlib.sha256(d['url'].encode()).hexdigest()[:10]}"
        out_json = os.path.join(out_dir, name + ".json")
        if os.path.exists(out_json):
            print("Cached:", out_json)
            ok += 1
            continue
        try:
            pdf = download_single_document(d["url"], prefix=f"{symbol}_tmp")
            extract_pdf_to_json(pdf, doc_name=f"{symbol} | {d['period']}",
                                doc_type=d["type"], out_path=out_json)
            sources[os.path.basename(out_json)] = d['url']
            with open(source_path, 'w') as source_file:
                json.dump(sources, source_file, indent=2)
            ok += 1
        except Exception as e:
            print(f"SKIPPED {d['period']!r}: {e}")
        time.sleep(1)
    if not ok:
        raise RuntimeError(f"No usable primary documents found for {symbol}")
    print(f"\nDone: {ok}/{len(transcripts)} primary documents ready in {out_dir}")


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "INFY"
    cnt = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    ingest(sym, cnt)
