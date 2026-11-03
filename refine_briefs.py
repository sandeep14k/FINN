"""Recheck saved research quality and recover issuer descriptions without an API call."""
import json
import sys
from urllib.parse import urlencode
from config import DATA_DIR, ROOT_DIR
from evidence_quality import useful_statement, business_descriptions, content_tokens, repeats_earlier
from research_brief import issuer_aliases


def refine(symbol):
    directory = DATA_DIR / 'docs' / symbol
    path = directory / 'brief.json'
    brief = json.loads(path.read_text())
    sources = json.loads((directory / 'sources.json').read_text())
    for section in brief['sections']:
        kept, token_sets = [], []
        for fact in section['facts']:
            if not useful_statement(fact['statement']) or repeats_earlier(fact['statement'], token_sets):
                continue
            kept.append(fact)
            token_sets.append(content_tokens(fact['statement']))
        section['facts'] = kept
    descriptions = []
    for report in directory.glob('ar_*.json'):
        for fact in business_descriptions(json.loads(report.read_text()), issuer_aliases(symbol)):
            descriptions.append({'statement': fact['statement'], 'citation': {
                'document': 'Annual report', 'quote': fact['quote'], 'page': fact['page'], 'verified': True,
                'source_url': sources.get(report.name),
                'source_path': '/api/source?' + urlencode({'symbol': symbol, 'file': report.name}),
            }})
    if descriptions:
        brief['sections'] = [section for section in brief['sections'] if section['key'] != 'business']
        brief['sections'].insert(0, {'key': 'business', 'title': 'The business, in context', 'facts': descriptions[:1]})
    brief['sections'] = [section for section in brief['sections'] if section['facts']]
    path.write_text(json.dumps(brief, indent=2))
    output = ROOT_DIR / 'finn-app/public/data/pull' / f'{symbol}.json'
    payload = json.loads(output.read_text())
    payload['sections'] = brief['sections']
    payload['business_snapshot'] = next((section['facts'] for section in brief['sections'] if section['key'] == 'business'), [])
    payload['evidence'] = [fact for section in brief['sections'] if section['key'] != 'business' for fact in section['facts']]
    if not payload.get('metrics'):
        payload['executive_summary'] = f'{len(brief["sections"])} research sections grounded in company reports and earnings calls. No completed promise-to-outcome verdict has been established.'
    output.write_text(json.dumps(payload, indent=2))
    print(symbol, [fact['statement'] for fact in payload['business_snapshot']])


if __name__ == '__main__':
    for symbol in sys.argv[1:] or ['INFY']:
        refine(symbol)
