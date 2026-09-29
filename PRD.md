# Shortcut: Product Requirements Document (v1)

Owner: Yengnong Xiong · Status: Ready to build · Last updated: 2026-09-29

## 1. Summary
Shortcut is a web app that builds an Arkansas Tech University (ATU) student's fastest realistic path to graduation. It starts from where the student is now (completed courses, AP/CLEP/IB scores, transfer credit, placement). It models every acceleration option ATU allows: exam credit, summer, winter intersession, heavier loads, overloads, and transfer. It outputs three things:
- a term-by-term plan,
- the courses that actually set the graduation date (the critical path),
- how much time each option saves.

Positioning: ATU's degree map is the path for the average student. Shortcut is the path for you.

Not affiliated with ATU. Not official advising. Portfolio demo: no real users, no accounts.

## 2. Problem
- ATU publishes one static degree map per major: an 8-semester sample schedule. It assumes a first-time freshman with no credit, full-time fall/spring enrollment, and no failed courses. These guaranteed eight-semester plans exist because of Arkansas Act 1014 of 2005.
- Real students deviate from that path. They arrive with AP, CLEP, or dual credit. They fail or drop courses, change majors, or want to finish early to save money.
- The information needed to find a faster path is public, but it's scattered across degree map PDFs, catalog course descriptions, credit-by-exam tables, and academic regulations. Nobody assembles it for a specific student.
- The costliest mistake is invisible: missing one link in a chain of fall-only or spring-only courses can delay graduation by a full year.
- Founder insight: the owner graduated a year early at ATU by assembling this by hand with CLEP and AP credit.

## 3. Users
Primary users are ATU undergraduates planning their path, especially:
- students with prior credit,
- students who want to finish early,
- off-track students recovering from a failed or dropped course.

Secondary users are academic advisors, who receive a student's Shortcut plan as a conversation starter.

Personas, shipped as one-click demo profiles:
- P1 "Starting from scratch": incoming CS freshman, Fall 2026, no credit, math ACT 27.
- P2 "Exam-credit sprinter": CS student with several AP/CLEP credits. Sample data, clearly labeled as such.
- P3 "Off-track junior": a student in a second cross-checked major who failed a fall-only course. Demonstrates what-if recovery.
- P4 "No shortcut" (only if a cohort- or admission-based major gets cross-checked): demonstrates Shortcut honestly explaining when a program can't be compressed.
- Template: data/personas/my-path.template.json, for the owner to fill in with real credits.

## 4. Competitive landscape
| Alternative | What it does | Gap Shortcut fills |
|---|---|---|
| ATU degree maps (one PDF per major) | Sample 8-semester schedule, fall/spring only, starting from zero credit | Not personalized; ignores exam credit, summer, winter, and overloads; never recalculates; doesn't surface bottlenecks |
| Academic advisor | Personalized human guidance | Limited meeting time; hard to compare many scenarios live. Shortcut prepares students for the meeting rather than replacing it |
| Degree audit tools in OneTech (if present; to confirm) | Track completed vs. remaining requirements | Show what's left, but don't optimize order and timing or compare acceleration options |

## 5. Goals and non-goals
Goals (v1):
- G1: Generate a valid term-by-term plan for any ATU bachelor's major with a published degree map.
- G2: Model every acceleration option in §8 and show each one's marginal impact on graduation date.
- G3: Surface the critical path and per-course slack.
- G4: Be honest about data quality. Label every major by trust tier and make every assumption visible.
- G5: Be demo-ready: four personas, a polished UI, loads in seconds, and understandable in under a minute.

Non-goals:
- official advising or degree certification
- registration
- accounts or login
- real-time seat availability
- financial aid math
- graduate programs, certificates, associate degrees, and minors (though the data model must not preclude them)
- other universities
- any LLM API calls at runtime

## 6. Features

F1 Major picker
- Search all ingested bachelor's programs.
- Show college, catalog year, and a trust badge: Cross-checked, Auto-imported, or Needs review.
- Needs-review programs stay selectable but show a prominent warning.

