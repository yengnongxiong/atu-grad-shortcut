"""Link one major's degree maps across catalog years (PRD v1.1 §3.2).

ATU students may graduate under the catalog in force when they entered or any later one
(catalog of entry). Each program records its `major_key` and its `successors`: the same major
in newer catalogs, so the app can ask "should I switch?". Two maps are the same major when
their filenames match (Accounting.pdf) or, when ATU renamed the file (EmergencyMgmt.pdf ->
EmergencyManagement.pdf), when the listed title and degree match exactly. Majors that were
split between years come from data/manual/catalog_successors.json.
"""

from __future__ import annotations

from typing import Any


def _file_key(program: dict[str, Any]) -> str:
    return str(program["id"]).removesuffix(f"-{program['catalog_year']}")


def _title_key(program: dict[str, Any]) -> tuple[str, str] | None:
    title = program.get("listed_title")
    return (str(title), str(program.get("degree", ""))) if title else None


def link_catalog_years(programs: list[dict[str, Any]], manual: dict[str, list[str]]) -> None:
    by_file: dict[str, str] = {}  # file key -> major key
    by_title: dict[tuple[str, str], tuple[str, str]] = {}  # title key -> (major key, catalog year)
    for program in sorted(programs, key=lambda p: p["catalog_year"], reverse=True):
        file_key, title = _file_key(program), _title_key(program)
        key = by_file.get(file_key)
        if key is None and title in by_title and by_title[title][1] != program["catalog_year"]:
            key = by_title[title][0]  # a renamed file: same title and degree, another year
        key = key or file_key
        program["major_key"] = key
        by_file.setdefault(file_key, key)
        if title:
            by_title.setdefault(title, (key, program["catalog_year"]))
    by_id = {p["id"]: p for p in programs}
    for program in programs:
        newer = sorted(
            (
                p
                for p in programs
                if p["major_key"] == program["major_key"] and p["catalog_year"] > program["catalog_year"]
            ),
            key=lambda p: p["catalog_year"],
        )
        successors = [p["id"] for p in newer]
        successors += [pid for pid in manual.get(program["id"], []) if pid in by_id and pid not in successors]
        program["successors"] = successors
