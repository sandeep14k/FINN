import { ArrowUpRight, UserRound } from 'lucide-react';
import type { Signal } from '../lib/types';
import { dateLabel, percent, titleCase } from '../lib/format';

export default function FilingEnrichment({ signal }: { signal: Signal }) {
  const results = signal.enrichment?.results;
  const people = signal.enrichment?.management || [];
  const amount = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return <>
    {results && <details className="results-enrichment" open><summary><span>Quarterly first look</span><span>{titleCase(results.scope)} · {results.unit}</span></summary><p className="results-periods">Quarter ends: {dateLabel(results.current_period, true)} / {dateLabel(results.previous_period, true)} / {dateLabel(results.year_ago_period, true)}</p><div className="financial-table-scroll" role="region" aria-label="Quarterly financial comparison" tabIndex={0}><table className="financial-table"><thead><tr><th>Metric</th><th>This quarter</th><th>Previous Q</th><th>Year ago</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>{['Revenue', 'EBITDA', 'PBT', 'PAT'].map(metric => { const row = results.rows.find(row => row.metric === metric); return <tr key={metric}><th>{signal.source_url && row ? <a href={`${signal.source_url}#page=${row.page}`} target="_blank" rel="noreferrer">{metric}<ArrowUpRight size={10}/></a> : metric}</th><td>{amount(row?.current)}</td><td>{amount(row?.previous)}</td><td>{amount(row?.year_ago)}</td><td>{percent(row?.qoq)}</td><td>{percent(row?.yoy)}</td></tr>; })}</tbody></table></div><p className="fine-print">— means unavailable or not comparable. Percentage changes use positive comparison bases only. Open a metric’s original page to verify the row.</p></details>}
    {people.map(person => <div className="management-profile" key={person.name}><div className="profile-icon"><UserRound size={18}/></div><div><span className="section-kicker">{titleCase(person.change)}{person.effective_date ? ` · ${person.effective_date}` : ''}</span><h4>{person.name}</h4><strong>{person.role}</strong><p>{person.background || 'A professional background was not disclosed in the available filing text.'}</p>{signal.source_url && <a href={`${signal.source_url}#page=${person.background_page || person.page}`} target="_blank" rel="noreferrer">Read the disclosed profile <ArrowUpRight size={12}/></a>}</div></div>)}
  </>;
}