F2 Student profile (3-step setup)
- Step 1: major, catalog year, first term at ATU, and the term to plan from.
- Step 2: credit already earned:
  - A checklist of the program's courses, with a grade for completed ones (default "C or better").
  - In-progress courses.
  - AP/CLEP/IB exams with scores, auto-mapped through ATU's tables.
  - Transfer courses, entered by ATU-equivalent code.
  - Math ACT subscore, for placement.
- Step 3: preferences:
  - Preferred max hours per regular term (default 16).
  - Last-term GPA (optional), plus an "I expect to keep a 3.25+ GPA" checkbox for overload eligibility.
  - Availability mode: Conservative or Optimistic (§7.4).
- Persist the profile in localStorage and in a shareable URL.

F3 Plan view
- Headline comparison, for example: "Degree map: May 2030 · Standard pace: May 2030 · Your Shortcut: May 2029 · 2 terms sooner". It compares against:
  - (a) the degree map's 8 semesters counted from the student's first term, and
  - (b) standard pace: fall/spring only, no summer or winter, at most the preferred hours per term (default 16).
- Term-by-term timeline:
  - Fall, Winter, Spring, and Summer columns, shown only when used.
  - Course chips with hours and badges: exam credit, transfer, critical, low-confidence offering.
  - Hour totals per term.
  - Estimated weekly workload per term, using ATU's guidance of 2–3 hours outside class per credit hour.

F4 Acceleration levers
Each lever is a toggle that shows:
- terms saved (marginal: the full plan vs. the same plan with only this lever turned off),
- a cost tag: extra tuition, exam fee, or none (no invented dollar amounts),
- an approval tag: none, advisor, or dean petition,
- a workload tag.

The levers:
- Heavier regular terms (up to 18 hrs; no petition needed)
- Summer terms
- Winter intersession
- Overloads (19–21 hrs; eligibility required; dean petition)
- Aggressive overloads (22–24 hrs; flagged for Academic Affairs review)
- Transfer summer courses at another Arkansas public college (ACTS-equivalent courses only)
- Planned exams (added from F6)

Credit for Prior Learning appears as an informational "ask your department" card and is never scheduled.

F5 Bottleneck view
- A prerequisite graph of remaining courses, laid out left to right by term.
- The critical chain is highlighted.
- Each node shows its slack (in terms) and offering pattern (F/S/Su/W).
- Clicking a course offers two actions:
  - "What if I delay this one term?" (a true re-solve)
  - "What if I fail it?" (F7)

F6 Exam opportunities
- A ranked list of ATU-accepted exams that map to a still-needed requirement. CLEP comes first; AP and IB are listed for incoming students.
- Each row shows: exam, qualifying score, courses awarded, requirement satisfied, credit hours saved, and terms saved (true re-solve).
- Only exact course-code matches, or courses listed in a requirement bucket, count. Never assume equivalence.
- Respect the exam-credit cap (§8).
- Each row has an "add to plan" toggle.

F7 What-if
- Events: fail course X in term T; drop to N hours in term T; skip term T; change major (re-plan against another program with the same credits).
- Show before/after graduation terms and which terms changed.

F8 Warnings and assumptions
- Policy checks:
  - residency
  - upper-level hours
  - total hours
  - exam cap
  - overload eligibility
  - no overload in the first ATU term
  - standing requirements
- Data warnings: needs-review program, low-confidence offerings, unparsed prerequisites.
- Note that exam credit doesn't count toward GPA, so it can't help keep a scholarship.
- Every warning links to its source.

F9 Advisor export
- A print-friendly one-page summary: plan table, levers used, petitions needed and who approves them, assumptions, and the disclaimer.
- A copyable share link.

F10 About the data
- Sources with URLs.
- Catalog year and last pipeline run.
- Counts per trust tier.
- The full list of assumptions.
- A "not affiliated with ATU" disclaimer.

