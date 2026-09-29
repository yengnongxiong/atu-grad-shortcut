"""PRD §3 personas: each demo profile tells the story it claims (G5, A10)."""

from __future__ import annotations

import json
from typing import Any

from shortcut.data.loader import load_dataset
from shortcut.planner.service import plan_detailed
from shortcut.planner.whatif import run_whatif
from shortcut.schemas.plan import PlanRequest, WhatIfRequest


def persona(persona_id: str) -> dict[str, Any]:
    return load_dataset().personas[persona_id]


def test_every_persona_is_feasible_and_template_is_excluded() -> None:
    dataset = load_dataset()
    assert {"p1", "p2", "p3", "p4"} <= set(dataset.personas)
    assert "my-path" not in dataset.personas
    template = json.loads((dataset.data_dir / "personas" / "my-path.template.json").read_text())
    PlanRequest.model_validate(template["request"])  # the template itself is a valid request
    for persona_id, record in dataset.personas.items():
        response = plan_detailed(dataset, PlanRequest.model_validate(record["request"])).response
        assert response.feasible, persona_id
        assert record["sample_data"] or persona_id == "p1"


def test_p3_off_track_junior_is_behind_and_what_if_finds_recovery() -> None:
    request = PlanRequest.model_validate(persona("p3")["request"])
    dataset = load_dataset()
    response = plan_detailed(dataset, request).response
    assert response.program.trust_tier == "cross_checked"
    assert (response.terms_sooner_than_map or 0) < 0  # the F put the student behind the map
    retake = next(c for t in response.terms for c in t.courses if c.code == "ACCT 3003")
    assert next(t for t in response.terms if retake in t.courses).season == "FA"  # fall-only
    assert response.pace_note and "ACCT 3003" in response.pace_note
    switch = run_whatif(
        dataset,
        WhatIfRequest.model_validate(
            {"plan": request.model_dump(), "event": {"type": "change_major", "program_id": "finance-2026-27"}}
        ),
    )
    assert switch.terms_later is not None and switch.terms_later < 0  # a real recovery option


def test_p4_no_shortcut_explains_why_nothing_helps() -> None:
    request = PlanRequest.model_validate(persona("p4")["request"])
    response = plan_detailed(load_dataset(), request).response
    assert response.program.trust_tier == "cross_checked"
    enabled = [lever for lever in response.levers if lever.enabled]
    assert len(enabled) >= 4
    assert all(lever.terms_saved == 0 for lever in enabled)
    assert response.terms_sooner_than_standard == 0
    assert response.pace_note and response.pace_note.startswith("None of the levers you turned on")
    assert any(w.id == "admission-gate" or "Admission gate" in w.message for w in response.warnings)
