# Progress

Resume here: read this file first, then DECISIONS.md, then continue from the first unchecked milestone.

## v1.1 summary (2026-09-29): ATU sources

All 16 tasks of [the v1.1 plan](plans/2026-09-29-atu-sources-plan.md) are complete on `feat/atu-sources`. The spec is [prd/v1.1.md](prd/v1.1.md).

### What shipped
- **Degree Works import** (`frontend/src/degreeworks`):
  - A saved audit PDF is read in the browser with pdf.js, turned into a profile, and reviewed before it's applied.
  - Posted exam credit, transfer work, in-progress courses, and unapplied hours all count, with the audit's own hours.
  - Name and student ID are never read into anything.
  - The plan page compares Degree Works' still-needed lines with the plan (D25).
- **Every catalog year:** 161 degree maps (2025–26 and 2026–27) give 145 bachelor's programs. A student plans against the map for their year of entry and can test switching to a newer catalog as a what-if.
- **Catalog snapshots:** AP (55), CLEP (43), and IB (82) tables and the credit, graduation, and load policies were saved from a regular browser (D23). Exact course codes only. About shows each page's capture date and the trust tiers per catalog year.
- **Correctness fixes** found with a real record:
  - catalog hours for courses outside the program data
  - posted exam credit and per-course hours
  - the exam-cap overcount
  - TECH 1001 map order
- **Minimal black-and-white interface** (PRD v1.1 §3.5), guarded by a source-scan test (`frontend/src/design.test.ts`).

### Final QA pass (this session)
- **Solver determinism (D26).** Parallel CP-SAT workers returned a different tie-optimal schedule for the same request, so a reload or share link could move courses. The solver now runs on one worker. CS p95 is 2.07 s (target: under 3 s).
- **Policy numbers.** Lever labels, warnings, assumptions, Setup, and the import's overload-GPA threshold hardcoded policy values. They now come from `policies.json` (through `/api/meta` in the browser), and each number shown links to its About entry.
- **UI:**
  - tinted panels and table headers removed
  - landing overflow at 390 px fixed
  - "Majors" counts majors (74), not catalog-year versions (145)
  - duplicate "16" in Setup removed
  - singular/plural wording in the import review
  - black native radios and checkboxes
- **Personas:** P3 and P4 stay on the cross-checked 2026–27 maps and say why (D27).
- **Review fixes:**
  - REPORT.md lists the catalog snapshots and flags any older than the newest catalog year.
  - The import review offers a catalog-year picker when the audit's year has no map.
  - Setup keeps a shared part-time load selectable.

### Checks (last run)
- `make lint`: ruff, ruff format, mypy --strict, ESLint, and tsc are clean.
- `make test`: 276 backend tests (including A1–A10, all 145 programs, and determinism) and 95 frontend tests pass. `make build` passes.
- HTTP smoke test against `make serve`: 43 of 43 checks pass, covering:
  - every endpoint
  - all four personas, each with plan, delay, fail, skip, drop, change of major, and exam opportunities
  - bad input (404/422)
  - SPA deep links
- Browser: every page and tab at 1360 px and 390 px, with no console errors and no horizontal overflow. The import → plan flow sends no PDF bytes (one `POST /api/plan`). Share link, reload, and localStorage restore all return the identical plan.
- axe-core (WCAG 2.1 A/AA): 0 violations on the landing, Setup, import, review, About, plan, and all plan tabs.
- `docker build` passes, and the container serves health, the app, meta, and plans.
- Real record (local only, never committed): 77 credits match Degree Works, graduation is May 2028, and the chain is COMS 3213 → COMS 3313.

### Open items for the owner
- Q2 (exam-credit cap): still conflicting (30 hours vs. 50%). Shortcut uses 30 (D24).
- The 30 Needs-review programs, mostly 2025–26 maps whose course codes aren't in Banner's details.
- Merging `feat/atu-sources` into `main`.

## v1 summary (2026-09-29)

All milestones M0–M8 are complete on `claude/optimistic-bohr-nwjsi5`.

### What's built
- **Data pipeline** (`backend/pipeline`, `make pipeline` / `make pipeline-offline`):
  - Discovers and downloads every ATU degree map and parses each PDF by word coordinates.
  - Enriches every course from ATU's public Banner catalog and three years of class schedules: prerequisite trees, corequisite groups, standing, and offering confidence.
  - Validates each program with 11 checks, assigns trust tiers, and writes `data/REPORT.md`.
  - Raw sources are committed, and the offline rebuild is byte-for-byte reproducible (CI enforces this).
- **Planner** (`backend/shortcut/planner`):
  - An OR-Tools CP-SAT model covering prerequisites, corequisites, offerings, standing, hour caps, overload eligibility, summer/winter/transfer, residency, and the exam cap.
  - A two-phase solve: earliest graduation first, then a realism polish.
  - Slack and the true critical chain, marginal lever attribution, what-ifs (fail, drop, skip, change major), delay impact, and exam opportunities. The last three are all full re-solves.
  - Honest outputs: `pace_note` names the chain when no lever helps, and plans are never compressed past what the data supports.