## 7. Data

7.1 Sources (all public; see Appendix C)
- Degree map PDFs: one per program, under https://www.atu.edu/advising/degreemaps_docs/<year>/. Find the index starting from https://www.atu.edu/advising/.
- Catalog course descriptions and program pages.
- Institutional credit pages: CLEP, AP, and IB.
- Regulations & procedures, graduation requirements, and the academic calendar.
- Optional: a public class schedule, if reachable without login, to confirm summer and winter offerings.

Ingest the newest catalog year's maps for all programs. Also ingest the 2025–26 CS map, which is the ground truth (Appendix A) and the owner's catalog year. If a newer CS map exists, record its differences from Appendix A rather than forcing a match.

7.2 Pipeline
- Python, reproducible with one command.
- Stages in order: discover → download (commit raw files) → parse degree maps → enrich from the catalog → exam tables → validate → assign trust tier.
- Outputs: processed JSON plus data/REPORT.md.

7.3 Model (JSON under data/processed/)
- Course:
  - code, title, hours, level
  - prerequisites: an AND/OR tree with minimum grades, plus the raw text and a parse_confidence value
  - corequisites and standing requirement
  - offered_in {FA, SP, SU, WI}, each with a source and a confidence level
  - acts_equivalent and source URLs
- Program:
  - id, name, degree, college, catalog_year
  - total_hours_min, upper_level_hours_min, gpa_min
  - requirements: either a specific course or a bucket {name, hours, allowed codes or a rule such as "3000–4000 level approved elective"}
  - map_schedule: the sample schedule, kept for the baseline
  - min_grade_courses and notes
  - trust_tier, validation results, and source URLs
- ExamEquivalency: {program: CLEP|AP|IB, exam, min_score, courses_awarded, source}
- Policies: the rules in §8, each with a value, source, and confidence.

7.4 Offering confidence
- Fall and spring:
  - With no restriction noted, a course counts as offered in both, labeled "assumed".
  - A "Fall Only" or "Spring Only" note from a map or the catalog is labeled "documented".
- Summer and winter:
  - 1000–2000 level gen-ed courses and gen-ed buckets are "likely (assumed)".
  - Everything else is "unknown".
- Conservative mode (the default) schedules summer and winter only for documented or likely courses. Optimistic mode also allows unknown courses and flags each use.

7.5 Trust tiers
- Cross-checked: all validation passed, plus a manual review against both the PDF and the catalog program page.
- Auto-imported: validation passed.
- Needs review: any validation check failed.
- Target: CS plus at least 4 other majors from different colleges reach Cross-checked.

7.6 Validation checks
- Semester hours sum to the stated semester totals.
- Total hours meet the stated minimum.
- Every prerequisite code resolves to a known course, or is flagged as external.
- No prerequisite cycles.
- Fall-only and spring-only flags agree between map and catalog; conflicts are flagged.
- Buckets are non-empty.
- The upper-level hour minimum is achievable.

