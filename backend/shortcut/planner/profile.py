"""Student state: credits, requirement matching, and the remaining schedulable items."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shortcut.data.loader import Dataset
from shortcut.planner.policies import Policies
from shortcut.schemas.plan import StudentProfile

PASSING = {"A", "B", "C", "D", "P"}
GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, "P": 1, "F": 0, "W": -1}
CONF_RANK = {"documented": 4, "derived": 3, "conflicting": 2, "assumed": 2, "unknown": 0}
SEASONS = ("FA", "WI", "SP", "SU")

Tree = dict[str, Any]


# ----------------------------------------------------------------------------- credits


@dataclass
class Credit:
    code: str
    title: str
    hours: float
    source: str  # atu | transfer | exam | planned_exam | in_progress | assumed_pass
    grade: str | None  # None = credit by exam (no grade)
    level: int
    exam_id: str | None = None
    retaken: bool = False  # a retake is planned (grade too low for a requirement); hours count once

    @property
    def earned(self) -> bool:
        return self.grade is None or self.grade in PASSING

    @property
    def counts_toward_degree(self) -> bool:
        return self.earned and not self.retaken

    def meets(self, min_grade: str | None) -> bool:
        if not self.earned:
            return False
        if min_grade is None or self.grade is None or self.grade == "P":
            return True
        return GRADE_RANK[self.grade] >= GRADE_RANK[min_grade]

    @property
    def at_atu(self) -> bool:
        return self.source in ("atu", "in_progress", "assumed_pass")

    @property
    def by_exam(self) -> bool:
        return self.source in ("exam", "planned_exam")


@dataclass
class ExamAward:
    exam_id: str
    exam: str
    options: list[list[str]]
    source: str  # exam | planned_exam


@dataclass
class StudentState:
    credits: dict[str, Credit]
    failed: set[str]
    math_act: int | None
    exam_awards: list[ExamAward]
    notes: list[str] = field(default_factory=list)

    def has(self, code: str, min_grade: str | None = None) -> bool:
        credit = self.credits.get(code)
        return credit is not None and credit.meets(min_grade)

    @property
    def earned_hours(self) -> float:
        """Hours toward the degree (a course being retaken counts once, through the retake)."""
        return sum(c.hours for c in self.credits.values() if c.counts_toward_degree)

    @property
    def atu_hours(self) -> float:
        return sum(c.hours for c in self.credits.values() if c.counts_toward_degree and c.at_atu)

    @property
    def exam_hours(self) -> float:
        return sum(c.hours for c in self.credits.values() if c.counts_toward_degree and c.by_exam)

    def standing_hours(self, count_exam_transfer: bool) -> float:
        """Earned hours for class standing: every passed attempt counts until it is replaced."""
        return sum(c.hours for c in self.credits.values() if c.earned and (count_exam_transfer or c.at_atu))


def course_hours(dataset: Dataset, code: str, fallback: float = 3.0) -> float:
    course = dataset.courses.get(code)
    if course and course.get("hours") is not None:
        return float(course["hours"])
    return fallback


def course_title(dataset: Dataset, code: str) -> str:
    course = dataset.courses.get(code)
    return str(course["title"]) if course else code


def level_of(code: str) -> int:
    number = code.split(" ")[-1]
    return int(number[0]) * 1000 if number[:1].isdigit() else 0


def build_state(
    dataset: Dataset,
    profile: StudentProfile,
    planned_exam_ids: list[str],
    extra_credits: list[Credit] | None = None,
) -> StudentState:
    credits: dict[str, Credit] = {}
    failed: set[str] = set()

    def add(credit: Credit) -> None:
        current = credits.get(credit.code)
        if current is None or _better(credit, current):
            credits[credit.code] = credit

    for done in profile.completed:
        credit = Credit(
            code=done.code,
            title=course_title(dataset, done.code),
            hours=course_hours(dataset, done.code),
            source=done.source,
            grade=done.grade,
            level=level_of(done.code),
        )
        if credit.earned:
            add(credit)
        else:
            failed.add(done.code)
    for code in profile.in_progress:
        normalized = " ".join(code.upper().split())
        add(
            Credit(
                normalized,
                course_title(dataset, normalized),
                course_hours(dataset, normalized),
                "in_progress",
                "C",
                level_of(normalized),
            )
        )
    for credit in extra_credits or []:
        add(credit)
    failed -= {c for c, cr in credits.items() if cr.earned}

    awards = exam_awards(dataset, profile, planned_exam_ids)
    state = StudentState(credits=credits, failed=failed, math_act=profile.math_act, exam_awards=awards)
    return state


def _better(new: Credit, old: Credit) -> bool:
    if not old.earned:
        return True
    if new.grade is None:
        return False  # exam credit never replaces a graded attempt (no duplicate credit)
    if old.grade is None:
        return True
    return GRADE_RANK.get(new.grade, 0) > GRADE_RANK.get(old.grade, 0)


def exam_awards(dataset: Dataset, profile: StudentProfile, planned_exam_ids: list[str]) -> list[ExamAward]:
    rows = dataset.equivalencies()
    awards: list[ExamAward] = []
    for score in profile.exams:
        matching = [
            r
            for r in rows
            if r["program"] == score.program
            and r["exam"].lower() == score.exam.lower()
            and score.score >= r["min_score"]
        ]
        if matching:
            best = max(matching, key=lambda r: r["min_score"])
            awards.append(ExamAward(best["id"], best["exam"], best["awards"], "exam"))
    by_id = {r["id"]: r for r in rows}
    held = {a.exam.lower() for a in awards}
    for exam_id in planned_exam_ids:
        row = by_id.get(exam_id)
        if row and row["exam"].lower() not in held:
            awards.append(ExamAward(row["id"], row["exam"], row["awards"], "planned_exam"))
    return awards


# ----------------------------------------------------------------------------- matching


@dataclass
class ReqStatus:
    req: dict[str, Any]
    credited: list[Credit]
    remaining_codes: list[str]  # course requirements: codes still to take
    satisfied: bool


def resolve_exam_awards(state: StudentState, program: dict[str, Any], dataset: Dataset) -> None:
    """Turn exam awards into credits, picking the award option that fills a requirement."""
    needed = _requirement_codes(program)
    for award in state.exam_awards:
        best = max(award.options, key=lambda opt: sum(c in needed for c in opt))
        for code in best:
            if code in state.credits and state.credits[code].earned:
                continue  # no duplicate credit
            state.credits[code] = Credit(
                code=code,
                title=course_title(dataset, code),
                hours=course_hours(dataset, code),
                source=award.source,
                grade=None,
                level=level_of(code),
                exam_id=award.exam_id,
            )


def _requirement_codes(program: dict[str, Any]) -> set[str]:
    codes: set[str] = set()
    for req in program["requirements"]:
        if req["kind"] == "course":
            codes.update(c for option in req["options"] for c in option)
        else:
            codes.update(req["bucket"]["codes"])
    return codes


def match_requirements(
    state: StudentState, program: dict[str, Any], dataset: Dataset
) -> tuple[list[ReqStatus], list[Credit]]:
    used: set[str] = set()
    statuses: dict[str, ReqStatus] = {}
    reqs = program["requirements"]

    # What-if re-solves credit completed bucket slots directly ("REQ:<requirement id>").
    for req in reqs:
        slot_credit = state.credits.get(slot_code(req["id"]))
        if slot_credit is not None and slot_credit.earned:
            used.add(slot_credit.code)
            statuses[req["id"]] = ReqStatus(req, [slot_credit], [], True)
    reqs = [r for r in reqs if r["id"] not in statuses]
    all_reqs = program["requirements"]

    planned: set[str] = set()  # codes an earlier open requirement already chose to schedule
    wanted = _mandatory_prerequisites(program, dataset)
    listed = {c for r in all_reqs if r["kind"] == "course" for option in r["options"] for c in option}

    def listed_or_earned(code: str, min_grade: str | None) -> bool:
        return code in listed or state.has(code, min_grade)

    def added_hours(option: list[str]) -> float:
        """Prerequisite hours an option would add beyond the program's own courses."""
        total = 0.0
        for code in option:
            course = dataset.courses.get(code)
            tree = course["prerequisites"] if course else None
            needed = _cheapest_additions(dataset, tree, listed_or_earned, state.math_act)
            if needed is None:
                return float("inf")
            total += _hours(dataset, [c for c in needed if c not in option])
        return total

    for req in (r for r in reqs if r["kind"] == "course"):
        statuses[req["id"]] = _match_course(req, state, used, planned, wanted, added_hours, dataset)
        planned.update(statuses[req["id"]].remaining_codes)

    code_buckets = [r for r in reqs if r["kind"] == "bucket" and r["bucket"]["codes"]]
    for req in sorted(code_buckets, key=lambda r: len(r["bucket"]["codes"])):
        min_grade = req.get("min_grade")
        hit = next(
            (
                state.credits[c]
                for c in req["bucket"]["codes"]
                if c in state.credits and c not in used and state.credits[c].meets(min_grade)
            ),
            None,
        )
        if hit:
            used.add(hit.code)
        statuses[req["id"]] = ReqStatus(req, [hit] if hit else [], [], hit is not None)

    rule_buckets = [r for r in reqs if r["kind"] == "bucket" and not r["bucket"]["codes"]]
    rule_buckets.sort(key=lambda r: 1 if (r["bucket"].get("rule") or {}).get("general") else 0)
    for req in rule_buckets:
        rule = req["bucket"].get("rule") or {}
        hit = None
        if req["bucket"]["category"] != "unrecognized":
            hit = next(
                (
                    c
                    for c in sorted(state.credits.values(), key=lambda c: c.code)
                    if c.code not in used and c.earned and rule_matches(rule, c.code)
                ),
                None,
            )
        if hit:
            used.add(hit.code)
        statuses[req["id"]] = ReqStatus(req, [hit] if hit else [], [], hit is not None)

    ordered = [statuses[r["id"]] for r in all_reqs]
    extra = [c for c in state.credits.values() if c.code not in used and c.earned]
    return ordered, extra


