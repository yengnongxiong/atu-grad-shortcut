"""Academic terms. Order within an academic year: FA < WI < SP < SU (CLAUDE.md).

A term id is "<year><season>", where year is the calendar year the term starts in:
2026FA (Aug-Dec 2026), 2026WI (Dec 2026-Jan 2027), 2027SP, 2027SU.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import total_ordering

SEASONS = ("FA", "WI", "SP", "SU")
REGULAR = ("FA", "SP")
SEASON_NAMES = {"FA": "Fall", "WI": "Winter", "SP": "Spring", "SU": "Summer"}
TERM_ID_RE = re.compile(r"^(\d{4})(FA|WI|SP|SU)$")


@total_ordering
@dataclass(frozen=True)
class Term:
    year: int
    season: str

    @classmethod
    def parse(cls, term_id: str) -> Term:
        match = TERM_ID_RE.match(term_id.strip().upper())
        if not match:
            raise ValueError(f"invalid term id {term_id!r}; expected e.g. 2026FA")
        return cls(int(match.group(1)), match.group(2))

    @property
    def id(self) -> str:
        return f"{self.year}{self.season}"

    @property
    def academic_year(self) -> int:
        """Fall year of the academic year this term belongs to."""
        return self.year if self.season in ("FA", "WI") else self.year - 1

    @property
    def order_key(self) -> tuple[int, int]:
        return (self.academic_year, SEASONS.index(self.season))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Term):
            return NotImplemented
        return self.order_key < other.order_key

    @property
    def is_regular(self) -> bool:
        return self.season in REGULAR

    @property
    def label(self) -> str:
        if self.season == "WI":
            return f"Winter {self.year}–{str(self.year + 1)[2:]}"
        return f"{SEASON_NAMES[self.season]} {self.year}"

    def end_label(self, end_months: dict[str, str]) -> str:
        """Graduation-style date label: Spring 2030 -> 'May 2030'; Winter 2026 -> 'Jan 2027'."""
        month = end_months[self.season][:3]
        year = self.year + 1 if self.season == "WI" else self.year
        return f"{month} {year}"

    def next(self) -> Term:
        index = SEASONS.index(self.season)
        season = SEASONS[(index + 1) % 4]
        if self.season == "FA":  # FA -> WI keeps the start year
            return Term(self.year, season)
        if self.season == "WI":  # WI 2026 -> SP 2027
            return Term(self.year + 1, season)
        if self.season == "SP":
            return Term(self.year, season)
        return Term(self.year, "FA")  # SU 2027 -> FA 2027

    def next_regular(self) -> Term:
        term = self.next()
        while not term.is_regular:
            term = term.next()
        return term

    @property
    def semester_position(self) -> float:
        """Position on a half-semester grid: each regular term is 1.0, WI/SU sit halfway."""
        base = self.academic_year * 2
        return {"FA": base, "WI": base + 0.5, "SP": base + 1, "SU": base + 1.5}[self.season]


def term_sequence(start: Term, regular_count: int) -> list[Term]:
    """All terms from `start` through the `regular_count`-th regular term."""
    terms: list[Term] = []
    term = start
    regular = 0
    while True:
        terms.append(term)
        if term.is_regular:
            regular += 1
            if regular >= regular_count:
                return terms
        term = term.next()


def nth_regular_after(first: Term, n: int) -> Term:
    """The n-th regular semester counted from `first` (n=1 -> first regular term)."""
    term = first if first.is_regular else first.next_regular()
    for _ in range(n - 1):
        term = term.next_regular()
    return term


def terms_between(a: Term, b: Term) -> float:
    """Signed distance in regular semesters (WI/SU count half)."""
    return b.semester_position - a.semester_position
