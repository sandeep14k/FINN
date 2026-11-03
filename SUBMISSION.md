# Covering note

Subject: ENAM - IIT screening - 2027

Hello ENAM team,

I built FINN around one investor workflow: a prioritised portfolio disclosure desk connected to an evidence-backed management promise check.

Prototype: https://finn-attention-desk-13oolrbrhrs.qoder.website
Repository: https://github.com/sandeep14k/FINN
AI build history: [BUILD_HISTORY.md](BUILD_HISTORY.md) (curated transcript of the coding-agent session, with the prompts and decisions that shaped the build)

The workspace tracks 18 Indian listed companies. Investors can change the digest window (24h / 3d / 7d / all), filter by holding or category, set price and volume thresholds, mark items reviewed, and inspect original filings. The briefing states its own coverage: the saved snapshot date, holdings on a limited fallback feed, and any sources that could not refresh. Five material filings expose a verbatim "Inside the filing" preview with a page number and a link to the original PDF.

The research side starts from an NSE symbol, discovers recent earnings-call transcripts and annual reports, and builds a brief where every statement carries a quotation and a page. The demo includes INFY, KPITTECH, ETERNAL, LAURUSLABS, HCLTECH and unseen-ticker ingestion checks with TCS. For INFY, the Management memory view reconstructs the FY27 revenue guidance revisions (1.5–3.5%, then 1.5–3%, then 1–2%) and unchanged 20–22% margin guidance. It also reaches one real delivery verdict: FY26 revenue guidance of 3–3.5% constant currency is **MET** by the reported 3.1%. Both sides cite the Q3 and Q4 FY26 calls, and a separately verified annual-report statement fixes the consolidated reporting scope without altering either value. FY26 operating margin is **NOT COMPARABLE** because the reported observation covers a quarter, not the year. FY27 targets are **PENDING**. When a definition cannot be verified, the product shows that uncertainty rather than inventing a score.

Research uses Groq with bounded extraction, strict structured outputs, shared rate pacing and response caching to control cost. Numeric comparisons, period matching and citation verification are deterministic; explicit guidance patterns and filing previews need no model tokens. Every quotation is checked against the extracted page before it is published. An interim quarter never counts as annual delivery. The saved snapshot keeps the demo usable without model access, and a missing key or provider failure falls back to clearly labelled verbatim evidence with no verdict.

The hosted demo is a static export of the saved snapshot, six cached research briefs and their page extracts. It deliberately disables live new-ticker research and server-side refresh; the same repository runs the full Node + Python pipeline locally or in the included Docker image, where those are enabled. I made that trade-off so the assessment link is fast, stable and cannot fail because of a free-tier model quota during review.

I deliberately left out exhaustive exchange pagination, continuous notification delivery, OCR for scanned filings, automated quarterly financial tables and executive biographies. Next I would widen exchange coverage, make research a durable worker queue, and add authentication plus shared rate limits for multi-user use.

Sandeep Kumar Jha

# Three-minute demo route

1. Open the briefing: 21 prioritised items, 9 disclosures in the feed, 13 market-move alerts and 5 filing previews. Point out the coverage notices (snapshot date, fallback-feed holdings, stale sources).
2. Expand "Inside the filing" on an ITC disclosure and follow "Verify original page" to the exchange PDF.
3. Open Preferences, lower the price threshold, save, and confirm the digest changes; reload to show preferences persist.
4. Open INFY research → Overview, then Management memory. Show the FY27 guidance revisions and the FY26 Revenue Growth **MET** card: promise quote, delivery quote, annual-report scope citation and the scope note.
5. Open the Annual report p.78 citation, show "Quotation matched against this extracted page", and expand the full page extract.
6. Show FY26 margin **NOT COMPARABLE** and FY27 **PENDING** to make the judgment call explicit, then open an evidence-only company (HCLTECH or TCS) and an invalid ticker error.

# Before sending

- If a Qoder session share link exists, add it next to `BUILD_HISTORY.md`; the committed curated export is sufficient on its own.
- `TEST_RESULTS.md` records the checks actually run: 66 Python tests, ESLint, production build, static build and browser verification.
- The dedicated repository is public and its tracked files exclude `.env`, `venv/`, `node_modules/`, `.next/`, `out/` and internal planning notes.
- The live demo is public and was verified in a fresh browser session. A real-phone check is still recommended.
- Confirm the displayed snapshot date and coverage notices match the refreshed data.

Extended deadline confirmed by the user: 3 November 2026 EOD.

# Submission message

To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Body: the covering note above, with the deployed URL, repository URL and build-history link, sent from the candidate's email address.