SLOT_PREFIX = "REQ:"


def slot_code(requirement_id: str) -> str:
    return f"{SLOT_PREFIX}{requirement_id}"


def rule_matches(rule: dict[str, Any], code: str) -> bool:
    level = level_of(code)
    if rule.get("min_level") and level < int(rule["min_level"]):
        return False
    if rule.get("max_level") and level > int(rule["max_level"]):
        return False
    subjects = rule.get("subjects")
    return not subjects or code.split(" ")[0] in subjects


def restrict_tree(tree: Tree | None, keep: set[str]) -> Tree | None:
    """Treat course leaves outside `keep` as met (None means no prerequisite remains)."""
    if tree is None:
        return None
    if tree["type"] == "course":
        return tree if tree["code"] in keep else None
    if tree["type"] in ("and", "or"):
        children = [restrict_tree(t, keep) for t in tree["items"]]
        if tree["type"] == "or" and any(c is None for c in children):
            return None
        kept = [c for c in children if c is not None]
        if not kept:
            return None
        return kept[0] if len(kept) == 1 else {**tree, "items": kept}
    return tree


def _mandatory_leaves(tree: Tree | None) -> set[str]:
    """Courses a prerequisite tree requires on every path."""
    if tree is None:
        return set()
    if tree["type"] == "course":
        return {tree["code"]}
    if tree["type"] == "and":
        return set().union(*(_mandatory_leaves(t) for t in tree["items"]))
    if tree["type"] == "or":
        branches = [_mandatory_leaves(t) for t in tree["items"]]
        return set.intersection(*branches) if branches else set()
    return set()


