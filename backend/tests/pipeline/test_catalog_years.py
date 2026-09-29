"""A major's maps across catalog years (PRD v1.1 §3.2)."""

from __future__ import annotations

from typing import Any

from pipeline.catalog_years import link_catalog_years


def p(program_id: str, year: str) -> dict[str, Any]:
    return {"id": program_id, "catalog_year": year}


def test_same_map_name_in_a_newer_year_is_the_successor() -> None:
    programs = [
        p("accounting-2025-26", "2025-26"),
        p("accounting-2026-27", "2026-27"),
        p("history-2026-27", "2026-27"),
    ]
    link_catalog_years(programs, {})
    by_id = {x["id"]: x for x in programs}
    assert by_id["accounting-2025-26"]["major_key"] == "accounting"
    assert by_id["accounting-2025-26"]["successors"] == ["accounting-2026-27"]
    assert by_id["accounting-2026-27"]["successors"] == []


def test_a_renamed_or_split_major_uses_the_manual_table() -> None:
    programs = [
        p("computer-science-2025-26", "2025-26"),
        p("computer-science-ai-2026-27", "2026-27"),
        p("computer-science-software-dev-2026-27", "2026-27"),
    ]
    manual = {
        "computer-science-2025-26": ["computer-science-ai-2026-27", "computer-science-software-dev-2026-27"]
    }
    link_catalog_years(programs, manual)
    assert programs[0]["successors"] == [
        "computer-science-ai-2026-27",
        "computer-science-software-dev-2026-27",
    ]


def test_manual_entries_for_programs_that_were_not_ingested_are_ignored() -> None:
    programs = [p("computer-science-2025-26", "2025-26")]
    link_catalog_years(programs, {"computer-science-2025-26": ["computer-science-ai-2026-27"]})
    assert programs[0]["successors"] == []


def test_a_renamed_map_file_with_the_same_title_and_degree_is_the_same_major() -> None:
    old = {**p("emergency-mgmt-2025-26", "2025-26"), "listed_title": "Emergency Management", "degree": "BS"}
    new = {
        **p("emergency-management-2026-27", "2026-27"),
        "listed_title": "Emergency Management",
        "degree": "BS",
    }
    other = {**p("history-2026-27", "2026-27"), "listed_title": "History", "degree": "BA"}
    programs = [old, new, other]
    link_catalog_years(programs, {})
    assert old["successors"] == ["emergency-management-2026-27"]
    assert old["major_key"] == new["major_key"]


def test_two_majors_in_the_same_year_are_never_merged_by_title() -> None:
    a = {**p("music-ed-a-2026-27", "2026-27"), "listed_title": "Music Education", "degree": "BM"}
    b = {**p("music-ed-b-2026-27", "2026-27"), "listed_title": "Music Education", "degree": "BM"}
    link_catalog_years([a, b], {})
    assert a["major_key"] != b["major_key"]
