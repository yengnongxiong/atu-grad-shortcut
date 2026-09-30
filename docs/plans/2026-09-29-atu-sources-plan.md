# ATU Sources (PRD v1.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Shortcut start from ATU's own tools. It reads the catalog's AP/IB/CLEP tables, plans against every catalog year's degree maps, and imports a Degree Works audit. It also fixes the credit bugs found with a real record and gets a minimal black-and-white UI.

**Architecture:**
- The data pipeline adds parsers for three things: saved catalog snapshots, every catalog year on the degree-map index, and a full course index.
- The planner gains a posted-exam-credit source and per-course hour overrides.
- The frontend gains a Degree Works importer that runs in the browser (pdf.js, lazy-loaded). Its pure parser turns an audit into a `StudentProfile` plus an audit-vs-plan comparison.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, OR-Tools, pdfplumber, BeautifulSoup4, pytest. React 19, TypeScript (strict), Vite 8, Tailwind v4, Vitest, pdfjs-dist.

**Spec:** `docs/prd/v1.1.md` (extends `docs/prd/v1.md`)

## Global Constraints
- Never invent academic data. Every course, exam row, and policy traces to a source URL or a saved snapshot (CLAUDE.md data rules).
- Exam equivalencies use exact course codes only. Generic credit ("3 hours General Education Humanities") is never mapped to a guessed course.
- A Degree Works PDF is parsed only in the browser. Name and student ID are never copied into the profile, logged, or sent. No audit file is ever committed.
- Automated code never works around catalog.atu.edu's bot challenge. Snapshots are saved by a person in a normal browser.
- Visual: white background, black text, gray borders, and red only for blocking errors. One system sans-serif, 6px corners, no shadows or accent colors, and minimal icons. "Critical" is shown with a text label.
- Keep `make lint` (ruff, ruff format, mypy --strict, eslint, tsc) and `make test` green after every task. CS plan p95 stays under 3 s.
- Conventional commits, authored as the owner's noreply identity (already the global git config), ending with the Co-Authored-By trailer.
- Log every judgment call in `docs/DECISIONS.md` as D22 onward.

## Review Focus
- An audit course whose code isn't in Shortcut's data (e.g. COMS 1411) must count with the audit's own hours, not a 3-hour guess. Covered in Task 2, Task 3, and Task 12.
- An audit whose term cell wraps onto two lines ("Spring Term" / "2026") must still read the right term. Covered in Task 11.
- An audit from a catalog year or major Shortcut doesn't have must say so and let the student pick, not crash or silently pick another major. Covered in Task 12.
- A student with both an AP score entry and the same course posted as exam credit must not get double credit. Covered in Task 3.
- 2025–26 maps whose course codes are missing from Banner details must still plan, with a warning. Covered in Task 9 (all-programs test over both years).

---

## Phase 1: Repository hygiene

### Task 1: Clean repository layout and personal-data guards

**Files:**
- Modify: `.gitignore`
- Delete (from git): `.claude/settings.json`
- Create: `LICENSE` (MIT, "Copyright (c) 2026 Yengnong Xiong")
- Move: `DECISIONS.md` → `docs/DECISIONS.md`, `PROGRESS.md` → `docs/PROGRESS.md`
- Modify: every reference found by `git grep -n "DECISIONS.md\|PROGRESS.md"`

- [ ] **Step 1: Add the ignore rules**

```gitignore
# Personal records: never commit real grades or audits
data/personas/my-*.json
!data/personas/my-path.template.json
*audit*.pdf
.claude/
```

- [ ] **Step 2: Verify the guard works**

Run `cp data/personas/my-path.template.json data/personas/my-path.json && git status --porcelain data/personas`.
Expected: no output (the file is ignored). Then `rm data/personas/my-path.json`.

- [ ] **Step 3: Remove the permissions file and move the docs**

```bash
git rm --cached .claude/settings.json
git mv DECISIONS.md docs/DECISIONS.md
git mv PROGRESS.md docs/PROGRESS.md
git grep -n "DECISIONS.md\|PROGRESS.md"
```
Fix each hit: README links become `docs/DECISIONS.md`, and code comments keep the bare name.

- [ ] **Step 4: Add the LICENSE (MIT text), then run `make lint && make test`.** Expected: all green.

- [ ] **Step 5: Commit** `chore: gitignore personal records, drop committed agent permissions, MIT license, docs/ layout`

---

## Phase 2: Correctness fixes found with a real record

### Task 2: Every catalog course resolves its real hours

**Problem:** `profile.course_hours` falls back to 3.0 for any code outside the 888-course dataset. COMS 1411 (1 hr) counted as 3.

**Files:**
- Modify: `backend/pipeline/build.py` (write `data/processed/course_index.json`)
- Modify: `backend/shortcut/data/loader.py` (load `course_index`)
- Modify: `backend/shortcut/planner/profile.py:100-109` (`course_hours`, `course_title` fall back to the index)
- Modify: `backend/shortcut/planner/service.py` (warning for codes found nowhere)
- Test: `backend/tests/unit/test_course_index.py`

