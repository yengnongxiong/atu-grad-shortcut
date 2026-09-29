"""Prerequisite parsing (Banner tables + free text) and course-code extraction."""

from __future__ import annotations

from typing import Any

from pipeline.codes import extract_codes
from pipeline.enrich_catalog import _regular_season, _short_season
from pipeline.prereqs import (
    parse_banner_coreq_html,
    parse_banner_prereq_html,
    parse_coreq_groups,
    parse_description,
    parse_prereq_text,
)
from pipeline.validate import _no_cycles

SUBJECTS = {"Mathematics": "MATH", "Computer/Information Science": "COMS"}
LADDER = ["MATH 1113", "MATH 1203", "MATH 1914", "MATH 2223", "MATH 2243", "MATH 2914", "MATH 2924"]


def row(connector: str, lp: str, test: str, score: str, subj: str, num: str, grade: str, rp: str) -> str:
    cells = [connector, lp, test, score, subj, num, "Undergraduate" if subj else "", grade, rp]
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def test_banner_table_with_parentheses_and_test() -> None:
    html = (
        "<table><tbody>"
        + row("", "(", "ACT Math", "26", "", "", "", ")")
        + row("Or", "(", "", "", "Mathematics", "1914", "C", "")
        + row("Or", "", "", "", "Mathematics", "1203", "C", ")")
        + "</tbody></table>"
    )
    result = parse_banner_prereq_html(html, SUBJECTS)
    assert result.confidence == "high"
    assert result.tree == {
        "type": "or",
        "items": [
            {"type": "test", "test": "ACT Math", "min_score": 26.0},
            {"type": "course", "code": "MATH 1914", "min_grade": "C"},
            {"type": "course", "code": "MATH 1203", "min_grade": "C"},
        ],
    }


def test_banner_and_binds_tighter_than_or() -> None:
    html = (
        row("", "", "", "", "Computer/Information Science", "2213", "D", "")
        + row("And", "", "", "", "Computer/Information Science", "2223", "D", "")
        + row("Or", "", "", "", "Mathematics", "2914", "C*", "")
    )
    result = parse_banner_prereq_html(html, SUBJECTS)
    assert result.confidence == "medium"
    assert result.tree is not None and result.tree["type"] == "or"
    assert result.tree["items"][0]["type"] == "and"
    assert result.tree["items"][1]["min_grade"] == "C"  # 'C*' normalized


def test_banner_corequisites() -> None:
    html = "<tr><td>Computer/Information Science</td><td>1011</td><td>LAB</td></tr>"
    assert parse_banner_coreq_html(html, SUBJECTS) == ["COMS 1011"]


def test_description_offered_standing_and_acts() -> None:
    facts = parse_description(
        "ACTS Common Course - MATH 2505. Offered: Fall, Spring. Prerequisite: Senior standing. Pass/fail."
    )
    assert facts.offered == ["FA", "SP"]
    assert facts.standing == "SR"
    assert facts.acts_equivalent == "MATH 2505"
    assert facts.pass_fail


def test_text_prereq_math_ladder_and_grades() -> None:
    tree = parse_prereq_text("C> COMS 1013 & C> MATH 1113 or higher", LADDER).tree
    assert tree is not None and tree["type"] == "and"
    ladder = tree["items"][1]
    assert [i["code"] for i in ladder["items"]] == LADDER
    assert all(i["min_grade"] == "C" for i in ladder["items"])


def test_text_prereq_act_above_26_and_bare_numbers() -> None:
    tree = parse_prereq_text("MATH ACT >26, or C> in MATH 1203/1914", LADDER).tree
    assert tree is not None
    assert tree["items"][0] == {"type": "test", "test": "ACT Math", "min_score": 27}
    both = parse_prereq_text("COMS 2213 & 2223", LADDER).tree
    assert both == {
        "type": "and",
        "items": [
            {"type": "course", "code": "COMS 2213", "min_grade": None},
            {"type": "course", "code": "COMS 2223", "min_grade": None},
        ],
    }


def test_text_prereq_standing_and_leftovers() -> None:
    result = parse_prereq_text("Junior standing in COMS", LADDER)
    assert result.tree == {"type": "standing", "standing": "JR"}
    fuzzy = parse_prereq_text("Instructor approval of portfolio", LADDER)
    assert fuzzy.confidence == "low" and fuzzy.tree is not None and fuzzy.tree["type"] == "unparsed"


