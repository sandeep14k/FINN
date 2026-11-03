import json
import sys
import re
from pydantic import BaseModel
from typing import Optional, Literal
from dotenv import load_dotenv
from config import cache_and_retry, AI_FAST_MODEL, DATA_DIR

load_dotenv()

class DocumentLabel(BaseModel):
    quarter: str
    call_date: str
    doc_kind: Literal["earnings_call", "other"]
    is_duplicate_of: Optional[str]

def parse_quarter(q_str: str) -> tuple:
    try:
        parts = q_str.replace("FY", "").split()
        return (int(parts[1]), int(parts[0].replace("Q", "")))
    except:
        return (0, 0)

def explicit_quarter(text):
    """Prefer an explicit quarter-ended disclosure over a model's inferred period."""
    match = re.search(r'quarter\s+ended\s+(March|June|September|December)\s+(\d{1,2}),?\s+(20\d{2})', text, re.I)
    if not match:
        return None
    month, year = match[1].lower(), int(match[3])
    quarter = {'june': 1, 'september': 2, 'december': 3, 'march': 4}[month]
    return f'Q{quarter} FY{(year if quarter == 4 else year + 1) % 100:02d}'

def label_documents(symbol: str):
    doc_dir = DATA_DIR / "docs" / symbol
    if not doc_dir.exists():
        print(f"Directory {doc_dir} not found.")
        return

    # Make sure this line has exactly 4 spaces at the start, no tabs!
    files = sorted([f for f in doc_dir.glob("*.json") if f.name not in ["index.json", "extracted_metrics.json", "comparison.json", "snapshot.json", "sources.json", "brief.json"]])
    index = []
    seen_quarters = {}
    
    system_prompt = (
        "Classify financial transcripts. Output 'doc_kind' as 'earnings_call' ONLY IF it is a standard "
        "quarterly or annual earnings call / press conference. If it is an Investor Day, AI Day, ad-hoc presentation, "
        "or press release, output 'other'."
    )
    
    for file_path in files:
        if file_path.name.startswith("ar_"):
            index.append({"filename": file_path.name, "quarter": "Annual report", "call_date": "", "doc_kind": "annual_report", "is_duplicate": False})
            continue
        with open(file_path, 'r', encoding='utf-8') as f:
            pages = json.load(f)
            
        intro_text = "\n\n".join([f"Page {p['page']}: {p['text']}" for p in pages[:3]])[:2500]
        
        prompt = (
            "Analyze this cover letter/intro. Return the quarter ('Q2 FY27'), call date, document kind, "
            "and whether this is a duplicate of another transcript.\n"
            f"Content:\n{intro_text}"
        )
        
        result = cache_and_retry(model=AI_FAST_MODEL, prompt=prompt, schema=DocumentLabel, system=system_prompt)
        q_label = explicit_quarter(intro_text) or result["quarter"]
        
        if result["doc_kind"] == "earnings_call":
            if q_label in seen_quarters and result["is_duplicate_of"] is None:
                result["is_duplicate_of"] = seen_quarters[q_label]
            if not result["is_duplicate_of"]:
                seen_quarters[q_label] = file_path.name
                
        index.append({
            "filename": file_path.name,
            "quarter": q_label,
            "call_date": result["call_date"],
            "doc_kind": result["doc_kind"],
            "is_duplicate": bool(result["is_duplicate_of"])
        })
            
    index.sort(key=lambda x: parse_quarter(x["quarter"]))
    
    with open(doc_dir / "index.json", 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)
        
    print(f"Labeled {len(index)} documents for {symbol}.")

if __name__ == "__main__":
    label_documents(sys.argv[1] if len(sys.argv) > 1 else "INFY")