**Interfaces:**
- Produces: `Dataset.course_index: dict[str, dict[str, Any]]` mapping code → `{"title": str, "hours": float}` for every Banner catalog course. Also `course_known(dataset, code) -> bool`.

- [ ] **Step 1: Write the failing tests**

```python
from shortcut.data.loader import load_dataset
from shortcut.planner.profile import course_hours, course_known


def test_lab_outside_program_data_keeps_its_catalog_hours() -> None:
    ds = load_dataset()
    assert "COMS 1411" not in ds.courses
    assert course_hours(ds, "COMS 1411") == 1.0


def test_unknown_code_is_flagged() -> None:
    ds = load_dataset()
    assert course_known(ds, "COMS 1411")
    assert not course_known(ds, "ZZZZ 1234")
```

- [ ] **Step 2: Run** `uv --directory backend run pytest tests/unit/test_course_index.py -v`. Expected: FAIL (`course_known` is undefined).

- [ ] **Step 3: Implement**
  - In `build.py`, after `load_banner_raw()`, build the index from every `data/raw/banner/catalog/<term>/*.json` row: `f"{subjectCode} {courseNumber}"` → `{"title": courseTitle, "hours": creditHourLow}`. When `creditHourHigh` is set, use it instead of `creditHourLow` (variable-credit courses). Write the index with the other outputs.
  - `loader.py` reads it, defaulting to `{}` when the file is missing.
  - `profile.py`:

```python
def course_hours(dataset: Dataset, code: str, fallback: float = 3.0) -> float:
    for table in (dataset.courses, dataset.course_index):
        entry = table.get(code)
        if entry and entry.get("hours") is not None:
            return float(entry["hours"])
    return fallback


def course_known(dataset: Dataset, code: str) -> bool:
    return code in dataset.courses or code in dataset.course_index
```

  - In `service.py`, add a `warning` for every completed or in-progress code where `not course_known(...)`: "{code} isn't in ATU's catalog data; counted as {hours} hours."

- [ ] **Step 4: Run** `make pipeline-offline && make test`. Expected: PASS, with processed data diff limited to the new `course_index.json` and `meta.json`.

- [ ] **Step 5: Commit** `fix: courses outside program data use their catalog hours, not a 3-hour guess`

### Task 3: Posted exam credit and audit-supplied hours

**Files:**
- Modify: `backend/shortcut/schemas/plan.py:14-22` (`CompletedCourse`)
- Modify: `backend/shortcut/planner/profile.py:131-143` (`build_state`)
- Modify: `frontend/src/api/types.ts:9-13`
- Test: `backend/tests/unit/test_posted_exam_credit.py`

**Interfaces:**
- Produces:
  - `CompletedCourse.source: Literal["atu", "transfer", "exam"]`
  - `CompletedCourse.hours: float | None` (None means use catalog hours)
  - `CompletedCourse.exam: str | None`, e.g. "AP Computer Science A", for display only
  - The TS mirror has the same fields.

- [ ] **Step 1: Write the failing tests**

```python
from shortcut.data.loader import load_dataset
from shortcut.planner.profile import build_state
from shortcut.schemas.plan import CompletedCourse, ExamScore, StudentProfile


def _profile(**kw) -> StudentProfile:
    return StudentProfile(program_id="computer-science-2025-26", first_term="2025FA", **kw)


def test_posted_exam_credit_counts_toward_cap_not_residency() -> None:
    p = _profile(completed=[CompletedCourse(code="COMS 1013", grade="P", source="exam", exam="AP Computer Science A")])
    state = build_state(load_dataset(), p, [])
    assert state.exam_hours == 3.0
    assert state.atu_hours == 0.0
    assert state.credits["COMS 1013"].grade is None


def test_audit_hours_override_catalog_hours() -> None:
    p = _profile(completed=[CompletedCourse(code="COMS 1411", grade="P", source="exam", hours=1)])
    assert build_state(load_dataset(), p, []).earned_hours == 1.0


def test_posted_credit_and_score_for_same_course_count_once() -> None:
    p = _profile(
        completed=[CompletedCourse(code="ENGL 1013", grade="P", source="exam")],
        exams=[ExamScore(program="CLEP", exam="College Composition", score=52)],
    )
    ds = load_dataset()
    state = build_state(ds, p, [])
    from shortcut.planner.profile import resolve_exam_awards
    resolve_exam_awards(state, ds.program("computer-science-2025-26"), ds)
    assert sum(1 for c in state.credits.values() if c.code == "ENGL 1013") == 1
    assert state.exam_hours == 3.0
```

- [ ] **Step 2: Run the tests.** Expected: FAIL (validation error on `source="exam"`).

- [ ] **Step 3: Implement.** Schema:

```python
class CompletedCourse(BaseModel):
    code: str
    grade: Grade = "C"
    source: Literal["atu", "transfer", "exam"] = "atu"
    hours: float | None = Field(default=None, ge=0, le=12)
    exam: str | None = None
```

In `build_state`, `hours=done.hours if done.hours is not None else course_hours(dataset, done.code)`, and `grade=None if done.source == "exam" else done.grade`. Mirror the fields in `types.ts`.

- [ ] **Step 4: Run** `make test && make lint`. Expected: PASS.

