# Architecture

Shortcut has two halves. A **data pipeline** turns ATU's published documents into JSON once, at build time. A **web app** loads that JSON at startup and plans a student's path on request. Nothing runs in the background, and nothing is stored about a student on the server.

```
data/raw  ── pipeline ──▶  data/processed/*.json  ──▶  FastAPI (/api)  ◀──▶  React app
(degree-map PDFs,           programs, courses,          planner: CP-SAT        (served by the same
 Banner JSON, catalog       exam tables, policies       + slack + what-if       process; Degree Works
 snapshots)                                                                     import runs in-browser)
```

## Data pipeline (`backend/pipeline`)

Run it with `make pipeline-offline` (from the committed raw files, about 1 minute) or `make pipeline` (fetches anything missing first). The entry point is `build.py`. Stages, in order:

1. **Discover** (`discover.py`): every catalog year on ATU's degree-map index from 2025–26 on. It handles two index quirks visibly: one PDF linked under two titles, and one map stored outside the usual folder.
2. **Download** (`download.py`): degree-map PDFs and supporting pages, committed under `data/raw/`.
3. **Parse degree maps** (`parse_degree_map.py`): reads each PDF with pdfplumber word coordinates, covering semester blocks, hours columns, continuation rows, "Fall Only" notes, gen-ed option boxes, and summer blocks.
4. **Enrich from Banner** (`enrich_catalog.py`, `banner.py`, `prereqs.py`): joins each course to ATU's public Banner catalog for titles, hours, prerequisite trees, corequisite groups, and standing. Offering confidence comes from catalog text, map notes, and three years of class schedules (D8). Prerequisites naming retired courses are dropped and recorded (D11).
5. **Build programs** (`programs.py`): requirements, gen-ed buckets, and the map's own schedule, kept as the baseline.
6. **Validate and tier** (`validate.py`): 11 checks per program, then a trust tier (below).
7. **Link catalog years** (`catalog_years.py`): pairs each major across years for the "switch to a newer catalog" what-if, using `data/manual/catalog_successors.json` for renames and splits.
8. **Exam tables** (`catalog_tables.py`, `exams.py`): the AP, CLEP, and IB tables saved from catalog.atu.edu (`data/raw/catalog`), mapped to exact course codes only.
9. **Write** `data/processed/*.json` and [`data/REPORT.md`](../data/REPORT.md) (`report.py`).

CI rebuilds the processed data offline and fails if anything but the timestamp changes, so the committed data is always exactly what the code produces.

## Planner (`backend/shortcut/planner`)

- **`profile.py`** turns a student's record into credits and remaining items. That covers matching requirements (alternatives, buckets, electives), adding prerequisites the map omits, and fillers for total and upper-level hours.
- **`model.py`** is the CP-SAT model: `x[item, term]` for courses at ATU and `y[item, term]` for transfer courses (summer only).
  - It encodes prerequisites, corequisites, class standing via cumulative hours, hour caps and overload eligibility, residency, and the exam-credit cap.
  - The solve has two phases. Phase 1 finds the earliest graduation term. Phase 2 holds that term and polishes the schedule: fewer short terms, fewer overload hours, the preferred load, and the degree map's order (D10, D22). Tie-breaks can never move the date.
  - One solver worker and a fixed seed make the same request return the same schedule (D26).
- **`slack.py`** runs a calendar-aware backward pass over the prerequisite edges the plan uses, holding the graduation term fixed. Slack is how many regular semesters a course could slip, respecting fall-only and spring-only offerings. Zero slack means critical.
- **`service.py`** assembles a response: the standard-pace solve, the full solve, one extra solve per enabled lever (marginal attribution), slack and the critical chain, warnings, and assumptions.
  - A lever's saving is the full plan vs. the same plan with only that lever off, so it doesn't depend on the order levers were turned on. Complementary levers (heavier terms and summer) can each show the full saving, and the lever panel says "Levers can overlap".
- **`whatif.py`** and **`exams.py`** handle what-ifs (fail, drop, skip, change major, newer catalog), delay impact, and exam opportunities, all as full re-solves.
- Every policy number lives in `data/manual/policies.json` with its ATU source and a confidence label (documented, derived, assumed, unknown, or conflicting).

## API (`backend/shortcut/api`)

