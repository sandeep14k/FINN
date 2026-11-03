# Architecture

FINN is one product with two surfaces: a prioritised portfolio briefing (Push) and a primary-source research brief with promise-to-outcome checks (Pull). The Next.js app and the Python pipeline are deployed together on a persistent host because research runs as a bounded background process that reads and writes shared files. This is a small monorepo by design, not a package boundary that adds no value at this scale.

```text
Finn/
  finn-app/
    app/                 Next.js routes, layout and global design styles
      api/               Server-only snapshot, research, preferences and source endpoints
    components/          Briefing, research, citation and dialog interfaces
    lib/                 Shared TypeScript types and formatting helpers
    public/data/         Published, browser-readable snapshots and research
    scripts/             Tailwind build/watch tooling
  data/
    announcements.json   Raw BSE/Screener announcement feed
    eod_*.json           End-of-day prices, history and volume baselines
    docs/<SYMBOL>/       Extracted annual-report and transcript pages, sources, comparison
    filings/             Extracted pages for material exchange-filing previews
    scope_evidence.json  Optional, page-verified scope records per company
    .cache/              Private, ignored model response and rate-limit cache
    .jobs/               Private, ignored research progress
  tests/                 Financial correctness, source-integrity and failure-path checks
  *.py                   Python pipeline modules and command-line entry points
  Dockerfile             One persistent Node/Python deployment
```

## Push: snapshot pipeline

```text
fetch_prices.py ─┐
fetch_announcements.py ─┼→ generate_push.py → finn-app/public/data/snapshot.json → GET /api/snapshot → briefing
enrich_push.py ──┤                ↑
filing_analysis.py ─┘   data/filing_evidence.json + data/filing_analysis.json
```

- `fetch_prices.py` computes close, day change and volume multiple against the previous 20 sessions. It drops an in-progress intraday row before the 15:30 IST close so a partial bar is never published as EOD.
- `fetch_announcements.py` collects exchange disclosures per holding. `generate_push.py` classifies each into a material category and priority, computes a stable SHA-256 identity, attaches any verified filing preview and emits one snapshot containing the feed, prices, histories and coverage metadata. Classification reads only the filing title (the part before the exchanged summary), and one results event split across several filings keeps its richest filing in the priority desk while companions are demoted with a visible reason.
- `filing_analysis.py` extracts a quarterly table (Revenue, EBITDA, PBT, PAT for current, previous and year-ago quarters) and management changes from results and leadership filings. A table is published only when period dates agree, the header quote verifies on its page, and every number appears verbatim in the cited row; otherwise the filing stays a link without inferred figures.
- Partial upstream failures keep the previous company records, list stale tickers explicitly and mark holdings using a limited fallback feed. The interface names them instead of implying complete coverage.
- `snapshot.json` is also served in-browser; digest filtering (24h/3d/7d/all, holding, category, unreviewed) happens client-side against the snapshot date. Reviewed state is kept in `localStorage` and never leaves the device.
- `enrich_push.py` downloads the newest material filings and selects one verbatim excerpt per filing, with its page number and a link back to the original PDF. No model tokens are used.

## Pull: research pipeline

```text
ingest_ticker.py
  → discover recent transcripts + one annual report (Screener / exchange)
  → extract_pdf.py (PyMuPDF, page-preserving text)
  → guidance_extract.py / explicit_guidance.py / financial_metrics.py
  → promised_vs_delivered.py + ground.py
  → research_brief.py
  → finn-app/public/data/pull/<SYMBOL>.json → GET /api/research → research view
```