- [ ] **Step 5: Commit** `feat: posted exam credit and per-course hours in the student profile`

### Task 4: Hands-on QA sweep

**Files:** whatever the sweep finds. Each fix gets a regression test next to the code it fixes.

- [ ] **Step 1:** `make build && make serve`. In Chrome, run each persona P1–P4 through every tab: Plan, Bottlenecks, Exam opportunities, What-if, Advisor export, and About. Also cover Setup steps 1–3 by hand, a share-link round trip, a reload with localStorage, and a 390px-wide mobile viewport. Read the console for errors and warnings.
- [ ] **Step 2:** Code-review `profile.py`, `service.py`, `whatif.py`, `exams.py`, and `state/profile.ts` for logic errors. Record each finding in the working notes with a reproduction.
- [ ] **Step 3:** For each confirmed bug:
  - write the failing test
  - fix it
  - `make test`
  - commit `fix: <what>` (one commit per bug)
- [ ] **Step 4:** Re-run the scratch real-record script (outside the repo). Expected: credited hours equal the audit's 77, and graduation is May 2028.

---

## Phase 3: Minimal visual design

### Task 5: Black-and-white theme

**Files:**
- Modify: `frontend/src/index.css` (tokens and component classes)
- Modify: `frontend/index.html` (drop the web-font `<link>`s if present)
- Modify: `frontend/src/components/ui.tsx` (`CriticalIcon`, `ArrowIcon`, toggle, tags)
- Modify: `frontend/src/components/Layout.tsx` (text wordmark)
- Modify: `Timeline.tsx`, `LeverPanel.tsx`, `PlanHeadline.tsx`, `BottleneckGraph.tsx`, `graphLayout.ts`, `WarningsPanel.tsx`, `AdvisorExport.tsx`, `Landing.tsx`, `Setup.tsx`, `About.tsx` (remove colored classes, serif, and shadows)
- Test: `frontend/src/components/components.test.tsx` (critical label is text)

- [ ] **Step 1: Write the failing test.** A critical course chip renders the visible text "Critical" (not only an icon or color):

```tsx
it('marks critical courses with a text label', () => {
  render(<Timeline terms={[termWithCriticalCourse]} />)
  expect(screen.getByText('Critical')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run** `cd frontend && npx vitest run src/components/components.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Replace the tokens** in `index.css`:

```css
@theme {
  --font-sans: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-display: var(--font-sans);
  --font-mono: ui-monospace, SFMono-Regular, Menlo, monospace;
  --color-paper: #ffffff;
  --color-paper-deep: #f5f5f5;
  --color-surface: #ffffff;
  --color-ink: #000000;
  --color-ink-soft: #262626;
  --color-muted: #6b6b6b;
  --color-line: #e5e5e5;
  --color-line-strong: #d4d4d4;
  --color-critical: #000000;
  --color-critical-soft: #f5f5f5;
  --color-saved: #000000;
  --color-saved-soft: #f5f5f5;
  --color-warn: #000000;
  --color-warn-soft: #f5f5f5;
  --color-error: #b00020;
  --color-error-soft: #fff5f5;
  --color-info: #000000;
  --color-info-soft: #f5f5f5;
}
```

Then:
- `.card`: `rounded-md border border-line bg-surface` (no shadow).
- Buttons and inputs: `rounded-md`.
- `.chip`: `rounded border-line text-muted font-medium`.
- h1–h3: normal tracking, `font-semibold`.
- Focus outline: black.
- Selection: `#e5e5e5`.

- [ ] **Step 4:** Walk each component listed above:
  - remove colored top borders (`border-t-4 border-*`), tinted backgrounds, and `shadow-*`
  - replace `CriticalIcon` with a small bordered "Critical" text tag
  - make the wordmark the plain text "Shortcut"
  - make toggles black when on and gray when off
  - make graph nodes white with black borders, critical nodes 2px black, and edges gray (critical edges black)

- [ ] **Step 5: Verify.** Run `make lint && make test && make build`, then take screenshots of the landing, plan, bottlenecks, and mobile views in Chrome and review them against the spec §3.5 checklist.

- [ ] **Step 6: Commit** `style: minimal black-and-white interface`

---

## Phase 4: Catalog (catalog.atu.edu)

### Task 6: Save catalog snapshots

**Files:**
- Create: `data/raw/catalog/{institutional-credit,ap,clep,ib,graduation-requirements,regulations-procedures}.html`
- Create: `data/raw/catalog/captured.json` (`{page: {url, captured_at, method: "manual browser save"}}`)

- [ ] **Step 1:** In the owner's Chrome, open each URL:
  - `/undergraduate/institutional-credit/` and its `ap/`, `clep/`, `ib/` subpages
  - `/undergraduate/graduation-requirements/`
  - `/undergraduate/regulations-procedures/`

  Save `document.querySelector('main').outerHTML` from each into the file above (read through the browser tool, then written with Write).
- [ ] **Step 2:** Verify each file contains its `<table>` (AP ≥ 50 rows) and the policy paragraphs (grep "maximum of 50%").
- [ ] **Step 3: Commit** `data: catalog snapshots (institutional credit, AP/CLEP/IB, graduation, regulations)`

