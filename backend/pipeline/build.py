"""Pipeline CLI: discover -> download -> parse -> enrich -> exams -> validate -> tier.

uv run python -m pipeline.build --online      # fetch anything missing, then rebuild
uv run python -m pipeline.build --offline     # rebuild from committed raw files only
"""

from __future__ import annotations

import argparse
import re
import shutil
import time
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any

import httpx

from pipeline.banner import BannerClient
from pipeline.codes import code_groups, extract_codes, strip_acts
from pipeline.common import (
    MANUAL_DIR,
    PROCESSED_DIR,
    USER_AGENT,
    Fetcher,
    read_json,
    utc_now_iso,
    write_json,
)
from pipeline.discover import MapRef, discover
from pipeline.download import CATALOG_PROBE_URL, download_maps, download_supporting_pages
from pipeline.enrich_catalog import (
    CourseBuildContext,
    MapNote,
    build_course,
    build_course_index,
    load_banner_raw,
    notes_for_row,
    prerequisite_closure,
    prune_retired,
)
from pipeline.exams import build_exam_tables
from pipeline.fetch_banner import fetch_all
from pipeline.parse_degree_map import ParsedMap, parse_degree_map
from pipeline.programs import ProgramContext, build_program, list_category
from pipeline.report import write_report
from pipeline.validate import assign_tier, validate_program

ONLY_IN_TEXT = re.compile(r"\b(?:fall|spring|summer)\s+only\b", re.I)


@dataclass
class RunStats:
    mode: str
    started: float = field(default_factory=time.time)
    catalog_status: str = "not probed"
    banner_status: str = "not used"
    notes: list[str] = field(default_factory=list)


def probe_catalog() -> str:
    try:
        response = httpx.get(CATALOG_PROBE_URL, timeout=20, headers={"User-Agent": USER_AGENT})
    except httpx.HTTPError as exc:
        return f"unreachable ({exc.__class__.__name__})"
    if response.status_code == 202 and not response.content:
        return "blocked by AWS WAF JavaScript challenge (HTTP 202, empty body)"
    return f"reachable (HTTP {response.status_code})"


def collect_map_notes(parsed: dict[str, tuple[MapRef, ParsedMap]]) -> dict[str, list[MapNote]]:
    notes: dict[str, list[MapNote]] = {}
    for ref, pm in parsed.values():
        for semester in pm.semesters:
            for row in semester.rows:
                groups = code_groups(strip_acts(row.text))
                if len(groups) != 1 or not (row.notes or ONLY_IN_TEXT.search(row.text)):
                    continue
                note = notes_for_row(ref.program_id, ref.url, row.notes, row.text)
                if not (note.only or note.prereq_text or note.coreq_text or note.pass_fail):
                    continue
                # "PHYS 2114/2000 ... Co-req: MATH 2914": prerequisite and corequisite notes describe
                # the lecture. A 0-credit lab in the same cell (ATU numbers end in the credit hours)
                # keeps only the offering and pass/fail facts; its own catalog entry names its coreqs.
                lab_note = replace(note, prereq_text="", coreq_text="")
                has_credit = any(not code.endswith("0") for code in groups[0])
                for code in groups[0]:
                    lab = code.endswith("0") and has_credit
                    notes.setdefault(code, []).append(lab_note if lab else note)
    return notes


def seed_codes(parsed: dict[str, tuple[MapRef, ParsedMap]]) -> set[str]:
    seeds: set[str] = set()
    for _, pm in parsed.values():
        for semester in pm.semesters:
            for row in semester.rows:
                seeds.update(extract_codes(row.text))
                seeds.update(extract_codes(row.notes))
        for codes in pm.gen_ed_lists.values():
            seeds.update(codes)
    return seeds


def appendix_a_courses() -> dict[str, dict[str, Any]]:
    data = read_json(MANUAL_DIR / "appendix_a_cs_2025_26.json")
    out: dict[str, dict[str, Any]] = {}
    acts = data.get("acts_equivalents", {})
    for semester in data["semesters"]:
        for row in semester["rows"]:
            if "code" in row:
                out[row["code"]] = {**row, "acts": acts.get(row["code"])}
    return out


