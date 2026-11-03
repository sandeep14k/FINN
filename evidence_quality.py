"""Select useful, complete primary-source statements rather than keyword noise."""
import re
from config import normalize_text

SECTION_TITLES = {
    'business': 'The business, in context', 'financials': 'The financial picture',
    'trajectory': 'Direction of travel', 'balance_sheet': 'Balance-sheet watch',
    'cash_quality': 'Do earnings turn into cash?', 'narrative': 'Management’s narrative',
    'guidance': 'What management expects', 'bull_bear': 'Opportunity & risk',
}
BOILERPLATE = re.compile(r'defined as|fair value|hedging reserve|accounting polic|recognis(?:ed|ation)|recogniz(?:ed|ation)|solely payments|pass.through arrangement|estimated cash flows|flows.*segregated|forward.looking statements|safe.harbour|disclaimer|all rights reserved|guidance note|conducted our audit|terms of reference|committee charter|risk management policy|statutory reports|notes to the.*financial|material identified issue|indicate whether|sustainability framework|basis historical trend|the following table|financial implications of|annual report.{0,20}\d|attendance.*meetings|global vice president|best regards|yours sincerely|yours truly', re.I)
IRRELEVANT = re.compile(r'childcare|micro.donations|feeding india|lake rejuvenation|freshwater|emissions|SBTi|BRSR|female.*headcount|women employees|dedicated platforms|employee resource|diversity and inclusion|corporate social responsibility|\bCSR\b|biodiversity|sustainability|\bIMF\b|global GDP|accounting standards?|Ind AS \d|so there are always|founded|began its operations|non.GAAP financial measures|external document|copyright|vulnerabilit', re.I)
QUESTION = re.compile(r'\?|\b(?:you|your|could you|can you|would you|my question|first question|next question|last question|one question|thank you|thanks for|congratulations)\b', re.I)
TERMS = {
    'business': r'\b(?:provides?|manufactur\w*|operates?|business segments?|revenue mix|our clients|our services|our products|core market)\b',
    'financials': r'\b(?:revenue|profit|PAT|EBITDA|operating margin)\b',
    'trajectory': r'\b(?:grew|growth|declined|increased|decreased|year.on.year|sequentially)\b',
    'balance_sheet': r'\b(?:net debt|debt.to|debt.free|working capital|liquidity|cash and investments|DSO|receivables)\b',
    'cash_quality': r'\b(?:free cash flow|operating cash flow|cash conversion|cash from operations|cash generation)\b',
    'guidance': r'\b(?:guidance|we expect|we anticipate|we target|we forecast)\b',
    'bull_bear': r'\b(?:headwinds|tailwinds|competitive intensity|demand uncertainty|customer concentration|pricing pressure|market demand|supply.chain disruption|cyber.attack)\b',
}


def useful_statement(text):
    words = text.split()
    return (10 <= len(words) <= 45 and bool(re.search(r'[.!]$', text))
            and not QUESTION.search(text) and not BOILERPLATE.search(text)
            and not re.search(r'key audit matter|auditor.s response|revenue recognition|items that will not be reclassified|expected credit loss|computation of ECL|Ind.AS\s*\d|supplier finance arrangements|it basically|on the back of this|we expect the next.*whether any of this|we believe this growth', text, re.I)
            and not IRRELEVANT.search(text)
            and not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\uf000-\uf8ff]', text)
            and text[0].isupper()
            and len(re.findall(r'\d+(?:\.\d+)?', text)) <= 7
            and not re.search(r'\b(?:to|and|of|from|the|at|in)\s*[.!]?$', text, re.I))


STOPWORDS = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'was', 'were', 'has', 'have', 'had', 'its',
             'our', 'their', 'into', 'than', 'then', 'also', 'which', 'have', 'been', 'are', 'not', 'but', 'per',
             'net', 'year', 'years', 'company', 'group', 'said', 'will', 'would', 'over', 'more', 'about'}


def content_tokens(text):
    return {word for word in re.findall(r'[a-z0-9]+', text.lower()) if len(word) > 2 and word not in STOPWORDS}


def repeats_earlier(text, earlier_tokens, threshold=0.8):
    """Near-duplicate statements with different wording must not both be shown."""
    tokens = content_tokens(text)
    if not tokens:
        return False
    return any(len(tokens & earlier) / max(1, min(len(tokens), len(earlier))) >= threshold for earlier in earlier_tokens)