### Task 7: AP, IB, and CLEP from the catalog, plus the policy refresh

**Files:**
- Create: `backend/pipeline/catalog_tables.py`
- Modify: `backend/pipeline/exams.py` (use the snapshot tables, keeping Appendix B as a fallback and diffing against it)
- Modify: `data/manual/policies.json` (exam cap, catalog of entry, repeat policy, each with source URLs)
- Test: `backend/tests/pipeline/test_catalog_tables.py`

**Interfaces:**
- Produces:
  - `parse_exam_table(html: str, program: Literal["AP","IB","CLEP"], url: str) -> list[dict]`. Each row is `{id, program, exam, min_score, awards: list[list[str]], generic_credit: str|None, source}`.
  - The `awards` option lists use exact codes only. A row whose credit contains no course code sets `generic_credit` to that text and `awards=[]`.

- [ ] **Step 1: Write the failing tests** (against the committed snapshot):

```python
from pathlib import Path
from pipeline.catalog_tables import parse_exam_table

AP = Path(__file__).parents[3] / "data/raw/catalog/ap.html"


def rows() -> list[dict]:
    return parse_exam_table(AP.read_text(), "AP", "https://catalog.atu.edu/undergraduate/institutional-credit/ap/")


def test_calculus_bc_awards_both_calculus_courses() -> None:
    bc = next(r for r in rows() if r["exam"] == "Calculus BC")
    assert bc["min_score"] == 3 and bc["awards"] == [["MATH 2914", "MATH 2924"]]


def test_chemistry_alternatives_are_separate_options() -> None:
    chem = next(r for r in rows() if r["exam"] == "Chemistry")
    assert ["CHEM 2124", "CHEM 2134"] in chem["awards"] and len(chem["awards"]) == 2


def test_generic_credit_is_not_mapped_to_a_course() -> None:
    aas = next(r for r in rows() if r["exam"] == "African American Studies")
    assert aas["awards"] == [] and "Humanities" in aas["generic_credit"]


def test_same_exam_higher_score_is_its_own_row() -> None:
    bio = [r for r in rows() if r["exam"] == "Biology"]
    assert {(r["min_score"], tuple(r["awards"][0])) for r in bio} == {(3, ("BIOL 1014",)), (4, ("BIOL 1114",))}
```

- [ ] **Step 2: Run** `uv --directory backend run pytest tests/pipeline/test_catalog_tables.py -v`. Expected: FAIL (module missing).

- [ ] **Step 3: Implement** `parse_exam_table` with BeautifulSoup:
  - Columns are exam | score | credit.
  - Split the credit text on `, or ` and ` or ` into options. Within an option, extract codes with `re.findall(r"\b([A-Z]{2,4}) ?(\d{4})\b", ...)` and carry the subject forward for bare numbers ("MATH 2914 & 2924").
  - `id = f"{program.lower()}-{slug(exam)}-{min_score}"`.
  - `exams.py`: when the snapshot exists, use it for AP/IB/CLEP. Log `appendix_b_diff` in `meta.json`.
  - Keep `exam_codes` in `build.py` as the union across all tables, so those courses get built.

- [ ] **Step 4: Refresh `policies.json`** from the snapshots: the exam cap, catalog of entry, and repeat policy. Update the `policies.py` readers and `tests/unit/test_policies.py` for any changed value. Log D22 (snapshots) and D23 (the cap decision, with quotes of both pages).

- [ ] **Step 5: Run** `make pipeline-offline && make test`. Fix `test_a5`/`test_a8` only where the source data changed, and record why in DECISIONS. Never weaken a test.

- [ ] **Step 6: Commit** `feat(data): AP, IB, and CLEP credit from the ATU catalog; refreshed credit policies`

### Task 8: AP/IB entry in Setup and course links to the catalog

**Files:**
- Modify: `frontend/src/pages/Setup.tsx` (`ExamEntry`: program selector AP/CLEP/IB, exam list from `/api/exams`)
- Create: `frontend/src/catalog.ts`
- Modify: `Timeline.tsx`, `BottleneckGraph.tsx`, `AdvisorExport.tsx` (the course code becomes a link)
- Test: `frontend/src/catalog.test.ts`

- [ ] **Step 1: Check the URL pattern** in Chrome: `https://catalog.atu.edu/search/?P=COMS%201013` shows the course entry.
- [ ] **Step 2: Write the failing test**

```ts
import { catalogUrl } from './catalog'
it('links a course code to its catalog entry', () => {
  expect(catalogUrl('COMS 1013')).toBe('https://catalog.atu.edu/search/?P=COMS%201013')
})
```

- [ ] **Step 3: Implement**

