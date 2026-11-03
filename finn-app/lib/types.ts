export type Citation = { document: string; page: number; quote: string; verified?: boolean; source_url?: string | null; source_path?: string };
export type Fact = { statement: string; citation: Citation };
export type GuidanceHistory = { metric: string; period: string; unit: string; basis: string; scope: string; change: string; entries: { document: string; low: number; high: number; period_inferred?: boolean; citation: Citation }[] };
export type ResearchSection = { key: string; title: string; facts: Fact[] };
export type Research = {
  symbol?: string; mode?: string; executive_summary: string; generated_at?: string;
  coverage?: { transcripts: number; annual_reports: number };
  business_snapshot?: Fact[]; evidence?: Fact[]; sections?: ResearchSection[];
  guidance_history?: GuidanceHistory[];
  metrics: { theme: string; promise: { statement: string; period?: string; citations: Citation[] }; delivery: { statement: string; period?: string; status?: string; reason?: string; observation?: string; citations: Citation[] }; scope_evidence?: { scope: string; quote: string; note?: string } }[];
};
export type ResultsRow = { metric: string; current: number | null; previous: number | null; year_ago: number | null; qoq: number | null; yoy: number | null; quote: string; page: number };
export type FilingResults = { scope: string; unit: string; current_period: string; previous_period: string; year_ago_period: string; rows: ResultsRow[] };
export type ManagementChange = { name: string; role: string; change: string; effective_date: string; background: string; quote: string; page: number; background_quote: string; background_page: number | null };
export type Signal = { id: string; ticker: string; timestamp: string | null; type: string; priority: number; headline: string; one_line_why: string; source_url?: string; enrichment?: { results?: FilingResults; management?: ManagementChange[] }; filing_evidence?: { quote: string; page: number; source_url: string } | null };
export type Price = { date: string; close: number | null; pct_change: number | null; vol_multiple: number | null; volume?: number | null };
export type Rules = { price: number; volume: number; categories: string[] };
export type View = 'briefing' | 'portfolio' | 'research';
