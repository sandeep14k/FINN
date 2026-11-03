'use client';

export type HistoryCitation = { document: string; page: number; quote: string; verified?: boolean; source_url?: string; source_path?: string };
export type GuidanceHistory = {
  metric: string; period: string; unit: string; basis: string; scope: string;
  change: 'raised' | 'lowered' | 'unchanged' | 'revised';
  entries: { document: string; low: number; high: number; period_inferred?: boolean; citation: HistoryCitation }[];
};

export default function GuidanceTimeline({ histories, inspect }: {
  histories: GuidanceHistory[]; inspect: (citation: HistoryCitation) => void;
}) {
  return <section aria-label="Guidance history" className="space-y-4">
    <div><h3 className="text-lg font-semibold tracking-tight">Management memory</h3>
      <p className="mt-1 text-xs leading-relaxed text-slate-500">How expectations changed for the same reporting period. Revisions track management’s outlook; delivery is assessed separately.</p></div>
    {histories.map((history, index) => <article key={index} className="rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3"><div><h4 className="text-sm font-semibold">{history.metric}</h4>
        <p className="mt-1 text-xs text-slate-500">{history.period} · {history.basis}{history.scope !== 'unspecified' && history.scope !== 'unknown' ? ` · ${history.scope}` : ''}</p></div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-bold uppercase tracking-wide">{history.change}</span></div>
      <ol className="mt-5 space-y-0">{history.entries.map((entry, position) => <li key={entry.document} className="relative border-l-2 border-teal-100 pb-5 pl-5 last:pb-0">
        <span className={`absolute -left-[5px] top-1 h-2 w-2 rounded-full ${position === history.entries.length - 1 ? 'bg-teal-700' : 'bg-teal-300'}`} />
        <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs text-slate-500">{entry.document}</span>
          <strong className="text-lg tabular-nums tracking-tight">{entry.low === entry.high ? entry.low : `${entry.low}–${entry.high}`}<span className="ml-1 text-xs font-normal text-slate-500">{history.unit}</span></strong></div>
        <button onClick={() => inspect(entry.citation)} className="mt-1 text-xs font-semibold text-teal-700 underline-offset-4 hover:underline">Inspect guidance · p.{entry.citation.page}</button>
      </li>)}</ol>
      {history.entries.some(entry => entry.period_inferred) && <p className="mt-4 text-[11px] leading-relaxed text-slate-400">Where the quote omits a year, the annual period is inferred from its earnings-call context.</p>}
    </article>)}
  </section>;
}