```ts
export const catalogUrl = (code: string): string => `https://catalog.atu.edu/search/?P=${encodeURIComponent(code)}`
```

Wire it into the three components with `target="_blank" rel="noreferrer"`. Add the AP and IB programs to `ExamEntry`.

- [ ] **Step 4: Run** `make test && make lint`. Commit `feat(ui): enter AP and IB scores; course codes link to the ATU catalog`

---

## Phase 5: Degree maps for every catalog year

### Task 9: Ingest every catalog year

**Files:**
- Modify: `backend/pipeline/discover.py:96-123` (return refs for every year page)
- Modify: `backend/pipeline/build.py` (`newest` is still recorded; `catalog_years` is added to meta; report grouped by year)
- Modify: `backend/pipeline/report.py`
- Modify: `backend/tests/acceptance/test_all_programs.py` (parametrize over all programs, both years)
- Test: `backend/tests/pipeline/test_discover_years.py`

**Interfaces:**
- Produces: `discover(fetcher) -> tuple[str, list[MapRef]]` (unchanged signature) now includes every year. Also `meta["catalog_years"]: list[str]`, for example `["2025-26", "2026-27"]`.

- [ ] **Step 1: Write the failing test**

```python
from pipeline.common import Fetcher
from pipeline.discover import discover


def test_discovers_every_listed_catalog_year() -> None:
    newest, refs = discover(Fetcher(online=False, refresh=False))
    years = {r.catalog_year for r in refs}
    assert newest == "2026-27" and years == {"2025-26", "2026-27"}
    assert sum(r.catalog_year == "2025-26" for r in refs) >= 75
```

- [ ] **Step 2:** Run it. Expected: FAIL (only 1 ref for 2025-26).
- [ ] **Step 3: Implement.** Loop over every year page in `discover`. Then run `make pipeline` (online) to download the 2025-26 PDFs into `data/raw/degree_maps/2025-26/` and fetch Banner details for any new course codes.
- [ ] **Step 4: Run**
  - `make pipeline-offline`
  - `uv --directory backend run pytest tests/acceptance/test_all_programs.py -q`

  Fix parser or planner failures the new maps expose, each with a fixture test in `tests/pipeline/test_parser_fixtures.py`. Record the per-year tier counts from `data/REPORT.md`.
- [ ] **Step 5: Commit** in two parts:
  - `data: 2025-26 degree maps for every major`
  - `feat(pipeline): ingest every catalog year on the degree-map index`

### Task 10: Catalog-year choice and the "switch to a newer catalog" what-if

**Files:**
- Create: `data/manual/catalog_successors.json` (`{"computer-science-2025-26": ["computer-science-ai-2026-27", "computer-science-software-dev-2026-27"]}`)
- Modify: `backend/pipeline/build.py` (each program gets `successors: list[str]`, paired by map filename or the manual table)
- Modify: `backend/shortcut/schemas/api.py`, `routes.py` (`ProgramListItem.successors`, `ProgramListItem.major_key`)
- Modify: `frontend/src/components/ProgramPicker.tsx` (one row per `major_key`, with year buttons)
- Modify: `frontend/src/pages/Setup.tsx` (default year from `first_term`; helper copy)
- Modify: `frontend/src/components/WhatIfPanel.tsx` ("Newer catalog" option using `change_major`)
- Create: `frontend/src/catalogYear.ts`
- Test: `backend/tests/unit/test_api.py::test_programs_list_successors`, `frontend/src/catalogYear.test.ts`

**Interfaces:**
- Produces: `catalogYearFor(termId: string): string`. `2025FA` → `2025-26`, `2026SP` → `2025-26`, `2026SU` → `2025-26`, and `2026FA` → `2026-27`.

- [ ] **Step 1: Write the failing tests**

```ts
import { catalogYearFor } from './catalogYear'
it.each([
  ['2025FA', '2025-26'], ['2026SP', '2025-26'], ['2026SU', '2025-26'], ['2026WI', '2026-27'], ['2026FA', '2026-27'],
])('%s starts in the %s catalog', (term, year) => expect(catalogYearFor(term)).toBe(year))
```

```python
def test_programs_list_successors(client) -> None:
    items = {p["id"]: p for p in client.get("/api/programs").json()}
    assert items["accounting-2025-26"]["successors"] == ["accounting-2026-27"]
    assert set(items["computer-science-2025-26"]["successors"]) == {
        "computer-science-ai-2026-27", "computer-science-software-dev-2026-27"}
```

Note on `2026WI`: winter intersession runs Dec 2026–Jan 2027, inside academic year 2026–27.

- [ ] **Step 2:** Run both. Expected: FAIL.
- [ ] **Step 3: Implement**

```ts
export function catalogYearFor(termId: string): string {
  const year = Number(termId.slice(0, 4))
  const season = termId.slice(4)
  const start = season === 'FA' || season === 'WI' ? year : year - 1
  return `${start}-${String((start + 1) % 100).padStart(2, '0')}`
}
```

  - Backend: `major_key` is the map filename stem, and `successors` are the same-stem programs in newer years plus the manual table.
  - Picker: search results show one row per `major_key` with its years as buttons, defaulting to `catalogYearFor(profile.first_term)` when available.
  - What-if: when `successors` is non-empty, show "Switch to the {year} catalog" buttons that run `change_major`. Cite the catalog-of-entry policy source.
- [ ] **Step 4: Run** `make test && make lint`. Commit `feat: choose a major's map by catalog year; what-if for switching to a newer catalog`

---

## Phase 6: Degree Works import

### Task 11: Audit parser (pure TypeScript)

