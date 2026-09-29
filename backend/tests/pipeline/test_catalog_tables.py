"""AP, IB, and CLEP credit tables parsed from the ATU catalog snapshots (PRD v1.1 §3.1)."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from pipeline.catalog_tables import parse_exam_table

RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "catalog"


@cache
def rows(program: str) -> list[dict[str, Any]]:
    snapshot = json.loads((RAW / f"{program.lower()}.json").read_text())
    return parse_exam_table(snapshot, program)


def row(program: str, exam: str, score: int) -> dict[str, Any]:
    return next(r for r in rows(program) if r["exam"] == exam and r["min_score"] == score)


def test_every_table_row_becomes_one_equivalency() -> None:
    assert (len(rows("AP")), len(rows("CLEP")), len(rows("IB"))) == (55, 43, 82)


def test_ampersand_lists_award_every_course() -> None:
    assert row("AP", "Calculus BC", 3)["awards"] == [["MATH 2914", "MATH 2924"]]
    assert row("AP", "Computer Science A", 4)["awards"] == [["COMS 1013", "COMS 1011", "COMS 2203"]]


def test_or_separates_alternatives() -> None:
    assert row("AP", "Environmental Science", 3)["awards"] == [["BIOL 1004"], ["ENVS 1004"]]
    assert row("AP", "Chemistry", 3)["awards"] == [
        ["CHEM 1113", "CHEM 1111", "CHEM 2204"],
        ["CHEM 2124", "CHEM 2134"],
    ]


def test_generic_credit_is_never_mapped_to_a_course() -> None:
    aas = row("AP", "African American Studies", 3)
    assert aas["awards"] == []
    assert aas["generic_credit"] == "3 hours General Education Humanities"


def test_mixed_course_and_generic_credit_keeps_both() -> None:
    latin = row("IB", "Latin: Language B/Standard or Higher", 4)
    assert latin["awards"] == [["LAT 1013", "LAT 1023"]]
    assert latin["generic_credit"] == "6 hours General Education Humanities"


def test_hours_from_a_list_become_every_qualifying_combination() -> None:
    english = row("IB", "English/Higher", 4)
    assert len(english["awards"]) == 6  # any two of four 3-hour courses
    assert ["ENGL 1013", "ENGL 1023"] in english["awards"]
    assert all(len(option) == 2 for option in english["awards"])


def test_same_exam_higher_score_is_its_own_row() -> None:
    bio = [r for r in rows("AP") if r["exam"] == "Biology"]
    assert {(r["min_score"], tuple(r["awards"][0])) for r in bio} == {
        (3, ("BIOL 1014",)),
        (4, ("BIOL 1114",)),
    }


def test_clep_ids_match_the_appendix_ids_already_in_use() -> None:
    appendix = json.loads((RAW.parents[1] / "manual" / "clep_appendix_b.json").read_text())
    ids = {r["id"] for r in rows("CLEP")}
    assert {r["id"] for r in appendix["equivalencies"]} <= ids


def test_rows_cite_the_catalog_page() -> None:
    assert row("IB", "Psychology/Standard or Higher", 4)["source"]["url"].endswith(
        "/institutional-credit/ib/"
    )


def test_ids_are_unique_within_each_table() -> None:
    for program in ("AP", "CLEP", "IB"):
        ids = [r["id"] for r in rows(program)]
        assert len(ids) == len(set(ids)), program
