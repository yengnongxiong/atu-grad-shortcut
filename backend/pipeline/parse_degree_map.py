"""Stage 3: parse ATU degree-map PDFs using pdfplumber word coordinates.

Degree maps are laid out in two schedule columns (semesters 1-4 left, 5-8 right; some
maps put 5-8 on page 2) with a "Milestones/Notes" area to the right of each column, then
multi-column general-education option lists at the bottom. Plain text extraction
interleaves the columns, so everything here works from word positions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

# ----------------------------------------------------------------------------- types


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    bold: bool
    page: int


@dataclass
class MapRow:
    """One line item in a semester of the sample schedule."""

    semester: int
    text: str
    hours_text: str
    hours_min: float | None
    hours_max: float | None
    grade_c: bool
    notes: str
    page: int
    top: float


@dataclass
class ParsedSemester:
    number: int
    rows: list[MapRow] = field(default_factory=list)
    stated_total_text: str = ""
    stated_total_min: float | None = None
    stated_total_max: float | None = None


@dataclass
class ParsedMap:
    path: str
    title_line: str = ""
    catalog_year_text: str = ""
    degree_name: str = ""
    program_name: str = ""
    revision: str = ""
    semesters: list[ParsedSemester] = field(default_factory=list)
    gen_ed_lists: dict[str, list[str]] = field(default_factory=dict)
    gen_ed_text: dict[str, list[str]] = field(default_factory=dict)
    min_total_hours: int | None = None
    min_upper_hours: int | None = None
    gpa_min: float | None = None
    max_pe_hours: int | None = None
    footnotes: list[str] = field(default_factory=list)
    prerequisite_courses_line: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "title_line": self.title_line,
            "catalog_year_text": self.catalog_year_text,
            "degree_name": self.degree_name,
            "program_name": self.program_name,
            "revision": self.revision,
            "semesters": [
                {
                    "number": s.number,
                    "stated_total_text": s.stated_total_text,
                    "stated_total_min": s.stated_total_min,
                    "stated_total_max": s.stated_total_max,
                    "rows": [
                        {
                            "text": r.text,
                            "hours_text": r.hours_text,
                            "hours_min": r.hours_min,
                            "hours_max": r.hours_max,
                            "grade_c": r.grade_c,
                            "notes": r.notes,
                        }
                        for r in s.rows
                    ],
                }
                for s in self.semesters
            ],
            "gen_ed_lists": self.gen_ed_lists,
            "min_total_hours": self.min_total_hours,
            "min_upper_hours": self.min_upper_hours,
            "gpa_min": self.gpa_min,
            "max_pe_hours": self.max_pe_hours,
            "footnotes": self.footnotes,
            "prerequisite_courses_line": self.prerequisite_courses_line,
            "warnings": self.warnings,
        }


# ----------------------------------------------------------------------------- regexes

HOURS_RE = re.compile(r"^\d{1,2}(?:\.\d)?(?:-\d{1,2})?$")
TITLE_RE = re.compile(
    r"(?P<year>\d{4}\s*-\s*\d{2,4})\s+Degree\s+Map\s*[-–—]\s*(?P<rest>.+?)"
    r"(?:,?\s*Page\s+\d+\s+of\s+\d+)?\s*$",
    re.IGNORECASE,
)
DEGREE_RE = re.compile(
    r"^(?P<degree>(?:Bachelor|Associate)\s+of\s+[A-Za-z ]+?)\s+(?:in|-)\s+(?P<name>.+)$",
    re.IGNORECASE,
)
SUBJECT_TOKEN = r"[A-Z]{2,5}(?:/[A-Z]{2,5})*"
CODE_START_RE = re.compile(rf"^{SUBJECT_TOKEN}$")
NUMBER_RE = re.compile(r"^\d{4}[-–:,)]*$")


# ----------------------------------------------------------------------------- helpers


def _load_words(pdf_path: Path) -> tuple[list[list[Word]], list[float]]:
    pages: list[list[Word]] = []
    widths: list[float] = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages):
            raw = page.extract_words(extra_attrs=["size", "fontname"], x_tolerance=1.6)
            pages.append(
                [
                    Word(
                        text=str(w["text"]),
                        x0=float(w["x0"]),
                        x1=float(w["x1"]),
                        top=float(w["top"]),
                        bottom=float(w["bottom"]),
                        size=float(w["size"]),
                        bold="bold" in str(w["fontname"]).lower(),
                        page=index,
                    )
                    for w in raw
                ]
            )
            widths.append(float(page.width))
    return pages, widths


def cluster_lines(words: list[Word], tolerance: float = 3.5) -> list[list[Word]]:
    """Group words into visual lines (sorted top-to-bottom, words left-to-right)."""
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        if lines and word.top - lines[-1][0].top <= tolerance:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def join_words(words: list[Word]) -> str:
    return re.sub(r"\s+", " ", " ".join(w.text for w in words)).strip()


def parse_hours(text: str) -> tuple[float | None, float | None]:
    text = text.strip()
    if not text:
        return None, None
    if "-" in text:
        low, high = (float(part) for part in text.split("-", 1))
        # "3-0" appears in at least one map; a descending range is treated as its low end.
        return (low, high) if high >= low else (low, low)
    value = float(text)
    return value, value


# ----------------------------------------------------------------------------- headers


@dataclass
class _Header:
    number: int
    page: int
    x0: float
    top: float
    bottom: float
    hrs: Word | None
    grade: Word | None
    x_end: float = 0.0


def _find_headers(lines: list[list[Word]]) -> list[_Header]:
    """Schedule-column headers ("Semester N  Hrs.  Grade").

    Milestone columns repeat "Semester N" too, so a header is *strong* when "Hrs." follows
    it. A weak candidate (e.g. "Semester 1 Grade" or "Semester 6 (Take all...") is kept
    only if it sits in the same x column as a strong header, borrowing that column's
    "Hrs." position.
    """
    strong: list[_Header] = []
    weak: list[_Header] = []
    for line in lines:
        for i, word in enumerate(line[:-1]):
            if word.text != "Semester" or not line[i + 1].text.isdigit():
                continue
            after = line[i + 2 :]
            nxt = after[0] if after else None
            hrs = next((w for w in after[:3] if w.text.lower().startswith("hrs")), None)
            grade = next((w for w in after[:3] if w.text == "Grade"), None)
            header = _Header(
                number=int(line[i + 1].text),
                page=word.page,
                x0=word.x0,
                top=min(w.top for w in line),
                bottom=max(w.bottom for w in line),
                hrs=hrs if hrs is not None and hrs.x0 - word.x0 < 260 else None,
                grade=grade,
            )
            if header.hrs is not None and nxt is not None and nxt.text != "Semester":
                strong.append(header)
            elif nxt is None or nxt.text != "Semester":
                weak.append(header)
    headers = list(strong)
    for candidate in weak:
        column = [h for h in strong if h.page == candidate.page and abs(h.x0 - candidate.x0) < 8]
        if not column or any(h.number == candidate.number for h in strong):
            continue
        template = column[0]
        candidate.hrs = template.hrs
        candidate.grade = candidate.grade or template.grade
        headers.append(candidate)
    return headers


def _assign_column_ends(headers: list[_Header], page_width: float) -> None:
    for header in headers:
        same_line_right = [
            h.x0
            for h in headers
            if h.page == header.page and abs(h.top - header.top) < 4 and h.x0 > header.x0 + 20
        ]
        header.x_end = (min(same_line_right) - 3) if same_line_right else page_width


def _grade_x_for(headers: list[_Header], header: _Header) -> tuple[float, float] | None:
    """Grade column span. Only semester-1/5 header lines carry the word 'Grade'."""
    if header.grade is not None:
        return header.grade.x0, header.grade.x1
    for other in headers:
        if (
            other.grade is not None
            and other.hrs is not None
            and header.hrs is not None
            and abs(other.hrs.x0 - header.hrs.x0) < 6
        ):
            return other.grade.x0, other.grade.x1
    return None


# ----------------------------------------------------------------------------- semesters


def _parse_semester(
    header: _Header, headers: list[_Header], page_words: list[Word]
) -> tuple[ParsedSemester, float]:
    assert header.hrs is not None
    x_start = header.x0 - 3
    hrs_left = header.hrs.x0 - 9
    grade_span = _grade_x_for(headers, header)
    hours_right = grade_span[0] - 0.5 if grade_span else header.hrs.x1 + 11
    grade_right = (grade_span[1] + 3) if grade_span else hours_right
    notes_left = grade_right

    # The semester ends at its "Total hours" line.
    total_word = next(
        (
            w
            for w in sorted(page_words, key=lambda w: w.top)
            if w.top > header.top + 3.5
            and (
                (w.text == "Total" and x_start - 2 <= w.x0 <= x_start + 18)
                # Some maps drop the "Total hours" label; the "<n> GPA" cell remains.
                or (
                    w.text == "GPA"
                    and grade_span is not None
                    and abs(w.x0 - grade_span[0]) < 8
                    and any(
                        abs(o.top - w.top) < 2.5 and hrs_left <= o.x0 < w.x0 and HOURS_RE.match(o.text)
                        for o in page_words
                    )
                )
            )
        ),
        None,
    )
    y_end = total_word.top - 1.0 if total_word else header.bottom + 120
    band = [w for w in page_words if header.top + 3.5 < w.top < y_end and x_start <= w.x0 < header.x_end]
    semester = ParsedSemester(number=header.number)
    if total_word is not None:
        total_line = [
            w for w in page_words if abs(w.top - total_word.top) < 3.5 and hrs_left <= w.x0 < hours_right + 4
        ]
        total_text = next((w.text for w in total_line if HOURS_RE.match(w.text)), "")
        semester.stated_total_text = total_text
        semester.stated_total_min, semester.stated_total_max = parse_hours(total_text)

    lines = cluster_lines(band)
    parts: list[dict[str, Any]] = []
    for line in lines:
        course = [w for w in line if w.x0 < hrs_left]
        hours = [w for w in line if hrs_left <= w.x0 < hours_right and HOURS_RE.match(w.text)]
        grade = [w for w in line if hours_right <= w.x0 < grade_right and w.text == "#"]
        notes = [
            w
            for w in line
            if w.x0 >= notes_left or (hrs_left <= w.x0 < notes_left and w not in hours and w not in grade)
        ]
        parts.append(
            {
                "course": course,
                "hours": hours,
                "grade": grade,
                "notes": notes,
                "top": line[0].top,
            }
        )

    semester.rows = _group_rows(parts, header)
    return semester, y_end


ROW_START_RE = re.compile(
    rf"^\*?\s*(?:{SUBJECT_TOKEN}\s?-?\d{{4}}"
    r"|Fine Arts|Social Sci|Science with|Natural Science|U\.?\s?S\.? History|US History"
    r"|Communication|General Elective|Approved Elective|Upper[- ]Level|Elective|Humanities"
    r"|Mathematics|Statistics|Foreign Language|Major|Minor|Emphasis)",
    re.IGNORECASE,
)
CONTINUATION_RE = re.compile(r"^(or\b|OR\b|\(|&|and\b|-|[a-z])")
TRAILING_CONNECTOR_RE = re.compile(r"(?:\s|^)(?:or|OR|and|&)\s*$")
# "CHEM 2134/2130 ... OR PHYS" + next line "2124/2010 ... 4": the subject wrapped away from its number.
SPLIT_CODE_RE = re.compile(r"(?:\s|^)(?:or|OR|and|&)\s+[A-Z]{2,5}\s*$")
# "Major Support Elective (choose from list below)" + a small-print line of options, no hours.
OPTION_LIST_RE = re.compile(r"choose from|select from|from (?:the )?list", re.IGNORECASE)


def _group_rows(parts: list[dict[str, Any]], header: _Header) -> list[MapRow]:
    """Group visual lines into schedule rows.

    A row is anchored on the line carrying its hours value. Wrapped title lines are
    indented or start with a continuation token, so they join the row above. A line that
    starts at the column edge with a course code or bucket label but has no hours value
    (a few PDFs omit it from the text layer) becomes its own row with unknown hours
    rather than being merged into a neighbour.
    """
    x_start = header.x0 - 3
    anchors = [i for i, p in enumerate(parts) if p["hours"]]
    owner: dict[int, int] = {i: i for i in anchors}
    # Multi-line cells center their hours value vertically on its own line: claim the
    # course lines just above and below an hours-only anchor.
    for anchor in anchors:
        if parts[anchor]["course"]:
            continue
        y = parts[anchor]["top"]
        for i, part in enumerate(parts):
            if i in owner or not part["course"]:
                continue
            if abs(part["top"] - y) <= 12.5:
                owner[i] = anchor

    row_heads = set(anchors)
    current: int | None = None

    def row_text(head: int) -> str:
        return join_words([w for j in sorted(owner) if owner[j] == head for w in parts[j]["course"]])

    for i, part in enumerate(parts):
        if i in owner:
            current = owner[i] if part["course"] else current
            continue
        if not part["course"]:
            continue
        first = part["course"][0]
        text = join_words(part["course"])
        indented = first.x0 > x_start + 12
        next_anchor = min((a for a in anchors if a > i), default=None)
        if current is not None and TRAILING_CONNECTOR_RE.search(row_text(current)):
            owner[i] = current  # "COMM 2173 ... or" + next line "COMM 2003 ..."
        elif TRAILING_CONNECTOR_RE.search(text) and next_anchor == i + 1:
            owner[i] = next_anchor  # "STAT 2163 ... or" + next line "PSY/SOC 2053 ... 3"
        elif (
            SPLIT_CODE_RE.search(text)
            and next_anchor == i + 1
            and re.match(r"\d{4}", join_words(parts[i + 1]["course"]))
        ):
            owner[i] = next_anchor
        elif current is not None and OPTION_LIST_RE.search(row_text(current)):
            owner[i] = current  # the listed options belong to the elective row above
        elif current is not None and (indented or CONTINUATION_RE.match(text)):
            owner[i] = current
        elif not indented and ROW_START_RE.match(text):
            owner[i] = i
            row_heads.add(i)
            current = i
        elif next_anchor is not None:
            owner[i] = next_anchor
        elif current is not None:
            owner[i] = current
        else:
            owner[i] = i
            row_heads.add(i)
            current = i

    rows: list[MapRow] = []
    for head in sorted(row_heads):
        members = [parts[i] for i in sorted(owner) if owner[i] == head]
        course_words = [w for m in members for w in m["course"]]
        if not course_words:
            continue  # stray hours value with no course text (e.g. hidden form artifacts)
        note_words = [w for m in members for w in m["notes"]]
        hours_text = join_words(parts[head]["hours"][:1])
        hours_min, hours_max = parse_hours(hours_text)
        rows.append(
            MapRow(
                semester=header.number,
                text=join_words(course_words),
                hours_text=hours_text,
                hours_min=hours_min,
                hours_max=hours_max,
                grade_c=any(m["grade"] for m in members)
                or bool(re.search(r"\s#\s*$", join_words(course_words))),
                notes=join_words(note_words),
                page=header.page,
                top=parts[head]["top"],
            )
        )
    return rows


# ----------------------------------------------------------------------------- gen-ed lists

GEN_ED_HEADER_SKIP = ("university", "should", "honors", "indicates", "choose", "shaded", "note")


def _bold_phrases(words: list[Word]) -> list[tuple[str, float, float, float]]:
    """Small bold phrases (list headers): (text, x0, x1, top)."""
    phrases: list[tuple[str, float, float, float]] = []
    for line in cluster_lines([w for w in words if w.bold and w.size < 7.0], tolerance=1.5):
        current: list[Word] = []
        for word in line:
            if current and word.x0 - current[-1].x1 > 8:
                phrases.append(_phrase(current))
                current = []
            current.append(word)
        if current:
            phrases.append(_phrase(current))
    return [
        p
        for p in phrases
        if len(p[0].split()) <= 6 and not any(s in p[0].lower() for s in GEN_ED_HEADER_SKIP)
    ]


def _phrase(words: list[Word]) -> tuple[str, float, float, float]:
    return join_words(words), words[0].x0, words[-1].x1, words[0].top


def _column_starts(words: list[Word]) -> list[float]:
    starts: list[float] = []
    by_line = cluster_lines(words, tolerance=1.5)
    for line in by_line:
        for i, word in enumerate(line):
            nxt = line[i + 1].text if i + 1 < len(line) else ""
            is_code = CODE_START_RE.match(word.text) and NUMBER_RE.match(nxt)
            is_lang = re.match(r"^\d{4}$", word.text) and nxt == "from"
            if is_code or is_lang:
                starts.append(word.x0)
    clusters: list[list[float]] = []
    for x in sorted(starts):
        if clusters and x - clusters[-1][-1] <= 6:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [min(c) for c in clusters if len(c) >= 2]


def parse_gen_ed_lists(words: list[Word], page_width: float) -> dict[str, list[str]]:
    """Parse the option lists under the schedule into {list name: [item text]}."""
    headers = _bold_phrases(words)
    items = [w for w in words if not w.bold and w.size < 7.0]
    columns = _column_starts(items)
    if not headers or not columns:
        return {}
    bounds = [(x, columns[i + 1] if i + 1 < len(columns) else page_width) for i, x in enumerate(columns)]
    result: dict[str, list[str]] = {h[0]: [] for h in headers}
    for line in cluster_lines(items, tolerance=1.5):
        for col_x, col_end in bounds:
            cell = [w for w in line if col_x - 2 <= w.x0 < col_end - 2]
            if not cell:
                continue
            text = join_words(cell)
            top = cell[0].top
            applicable = [h for h in headers if h[3] < top and h[1] < col_end - 2 and h[2] > col_x - 2]
            if not applicable:
                continue
            owner = max(applicable, key=lambda h: h[3])
            result[owner[0]].append(text)
    return {name: rows for name, rows in result.items() if rows}


# ----------------------------------------------------------------------------- document


def parse_degree_map(pdf_path: Path) -> ParsedMap:
    pages, widths = _load_words(pdf_path)
    parsed = ParsedMap(path=str(pdf_path))
    all_lines = [cluster_lines(page) for page in pages]

    for lines in all_lines:
        for line in lines:
            text = join_words(line)
            match = TITLE_RE.search(text)
            if match and not parsed.title_line:
                parsed.title_line = text
                parsed.catalog_year_text = re.sub(r"\s+", "", match.group("year"))
                rest = match.group("rest").strip()
                degree = DEGREE_RE.match(rest)
                if degree:
                    parsed.degree_name = degree.group("degree").strip()
                    parsed.program_name = degree.group("name").strip()
                else:
                    parsed.program_name = rest
            rev = re.search(r"Rev\.?\s*([\d.]+)", text)
            if rev and not parsed.revision:
                parsed.revision = rev.group(1)
            if text.startswith("#Prerequisite Courses") and not parsed.prerequisite_courses_line:
                parsed.prerequisite_courses_line = text

    semesters: dict[int, ParsedSemester] = {}
    for page_index, page_words in enumerate(pages):
        headers = _find_headers(all_lines[page_index])
        _assign_column_ends(headers, widths[page_index])
        lowest_total = 0.0
        for header in headers:
            if header.number in semesters:
                parsed.warnings.append(f"duplicate semester {header.number} header")
                continue
            semester, y_end = _parse_semester(header, headers, page_words)
            semesters[header.number] = semester
            lowest_total = max(lowest_total, y_end)
        if headers:
            below = [w for w in page_words if w.top > lowest_total + 6]
            for name, rows in parse_gen_ed_lists(below, widths[page_index]).items():
                parsed.gen_ed_text.setdefault(name, []).extend(rows)
        _parse_requirements_text(parsed, all_lines[page_index])

    parsed.semesters = [semesters[k] for k in sorted(semesters)]
    parsed.gen_ed_lists = {name: expand_list_codes(rows) for name, rows in parsed.gen_ed_text.items()}
    if not parsed.semesters:
        parsed.warnings.append("no semester blocks found")
    return parsed


def _parse_requirements_text(parsed: ParsedMap, lines: list[list[Word]]) -> None:
    text = "\n".join(join_words(line) for line in lines)
    patterns: list[tuple[str, str]] = [
        ("min_upper_hours", r"Min\.?\s*hours\s*3000\s*-\s*4000\s*level\s*courses:\s*(\d+)"),
        ("min_total_hours", r"Min\.?\s*hours\s*required:?\s*(\d+)"),
        ("max_pe_hours", r"No more than\s*(\d+)\s*PE activity hours"),
    ]
    for attr, pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match and getattr(parsed, attr) is None:
            setattr(parsed, attr, int(match.group(1)))
    gpa = re.search(r"(\d\.\d{2})\+?\s*GPA", text)
    if gpa and parsed.gpa_min is None:
        parsed.gpa_min = float(gpa.group(1))
    for match in re.finditer(
        r"((?:Approved|General|Upper[- ]Level|Major|Directed)?\s*Electives?:[^\n]{0,80}?hours?"
        r"(?:\s*\([^)]*\))?)",
        text,
        re.IGNORECASE,
    ):
        note = match.group(1).strip()
        if note not in parsed.footnotes:
            parsed.footnotes.append(note)


# ----------------------------------------------------------------------------- code parsing

LANG_RE = re.compile(r"^(\d{4})\s+from\s+(.+)$")


def expand_list_codes(rows: list[str]) -> list[str]:
    """Course codes named in gen-ed list rows (cross-lists and language lists expanded)."""
    codes: list[str] = []
    for row in rows:
        lang = LANG_RE.match(row)
        if lang:
            number = lang.group(1)
            subjects = re.findall(r"\b([A-Z]{2,5})\b", lang.group(2))
            codes.extend(f"{s} {number}" for s in subjects)
            continue
        codes.extend(leading_codes(row))
    seen: set[str] = set()
    unique = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            unique.append(code)
    return unique


def leading_codes(text: str) -> list[str]:
    """Codes at the start of a list item: 'ENGL/JOUR 2173 Intro...' -> ENGL 2173, JOUR 2173."""
    match = re.match(rf"^\*?\s*({SUBJECT_TOKEN})\s?(\d{{4}})", text.strip())
    if not match:
        return []
    return [f"{subject} {match.group(2)}" for subject in match.group(1).split("/")]
