"""Stage 4: build course records (courses.json) from Banner catalog data plus map notes.

Precedence for prerequisites (DECISIONS.md D5):
  1. Banner's structured prerequisite table (what registration enforces),
  2. the catalog description's "Prerequisite:" text (adds class-standing rules the table omits),
  3. degree-map notes,
  4. PRD Appendix A (fallback when Banner is unavailable).
Offerings follow DECISIONS.md D8.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.banner import (
    BANNER_CATALOG_URL,
    BANNER_DIR,
    BANNER_SCHEDULE_URL,
    CATALOG_TERM,
    HISTORY_TERMS,
    term_season,
)
from pipeline.codes import extract_codes, level_of, number_of, subject_of
from pipeline.common import PRD_APPENDIX_SOURCE
from pipeline.prereqs import (
    Tree,
    combine,
    parse_banner_coreq_html,
    parse_banner_prereq_html,
    parse_description,
    parse_prereq_text,
    parse_standing,
    tree_codes,
)

SEASONS = ("FA", "WI", "SP", "SU")


# ----------------------------------------------------------------------------- map notes


@dataclass
class MapNote:
    program_id: str
    source_url: str
    prereq_text: str = ""
    coreq_text: str = ""
    only: str | None = None  # "FA" / "SP" / "SU"
    pass_fail: bool = False


ONLY_RE = re.compile(r"\b(?:offered\s+)?(fall|spring|summer)\s+only\b", re.I)
PREREQ_NOTE_RE = re.compile(
    r"(?:pre-?req(?:uisite)?s?)\s*[:\-]?\s*(.+?)(?=\s*(?:co-?req|fall only|spring only|summer only|"
    r"offered|pass/fail|see note|$))",
    re.I,
)
COREQ_NOTE_RE = re.compile(r"co-?req(?:uisite)?s?\s*[:\-]?\s*((?:[A-Z]{2,5}\s?\d{4}[\s,&and]*)+)", re.I)


def notes_for_row(program_id: str, source_url: str, notes: str) -> MapNote:
    note = MapNote(program_id=program_id, source_url=source_url)
    only = ONLY_RE.search(notes)
    if only:
        note.only = {"fall": "FA", "spring": "SP", "summer": "SU"}[only.group(1).lower()]
    prereq = PREREQ_NOTE_RE.search(notes)
    if prereq:
        note.prereq_text = prereq.group(1).strip(" ,;")
    coreq = COREQ_NOTE_RE.search(notes)
    if coreq:
        note.coreq_text = coreq.group(1).strip(" ,;")
    note.pass_fail = "pass/fail" in notes.lower()
    return note


# ----------------------------------------------------------------------------- inputs


@dataclass
class BannerData:
    subjects: dict[str, str]  # description -> code
    catalog: dict[str, dict[str, Any]]  # code -> catalog row
    details: dict[str, dict[str, str]]  # code -> details html
    history: dict[str, dict[str, list[str]]]  # code -> season -> [term codes]
    history_subjects: set[str]
    available: bool


def load_banner_raw(root: Path = BANNER_DIR) -> BannerData:
    subjects_path = root / "subjects.json"
    if not subjects_path.exists():
        return BannerData({}, {}, {}, {}, set(), False)
    subjects = {s["description"]: s["code"] for s in json.loads(subjects_path.read_text())}
    catalog: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "catalog" / CATALOG_TERM).glob("*.json")):
        for row in json.loads(path.read_text()):
            catalog[f"{row['subjectCode']} {row['courseNumber']}"] = row
    details: dict[str, dict[str, str]] = {}
    for path in sorted((root / "course_details").glob("*/*.json")):
        details[f"{path.parent.name} {path.stem}"] = json.loads(path.read_text())
    history: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    history_subjects: set[str] = set()
    for term in HISTORY_TERMS:
        for path in sorted((root / "schedule" / term).glob("*.json")):
            history_subjects.add(path.stem)
            for section in json.loads(path.read_text()):
                code = f"{section['subject']} {section['courseNumber']}"
                seen = history[code][term_season(term)]
                if term not in seen:
                    seen.append(term)
    return BannerData(
        subjects=subjects,
        catalog=catalog,
        details=details,
        history={k: dict(v) for k, v in history.items()},
        history_subjects=history_subjects,
        available=bool(catalog),
    )


# ----------------------------------------------------------------------------- builder


@dataclass
class CourseBuildContext:
    banner: BannerData
    map_notes: dict[str, list[MapNote]]
    gen_ed_codes: set[str]
    math_ladder: list[str]
    math_act_min: int
    appendix_a: dict[str, dict[str, Any]] = field(default_factory=dict)


def season_terms_in_window() -> dict[str, list[str]]:
    window: dict[str, list[str]] = defaultdict(list)
    for term in HISTORY_TERMS:
        window[term_season(term)].append(term)
    return dict(window)


def build_course(code: str, ctx: CourseBuildContext) -> dict[str, Any]:
    banner = ctx.banner
    row = banner.catalog.get(code)
    details = banner.details.get(code)
    notes = ctx.map_notes.get(code, [])
    appendix = ctx.appendix_a.get(code)
    sources: list[dict[str, str]] = []
    warnings: list[str] = []

    title = ""
    hours: float | None = None
    hours_max: float | None = None
    college = department = ""
    if row:
        title = str(row.get("courseTitle") or "")
        hours = _num(row.get("creditHourLow"))
        hours_max = _num(row.get("creditHourHigh"))
        college = str(row.get("college") or "")
        department = str(row.get("department") or "")
        sources.append({"title": "ATU Banner course catalog", "url": BANNER_CATALOG_URL})
    elif appendix:
        title = str(appendix.get("title", ""))
        hours = float(appendix["hours"])
        sources.append({"title": PRD_APPENDIX_SOURCE, "url": ""})
    else:
        warnings.append("course not found in the Banner catalog")

    facts = parse_description(details["description_html"]) if details else None
    prereq_tree: Tree | None = None
    prereq_raw = ""
    prereq_source: str | None = None
    confidence = "high"
    if details:
        table = parse_banner_prereq_html(details["prerequisites_html"], banner.subjects)
        prereq_tree, confidence = table.tree, table.confidence
        warnings.extend(table.warnings)
        prereq_raw = facts.prereq_text if facts else ""
        prereq_source = "banner_prerequisite_table" if prereq_tree else None
        if prereq_tree is None and facts and facts.prereq_text:
            text = parse_prereq_text(facts.prereq_text, ctx.math_ladder)
            prereq_tree, confidence = _drop_standing(text.tree), text.confidence
            warnings.extend(text.warnings)
            prereq_source = "catalog_description" if prereq_tree else None
    map_prereq = next((n for n in notes if n.prereq_text), None)
    # Map notes fill in only when Banner has no record of the course at all; if Banner lists
    # no prerequisite, the catalog says there is none.
    if prereq_tree is None and details is None and map_prereq is not None:
        text = parse_prereq_text(map_prereq.prereq_text, ctx.math_ladder)
        prereq_tree, confidence = _drop_standing(text.tree), text.confidence
        prereq_raw = map_prereq.prereq_text
        prereq_source = f"degree_map:{map_prereq.program_id}"
        warnings.extend(text.warnings)
    if prereq_tree is None and not details and appendix and appendix.get("prereq"):
        text = parse_prereq_text(str(appendix["prereq"]), ctx.math_ladder)
        prereq_tree, confidence = _drop_standing(text.tree), text.confidence
        prereq_raw = str(appendix["prereq"])
        prereq_source = "prd_appendix_a"

    # Class standing: the Banner table omits it; take it from description or map notes.
    standing = facts.standing if facts else None
    standing_raw = facts.standing_text if facts else ""
    if standing is None:
        for note in notes:
            s, raw = parse_standing(note.prereq_text)
            if s:
                standing, standing_raw = s, f"{raw} (degree map {note.program_id})"
                break

    prereq_tree = _apply_math_policy(code, prereq_tree, ctx.math_act_min)

    coreqs: list[str] = []
    if details:
        coreqs = parse_banner_coreq_html(details["corequisites_html"], banner.subjects)
        if facts and facts.coreq_text:
            coreqs += [c for c in extract_codes(facts.coreq_text) if c not in coreqs]
    for note in notes:
        coreqs += [c for c in extract_codes(note.coreq_text) if c not in coreqs and c != code]

    offered = _offerings(code, facts.offered if facts else None, notes, ctx)
    map_prereq_notes = [{"program_id": n.program_id, "text": n.prereq_text} for n in notes if n.prereq_text]
    level = level_of(code)
    return {
        "code": code,
        "subject": subject_of(code),
        "number": number_of(code),
        "title": _title_case(title),
        "hours": hours,
        "hours_max": hours_max if hours_max and hours_max != hours else None,
        "level": level,
        "upper_division": level >= 3000,
        "college": college,
        "department": department,
        "description": facts.text if facts else "",
        "prerequisites": prereq_tree,
        "prereq_raw": prereq_raw,
        "prereq_source": prereq_source if prereq_tree is not None else None,
        "parse_confidence": confidence if prereq_tree is not None else "high",
        "map_prereq_notes": map_prereq_notes,
        "corequisites": coreqs,
        "standing": standing,
        "standing_raw": standing_raw,
        "offered": offered,
        "history": {s: ctx.banner.history.get(code, {}).get(s, []) for s in SEASONS},
        "acts_equivalent": (facts.acts_equivalent if facts else None)
        or (appendix.get("acts") if appendix else None),
        "pass_fail": bool(facts and facts.pass_fail) or any(n.pass_fail for n in notes),
        "gen_ed": code in ctx.gen_ed_codes,
        "in_catalog": row is not None,
        "warnings": warnings,
        "sources": sources,
    }


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _drop_standing(tree: Tree | None) -> Tree | None:
    """Standing lives in its own field; strip standing nodes from course trees."""
    if tree is None:
        return None
    if tree["type"] == "standing":
        return None
    if tree["type"] in ("and", "or"):
        items = [t for t in (_drop_standing(i) for i in tree["items"]) if t is not None]
        return combine(tree["type"], items)
    return tree


def _apply_math_policy(code: str, tree: Tree | None, act_min: int) -> Tree | None:
    """PRD §8: math ACT above 26 (i.e. 27+) satisfies the Calculus I prerequisite."""
    if tree is None or code != "MATH 2914":
        return tree

    def walk(node: Tree) -> Tree:
        if node["type"] == "test" and "ACT" in node["test"] and "Math" in node["test"]:
            if node["min_score"] < act_min:
                return {**node, "min_score": act_min, "source_min_score": node["min_score"]}
            return node
        if node["type"] in ("and", "or"):
            return {**node, "items": [walk(i) for i in node["items"]]}
        return node

    return walk(tree)


def _title_case(title: str) -> str:
    if title.isupper():
        return title.title()
    return title


def _offerings(
    code: str, catalog_offered: list[str] | None, notes: list[MapNote], ctx: CourseBuildContext
) -> dict[str, dict[str, Any]]:
    history = ctx.banner.history.get(code, {})
    total_runs = sum(len(v) for v in history.values())
    has_history_data = subject_of(code) in ctx.banner.history_subjects
    map_only = sorted({n.only for n in notes if n.only})
    map_sources = sorted({n.program_id for n in notes if n.only})
    level = level_of(code)
    result: dict[str, dict[str, Any]] = {}
    for season in SEASONS:
        runs = history.get(season, [])
        evidence = f"ran {len(runs)}x in {season} ({', '.join(runs)})" if runs else ""
        entry: dict[str, Any]
        if season in ("FA", "SP"):
            entry = _regular_season(season, catalog_offered, map_only, map_sources, runs, total_runs)
        else:
            entry = _short_season(
                season,
                catalog_offered,
                map_only,
                runs,
                total_runs,
                has_history_data,
                gen_ed=code in ctx.gen_ed_codes and level <= 2000,
            )
        if evidence and evidence not in entry["note"]:
            entry["note"] = (entry["note"] + "; " + evidence).strip("; ")
        result[season] = entry
    return result


def _regular_season(
    season: str,
    catalog_offered: list[str] | None,
    map_only: list[str],
    map_sources: list[str],
    runs: list[str],
    total_runs: int,
) -> dict[str, Any]:
    catalog_says = None if catalog_offered is None else season in catalog_offered
    map_says = None if not map_only else season in map_only
    if catalog_says is not None and map_says is not None and catalog_says != map_says:
        return {
            "available": bool(catalog_says and map_says),
            "confidence": "conflicting",
            "source": "catalog+map",
            "note": f"catalog 'Offered: {', '.join(catalog_offered or [])}' vs map "
            f"'{'/'.join(map_only)} only' ({', '.join(map_sources)}); using the stricter",
        }
    if map_says is not None:
        return {
            "available": map_says,
            "confidence": "documented",
            "source": "degree_map",
            "note": f"map note '{'/'.join(map_only)} only' ({', '.join(map_sources)})",
        }
    if catalog_says is not None:
        return {
            "available": catalog_says,
            "confidence": "documented",
            "source": "catalog",
            "note": f"catalog 'Offered: {', '.join(catalog_offered or [])}'",
        }
    if runs:
        return {
            "available": True,
            "confidence": "derived",
            "source": "schedule_history",
            "note": "",
        }
    if total_runs >= 2:
        return {
            "available": True,
            "confidence": "unknown",
            "source": "schedule_history",
            "note": f"not offered in {season} in the Fall 2023-Spring 2027 schedule",
        }
    return {
        "available": True,
        "confidence": "assumed",
        "source": "default",
        "note": "PRD §7.4 default",
    }


def _short_season(
    season: str,
    catalog_offered: list[str] | None,
    map_only: list[str],
    runs: list[str],
    total_runs: int,
    has_history_data: bool,
    gen_ed: bool,
) -> dict[str, Any]:
    if catalog_offered is not None:
        listed = season in catalog_offered
        if listed:
            return {
                "available": True,
                "confidence": "documented",
                "source": "catalog",
                "note": f"catalog 'Offered: {', '.join(catalog_offered)}'",
            }
        if season == "SU" or not runs:
            return {
                "available": False,
                "confidence": "documented",
                "source": "catalog",
                "note": f"catalog 'Offered: {', '.join(catalog_offered)}'",
            }
    if map_only and season not in map_only:
        return {
            "available": False,
            "confidence": "documented",
            "source": "degree_map",
            "note": f"map note '{'/'.join(map_only)} only'",
        }
    if runs:
        return {
            "available": True,
            "confidence": "derived",
            "source": "schedule_history",
            "note": "",
        }
    if has_history_data and total_runs > 0:
        return {
            "available": True,
            "confidence": "unknown",
            "source": "schedule_history",
            "note": f"not offered in {season} in the Fall 2023-Spring 2027 schedule",
        }
    if gen_ed:
        return {
            "available": True,
            "confidence": "assumed",
            "source": "default",
            "note": "likely: 1000-2000 level gen-ed (PRD §7.4)",
        }
    return {"available": True, "confidence": "unknown", "source": "default", "note": "no evidence"}


def prerequisite_closure(codes: set[str], courses: dict[str, dict[str, Any]]) -> set[str]:
    seen = set(codes)
    frontier = list(codes)
    while frontier:
        code = frontier.pop()
        course = courses.get(code)
        if not course:
            continue
        for dep in tree_codes(course["prerequisites"]) + list(course["corequisites"]):
            if dep not in seen:
                seen.add(dep)
                frontier.append(dep)
    return seen


SCHEDULE_SOURCE = {
    "title": "ATU Banner class schedule (Fall 2023-Spring 2027)",
    "url": BANNER_SCHEDULE_URL,
}
