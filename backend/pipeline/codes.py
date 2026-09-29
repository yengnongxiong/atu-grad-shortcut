"""Course-code extraction shared by the map parser, program builder, and prereq parser."""

from __future__ import annotations

import re

ACTS_PAREN_RE = re.compile(r"\(\s*ACTS\s*[-=:]?[^)]*\)", re.IGNORECASE)
ACTS_INLINE_RE = re.compile(r"ACTS\s*[-=:]\s*[A-Z]{2,5}\s?\d{4}", re.IGNORECASE)
ACTS_CODE_RE = re.compile(r"ACTS\s*(?:Common Course)?\s*[-=:]?\s*([A-Z]{2,5})\s?(\d{4})", re.IGNORECASE)

# SUBJ 1234, SUBJ-1234, SUBJ1234, SUBJ/SUBJ 1234, SUBJ 1234/1235, SUBJ 1234/SUBJ 1235
CODE_GROUP_RE = re.compile(
    r"(?<![A-Za-z])(?P<subjects>[A-Z]{2,5}(?:/[A-Z]{2,5})*)\s?[-–]?\s?(?P<number>\d{4})"
    r"(?P<tail>(?:\s?/\s?\d{4}(?!\d))*)"
)

NOT_SUBJECTS = frozenset({"ACT", "ACTS", "GPA", "SAT", "AND", "OR", "THE", "FALL", "ONLY", "HRS"})


def strip_acts(text: str) -> str:
    """Remove ACTS cross-references so they aren't mistaken for ATU course codes."""
    text = ACTS_PAREN_RE.sub(" ", text)
    return ACTS_INLINE_RE.sub(" ", text)


def acts_codes(text: str) -> list[str]:
    return [f"{m.group(1).upper()} {m.group(2)}" for m in ACTS_CODE_RE.finditer(text)]


def extract_codes(text: str) -> list[str]:
    """All ATU course codes in reading order, cross-lists and slash numbers expanded."""
    codes: list[str] = []
    for match in CODE_GROUP_RE.finditer(strip_acts(text)):
        subjects = [s for s in match.group("subjects").split("/") if s not in NOT_SUBJECTS]
        if not subjects:
            continue
        numbers = [match.group("number"), *re.findall(r"\d{4}", match.group("tail") or "")]
        for subject in subjects:
            for number in numbers:
                code = f"{subject} {number}"
                if code not in codes:
                    codes.append(code)
    return codes


def code_groups(text: str) -> list[list[str]]:
    """Codes grouped by the token they came from (useful to spot lecture/lab pairs)."""
    groups: list[list[str]] = []
    for match in CODE_GROUP_RE.finditer(strip_acts(text)):
        subjects = [s for s in match.group("subjects").split("/") if s not in NOT_SUBJECTS]
        numbers = [match.group("number"), *re.findall(r"\d{4}", match.group("tail") or "")]
        group = [f"{s} {n}" for s in subjects for n in numbers]
        if group:
            groups.append(group)
    return groups


def subject_of(code: str) -> str:
    return code.split(" ", 1)[0]


def number_of(code: str) -> str:
    return code.split(" ", 1)[1]


def level_of(code: str) -> int:
    number = number_of(code)
    return int(number[0]) * 1000 if number[:1].isdigit() else 0