## 8. Policies and assumptions (encode in data/processed/policies.json)
| Rule | Value | Confidence |
|---|---|---|
| Recommended max load | 18 hrs per fall/spring; more requires dean permission in advance | documented |
| Overload eligibility | Petition to dean; 3.25 GPA in the preceding term (≥12 ATU hrs), or good standing if it's the final semester | documented |
| Overload ceiling | 24 hrs in fall, spring, or summer; loads over 21 get Academic Affairs review | documented |
| First ATU term | No overload (no prior-term GPA) unless it's the final semester | derived |
| Probation | Loads over 15 hrs need advisor approval | documented (warning only in v1) |
| Workload guidance | 2–3 hrs outside class per credit hour | documented |
| Class standing | FR under 30, SO 30–59, JR 60–89, SR 90+ earned hrs | documented |
| Residency | ≥30 hrs taken at ATU, including ≥6 upper-division hrs in the major | documented |
| Total hours | ≥120 (a program may require more) | documented |
| Exam/prior-learning cap | CONFLICT: the institutional-credit page says max 50% of the degree; the graduation-requirements page says max 30 hrs from correspondence, extension, military, or exam credit. Use the stricter 30 hrs and flag "confirm with registrar" | conflicting |
| Exam credit and GPA | Not counted in GPA; can't be used to retain scholarships; no duplicate credit | documented |
| Terms | Fall; Winter intersession (e.g., Dec 14, 2026–Jan 1, 2027); Spring; Summer sessions (May, June/July, 10-week, July/August). Fall and spring also have 8-week sessions | documented |
| Math placement | Math ACT above 26 satisfies the Calculus I prerequisite (CS map) | documented |
| "MATH 1113 or higher" | Satisfied by any course on a hand-maintained math ladder (MATH 1113 and above in sequence) | derived |
| Summer max load (planning) | 12 hrs total across summer sessions, configurable | ASSUMED |
| Winter max load | 1 course, ≤4 hrs, configurable | ASSUMED |
| Summer sub-sessions | Treated as one planning term (no prerequisite chaining within a summer) | simplification |
| 8-week sessions | Not modeled (no chaining within a semester) | simplification |
| Standing counts exam/transfer hours | Yes | ASSUMED |

## 9. Planning engine

Solver
- OR-Tools CP-SAT, with a boolean x[course, term] over a horizon of up to 16 regular semesters plus optional summer and winter terms.

Constraints
- Each remaining requirement is satisfied exactly once, whether it's a specific course or a bucket slot.
- A course is placed only in terms allowed by its offering data and the availability mode.
- Prerequisites are satisfied in strictly earlier terms, or by existing credit, respecting minimum grades.
- Corequisites are in the same or an earlier term.
- Standing requirements are enforced through cumulative earned hours before the term.
- Per-term hour caps follow the term type and lever state. Overloads are allowed only when eligible.
- Residency, upper-level hours, total hours, and the exam cap all hold.
- Transfer courses go only in summer, and only for ACTS-equivalent lower-level courses. They don't count toward residency.
- General-elective filler slots are added if needed to reach total hours.

Objective (lexicographic, via weights)
1. Earliest graduation term.
2. Fewest summer/winter terms and overload hours used.
3. Closest to the student's preferred hours per term.
4. Balanced loads.

Critical path and slack
- After solving, run a calendar-aware forward/backward pass over the prerequisite DAG, respecting offering patterns and holding the graduation term fixed.
- Slack = latest feasible term minus scheduled term, counted in regular semesters. Slack 0 means critical.
- Label this "prerequisite slack (ignores hour caps)". The click-to-delay action in F5 uses a true re-solve.

Lever attribution
- Solve standard pace, the full plan, and one extra solve per enabled lever with only that lever disabled. Report marginal terms saved.

What-if
- Apply the event, then re-solve from the following term.
- A failed course is not credited and must be retaken.
- A grade below a course's required minimum doesn't satisfy prerequisites.

Performance and determinism
- 5-second time limit per solve.
- A full plan response, including attribution, should have p95 under 3 s for CS.
- On timeout, return the best feasible plan with a flag.
- Use a fixed seed so tests are reproducible.

## 10. UX and demo

Visual direction
- Clean, confident, editorial. Not a generic admin dashboard.
- One accent color for "critical" and one for "time saved".
- Neutral Shortcut branding; no ATU logos or trademarks.
- Responsive; the timeline scrolls horizontally on mobile.

Screen flow
Landing (headline, major search, persona buttons) → Setup (3 steps) → Plan (comparison headline, timeline, lever panel, warnings) → tabs: Bottlenecks, Exam opportunities, What-if, Advisor export → About the data.

60-second demo script (goes in the README)
1. Pick P1 and show the degree map vs. standard pace.
2. Toggle summer, winter, and heavier terms. The graduation date moves up and the lever panel credits each one.
3. Open Bottlenecks and point to the critical fall-only chain.
4. Run a what-if: fail that course, and graduation slips.
5. Switch to P2 and show the ranked exam opportunities.
6. Export for the advisor.

