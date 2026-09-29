"""Load processed JSON once at startup (no database; PRD §11)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from shortcut.planner.policies import Policies

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


@dataclass(frozen=True)
class Dataset:
    programs: dict[str, dict[str, Any]]
    courses: dict[str, dict[str, Any]]
    exams: dict[str, dict[str, Any]]
    policies: Policies
    meta: dict[str, Any]
    personas: dict[str, dict[str, Any]]
    data_dir: Path
    # title + hours for every ATU catalog course (programs' courses live in `courses`)
    course_index: dict[str, dict[str, Any]] = field(default_factory=dict)

    def program(self, program_id: str) -> dict[str, Any]:
        try:
            return self.programs[program_id]
        except KeyError as exc:
            raise KeyError(f"unknown program {program_id!r}") from exc

    def equivalencies(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for table in self.exams.values():
            rows.extend(table.get("equivalencies", []))
        return rows


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def data_dir() -> Path:
    return Path(os.environ.get("SHORTCUT_DATA_DIR", DEFAULT_DATA_DIR))


@lru_cache(maxsize=4)
def load_dataset(root: Path | None = None) -> Dataset:
    base = root or data_dir()
    processed = base / "processed"
    programs = {path.stem: _read(path) for path in sorted((processed / "programs").glob("*.json"))}
    exams = {path.stem: _read(path) for path in sorted((processed / "exams").glob("*.json"))}
    personas: dict[str, dict[str, Any]] = {}
    personas_dir = base / "personas"
    if personas_dir.exists():
        for path in sorted(personas_dir.glob("*.json")):
            if path.name.endswith(".template.json"):
                continue
            persona = _read(path)
            personas[str(persona.get("id", path.stem))] = persona
    index_path = processed / "course_index.json"
    return Dataset(
        programs=programs,
        courses=_read(processed / "courses.json"),
        exams=exams,
        policies=Policies(_read(processed / "policies.json")),
        meta=_read(processed / "meta.json"),
        personas=personas,
        data_dir=base,
        course_index=_read(index_path) if index_path.exists() else {},
    )