**Files:**
- Create: `frontend/src/degreeworks/parse.ts`
- Create: `frontend/src/degreeworks/types.ts`
- Create: `frontend/src/degreeworks/fixtures/sample-audit.ts` (a synthetic audit: "Sample, Student", ID T00000000, the same shapes as a real audit)
- Test: `frontend/src/degreeworks/parse.test.ts`

**Interfaces:**
- Produces:

```ts
export interface AuditCourse {
  code: string            // "COMS 1013"
  title: string
  grade: string           // raw: A B C D F P W CE IP TA… (as printed)
  credits: number
  term: string | null     // "2025FA"
  exam: string | null     // "AP07 - COMPUTER SCIENCE A" when "Satisfied by … Credit by AP Exam"
  examProgram: 'AP' | 'CLEP' | 'IB' | null
  transfer: boolean
  section: 'requirement' | 'not_used' | 'in_progress'
}
export interface StillNeeded { label: string; codes: string[] }  // "Algorithm Design and Analysis", ["COMS 3213"]
export interface AuditImport {
  degree: string | null        // "BS Computer Science"
  catalogYear: string | null   // "2025-26"
  gpa: number | null
  creditsRequired: number | null
  creditsApplied: number | null
  courses: AuditCourse[]       // unique by code; the requirement section wins over in_progress duplicates
  stillNeeded: StillNeeded[]
  unrecognized: string[]       // lines that look like course rows but didn't parse
}
export function parseAudit(lines: string[]): AuditImport
```

Name and student ID lines are skipped, and no field holds them.

- [ ] **Step 1: Write the fixture.** Use line arrays shaped like pdf.js output: one string per visual line, with wrapped cells on the next line. The rows must include:
  - `TECH 1001 ORIENTATION TO UNIVERSITY A 1 Fall Term 2025`
  - `ENGL 1013 COMPOSITION I CE 3 Spring Term` then the next line `2024`, then `Satisfied by: AP10 - ENGLISH LITERATURE/COMP - Credit by AP Exam`
  - `COMS 2163 SCRIPTING LANGUAGES IP (3) Fall Term 2026`
  - `Still needed: 1 Class in COMS 3213`
  - the "Not Used and Not Eligible for Financial Aid" section with `COMS 1411 COMPUTER/INFO SCI LAB CE 1 Spring Term 2025`
  - `Catalog year: 2025-2026`, `Overall GPA` then `3.500`, `Credits required: 120 Credits applied: 77`
  - a transfer row: `ENGL 2003 INTRO TO LITERATURE TA 3 Summer Term 2024` then `Satisfied by: ENGL 2113 - INTRO TO LIT - Some Community College`
- [ ] **Step 2: Write the failing tests**

```ts
import { parseAudit } from './parse'
import { SAMPLE_AUDIT } from './fixtures/sample-audit'

const audit = parseAudit(SAMPLE_AUDIT)
const byCode = (c: string) => audit.courses.find((x) => x.code === c)!

it('reads catalog year, GPA and credit totals', () => {
  expect(audit.catalogYear).toBe('2025-26')
  expect(audit.gpa).toBe(3.5)
  expect([audit.creditsRequired, audit.creditsApplied]).toEqual([120, 77])
})
it('reads posted AP credit with its exam and a wrapped term', () => {
  expect(byCode('ENGL 1013')).toMatchObject({ grade: 'CE', examProgram: 'AP', term: '2024SP', credits: 3 })
})
it('reads in-progress rows with parenthesized credits', () => {
  expect(byCode('COMS 2163')).toMatchObject({ grade: 'IP', credits: 3, term: '2026FA' })
})
it('keeps unapplied credit from the Not Used section', () => {
  expect(byCode('COMS 1411')).toMatchObject({ section: 'not_used', credits: 1 })
})
it('marks transfer credit', () => {
  expect(byCode('ENGL 2003').transfer).toBe(true)
})
it('collects still-needed course codes', () => {
  expect(audit.stillNeeded).toContainEqual({ label: expect.any(String), codes: ['COMS 3213'] })
})
it('never exposes the student name or ID', () => {
  expect(JSON.stringify(audit)).not.toMatch(/Sample, Student|T00000000/)
})
```

- [ ] **Step 3: Run** `cd frontend && npx vitest run src/degreeworks`. Expected: FAIL.
- [ ] **Step 4: Implement `parseAudit`** as a single pass over lines:
  - Section tracking: "Not Used" means `not_used`, and "In-progress" means `in_progress`. Everything else is `requirement`.
  - Row regex: `/\b([A-Z]{2,4}) (\d{4})\s+(.+?)\s+(A|B|C|D|F|P|W|CE|IP|T[A-D]|TP|TR)\s+\(?(\d+(?:\.\d+)?)\)?\s*(Fall|Spring|Summer|Winter)?(?: Term)?\s*(\d{4})?/`. When the year is missing, take it from the next line if that line is `^\d{4}$`.
  - A "Satisfied by:" line attaches to the previous course. `Credit by (AP|CLEP|IB) Exam` sets exam and examProgram. Any other "Satisfied by" on a T-grade row sets `transfer=true`.
  - `Still needed:` lines collect codes with subject carry-forward ("PHSC 1013 or 1053 or CHEM 1113").
  - A line starting with a course code that fails the regex goes to `unrecognized`.
