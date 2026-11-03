# FINN — an investor's attention desk

FINN is a mobile-first portfolio attention desk plus a primary-source management memory. It includes verified guidance revision timelines, delivery checks, filing previews and a persistent reviewed/unreviewed feed. The deliberate scope is two connected workflows: identify a disclosure worth attention, then inspect management's promises and the reported evidence.

Live demo: https://finn-attention-desk-13oolrbrhrs.qoder.website · AI build history: [BUILD_HISTORY.md](BUILD_HISTORY.md)

The hosted demo is a static export of the saved snapshot and six cached research briefs. Live new-ticker research and scheduled refresh run in the local/Docker build described below, not in the static demo.

## Run locally

Use Python 3.13 and Node 20.9+ (the supplied environment uses Python 3.13 / Node 20).

```sh
python3.13 -m venv venv
venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
# Set GROQ_API_KEY in .env. Default: qwen/qwen3.8-27b.
cd finn-app
npm ci
npm run dev
```

Open http://localhost:3000. The saved portfolio snapshot and cached research work without calling an LLM. The snapshot toggle explicitly anchors filtering to the saved data date; turn it off to use the current clock.

For new ticker research, restart the frontend with:

```sh
FINN_ENABLE_RESEARCH=1 npm run dev
```

The server must have access to the root Python virtual environment and `.env`. Research runs as a bounded, serialized background subprocess on the same persistent host. It is **not compatible with serverless function lifecycles**. Cached research remains available with live research disabled.

## Groq setup

Create an API key in https://console.groq.com/keys and set `GROQ_API_KEY` in the root `.env`. Existing Gemini credentials are preserved locally but are no longer used. No extra SDK is required: the client uses the existing `requests` dependency and Groq's strict JSON-schema endpoint.

```sh
venv/bin/python check_groq.py
venv/bin/python run_pull.py KPITTECH
```

Model extraction defaults to `qwen/qwen3.8-27b`. Set `GROQ_FAST_MODEL` to another Groq model that supports strict structured outputs. Financial matching and verdicts are deterministic and do not call an LLM; `GROQ_REASONING_MODEL` is retained only for compatibility. `openai/gpt-oss-120b` is another documented option.

The client validates responses, caches by provider/model/prompt/schema, reserves a shared rolling token budget across pipeline processes, respects short Retry-After delays, and stops on daily quota errors. Set `GROQ_TOKENS_PER_MINUTE` to match your account (default 7,000 conservatively below the documented 8,000 free-tier tokens/minute). `GROQ_MAX_OUTPUT_TOKENS` defaults to 1,800. Estimates are conservative rather than an exact model tokenizer; the provider's limits remain authoritative. See https://console.groq.com/docs/rate-limits and https://console.groq.com/docs/structured-outputs.

Selected financial excerpts are split into chunks of at most 4,500 characters, with real page markers and boundary overlap. Extraction ranks up to six chunks per transcript for outlook relevance and document coverage, plus up to two focused full-year excerpts for Q4 calls. Annual-report snapshots review up to three chunks. Narrow source-pattern extraction also recovers explicit percentage guidance without model tokens. Comparisons use canonical financial metrics, reporting periods and deterministic checks. This is bounded coverage, not an exhaustive reading of every document. Free-tier jobs may take 10–30 minutes; the local server permits a maximum of 30 minutes per research job. Missing credentials or API failure produce explicitly labelled evidence-only research.

Saved research is not regenerated merely by adding a key: run `run_pull.py SYMBOL` to replace an existing cached research result. Cached model responses can also satisfy the connection check; a successful connection check is not a complete company-analysis test.

## Refresh and research

From the repository root:

```sh
venv/bin/python refresh.py
# Optional: attach verbatim previews from five material exchange filings.
venv/bin/python enrich_push.py --limit 5
venv/bin/python run_pull.py INFY
venv/bin/python run_pull.py KPITTECH
venv/bin/python run_pull.py ETERNAL
venv/bin/python run_pull.py LAURUSLABS
```

Refresh fetches EOD prices, announcements and republishes the portfolio digest. Saved research includes INFY, KPITTECH, ETERNAL, LAURUSLABS, TCS and HCLTECH. INFY shows verified FY27 revenue and operating-margin guidance histories. Its FY26 revenue guidance (3–3.5% constant currency) is **MET** by the reported 3.1%; both sides cite the Q3/Q4 FY26 transcripts and a separately verified annual-report page that fixes consolidated reporting scope. FY26 operating margin remains **NOT COMPARABLE** because the reported observation covers a quarter, not the full year, and FY27 targets remain **PENDING**. KPITTECH currently has annual-report facts but no extracted comparisons. ETERNAL, LAURUSLABS and TCS show verbatim evidence only. TCS was ingested as an unseen-ticker generalisation check. The API returns saved research until it is explicitly regenerated.

Run it after market close using your host's scheduler. No browser push notifications or continuous polling service is included.