def run(online: bool, refresh: bool, fetch_banner: bool) -> dict[str, Any]:
    stats = RunStats(mode="online" if online else "offline")
    fetcher = Fetcher(online=online, refresh=refresh)
    newest, refs = discover(fetcher)
    download_results = download_maps(fetcher, refs)
    pages_status = download_supporting_pages(fetcher)
    if online:
        stats.catalog_status = probe_catalog()
    fetcher.close()

    parsed: dict[str, tuple[MapRef, ParsedMap]] = {}
    failures: dict[str, str] = {}
    for result in download_results:
        if not result.ok:
            failures[result.ref.program_id] = f"download failed: {result.detail}"
            continue
        try:
            parsed[result.ref.program_id] = (result.ref, parse_degree_map(result.ref.raw_path()))
        except Exception as exc:
            failures[result.ref.program_id] = f"parse failed: {exc}"

    seeds = seed_codes(parsed)
    if online and fetch_banner:
        client = BannerClient(online=True)
        try:
            summary = fetch_all(client, seeds)
            stats.banner_status = (
                f"fetched/cached {summary['detailed']} course details across "
                f"{summary['subjects']} subjects ({client.stats.requests} requests)"
            )
        except Exception as exc:
            stats.banner_status = f"fetch failed ({exc}); using committed raw data"
        finally:
            client.close()
    banner = load_banner_raw()
    if banner.available:
        stats.banner_status = (
            stats.banner_status
            if stats.banner_status != "not used"
            else (f"loaded committed snapshots ({len(banner.details)} course details)")
        )
    else:
        stats.banner_status = "unavailable; CS falls back to PRD Appendix A"

    policies = read_json(MANUAL_DIR / "policies.json")
    rules = policies["rules"]
    gen_ed_codes = {c for _, pm in parsed.values() for codes in pm.gen_ed_lists.values() for c in codes}
    ctx = CourseBuildContext(
        banner=banner,
        map_notes=collect_map_notes(parsed),
        gen_ed_codes=gen_ed_codes,
        math_ladder=list(rules["math_ladder"]["value"]),
        math_act_min=int(rules["math_placement_act_min"]["value"]),
        appendix_a=appendix_a_courses(),
    )
    exam_codes = {
        c
        for row in read_json(MANUAL_DIR / "clep_appendix_b.json")["equivalencies"]
        for option in row["awards"]
        for c in option
    }
    wanted = set(seeds) | exam_codes | set(ctx.appendix_a) | set(rules["math_ladder"]["value"])
    wanted |= {c for c in banner.details}
    courses = {code: build_course(code, ctx) for code in sorted(wanted)}
    closure = prerequisite_closure(set(courses), courses)
    for code in sorted(closure - set(courses)):
        courses[code] = build_course(code, ctx)
    courses = {
        code: course
        for code, course in sorted(courses.items())
        if course["in_catalog"] or course["sources"] or code in closure
    }
    known = {code for code, course in courses.items() if course["in_catalog"]}
    if known:
        for course in courses.values():
            groups = [[c for c in group if c in known] for group in course["corequisites"]]
            course["corequisites"] = [group for group in groups if group]
            tree, removed = prune_retired(course["prerequisites"], known)
            if removed:
                course["prerequisites"] = tree
                course["pruned_prerequisites"] = removed
                course["warnings"].append(
                    "prerequisite(s) not in the current catalog ignored: " + ", ".join(removed)
                )
                if course["parse_confidence"] == "high":
                    course["parse_confidence"] = "medium"

    pooled: dict[str, list[str]] = {}
    for ref, pm in parsed.values():
        if ref.catalog_year != newest:
            continue
        for name, codes in pm.gen_ed_lists.items():
            category = list_category(name)
            if category:
                pooled.setdefault(category, [])
                pooled[category] += [c for c in codes if c not in pooled[category]]
    pctx = ProgramContext(
        courses=courses,
        subjects=set(banner.subjects.values()) or {c.split()[0] for c in courses},
        pooled_lists=pooled,
        policies=rules,
    )
    cross_checks: dict[str, Any] = read_json(MANUAL_DIR / "cross_checks.json")["programs"]

    programs: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    for ref in refs:
        if ref.program_id in failures:
            report_rows.append(_report_row(ref, None, "not_ingested", [], failures[ref.program_id]))
            continue
        _, pm = parsed[ref.program_id]
        program = build_program(ref, pm, pctx)
        semesters = pm.to_dict()["semesters"]
        if not program["is_bachelor"]:
            report_rows.append(
                _report_row(ref, program, "excluded", [], "not a bachelor's degree (PRD §5 non-goal)")
            )
            continue
        results = validate_program(program, semesters, courses)
        cross = cross_checks.get(ref.program_id)
        tier = assign_tier(results, cross)
        program["validation"] = results
        program["trust_tier"] = tier
        program["cross_check"] = cross
        program["parsed_map"] = {"gen_ed_list_names": list(pm.gen_ed_lists), "semesters": semesters}
        programs.append(program)
        report_rows.append(_report_row(ref, program, tier, results, ""))

    exams = build_exam_tables(courses)
    tier_counts = Counter(r["tier"] for r in report_rows)
    meta = {
        "generated_at": utc_now_iso(),
        "pipeline_mode": stats.mode,
        "newest_catalog_year": newest,
        "ground_truth_program": "computer-science-2025-26",
        "catalog_status": stats.catalog_status,
        "banner_status": stats.banner_status,
        "discovered_maps": len(refs),
        "bachelor_programs": len(programs),
        "tier_counts": dict(tier_counts),
        "course_count": len(courses),
        "supporting_pages": pages_status,
        "sources": _meta_sources(),
    }

    _write_outputs(programs, courses, build_course_index(banner.catalog), exams, policies, meta)
    write_report(meta, report_rows, programs, courses, parsed)
    return meta


