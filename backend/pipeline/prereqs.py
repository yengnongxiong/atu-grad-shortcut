"""Prerequisite parsing: Banner prerequisite tables, catalog description text, map notes.

Trees are plain dicts so they serialize straight into courses.json:

    {"type": "and" | "or", "items": [...]}
    {"type": "course", "code": "COMS 2213", "min_grade": "C" | "D" | null}
    {"type": "test", "test": "ACT Math", "min_score": 26}
    {"type": "standing", "standing": "JR"}          # SO / JR / SR
    {"type": "unparsed", "text": "consent of instructor"}
"""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass, field
from typing import Any

from pipeline.codes import ACTS_CODE_RE, extract_codes, strip_acts

Tree = dict[str, Any]

# ----------------------------------------------------------------------------- tree helpers


def normalize_grade(grade: str) -> str | None:
    """Banner grades: 'C*' -> 'C'; 'P'/'D'/blank mean any passing grade."""
    grade = grade.strip().rstrip("*").upper()
    return grade if grade in ("A", "B", "C") else ("D" if grade == "D" else None)


def course(code: str, min_grade: str | None = None) -> Tree:
    return {"type": "course", "code": code, "min_grade": min_grade}


def combine(kind: str, items: list[Tree]) -> Tree | None:
    flat: list[Tree] = []
    for item in items:
        if item["type"] == kind:
            flat.extend(item["items"])
        else:
            flat.append(item)
    unique: list[Tree] = []
    for item in flat:
        if item not in unique:
            unique.append(item)
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return {"type": kind, "items": unique}


def tree_codes(tree: Tree | None) -> list[str]:
    if tree is None:
        return []
    if tree["type"] == "course":
        return [tree["code"]]
    if tree["type"] in ("and", "or"):
        return [c for item in tree["items"] for c in tree_codes(item)]
    return []


def tree_has(tree: Tree | None, node_type: str) -> bool:
    if tree is None:
        return False
    if tree["type"] == node_type:
        return True
    return any(tree_has(i, node_type) for i in tree.get("items", []))


# ----------------------------------------------------------------------------- Banner tables

CELL_RE = re.compile(r"<td>(.*?)</td>", re.S)
ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.S)


@dataclass
class ParseResult:
    tree: Tree | None
    confidence: str  # high | medium | low
    warnings: list[str] = field(default_factory=list)


def parse_banner_prereq_html(prereq_html: str, subject_codes: dict[str, str]) -> ParseResult:
    """Parse Banner's flat And/Or/parenthesis rows into a tree (AND binds tighter than OR)."""
    tokens: list[Any] = []
    warnings: list[str] = []
    for row in ROW_RE.findall(prereq_html):
        cells = [htmllib.unescape(c).strip() for c in CELL_RE.findall(row)]
        if len(cells) < 9:
            continue
        connector, lparen, test, score, subject_desc, number, _level, grade, rparen = cells[:9]
        if connector:
            tokens.append(connector.upper())
        tokens.extend("(" for _ in range(lparen.count("(")))
        if test:
            try:
                tokens.append({"type": "test", "test": test, "min_score": float(score)})
            except ValueError:
                tokens.append({"type": "unparsed", "text": f"{test} {score}".strip()})
                warnings.append(f"unparsed test score: {test} {score}")
        elif subject_desc and number:
            code = subject_codes.get(subject_desc)
            if code is None:
                warnings.append(f"unknown subject description: {subject_desc}")
                tokens.append({"type": "unparsed", "text": f"{subject_desc} {number}"})
            else:
                tokens.append(course(f"{code} {number}", normalize_grade(grade)))
        tokens.extend(")" for _ in range(rparen.count(")")))
    if not tokens:
        return ParseResult(None, "high")
    mixed = _has_unparenthesized_mix(tokens)
    try:
        tree, rest = _parse_or(tokens, 0)
        if rest != len(tokens):
            raise ValueError("trailing tokens")
    except (ValueError, IndexError) as exc:
        codes = [t for t in tokens if isinstance(t, dict)]
        warnings.append(f"prerequisite table parse failed ({exc}); treating items as AND")
        return ParseResult(combine("and", codes), "low", warnings)
    if mixed:
        warnings.append("And/Or mixed without parentheses; read with AND binding tighter")
    return ParseResult(tree, "medium" if mixed else "high", warnings)


def _has_unparenthesized_mix(tokens: list[Any]) -> bool:
    depth_ops: dict[int, set[str]] = {}
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif token in ("AND", "OR"):
            depth_ops.setdefault(depth, set()).add(token)
    return any(len(ops) > 1 for ops in depth_ops.values())


