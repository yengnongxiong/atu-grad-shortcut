"""The 2025-26 CS degree-map parse must match PRD Appendix A (CLAUDE.md data rules)."""

from __future__ import annotations

import json
from functools import lru_cache

from pipeline.codes import extract_codes
from pipeline.enrich_catalog import notes_for_row
from pipeline.parse_degree_map import ParsedMap, parse_degree_map
from pipeline.programs import list_category
from tests.synthetic import REPO

APPENDIX = json.loads((REPO / "data" / "manual" / "appendix_a_cs_2025_26.json").read_text())
PDF = REPO / "data" / "raw" / "degree_maps" / "2025-26" / "ComputerScience.pdf"

BUCKET_ALIASES = {
    "Social Sciences": "social_sciences",
    "Science with Lab": "science_with_lab",
    "Fine Arts & Humanities": "fine_arts_humanities",
    "U.S. History/Government": "us_history_government",
}


@lru_cache(maxsize=1)
def parsed() -> ParsedMap:
    return parse_degree_map(PDF)


def test_header_and_graduation_requirements() -> None:
    p = parsed()
    program = APPENDIX["program"]
    assert p.degree_name == program["degree"]
    assert p.program_name == program["name"]
    assert p.catalog_year_text == "2025-2026"
    assert p.min_total_hours == program["total_hours_min"]
    assert p.min_upper_hours == program["upper_level_hours_min"]
    assert p.gpa_min == program["gpa_min"]
    assert p.max_pe_hours == program["max_pe_hours"]
    assert any("9 hours" in note for note in p.footnotes)


def test_semesters_rows_hours_and_grades_match() -> None:
    p = parsed()
    assert [s.number for s in p.semesters] == list(range(1, 9))
    for semester, expected in zip(p.semesters, APPENDIX["semesters"], strict=True):
        assert semester.stated_total_min == expected["total"]
        assert len(semester.rows) == len(expected["rows"]), semester.number
        for row, want in zip(semester.rows, expected["rows"], strict=True):
            assert row.hours_min == want["hours"], (semester.number, row.text)
            if "code" in want:
                assert extract_codes(row.text)[0] == want["code"]
                assert row.grade_c == want["grade_c"], want["code"]
            else:
                assert not extract_codes(row.text)
                assert want["bucket"].split(" (")[0].lower().replace(".", "")[:12] in (
                    row.text.lower().replace(".", "")
                )


def test_fall_spring_only_and_prerequisite_notes() -> None:
    p = parsed()
    rows = {extract_codes(r.text)[0]: r for s in p.semesters for r in s.rows if extract_codes(r.text)}
    for semester in APPENDIX["semesters"]:
        for want in semester["rows"]:
            code = want.get("code")
            if not code:
                continue
            note = notes_for_row("cs", "", rows[code].notes)
            assert note.only == want.get("only"), code
            if want.get("prereq"):
                assert note.prereq_text, code
            if want.get("coreq"):
                assert want["coreq"] in note.coreq_text
    assert "may sub" in rows["COMM 2173"].notes and "COMM 2003" in rows["COMM 2173"].notes


def test_gen_ed_buckets_match_appendix() -> None:
    lists = {list_category(name): set(codes) for name, codes in parsed().gen_ed_lists.items()}
    for name, codes in APPENDIX["gen_ed_buckets"].items():
        key = BUCKET_ALIASES.get(name) or list_category(name)
        assert lists[key] == set(codes), name