def source_statements(pages):
    for page in pages:
        text = ' '.join(page['text'].replace('\x07', '').split())
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            # Remove speaker labels while preserving a literal source substring.
            sentence = re.sub(r'^.{1,55}?:\s+', '', sentence)
            sentence = re.sub(r'^Page \d+ of \d+\s+', '', sentence)
            if useful_statement(sentence):
                yield {'statement': sentence, 'quote': sentence, 'page': page['page']}


def select_facts(pages, limit=3, section=None):
    candidates = []
    seen = set()
    for item in source_statements(pages):
        text = item['quote']
        key = normalize_text(text)
        if key in seen:
            continue
        seen.add(key)
        patterns = [TERMS[section]] if section in TERMS else list(TERMS.values())
        score = sum(len(re.findall(pattern, text, re.I)) for pattern in patterns)
        if not score:
            continue
        if section == 'business' and not re.search(r'we (?:are|provide|manufacture|operate|offer|serve)|our (?:business|services|products)|business segments?|core market', text, re.I):
            continue
        if section == 'business' and not re.search(r'services|software|consulting|manufactur|segments?|products?|platform|business|market|customer', text, re.I):
            continue
        if section == 'guidance' and not re.search(r'guidance|we expect|we anticipate|we target|we forecast', text, re.I):
            continue
        quantitative = bool(re.search(r'\d', text))
        if section in ('financials', 'trajectory', 'balance_sheet', 'cash_quality', 'guidance') and not quantitative:
            continue
        score += 2 if quantitative else 0
        score += 1 if re.search(r'\b(?:we|our|company|group)\b', text, re.I) else 0
        candidates.append((score, -item['page'], item))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    chosen, token_sets = [], []
    for _, _, item in candidates:
        if repeats_earlier(item['statement'], token_sets):
            continue
        chosen.append(item)
        token_sets.append(content_tokens(item['statement']))
        if len(chosen) == limit:
            break
    return chosen


def business_pages(pages):
    def score(page):
        text = page['text']
        return (len(re.findall(r'global leader|leading provider|we (?:are|provide|offer|operate)|our business|business segments?|company overview|about us|digital services|consulting|mobility|food delivery|quick commerce', text, re.I)) * 4
                - len(IRRELEVANT.findall(text)) * 3 - len(BOILERPLATE.findall(text)) * 2)
    return sorted(pages, key=lambda page: (-score(page), page['page']))[:3]


def business_descriptions(pages, aliases):
    """Find issuer descriptions as exact sentences, not company-history trivia."""
    names = '|'.join(re.escape(name) for name in aliases if name)
    pattern = re.compile(rf'\b(?:{names}|The Company|The Group|We)(?:\s+Limited|\s+Ltd\.?)?(?:\s*\([^)]{{0,90}}\))?\s+(?:is|are|provides|offers|operates|designs|manufactures|serves)\b', re.I)
    found = []
    for page in pages:
        text = ' '.join(page['text'].split())
        for match in pattern.finditer(text):
            tail = text[match.start():match.start() + 650]
            end = re.search(r'[.!](?=\s|$)', tail)
            if not end:
                continue
            sentence = tail[:end.end()]
            if not useful_statement(sentence):
                continue
            if re.search(r'we are committed|we are defined|is focused on creating|is uniquely positioned|is constantly testing', sentence, re.I):
                continue
            if not re.search(r'services|consulting|platform|manufactur|products?|business|industry|markets?|clients', sentence, re.I):
                continue
            score = 5 if any(sentence.lower().startswith(alias.lower()) for alias in aliases) else 0
            score += 5 if re.search(r'global leader|leading provider|business of|manufactur|technology services', sentence, re.I) else 0
            score += 8 if re.search(r'\bprovides|\boffers|\bdesigns|\bmanufactures|\boperates|engaged in|rendering|in the business', sentence, re.I) else 0
            found.append((score, -page['page'], {'statement': sentence, 'quote': sentence, 'page': page['page']}))
    found.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item for _, _, item in found[:2]]


def ranked_pages(pages, report=False):
    def score(page):
        text = page['text']
        weights = [(r'business segments?|our business|our clients|revenue mix|we provide|we manufacture|we operate', 5),
                   (r'revenue growth|operating margin|net debt|free cash flow|guidance|cash conversion', 3),
                   (r'cash from operations|consolidated.*revenue|segment revenue', 3)]
        return sum(weight * len(re.findall(pattern, text, re.I)) for pattern, weight in weights) - len(BOILERPLATE.findall(text)) * 2
    return sorted(pages, key=lambda page: (-score(page), page['page']))[:6 if report else 4]