- [ ] **Step 5: Run** the tests. Expected: PASS. Commit `feat(degreeworks): parse a Degree Works audit into courses, credit, and still-needed items`

### Task 12: Audit → profile

**Files:**
- Create: `frontend/src/degreeworks/toProfile.ts`
- Test: `frontend/src/degreeworks/toProfile.test.ts`

**Interfaces:**
- Consumes: `AuditImport` (Task 11), `ProgramListItem` with `major_key` and `catalog_year` (Task 10), `CompletedCourse` with `source: 'exam'`, `hours`, and `exam` (Task 3).
- Produces:

```ts
export interface ProfileImport {
  profile: StudentProfile
  programMatch: 'exact' | 'year_missing' | 'none'
  notes: string[]           // plain-language assumptions shown on the review screen
}
export function auditToProfile(audit: AuditImport, programs: ProgramListItem[]): ProfileImport
```

Rules:
- Match the program: normalize `audit.degree` ("BS Computer Science") against `name` and `degree_abbr`, then pick the entry whose `catalog_year === audit.catalogYear`. If no year matches, set `year_missing` and choose the newest year. If nothing matches, set `none` and leave `program_id` as ''.
- Grades:
  - `CE`, and T-grades with `examProgram`, become `{source:'exam', grade:'P', hours: credits, exam}`.
  - T-grades become `{source:'transfer', grade: letter after T, or 'P' for TP/TR, hours}`.
  - Letter grades become `{source:'atu', grade, hours}`.
  - `IP` becomes `in_progress`.
  - `W` is skipped.
- `first_term` is the earliest `term` of an ATU-graded (non-exam, non-transfer) row, and `plan_from` is the term after the latest IP term. The fallback for both is the next fall or spring after today.
- `preferences.expect_high_gpa = gpa >= 3.25`, plus a note.

- [ ] **Step 1: Write the failing tests**

```ts
it('builds a profile the planner accepts', () => {
  const { profile, programMatch } = auditToProfile(parseAudit(SAMPLE_AUDIT), PROGRAMS)
  expect(programMatch).toBe('exact')
  expect(profile.program_id).toBe('computer-science-2025-26')
  expect(profile.completed.find((c) => c.code === 'ENGL 1013')).toEqual(
    { code: 'ENGL 1013', grade: 'P', source: 'exam', hours: 3, exam: 'AP10 - ENGLISH LITERATURE/COMP' })
  expect(profile.completed.find((c) => c.code === 'COMS 1411')?.hours).toBe(1)
  expect(profile.in_progress).toContain('COMS 2163')
  expect(profile.first_term).toBe('2025FA')
  expect(profile.plan_from).toBe('2027SP')
})
it('reports a catalog year Shortcut does not have', () => {
  const audit = { ...parseAudit(SAMPLE_AUDIT), catalogYear: '2019-20' }
  expect(auditToProfile(audit, PROGRAMS).programMatch).toBe('year_missing')
})
it('reports an unknown major instead of guessing', () => {
  const audit = { ...parseAudit(SAMPLE_AUDIT), degree: 'BS Underwater Basketry' }
  const r = auditToProfile(audit, PROGRAMS)
  expect(r.programMatch).toBe('none')
  expect(r.profile.program_id).toBe('')
})
```

- [ ] **Step 2:** Run. FAIL. **Step 3:** Implement. **Step 4:** Run. PASS.
- [ ] **Step 5: Commit** `feat(degreeworks): turn an audit into a Shortcut profile`

### Task 13: PDF reading in the browser and the import screen

**Files:**
- Modify: `frontend/package.json` (add `pdfjs-dist`)
- Create: `frontend/src/degreeworks/pdfLines.ts`
- Create: `frontend/src/components/AuditImport.tsx`
- Modify: `frontend/src/pages/Landing.tsx`, `frontend/src/pages/Setup.tsx`, `frontend/src/App.tsx`
- Test: `frontend/src/degreeworks/pdfLines.test.ts` (line grouping from mocked text items), `frontend/src/components/components.test.tsx` (review screen)

**Interfaces:**
- Produces:
  - `groupTextItems(items: {str: string; x: number; y: number}[]): string[]`: sorts by y (descending) then x, joins items within 2.5pt of y into one line, and separates items with a single space.
  - `readPdfLines(file: File): Promise<string[]>`: lazy `import('pdfjs-dist')`, worker via `?url` import, and `groupTextItems` per page.

- [ ] **Step 1: Write the failing test** for `groupTextItems`, covering two items on one baseline and one wrapped item below.
- [ ] **Step 2: Implement.** In `AuditImport.tsx`:
  - a file input (accept `application/pdf`) with the privacy line "Read on your device. Your name and student ID are never saved or sent."
  - then `readPdfLines`, `parseAudit`, and `auditToProfile`
  - then a review panel with the program and catalog year (picker if not exact), counts (completed, exam credit, transfer, in progress, not used), notes, and unrecognized lines
  - then "Use this record", which saves the request and navigates to the plan
  - Keep the parsed `AuditImport` in session state (not the URL) for Task 14.
