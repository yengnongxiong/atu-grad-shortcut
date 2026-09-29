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