def _parse_or(tokens: list[Any], i: int) -> tuple[Tree, int]:
    left, i = _parse_and(tokens, i)
    items = [left]
    while i < len(tokens) and tokens[i] == "OR":
        right, i = _parse_and(tokens, i + 1)
        items.append(right)
    tree = combine("or", items)
    assert tree is not None
    return tree, i


def _parse_and(tokens: list[Any], i: int) -> tuple[Tree, int]:
    left, i = _parse_atom(tokens, i)
    items = [left]
    while i < len(tokens) and tokens[i] == "AND":
        right, i = _parse_atom(tokens, i + 1)
        items.append(right)
    tree = combine("and", items)
    assert tree is not None
    return tree, i


def _parse_atom(tokens: list[Any], i: int) -> tuple[Tree, int]:
    token = tokens[i]
    if token == "(":
        tree, j = _parse_or(tokens, i + 1)
        if j >= len(tokens) or tokens[j] != ")":
            raise ValueError("unbalanced parenthesis")
        return tree, j + 1
    if isinstance(token, dict):
        return token, i + 1
    raise ValueError(f"unexpected token {token!r}")


def parse_banner_coreq_html(coreq_html: str, subject_codes: dict[str, str]) -> list[str]:
    codes: list[str] = []
    for row in ROW_RE.findall(coreq_html):
        cells = [htmllib.unescape(c).strip() for c in CELL_RE.findall(row)]
        if len(cells) >= 2 and cells[0] in subject_codes and re.fullmatch(r"\d{4}", cells[1]):
            codes.append(f"{subject_codes[cells[0]]} {cells[1]}")
    return codes


# ----------------------------------------------------------------------------- descriptions

SEASON_WORDS = {"fall": "FA", "spring": "SP", "summer": "SU", "winter": "WI", "intersession": "WI"}


@dataclass
class DescriptionFacts:
    text: str
    offered: list[str] | None  # e.g. ["FA"], None when the description is silent
    offered_text: str
    prereq_text: str
    coreq_text: str
    acts_equivalent: str | None
    pass_fail: bool
    standing: str | None
    standing_text: str


def description_text(description_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", description_html)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", htmllib.unescape(text)).strip()


def parse_description(description_html: str) -> DescriptionFacts:
    text = description_text(description_html)
    flat = re.sub(r"\s+", " ", text)
    offered: list[str] | None = None
    offered_text = ""
    m = re.search(r"Offered:\s*([^.]+)\.", flat)
    if m:
        offered_text = m.group(1).strip()
        seasons = [
            SEASON_WORDS[w] for w in re.findall(r"[A-Za-z]+", offered_text.lower()) if w in SEASON_WORDS
        ]
        offered = sorted(set(seasons), key=["FA", "WI", "SP", "SU"].index) or None
    prereq_text = _sentence_after(flat, r"Pre-?requisites?\s*:")
    coreq_text = _sentence_after(flat, r"Co-?requisites?\s*:")
    acts = ACTS_CODE_RE.search(flat)
    standing, standing_text = parse_standing(prereq_text)
    return DescriptionFacts(
        text=flat,
        offered=offered,
        offered_text=offered_text,
        prereq_text=prereq_text,
        coreq_text=coreq_text,
        acts_equivalent=f"{acts.group(1).upper()} {acts.group(2)}" if acts else None,
        pass_fail=bool(re.search(r"pass/fail|pass-fail", flat, re.IGNORECASE)),
        standing=standing,
        standing_text=standing_text,
    )


def _sentence_after(text: str, label: str) -> str:
    m = re.search(label + r"\s*(.+?)(?:\.\s+(?=[A-Z])|\.$|$)", text)
    return m.group(1).strip() if m else ""


STANDING_RE = re.compile(r"\b(sophomore|junior|senior)\s+(?:standing|classification|status)", re.I)


def parse_standing(text: str) -> tuple[str | None, str]:
    m = STANDING_RE.search(text)
    if not m:
        return None, ""
    return {"sophomore": "SO", "junior": "JR", "senior": "SR"}[m.group(1).lower()], m.group(0)


# ----------------------------------------------------------------------------- free text