def _mandatory_prerequisites(program: dict[str, Any], dataset: Dataset) -> set[str]:
    """Courses that some required course of the program needs whatever path is taken."""
    out: set[str] = set()
    for req in program["requirements"]:
        if req["kind"] != "course":
            continue
        for option in req["options"]:
            for code in option:
                course = dataset.courses.get(code)
                if course:
                    out |= _mandatory_leaves(course["prerequisites"])
    return out


def _match_course(
    req: dict[str, Any],
    state: StudentState,
    used: set[str],
    planned: set[str],
    wanted: set[str],
    added_hours: Callable[[list[str]], float],
    dataset: Dataset,
) -> ReqStatus:
    min_grade = req.get("min_grade")
    best_option: list[str] | None = None
    best_hits: list[Credit] = []
    for option in req["options"]:
        hits = [
            state.credits[c]
            for c in option
            if c in state.credits and c not in used and state.credits[c].meets(min_grade)
        ]
        if len(hits) == len(option):
            used.update(c.code for c in hits)
            return ReqStatus(req, hits, [], True)
        if len(hits) > len(best_hits):
            best_option, best_hits = option, hits
    if best_option is None:
        # "X or Y" listed in two semesters means take one of each: skip options already scheduled.
        in_catalog = [opt for opt in req["options"] if all(c in dataset.courses for c in opt)]
        fresh = [opt for opt in in_catalog if not planned.intersection(opt)] or in_catalog
        # Prefer the option another required course needs anyway (PHYS 2114 before CHEM 3324),
        # then the one adding the fewest prerequisite hours, then the map's order.
        best_option = min(
            fresh,
            key=lambda opt: (not wanted.intersection(opt), added_hours(opt), fresh.index(opt)),
            default=req["options"][0],
        )
    used.update(c.code for c in best_hits)
    hit_codes = {c.code for c in best_hits}
    remaining = [c for c in best_option if c not in hit_codes]
    return ReqStatus(req, best_hits, remaining, False)