Research discovers up to five recent transcripts and one annual report, extracts text, labels periods, extracts guidance and actuals, matches them, then verifies quotations against extracted pages. Explicit quarter-ended dates override inferred document labels. URL hashes prevent similarly named documents from colliding. Scanned/empty documents are rejected. Each job exposes its current pipeline stage. Annual-report facts are retained only when their quotations verify. Primary-source excerpts and generated outputs are published into `finn-app/public/data/`.

`styles.mjs` compiles Tailwind before production builds and watches source edits during development, avoiding a separate Next CSS loader worker.

`ground.py` rejects legacy or mismatched reporting periods, and flags quotations that cannot be verified. An interim quarter does not establish annual delivery. Matching metric, unit, accounting basis and consolidation scope is checked before calculating scores. Numbers must also occur in the cited quotations. Unknown consolidation scope can be resolved by an optional `data/docs/<SYMBOL>/scope_evidence.json` record only when its quotation verifies against the cited page and the reported value appears in that quotation; evidence fills the missing scope field and is shown in the UI, never overwriting a value (`scope_evidence.py`). Semantic interpretation still needs investor review.

## Test

From the root:

```sh
venv/bin/python -m unittest discover -s tests -v
npm --prefix finn-app run lint
npm --prefix finn-app run build
```

See `TEST_RESULTS.md` for the checks actually run and their limits.

Then start the production server **from `finn-app/`**:

```sh
cd finn-app
npm start
```

Manual acceptance checks at a 390px mobile width:

1. Change 24h / 3d / 7d / all; confirm counts change with the snapshot date.
2. Select a holding; confirm every visible card belongs to it.
3. Lower price and volume thresholds; save and confirm alerts update. Reload and confirm preferences persist.
4. Expand routine disclosures and open an exchange filing.
5. Open saved INFY research → Management memory. Inspect the FY27 revenue guidance timeline (1.5–3.5%, 1.5–3%, 1–2%) and unchanged margin guidance. FY26 revenue is `MET` with consolidated scope explained; FY26 margin is `NOT COMPARABLE`; FY27 delivery checks remain `PENDING`.
6. Open a citation; expand the full page and verify the quote and page number.
7. Try another ticker with live research enabled; wait for completion and inspect its own evidence. Try an invalid ticker and confirm an error rather than an endless spinner.
8. Turn off snapshot anchoring to verify the current-time empty state when data is old.
9. Test Escape, keyboard focus, and 390px / desktop layouts.
10. Mark visible items reviewed, select Unreviewed only, reload and confirm review state persists.
11. Expand a material filing preview and check its exact quotation against the linked original page.

## Deployment

Build with `npm run build` inside `finn-app/`, then run `npm start` on a persistent Node/Python host. Keep the complete root directory and virtual environment alongside the app. Set `FINN_ENABLE_RESEARCH=1` and the root API key server-side; never use a `NEXT_PUBLIC_` key. `FINN_ROOT` and `FINN_PYTHON` support custom absolute paths.

For static hosting, run `npm run build:static` inside `finn-app/`. It exports `out/` with the saved snapshot, cached research and published page extracts; the build temporarily parks `app/api`, and the client reads `/data/*.json` directly. Live research, refresh and server-saved preferences are unavailable in this mode, and preferences fall back to `localStorage`. The static build is what the Qoder Sites demo uses.

Alternatively use the included Dockerfile. Supply `GROQ_API_KEY`, `GROQ_FAST_MODEL` and `GROQ_REASONING_MODEL` at runtime. Persist `/app/data` and generated public research if you need it across container replacements. The included job queue is single-process; use one application instance for this prototype.

## Known scope limits

- The checked-in feed is a saved snapshot, not a claim of live market coverage.
- Screener's latest-announcement list is limited; full exchange pagination and exhaustive window coverage are not implemented.
- Real source hosts can rate-limit or block downloads. Scanned PDFs need OCR, which is not included.
- Partial refresh failures retain prior company records and publish stale-source indicators. Announcement ingestion still cannot distinguish every empty feed from upstream failure.
- No fabricated quarterly financial widgets: results are linked to their actual filings. Automated Revenue/EBITDA/PBT/PAT tables and incoming-executive bios remain out of scope.
- Cached research is available only for successfully generated tickers. If model access fails, the pipeline explicitly falls back to verified verbatim excerpts; these carry no promise-delivery verdict.
- Public multi-user research needs durable jobs, shared rate limits and authentication. The current queue is intended for an assessment demo.

## Submission

See `SUBMISSION.md` for a covering-note draft and final checklist. Include a deployed mobile URL, a dedicated GitHub repository, and your actual AI build history. The PDFs ask for subject `ENAM - IIT screening - 2027` and delivery to `assessment@enam.com`.

## Submission schedule

The user-confirmed extended deadline is **3 November 2026, end of day**. Deploy on a persistent Node/Python host and complete a real-phone check before submission. The local project currently inherits a parent Git repository; create a dedicated repository rooted at Finn before publishing.
