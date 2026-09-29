# Progress

Resume here: read this file first, then DECISIONS.md, then continue from the first unchecked milestone.

## Status by milestone
- [x] **M0 Scaffold**: backend (uv, FastAPI), frontend (Vite React TS, Tailwind v4, Vitest, ESLint), Makefile, docs.
- [x] **M1 CS data, exam tables, policies**
  - Discovery + download of every degree map (82 PDFs: 81 for 2026–27 plus 2025–26 CS) and the policy/calendar pages.
  - Coordinate-based PDF parser (`backend/pipeline/parse_degree_map.py`); the CS 2025–26 parse matches PRD Appendix A (`tests/pipeline/test_cs_ground_truth.py`). Fixture tests cover 4 other layouts.
  - catalog.atu.edu is WAF-gated from this environment (D5), so course data comes from ATU's public Banner catalog and class schedule. The raw snapshots are committed: 836 course details, 15 terms × 76 subjects of schedule history.
  - `data/manual/policies.json` encodes PRD §8 with sources and confidence and is tested rule by rule. CLEP comes from Appendix B; AP/IB are unavailable (D6).
  - Offering confidence follows PRD §7.4 plus schedule history (D8).
- [x] **M2 Planner**: CP-SAT model (`shortcut/planner/model.py`) with two-phase solve (earliest graduation, then polish), slack/critical path, lever attribution, what-if, exam opportunities, and delay impact. A1–A8 pass; synthetic tests cover chains, coreqs, OR prereqs, standing, caps, transfer/residency, the exam cap, min grades, and infeasibility.
- [x] **M3 API**: every PRD §11 endpoint plus `/api/personas`; `tests/unit/test_api.py`. Latency is measured below.
- [x] **M4 Frontend core**: landing (search + personas), 3-step setup, plan view (comparison headline, timeline, lever panel, warnings), share URL + localStorage.
- [x] **M5**: bottleneck graph (xyflow + dagre, click to delay or fail), exam opportunities with add-to-plan, what-if panel, advisor export with print CSS.
- [ ] **M6 All majors**: pipeline runs on all 74 bachelor's maps (58 Auto-imported, 16 Needs review as of the last run). Manual cross-checks are still to do.
- [ ] **M7**: P3/P4 personas + my-path template, README, polish. Dockerfile and CI are drafted.
- [ ] **M8 Final QA**

## Checks (last run)
- Backend: `ruff check`, `ruff format --check`, `mypy --strict`: clean. `pytest`: 69 tests pass, including A1–A10 (A10 requires `make build` first).
- Frontend: `tsc -b`, `eslint`: clean. `vitest`: 11 tests pass. `npm run build` OK.

## Environment notes
- Network: www.atu.edu, reg-prod.ec.atu.edu (Banner), and adhe.edu are reachable. catalog.atu.edu is not (its WAF challenge host `*.token.awswaf.com` is denied).
- Working branch: `claude/optimistic-bohr-nwjsi5` (PRD/CLAUDE.md/settings were committed to `main` first).
- The Banner fetch takes about 30 minutes cold (3,725 requests). `make pipeline-offline` rebuilds from the committed snapshots in about 1 minute.
- Git author is the owner's GitHub noreply address (D1).

## Next step
M6: cross-check CS plus 4 majors from different colleges, record them in `data/manual/cross_checks.json`, and re-run the pipeline. Then M7 personas P3/P4.
