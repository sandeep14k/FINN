'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Activity, ArrowDown, ArrowRight, ArrowUpRight, Bell, BookOpen, CheckCheck, ChevronDown, Compass, FileText, LayoutDashboard, RefreshCw, Search, Settings2, ShieldCheck, SlidersHorizontal, Wallet } from 'lucide-react';
import Dialog from '../components/dialog';
import SignalCard from '../components/signal-card';
import ResearchView from '../components/research-view';
import { CompanyMark, Sparkline } from '../components/primitives';
import { categories, companyNames, dateLabel, defaults, getJSON, money, percent, titleCase } from '../lib/format';
import type { Citation, Price, Research, Rules, Signal, View } from '../lib/types';

const navigation = [{ key: 'briefing' as View, title: 'Your briefing', icon: LayoutDashboard }, { key: 'portfolio' as View, title: 'Portfolio', icon: Wallet }, { key: 'research' as View, title: 'Research', icon: Compass }];
const demoCompanies = ['INFY', 'KPITTECH', 'ETERNAL', 'LAURUSLABS', 'TCS', 'HCLTECH'];

export default function FinnApp() {
  const [view, setView] = useState<View>('briefing');
  const [filings, setFilings] = useState<Signal[]>([]);
  const [prices, setPrices] = useState<Record<string, Price>>({});
  const [history, setHistory] = useState<Record<string, Price[]>>({});
  const [portfolio, setPortfolio] = useState<string[]>([]);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [staleHoldings, setStaleHoldings] = useState<string[]>([]);
  const [limitedFeed, setLimitedFeed] = useState<string[]>([]);
  const [rules, setRules] = useState<Rules>(defaults);
  const [draft, setDraft] = useState<Rules>(defaults);
  const [showRules, setShowRules] = useState(false);
  const [ruleError, setRuleError] = useState('');
  const [savingRules, setSavingRules] = useState(false);
  const [period, setPeriod] = useState('24');
  const [tickerFilter, setTickerFilter] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [unreviewed, setUnreviewed] = useState(false);
  const [seen, setSeen] = useState<string[]>([]);
  const [snapshot, setSnapshot] = useState(true);
  const [now, setNow] = useState(0);
  const [snapshotDate, setSnapshotDate] = useState('');
  const [query, setQuery] = useState('');
  const [researchSymbol, setResearchSymbol] = useState('');
  const [research, setResearch] = useState<Research | null>(null);
  const [researchProgress, setResearchProgress] = useState('');
  const [researchError, setResearchError] = useState('');
  const [citation, setCitation] = useState<Citation | null>(null);
  const [sourceText, setSourceText] = useState('');
  const [notifications, setNotifications] = useState(false);
  const requestId = useRef(0);
  const sourceId = useRef(0);
  const notified = useRef(new Set<string>());
  const reloadId = useRef(0);

  const loadData = useCallback(async () => {
    const id = ++reloadId.current;
    setRefreshing(true);
    try {
      const { feed, eod, holdings, histories, as_of } = await getJSON('/api/snapshot');
      if (id !== reloadId.current) return;
      setFilings(feed); setPrices(eod.data); setPortfolio(holdings.tickers); setHistory(histories);
      setSnapshotDate(as_of);
      setStaleHoldings([...new Set<string>([...(holdings.stale_announcements || []), ...(holdings.stale_prices || [])])]);
      setLimitedFeed(holdings.limited_feed_holdings || []);
      setLoadError('');
    } catch (error) { if (id === reloadId.current) setLoadError(error instanceof Error ? error.message : 'Could not load your briefing.'); }
    finally { if (id === reloadId.current) { setLoading(false); setRefreshing(false); } }
  }, []);

  useEffect(() => {
    let mounted = true;
    const initialise = async () => {
      await loadData();
      if (!mounted) return;
      setNow(Date.now());
      try {
        const stored = JSON.parse(localStorage.getItem('finn-seen') || '[]');
        if (Array.isArray(stored)) setSeen(stored.filter(value => typeof value === 'string'));
        const saved = await getJSON('/api/preferences').catch(() => JSON.parse(localStorage.getItem('finn-rules') || 'null'));
        if (saved && typeof saved.price === 'number' && saved.price >= 1 && saved.price <= 10 && typeof saved.volume === 'number' && saved.volume >= 1 && saved.volume <= 5) {
          setRules({ price: saved.price, volume: saved.volume, categories: Array.isArray(saved.categories) ? saved.categories.filter((value: string) => categories.includes(value)) : categories.filter(category => !(category === 'results' && saved.results === false) && !(category === 'management_change' && saved.management === false)) });
        }
      } catch { /* Invalid saved preferences use defaults. */ }
      if ('Notification' in window) setNotifications(Notification.permission === 'granted');
    };
    initialise();
    const clock = setInterval(() => setNow(Date.now()), 30_000);
    const poll = setInterval(loadData, 60_000);
    return () => { mounted = false; clearInterval(clock); clearInterval(poll); };
  }, [loadData]);

  const signals = useMemo(() => {
    const output = [...filings];
    for (const ticker of portfolio) {
      const price = prices[`${ticker}.NS`];
      if (!price) continue;
      const timestamp = `${price.date}T15:30:00+05:30`;
      if (price.pct_change !== null && Math.abs(price.pct_change) >= rules.price) output.push({ id: `price-${ticker}-${price.date}`, ticker, timestamp, type: 'price_move', priority: 4, headline: `${percent(price.pct_change)} at the close`, one_line_why: `Crossed your ±${rules.price}% daily threshold. Closing price ${money(price.close)}.` });
      if (price.vol_multiple !== null && price.vol_multiple >= rules.volume) output.push({ id: `volume-${ticker}-${price.date}`, ticker, timestamp, type: 'volume_spike', priority: 4, headline: `${price.vol_multiple.toFixed(2)}× the usual trading volume`, one_line_why: `Above your ${rules.volume}× threshold, measured against the previous 20 trading sessions.` });
    }
    return output;
  }, [filings, prices, portfolio, rules]);
  const latestFiling = signals.reduce((max, item) => {
    const stamp = item.timestamp?.length === 10 ? `${item.timestamp}T00:00:00+05:30` : item.timestamp || '';
    return Math.max(max, Date.parse(stamp) || 0);
  }, 0);
  const latest = snapshotDate ? Date.parse(`${snapshotDate}T12:00:00+05:30`) : 0;
  const reference = snapshot && latest ? Math.max(latest, latestFiling) : now;
  const visible = signals.filter(item => {
    if (tickerFilter !== 'ALL' && item.ticker !== tickerFilter) return false;
    if (categoryFilter !== 'ALL' && item.type !== categoryFilter) return false;
    if (unreviewed && seen.includes(item.id)) return false;
    if (period === 'all') return true;
    const timestamp = item.timestamp?.length === 10 ? `${item.timestamp}T00:00:00+05:30` : item.timestamp || '';
    const age = reference - Date.parse(timestamp);
    return age >= 0 && age <= Number(period) * 3_600_000;
  }).sort((left, right) => right.priority - left.priority || Date.parse(right.timestamp || '') - Date.parse(left.timestamp || ''));
  const watched = (item: Signal) => item.priority >= 3 && (!categories.includes(item.type) || rules.categories.includes(item.type));
  const priority = visible.filter(watched);
  const routine = visible.filter(item => !watched(item));
  const movers = portfolio.map(ticker => ({ ticker, price: prices[`${ticker}.NS`] })).filter(item => item.price).sort((a, b) => Math.abs(b.price.pct_change || 0) - Math.abs(a.price.pct_change || 0));
  const up = movers.filter(item => (item.price.pct_change || 0) > 0).length;
  const down = movers.filter(item => (item.price.pct_change || 0) < 0).length;

  useEffect(() => {
    // Only newly observed, recent events notify. A saved snapshot never creates a notification storm.
    const eligible = signals.filter(item => item.priority >= 3 && Date.now() - Date.parse(item.timestamp || '') >= 0 && Date.now() - Date.parse(item.timestamp || '') < 86_400_000 && (!categories.includes(item.type) || rules.categories.includes(item.type)));
    for (const item of eligible) {
      if (notified.current.has(item.id)) continue;
      notified.current.add(item.id);
      if (notifications && 'Notification' in window && Notification.permission === 'granted' && document.visibilityState === 'hidden') {
        try { new Notification(`${item.ticker} · ${titleCase(item.type)}`, { body: item.headline, tag: item.id }); }
        catch { /* In-app alerts remain available without constructor support. */ }
      }
    }
  }, [signals, notifications, rules.categories]);

  function navigate(next: View) { setView(next); window.scrollTo({ top: 0 }); }
  function markReviewed() {
    const ids = [...new Set([...seen, ...visible.map(item => item.id)])].slice(-5000);
    setSeen(ids);
    try { localStorage.setItem('finn-seen', JSON.stringify(ids)); } catch { /* Session still works. */ }
  }
  const closeRules = useCallback(() => setShowRules(false), []);
  const closeCitation = useCallback(() => setCitation(null), []);
  async function saveRules() {
    setSavingRules(true); setRuleError('');
    try {
      const response = await fetch('/api/preferences', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(draft) });
      if (!response.ok) throw new Error('Could not save workspace preferences. Please retry.');
      setRules(draft);
      try { localStorage.setItem('finn-rules', JSON.stringify(draft)); } catch { /* Server preferences remain saved. */ }
      closeRules();
    } catch (error) { setRuleError(error instanceof Error ? error.message : 'Could not save preferences.'); }
    finally { setSavingRules(false); }
  }
  async function inspect(cite: Citation) {
    const id = ++sourceId.current;
    setCitation(cite); setSourceText('Loading the original page extract…');
    if (!cite.source_path) { setSourceText('A page extract is unavailable for this source.'); return; }
    try {
      const pages = await getJSON(`${cite.source_path}&page=${cite.page}`);
      const page = pages.find((page: { page: number }) => page.page === cite.page);
      const normalise = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();
      const text = page && normalise(page.text).includes(normalise(cite.quote)) ? page.text : page?.layout_text || page?.text;
      if (id === sourceId.current) setSourceText(text || 'This page is unavailable.');
    } catch { if (id === sourceId.current) setSourceText('Could not load the page. Please try again.'); }
  }
  async function openResearch(raw: string) {
    const symbol = raw.trim().toUpperCase().replace(/\.NS$/, '');
    if (!/^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(symbol)) { setResearchError('Enter a valid NSE symbol, such as INFY or TCS.'); setResearchProgress(''); return; }
    setResearchSymbol(symbol); setResearch(null); setResearchError(''); setResearchProgress('Finding company evidence'); navigate('research');
    const id = ++requestId.current;
    try {
      let result = await getResearch(symbol);
      for (let attempt = 0; result.status === 'running' && attempt < 950; attempt++) {
        if (id !== requestId.current) return;
        setResearchProgress(result.stage || 'Reading company reports and earnings calls');
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (id !== requestId.current) return;
        result = await getJSON(`/api/research?symbol=${encodeURIComponent(symbol)}`);
      }
      if (id !== requestId.current) return;
      if (result.status !== 'ready') throw new Error(result.error || 'Research is not ready yet. Please try again.');
      setResearch(result.data); setResearchProgress('');
    } catch (error) { if (id === requestId.current) { setResearchError(error instanceof Error ? error.message : 'Research failed.'); setResearchProgress(''); } }
  }
  async function getResearch(symbol: string) {
    const response = await fetch(`/api/research?symbol=${encodeURIComponent(symbol)}`, { method: 'POST' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Research could not start.');
    return result;
  }
  const researchForm = (compact = false) => <form className={`research-search ${compact ? 'compact' : ''}`} onSubmit={event => { event.preventDefault(); openResearch(query); }}><Search size={18}/><label className="sr-only" htmlFor={compact ? 'quick-ticker' : 'research-ticker'}>NSE ticker</label><input id={compact ? 'quick-ticker' : 'research-ticker'} value={query} onChange={event => setQuery(event.target.value)} placeholder={compact ? 'Research a company…' : 'Enter an NSE symbol, e.g. INFY'} maxLength={28}/><button aria-label="Start company research" type="submit"><ArrowRight size={18}/></button></form>;

  return <div className="app-shell">
    <aside className="sidebar"><Link href="/" className="brand" aria-label="FINN home"><span className="brand-symbol"><Activity size={25}/></span>finn<span className="brand-period">.</span></Link><p className="brand-description">A little less noise.<br/>A lot more perspective.</p><div className="nav-caption">YOUR WORKSPACE</div><nav aria-label="Main navigation">{navigation.map(item => <button key={item.key} onClick={() => navigate(item.key)} className={view === item.key ? 'active' : ''}><item.icon size={18}/>{item.title}{item.key === 'briefing' && priority.length > 0 && <span>{priority.length}</span>}</button>)}</nav><div className="sidebar-bottom"><div className="source-promise"><ShieldCheck size={19}/><strong>Evidence, always.</strong><p>Company disclosures.<br/>Visible sources.<br/>Your judgment.</p></div><button className="sidebar-settings" onClick={() => { setDraft({ ...rules, categories: [...rules.categories] }); setShowRules(true); }}><Settings2 size={17}/> Preferences</button><div className="profile-mark"><span>SI</span><div><strong>Your investment desk</strong><small>Personal workspace</small></div></div></div></aside>
    <div className="main-shell"><header className="topbar"><div className="mobile-brand"><Activity size={22}/>finn.</div><div className="breadcrumb">Workspace <span>/</span> <strong>{navigation.find(item => item.key === view)?.title}</strong></div><div className="topbar-actions"><span className="snapshot-badge"><span/>{snapshot ? 'Saved snapshot' : 'Current-time view'}</span><button className={`icon-button ${refreshing ? 'spin-icon' : ''}`} aria-label="Reload saved data" onClick={loadData}><RefreshCw size={17}/></button><button className="icon-button" aria-label="Configure alert rules" onClick={() => { setDraft({ ...rules, categories: [...rules.categories] }); setShowRules(true); }}><SlidersHorizontal size={18}/></button></div></header>
      <main className="workspace">
        {view === 'briefing' && <><div className="page-heading"><div><p className="eyebrow">YOUR DAILY ADVANTAGE</p><h1>Less noise.<br className="mobile-break"/> More signal<span className="heading-dot">.</span></h1><p className="page-description">The changes worth your attention. The evidence to go deeper.</p></div><div className="briefing-date"><span>{latest ? dateLabel(new Date(latest).toISOString(), true) : 'Portfolio briefing'}</span><small>{portfolio.length} holdings in focus</small></div></div>
          <section className="briefing-hero" aria-label="Briefing overview"><div className="hero-message"><span className="hero-label"><span className="pulse-dot"/> YOUR ATTENTION DESK</span><h2>{loading ? 'Gathering the signal.' : priority.length ? `${priority.length} things to look at.\nThe rest can wait.` : 'A quieter view.\nRoom to think.'}</h2><p>{routine.length} other disclosures are tucked away. Your rules decide what rises to the top. Market alerts show the latest saved session.</p><a href="#priority-desk">Read your briefing <ArrowDown size={15}/></a></div><div className="hero-stats"><div><FileText size={18}/><strong>{visible.filter(item => !['price_move', 'volume_spike'].includes(item.type)).length}</strong><span>Disclosures in view</span></div><div><Activity size={18}/><strong>{visible.filter(item => ['price_move', 'volume_spike'].includes(item.type)).length}</strong><span>Market-move alerts</span></div><div><ShieldCheck size={18}/><strong>{visible.filter(item => item.filing_evidence).length}</strong><span>Filing previews</span></div></div></section>
          <div className="briefing-grid"><div className="briefing-feed" id="priority-desk"><div className="section-heading"><div><p className="eyebrow">CURATED FOR YOUR PORTFOLIO</p><h2>Priority desk <span>{priority.length}</span></h2></div><button className="text-button" onClick={markReviewed} disabled={!visible.length}><CheckCheck size={15}/> Mark view reviewed</button></div>
            <div className="filter-row"><label className="select-wrap"><span className="sr-only">Digest period</span><select aria-label="Digest period" value={period} onChange={event => setPeriod(event.target.value)}><option value="24">Last 24 hours</option><option value="72">Last 3 days</option><option value="168">Last 7 days</option><option value="all">All available</option></select><ChevronDown size={13}/></label><label className="select-wrap"><select aria-label="Filter by holding" value={tickerFilter} onChange={event => setTickerFilter(event.target.value)}><option value="ALL">All holdings</option>{portfolio.map(ticker => <option key={ticker}>{ticker}</option>)}</select><ChevronDown size={13}/></label><label className="select-wrap category-select"><select aria-label="Filter by category" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="ALL">All categories</option>{[...new Set(signals.map(item => item.type))].sort().map(category => <option key={category} value={category}>{titleCase(category)}</option>)}</select><ChevronDown size={13}/></label></div><div className="feed-controls"><label><input type="checkbox" checked={unreviewed} onChange={event => setUnreviewed(event.target.checked)}/>Unreviewed only</label><label><input type="checkbox" checked={snapshot} onChange={event => setSnapshot(event.target.checked)}/>Anchor to snapshot</label></div>
            {limitedFeed.length > 0 && <p className="source-coverage"><ShieldCheck size={12}/>{limitedFeed.length} holdings use a limited fallback feed. Full filing coverage is not guaranteed.</p>}{loadError && <div className="error-panel" role="alert"><p>{loadError}</p><button onClick={loadData}>Try again</button></div>}{staleHoldings.length > 0 && <p className="coverage-warning">Some sources could not refresh: {staleHoldings.map(ticker => ticker.replace('.NS', '')).join(', ')}. Previous data is retained.</p>}{loading && <div className="loading-skeleton" role="status">Loading your briefing…</div>}
            <section aria-label="Portfolio signals" className="signal-list">{priority.map(signal => <SignalCard key={signal.id} signal={signal} reviewed={seen.includes(signal.id)} research={openResearch}/>)}{!loading && !priority.length && <div className="empty-panel"><CheckCheck size={26}/><h3>No watched changes in this view.</h3><p>Try a wider time window or adjust your filters to explore more disclosures.</p><button className="text-button" onClick={() => { setPeriod('all'); setTickerFilter('ALL'); setCategoryFilter('ALL'); setUnreviewed(false); }}>Show all available <ArrowRight size={14}/></button></div>}{routine.length > 0 && <details className="routine-group"><summary><div><FileText size={16}/><strong>Other disclosures</strong><span>{routine.length}</span></div><ChevronDown size={16}/></summary><p>Routine and unwatched disclosures remain available here.</p><div className="signal-list">{routine.map(signal => <SignalCard key={signal.id} signal={signal} reviewed={seen.includes(signal.id)} research={openResearch}/>)}</div></details>}</section>
          </div><aside className="context-column"><section className="research-invitation"><span className="invitation-icon"><Compass size={21}/></span><p className="eyebrow">FOLLOW THE THREAD</p><h2>Good questions.<br/>Better evidence.</h2><p>See what management promised, what changed, and what the numbers actually say.</p>{researchForm(true)}<button className="text-button" onClick={() => openResearch('INFY')}>Explore Infosys research <ArrowUpRight size={14}/></button></section><section className="movers-panel"><div className="section-heading"><h3>On the move</h3><span>EOD</span></div><p className="panel-description">Largest daily moves in your holdings.</p>{movers.slice(0, 5).map(({ ticker, price }) => <button className="mover-row" key={ticker} onClick={() => openResearch(ticker)}><CompanyMark symbol={ticker} small/><div><strong>{ticker}</strong><small>{money(price.close)}</small></div><Sparkline rows={history[`${ticker}.NS`] || []} positive={(price.pct_change || 0) >= 0}/><span className={(price.pct_change || 0) >= 0 ? 'positive' : 'negative'}>{percent(price.pct_change)}</span></button>)}<button className="text-button all-holdings" onClick={() => navigate('portfolio')}>View all holdings <ArrowRight size={14}/></button></section><div className="source-note"><ShieldCheck size={16}/><p>Primary sources. Visible uncertainty.<br/>A clearer starting point for your own research.</p></div></aside></div>
        </>}
        {view === 'portfolio' && <><div className="page-heading"><div><p className="eyebrow">THE BIGGER PICTURE</p><h1>Your portfolio<span className="heading-dot">.</span></h1><p className="page-description">{portfolio.length} companies. A view across the day’s market moves.</p></div></div><div className="portfolio-summary"><div><span>HOLDINGS TRACKED</span><strong>{portfolio.length}</strong></div><div><span>ADVANCING</span><strong className="positive">{up}</strong></div><div><span>DECLINING</span><strong className="negative">{down}</strong></div><div><span>LATEST CLOSE</span><strong className="summary-date">{movers[0] ? dateLabel(movers[0].price.date) : '—'}</strong></div></div><div className="portfolio-table"><div className="portfolio-table-head"><span>Company</span><span>Recent closes</span><span>Close</span><span>Day change</span><span>Volume</span></div>{portfolio.map(ticker => { const price = prices[`${ticker}.NS`]; return <button className="portfolio-row" key={ticker} onClick={() => openResearch(ticker)}><div className="company-identity"><CompanyMark symbol={ticker}/><div><strong>{companyNames[ticker] || ticker}</strong><span>{ticker}</span></div></div><Sparkline rows={history[`${ticker}.NS`] || []} positive={(price?.pct_change || 0) >= 0}/><strong className="portfolio-price">{money(price?.close)}</strong><span className={`change-pill ${(price?.pct_change || 0) >= 0 ? 'positive' : 'negative'}`}>{percent(price?.pct_change)}</span><span className="volume-cell">{price?.vol_multiple != null ? `${price.vol_multiple.toFixed(2)}×` : '—'}<small>vs 20-session avg.</small></span></button>; })}</div><p className="fine-print">An illustrative watchlist, not a return calculation. Sparklines use saved daily closing prices; volume excludes the current session from its baseline.</p></>}
        {view === 'research' && (researchSymbol ? <ResearchView key={researchSymbol} symbol={researchSymbol} data={research} progress={researchProgress} error={researchError} back={() => { requestId.current++; setResearchSymbol(''); }} retry={() => openResearch(researchSymbol)} inspect={inspect}/> : <><div className="page-heading"><div><p className="eyebrow">CURIOSITY, WITH RECEIPTS</p><h1>Go beyond<br/>the headline<span className="heading-dot">.</span></h1><p className="page-description">Company reports. Management commentary. A source behind every claim.</p></div></div><section className="research-library-search"><Compass size={26}/><div><h2>What are you looking into?</h2><p>Start with an NSE symbol. Follow the evidence from there.</p></div>{researchForm()}</section><div className="section-heading library-heading"><h2>Your research shelf</h2><span>{demoCompanies.length} saved companies</span></div><div className="company-library">{demoCompanies.map((symbol, index) => <button key={symbol} onClick={() => openResearch(symbol)} className="library-card"><div><CompanyMark symbol={symbol}/><ArrowUpRight size={19}/></div><p className="section-kicker">{symbol}</p><h3>{companyNames[symbol]}</h3><p>{index === 0 ? 'Guidance history, reported outcomes, and the evidence behind them.' : 'A company brief, financial context, and management commentary, with sources.'}</p><span><BookOpen size={13}/> Open research</span></button>)}</div></>)}
        <footer className="workspace-footer"><span>FINN <span>—</span> Signal over noise.</span><span>Research, grounded in company disclosures.</span></footer>
      </main>
    </div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{navigation.map(item => <button key={item.key} className={view === item.key ? 'active' : ''} onClick={() => navigate(item.key)}><item.icon size={20}/><span>{item.key === 'briefing' ? 'Briefing' : item.title}</span></button>)}</nav>
    {showRules && <Dialog title="Your alert rules" subtitle="MAKE THE SIGNAL YOURS" close={closeRules}><p className="dialog-description">Choose what earns your attention. Preferences update this investment workspace. Reviewed items stay on this device.</p><label className="range-label">Daily price movement<strong>±{draft.price}%</strong><input aria-label="Price movement threshold" type="range" min="1" max="10" step="0.5" value={draft.price} onChange={event => setDraft({ ...draft, price: Number(event.target.value) })}/><small>Absolute change from the previous close.</small></label><label className="range-label">Unusual trading volume<strong>{draft.volume}×</strong><input aria-label="Volume threshold" type="range" min="1" max="5" step="0.5" value={draft.volume} onChange={event => setDraft({ ...draft, volume: Number(event.target.value) })}/><small>Compared with the previous 20 sessions.</small></label><h3 className="preferences-title">Disclosures to watch</h3><div className="category-options">{categories.map(category => <label key={category}><span>{titleCase(category)}</span><input type="checkbox" checked={draft.categories.includes(category)} onChange={event => setDraft({ ...draft, categories: event.target.checked ? [...draft.categories, category] : draft.categories.filter(value => value !== category) })}/></label>)}</div><button className="primary-button save-rules" disabled={savingRules} onClick={saveRules}>{savingRules ? 'Saving…' : 'Save & update briefing'} <ArrowRight size={16}/></button>{ruleError && <p role="alert" className="coverage-warning">{ruleError}</p>}<button className="notification-button" onClick={async () => { if ('Notification' in window) { try { setNotifications(await Notification.requestPermission() === 'granted'); } catch { setNotifications(false); } } }}>{notifications ? <CheckCheck size={15}/> : <Bell size={15}/>} {notifications ? 'Browser notifications enabled' : 'Enable browser notifications'}</button><p className="fine-print">While FINN is open, saved data is checked every minute. Notifications require browser permission and a hidden tab. Source freshness is shown in the briefing.</p></Dialog>}
    {citation && <Dialog title={`${citation.document} · Page ${citation.page}`} subtitle="THE ORIGINAL EVIDENCE" close={closeCitation} wide><div className={`verification-note ${citation.verified ? '' : 'unverified'}`}><ShieldCheck size={16}/>{citation.verified ? 'Quotation matched against this extracted page' : 'Quotation has not been verified'}</div><blockquote className="source-quote">“{citation.quote}”</blockquote>{citation.source_url && <a className="primary-button original-source" href={`${citation.source_url}#page=${citation.page}`} target="_blank" rel="noreferrer">Open original document <ArrowUpRight size={15}/></a>}<details className="full-extract"><summary>Read the full page extract <ChevronDown size={15}/></summary><pre>{sourceText}</pre></details></Dialog>}
  </div>;
}
