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
