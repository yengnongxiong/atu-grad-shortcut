# Data

Everything Shortcut knows about ATU, with a source for each fact. `raw/` holds the committed sources: degree-map PDFs, Banner course and schedule snapshots, and catalog pages saved from a browser. `processed/` is what the pipeline builds from them and what the app loads; `manual/` holds hand-maintained inputs such as policies; `personas/` holds the four demo profiles. Personal records (`personas/my-*.json`) are git-ignored.

Read first:
- [REPORT.md](REPORT.md): coverage and trust tier for every program
- [manual/policies.json](manual/policies.json): every policy number with its source and confidence
- [processed/programs/computer-science-2025-26.json](processed/programs/computer-science-2025-26.json): one program as the planner sees it
