"""data/REPORT.md: coverage, tiers, issues for every discovered program (PRD A9)."""

from __future__ import annotations

from typing import Any

from pipeline.common import DATA_DIR, MANUAL_DIR, read_json
from pipeline.discover import MapRef
from pipeline.parse_degree_map import ParsedMap

TIER_LABEL = {
    "cross_checked": "Cross-checked",
    "auto_imported": "Auto-imported",
    "needs_review": "Needs review",
    "excluded": "Excluded (not bachelor's)",
    "not_ingested": "Not ingested",
}


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def write_report(
    meta: dict[str, Any],
    rows: list[dict[str, Any]],
    programs: list[dict[str, Any]],
    courses: dict[str, dict[str, Any]],
    parsed: dict[str, tuple[MapRef, ParsedMap]],
) -> None:
    tiers = meta["tier_counts"]
    bachelors = [r for r in rows if r["tier"] in ("cross_checked", "auto_imported", "needs_review")]
    good = [r for r in bachelors if r["tier"] in ("cross_checked", "auto_imported")]
    pct = 100.0 * len(good) / len(bachelors) if bachelors else 0.0
    lines: list[str] = [
        "# Shortcut data pipeline report",
        "",
        f"Generated {meta['generated_at']} · mode `{meta['pipeline_mode']}` · newest catalog year "
        f"**{meta['newest_catalog_year']}** (plus the 2025–26 Computer Science ground truth).",
        "",
        "## Coverage",
        "",
        f"- Degree maps discovered: **{meta['discovered_maps']}**",
        f"- Bachelor's programs ingested: **{len(bachelors)}** "
        f"({tiers.get('excluded', 0)} associate/other maps listed below as excluded, "
        f"{tiers.get('not_ingested', 0)} not ingested)",
        f"- Auto-imported or better: **{len(good)} of {len(bachelors)} ({pct:.0f}%)**",
        f"- Cross-checked: **{tiers.get('cross_checked', 0)}** · Auto-imported: "
        f"**{tiers.get('auto_imported', 0)}** · Needs review: **{tiers.get('needs_review', 0)}**",
        f"- Courses in courses.json: **{meta['course_count']}**",
        f"- catalog.atu.edu: {meta['catalog_status']}",
        f"- Banner (public course catalog + class schedule): {meta['banner_status']}",
        "",
        "## Every discovered program",
        "",
        "| Program | Year | Degree | College | Tier | Issues |",
        "|---|---|---|---|---|---|",
    ]
    order = {
        "cross_checked": 0,
        "auto_imported": 1,
        "needs_review": 2,
        "excluded": 3,
        "not_ingested": 4,
    }
    for row in sorted(rows, key=lambda r: (order.get(r["tier"], 9), r["title"])):
        issues = "; ".join(row["issues"]) or row["note"] or "—"
        lines.append(
            f"| [{_cell(row['title'])}]({row['url']}) | {row['catalog_year']} | {_cell(row['degree'])} | "
            f"{_cell(row['college'])} | {TIER_LABEL.get(row['tier'], row['tier'])} | {_cell(issues)} |"
        )
    lines += ["", "## Cross-checks", ""]
    cross = read_json(MANUAL_DIR / "cross_checks.json")
    if not cross["programs"]:
        lines.append("None recorded yet.")
    for program_id, record in cross["programs"].items():
        lines += [
            f"### {record.get('title', program_id)} (`{program_id}`)",
            "",
            f"- Result: **{record['result']}** · reviewed {record['date']} by {record['reviewer']}",
            f"- Compared: {'; '.join(record['compared'])}",
        ]
        for finding in record.get("findings", []):
            lines.append(f"- Finding: {finding}")
        lines.append("")
    lines += _cs_diff_section(programs)
    lines += [
        "",
        "## Warnings on ingested programs (non-blocking)",
        "",
    ]
    for row in sorted(bachelors, key=lambda r: r["title"]):
        if row["warnings"]:
            lines.append(f"- **{row['title']}**: " + "; ".join(_cell(w) for w in row["warnings"]))
    lines += [
        "",
        "## Data caveats",
        "",
        "- catalog.atu.edu is WAF-gated from the build environment, so course data comes from ATU's "
        "public Banner course catalog and class schedule (DECISIONS.md D5).",
        "- AP and IB course tables are not available (catalog-only); CLEP comes from PRD Appendix B (D6).",
        "- Summer/winter availability is inferred from three years of public schedules (D8); a course "
        "that ran before may not run again.",
        "- Rows the parser couldn't classify keep the program selectable but mark it Needs review.",
    ]
    (DATA_DIR / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _cs_diff_section(programs: list[dict[str, Any]]) -> list[str]:
    by_id = {p["id"]: p for p in programs}
    base = by_id.get("computer-science-2025-26")
    if not base:
        return []
    base_codes = _required_codes(base)
    lines = ["", "## 2026–27 Computer Science maps vs. Appendix A (2025–26)", ""]
    for other_id in ("computer-science-software-dev-2026-27", "computer-science-ai-2026-27"):
        other = by_id.get(other_id)
        if not other:
            continue
        codes = _required_codes(other)
        added = sorted(codes - base_codes)
        removed = sorted(base_codes - codes)
        lines.append(
            f"- **{other['name']}**: adds {', '.join(added) or 'nothing'}; drops "
            f"{', '.join(removed) or 'nothing'} (recorded, not forced to match; PRD §7.1)."
        )
    return lines


def _required_codes(program: dict[str, Any]) -> set[str]:
    return {c for r in program["requirements"] if r["kind"] == "course" for c in r["options"][0]}