def parse_prereq_text(text: str, math_ladder: list[str]) -> ParseResult:
    """Parse map-note / description prerequisite text into a tree.

    Handles the patterns that appear on ATU degree maps and catalog descriptions:
    'C> in X', 'X with a grade of C', 'X & Y', 'X and Y', 'X or Y', 'X/Y', bare numbers
    after a subject ('COMS 2213 & 2223'), 'MATH 1113 or higher' (math ladder),
    'Math ACT >26' / 'ACT math score of 26 or higher', and class standing. Anything with
    leftover words (e.g. 'consent of instructor') is kept but lowers confidence.
    """
    warnings: list[str] = []
    raw = strip_acts(text).strip().rstrip(".")
    if not raw:
        return ParseResult(None, "high")
    standing, standing_text = parse_standing(raw)
    working = raw.replace(standing_text, " ") if standing_text else raw
    working = re.sub(
        r",?\s*(or\s+)?(with\s+)?(the\s+)?consent of (the )?instructor", " ", working, flags=re.I
    )
    working = re.sub(r"\bor equivalent\b", " ", working, flags=re.I)
    working = GRADE_RE.sub(" C> ", working)
    working = re.sub(r"(\d{4})\s+or\s+(higher|above)", r"\1 +HIGHER", working, flags=re.I)
    working = re.sub(r"(\d{2})\s+or\s+(higher|above)", r"\1", working, flags=re.I)

    clauses = re.split(r"\s*(?:;|,?\s+and\s+|\s*&\s*|,\s+(?=[A-Z]{2,5}\s?\d{4}))\s*", working)
    and_items: list[Tree] = []
    leftover_words: list[str] = []
    last_subject: str | None = None
    for clause in clauses:
        clause = clause.strip(" ,")
        if not clause:
            continue
        min_grade = "C" if "C>" in clause else None
        options: list[Tree] = []
        for part in re.split(r",?\s+or\s+|,\s+|/(?=\d{4}\b)", clause):
            node, last_subject, leftovers = _parse_atom_text(part, last_subject, math_ladder, min_grade)
            if node is not None:
                options.append(node)
            leftover_words.extend(leftovers)
        if options:
            merged = combine("or", options)
            if merged is not None:
                and_items.append(merged)
    if standing:
        and_items.append({"type": "standing", "standing": standing})
    tree = combine("and", and_items)
    noise = {
        "in",
        "a",
        "grade",
        "of",
        "c",
        "or",
        "better",
        "above",
        "higher",
        "and",
        "the",
        "with",
        "minimum",
        "min",
        "prereq",
        "prereqs",
        "prerequisite",
        "prerequisites",
        "course",
        "courses",
        "both",
        "completion",
        "completed",
        "credit",
        "for",
        "score",
        "is",
        "required",
        "equivalent",
        "c>",
        "d",
        "at",
        "least",
        "courses:",
        "prereq:",
        "coms",
        "major",
        "majors",
        "+higher",
        "either",
        "an",
        "on",
        "placement",
        "each",
        "all",
        "must",
    }
    meaningful = [w for w in leftover_words if w.lower().strip(".,:;()") not in noise]
    confidence = "high"
    if meaningful:
        confidence = "low" if tree is None else "medium"
        warnings.append(f"unparsed prerequisite words: {' '.join(meaningful)}")
    if tree is None and meaningful:
        tree = {"type": "unparsed", "text": raw}
    return ParseResult(tree, confidence, warnings)


GRADE_RE = re.compile(
    r"(?:\bC\s*>|\bC\s+or\s+(?:better|above|higher)|(?:with\s+)?(?:a\s+)?(?:minimum\s+)?grade\s+of\s+\"?C\"?"
    r"(?:\s+or\s+(?:better|above|higher))?)",
    re.I,
)
ACT_RE = re.compile(r"(?:math\s*ACT|ACT\s*math)[^0-9]{0,30}?(>|>=|≥)?\s*(\d{2})(\s*or\s*higher)?", re.I)


def _parse_atom_text(
    part: str, last_subject: str | None, math_ladder: list[str], min_grade: str | None
) -> tuple[Tree | None, str | None, list[str]]:
    part = part.strip()
    act = ACT_RE.search(part)
    if act:
        score = int(act.group(2))
        if act.group(1) == ">":
            score += 1
        return {"type": "test", "test": "ACT Math", "min_score": score}, last_subject, []
    codes = extract_codes(part)
    if not codes and last_subject:
        bare = re.fullmatch(r"(?:C>\s*(?:in\s*)?)?(\d{4})(\s*\+HIGHER)?", part.strip(), re.I)
        if bare:
            codes = [f"{last_subject} {bare.group(1)}"]
    if not codes:
        return None, last_subject, re.findall(r"[A-Za-z>+]+\S*", part)
    last_subject = codes[-1].split(" ")[0]
    if "+HIGHER" in part and codes[0] in math_ladder:
        start = math_ladder.index(codes[0])
        ladder = [course(code, min_grade) for code in math_ladder[start:]]
        return combine("or", ladder), last_subject, []
    nodes = [course(code, min_grade) for code in codes]
    return combine("or", nodes), last_subject, []
