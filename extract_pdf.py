# extract_pdf.py
# Page-by-page text extraction with PyMuPDF. Transcripts: every page.
# Annual reports: only pages that score as MD&A / financial statements.
import json
import os
import re
import sys

try:
    import pymupdf  # new name
except ImportError:  # older installs
    import fitz as pymupdf

from config import DATA_DIR

AR_KEYWORDS = {
    # keyword -> weight. Curly quotes are normalised before matching.
    "management discussion": 3,
    "management's discussion": 3,
    "balance sheet": 3,
    "statement of profit and loss": 3,
    "cash flow statement": 3,
    "statement of cash flows": 3,
    "revenue from operations": 2,
    "total equity": 1,
    "ebitda": 1,
    "operating margin": 1,
    "outlook": 1,
}
AR_MIN_SCORE = 4


def _norm(s: str) -> str:
    return (s.replace("’", "'").replace("‘", "'")
             .replace("“", '"').replace("”", '"').lower())


def _ar_score(text: str) -> int:
    t = _norm(text)
    return sum(w for k, w in AR_KEYWORDS.items() if k in t)


def layout_text(page):
    """Reconstruct horizontal rows from PDF coordinates instead of column order."""
    words = page.get_text('words')
    rows = []
    for word in sorted(words, key=lambda item: ((item[1] + item[3]) / 2, item[0])):
        midpoint = (word[1] + word[3]) / 2
        matching = next((row for row in reversed(rows[-5:]) if abs(row['y'] - midpoint) <= 3), None)
        if matching is None:
            matching = {'y': midpoint, 'words': []}
            rows.append(matching)
        matching['words'].append(word)
    return '\n'.join('  '.join(word[4] for word in sorted(row['words'], key=lambda item: item[0])) for row in rows)


def extract_pdf_to_json(filepath: str, doc_name: str, doc_type: str,
                        out_path: str | None = None, delete_pdf: bool = True) -> str:
    print(f"Extracting {filepath} as {doc_type}...")
    doc = pymupdf.open(filepath)
    pages = []
    for i in range(len(doc)):
        text = doc[i].get_text("text").strip()
        if len(text) < 50:
            continue
        # Preserve business context and notes too. Downstream retrieval ranks pages;
        # discarding them here made business research impossible to recover later.
        pages.append({
            "document": doc_name,
            "page": i + 1,  # real PDF page number, used for citations
            "text": re.sub(r"\n{3,}", "\n\n", text),
            "layout_text": layout_text(doc[i]),
        })
    total = len(doc)
    doc.close()

    if not pages:
        raise ValueError('No readable pages found. The document may require OCR; it was not cached as usable evidence.')

    out_path = out_path or filepath.replace(".pdf", ".json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)
    if delete_pdf:
        os.remove(filepath)
    print(f"Kept {len(pages)}/{total} pages -> {out_path}")
    if not pages:
        print("WARNING: 0 pages kept. If this is a scanned PDF it has no text layer (needs OCR).")
    return out_path


if __name__ == "__main__":
    # Usage: python extract_pdf.py [path.pdf] [TRANSCRIPT|AR]
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        pdfs = [f for f in os.listdir(DATA_DIR) if f.endswith(".pdf")]
        if not pdfs:
            sys.exit("No PDF in data/. Run download_screener.py first.")
        path = os.path.join(DATA_DIR, pdfs[0])
    dtype = sys.argv[2] if len(sys.argv) > 2 else "TRANSCRIPT"
    extract_pdf_to_json(path, doc_name=os.path.basename(path), doc_type=dtype, delete_pdf=False)