## 11. Architecture
- Backend: Python 3.12, uv, FastAPI, Pydantic v2, OR-Tools, pdfplumber, httpx, BeautifulSoup4, pytest, ruff, mypy.
- Frontend: React + TypeScript (strict) + Vite + Tailwind CSS, @xyflow/react with a dagre layout, Vitest + React Testing Library.
- Deployment unit: one service. FastAPI serves the built frontend and /api. JSON data is loaded at startup; there is no database.
- Includes a multi-stage Dockerfile and a GitHub Actions workflow for lint and test. The agent does not deploy anything.
- API endpoints:
  - GET /api/health, GET /api/meta
  - GET /api/programs, GET /api/programs/{id}, GET /api/exams
  - POST /api/plan, POST /api/plan/whatif
  - POST /api/plan/exam-opportunities, POST /api/plan/delay-impact

## 12. Success metrics
Demo (now):
- Acceptance tests pass.
- At least 90% of discovered bachelor's maps reach Auto-imported or better (report the real number).
- CS plus at least 4 other majors are Cross-checked.
- Plan p95 under 3 s.
- Every persona runs end to end.

If launched (for interview discussion; not built):
- North star: share of plans finding at least 1 term sooner than standard pace.
- Activation: a plan generated within 3 minutes of landing.
- Engagement: levers toggled per session; advisor exports per plan.
- Guardrails: user-reported data errors per 100 plans; share of plans relying on unknown-availability courses.

## 13. Risks
| Risk | Mitigation |
|---|---|
| Wrong data produces a bad plan | Trust tiers, sources on every warning, cross-checking, disclaimer, advisor-export framing |
| Policy ambiguity (e.g., the exam cap) | Use the stricter rule and flag the conflict |
| Unknown summer/winter offerings | Confidence labels; Conservative mode by default |
| Unhealthy course loads | Per-term workload estimates; overload levers off by default |
| Mistaken for an official ATU tool | Neutral branding and a "not affiliated" disclaimer |
| Unusual PDF layouts break the parser | Needs-review tier; fixture tests for each layout variant |

## 14. Milestones
Build CS end to end first, then scale:
- M0: Scaffold
- M1: CS data, exam tables, and policies
- M2: Planner engine
- M3: API
- M4: Frontend core
- M5: Bottlenecks, exam opportunities, what-if, advisor export
- M6: All-majors pipeline and cross-checks
- M7: Personas, About page, polish, README, Dockerfile, CI
- M8: Final QA

Done criteria for each milestone are in CLAUDE.md.

## 15. Acceptance tests (automated; name them test_a1_… through test_a10_…)
- A1: CS (2025–26), start Fall 2026, no credit, math ACT 27, standard pace (≤16 hrs, fall/spring only). Should produce a valid plan graduating by Spring 2030, satisfying Appendix A. If catalog prerequisites make that impossible, the test must identify the binding constraint, and the finding is logged in DECISIONS.md.
- A2: Same student with heavier terms, summer, winter, and overload (expects 3.25+) enabled, in Conservative mode. Graduation should be strictly earlier than A1. If documented constraints prevent that, the test must identify the binding constraint, and the finding is logged in DECISIONS.md. Never weaken constraints to make a test pass.
- A3: COMS 3213, 3703, 4103, and 4913 are scheduled only in fall; COMS 3313 only in spring.
- A4: COMS 3053 is scheduled only when cumulative earned hours are ≥60 before that term.
- A5: CLEP College Composition with a score of 59+ removes ENGL 1013 and ENGL 1023. Those hours count toward the exam cap and total hours, but not toward residency.
- A6: No term exceeds its cap, and the first ATU term never exceeds 18 hrs.
- A7: What-if "fail COMS 2213" on the A1 plan matches a true re-solve, with an explanation of the impact.
- A8: P1's exam opportunities list only exams whose awarded courses satisfy a still-needed requirement, ranked by terms saved, then hours saved.
- A9: The pipeline report lists every discovered program with its tier; no program is silently dropped.
- A10: The frontend builds; one process serves the app and API; every persona loads and renders a plan.

