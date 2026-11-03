# Covering note

Subject: ENAM - IIT screening - 2027

Hello ENAM team,

I built FINN around one investor workflow: a prioritised portfolio disclosure desk connected to an evidence-backed management promise check.

Prototype: [ADD DEPLOYED URL]
Repository: [ADD DEDICATED GITHUB URL]
AI build history: [ADD ACTUAL EXPORT OR SHARE LINKS]

The workspace tracks 18 Indian listed companies. Investors can change the digest window (24h / 3d / 7d / all), filter by holding or category, set price and volume thresholds, mark items reviewed, and inspect original filings. The briefing states its own coverage: the saved snapshot date, holdings on a limited fallback feed, and any sources that could not refresh. Five material filings expose a verbatim "Inside the filing" preview with a page number and a link to the original PDF.

The research side starts from an NSE symbol, discovers recent earnings-call transcripts and annual reports, and builds a brief where every statement carries a quotation and a page. The demo includes INFY, KPITTECH, ETERNAL, LAURUSLABS, HCLTECH and unseen-ticker ingestion checks with TCS. For INFY, the Management memory view reconstructs the FY27 revenue guidance revisions (1.5–3.5%, then 1.5–3%, then 1–2%) and unchanged 20–22% margin guidance. It also reaches one real delivery verdict: FY26 revenue guidance of 3–3.5% constant currency is **MET** by the reported 3.1%. Both sides cite the Q3 and Q4 FY26 calls, and a separately verified annual-report statement fixes the consolidated reporting scope without altering either value. FY26 operating margin is **NOT COMPARABLE** because the reported observation covers a quarter, not the year. FY27 targets are **PENDING**. When a definition cannot be verified, the product shows that uncertainty rather than inventing a score.

Research uses Groq with bounded extraction, strict structured outputs, shared rate pacing and response caching to control cost. Numeric comparisons, period matching and citation verification are deterministic; explicit guidance patterns and filing previews need no model tokens. Every quotation is checked against the extracted page before it is published. An interim quarter never counts as annual delivery. The saved snapshot keeps the demo usable without model access, and a missing key or provider failure falls back to clearly labelled verbatim evidence with no verdict.

I deliberately left out exhaustive exchange pagination, continuous notification delivery, OCR for scanned filings, automated quarterly financial tables and executive biographies. Next I would widen exchange coverage, make research a durable worker queue, and add authentication plus shared rate limits for multi-user use.

[ADD YOUR NAME]

# Before sending

- Replace every placeholder above.
- Run the documented integrity, lint and production-build checks; `TEST_RESULTS.md` records the checks actually run.
- Create the dedicated repository rooted at Finn and confirm `.env`, `venv/`, `node_modules/` and `.next/` are not committed.
- Deploy on a host that supports a persistent Node/Python process and external source access; serverless functions cannot run the research job.
- Open the deployed URL from a fresh browser session and on an actual phone.
- Confirm the displayed snapshot date and coverage notices match the refreshed data.
- Attach or link the actual AI build conversations.

Extended deadline confirmed by the user: 3 November 2026 EOD.

# Submission message

To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Body: the covering note above, with the deployed URL, repository URL and build-history links, sent from the candidate's email address.
