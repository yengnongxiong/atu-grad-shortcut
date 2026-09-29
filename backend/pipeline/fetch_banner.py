"""Fetch the Banner catalog entries, course details, and schedule history Shortcut needs.

Seeds are every course code named on any degree map (rows, notes, gen-ed lists). Course
details are fetched for the seeds plus their prerequisite closure, so every prerequisite
code can be resolved (PRD §7.6).
"""

from __future__ import annotations

import html as htmllib
import re
from collections.abc import Iterable

from pipeline.banner import HISTORY_TERMS, BannerClient
from pipeline.codes import number_of, subject_of

PREREQ_CELL_RE = re.compile(r"<td>(.*?)</td>", re.S)


def prereq_codes_from_html(prereq_html: str, subject_codes: dict[str, str]) -> list[str]:
    """Course codes referenced by a Banner prerequisite table (subjects shown by description)."""
    codes: list[str] = []
    for row in re.findall(r"<tr>(.*?)</tr>", prereq_html, re.S):
        cells = [htmllib.unescape(c).strip() for c in PREREQ_CELL_RE.findall(row)]
        if len(cells) < 6:
            continue
        subject_desc, number = cells[4], cells[5]
        code = subject_codes.get(subject_desc)
        if code and re.fullmatch(r"\d{4}", number):
            codes.append(f"{code} {number}")
    return codes


def fetch_all(
    client: BannerClient,
    seed_codes: Iterable[str],
    max_depth: int = 3,
    history: bool = True,
    log: bool = False,
) -> dict[str, object]:
    subjects = client.subjects()
    by_desc = {s["description"]: s["code"] for s in subjects}
    known_subjects = {s["code"] for s in subjects}
    client.terms()

    catalog: dict[str, dict[str, object]] = {}
    fetched_subjects: set[str] = set()

    def ensure_subject(subject: str) -> None:
        if subject in fetched_subjects or subject not in known_subjects:
            return
        fetched_subjects.add(subject)
        for row in client.catalog_subject(subject):
            code = f"{row['subjectCode']} {row['courseNumber']}"
            catalog[code] = row

    frontier = sorted(set(seed_codes))
    detailed: set[str] = set()
    missing: set[str] = set()
    for depth in range(max_depth + 1):
        next_frontier: set[str] = set()
        for code in frontier:
            if code in detailed:
                continue
            ensure_subject(subject_of(code))
            if code not in catalog:
                missing.add(code)
                continue
            details = client.course_details(subject_of(code), number_of(code))
            detailed.add(code)
            for prereq in prereq_codes_from_html(details["prerequisites_html"], by_desc):
                if prereq not in detailed:
                    next_frontier.add(prereq)
        if log:
            print(f"depth {depth}: detailed={len(detailed)} next={len(next_frontier)}", flush=True)
        frontier = sorted(next_frontier)
        if not frontier:
            break

    history_subjects = sorted({subject_of(c) for c in detailed})
    if history:
        for term in HISTORY_TERMS:
            for subject in history_subjects:
                client.schedule_subject(term, subject)
            if log:
                print(f"schedule {term}: {len(history_subjects)} subjects", flush=True)
    return {
        "subjects": len(fetched_subjects),
        "detailed": len(detailed),
        "missing_from_catalog": sorted(missing),
        "history_subjects": history_subjects,
    }
