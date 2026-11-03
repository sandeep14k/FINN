import { ArrowUpRight, CheckCheck } from 'lucide-react';
import { companyNames } from '../lib/format';
import type { Citation, Price } from '../lib/types';

export function CompanyMark({ symbol, small = false }: { symbol: string; small?: boolean }) {
  return <span className={`company-mark ${small ? 'company-mark-small' : ''}`} data-tone={symbol.charCodeAt(0) % 4}>{symbol.slice(0, 2)}</span>;
}
export function Sparkline({ rows, positive = true }: { rows: Price[]; positive?: boolean }) {
  const values = rows.slice(-24).map(row => row.close).filter((value): value is number => value !== null && Number.isFinite(value));
  if (values.length < 2) return <span className="chart-unavailable">No history</span>;
  const low = Math.min(...values), span = Math.max(...values) - low || 1;
  const points = values.map((value, index) => `${index / (values.length - 1) * 104},${29 - (value - low) / span * 25}`).join(' ');
  return <svg className={`sparkline ${positive ? 'positive' : 'negative'}`} viewBox="0 0 104 34" role="img" aria-label={`${values.length} recent daily closing prices, latest ${values[values.length - 1]}`}><polyline points={points} fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round"/></svg>;
}
export function SourceButton({ citation, inspect }: { citation: Citation; inspect: (citation: Citation) => void }) {
  return <button className="source-chip" onClick={() => inspect(citation)}>{citation.verified && <CheckCheck size={13}/>} {citation.document} <span>p.{citation.page}</span><ArrowUpRight size={12}/></button>;
}
export function CompanyName({ symbol }: { symbol: string }) {
  return <><strong>{companyNames[symbol] || symbol}</strong><span className="ticker-label">{symbol}</span></>;
}