`GET /api/health`, `/api/meta`, `/api/programs`, `/api/programs/{id}`, `/api/exams`, `/api/personas`; `POST /api/plan`, `/api/plan/whatif`, `/api/plan/exam-opportunities`, `/api/plan/delay-impact`. Schemas are Pydantic v2 (`backend/shortcut/schemas`), mirrored by hand in `frontend/src/api/types.ts`. The same process serves the built React app, with an `index.html` fallback for client routes.

## Degree Works import (`frontend/src/degreeworks`)

pdf.js text lines (`pdfLines.ts`) → `parse.ts` (courses, exam credit, still-needed lines) → `toProfile.ts` (a plan request) → `reconcile.ts` (the audit-vs-plan comparison). The parser keys off stable tokens (course codes, the grade column, "Satisfied by:", "Still needed:") rather than page positions, and it never reads the student's name or ID. The parsed audit lives in the tab's sessionStorage only (D25). The committed test fixture, `fixtures/sample-audit.ts`, is synthetic.

## Frontend (`frontend`)

React 19, TypeScript (strict), Vite, Tailwind CSS v4, @xyflow/react with dagre for the prerequisite graph, pdf.js, and Vitest with Testing Library.
- The design is plain on purpose: black on white, one system font, and words instead of color or icons ("Critical" is a label). `src/design.test.ts` scans the source to enforce it.
- The plan request lives in the URL (`?s=`, shareable) and in localStorage. The app is keyboard navigable and targets WCAG AA contrast.

## Data and trust

From [`data/REPORT.md`](../data/REPORT.md):

| Catalog year | Bachelor's programs | Cross-checked | Auto-imported | Needs review | Auto-imported or better |
|---|---|---|---|---|---|
| 2025–26 | 72 | 1 | 54 | 17 | 55 (76%) |
| 2026–27 | 73 | 4 | 56 | 13 | 60 (82%) |

- 161 degree maps were discovered, and 145 bachelor's programs were ingested. The 16 associate or other maps are excluded (a PRD non-goal).
- `courses.json` holds 911 courses, plus a title-and-hours index of every course in ATU's Banner catalog.
- Every one of the 145 programs produces a feasible plan at standard pace (`backend/tests/acceptance/test_all_programs.py`).

The tiers mean:
- **Cross-checked:** every automated check passes, *and* the parse was compared row by row against the rendered degree map and Banner. The five are Computer Science (2025–26), Accounting, History, Nursing, and Mathematics, covering all four of ATU's colleges (D15, [`data/manual/cross_checks.json`](../data/manual/cross_checks.json)).
- **Auto-imported:** every blocking check passes.
- **Needs review:** a check failed (for example, a row without hours, or a map typo). The program can still be planned, with a warning.

## Caveats

- **catalog.atu.edu blocks automated tools.** Course rules come from ATU's public Banner catalog and class schedule. The AP/CLEP/IB tables and credit policies were saved once from a regular browser and are dated (D5, D23).
- **Some ATU pages disagree.** The catalog allows exam credit up to 50% of a degree, while the admissions page says 30 hours. Shortcut uses the stricter value and says so (D24).
- **Today's course rules apply to every catalog year.** A 2025–26 program is planned with the current Banner prerequisites and offerings.
- **Offerings are inferred.** Summer and winter availability comes from three years of public schedules, and every inference is labeled with its evidence.
- **Some things can't be scheduled.** Admission cycles, cohort starts, and Credit for Prior Learning are flagged, not modeled.
- **Degree Works is the official record.** Where it and the degree map list requirements differently, Shortcut shows the difference instead of picking a winner.

## Performance

A full CS plan with lever attribution, over all 64 lever combinations, took a median 0.83 s and p95 2.15 s on an Apple-silicon laptop (measured 2026-09-30). The PRD target is p95 under 3 s. The solver runs on one worker so the same request always returns the same schedule. That trade is recorded in D26, which measured p95 at 0.55 s with four workers and 2.07 s with one.

## Docker and deployment

```bash
docker build -t shortcut .
docker run --rm -p 8000:8000 shortcut      # http://localhost:8000
```

The image is multi-stage: Node builds the frontend, then a slim Python image runs uvicorn as a non-root user, with a `/api/health` health check. CI builds the image and checks that it serves.

Shortcut is a single stateless service with no database, secrets, or outbound calls at runtime. The JSON data is baked into the image and loaded at startup, so it runs anywhere that runs a container on port 8000. Nothing has been deployed from this repository.
