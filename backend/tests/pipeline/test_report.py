"""data/REPORT.md sections (PRD A9; PRD v1.1 risk table: stale catalog snapshots are flagged)."""

from __future__ import annotations

from pipeline.report import snapshot_lines


def snap(title: str, edition: str) -> dict[str, str]:
    url = f"https://catalog.atu.edu/{title}"
    return {"title": title, "url": url, "catalog_edition": edition, "captured_at": "2026-09-29"}


def test_snapshots_older_than_the_newest_catalog_year_are_flagged() -> None:
    text = "\n".join(snapshot_lines([snap("AP", "2025-2026"), snap("IB", "2026-2027")], "2026-27"))
    assert "## Catalog snapshots" in text
    stale = "| 2025-2026 | 2026-09-29 | Older than the newest catalog year (2026-27) |"
    assert f"| [AP](https://catalog.atu.edu/AP) {stale}" in text
    assert "| [IB](https://catalog.atu.edu/IB) | 2026-2027 | 2026-09-29 | Current |" in text