# ----------------------------------------------------------------------------- items


@dataclass
class Item:
    id: str
    kind: str  # course | bucket | elective | filler | added_prereq
    code: str | None
    label: str
    title: str
    hours: int
    level: int
    requirement_id: str | None
    prereq: Tree | None
    coreqs: list[list[str]]  # groups of alternatives; each group needs one member
    standing: str | None
    offered: dict[str, dict[str, Any]]
    transferable: bool
    in_major: bool
    min_grade: str | None
    options: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    map_semester: int | None = None

    @property
    def upper(self) -> bool:
        return self.level >= 3000

    def pattern(self, mode: str) -> str:
        letters = {"FA": "F", "WI": "W", "SP": "S", "SU": "Su"}
        return "/".join(letters[s] for s in SEASONS if offered_ok(self.offered[s], mode))


def offered_ok(entry: dict[str, Any], mode: str) -> bool:
    if not entry.get("available"):
        return False
    if entry.get("confidence") == "unknown":
        return mode == "optimistic"
    return True


def major_subjects(program: dict[str, Any]) -> set[str]:
    counts: Counter[str] = Counter()
    for req in program["requirements"]:
        if req["kind"] == "course":
            for code in req["options"][0]:
                if level_of(code) >= 3000:
                    counts[code.split(" ")[0]] += 1
    if not counts:
        return set()
    top = counts.most_common(1)[0][1]
    return {s for s, n in counts.items() if n >= max(2, top // 2)}


@dataclass
class ItemBuild:
    items: list[Item]
    statuses: list[ReqStatus]
    extra_credits: list[Credit]
    warnings: list[str]
    unschedulable: list[str]


def build_items(
    dataset: Dataset, program: dict[str, Any], state: StudentState, policies: Policies
) -> ItemBuild:
    resolve_exam_awards(state, program, dataset)
    statuses, extra = match_requirements(state, program, dataset)
    majors = major_subjects(program)
    items: list[Item] = []
    warnings: list[str] = []
    for status in statuses:
        req = status.req
        if status.satisfied:
            continue
        if req["kind"] == "course":
            for code in status.remaining_codes:
                items.append(course_item(dataset, code, req, majors, policies))
        else:
            items.append(bucket_item(dataset, req, majors, policies))
    in_program = _requirement_codes(program) | set(state.credits)
    for item in items:
        course = dataset.courses.get(item.code or "")
        if course and course.get("prerequisite_scope") == "program":
            item.prereq = restrict_tree(item.prereq, in_program)
            item.notes.append("prerequisite reads 'completion of all ...': only this program's courses apply")

    unschedulable = add_missing_prerequisites(dataset, items, state, majors, policies, warnings)
    # A passed course planned again to raise the grade (a D where a C is needed) is a retake: its
    # hours count once. A repeatable course the map lists twice (MUS 1501 applied lessons) keeps its
    # credit, because that attempt already fills its own requirement slot.
    in_slots = {c.code for status in statuses for c in status.credited}
    retaken = sorted(
        {
            i.code
            for i in items
            if i.code and state.has(i.code) and (i.code not in in_slots or i.kind == "added_prereq")
        }
    )
    for code in retaken:
        state.credits[code].retaken = True
    extra = [c for c in extra if not c.retaken]
    if retaken:
        warnings.append(
            f"Retake planned for {', '.join(retaken)} to reach the required grade; the earlier attempt's "
            "hours aren't counted twice toward the degree (confirm the repeat policy with the registrar)."
        )
    _add_fillers(dataset, program, state, items, extra, policies, warnings)
    _relax_placeholder_standing(items, program, policies)
    return ItemBuild(items, statuses, extra, warnings, unschedulable)


def _relax_placeholder_standing(items: list[Item], program: dict[str, Any], policies: Policies) -> None:
    """The junior-standing placeholder rule (D10) only makes sense for full-length degrees."""
    threshold = policies.standing_thresholds.get(UPPER_ELECTIVE_STANDING, 0)
    if threshold <= float(program["total_hours_min"]) / 2:
        return
    for item in items:
        if item.code is None and item.standing == UPPER_ELECTIVE_STANDING:
            item.standing = None


def course_item(
    dataset: Dataset,
    code: str,
    req: dict[str, Any] | None,
    majors: set[str],
    policies: Policies,
    kind: str = "course",
) -> Item:
    course = dataset.courses.get(code)
    hours = course_hours(dataset, code, float(req["hours"] or 3) if req else 3.0)
    offered = course["offered"] if course else _default_offered(level_of(code), gen_ed=False)
    acts = bool(course and course.get("acts_equivalent"))
    alternatives: list[str] = []
    if req:
        alternatives = [" + ".join(opt) for opt in req.get("options", [])[1:]]
    return Item(
        id=f"{req['id']}:{code}" if req else f"prereq:{code}",
        kind=kind,
        code=code,
        label=code,
        title=course_title(dataset, code),
        hours=max(0, round(hours)),
        level=level_of(code),
        requirement_id=req["id"] if req else None,
        prereq=course["prerequisites"] if course else None,
        coreqs=[list(group) for group in course["corequisites"]] if course else [],
        standing=course["standing"] if course else None,
        offered=offered,
        transferable=acts and level_of(code) <= policies.transfer_max_level,
        in_major=code.split(" ")[0] in majors,
        min_grade=req.get("min_grade") if req else None,
        options=alternatives,
        map_semester=req.get("map_semester") if req else None,
    )


def _default_offered(level: int, gen_ed: bool) -> dict[str, dict[str, Any]]:
    short = {
        "available": True,
        "confidence": "assumed" if gen_ed and level <= 2000 else "unknown",
        "source": "default",
        "note": "no course data",
    }
    regular = {
        "available": True,
        "confidence": "assumed",
        "source": "default",
        "note": "PRD §7.4 default",
    }
    return {"FA": dict(regular), "WI": dict(short), "SP": dict(regular), "SU": dict(short)}


def bucket_item(dataset: Dataset, req: dict[str, Any], majors: set[str], policies: Policies) -> Item:
    bucket = req["bucket"]
    codes: list[str] = [c for c in bucket["codes"] if c in dataset.courses]
    rule = bucket.get("rule") or {}
    hours = req["hours"] if req["hours"] is not None else 3
    if codes:
        offered = _best_offering([dataset.courses[c]["offered"] for c in codes])
        level = min(level_of(c) for c in codes)
        no_prereq = any(dataset.courses[c]["prerequisites"] is None for c in codes)
        prereq = (
            None
            if no_prereq
            else {
                "type": "or",
                "items": [
                    dataset.courses[c]["prerequisites"] for c in codes if dataset.courses[c]["prerequisites"]
                ],
            }
        )
        transferable = any(
            dataset.courses[c].get("acts_equivalent") and level_of(c) <= policies.transfer_max_level
            for c in codes
        )
        kind = "bucket"
    else:
        level = int(rule.get("min_level") or 1000)
        offered = _rule_offering(dataset, rule)
        prereq = None
        transferable = level <= policies.transfer_max_level and not rule.get("approved")
        kind = "elective"
    in_major = bool(rule.get("subjects") and set(rule["subjects"]) & majors)
    return Item(
        id=req["id"],
        kind=kind,
        code=None,
        label=req["label"],
        title=req["label"],
        hours=max(0, round(float(hours))),
        level=level,
        requirement_id=req["id"],
        prereq=prereq,
        coreqs=[],
        standing=UPPER_ELECTIVE_STANDING if kind == "elective" and level >= 3000 else None,
        offered=offered,
        transferable=transferable,
        in_major=in_major,
        min_grade=req.get("min_grade"),
        options=codes[:12] or list(bucket.get("recommended") or []),
        map_semester=req.get("map_semester"),
    )


def _best_offering(entries: list[dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for season in SEASONS:
        candidates = [e[season] for e in entries if e[season].get("available")]
        if not candidates:
            result[season] = {
                "available": False,
                "confidence": "documented",
                "source": "options",
                "note": "no listed option is offered this season",
            }
            continue
        best = max(candidates, key=lambda e: CONF_RANK.get(e["confidence"], 0))
        result[season] = {
            **best,
            "note": f"best of {len(entries)} options: {best.get('note', '')}".strip(),
        }
    return result


def _rule_offering(dataset: Dataset, rule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Offerings for rule-based electives, from courses that fit the rule."""
    general = bool(rule.get("general"))
    approved_only = bool(rule.get("approved")) and not rule.get("subjects")
    result: dict[str, dict[str, Any]] = {}
    for season in SEASONS:
        if season in ("FA", "SP"):
            result[season] = {
                "available": True,
                "confidence": "assumed",
                "source": "rule",
                "note": "elective slot; many courses qualify",
            }
            continue
        if approved_only:
            result[season] = {
                "available": True,
                "confidence": "unknown",
                "source": "rule",
                "note": "approved elective: availability depends on the course chosen",
            }
            continue
        examples = [
            code
            for code, course in dataset.courses.items()
            if rule_matches(rule, code)
            and course["offered"][season].get("confidence") in ("documented", "derived")
            and course["offered"][season].get("available")
        ]
        if examples:
            result[season] = {
                "available": True,
                "confidence": "derived",
                "source": "schedule_history",
                "note": f"qualifying courses that ran this season, e.g. {', '.join(sorted(examples)[:3])}",
            }
        else:
            result[season] = {
                "available": True,
                "confidence": "assumed" if general else "unknown",
                "source": "rule",
                "note": "no qualifying course found in the schedule history",
            }
    return result


# ----------------------------------------------------------------------------- prerequisites


def evaluate(tree: Tree | None, has: Callable[[str, str | None], bool], math_act: int | None) -> bool:
    if tree is None:
        return True
    kind = tree["type"]
    if kind == "course":
        return has(tree["code"], tree.get("min_grade") if tree.get("min_grade") == "C" else None)
    if kind == "test":
        return _test_ok(tree, math_act)
    if kind == "and":
        return all(evaluate(t, has, math_act) for t in tree["items"])
    if kind == "or":
        return any(evaluate(t, has, math_act) for t in tree["items"])
    return True  # standing handled separately; unparsed text is shown as a warning


MATH_TEST_WORDS = ("math", "algebra", "arithmetic", "quan")


def is_math_test(node: Tree) -> bool:
    name = str(node.get("test", "")).lower()
    return any(word in name for word in MATH_TEST_WORDS)


def _test_ok(node: Tree, math_act: int | None) -> bool:
    """Placement tests (DECISIONS.md D9).

    Math placement comes from the student's math ACT when given (other math tests aren't
    collected, so they count as not taken). With no math ACT, and for non-math placement
    tests (English, reading, ...), placement is assumed and the plan says so.
    """
    name = str(node.get("test", "")).lower()
    if not is_math_test(node):
        return True
    if math_act is None:
        return True
    if "act" in name and "math" in name:
        return math_act >= float(node["min_score"])
    return False


def add_missing_prerequisites(
    dataset: Dataset,
    items: list[Item],
    state: StudentState,
    majors: set[str],
    policies: Policies,
    warnings: list[str],
) -> list[str]:
    """Add prerequisite courses the plan needs but the program doesn't list (e.g. MATH 1914)."""
    unschedulable: list[str] = []
    for _ in range(6):
        planned = {i.code for i in items if i.code}

        def has(code: str, min_grade: str | None, planned: set[str] = planned) -> bool:
            return code in planned or state.has(code, min_grade)

        additions: dict[str, Item] = {}
        for item in list(items):
            if evaluate(item.prereq, has, state.math_act):
                continue
            needed = _cheapest_additions(dataset, item.prereq, has, state.math_act)
            if needed is None:
                if item.id not in unschedulable:
                    unschedulable.append(item.id)
                continue
            for code in needed:
                if code not in planned and code not in additions:
                    added = course_item(dataset, code, None, majors, policies, kind="added_prereq")
                    added.notes.append(f"added: needed before {item.label}")
                    additions[code] = added
        for item in list(items):
            for group in item.coreqs:
                if any(c in planned or c in additions or state.has(c) for c in group):
                    continue
                coreq = next((c for c in group if c in dataset.courses), None)
                if coreq is not None:
                    added = course_item(dataset, coreq, None, majors, policies, kind="added_prereq")
                    added.notes.append(f"added: corequisite of {item.label}")
                    additions[coreq] = added
        if not additions:
            break
        items.extend(additions.values())
        for code in additions:
            warnings.append(
                f"{code} ({course_title(dataset, code)}) was added because a required course needs it."
            )
    return unschedulable


def _cheapest_additions(
    dataset: Dataset,
    tree: Tree | None,
    has: Callable[[str, str | None], bool],
    math_act: int | None,
) -> list[str] | None:
    if tree is None or evaluate(tree, has, math_act):
        return []
    kind = tree["type"]
    if kind == "course":
        code = tree["code"]
        return [code] if code in dataset.courses and dataset.courses[code]["in_catalog"] else None
    if kind == "test":
        return None
    if kind == "and":
        out: list[str] = []
        for child in tree["items"]:
            sub = _cheapest_additions(dataset, child, has, math_act)
            if sub is None:
                return None
            out += [c for c in sub if c not in out]
        return out
    if kind == "or":
        best: list[str] | None = None
        for child in tree["items"]:
            sub = _cheapest_additions(dataset, child, has, math_act)
            if sub is not None and (best is None or _hours(dataset, sub) < _hours(dataset, best)):
                best = sub
        return best
    return []


def _hours(dataset: Dataset, codes: list[str]) -> float:
    return sum(course_hours(dataset, c) for c in codes)


# ----------------------------------------------------------------------------- fillers


def _add_fillers(
    dataset: Dataset,
    program: dict[str, Any],
    state: StudentState,
    items: list[Item],
    extra: list[Credit],
    policies: Policies,
    warnings: list[str],
) -> None:
    """General-elective filler so total and upper-level hour minimums hold (PRD §9)."""
    # Added prerequisites can stand in for general-elective slots.
    added = [i for i in items if i.kind == "added_prereq"]
    general_slots = [i for i in items if i.kind == "elective" and i.level < 3000 and i.transferable]
    for prereq_item in added:
        slot = next((s for s in general_slots if s.hours >= prereq_item.hours), None)
        if slot is not None:
            items.remove(slot)
            general_slots.remove(slot)
            prereq_item.notes.append(f"counts toward {slot.label}")

    credited = state.earned_hours
    planned = sum(i.hours for i in items)
    total_min = float(program["total_hours_min"])
    deficit = total_min - credited - planned
    upper_have = sum(c.hours for c in state.credits.values() if c.counts_toward_degree and c.level >= 3000)
    upper_have += sum(i.hours for i in items if i.upper)
    upper_deficit = float(program["upper_level_hours_min"]) - upper_have

    fillers: list[Item] = []
    if upper_deficit > 0:
        upper_deficit -= _designate_upper_slots(program, items, upper_deficit, policies)
    if upper_deficit > 0:
        for i in range(math.ceil(upper_deficit / 3)):
            fillers.append(_filler(dataset, f"filler:upper:{i + 1}", 3, 3000))
        deficit -= 3 * math.ceil(upper_deficit / 3)
        warnings.append(
            f"Added {3 * math.ceil(upper_deficit / 3)} hours of 3000-4000 level electives to reach "
            f"{program['upper_level_hours_min']} upper-division hours."
        )
    index = 0
    while deficit > 0.01:
        chunk = int(min(3, math.ceil(deficit)))
        index += 1
        fillers.append(_filler(dataset, f"filler:{index}", chunk, 1000))
        deficit -= chunk
    if index:
        warnings.append(
            f"Added {index} general-elective slot(s) to reach {program['total_hours_min']} total hours."
        )
    items.extend(fillers)


def _designate_upper_slots(
    program: dict[str, Any], items: list[Item], needed: float, policies: Policies
) -> float:
    """Meet the upper-level minimum with the map's own open slots before adding hours (D17).

    A general elective, minor slot, or subject elective with no level cap can be taken at the
    3000-4000 level. Latest map semesters go first, since they fall after junior standing anyway.
    """
    rules = {
        r["id"]: (r["bucket"].get("rule") or {}) for r in program["requirements"] if r["kind"] == "bucket"
    }
    candidates = [
        i
        for i in items
        if i.kind == "elective"
        and i.code is None
        and i.level < 3000
        and i.requirement_id in rules
        and rules[i.requirement_id].get("max_level") is None
    ]
    candidates.sort(key=lambda i: -(i.map_semester or 0))
    covered = 0.0
    for item in candidates:
        if covered >= needed:
            break
        item.level = 3000
        item.standing = UPPER_ELECTIVE_STANDING
        item.transferable = item.transferable and policies.transfer_max_level >= 3000
        item.label = f"{item.label} (3000-4000 level)"
        item.notes.append("taken at the 3000-4000 level to meet the upper-division minimum")
        covered += item.hours
    return covered


# Planning assumption (DECISIONS.md D10): a generic 3000-4000 elective slot is placed after
# junior standing, because most upper-division courses require it or upper-level prerequisites.
UPPER_ELECTIVE_STANDING = "JR"


def _filler(dataset: Dataset, item_id: str, hours: int, min_level: int) -> Item:
    rule = {
        "min_level": min_level if min_level >= 3000 else None,
        "max_level": None,
        "subjects": None,
        "approved": False,
        "general": True,
    }
    label = "Upper-level elective (3000–4000)" if min_level >= 3000 else "General elective"
    return Item(
        id=item_id,
        kind="filler",
        code=None,
        label=label,
        title=label,
        hours=hours,
        level=min_level,
        requirement_id=None,
        prereq=None,
        coreqs=[],
        standing=UPPER_ELECTIVE_STANDING if min_level >= 3000 else None,
        offered=_rule_offering(dataset, rule),
        transferable=min_level < 3000,
        in_major=False,
        min_grade=None,
    )