1. **Discovery and extraction.** `ingest_ticker.py` finds up to five recent earnings-call transcripts and one annual report, rejecting empty or scanned documents. Filenames include a URL hash so two documents with the same label cannot collide. Every extracted page keeps a page number, so a citation can be checked against the exact page.
2. **Evidence, not prose.** Model calls are bounded: transcripts are chunked (≤4,500 characters with overlap), ranked for outlook relevance, and reviewed under strict JSON schemas. Explicit percentage guidance is recovered with deterministic patterns without model tokens. Annual-report snapshots review up to three chunks. Every extracted statement keeps its verbatim quotation and page.
3. **Verification.** `research_brief.py` and `ground.py` reject any quotation that does not normalize to a substring of the cited extracted page. Summary statements may not introduce numbers absent from their supporting quote. Unverified facts never reach the published brief.
4. **Comparison.** `promised_vs_delivered.py` matches a promise to a reported observation only when metric, period, unit, accounting basis and consolidation scope all agree. `ground.py` then applies a fail-closed verdict:
   - `MET` / `BEAT` / `MISSED` only for a completed period with matching definitions and verified values;
   - `PENDING` when the target period has not ended;
   - `NOT_COMPARABLE` when a required definition is missing or mismatched;
   - `UNVERIFIED` when a quotation cannot be verified.

   An interim quarter never establishes annual delivery. Period inference from call context is disclosed in the UI.
5. **Scope evidence.** Consolidation scope is often stated in the annual report rather than repeated in each transcript. `scope_evidence.py` accepts an optional record keyed by metric and period. It is applied only if (a) the record's quotation verifies against the cited document and page, (b) the scope word appears in that quotation, and (c) any reported value also appears in that quotation. It fills a missing scope field on both sides and attaches the citation; it never overwrites an existing scope or a value. The research view shows the reasoning.
6. **Brief composition.** `research_brief.py` deduplicates near-identical facts by content-token containment and composes at most two grounded facts per section. `refine_briefs.py` can re-run the quality checks on saved briefs without a model call. When model analysis is unavailable, `evidence_research.py` publishes verbatim excerpts explicitly labelled `evidence_only`, with no implied verdict.

## Evidence and trust invariants

- A citation is only rendered as verified after its quotation is found on the cited extracted page.
- A numerical claim must appear in its quotation; no number is inferred or synthesized.
- Unknown or mismatched definitions produce a non-definitive state rather than a guessed verdict.
- Coverage is stated: snapshot date, stale sources, fallback-feed holdings and document counts are visible.
- Secrets live only in the ignored root `.env` or server environment. Generated extracts are public evidence, not credentials.

## Reliability and cost control

- JSON writes are atomic (temporary file + rename).
- Research jobs are serialized, bounded, run in their own process group and write progress to `data/.jobs/`; a timeout terminates the whole group.
- Groq calls validate structured responses, cache by provider/model/prompt/schema (SHA-256), reserve a shared rolling token budget across processes, respect Retry-After delays and stop on daily quota errors.
- `fetch_prices.py`, `generate_push.py` and `ground.py` are independently runnable, and `monitor.py --once` performs one refresh cycle for a host scheduler.

## Frontend boundaries

- All market and research data is fetched from same-origin API routes; long-lived credentials never reach the browser.
- `/api/research` serves saved research when live research is disabled and starts a bounded job when `FINN_ENABLE_RESEARCH=1`.
- `/api/source` only serves extracted pages for a requested symbol and known document, resolving paths inside `data/docs` and rejecting traversal.
- The mobile layout is the primary surface: a prioritised feed, a portfolio table, and a research view with Overview, Management memory and Evidence room. The desktop layout adds a sidebar and context column.

## Deployment boundary

Research requires a process that outlives a single HTTP request and writes to a persistent volume. Serverless functions are explicitly unsupported. The included Dockerfile runs the Next.js server and the Python virtual environment together; persist `/app/data` and generated research across container replacements. `FINN_ROOT` and `FINN_PYTHON` support non-default absolute paths. `FINN_MONITOR=0` starts only the web server, which is how the public demo keeps the committed snapshot stable while still running research on demand; without a mounted volume, newly generated research and saved preferences reset on restart.
