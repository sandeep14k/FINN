# Validation — 3 November 2026

## Automated checks

- **68 Python tests pass**: Ran 68 tests in 1.179s — OK (`venv/bin/python -m unittest discover -s tests`).
- **ESLint passes**: `npm --prefix finn-app run lint`.
- **Production build and TypeScript pass**: `npm --prefix finn-app run build`.
- Tests cover partial price and announcement failures preserving previous company records, total price failure preserving the snapshot, prior-20-session volume calculation, canonical metric distinctions, complete-period candidate preference, future guidance, unsupported numeric values, wrong-page quotations, document-period inference, chunk relevance selection, Groq request validation/cache isolation/rate pacing, missing credentials, scope-evidence verification, source-path traversal rejection and cache identity.

## Browser checks (in-app browser, 568px viewport)

- **Briefing**: 16 priority items (3 disclosures plus 13 market-move alerts), 9 disclosures in the feed, 13 market-move alerts and 5 filing previews render in the default 24-hour window. The coverage notice states that 18 holdings use a limited fallback feed, and stale sources (KPITTECH, POLYCAB, INDHOTEL) are named with retained previous data.
- **Quarterly results**: the ITC consolidated-results card shows Revenue 30,578.4 / 29,523.3 / 21,255.86 with QoQ +3.57% and YoY +43.86% and PBT 5,694.62 / 5,860.85 / 6,978.68 with QoQ −2.84% and YoY −18.40%, each from the verified filing page. EBITDA is absent from the filing and PAT fails the verbatim-value check after an OCR error, so both render as "—" rather than being repaired. On narrow screens the table becomes one labelled tile per metric, so no column is cut off. Two companion ITC filings are labelled as companions under "Other disclosures" instead of repeating the results card.
- **Filing previews**: the five newest material filings expose an "Inside the filing" excerpt with a page number and a link to verify the original page.
- **INFY research, Management memory**: the summary reads "1 verified delivery verdict; 2 pending targets; 2 guidance histories." FY26 Revenue Growth shows **MET**; the promise (Q3 FY26 guidance, p.4) and delivery (Q4 FY26 actual, p.4) both cite the verified Annual report p.78 statement, and the scope note explains that the annual report fixes consolidated reporting scope without altering either value. FY26 Operating Margin is **NOT COMPARABLE**; both FY27 targets are **PENDING**.
- **Citation inspection**: the Annual report p.78 citation opens "Quotation matched against this extracted page", shows the verified quotation, and loads the 5,110-character page extract from `/api/source`.
- **Layout**: `document.scrollWidth` equals the viewport at 352px, 390px and 568px (no horizontal overflow); the mobile navigation is visible and the desktop sidebar is hidden.
- **Console**: no browser console messages or exceptions.
- **Static deployment build**: `npm --prefix finn-app run build:static` produces a static `out/` export. Served locally, it renders the same 16/9/13/5 briefing, the ITC results table, all six saved research briefs, the INFY MET card and scope note, and the verified annual-report page extract. Research entry uses a picker of the six saved briefs; an unsaved holding shows a notice with a "Browse saved briefs" action instead of a retry that cannot succeed. Live research and server-saved preferences are intentionally unavailable in that build; preferences stay in `localStorage`.

## Hosted deployment (Render, public)

- **URL reachable**: `https://finn-4pi0.onrender.com/` returns HTTP 200 and serves the product.
- **Same data as local**: `/api/snapshot` reports `as_of` 2026-11-03 with 18 holdings and the committed feed; the interface renders the same 16 priority items (3 disclosures plus 13 market-move alerts), 9 disclosures, 13 market-move alerts and 5 filing previews. KPITTECH, POLYCAB and INDHOTEL are listed as stale with retained previous data, and all 18 holdings carry the limited-feed notice.
- **Server-saved preferences**: `GET /api/preferences` returns the stored rules and `POST` writes and echoes them with HTTP 200, so saving works on the container filesystem rather than only in `localStorage`.
- **Citations**: `/api/source?symbol=INFY&file=ar_annual_report_2026_from_bse_ai_summary.json&page=78` returns the extracted annual-report page from the container.
- **Live research**: `GET /api/research?symbol=INFY` returns the cached brief, while `POST` for `WIPRO` — outside the saved six — returned 202. In the browser, submitting `WIPRO` opened "COMPANY RESEARCH · WIPRO" and the run advanced through "Discovering annual reports and earnings-call transcripts", "Identifying reporting periods", "Reading the annual report" and "Extracting guidance and reported results", with the note that a run can take several minutes. The Python pipeline runs on the host; this is not a static fallback.
- **Scheduled refresh off by design**: `FINN_MONITOR=0` keeps the committed snapshot stable during review. The same image runs the 15-minute refresh loop with `FINN_MONITOR=1`.
- **Host behaviour**: a free instance sleeps after about 15 minutes idle, so the first visit can take roughly a minute; a restart resets newly researched tickers and preferences to the committed state, while the snapshot, six briefs and citation extracts are part of the image.

## Real source validation

- Live Groq extraction completed against existing INFY primary-source transcripts. A focused annual-results pass recovered a verified FY26 full-year constant-currency growth observation of 3.1% on page 78 of the annual report.
- Explicit-source percentage-guidance recovery reconstructs INFY's FY27 revenue guidance timeline: 1.5–3.5%, 1.5–3%, then 1–2%. Operating-margin guidance remains 20–22%. Every published timeline quotation is checked against its stated extracted page. Annual periods inferred from call context are disclosed in the view.
- Numeric matching does not call an LLM. A definitive verdict requires matching period, metric, unit, accounting basis and consolidation scope, and every value must appear in the verified quotation. Scope evidence is accepted only when its quotation verifies against the cited page; it never overrides a value.
- TCS, outside the original demo set, successfully ingested four transcripts and one annual report and published verbatim excerpts. One additional transcript returned HTTP 403 and was skipped. This validates unseen-ticker source discovery and evidence publication, not complete model-scored research for TCS.
- Five material exchange filings were downloaded and their verbatim previews verified against the stated pages. No model calls are used for previews.
- A duplicate July document label found during TCS ingestion exposed a source-map collision. New filenames include a URL hash; successful legacy TCS source associations were checked against the download URL hash and repaired. A regression test covers distinct documents with identical labels.

## Failure-path checks

- Research POST rejects invalid or empty tickers before starting a job.
- Unknown, missing or mismatched scope/basis/period produces NOT_COMPARABLE or PENDING rather than a guessed verdict.
- A scope quotation that fails page verification, or a value absent from its quotation, cannot upgrade a comparison.
- Partial feed failures preserve previous records and surface stale holdings instead of silently dropping them.
- An in-progress intraday bar is not published as an end-of-day close before 15:30 IST.

## Remaining limits

- The hosted deployment was verified from this machine; a real-phone network test was not performed. Render built the container image from the committed Dockerfile, so the image itself is proven on a clean host, but its behaviour on a physical phone network is not.
- Consolidation/accounting scope is source-supported for INFY FY26 revenue only; other saved comparisons remain non-definitive.
- Exhaustive exchange coverage, background push notifications (a service worker) and OCR remain outside this implementation. An open tab does poll saved data every minute and can raise a browser notification with permission.
- Quarterly results tables and management profiles are extracted for the filings in the saved analysis, not for every holding or every historic filing; extraction is model-driven with page and verbatim checks, so an unreadable figure is shown as unavailable rather than repaired.
- An apparent credential was removed from `.env.example`; provider-side revocation/rotation was not performed.
