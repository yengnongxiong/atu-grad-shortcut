"""Parser fixtures from four differently formatted 2026-27 maps (CLAUDE.md: at least three)."""

from __future__ import annotations

from pipeline.codes import extract_codes
from pipeline.parse_degree_map import parse_degree_map
from tests.synthetic import REPO

MAPS = REPO / "data" / "raw" / "degree_maps" / "2026-27"


def rows_of(name: str) -> dict[int, list[str]]:
    parsed = parse_degree_map(MAPS / name)
    return {s.number: [r.text for r in s.rows] for s in parsed.semesters}


def test_nursing_single_line_rows_and_admission_notes() -> None:
    parsed = parse_degree_map(MAPS / "NursingBSN.pdf")
    assert parsed.degree_name == "Bachelor of Science" and parsed.program_name == "Nursing"
    sem5 = parsed.semesters[4]
    assert [extract_codes(r.text)[0] for r in sem5.rows] == [
        "NUR 3206",
        "NUR 3402",
        "NUR 3404",
        "NUR 3513",
    ]
    assert sem5.stated_total_min == 15
    sem4 = parsed.semesters[3]
    assert any("Requires admission to Upper Level" in r.notes for r in sem4.rows)
    assert "Communication Courses" in parsed.gen_ed_lists


def test_accounting_multiline_cells_with_centered_hours() -> None:
    parsed = parse_degree_map(MAPS / "Accounting.pdf")
    sem2 = parsed.semesters[1]
    comm = next(r for r in sem2.rows if "COMM 2173" in r.text)
    assert "COMM 2003" in comm.text  # both alternatives in one row
    assert comm.hours_min == 3
    assert sum(r.hours_min or 0 for r in sem2.rows) == sem2.stated_total_min


def test_criminal_justice_header_without_hrs_label() -> None:
    parsed = parse_degree_map(MAPS / "CriminalJusticeBA.pdf")
    assert [s.number for s in parsed.semesters] == list(range(1, 9))
    sem1 = parsed.semesters[0]
    assert sum(r.hours_min or 0 for r in sem1.rows) == sem1.stated_total_min


def test_fisheries_two_page_map() -> None:
    parsed = parse_degree_map(MAPS / "FisheriesWildlifeBio.pdf")
    assert [s.number for s in parsed.semesters] == list(range(1, 9))
    sem8 = parsed.semesters[7]
    assert any("FW 4083" in r.text for r in sem8.rows)
    assert parsed.min_total_hours == 120


def test_subject_wrapped_away_from_its_number_joins_the_next_line() -> None:
    """Mechanical Engineering: "CHEM 2134/2130 ... OR PHYS" / "2124/2010 ... 4" is one row."""
    parsed = parse_degree_map(MAPS / "MechanicalEngineering.pdf")
    sem3 = parsed.semesters[2]
    first = sem3.rows[0]
    assert "OR PHYS 2124/2010" in first.text and first.hours_min == 4
    assert sum(r.hours_min or 0 for r in sem3.rows) == sem3.stated_total_min == 14


def test_option_list_under_choose_from_row_stays_in_that_row() -> None:
    """Biology-Biomedical: the small-print options belong to "Major Support Elective"."""
    parsed = parse_degree_map(MAPS / "BiologyBiomedical.pdf")
    sem4 = parsed.semesters[3]
    elective = next(r for r in sem4.rows if "Major Support Elective" in r.text)
    assert "AHS 2013" in elective.text and "PHIL 3103" in elective.text
    assert sum(r.hours_min or 0 for r in sem4.rows) == sem4.stated_total_min == 15


def test_summer_block_after_senior_year_is_parsed_as_a_summer() -> None:
    """Health Information Management ends with "Summer after Senior year" (HIM 4892 + 4895)."""
    parsed = parse_degree_map(MAPS / "HealthInformationMgmt.pdf")
    assert [s.number for s in parsed.semesters] == list(range(1, 10))
    summer = parsed.semesters[-1]
    assert summer.season == "SU" and summer.label == "Summer after Senior year"
    assert [extract_codes(r.text)[0] for r in summer.rows] == ["HIM 4892", "HIM 4895"]
    assert summer.stated_total_min == 7
    assert sum(s.stated_total_min or 0 for s in parsed.semesters) == 120
