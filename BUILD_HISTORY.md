# AI build history

FINN was built across two AI-assisted sessions. The initial build was done in Gemini; that conversation is shared at https://share.gemini.google/emH3nUzIRlpg. The work was then continued and completed in a Qoder desktop agent session on **3 November 2026** (Claude-based coding agent with file, shell, browser and Sites tools). This page is a curated export of the Qoder session: the verbatim user requests, the milestones the agent reported, and the engineering decisions behind them. The full session transcript is available from the author on request.

## Verbatim requests

| Time (UTC) | Request |
| --- | --- |
| 04:42 | "there is two pdf files of assignment details read that first and remember" |
| 04:47 | "now read all code files(all python and frontend ) all first and check how much work has done except deployment in % also check perfection or grading point of view how much is done" |
| 05:00 | "make a plan for perfection and completion of assigment according to get highest grading" |
| 05:05 | "now work and complete this assigmnet" |
| 06:04 | "is all done check at grading scope" |
| 06:15 | "so i have time so improve it also frontend should not content any thing not working should be good simple to use easy and all functionable if not then remove" |

The agent then worked autonomously through verification, product fixes, the submission pack and deployment, followed by a grading audit and a second improvement pass.

## Milestones reported during the build

| Time (UTC) | Milestone |
| --- | --- |
| 04:43 | Read both assignment PDFs and saved the FINN spec (Push/Pull modes, primary-source-only research, deliverables) to project memory. |
| 04:47–04:50 | Inventoried ~2,660 lines of Python across 30 modules and the Next.js frontend; read every source file, test and API route. |
| 04:48 | Ran the existing suite: 65 tests, ESLint and production build all green. |
| 04:50 | Found the flagship promise had a reporting-scope gap: INFY's FY26 revenue outcome was known but not provably comparable. |
| 04:56 | Delivered the audit: ~78% complete excluding deployment, with a grading-oriented gap list. |
| 05:02 | Located the decisive primary source: the FY26 annual report states the constant-currency revenue outcome on a consolidated basis on page 78. |
| 05:05–05:10 | Added verified scope evidence (`scope_evidence.py`), regenerated INFY research, and reached **MET** without weakening any comparison guard. |
| 05:13 | Tightened fact-quality filters and near-duplicate suppression, then re-ran the saved briefs. |
| 05:18 | Diagnosed "Filing previews: 0" as stale evidence outside the 24-hour window and enriched the five current material filings. |
| 05:24 | Verified the INFY MET card, both citations, the scope note and the full page extract in the browser; no console errors and no mobile overflow. |
| 05:31 | Re-ran the full suite (66 tests), lint and build; wrote the dedicated submission repository with secrets excluded. |
| 05:34 | Added a static export path for Qoder Sites; verified the saved briefing, all six research briefs and citation extracts in the static build. |
| 05:40 | Published the public demo and dedicated repository. |
| 06:04–06:10 | Audited the build against the grading scope and reported the remaining gaps: quarterly tables, leadership profiles, a cross-quarter promise grid and live research on the static host. |
| 06:12 | Fixed results filings being relabelled by words in the exchange summary: classification now reads only the filing title, with results ranked ahead of M&A. Added collapse of duplicate results filings so one event yields one priority card. |
| 06:18 | Extracted and page-verified the ITC consolidated quarterly table (Revenue, PBT, QoQ, YoY); EBITDA and PAT remain unavailable rather than repaired after OCR and absent-figure checks. |
| 06:24 | Removed static-demo dead ends: research now opens from a saved-brief picker, unsaved symbols explain themselves, and the error action offers a working route back to the shelf. |
| 06:32 | Re-ran 68 tests, ESLint and both builds, reset saved preferences to defaults, and republished the improved static export. |

## Key engineering decisions

1. **Fail closed.** A verdict is emitted only when period, metric, unit, accounting basis and consolidation scope match on both sides, and every number appears in a verified quotation. Unknown definitions yield `NOT_COMPARABLE`; unfinished periods yield `PENDING`. No guard was relaxed to manufacture a green badge.
2. **Scope evidence is cited, not assumed.** When the annual report states consolidation scope for the same metric and period, a separately page-verified quotation fills the missing field on both sides. It never overwrites a value or an existing scope, and the UI explains the reasoning.
3. **One real verdict is better than several weak ones.** FY26 revenue is `MET` (3–3.5% guidance vs 3.1% reported, constant currency, consolidated). FY26 operating margin stays `NOT COMPARABLE` because the available observation covers a quarter, not the full year.
4. **Coverage is stated.** The briefing shows its snapshot date, holdings on a limited fallback feed, sources that could not refresh, and the document counts behind each research brief.
5. **Cost and reliability are bounded.** Research uses strict structured outputs, bounded chunk selection, shared rate pacing, response caching and an atomic job queue. Numeric matching and filing previews use no model tokens.
6. **The demo runs the real pipeline.** The live demo runs the same Node + Python container as the local setup: research is executed on demand, preferences are saved server-side, and the saved snapshot and six briefs load instantly. Scheduled refresh is switched off on the demo host so a throttled price source cannot make the briefing look stale during review. The static export remains available for zero-backend hosting, where it labels live research as unavailable rather than pretending to run a Python job.
7. **A filing is classified by its title.** Exchange summaries appended to headlines describe many things; only the title decides the category, and companions to one results event are visibly grouped instead of inflating the priority desk.
8. **Every visible control has a working path.** On the live demo, an unsaved holding starts a real research job and shows its stage. In the static build, research is a picker of the six saved briefs and an unsaved holding shows a notice with a working "Browse saved briefs" action, never a retry that can only fail.

## Artifacts

- Live demo: https://finn-4pi0.onrender.com/
- Repository: https://github.com/sandeep14k/FINN
- Verification log: [TEST_RESULTS.md](TEST_RESULTS.md)
- Architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