- [ ] **Step 3: Manual check.** Load the owner's real audit PDF in Chrome (from `~/Downloads`, never copied into the repo). Expected: CS 2025-26, 77 credits applied, a plan with no manual edits. Confirm there's no network request containing PDF bytes in the DevTools network log.
- [ ] **Step 4: Run** `make test && make lint && make build`. Commit `feat: import a Degree Works audit (read in the browser)`

### Task 14: Audit vs. plan panel

**Files:**
- Create: `frontend/src/degreeworks/reconcile.ts`
- Create: `frontend/src/components/AuditCheck.tsx`
- Modify: `frontend/src/pages/PlanPage.tsx` (panel under the headline when an import is present), `AdvisorExport.tsx` (a "Differences to raise with your advisor" list)
- Test: `frontend/src/degreeworks/reconcile.test.ts`

**Interfaces:**
- Produces:

```ts
export interface Reconciliation {
  agree: number
  total: number
  onlyInAudit: StillNeeded[]            // audit still needs it; Shortcut doesn't plan any of its codes
  onlyInPlan: { code: string | null; label: string }[]   // planned, but no still-needed line covers it
  creditsAudit: number | null
  creditsShortcut: number
}
export function reconcile(audit: AuditImport, plan: PlanResponse): Reconciliation
```

- A still-needed line agrees when any of its codes is planned, or a planned bucket's `options` intersect its codes. Generic lines ("9 Credits in @ 3@ or 4@") agree with any planned upper-level elective.
- `creditsShortcut` is the sum of `plan.credited` hours.

- [ ] **Step 1: Write the failing tests:**
  - "COMS 3213 still needed + planned" means agree
  - "science line + planned Science with Lab bucket with BIOL 1014 option" means agree
  - "audit line with codes Shortcut doesn't plan" means onlyInAudit
- [ ] **Step 2:** Run. FAIL. **Step 3:** Implement and the UI:
  - The panel shows "Degree Works and this plan agree on {agree} of {total} remaining requirements."
  - Then two short lists.
  - Credit totals are shown side by side.
  - Differences are neutral text, not errors.
- [ ] **Step 4: Run** `make test && make lint`. Commit `feat: compare a Degree Works audit with the plan`

---

## Phase 7: Documentation and release

### Task 15: README, About, CLAUDE.md, decisions

**Files:** `README.md`, `frontend/src/pages/About.tsx`, `CLAUDE.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md`, `docs/prd/v1.1.md` (status → Shipped), `docs/prd/v1.md` (link to v1.1), `docs/screenshots/*`

- [ ] **Step 1: README**
  - CI badge
  - one-paragraph pitch
  - the §1 comparison table plus a "How Shortcut uses it" column
  - the Degree Works import in the demo script
  - one anonymized line: "Run on the owner's own Degree Works audit (Fall 2025 CS admit), Shortcut finds May 2028, a year ahead of the 2025–26 map, and shows the fall-only capstone chain that sets that date." Use the measured date from Task 4.
  - a "How it was built" section: PRD and acceptance tests written by the owner, built by directing Claude Code, and the decision log
  - updated numbers from `data/REPORT.md` and resume bullets
- [ ] **Step 2: About page.** The same three-source table with snapshot capture dates and a per-year tier table.
- [ ] **Step 3: CLAUDE.md.** Remove the "owner is asleep / never ask" operating mode. Keep the build, data, planner, and UI rules, and update the UI rules to spec §3.5 and the paths to `docs/`.
- [ ] **Step 4: Screenshots.** Recapture landing, plan, bottlenecks, what-if, the import review (synthetic fixture PDF or a demo persona, never the real audit), and mobile at 1360×900 in Chrome.
- [ ] **Step 5: Run** `make lint && make test && make build`. Commit `docs: v1.1 README, About page, and build brief`

### Task 16: Verify, push, pull request, GitHub metadata

- [ ] **Step 1:** Run `make lint && make test && make build`, then `make serve` with an HTTP smoke test of every endpoint and persona. Also do a `docker build` if Docker is available locally; otherwise rely on the CI docker job.
- [ ] **Step 2:** `git push -u origin feat/atu-sources`, then `gh pr create` with a summary, test evidence, and screenshots. The body ends with the Claude Code line.
- [ ] **Step 3:**
  - `gh repo edit --description "Plan your fastest realistic path to graduation at Arkansas Tech: imports Degree Works, reads the catalog, and schedules with a constraint solver." --add-topic ...`
  - Topics: `graduation-planner, constraint-programming, or-tools, fastapi, react, typescript, degree-audit, product-management`.
  - `gh api -X PATCH repos/yengnongxiong/shortcut -f delete_branch_on_merge=true`
  - `git push origin --delete claude/optimistic-bohr-nwjsi5`
- [ ] **Step 4:** Wait for the CI checks on the PR to go green. Report the PR link to the owner, who merges.
- [ ] **Step 5:** Recheck contributions: the GraphQL `contributionsCollection` for `yengnongxiong/shortcut` should show more than 1 commit.
