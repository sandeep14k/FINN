import { ArrowUpRight, ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { dateLabel, titleCase, companyNames } from '../lib/format';
import type { Signal } from '../lib/types';
import { CompanyMark } from './primitives';
import FilingEnrichment from './filing-enrichment';

export default function SignalCard({ signal, reviewed, research }: { signal: Signal; reviewed: boolean; research: (symbol: string) => void }) {
  const market = signal.type === 'price_move' || signal.type === 'volume_spike';
  return <article className={`signal-card ${reviewed ? 'is-reviewed' : ''}`}>
    <div className="signal-top"><div className="company-identity"><CompanyMark symbol={signal.ticker} small/><div><strong>{companyNames[signal.ticker] || signal.ticker}</strong><span>{signal.ticker}</span></div></div><div className="signal-meta">{!reviewed && <span className="new-dot" title="Unreviewed"/>}<time>{signal.timestamp ? dateLabel(signal.timestamp) : 'Undated'}</time></div></div>
    <div className="signal-category"><span className={`category-tag ${signal.priority >= 5 ? 'material' : market ? 'market' : ''}`}>{titleCase(signal.type)}</span>{signal.priority >= 5 && <span className="material-caption">Needs a closer look</span>}</div>
    <h3>{signal.headline}</h3><p className="signal-reason">{signal.one_line_why}</p>
    <FilingEnrichment signal={signal}/>
    {signal.filing_evidence && <details className="filing-preview"><summary><FileText size={14}/> Inside the filing <span>Page {signal.filing_evidence.page}</span><ChevronDown size={14}/></summary><blockquote>{signal.filing_evidence.quote}</blockquote><a href={`${signal.filing_evidence.source_url}#page=${signal.filing_evidence.page}`} target="_blank" rel="noreferrer">Verify original page <ArrowUpRight size={13}/></a></details>}
    <div className="signal-actions">{signal.source_url ? <a href={signal.source_url} target="_blank" rel="noreferrer">Original filing <ArrowUpRight size={13}/></a> : <span className="market-source">End-of-day observation</span>}<button onClick={() => research(signal.ticker)}>Research company <ChevronRight size={14}/></button></div>
  </article>;
}
