"""A9: the pipeline report lists every discovered program with its tier; none silently dropped."""

from __future__ import annotations

import json
import re

from pipeline.common import Fetcher
from pipeline.discover import discover
from tests.synthetic import REPO

REPORT = REPO / "data" / "REPORT.md"
TIERS = {
    "Cross-checked",
    "Auto-imported",
    "Needs review",
    "Excluded (not bachelor's)",
    "Not ingested",
}


def report_rows() -> list[list[str]]:
    rows = []
    in_table = False
    for line in REPORT.read_text(encoding="utf-8").splitlines():
        if line.startswith("| Program | Year | Degree | College | Tier | Issues |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if line.startswith("|---"):
                continue
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            rows.append(cells)
    return rows


def test_a9_report_lists_every_discovered_program_with_a_tier() -> None:
    fetcher = Fetcher(online=False)
    _, refs = discover(fetcher)
    rows = report_rows()
    assert len(rows) == len(refs)
    urls = {re.search(r"\((https?://[^)]+)\)", r[0]).group(1) for r in rows}  # type: ignore[union-attr]
    assert {ref.url for ref in refs} <= urls
    for row in rows:
        assert row[4] in TIERS, row


def test_a9_every_processed_program_is_in_the_report_and_meta() -> None:
    meta = json.loads((REPO / "data" / "processed" / "meta.json").read_text())
    rows = report_rows()
    assert meta["discovered_maps"] == len(rows)
    ingested = [r for r in rows if r[4] in ("Cross-checked", "Auto-imported", "Needs review")]
    programs = list((REPO / "data" / "processed" / "programs").glob("*.json"))
    assert len(programs) == len(ingested) == meta["bachelor_programs"]
    counted = sum(v for k, v in meta["tier_counts"].items())
    assert counted == len(rows)