def test_code_extraction_cases() -> None:
    assert extract_codes("CHEM 1113/1111-Surv. of Chemistry(ACTS=CHEM 1214)") == [
        "CHEM 1113",
        "CHEM 1111",
    ]
    assert extract_codes("BIOL 3803/NUR 3803-Applied Pathophysiology") == ["BIOL 3803", "NUR 3803"]
    assert extract_codes("PSY/SOC 2053- Stat.") == ["PSY 2053", "SOC 2053"]
    assert extract_codes("* ACCT-2004 -Accounting Principles I (ACTS=ACCT 2003)") == ["ACCT 2004"]
    assert extract_codes("TECH1001-Orientation") == ["TECH 1001"]
    assert extract_codes("MATH ACT >26") == []


def test_offering_rules_follow_prd_and_history() -> None:
    # Map says Fall only, catalog says Fall/Spring: stricter wins, flagged conflicting.
    spring = _regular_season("SP", ["FA", "SP"], ["FA"], ["cs"], [], 4, {})
    assert spring["available"] is False and spring["confidence"] == "conflicting"
    # Catalog says Fall, map says Spring only: the stricter reading leaves nothing, so the
    # class schedule decides (FW 3053 ran four falls) ...
    history = {"FA": ["202370", "202470", "202570", "202670"]}
    fall = _regular_season("FA", ["FA"], ["SP"], ["fw"], history["FA"], 4, history)
    spring = _regular_season("SP", ["FA"], ["SP"], ["fw"], [], 4, history)
    assert fall["available"] and not spring["available"] and fall["confidence"] == "conflicting"
    # ... and with no schedule record either term is allowed.
    assert _regular_season("SP", ["FA"], ["SP"], ["fw"], [], 0, {})["available"]
    # No restriction anywhere: assumed available (PRD §7.4).
    assert _regular_season("SP", None, [], [], [], 0, {})["confidence"] == "assumed"
    # Ran in fall 3x, never in spring: spring is unknown (D8).
    assert _regular_season("SP", None, [], [], [], 3, {})["confidence"] == "unknown"
    # Summer: likely for lower-level gen-eds with no history; unknown otherwise.
    assert _short_season("SU", None, [], [], 0, False, gen_ed=True)["confidence"] == "assumed"
    assert _short_season("SU", None, [], [], 0, False, gen_ed=False)["confidence"] == "unknown"
    assert _short_season("SU", None, [], ["202540"], 5, True, gen_ed=False)["confidence"] == "derived"
    assert _short_season("SU", ["FA", "SP"], [], [], 5, True, gen_ed=True)["available"] is False


def test_cycle_check_ignores_or_alternatives() -> None:
    def course(code: str, tree: Any) -> dict[str, object]:
        return {"prerequisites": tree}

    either = {
        "type": "or",
        "items": [
            {"type": "course", "code": "B 1", "min_grade": None},
            {"type": "course", "code": "C 1", "min_grade": None},
        ],
    }
    program = {
        "requirements": [
            {"kind": "course", "options": [["A 1"]]},
            {"kind": "course", "options": [["B 1"]]},
            {"kind": "course", "options": [["C 1"]]},
        ]
    }
    soft = {
        "A 1": course("A 1", None),
        "B 1": course(
            "B 1",
            {
                "type": "or",
                "items": [
                    {"type": "course", "code": "A 1", "min_grade": None},
                    {"type": "course", "code": "C 1", "min_grade": None},
                ],
            },
        ),
        "C 1": course("C 1", either),
    }
    assert _no_cycles(program, soft)["passed"]
    hard = {
        "A 1": course("A 1", {"type": "course", "code": "B 1", "min_grade": None}),
        "B 1": course("B 1", {"type": "course", "code": "A 1", "min_grade": None}),
        "C 1": course("C 1", None),
    }
    result = _no_cycles(program, hard)
    assert not result["passed"] and "A 1" in result["detail"]


def test_corequisite_groups() -> None:
    assert parse_coreq_groups("SEED 4809 or SEED 4909") == [["SEED 4809", "SEED 4909"]]
    assert parse_coreq_groups("NUR 3204 and 3402") == [["NUR 3204"], ["NUR 3402"]]
    assert parse_coreq_groups("MATH 2914 and PHYS 2000") == [["MATH 2914"], ["PHYS 2000"]]
    assert parse_coreq_groups("EAM 3003, 3013 and 4033, or consent of department head") == [
        ["EAM 3003"],
        ["EAM 3013"],
        ["EAM 4033"],
    ]
    with_consent = "MUS 1441 or MUS 1201 or permission of instructor"
    assert parse_coreq_groups(with_consent) == [["MUS 1441", "MUS 1201"]]
    assert parse_coreq_groups("3000 level applied instruction on major performance instrument") == []
