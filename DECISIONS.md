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
