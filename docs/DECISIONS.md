# Decisions log

Every judgment call made while building Shortcut autonomously. Format: date · decision · alternatives · reason.

## 2026-09-29

### D1 · Commits authored as the owner
- **Decision:** Repo-local git identity is `Yengnong Xiong <207461518+yengnongxiong@users.noreply.github.com>` (the owner's GitHub noreply address).
- **Alternatives:** Personal email; default agent identity.
- **Reason:** The owner asked for contribution credit. GitHub always links the noreply address to the account, so commits count regardless of which emails are verified, and it can't trip "block pushes that expose my email".

### D2 · Python 3.12 via uv; frontend on Vite 8 / React 19 / TS 6 / Tailwind v4
- **Decision:** Pin Python 3.12 (`backend/.python-version`). Scaffold the frontend with `create-vite` (react-ts), then swap its default oxlint for ESLint + typescript-eslint (strict) to match CLAUDE.md's `make lint`.
- **Alternatives:** System Python 3.11; keep oxlint.
- **Reason:** PRD §11 specifies Python 3.12 and CLAUDE.md specifies eslint.

### D3 · Newest catalog year is 2026–27, and CS splits into two maps
- **Decision:** Treat 2026–27 as the newest catalog year. Its index lists `ComputerScienceAI.pdf` and `ComputerScienceSoftwareDev.pdf` instead of the single 2025–26 `ComputerScience.pdf`. The 2025–26 CS map stays the primary CS program (PRD §7.1: ground truth, owner's catalog year). Differences to the 2026–27 tracks are recorded in data/REPORT.md, not forced to match.
- **Alternatives:** Treat 2026–27 Software Development as "the" CS program.
- **Reason:** PRD §7.1 and Appendix A pin 2025–26 CS as ground truth.

### D4 · Q4 (degree audit in OneTech) partially answered
- **Decision:** Record that ATU's advising page links a video titled "How to use Degree Works", so a Degree Works audit tool exists. Update the competitive landscape wording in the README, not the PRD.
- **Alternatives:** Leave Q4 fully open.
- **Reason:** Public evidence exists; PRD is the owner's document, so it stays untouched.

### D5 · catalog.atu.edu is unreachable here; use ATU's public Banner catalog + schedule instead
- **Finding:** `catalog.atu.edu` answers every request with an AWS WAF JavaScript challenge (HTTP 202, empty body). The challenge script is served from `*.token.awswaf.com`, which this environment's egress policy blocks (403 at the proxy), so neither curl, headless Chromium, nor WebFetch can get past it.
- **Decision:** Use ATU's public, login-free Banner 9 self-service at `https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb/` as the catalog source. Its "Browse Course Catalog" returns the catalog's own course entries: title, hours, college/department, full description including "Offered:" and "Prerequisite:" text and ACTS common-course numbers, plus structured And/Or prerequisite tables with minimum grades and test-score alternatives, and corequisites. Its "Browse Classes" gives the real sections offered in each Fall/Winter/Spring/Summer term, which PRD §7.1 lists as the optional source for confirming summer/winter offerings.
- **Fallback retained:** The pipeline still tries catalog.atu.edu first in online mode. If the WAF blocks it, the pipeline logs that and uses Banner. If Banner is also unreachable, CS falls back to PRD Appendix A with source "PRD appendix (transcribed)". CLEP always comes from Appendix B, because the CLEP page is catalog-only. Appendix B is dated 2026–27, so it's current.
- **Alternatives:** Appendix A/B only (loses prerequisites the map doesn't state, which PRD says "must come from the catalog"); spoofing crawler user agents to dodge the WAF (rejected: circumventing access control).
- **Reason:** Banner is ATU's own system of record for course prerequisites and offerings, it's public, and it's on the allowlisted `*.atu.edu` domain.

### D6 · AP and IB tables are unavailable in v1
- **Decision:** Ship CLEP equivalencies (Appendix B) only. AP and IB course tables live solely on catalog.atu.edu subpages (`/institutional-credit/ap/`, `/ib/`, linked from www.atu.edu/admissions/credit.php), which are blocked here. The IB Diploma rule (24 hrs of gen-ed for a score ≥4 on each exam) is documented on www.atu.edu/admissions/credit.php and is recorded as a policy but not auto-mapped to courses. The exam-opportunity UI says AP/IB mappings are pending, rather than guessing.
- **Alternatives:** Transcribe AP tables from memory or third-party sites (rejected: "never invent academic data").
- **Reason:** CLAUDE.md data rules.

### D7 · Q3 answered: a public class schedule exists
- **Decision:** Record that ATU's registrar links a public "Searchable Schedule" (Banner, view-only, no login) with term codes back to 2022, including Winter Intersession terms. The pipeline uses it for historical offering evidence.

### D8 · Offering confidence uses catalog "Offered:" text, map notes, and three years of schedule history
- **Decision:** Per season, a course's offering entry is `{available, confidence, source, note}`:
  - **Fall/Spring.** The catalog's "Offered:" line (Banner description) or a map's "Fall Only"/"Spring Only" note makes a season *documented*. If the two disagree, the stricter intersection applies with confidence *conflicting*. Example: the CS map says COMS 4913 is Fall Only, but the catalog says Fall, Spring, so it's scheduled Fall-only (PRD A3 expects this).
  - **Fall/Spring, no documented restriction.** Both seasons default to available and *assumed* (PRD §7.4). Two refinements from the public schedule (Fall 2023–Spring 2027): a season in which the course actually ran becomes *derived*. If the course ran at least twice in the window but never in that season, the season becomes *unknown*, so Conservative mode won't rely on it.
  - **Summer/Winter.** Catalog "Offered:" wins (*documented*). Otherwise, having run in that season at least once in the window makes it *derived*. With no history for the course at all, PRD §7.4 applies: 1000–2000-level gen-ed courses are *assumed* ("likely"), everything else *unknown*. If the course ran in the window but never in that season, the season is *unknown* even for gen-eds.
- **Conservative mode** schedules only documented/derived/assumed/conflicting-available seasons; **Optimistic** also allows unknown and flags each use.
- **Alternatives:** Pure PRD §7.4 defaults (fall/spring always assumed), which produces plans that put spring-only courses in fall.
- **Reason:** PRD §7.1 names the public schedule as the source to confirm summer/winter offerings, and the product promise is a *realistic* path. Every inference keeps its evidence (term codes) in `note`, so it's visible and reversible.

### D9 · Placement tests
- **Decision:** Banner prerequisite trees include placement tests (ACT English, SAT, COMPASS, Accuplacer, ACT Math). Shortcut collects only the math ACT (PRD F2), so:
  - A math-ACT node is evaluated against the student's score. Per PRD §8, Calculus I uses the stricter 27 from the CS map; Banner says 26.
  - If a math ACT is entered, other math tests count as not taken, so the planner adds the course alternative (e.g. MATH 1914 before Calculus I).
  - If no math ACT is entered, and for every non-math placement test, placement is **assumed** and listed in the plan's assumptions.
- **Alternatives:** Treat unknown tests as failed. That would add developmental English to every plan, which is wrong for most students.
- **Reason:** The only placement input the PRD asks for is the math ACT subscore; everything else must be visible as an assumption rather than silently guessed.

### D10 · Upper-level elective placeholders wait for junior standing; ties follow the degree map
- **Decision:**
  - Generic "3000–4000 level elective" slots have no specific course and therefore no prerequisites. The planner places them only after 60 earned hours (junior standing), because most upper-division courses require that or upper-level prerequisites.
  - Among equally fast plans, a small tie-break weight keeps each course near its degree-map semester, so plans read like the map a student and advisor already know.
- **Alternatives:** No standing on placeholders, which put upper-level electives in freshman fall. A purely "earliest-first" tie-break, which scattered gen-eds.
- **Reason:** Realism. Neither rule changes the graduation term the planner optimizes first; the second only breaks ties.

### D11 · Prerequisites that name retired courses are ignored (and recorded)
- **Finding:** Banner's prerequisite tables still cite course numbers the current catalog no longer has. Example: NUR 3606 requires NUR 3204 and NUR 4206 requires NUR 3802, while the 2026–27 Nursing map lists NUR 3206 and NUR 3801. Taken literally, those requirements are impossible, and the Nursing plan was infeasible.
- **Decision:** The pipeline drops prerequisite leaves whose course isn't in the current Banner catalog. It stores them in the course's `pruned_prerequisites` with a warning and lowers `parse_confidence` to medium, which surfaces in plan warnings. OR-alternatives that are retired (e.g. "COMS 1013 or COMS 2104") drop silently, since another option remains.
- **Alternatives:** Keep them, which makes several programs impossible to plan. Or guess the renumbered successor, which would be inventing data.
- **Reason:** A student can't take a retired course, and the replacement course is already required by the map. The removal is visible, not silent.

### D12 · Corequisites are groups of alternatives; "completion of all … courses" is scoped to the student's program
- **Findings from the all-majors sweep (M6).** Planning every bachelor's map at standard pace turned up two data shapes the planner read too literally:
  - *"Co-requisite: SEED 4809 or SEED 4909."* A flat corequisite list made both 9-hour residencies required in the same term, so 9 education programs had no feasible plan. The same thing happens with "PHYS 2014 or PHYS 2114" for the PHYS 2000 lab.
  - *HES 4012: "level 3 requires completion of all HES, PE, and HLED content area courses".* Banner's structured table for it lists the union of every HES concentration, which added a dozen courses from other concentrations to each HES plan.
- **Decision:**
  - A course's `corequisites` is a list of groups, and each group needs one member. "A or B" becomes `[[A, B]]`; "NUR 3204 and 3402" becomes `[[NUR 3204], [NUR 3402]]`. A clause with no course code ("or consent of the department head") adds nothing.
  - A course whose prerequisite text says "completion of all …" gets `prerequisite_scope: "program"`. The planner then treats prerequisite leaves outside the student's own program (and credits) as met, and adds a note to the course.
- **Alternatives:** Keep the literal reading, which is infeasible or over-long for 12 programs. Or drop these prerequisites entirely, which would lose real ordering within the program.
- **Reason:** Both readings follow the source text word for word ("or"; "all … content area courses" of the student's program). Each is visible on the course.

### D13 · A required course offered only in summer gets a summer term even with the summer lever off
- **Finding:** GEOL 4006 Field Geology (6 hrs) is "Offered: SU" in the catalog. With summers off, Geosciences was infeasible at standard pace.
- **Decision:** With the summer lever off, a summer slot is still open to an item whose only allowed season (under the current mode) is summer. It stays closed to everything else. The plan carries an info warning ("GEOL 4006 is offered only in summer, so the plan includes Summer 2029 even with summer terms off").
- **Alternatives:** Report the program infeasible unless the student turns summer on, which would make "summer" look like a shortcut when it's actually a degree requirement.
- **Reason:** The degree map itself schedules field camp in a summer; standard pace should match it.

### D14 · Choosing among map alternatives; offering conflicts with no overlap
- **Decision:**
  - When a map row offers alternatives ("PHYS 2014 or PHYS 2114") and nothing is credited yet, the planner prefers the option another required course needs on every prerequisite path (CHEM 3324 needs PHYS 2114). Otherwise it follows the map's order, and it skips an option an earlier row already chose ("COMS 2213 or COMS 2323" listed in two semesters means one of each).
  - A 0-credit lab in a slash list ("PHYS 2014/2114/2000") isn't an alternative to the lecture. It's scheduled through the corequisite rule instead.
  - A row "PHYS 4003 or Elective (3000-4000 level)" that the map repeats in a later semester becomes that elective the second time.
  - If the catalog's "Offered:" line and a map's "… Only" note share no regular term (FW 3053: catalog Fall, map Spring only), the D8 stricter-intersection rule would leave no term. The class schedule decides instead (FW 3053 ran four falls and no springs), still labeled *conflicting*. With no schedule record, either term is allowed.
- **Reason:** Each rule removes a duplicate or impossible schedule found in the sweep without adding data. The evidence stays in warnings and notes.

### D15 · Which programs were cross-checked
- **Decision:** Five programs are cross-checked: Computer Science 2025–26, Accounting, History, Nursing (BSN), and Mathematics. Banner assigns every course to one of four colleges (Arts and Humanities; Business and Economic Development; Education and Health; Science, Technology, Engineering and Mathematics), so the five cover all four colleges. CS and Mathematics are both in STEM, and Mathematics was added because its map repeats "X or Y" rows.
- **How:** The rendered degree-map page was compared row by row with the parsed program (codes, titles, hours, C marks, offering notes, totals), along with the Banner entries for the major courses. The catalog program page is unreachable (D5), so it wasn't compared, and each record says so. Records and findings are in `data/manual/cross_checks.json` and the "Cross-checks" section of `data/REPORT.md`.
- **Reason:** PRD M6 asks for CS plus 4 majors from different colleges. The review was done by the build agent, not an ATU advisor, and the records state that.

### D16 · A course retaken for a grade counts once toward the degree
- **Finding (M8 review):** A D in ENGL 1013, where the map requires a C, correctly scheduled a retake. But the D attempt's 3 hours still counted toward the 120-hour total, so the same course counted twice (123 hours).
- **Decision:** When the plan retakes a passed course to reach a required grade, the earlier attempt is marked `retaken`. Its hours stop counting toward total, ATU, exam, and upper-level hours, and the credited list shows "replaced by the planned retake". It still satisfies D-level prerequisites, and it still counts for class standing until it's replaced.
  - A repeatable course the map lists more than once (e.g. MUS 1501 applied lessons) keeps its credit, because that attempt fills its own requirement slot.
  - The plan carries a warning to confirm the repeat policy with the registrar.
- **Alternatives:** Count both attempts, which overstates progress. Or drop the D entirely, which would wrongly block D-level prerequisites and standing.
- **Reason:** The pipeline has no ATU repeat-policy source. Counting a course once is the conservative reading: it never makes a plan look shorter than it is, and the warning makes the assumption visible.

### D17 · The upper-level minimum is met with the map's own open slots first
- **Finding (M8 review):** Psychology planned 147 hours instead of 120. The map's open slots (General Electives, "Minor or 2nd Major", PSY Topical Core) have no level rule, so the planner didn't count them toward the 40 upper-division hours and added 27 hours of new upper-level fillers.
- **Decision:** Before adding hours, the planner designates open slots with no maximum level as "3000-4000 level", latest map semesters first, since those fall after junior standing anyway. They're labeled that way in the plan. New filler hours are added only if a deficit remains. This matches the validator's `upper_level_achievable` check, which already counted such slots as flexible.
- **Reason:** A student meets the upper-division minimum by choosing upper-level courses for their electives, not by taking extra hours. Psychology now plans 120 hours and matches its map.

### D18 · No graduation in a winter intersession
- **Source:** The ATU 2026–27 academic calendar lists December, May, and summer graduates. Winter Intersession runs Dec 14 – Jan 1, after the December ceremony.
- **Decision:** A plan whose last course falls in winter graduates the following spring (`model.conferral_index`). The solver then keeps the final course in spring unless winter frees an earlier term.
- **Reason:** Showing "Winter 2028–29" as a graduation date would promise a conferral that doesn't exist.

### D19 · Map-note prerequisites and corequisites describe the lecture, not a 0-credit lab in the same cell
- **Finding:** "PHYS 2114/2000 … Co-req: MATH 2914" attached MATH 2914 as a corequisite of the PHYS 2000 lab. Via "PHYS 2014 or PHYS 2114", that added 8 hours of calculus to Biology plans that take algebra-based physics.
- **Decision:** In a map cell that lists a credit-bearing course with a 0-credit lab (ATU course numbers end in the credit hours), the lab keeps the note's offering and pass/fail facts but not its prerequisite or corequisite text. The lab's own catalog entry supplies its corequisites.

### D20 · Summer blocks on a degree map
- **Finding:** Health Information Management ends with a "Summer after Senior year" block (HIM 4892 Seminar, HIM 4895 Affiliation, 7 hrs) laid out like a semester. The parser only read "Semester N" blocks, so the program totaled 113 hours and dropped its capstone.
- **Decision:**
  - A "Summer … Hrs." header is parsed as a summer block and numbered after the regular semesters, with `season: "SU"` and its label kept.
  - The degree-map baseline then ends in that summer.
  - A block label such as "after Senior year" becomes a standing hint (SR) on its courses. Banner lists no prerequisites for them, and without the hint the map-order tie-break put the Affiliation in freshman summer.
- **Reason:** The map says when these courses happen. Senior standing is the least a reader can take from "after Senior year", and the hint is kept only as standing, not as a fixed term.

### D21 · "All required HIM courses except HIM 4892", and repeatable alternatives
- **Findings (M8 HTTP sweep):**
  - After fetching HIM 4895's catalog entry, its prerequisite "completion of all required HIM courses except HIM 4892" was read as "requires HIM 4892". That contradicted the HIM 4892 ↔ 4895 corequisite and made the program infeasible.
  - The music maps list "MUS 1501 Band or MUS 1681 Concert Chorale" in four semesters. D14's "one of each" rule had a band student switch to choir for a semester.
- **Decision:**
  - Codes after "except" in prerequisite text are exclusions, not requirements.
  - For a program-scoped prerequisite of the form "all required SUBJ courses [except …]" (D12), the planner requires every planned SUBJ course of the student's program, minus the exclusions. The HIM Affiliation therefore follows the last HIM course, in the summer the map shows.
  - An identical "X or Y" row repeated more times than it has options names repeatable courses, so the same choice is kept each time. D14's one-of-each rule still applies when the repeats don't exceed the options (COMS 2213 or COMS 2323, twice).
- **Guard:** `tests/acceptance/test_all_programs.py` plans every program at standard pace. It checks feasibility, the total-hours minimum, no winter graduation, and that no course is planned more times than the map lists it.

## 2026-09-29 (v1.1)

### D22 · Degree-map courses are charged for landing behind their map semester
- **Finding (v1.1 QA):** The map-order tie-break (D10) only rewarded placing courses early. With every term packed to the preferred 16 hours, the polish pass used 1-hour TECH 1001 (Orientation) as filler and put a freshman's orientation in their third term. With every lever on, it also moved Calculus I, the head of the CS critical chain, out of the first term to avoid a 17-hour first term.
- **Decision:** A second tie-break charges each course, per regular semester it lands after its degree-map semester, `W_MAP_LATE × order_weight` (semester 1 courses weigh 9, semester 8 courses 2). Courses planned ahead of the map cost nothing, so students with credit still accelerate. `W_MAP_LATE = 50` makes a foundational course one semester late (450) cost more than one hour above the preferred load (400), while later-map courses still defer to the student's preference. Graduation dates are unchanged: the tie-break runs only after the earliest graduation term is fixed.
- **Alternatives:** A larger weight on the existing "earliest-first" term (still front-loads by hours and fights map order); pinning specific courses to the first term (special cases, not a rule).
- **Reason:** A plan an advisor reads should look like the map they know unless there's a reason to differ. Measured: all 74 programs still plan, and the CS plan with every lever solves in ~0.3 s.

### D23 · Catalog snapshots replace the unreachable catalog (supersedes D6)
- **Finding:** catalog.atu.edu still answers automated tools with an AWS WAF challenge (D5), but it loads normally in a regular browser.
- **Decision:** The owner's browser opened each needed page once, and its tables and policy paragraphs were saved verbatim as JSON under `data/raw/catalog/`: AP (55 rows), CLEP (43), IB (82), and the credit, graduation, and load policy text. Each table's rows were checked against the live page by SHA-256. The pipeline parses these snapshots offline (`pipeline/catalog_tables.py`), and automated code never works around the challenge.
  - Credit text maps to exact course codes only. "A & B" awards both, "A or B" is a choice, "6 hours from the following courses: …" becomes every combination worth 6 hours, and generic credit ("3 hours General Education Humanities") is kept as text and never mapped to a course.
  - CLEP now comes from the catalog, not PRD Appendix B. The catalog adds 11 exams the appendix lacked (e.g. Principles of Microeconomics, Western Civilization I/II) and changes none; the diff is stored in `exams/clep.json`.
  - An exam is identified by program and name together, because AP and CLEP share names ("French Language").
  - AP and IB exams are offered as opportunities only before a student starts at ATU, since they're taken in high school.
- **Alternatives:** Keep AP/IB unavailable (the owner's own record has AP credit); transcribe from third-party sites (not a source).

### D24 · The exam-credit cap conflict, restated
- **Finding:** Both 2026–27 catalog pages (institutional credit and graduation requirements) now say up to 50% of a degree may come from correspondence, extension, military, exam, or prior-learning credit. ATU's admissions credit page (www.atu.edu/admissions/credit.php, checked live 2026-09-29) still says no more than 30 semester hours. The v1 note said the graduation-requirements page was on the 30-hour side; it no longer is.
- **Decision:** Keep the stricter 30 hours, labeled *conflicting*, with the note corrected. A plan should never look shorter than it is. The owner's own record uses 23 of those hours.
- **Alternatives:** 50% (the catalog governs graduation requirements, but the admissions page is also current and official).

### D25 · Degree Works import runs in the browser and compares, never overrides
- **Decision:**
  - A student's Degree Works audit (saved as PDF) is read with pdf.js in the browser. No file is uploaded, and the parser never reads the name or student ID into anything it returns. The parsed audit (codes, grades, terms, still-needed lines) lives in this tab's sessionStorage only, so the plan page can compare against it.
  - The parser keys off stable tokens (course codes, the grade column, "Satisfied by:", "Still needed:") rather than positions. It handles wrapped term and title cells, page headers between a row and its exam line, "Choose from N of the following" blocks, and subject carry-forward in "PHSC 1013 or 1053" lists. Rows it can't read are listed, not dropped.
  - `CE` rows become posted exam credit (`source: "exam"`, the audit's own hours), T-grades transfer credit, `IP` rows in progress, and `W` rows are left out. The Not Used section still counts toward hours and standing.
  - The first ATU term is the earliest ATU-graded term, and the plan starts the term after the latest in-progress one.
  - An overall GPA of 3.25+ sets the "expect 3.25+" preference, labeled as an assumption (overloads use the preceding term's GPA).
  - The plan page compares Degree Works' still-needed lines with the plan ("agree on N of M"). Each planned item covers one line; a generic "3000–4000 level" line covers every upper-level elective slot. Differences are shown for the advisor, and Shortcut doesn't pick a winner.
- **Verified:** Locally, against the owner's real audit (never committed): 27 courses, 77 credits applied, and 12 still-needed lines, matching Degree Works exactly. The committed test fixture is synthetic.
- **Alternatives:** Server-side parsing with pdfplumber (would upload a document carrying the student's name and ID); asking students to retype their record (the source of the v1.1 exam-credit bugs).

### D26 · One solver worker, so a request always returns the same schedule
- **Finding:** With 4 parallel CP-SAT workers, every solve still reached OPTIMAL, but the polish objective has ties. Each worker found a different tie-optimal schedule, so the same P1 request (heavier terms, summer, winter) returned 3 different schedules in 3 runs. The date never moved, but a reload, a share link, or the advisor export could show courses in different terms than the student had just seen. PRD §9 asks for a fixed seed so results are reproducible, and a seed alone doesn't make parallel search deterministic.
- **Decision:** Solve with `num_workers = 1` (and the fixed seed). `tests/acceptance/test_determinism.py` solves the same request four times and requires identical schedules. The CS p95 over all 64 lever combinations went from 0.55 s to 2.07 s (target: under 3 s). A sweep of all 145 program maps with four levers on hit the 5 s limit on 41 solves, the same count as with 4 workers. When a solve does hit the limit, the plan page already says "hit the time limit; showing the best plan found."
- **Alternatives:** `interleave_search` with 4 workers (deterministic, but P1 took about 2 s per plan against 0.75 s single-threaded); keeping parallel workers for date-only solves (their placements seed later solves as hints, so they must be deterministic too); a deterministic-time budget instead of wall-clock (machine-dependent wall time, against PRD §9's 5 s limit).