- **API** (FastAPI): every PRD §11 endpoint plus `/api/personas`, with Pydantic schemas mirrored in the frontend.
- **Web app** (React 19 + TypeScript + Tailwind v4):
  - Landing with major search and four demo profiles, and a 3-step setup.
  - The plan view: comparison headline, timeline, lever panel, and warnings.
  - Tabs for Bottlenecks (graph plus chain), Exam opportunities, What-if, Advisor export (print), and About the data.
  - Share URL plus localStorage, keyboard navigation, and a mobile layout.
- **Personas:** P1 (CS from scratch), P2 (CS with CLEP credit), P3 (Accounting, off-track after an F in fall-only ACCT 3003), P4 (Nursing, "no shortcut"), plus `data/personas/my-path.template.json`.
- **Docs and ops:**
  - README with a browser-verified 60-second demo, screenshots, architecture, caveats, and a resume bullet.
  - DECISIONS D1–D21.
  - A multi-stage Dockerfile, built and served here.
  - GitHub Actions CI: backend, frontend, one-process serve (A10), a Docker build/serve job, and the data-drift check.

### Test results (final run)
- **Backend:** 163 pytest tests pass (unit, pipeline fixtures, CS ground truth, acceptance A1–A10, 4 personas, and a feasibility check for every one of the 74 programs). ruff, ruff format, and mypy --strict are clean.
- **Frontend:** 12 Vitest tests pass. ESLint and tsc are clean, and the production build works.
- **PRD §15 acceptance:**
  - A1: standard pace is May 2030.
  - A2: accelerated graduates May 2029.
  - A3–A8 cover offerings, what-if, attribution, exams, and latency.
  - A9: the report.
  - A10: one process serves every persona.
  - All pass.
- **Over HTTP:**
  - Every endpoint and every persona (plan, exams, delay, and all four what-if types) was smoke-tested, along with bad inputs.
  - All 74 programs return feasible plans.
  - The README demo was replayed in headless Chromium.
  - axe-core found 0 WCAG 2.1 A/AA violations across 10 page states.
  - No horizontal overflow at 390 px.
  - The Docker image serves health, the app, personas, and plans.
- **Latency:** a full CS plan with attribution over all 64 lever combinations takes a median 0.84 s and p95 2.18 s (PRD target: p95 < 3 s).

### Data coverage (data/REPORT.md)
- 82 degree maps discovered (81 for 2026–27 plus the 2025–26 CS ground truth).
- 74 bachelor's programs ingested; 8 associate or other maps excluded (PRD non-goal).
- Tiers: **5 Cross-checked, 56 Auto-imported, 13 Needs review**, so 82% are Auto-imported or better.
  - The cross-checks (CS, Accounting, History, Nursing, Mathematics) span all four colleges (D15).
- 888 courses from 838 Banner course records.
- CLEP: 32 equivalencies. AP/IB: unavailable (D6).

### Known limitations
- **Course data comes from Banner, not the catalog site.** catalog.atu.edu is behind a bot challenge from this environment (D5), and AP/IB tables live only there.
- **13 programs Need review.** Most are map arithmetic that doesn't add up, such as a semester's rows not matching its stated total or CHEM 4424 listed at 1 hour. Two are ambiguous layouts (a "14/18" total, unlabeled "Performance/Technology Course" slots). One is a typo (BIOL 2134 listed as both Botany and Zoology). They still plan, with a warning.
- **Banner prerequisites the maps omit add courses in a few programs.** Examples: MGMT 3003 needs ACCT 2013 for the HES tracks, and HA 3183 needs CHEM 1113 for Tourism. Each plan names the added course and why. Departments may waive some of these.
- **Offering availability is inferred** from 3 years of schedules (D8), and a course that ran before may not run again.
- **Several rules are assumptions, labeled as such.** Class standing counts exam and transfer credit. Non-math placement tests are assumed met (D9). A retaken course counts once (D16).
- **Some requirements can't be scheduled.** Admission cycles, cohort starts, and Credit for Prior Learning are flagged, not modeled.
- **Cross-checks were done by the build agent**, by comparing rendered PDFs row by row. That isn't an ATU advisor's sign-off.
- **Lever savings are marginal.** Complementary levers (heavier terms plus summer) can each show the full saving.
- **Nothing is deployed.**

