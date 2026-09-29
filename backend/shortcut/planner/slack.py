"""Critical path and prerequisite slack (PRD §9).

After solving, run a calendar-aware backward pass over the prerequisite edges each course
actually used in the plan, holding the graduation term fixed. Slack is the number of regular
semesters a course could slip without delaying graduation; it ignores hour caps (the UI
labels it "prerequisite slack"). The delay action in the UI uses a true re-solve instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from shortcut.planner.model import Placement, Slot, atu_slot_ok, coreq_groups, simplify
from shortcut.planner.profile import Item, StudentState


@dataclass
class Edge:
    source: str
    target: str
    kind: str  # prereq | coreq


def used_edges(items: Sequence[Item], state: StudentState, placements: dict[str, Placement]) -> list[Edge]:
    """Prerequisite edges the plan relies on (for OR groups: the option completed first)."""
    planned = {i.code: i.id for i in items if i.code}
    edges: list[Edge] = []
    for item in items:
        placement = placements.get(item.id)
        if placement is None:
            continue
        tree = simplify(item.prereq, state, planned)
        for dep in _chosen_leaves(tree, placement.term_index, placements):
            edges.append(Edge(dep, item.id, "prereq"))
        for group in coreq_groups(item, state, planned):
            placed = [dep for dep in group if dep in placements]
            if placed:  # the alternative taken first satisfies the group
                dep_id = min(placed, key=lambda dep: placements[dep].term_index)
                edges.append(Edge(dep_id, item.id, "coreq"))
    return edges


def _chosen_leaves(node: dict[str, Any] | bool, term: int, placements: dict[str, Placement]) -> list[str]:
    if not isinstance(node, dict):
        return []
    if node["type"] == "item":
        return [node["id"]]
    if node["type"] == "and":
        return [leaf for child in node["items"] for leaf in _chosen_leaves(child, term, placements)]
    satisfied = [
        child
        for child in node["items"]
        if all(
            placements.get(leaf) is not None and placements[leaf].term_index < term
            for leaf in _chosen_leaves(child, term, placements)
        )
    ]
    if not satisfied:
        return []
    best = min(
        satisfied,
        key=lambda child: max(
            (placements[leaf].term_index for leaf in _chosen_leaves(child, term, placements)),
            default=-1,
        ),
    )
    return _chosen_leaves(best, term, placements)


def latest_indices(
    items: Sequence[Item],
    placements: dict[str, Placement],
    edges: list[Edge],
    slots: Sequence[Slot],
    graduation_index: int,
    mode: str,
) -> dict[str, int]:
    """Latest term each item could occupy (offering-aware, ignoring hour caps)."""
    by_id = {i.id: i for i in items}

    def allowed(item: Item, index: int) -> bool:
        slot = slots[index]
        if slot.cap_max <= 0 and item.hours > 0:
            return False
        placement = placements[item.id]
        if placement.transfer:
            return slot.transfer_allowed
        return atu_slot_ok(slot, item, mode)

    successors: dict[str, list[Edge]] = {}
    for edge in edges:
        successors.setdefault(edge.source, []).append(edge)
    latest: dict[str, int] = {}

    def compute(item_id: str, stack: frozenset[str] = frozenset()) -> int:
        if item_id in latest:
            return latest[item_id]
        item = by_id[item_id]
        bound = graduation_index
        for edge in successors.get(item_id, []):
            if edge.target in stack or edge.target not in placements:
                continue
            target_latest = compute(edge.target, stack | {item_id})
            bound = min(bound, target_latest - (1 if edge.kind == "prereq" else 0))
        placed = placements[item_id].term_index
        value = placed
        for index in range(bound, placed - 1, -1):
            if allowed(item, index):
                value = index
                break
        latest[item_id] = max(value, placed)
        return latest[item_id]

    for item_id in placements:
        compute(item_id)
    return latest


def regular_semesters_between(slots: Sequence[Slot], start: int, end: int) -> float:
    """Slack measured in regular semesters (winter/summer count as half)."""
    if end <= start:
        return 0.0
    return slots[end].term.semester_position - slots[start].term.semester_position


def compute_slack(
    items: Sequence[Item],
    state: StudentState,
    placements: dict[str, Placement],
    slots: Sequence[Slot],
    graduation_index: int,
    mode: str,
) -> tuple[dict[str, float], list[Edge]]:
    edges = used_edges(items, state, placements)
    latest = latest_indices(items, placements, edges, slots, graduation_index, mode)
    slack = {
        item_id: regular_semesters_between(slots, placements[item_id].term_index, latest[item_id])
        for item_id in placements
    }
    return slack, edges
