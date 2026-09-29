"""Stage 5: turn a parsed degree map into a Program with requirements (PRD §7.3)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pipeline.codes import code_groups, extract_codes, level_of, strip_acts, subject_of
from pipeline.discover import MapRef
from pipeline.parse_degree_map import MapRow, ParsedMap

# ----------------------------------------------------------------------------- gen-ed categories

CATEGORY_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "fine_arts_humanities",
        "Fine Arts & Humanities",
        re.compile(r"fine\s*arts|humanit|\bhum\b", re.I),
    ),
    (
        "us_history_government",
        "U.S. History & Government",
        re.compile(r"u\.?\s?s\.?\s*hist|us\s*history|history\s*(?:&|and|or|/)\s*gov", re.I),
    ),
    ("social_sciences", "Social Sciences", re.compile(r"social\s*sci", re.I)),
    (
        "science_with_lab",
        "Science with Lab",
        re.compile(r"science\s*w(?:ith|/)?\s*(?:a\s+)?lab|lab\s*science", re.I),
    ),
    (
        "communication",
        "Communication",
        re.compile(r"(?:^|/|\s)(?:comm(?:unication|unicat)?|speech)\b(?!\s*\d)", re.I),
    ),
]

SUBJECT_WORDS: dict[str, list[str]] = {
    "biology": ["BIOL"],
    "english": ["ENGL"],
    "history": ["HIST"],
    "music": ["MUS"],
    "art": ["ART"],
    "political science": ["POLS"],
    "geography": ["GEOG"],
    "economics": ["ECON"],
    "philosophy": ["PHIL"],
    "psychology": ["PSY"],
    "sociology": ["SOC"],
    "chemistry": ["CHEM"],
    "physics": ["PHYS"],
    "math": ["MATH"],
    "statistics": ["STAT"],
    "agricultur": ["AGBU", "AGAS", "AGPS", "AGSS", "AGEG", "AGLE", "AGED"],
    "journalism": ["JOUR"],
    "theatre": ["TH"],
    "theater": ["TH"],
}

LIST_NAME_TO_CATEGORY: list[tuple[str, re.Pattern[str]]] = [
    ("fine_arts_humanities", re.compile(r"fine\s*arts|humanities", re.I)),
    ("us_history_government", re.compile(r"history\s*(?:&|and)\s*gov", re.I)),
    ("social_sciences", re.compile(r"^social\s*sci", re.I)),
    ("science_with_lab", re.compile(r"science\s*with\s*lab|lab\s*science", re.I)),
    ("communication", re.compile(r"communication", re.I)),
]


def list_category(list_name: str) -> str | None:
    for key, pattern in LIST_NAME_TO_CATEGORY:
        if pattern.search(list_name):
            return key
    return None


def row_categories(label: str) -> list[tuple[str, str]]:
    return [(key, name) for key, name, pattern in CATEGORY_PATTERNS if pattern.search(label)]


ELECTIVE_RE = re.compile(r"elective", re.I)
LEVEL_RANGE_RE = re.compile(r"\(?\s*(\d)000\s*-\s*(\d)000\s*(?:level)?\)?", re.I)


# ----------------------------------------------------------------------------- program


@dataclass
class ProgramContext:
    courses: dict[str, dict[str, Any]]
    subjects: set[str]
    pooled_lists: dict[str, list[str]]  # category -> codes (from same-year maps)
    policies: dict[str, Any]


def degree_abbreviation(degree_name: str) -> str:
    words = [w for w in degree_name.split() if w.lower() not in {"of", "in", "and"}]
    return "".join(w[0].upper() for w in words)


def program_lists(parsed: ParsedMap) -> dict[str, list[str]]:
    lists: dict[str, list[str]] = {}
    for name, codes in parsed.gen_ed_lists.items():
        category = list_category(name)
        if category:
            lists.setdefault(category, [])
            lists[category] += [c for c in codes if c not in lists[category]]
    return lists


def build_program(ref: MapRef, parsed: ParsedMap, ctx: ProgramContext) -> dict[str, Any]:
    own_lists = program_lists(parsed)
    requirements: list[dict[str, Any]] = []
    schedule: list[dict[str, Any]] = []
    for semester in parsed.semesters:
        semester_reqs = [
            build_requirement(f"s{semester.number}r{index + 1}", row, own_lists, parsed, ctx)
            for index, row in enumerate(semester.rows)
        ]
        infer_missing_hours(semester_reqs, semester.stated_total_min, semester.stated_total_max, ctx)
        requirements.extend(semester_reqs)
        schedule.append(
            {
                "semester": semester.number,
                "stated_total": semester.stated_total_text,
                "stated_total_min": semester.stated_total_min,
                "stated_total_max": semester.stated_total_max,
                "items": [
                    {
                        "requirement_id": r["id"],
                        "label": r["label"],
                        "hours": r["hours"],
                        "hours_max": r["hours_max"],
                        "hours_source": r["hours_source"],
                    }
                    for r in semester_reqs
                ],
            }
        )
    resolve_repeated_alternatives(requirements)
    degree = parsed.degree_name
    is_bachelor = degree.lower().startswith("bachelor") or (
        not degree and not ref.listed_as_associate and len(parsed.semesters) >= 8
    )
    name = parsed.program_name or ref.title
    policies = ctx.policies
    return {
        "id": ref.program_id,
        "name": _clean_name(name),
        "listed_title": ref.title,
        "degree": degree or ("Bachelor's degree" if is_bachelor else ""),
        "degree_abbr": degree_abbreviation(degree) if degree else "",
        "is_bachelor": is_bachelor,
        "college": derive_college(requirements, ctx.courses),
        "catalog_year": ref.catalog_year,
        "revision": parsed.revision,
        "total_hours_min": parsed.min_total_hours or policies["total_hours_min"]["value"],
        "total_hours_source": "degree_map" if parsed.min_total_hours else "policy_default",
        "upper_level_hours_min": parsed.min_upper_hours or policies["upper_level_hours_min_default"]["value"],
        "upper_level_source": "degree_map" if parsed.min_upper_hours else "policy_default",
        "gpa_min": parsed.gpa_min or 2.0,
        "max_pe_hours": parsed.max_pe_hours,
        "requirements": requirements,
        "map_schedule": schedule,
        "min_grade_courses": sorted(
            {c for r in requirements if r.get("min_grade") for opt in r.get("options", []) for c in opt}
        ),
        "notes": parsed.footnotes,
        "prerequisite_courses_line": parsed.prerequisite_courses_line,
        "gen_ed_lists": own_lists,
        "admission_gates": admission_gates(parsed),
        "parser_warnings": parsed.warnings,
        "sources": [{"title": f"{ref.catalog_year} degree map: {ref.title}", "url": ref.url}],
        "raw_path": str(ref.raw_path().relative_to(ref.raw_path().parents[3])),
    }


def infer_missing_hours(
    reqs: list[dict[str, Any]],
    stated_min: float | None,
    stated_max: float | None,
    ctx: ProgramContext,
) -> None:
    """Fill hours the PDF's text layer lacks, keeping provenance (never silently).

    1. A course row takes the catalog's credit hours (documented).
    2. If exactly one row is still missing and the semester total is a single number, it takes
       the remainder (derived).
    """
    for req in reqs:
        if req["hours"] is not None or req["kind"] != "course":
            continue
        total = 0.0
        for code in req["options"][0]:
            course = ctx.courses.get(code)
            if course is None or course.get("hours") is None:
                total = -1
                break
            total += float(course["hours"])
        if total >= 0:
            req["hours"] = total
            req["hours_source"] = "catalog"
            req["warnings"].append("hours missing from the PDF text; taken from the catalog")
    missing = [r for r in reqs if r["hours"] is None]
    known = sum(float(r["hours"]) for r in reqs if r["hours"] is not None)
    if len(missing) == 1 and stated_min is not None and stated_min == stated_max:
        remainder = stated_min - known
        if remainder > 0:
            missing[0]["hours"] = remainder
            missing[0]["hours_source"] = "semester_total"
            missing[0]["warnings"].append(
                f"hours missing from the PDF text; derived from the stated semester total ({remainder:g})"
            )


def _clean_name(name: str) -> str:
    name = re.sub(r",?\s*Page\s+\d+\s+of\s+\d+", "", name).strip(" ,-")
    return re.sub(r"\s+", " ", name)


def admission_gates(parsed: ParsedMap) -> list[str]:
    """Notes saying upper-level courses need program admission (cohort programs)."""
    gates: list[str] = []
    for semester in parsed.semesters:
        for row in semester.rows:
            if re.search(r"admission to (?:the )?upper[- ]level|require[s]? admission", row.notes, re.I):
                text = re.search(r"[^.]*admission[^.]*", row.notes, re.I)
                gate = text.group(0).strip() if text else row.notes
                if gate not in gates:
                    gates.append(gate)
    return gates


def derive_college(requirements: list[dict[str, Any]], courses: dict[str, dict[str, Any]]) -> str:
    counts: Counter[str] = Counter()
    for req in requirements:
        for option in req.get("options", [])[:1]:
            for code in option:
                course = courses.get(code)
                if course and course.get("college"):
                    counts[str(course["college"])] += 3 if course["level"] >= 3000 else 1
    return counts.most_common(1)[0][0] if counts else ""


# ----------------------------------------------------------------------------- requirements


def build_requirement(
    req_id: str,
    row: MapRow,
    own_lists: dict[str, list[str]],
    parsed: ParsedMap,
    ctx: ProgramContext,
) -> dict[str, Any]:
    text = re.sub(r"\s+#\s*$", "", row.text).strip()
    clean = strip_acts(text)
    codes = extract_codes(clean)
    first_code = re.search(r"[A-Z]{2,5}(?:/[A-Z]{2,5})*\s?-?\d{4}", clean)
    prefix = clean[: first_code.start()] if first_code else clean
    warnings: list[str] = []
    base: dict[str, Any] = {
        "id": req_id,
        "map_semester": row.semester,
        "hours": row.hours_min,
        "hours_max": row.hours_max if row.hours_max != row.hours_min else None,
        "hours_source": "degree_map" if row.hours_min is not None else None,
        "min_grade": "C" if row.grade_c else None,
        "raw_text": row.text,
        "notes": row.notes,
        "warnings": warnings,
    }
    if row.hours_min is None:
        warnings.append("no hours value in the PDF text for this row")

    categories = row_categories(prefix)
    has_elective_word = bool(ELECTIVE_RE.search(prefix))
    if has_elective_word and not (categories and not _subject_tokens(prefix, ctx)):
        return {**base, **_elective_bucket(prefix or clean, codes, ctx, warnings)}
    if categories and (not codes or re.search(r"recommend|suggest|\bor\b", clean, re.I)):
        return {**base, **_category_bucket(prefix, categories, codes, own_lists, ctx, warnings)}
    if not codes:
        special = _special_bucket(clean, parsed, ctx, warnings)
        if special is not None:
            return {**base, **special}
        warnings.append(f"unrecognized requirement label: {clean!r}")
        return {
            **base,
            "kind": "bucket",
            "label": clean,
            "bucket": {"category": "unrecognized", "codes": [], "rule": None, "recommended": []},
            "confidence": "low",
        }
    return {**base, **_course_requirement(clean, row, ctx, warnings)}


def _subject_tokens(label: str, ctx: ProgramContext) -> list[str]:
    tokens = [t for t in re.findall(r"\b([A-Z]{2,5})\b", label) if t in ctx.subjects]
    lowered = label.lower()
    for word, subjects in SUBJECT_WORDS.items():
        if re.search(rf"\b{word}", lowered):
            tokens += [s for s in subjects if s not in tokens]
    return tokens


LANGUAGE_RE = re.compile(r"beginning\s+language\s+(i{1,2})\b", re.I)


def _special_bucket(
    label: str, parsed: ParsedMap, ctx: ProgramContext, warnings: list[str]
) -> dict[str, Any] | None:
    """Codeless rows that name a rule rather than a list: math, languages, minors, subjects."""
    lang = LANGUAGE_RE.search(label)
    if lang:
        number = "1013" if lang.group(1).lower() == "i" else "1023"
        pool = [c for codes in parsed.gen_ed_lists.values() for c in codes]
        if not pool:  # maps without option lists: the common 2026-27 Fine Arts & Humanities list
            pool = ctx.pooled_lists.get("fine_arts_humanities", [])
            warnings.append("language options not listed on this map; using the common list")
        languages = {"SPAN", "FR", "GER", "JPN", "CHIN", "LAT"}
        codes = [c for c in dict.fromkeys(pool) if c.endswith(number) and c.split()[0] in languages]
        if codes:
            return {
                "kind": "bucket",
                "label": label,
                "confidence": "high",
                "bucket": {"category": "language", "codes": codes, "rule": None, "recommended": []},
            }
    if re.fullmatch(r"\*?\s*mathematics\s*#?", label.strip(), re.I):
        warnings.append(
            "general-education mathematics: any MATH course that meets the gen-ed "
            "math requirement (list not on the map); confirm with an advisor"
        )
        return {
            "kind": "bucket",
            "label": "Mathematics (gen-ed)",
            "confidence": "medium",
            "bucket": {
                "category": "gen_ed_math",
                "codes": [],
                "rule": {
                    "min_level": 1000,
                    "max_level": 2000,
                    "subjects": ["MATH"],
                    "approved": False,
                    "general": False,
                },
                "recommended": ["MATH 1113"],
            },
        }
    if re.search(r"\bminor\b|2nd major|second major", label, re.I):
        return {
            "kind": "bucket",
            "label": re.sub(r"\s+", " ", label).strip(),
            "confidence": "medium",
            "bucket": {
                "category": "minor",
                "codes": [],
                "rule": {
                    "min_level": None,
                    "max_level": None,
                    "subjects": None,
                    "approved": False,
                    "general": True,
                },
                "recommended": [],
            },
        }
    subjects = _subject_tokens(label, ctx)
    level = LEVEL_RANGE_RE.search(label)
    if subjects or level:
        warnings.append(f"rule inferred from the label {label!r}")
        return {
            "kind": "bucket",
            "label": re.sub(r"\s+", " ", label.replace("*", "")).strip(),
            "confidence": "medium",
            "bucket": {
                "category": "rule",
                "codes": [],
                "rule": {
                    "min_level": int(level.group(1)) * 1000 if level else None,
                    "max_level": int(level.group(2)) * 1000 if level else None,
                    "subjects": subjects or None,
                    "approved": True,
                    "general": False,
                },
                "recommended": [],
            },
        }
    return None


def _category_bucket(
    label: str,
    categories: list[tuple[str, str]],
    recommended: list[str],
    own_lists: dict[str, list[str]],
    ctx: ProgramContext,
    warnings: list[str],
) -> dict[str, Any]:
    codes: list[str] = []
    for key, name in categories:
        options = own_lists.get(key)
        if not options:
            options = ctx.pooled_lists.get(key, [])
            if options:
                warnings.append(f"{name} options not listed on this map; using the common list")
        codes += [c for c in options if c not in codes]
    if not codes:
        warnings.append(f"no option list found for {label.strip()!r}")
    display = " / ".join(name for _, name in categories)
    return {
        "kind": "bucket",
        "label": display,
        "bucket": {
            "category": "+".join(key for key, _ in categories),
            "codes": codes,
            "rule": None,
            "recommended": recommended,
        },
        "confidence": "high" if codes else "low",
    }


def _elective_bucket(
    label: str, codes: list[str], ctx: ProgramContext, warnings: list[str]
) -> dict[str, Any]:
    level = LEVEL_RANGE_RE.search(label)
    min_level = int(level.group(1)) * 1000 if level else None
    max_level = int(level.group(2)) * 1000 if level else None
    if re.search(r"upper[- ]level|upper[- ]division", label, re.I) and min_level is None:
        min_level, max_level = 3000, 4000
    subjects = _subject_tokens(label, ctx)
    approved = bool(re.search(r"approved|directed|major|support", label, re.I))
    general = bool(re.search(r"general", label, re.I)) or not (subjects or approved or min_level)
    clean_label = re.sub(r"\s+", " ", label.replace("*", "")).strip(" -")
    confidence = "high" if (general or min_level or subjects) else "medium"
    if approved and not (min_level or subjects):
        warnings.append("approved elective with no level/subject rule; any course assumed")
    return {
        "kind": "bucket",
        "label": clean_label,
        "bucket": {
            "category": "elective",
            "codes": [],
            "rule": {
                "min_level": min_level,
                "max_level": max_level,
                "subjects": subjects or None,
                "approved": approved,
                "general": general,
            },
            "recommended": codes,
        },
        "confidence": confidence,
    }


def _course_requirement(clean: str, row: MapRow, ctx: ProgramContext, warnings: list[str]) -> dict[str, Any]:
    segments = [s for s in re.split(r"\s+(?:or|OR)\s+", clean) if s.strip()]
    options: list[list[str]] = []
    unresolved: list[str] = []
    for segment in segments:
        groups = code_groups(segment)
        bare = re.match(r"^\s*(\d{4})\b", segment)
        if not groups and bare and options:
            # "PHIL 2003 or 2043- Honors Philosophy": the alternative inherits the subject.
            groups = [[f"{subject_of(options[-1][0])} {bare.group(1)}"]]
        if not groups:
            unresolved.append(segment.strip())
            continue
        for option in _options_from_groups(groups, segment, row, ctx):
            if option not in options:
                options.append(option)
    sub = re.search(r"([A-Z]{2,5}\s?\d{4})[^.]*?\bmay\s+sub", row.notes)
    if sub:
        alt = extract_codes(sub.group(1))
        if alt and alt not in options:
            options.append(alt)
    # "PHYS 2014/2114/2000": a 0-credit lab is not an alternative to the lecture; its
    # corequisite link schedules it with whichever lecture is chosen.
    credit_options = [o for o in options if any(_catalog_hours(c, ctx) != 0 for c in o)]
    if credit_options and len(credit_options) < len(options):
        dropped = [c for o in options if o not in credit_options for c in o]
        warnings.append(
            f"0-credit lab(s) {', '.join(dropped)} left to corequisite rules, not listed as alternatives"
        )
        options = credit_options
    alternative: dict[str, Any] | None = None
    electives = [s for s in unresolved if ELECTIVE_RE.search(s)]
    if electives:
        # "PHYS 4003 or Elective (3000-4000 level)": kept so a repeat of the row can become the elective.
        elective = _elective_bucket(electives[0], [], ctx, [])
        alternative = {"label": elective["label"], "bucket": elective["bucket"]}
    if unresolved:
        warnings.append(f"alternative without a course code: {'; '.join(unresolved)}")
    unknown = [c for opt in options for c in opt if c not in ctx.courses]
    if unknown:
        warnings.append(f"not in the Banner catalog: {', '.join(unknown)}")
    primary = options[0]
    title = _title_for(primary, clean, ctx)
    confidence = "high"
    if unresolved or unknown:
        confidence = "low" if unknown and all(c in unknown for c in primary) else "medium"
    result: dict[str, Any] = {
        "kind": "course",
        "label": title,
        "options": options,
        "confidence": confidence,
    }
    if alternative:
        result["elective_alternative"] = alternative
    return result


def _catalog_hours(code: str, ctx: ProgramContext) -> float | None:
    course = ctx.courses.get(code)
    return None if course is None or course.get("hours") is None else float(course["hours"])


def resolve_repeated_alternatives(requirements: list[dict[str, Any]]) -> None:
    """A row like "PHYS 4003 or Elective (3000-4000 level)" listed in two semesters means one of
    each: the later copy becomes the elective."""
    seen: dict[str, dict[str, Any]] = {}
    for req in requirements:
        if req["kind"] != "course":
            continue
        key = repr(req["options"])
        first = seen.get(key)
        alternative = req.get("elective_alternative")
        if first is not None and alternative:
            req["kind"] = "bucket"
            req["label"] = alternative["label"]
            req["bucket"] = {**alternative["bucket"], "recommended": []}
            req["warnings"].append(
                f"{first['label']} is already on the map in semester {first['map_semester']}, "
                f"so this repeat of the row is the elective alternative"
            )
            del req["options"]
            continue
        seen.setdefault(key, req)


def _options_from_groups(
    groups: list[list[str]], segment: str, row: MapRow, ctx: ProgramContext
) -> list[list[str]]:
    """Lecture/lab pairs and '&' become one option; cross-lists become alternatives."""
    joined_by_and = bool(re.search(r"&|\band\b|/\s*lab|and lab", segment, re.I))
    options: list[list[str]] = []
    for group in groups:
        subjects = {subject_of(c) for c in group}
        if len(group) > 1 and len(subjects) == 1 and _hours_match(group, row, ctx):
            options.append(group)  # e.g. CHEM 1113/1111 lecture + lab
        elif len(group) > 1:
            options.extend([c] for c in group)  # cross-listed alternatives
        else:
            options.append(group)
    if joined_by_and and len(options) > 1 and _hours_match([c for o in options for c in o], row, ctx):
        return [[c for o in options for c in o]]
    return options


def _hours_match(codes: list[str], row: MapRow, ctx: ProgramContext) -> bool:
    if row.hours_min is None:
        return False
    total = 0.0
    for code in codes:
        course = ctx.courses.get(code)
        if not course or course["hours"] is None:
            return False
        total += float(course["hours"])
    return abs(total - row.hours_min) < 0.01 or (
        row.hours_max is not None and row.hours_min <= total <= row.hours_max
    )


def _title_for(option: list[str], clean: str, ctx: ProgramContext) -> str:
    titles = [str(ctx.courses[c]["title"]) for c in option if c in ctx.courses]
    if titles:
        return " + ".join(titles)
    m = re.search(r"\d{4}\s*[-–]\s*([^()]+)", clean)
    return m.group(1).strip() if m else clean


def requirement_levels(req: dict[str, Any], courses: dict[str, dict[str, Any]]) -> int:
    """Lowest course level a requirement can be met with (for upper-level hour checks)."""
    if req["kind"] == "course":
        return min(level_of(c) for c in req["options"][0])
    rule = req["bucket"].get("rule") or {}
    if rule.get("min_level"):
        return int(rule["min_level"])
    codes = req["bucket"].get("codes") or []
    return min((level_of(c) for c in codes), default=1000)
