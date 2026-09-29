# Shortcut PRD v1.1: Build on ATU's own planning tools

Owner: Yengnong Xiong · Status: Shipped · 2026-09-29 · Extends [PRD.md](../PRD.md) v1 · Build plan: [plans/2026-09-29-atu-sources-plan.md](plans/2026-09-29-atu-sources-plan.md)

## 1. Why this release

Shortcut v1 treats ATU's planning tools as background. A student at ATU already has three official sources, and each one answers part of the question Shortcut is built around:

| Source | What it answers | What it can't answer |
|---|---|---|
| **Academic catalog** (catalog.atu.edu) | The rules: course prerequisites, AP/CLEP/IB credit tables, graduation and repeat policies | How the rules combine into a schedule for one student |
| **Degree maps** (one PDF per major, per catalog year) | The average path: 8 semesters for a first-time freshman admitted that year | Anything personal: prior credit, summer, a failed course |
| **Degree Works** (the registrar's degree audit) | The official record: what's done, in progress, and still needed | When to take what's left, in what order, and how fast it could go |
| **Shortcut** | When and in what order, the fastest realistic finish, and the price of each option | Official status. It's a planning aid, not an audit |

These tools compete with Shortcut for the student's attention, but they're also its best inputs. v1.1 makes Shortcut **start from them**:
- **Catalog:** use the catalog's own AP/IB/CLEP tables and policies, and link each course back to its catalog entry.
- **Degree maps:** plan against the map for the student's **catalog year**. A Fall 2025 admit follows the 2025–26 map, and a Fall 2026 admit follows 2026–27.
- **Degree Works:** import the student's audit so setup takes seconds, then show where the audit and the plan agree.

Positioning stays: *the degree map is the path for the average student; Shortcut is the path for you*. It's now reached by importing the audit rather than retyping it.

## 2. Evidence from a real audit

Before this release, the owner's own record (a Fall 2025 CS admit whose Degree Works audit is dated 2026-08-19) exposed two gaps:
1. **Posted exam credit has no home.** Degree Works lists AP and CLEP credit as already-awarded courses (grade `CE`, "Satisfied by: AP07 - COMPUTER SCIENCE A"). v1 only accepts raw exam *scores*, and only CLEP. The workaround, entering the courses as "transfer", skips the exam-credit cap.
2. **Unapplied credit is easy to leave out, and it matters.** The audit shows 4 hours that don't apply to the degree but still count toward class standing. Leaving them out puts the student one hour short of senior standing before a fall-only capstone, and the plan slips a full year (May 2028 → May 2029).

Both gaps go away when the audit is the input instead of manual entry.

## 3. Scope

### 3.1 Catalog (catalog.atu.edu)
- **Snapshots.** The catalog sits behind a bot challenge (v1 D5), so the pipeline can't fetch it. A person opens each page once in a normal browser and saves it under `data/raw/catalog/`. The pipeline parses those snapshots offline, with the capture date recorded. Automated code never works around the challenge.
- Pages captured:
  - Institutional credit, plus its AP, CLEP, and IB subpages
  - Graduation requirements
  - Regulations and procedures (catalog-of-entry, repeat, and load rules)
- **AP and IB credit.** Parse the AP table (55 rows) and the IB table into `data/processed/exams/ap.json` and `ib.json`, replacing the current "unavailable" stubs. Map exact course codes only. Rows like "3 hours General Education Humanities" become non-course credit, not a guessed course.
- **CLEP.** Parse the live catalog table and diff it against PRD Appendix B. The catalog wins, and any differences are logged in the decisions log.
- **Policy refresh.**
  - Re-read the exam/prior-learning cap. The institutional-credit page now says 50% of the degree. If the graduation-requirements page no longer says 30 hours, the "conflicting" label and the stricter-value rule are retired.
  - Add the catalog-of-entry rule, with its source.
- **Course links.** Every course chip, bottleneck node, and export row links to the course's catalog entry.

### 3.2 Degree maps for every catalog year
- Discovery ingests **every catalog year listed on the degree-map index** (today 2025–26: 81 maps; 2026–27: 82), instead of the newest year plus CS 2025–26.
  - Program ids already carry the year (`accounting-2025-26`).
  - Validation, trust tiers, and REPORT.md are produced per year.
  - Course data (prerequisites, offerings) comes from the current Banner catalog for both years. That's a documented assumption.
- **Picker.** One entry per major, with a catalog-year choice. The default is derived from the first ATU term: a fall or spring start in academic year Y uses Y's map. Copy: "Use the map for the year you started. Your catalog year is on your Degree Works audit."
- **"Switch to a newer catalog?" what-if.** Re-plan the same credits against the newer year's version of the major, and show the date change and which requirements differ.
  - Majors pair across years by map filename.
  - A small manual table handles renames and splits (2025–26 Computer Science → 2026–27 CS: AI and CS: Software Development).
  - The what-if cites the catalog-of-entry policy.

### 3.3 Degree Works import
- **Flow.** Landing page and Setup step 1 get a new "Start from your Degree Works audit" action. The student saves the audit as a PDF from Degree Works and drops it in.
- **Privacy by design.**
  - The PDF is parsed **in the browser** with pdf.js, loaded only when needed, and never uploaded.
  - Name and student ID are never read into the profile.
  - Only course codes, grades, and terms reach the planner, the same as manual entry.
  - The page says this in plain words.
- **What's read:**
  - Degree, major, and catalog year pick the program version.
  - Each course row gives its code, grade, credits, and term.
  - `CE` rows with "Satisfied by: … Credit by AP/CLEP Exam" become **posted exam credit**.
  - `IP` rows are in progress.
  - Transfer rows keep their source.
  - The "Not Used" section counts toward total hours and standing.
  - Overall GPA sets the 3.25+ overload expectation, labeled as an assumption.
  - First ATU term and the first term still to plan are inferred from ATU-taken terms.
- **Review before applying.** A summary shows the program, catalog year, and counts of completed courses, exam credit, and in-progress courses, plus any rows that weren't recognized. The student confirms or edits, then goes straight to the plan.
- **Model change.** `CompletedCourse.source` gains `"exam"`. It counts toward total hours, standing, and the exam-credit cap, and never toward residency or GPA (PRD §8).
- **Audit vs. plan panel.** Shown when a plan came from an audit.
  - Compare the audit's "Still needed" lines with Shortcut's remaining requirements: "Agrees on N of M", then a list of items only in the audit and items only in Shortcut.
  - Also compare credits applied.
  - Disagreements are shown as information, not errors: for example, Degree Works accepts more science-with-lab courses than the map lists. The advisor-export copy tells the student to bring them to the advisor.

### 3.4 Presentation (README, About page)
- The "Where it fits" section becomes the table in §1, with a column for how Shortcut uses each source.
- A "How it was built" section: the owner wrote the PRD and acceptance tests and directed Claude Code, and the decision log records every judgment call. CLAUDE.md is rewritten as the build brief for agents, without the overnight-run instructions.
- One anonymized line about the owner's own result (outcome only; no grades, GPA, or ID), updated after the fixes above.
- Refreshed numbers and resume bullets.

### 3.5 Visual design: minimal
The owner's direction: very simple and minimal, so it doesn't read as generated.
- **Color:** white background and black text only, with grays for borders and secondary text. The one exception is red, reserved for errors that block a plan. There are no accent colors for "critical" or "time saved"; those are shown in words and weight ("Critical" label, bold).
- **Type:** one sans-serif family (the system UI font) for everything, and no display serif. Monospace only for course codes.
- **Shape:** slightly rounded corners (6px) and 1px gray borders. No shadows, gradients, tinted panels, or colored top borders.
- **Icons:** the logo mark is removed, and the wordmark is text. Other icons are kept only where a word wouldn't fit. Critical courses use a text label instead of the diamond icon, which still satisfies "color is never the only signal".
- **Controls:** toggles and buttons are black and white. Tags become plain gray-bordered text.
- The bottleneck graph and the advisor export follow the same palette.

### 3.6 Repository hygiene and QA
- Delete the merged branch and turn on auto-delete of head branches.
- Remove the committed `.claude/settings.json`, which grants blanket tool permissions to anyone who clones the repo.
- Git-ignore personal files (`data/personas/my-*.json` except the template, and `*audit*.pdf`).
- Add a repo description and topics, an MIT license, and a CI badge.
- Move `DECISIONS.md` and `PROGRESS.md` into `docs/`, fixing links.
- **QA pass.** Run every persona and flow in a browser, and review the planner and profile code. Each bug found gets a regression test. Known lead: credited hours in one real-record run were 2 above the audit's total.

## 4. Non-goals
- Logging into Degree Works or any ATU system, or scraping it. Import is a file the student already has.
- Storing audits or any profile on a server.
- Guessing course equivalents for AP/IB rows that award generic credit.
- Catalog years before 2025–26, graduate programs, and minors.
- Deploying a public instance. That's a separate decision (PRD Q5).

## 5. Success criteria
- Importing the owner's real audit, verified locally and never committed, produces the same credited-hours total as Degree Works and a plan with no manual edits.
- A synthetic audit fixture (fake name and ID) covers the parser in Vitest: completed, CE/AP, CE/CLEP, IP, Not Used, and wrapped term cells.
- All 2025–26 bachelor's maps are ingested and tiered. The report gives the real Auto-imported-or-better share for each year, and every program plans at standard pace.
- AP credit works end to end: an AP Computer Science A score of 3+ awards COMS 1013 and 1011 and counts toward the exam cap.
- `make lint`, `make test`, `make build`, and CI stay green. The p95 plan time for CS stays under 3 s.
- If launched (for interview discussion): the share of new plans started from an import, the median time from landing to first plan, and audit-vs-plan disagreements per 100 imports (a data-quality guardrail).

## 6. Risks
| Risk | Mitigation |
|---|---|
| The Degree Works PDF layout changes, or differs by college | The parser keys off stable tokens (course-code pattern, grade column, "Satisfied by:") rather than page positions. Unrecognized rows are shown, never dropped silently. Manual editing stays available. |
| A student's audit leaks | Parsing happens in the browser only, name and ID are discarded, the files are git-ignored, and there's no server storage |
| Catalog snapshots go stale | Capture dates are shown on the About page. REPORT.md flags snapshots older than the newest catalog year. |
| Current Banner prerequisites differ from 2025–26 rules | A documented assumption, shown on 2025–26 programs |
| The audit and the map disagree on a requirement | Shown in the audit-vs-plan panel for the advisor. Shortcut doesn't pick a winner silently. |

## 7. Delivery
Work happens on branch `feat/atu-sources` in this order: hygiene → QA fixes → catalog → catalog years → Degree Works import → docs. Commits are small and conventional, and the branch ships as one pull request for the owner to merge.