## 16. Open questions for the owner (after the first build)
- Q1: Replace P2's sample data with the owner's real credits for the "my path" story?
- Q2: Confirm the exam-credit cap with the registrar.
- Q3: Is a public class schedule available to confirm summer/winter offerings?
- Q4: Does OneTech include a degree audit or planning tool?
- Q5: Preferred deployment host?

## Appendix A: CS degree map 2025–26 (transcribed; parser ground truth and fallback seed)
"#" means a grade of C or higher is required.
- Sem 1 (14): ENGL 1013 Composition I 3 #; CSEC 1003 Intro to Cybersecurity 3; COMS 1333 Web and Mobile Technologies 3; TECH 1001 Orientation to the University 1; MATH 2914 Calculus I 4 # (prereq: math ACT >26, or C or better in MATH 1203/1914).
- Sem 2 (14): ENGL 1023 Composition II 3 #; CSEC 1113 Intro to Networking 3; COMS 1013 Programming Foundations I 3 (prereq: MATH 1113 or higher); COMS 1011 Programming Foundations I Lab 1 (pass/fail; coreq COMS 1013); MATH 2924 Calculus II 4.
- Sem 3 (15): COMS 2203 Programming Foundations II 3 (prereq: C or better in COMS 1013 and in MATH 1113 or higher); MATH 2703 Discrete Mathematics 3 (prereq: C or better in MATH 1113 or higher); COMS 2703 Computer Hardware & Architecture 3; COMM 2173 Business and Professional Speaking 3 (COMM 2003 may substitute); Social Sciences 3.
- Sem 4 (16): COMS 2213 Data Structures 3 (prereq: MATH 2703 and C or better in COMS 2203); COMS 2223 Computer Organization and Programming 3 (prereq: COMS 2203 and MATH 2703); COMS 2163 Scripting Languages 3 (prereq: COMS 1333 and COMS 2203); Science with Lab 4; ENGL 2053 Technical Writing 3 (prereq: ENGL 1023).
- Sem 5 (15): Fine Arts & Humanities 3; COMS 3703 Advanced Operating Systems 3 FALL ONLY (prereq: COMS 2213 and COMS 2223); COMS 3213 Algorithm Design & Analysis 3 FALL ONLY (prereq: COMS 2213); COMS 2323 Programming in Python 3 (prereq: COMS 2203); Approved Elective (3000–4000) 3.
- Sem 6 (16): Science with Lab 4; COMS 3053 Ethical Issues in Technology 3 (prereq: junior standing in COMS); COMS 3233 Data Design and Implementation 3 (prereq: COMS 2203); COMS 3313 Software Engineering 3 SPRING ONLY (prereq: COMS 3213); Approved Elective (3000–4000) 3.
- Sem 7 (15): STAT 3153 Applied Statistics 3 (prereq: MATH 2924); COMS 4913 Capstone I 3 FALL ONLY; COMS 4103 Organization of Programming Languages 3 FALL ONLY (prereq: COMS 2213 and COMS 2223); U.S. History/Government 3; Fine Arts & Humanities 3.
- Sem 8 (15): Social Sciences 3; MATH 4003 Linear Algebra I 3; COMS 4413 Parallel and Distributed Computing 3; COMS 4923 Capstone II 3; Approved Elective (3000–4000) 3.

Graduation requirements: ≥120 hrs; ≥40 hrs at the 3000–4000 level; ≤4 PE activity hrs; GPA ≥2.00; 9 hrs of approved 3000–4000 electives.

Prerequisites the map doesn't state (e.g., Calculus II, the capstones, MATH 4003, COMS 4413) must come from the catalog.