### PRD §16 open questions
- **Q1** (replace P2's sample data with real credits): still sample data. Fill in `data/personas/my-path.template.json` (copy it to `my-path.json`) to add your real record as a profile.
- **Q2** (exam-credit cap): still unresolved. ATU pages disagree (30 hours vs. 50% of the degree). Shortcut uses 30 and says so in every plan that uses exam credit. It needs registrar confirmation.
- **Q3** (public class schedule): **answered, yes.** ATU's public Banner class search is used for three years of offering history (D7).
- **Q4** (degree audit in OneTech): **partially answered.** ATU's advising page links "How to use Degree Works", so an audit tool exists (D4). Shortcut complements it with planning and what-ifs.
- **Q5** (deployment host): open. The Docker image runs on any container host (see the README's deploy notes).

## Status by milestone
- [x] **M0 Scaffold**: backend (uv, FastAPI), frontend (Vite React TS, Tailwind v4, Vitest, ESLint), Makefile, docs.
- [x] **M1 CS data, exam tables, policies**
  - Discovery + download of every degree map (82 PDFs: 81 for 2026–27 plus 2025–26 CS) and the policy/calendar pages.
  - Coordinate-based PDF parser (`backend/pipeline/parse_degree_map.py`); the CS 2025–26 parse matches PRD Appendix A (`tests/pipeline/test_cs_ground_truth.py`). Fixture tests cover 4 other layouts.
  - catalog.atu.edu is WAF-gated from this environment (D5), so course data comes from ATU's public Banner catalog and class schedule. The raw snapshots are committed: 838 course details, 15 terms × 76 subjects of schedule history.
  - `data/manual/policies.json` encodes PRD §8 with sources and confidence and is tested rule by rule. CLEP comes from Appendix B; AP/IB are unavailable (D6).
  - Offering confidence follows PRD §7.4 plus schedule history (D8).
- [x] **M2 Planner**: CP-SAT model (`shortcut/planner/model.py`) with two-phase solve (earliest graduation, then polish), slack/critical path, lever attribution, what-if, exam opportunities, and delay impact. A1–A8 pass; synthetic tests cover chains, coreqs, OR prereqs, standing, caps, transfer/residency, the exam cap, min grades, and infeasibility.
- [x] **M3 API**: every PRD §11 endpoint plus `/api/personas`; `tests/unit/test_api.py`. Latency is measured below.
- [x] **M4 Frontend core**: landing (search + personas), 3-step setup, plan view (comparison headline, timeline, lever panel, warnings), share URL + localStorage.
- [x] **M5**: bottleneck graph (xyflow + dagre, click to delay or fail), exam opportunities with add-to-plan, what-if panel, advisor export with print CSS.
- [x] **M6 All majors**: pipeline runs on all 74 bachelor's maps: 5 Cross-checked, 56 Auto-imported, 13 Needs review (82% Auto-imported or better). All 74 produce a feasible standard-pace plan. The sweep fixed 11 infeasible programs (D12–D14). The 5 cross-checks (CS, Accounting, History, Nursing, Mathematics) cover all four colleges (D15).
- [x] **M7**: P3 (Accounting, off-track after an F in fall-only ACCT 3003) and P4 (Nursing, "no shortcut") personas, the my-path template, and a README with a browser-verified 60-second demo and screenshots (`docs/screenshots`). Polish:
  - `pace_note` explains the date when no lever helps.
  - `critical_chain` is the true longest prerequisite chain.
  - The graph opens at its first term.
  - The headline is honest when a student is behind the map.
  - Dockerfile and CI are in place.
- [x] **M8 Final QA**:
  - lint/test/build/serve all pass.
  - The HTTP sweep and the review as a skeptical senior engineer found and fixed several real problems:
    - the Psychology hour inflation (D17)
    - graduating in a winter intersession (D18)
    - a lab corequisite leak (D19)
    - the missing HIM summer block (D20)
    - "except" clauses and repeatable ensembles (D21)
    - retakes counting twice (D16)
    - two map layouts
  - Also covered: the Docker build, the axe audit, and a strict data-drift check in CI.

## Checks (last run)
- Backend: `ruff check`, `ruff format --check`, `mypy --strict`: clean. `pytest`: 163 tests pass, including A1–A10 (A10 requires `make build` first) and the 74 per-program checks.
- Frontend: `tsc -b`, `eslint`: clean. `vitest`: 12 tests pass. `npm run build` OK.

## Environment notes
- Network: www.atu.edu, reg-prod.ec.atu.edu (Banner), and adhe.edu are reachable. catalog.atu.edu is not (its WAF challenge host `*.token.awswaf.com` is denied).
- Working branch: v1 on `claude/optimistic-bohr-nwjsi5` (merged into `main`); v1.1 on `feat/atu-sources`.
- The Banner fetch takes about 30 minutes cold (3,725 requests). `make pipeline-offline` rebuilds from the committed snapshots in about 1 minute.
- Git author is the owner's GitHub noreply address (D1).

## Next step
Owner decisions: Q1 (your real record), Q2 (registrar on the exam cap), Q5 (host), and merging the PR into `main`.
