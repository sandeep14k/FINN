# download_screener.py
# Lists annual-report + concall-transcript links for a Screener ticker and
# downloads ONE file at a time. Does not rely on guessed container ids.
import hashlib
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

from config import DATA_DIR

RAW_DIR = os.path.join(DATA_DIR, "raw")
os.makedirs(RAW_DIR, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PAGE_HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}


def _get_page(symbol: str):
    """Try consolidated first, then standalone. Returns (html, url) or (None, None)."""
    for suffix in ("consolidated/", ""):
        url = f"https://www.screener.in/company/{symbol}/{suffix}"
        r = requests.get(url, headers=PAGE_HEADERS, timeout=20)
        print(f"GET {url} -> HTTP {r.status_code}, {len(r.text)} chars")
        if r.status_code == 200:
            # Save raw HTML so we can inspect it if parsing finds nothing.
            with open(os.path.join(RAW_DIR, f"screener_{symbol}.html"), "w", encoding="utf-8") as f:
                f.write(r.text)
            yield r.text, url
        time.sleep(1)


def _classify(text: str):
    t = text.lower()
    if "transcript" in t:
        return "TRANSCRIPT"
    if "financial year" in t or "annual report" in t:
        return "AR"
    return None


def search_screener_documents(symbol: str):
    """Return [{type, title, period, url}] by scanning EVERY <a> on the page."""
    for html, page_url in _get_page(symbol):
        soup = BeautifulSoup(html, "html.parser")
        print("Page title:", soup.title.get_text(strip=True) if soup.title else None)

        docs, seen = [], set()
        for a in soup.find_all("a", href=True):
            title = a.get_text(" ", strip=True)
            kind = _classify(title)
            if not kind:
                continue
            href = a["href"]
            if href.startswith("/"):
                href = "https://www.screener.in" + href
            if href in seen:
                continue
            seen.add(href)

            # The quarter/date usually sits in the surrounding row, not the link text.
            row = a.find_parent("li") or a.parent
            period = re.sub(r"\s+", " ", row.get_text(" ", strip=True))[:80] if row else ""
            docs.append({"type": kind, "title": title, "period": period, "url": href})

        if docs:
            return docs
        print("No matching links on this page variant; trying the next one...")

    # Nothing found: help debug.
    print("\nZERO documents found. Open data/raw/screener_%s.html and search for "
          "'Transcript'. If it is missing, Screener may be showing a login/bot page." % symbol)
    return []


def download_single_document(url: str, prefix: str = "doc", retries: int = 2) -> str:
    """Download one PDF to disk. Cached by URL hash. Verifies it is really a PDF."""
    name = f"{prefix}_{hashlib.md5(url.encode()).hexdigest()[:10]}.pdf"
    path = os.path.join(DATA_DIR, name)
    if os.path.exists(path):
        print("Cached:", path)
        return path

    headers = {
        "User-Agent": UA,
        "Referer": "https://www.bseindia.com/",
        "Accept": "application/pdf,*/*",
    }
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=60, stream=True)
            r.raise_for_status()
            first = next(r.iter_content(chunk_size=8192), b"")
            if not first.startswith(b"%PDF"):
                raise ValueError(f"Not a PDF (starts with {first[:30]!r})")
            with open(path + ".part", "wb") as f:
                f.write(first)
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            os.replace(path + ".part", path)
            print("Saved:", path)
            return path
        except Exception as e:
            last_err = e
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    raise RuntimeError(f"Download failed for {url}: {last_err}")


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "INFY"
    docs = search_screener_documents(symbol)
    print(f"\nFound {len(docs)} documents for {symbol}")
    for d in docs[:12]:
        print(f"  [{d['type']}] {d['period']!r} -> {d['url']}")

    transcripts = [d for d in docs if d["type"] == "TRANSCRIPT"]
    if transcripts:
        try:
            download_single_document(transcripts[0]["url"], prefix=f"{symbol}_transcript")
        except Exception as e:
            print("Download test failed:", e)