Gen-ed buckets, reconstructed from interleaved PDF text (confirm against the PDF):
- Fine Arts & Humanities: ART 2123, MUS 2003, TH 2273, ENGL/JOUR 2173, ENGL 2003, ENGL 2013, PHIL 2003, PHIL 2053, LEAD 2003, and 1013 or 1023 in SPAN, FR, GER, JPN, CHIN, or LAT.
- U.S. History & Government: HIST 1903, HIST 2003, HIST 2013, POLS 2003.
- Social Sciences: HIST 1503, HIST 1513, HIST 1903, HIST 2003, HIST 2013, POLS 2003, ECON 2003, ECON 2013, SOC 1003, PSY 2003, ANTH 1213, ANTH 2003, GEOG 2013, AMST 2003, FIN 2013, LEAD 1003.
- Science with Lab: BIOL 1014, BIOL/PHSC 1004, GEOL 1014.

ACTS equivalents shown on the map: ENGL 1013 = ACTS ENGL 1013; ENGL 1023 = ACTS ENGL 1023; MATH 2914 = ACTS MATH 2405; MATH 2924 = ACTS MATH 2505; ENGL 2053 = ACTS ENGL 2023. Several gen-ed options also list ACTS codes.

## Appendix B: ATU CLEP equivalencies (catalog 2026–27; re-scrape and diff)
| Exam | Min score | ATU credit |
|---|---|---|
| American Government | 50 | POLS 2003 |
| American Literature | 50 | ENGL 2013 |
| Biology | 50 | BIOL 1014 or BIOL 1114 |
| Calculus | 50 | MATH 2914 |
| Chemistry | 50 / 55 | CHEM 2124 / CHEM 2124 & 2134 |
| College Algebra | 50 | MATH 1113 |
| College Mathematics | 50 | MATH 1003 |
| College Composition | 50 / 59 | ENGL 1013 / ENGL 1013 & 1023 |
| College Composition Modular | 50 / 59 | ENGL 1013 / ENGL 1013 & 1023 |
| English Literature | 50 / 55 | ENGL 3413 / ENGL 3413 & 3423 |
| French Language | 42 / 50 | FR 1013 / FR 1013 & 1023 |
| German Language | 43 / 55 | GER 1013 / GER 1013 & 1023 |
| History of the United States I | 50 | HIST 2003 |
| History of the United States II | 50 | HIST 2013 |
| Human Growth & Development | 50 | PSY 3813 |
| Humanities | 50 | HUM 2003 |
| Information Systems & Computer Applications | 52 | COMS 1003 |
| Natural Sciences | 56 | BIOL 1014, PHSC 1013 & PHSC 1021 |
| Precalculus | 50 | MATH 1914 |
| Principles of Macroeconomics | 50 | ECON 2003 |
| Psychology, Introductory | 50 | PSY 2003 |
| Social Sciences & History | 50 / 56 | HIST 1503 / HIST 1503 & 1513 |
| Sociology, Introductory | 50 | SOC 1003 |
| Spanish Language | 45 / 55 | SPAN 1013 / SPAN 1013 & 1023 |

## Appendix C: Sources
- Degree map example: https://www.atu.edu/advising/degreemaps_docs/2025-26/ComputerScience.pdf
- Catalog home: https://catalog.atu.edu/
- Regulations & procedures: https://catalog.atu.edu/undergraduate/regulations-procedures/
- Graduation requirements: https://catalog.atu.edu/undergraduate/graduation-requirements/
- Institutional credit: https://catalog.atu.edu/undergraduate/institutional-credit/ (the CLEP subpage is /clep/; discover the AP and IB subpages)
- Academic calendar 2026–27: https://www.atu.edu/academicaffairs/docs/2026-27%20UpdateCalendar.pdf
- Registration and summer sessions: https://www.atu.edu/registrar/registrationinfo.php
- ACTS (Arkansas Course Transfer System): https://adhe.edu/
