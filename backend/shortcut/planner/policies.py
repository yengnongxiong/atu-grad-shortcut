"""Typed access to data/processed/policies.json. Policy numbers are never hardcoded elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PolicySource:
    key: str
    title: str
    url: str


@dataclass(frozen=True)
class Policies:
    raw: dict[str, Any]

    # -- generic access ------------------------------------------------------------
    def rule(self, key: str) -> dict[str, Any]:
        rule: dict[str, Any] = self.raw["rules"][key]
        return rule

    def value(self, key: str) -> Any:
        return self.rule(key)["value"]

    def sources_for(self, key: str) -> list[PolicySource]:
        out: list[PolicySource] = []
        for source_key in self.rule(key)["sources"]:
            source = self.raw["sources"][source_key]
            out.append(PolicySource(source_key, source["title"], source["url"]))
        return out

    def first_url(self, key: str) -> str:
        return next((s.url for s in self.sources_for(key) if s.url), "")

    # -- typed shortcuts -----------------------------------------------------------
    @property
    def regular_load_max(self) -> int:
        return int(self.value("regular_load_max"))

    @property
    def overload_ceiling(self) -> int:
        return int(self.value("overload_ceiling"))

    @property
    def overload_review_threshold(self) -> int:
        return int(self.value("overload_review_threshold"))

    @property
    def overload_gpa_min(self) -> float:
        return float(self.value("overload_gpa_min"))

    @property
    def overload_prior_term_min_hours(self) -> int:
        return int(self.value("overload_prior_term_min_hours"))

    @property
    def first_term_no_overload(self) -> bool:
        return bool(self.value("first_term_no_overload"))

    @property
    def probation_advisor_threshold(self) -> int:
        return int(self.value("probation_advisor_threshold"))

    @property
    def workload_per_credit(self) -> tuple[int, int]:
        low, high = self.value("workload_outside_per_credit")
        return int(low), int(high)

    @property
    def standing_thresholds(self) -> dict[str, int]:
        return {k: int(v) for k, v in self.value("standing_thresholds").items()}

    @property
    def residency_min_hours(self) -> int:
        return int(self.value("residency_min_hours"))

    @property
    def residency_upper_major_hours(self) -> int:
        return int(self.value("residency_upper_major_hours"))

    @property
    def exam_credit_cap_hours(self) -> int:
        return int(self.value("exam_credit_cap_hours"))

    @property
    def math_placement_act_min(self) -> int:
        return int(self.value("math_placement_act_min"))

    @property
    def math_ladder(self) -> list[str]:
        return list(self.value("math_ladder"))

    @property
    def summer_max_load(self) -> int:
        return int(self.value("summer_max_load"))

    @property
    def winter_max_courses(self) -> int:
        return int(self.value("winter_max_courses"))

    @property
    def winter_max_hours(self) -> int:
        return int(self.value("winter_max_hours"))

    @property
    def preferred_hours_default(self) -> int:
        return int(self.value("preferred_hours_default"))

    @property
    def standing_counts_exam_transfer(self) -> bool:
        return bool(self.value("standing_counts_exam_transfer"))

    @property
    def transfer_max_level(self) -> int:
        return int(self.value("transfer_rules")["max_level"])

    @property
    def term_end_months(self) -> dict[str, str]:
        return dict(self.value("terms")["end_month"])

    @property
    def term_names(self) -> dict[str, str]:
        return dict(self.value("terms")["names"])
