import json
import sys
import re
from pydantic import BaseModel, Field
from research_chunks import page_chunks, unique_items, select_chunks
from typing import List, Optional, Literal
from dotenv import load_dotenv
from config import cache_and_retry, AI_FAST_MODEL, DATA_DIR
from explicit_guidance import extract_explicit_guidance
from financial_metrics import metric_key

load_dotenv()

class GuidanceItem(BaseModel):
    metric: str
    target_low: Optional[float]
    target_high: Optional[float]
    unit: str
    period_covered: str
    basis: str = Field(description='Measurement basis, e.g. constant currency, reported, adjusted. Use unknown when not stated; currency alone is not a growth or margin basis.')
    scope: Literal['consolidated', 'standalone', 'unknown']
    quote: str
    page: int

class ActualItem(BaseModel):
    metric: str
    value: float
    unit: str
    period: str
    basis: str = Field(description='Measurement basis, e.g. constant currency, reported, adjusted. Use unknown when not stated; currency alone is not a growth or margin basis.')
    scope: Literal['consolidated', 'standalone', 'unknown']
    quote: str
    page: int

class ExtractionResult(BaseModel):
    forward_looking_guidance: List[GuidanceItem]
    reported_actuals: List[ActualItem]


def complete_year_actuals(pages, quarter):
    """A narrow pass prevents annual outcomes being crowded out by quarterly KPIs."""
    candidates = [page for page in pages if re.search(r'full.year', page['text'], re.I)
                  and re.search(r'growth|margin', page['text'], re.I)]
    actuals = []
    for chunk in page_chunks(candidates[:2], relevant=True)[:2]:
        result = cache_and_retry(AI_FAST_MODEL,
            'Extract ONLY completed full-year revenue growth and operating margin actuals. '
            'Do not extract guidance, quarterly results, YTD or other KPIs. '
            'Use annual period FYxx, not the call quarter. Basis must distinguish constant-currency '
            'versus reported growth, and adjusted versus reported operating margin. USD is a currency, '
            'not an accounting basis for a percentage margin. Quotes must include enough surrounding '
            'words to establish the period and measurement basis. Use unknown if absent. '
            'Return no forward-looking guidance. This is the ' + quarter + ' call.\n' + chunk,
            ExtractionResult, 'Extract only explicitly supplied primary-source financial results.')
        actuals.extend(result['reported_actuals'])
    return unique_items(actuals)

def extract_guidance(symbol: str):
    doc_dir = DATA_DIR / "docs" / symbol
    index_path = doc_dir / "index.json"
    
    if not index_path.exists():
        print(f"Index not found for {symbol}. Run label_docs.py first.")
        return
        
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)
        
    extracted_data = []
    
    system_prompt = (
        "You are an expert financial analyst. Extract EXPLICIT numerical forward-looking guidance "
        "targets and historical reported actuals. Never invent numbers. Quotes must be <40 words and verbatim."
    )
    
    for doc_meta in index:
        # STRICT FILTER: Protect downstream processes by ignoring bad files here.
        if doc_meta.get("doc_kind") != "earnings_call" or doc_meta.get("is_duplicate"):
            print(f"Skipping {doc_meta['filename']} (kind: {doc_meta.get('doc_kind')}, duplicate: {doc_meta.get('is_duplicate')})")
            continue
            
        file_path = doc_dir / doc_meta["filename"]
        with open(file_path, 'r', encoding='utf-8') as f:
            pages = json.load(f)
            
        chunks = page_chunks(pages, relevant=True)
        merged = {"forward_looking_guidance": [], "reported_actuals": []}
        print(f"Extracting selected evidence from {doc_meta['filename']} ({min(6, len(chunks))}/{len(chunks)} chunks)...", flush=True)
        for position, chunk in enumerate(select_chunks(chunks), 1):
            print(f'  Evidence chunk {position}/{min(6, len(chunks))}', flush=True)
            prompt = (f"Extract up to 3 explicit guidance targets and 4 reported actuals for {doc_meta['quarter']}. "
                      "Use only this excerpt. Omit unsupported items. Retain the real PAGE number. "
                      "State currency/accounting basis and consolidated/standalone scope explicitly; use unknown when absent. "
                      f"Do not treat an annual target as a quarterly target.\n{chunk}")
            result = cache_and_retry(model=AI_FAST_MODEL, prompt=prompt, schema=ExtractionResult, system=system_prompt)
            for key in merged:
                merged[key].extend(result[key])
        result = {key: unique_items(items) for key, items in merged.items()}
        explicit = extract_explicit_guidance(pages, doc_meta['quarter'])
        explicit_keys = {(metric_key(item['metric']), item['period_covered']) for item in explicit}
        result['forward_looking_guidance'] = explicit + [item for item in result['forward_looking_guidance']
            if (metric_key(item['metric']), item['period_covered']) not in explicit_keys]
        if doc_meta['quarter'].startswith('Q4 '):
            annual = complete_year_actuals(pages, doc_meta['quarter'])
            if annual:
                periods = {item['period'] for item in annual}
                result['reported_actuals'] = [item for item in result['reported_actuals'] if item['period'] not in periods] + annual

        extracted_data.append({
            "document": doc_meta["quarter"],
            "filename": doc_meta["filename"],
            "chunks_reviewed": min(6, len(chunks)),
            "chunks_available": len(chunks),
            "guidance": result["forward_looking_guidance"],
            "actuals": result["reported_actuals"]
        })
        
    if not extracted_data:
        raise RuntimeError("No earnings-call evidence available; refusing to generate comparisons.")
    out_path = doc_dir / "extracted_metrics.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=2)
        
    print(f"Extraction complete for {symbol}. Saved to {out_path}.")

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'INFY'
    if '--full-year-only' in sys.argv:
        directory = DATA_DIR / 'docs' / symbol
        extracted = json.loads((directory / 'extracted_metrics.json').read_text())
        for item in extracted:
            if item['document'].startswith('Q4 '):
                annual = complete_year_actuals(json.loads((directory / item['filename']).read_text()), item['document'])
                if annual:
                    periods = {actual['period'] for actual in annual}
                    item['actuals'] = [actual for actual in item['actuals'] if actual['period'] not in periods] + annual
        (directory / 'extracted_metrics.json').write_text(json.dumps(extracted, indent=2))
    else:
        extract_guidance(symbol)
