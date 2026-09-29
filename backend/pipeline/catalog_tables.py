"""AP, IB, and CLEP credit tables from ATU catalog snapshots (PRD v1.1 §3.1, D23).

catalog.atu.edu is behind a bot challenge (D5), so each table was saved once from a regular
browser session into data/raw/catalog/<program>.json as verbatim cell text. This module turns
the "Credit Awarded" text into award options using exact course codes only:

- "MATH 2914 & MATH 2924"            -> [["MATH 2914", "MATH 2924"]]
- "BIOL 1004 or ENVS 1004"           -> [["BIOL 1004"], ["ENVS 1004"]]
- "A, B, & C, or D & E"              -> [["A", "B", "C"], ["D", "E"]]
- "6 hours from the following courses: A, B, C, D" -> every combination worth 6 hours
- "3 hours General Education Humanities" -> no course; kept as generic_credit, never guessed
"""

from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path
from typing import Any

CODE_RE = re.compile(r"\b([A-Z]{2,4}) (\d{4})\b")
GENERIC_RE = re.compile(r"\d+ hours General [A-Za-z ]+")
FROM_LIST_RE = re.compile(r"^(\d+) hours from the following courses:\s*(.+)$")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", " ")).strip("-")


def course_hours(code: str) -> int:
    """ATU course numbers end in their credit hours (COMS 1013 is 3 hours)."""
    return int(code[-1])


def _codes(text: str) -> list[str]:
    return [f"{subject} {number}" for subject, number in CODE_RE.findall(text)]


def parse_credit(text: str) -> tuple[list[list[str]], str | None]:
    """(award options, generic credit text) for one "Credit Awarded" cell."""
    from_list = FROM_LIST_RE.match(text)
    if from_list:
        hours, listed = int(from_list.group(1)), _codes(from_list.group(2))
        options = [
            list(combo)
            for size in range(1, len(listed) + 1)
            for combo in combinations(listed, size)
            if sum(course_hours(c) for c in combo) == hours
        ]
        return options, None
    generic = GENERIC_RE.search(text)
    options = [codes for part in re.split(r",? or ", text) if (codes := _codes(part))]
    return options, generic.group(0) if generic else None


def parse_exam_table(snapshot: dict[str, Any], program: str) -> list[dict[str, Any]]:
    """Every data row of a snapshot's first table as an exam equivalency."""
    _header, *body = snapshot["tables"][0]
    source = {"title": snapshot["title"], "url": snapshot["url"], "captured_at": snapshot["captured_at"]}
    out: list[dict[str, Any]] = []
    for exam, score, credit in body:
        awards, generic = parse_credit(credit)
        out.append(
            {
                "id": f"{program.lower()}-{slug(exam)}-{int(score)}",
                "program": program,
                "exam": exam,
                "min_score": int(score),
                "awards": awards,
                "generic_credit": generic,
                "credit_text": credit,
                "source": source,
                "confidence": "documented",
            }
        )
    return out


def snapshot_sources(catalog_dir: Path) -> list[dict[str, str]]:
    """Every catalog page saved under `catalog_dir`, with its edition and capture date."""
    sources: list[dict[str, str]] = []
    for path in sorted(catalog_dir.glob("*.json")):
        snapshot = json.loads(path.read_text())
        for page in snapshot.get("pages") or [snapshot]:
            sources.append(
                {
                    "title": page["title"].split(" | ")[0],
                    "url": page["url"],
                    "catalog_edition": snapshot["catalog_edition"],
                    "captured_at": snapshot["captured_at"],
                }
            )
    return sources