def _report_row(
    ref: MapRef, program: dict[str, Any] | None, tier: str, results: list[dict[str, Any]], note: str
) -> dict[str, Any]:
    issues = [f"{r['check']}: {r['detail']}" for r in results if not r["passed"]]
    warnings = [f"{r['check']}: {r['detail']}" for r in results if r["passed"] and r["detail"]]
    return {
        "program_id": ref.program_id,
        "title": ref.title,
        "catalog_year": ref.catalog_year,
        "degree": (program or {}).get("degree_abbr") or (program or {}).get("degree", ""),
        "college": (program or {}).get("college", ""),
        "tier": tier,
        "issues": issues,
        "warnings": warnings,
        "note": note,
        "url": ref.url,
    }


def _meta_sources() -> list[dict[str, str]]:
    policies = read_json(MANUAL_DIR / "policies.json")
    sources = [
        {
            "title": "ATU degree maps by catalog year",
            "url": "https://www.atu.edu/advising/degreemaps.php",
        },
        {
            "title": "ATU Banner course catalog (public)",
            "url": "https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=courseSearch",
        },
        {
            "title": "ATU Banner class schedule (public)",
            "url": "https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb/term/termSelection?mode=search",
        },
    ]
    for source in policies["sources"].values():
        if source["url"] and all(s["url"] != source["url"] for s in sources):
            sources.append({"title": source["title"], "url": source["url"]})
    return sources


def _write_outputs(
    programs: list[dict[str, Any]],
    courses: dict[str, dict[str, Any]],
    course_index: dict[str, dict[str, Any]],
    exams: dict[str, dict[str, Any]],
    policies: dict[str, Any],
    meta: dict[str, Any],
) -> None:
    programs_dir = PROCESSED_DIR / "programs"
    if programs_dir.exists():
        shutil.rmtree(programs_dir)
    for program in programs:
        write_json(programs_dir / f"{program['id']}.json", program)
    write_json(PROCESSED_DIR / "courses.json", courses)
    write_json(PROCESSED_DIR / "course_index.json", course_index)
    for name, table in exams.items():
        write_json(PROCESSED_DIR / "exams" / f"{name}.json", table)
    write_json(PROCESSED_DIR / "policies.json", policies)
    write_json(PROCESSED_DIR / "meta.json", meta)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--online", action="store_true", help="fetch missing raw files (default)")
    mode.add_argument("--offline", action="store_true", help="use committed raw files only")
    parser.add_argument("--refresh", action="store_true", help="re-download raw files")
    parser.add_argument("--skip-banner", action="store_true", help="don't call Banner online")
    args = parser.parse_args(argv)
    online = not args.offline
    meta = run(online=online, refresh=args.refresh, fetch_banner=not args.skip_banner)
    print(
        f"pipeline done ({meta['pipeline_mode']}): {meta['bachelor_programs']} bachelor's programs, "
        f"{meta['course_count']} courses, tiers {meta['tier_counts']}"
    )


if __name__ == "__main__":
    main()
