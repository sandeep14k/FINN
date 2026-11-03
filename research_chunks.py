"""Bound source excerpts while retaining real PDF page numbers."""
import re

FINANCIAL_TERMS = re.compile(r'guidance|revenue|margin|cash flow|profit|ebitda|capex|growth|debt', re.I)


def page_chunks(pages, max_chars=4500, relevant=False):
    if max_chars < 500:
        raise ValueError('Chunk size must be at least 500 characters.')
    chunks, current = [], ''
    for page in pages:
        text = page['text']
        regions = [(0, len(text))]
        if relevant:
            regions = []
            for match in FINANCIAL_TERMS.finditer(text):
                left, right = max(0, match.start() - 350), min(len(text), match.end() + 500)
                if regions and left <= regions[-1][1]:
                    regions[-1] = (regions[-1][0], max(right, regions[-1][1]))
                else:
                    regions.append((left, right))
        for left, right in regions:
            marker = f"--- PAGE {page['page']} ---\n"
            while left < right:
                # Leave room for page marker and the separator in the packed chunk.
                end = min(right, left + max_chars - len(marker) - 2)
                if end < right:
                    boundary = text.rfind(' ', left + (end-left)//2, end)
                    if boundary > left:
                        end = boundary
                fragment = marker + text[left:end]
                if current and len(current) + len(fragment) + 2 > max_chars:
                    chunks.append(current)
                    current = ''
                current += ('\n\n' if current else '') + fragment
                if end == right:
                    break
                left = max(left + 1, end - 180)  # Preserve sentences at boundaries.
    if current:
        chunks.append(current)
    return chunks


def unique_items(items):
    seen, result = set(), []
    for item in items:
        key = (item.get('metric'), item.get('page'), ' '.join(item.get('quote', '').split()))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def select_chunks(chunks, limit=6):
    """Prioritise explicit outlook while reserving coverage across the document."""
    if len(chunks) <= limit:
        return chunks
    pattern = re.compile(r'guidance|outlook|we expect|we anticipate|we target|full.year', re.I)
    ranked = sorted(range(len(chunks)), key=lambda i: (-len(pattern.findall(chunks[i])), i))
    chosen = set(ranked[:max(1, limit - 2)])
    for position in (0, len(chunks) - 1, len(chunks) // 2, *ranked):
        if len(chosen) >= limit:
            break
        chosen.add(position)
    return [chunks[i] for i in sorted(chosen)]
