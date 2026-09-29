"""Client for ATU's public Banner 9 self-service (course catalog + class schedule).

catalog.atu.edu sits behind a JavaScript WAF challenge that this environment cannot pass
(see DECISIONS.md D5). Banner's "Browse Course Catalog" and "Browse Classes" pages are
public, view-only, and need no login. They are ATU's system of record for course
prerequisites and term offerings.

Raw snapshots are trimmed to the fields Shortcut uses (no instructor names or enrollment
counts) and committed under data/raw/banner/ so the pipeline can rerun offline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from pipeline.common import RAW_DIR, USER_AGENT, OfflineMissingError, write_json

BANNER_BASE = "https://reg-prod.ec.atu.edu/StudentRegistrationSsb/ssb"
BANNER_CATALOG_URL = f"{BANNER_BASE}/term/termSelection?mode=courseSearch"
BANNER_SCHEDULE_URL = f"{BANNER_BASE}/term/termSelection?mode=search"
BANNER_DIR = RAW_DIR / "banner"

# Catalog entries are read as of Fall 2026, the first term of the newest (2026-27) catalog.
CATALOG_TERM = "202670"

# Three academic years of schedule history, including Winter Intersession and Summer.
HISTORY_TERMS: tuple[str, ...] = (
    "202370",
    "202380",
    "202420",
    "202440",
    "202470",
    "202480",
    "202520",
    "202540",
    "202570",
    "202580",
    "202620",
    "202640",
    "202670",
    "202680",
    "202720",
)

SECTION_FIELDS = (
    "courseReferenceNumber",
    "subject",
    "courseNumber",
    "sequenceNumber",
    "courseTitle",
    "creditHours",
    "creditHourLow",
    "creditHourHigh",
    "scheduleTypeDescription",
    "campusDescription",
    "instructionalMethodDescription",
    "partOfTerm",
)

CATALOG_FIELDS = (
    "subjectCode",
    "courseNumber",
    "courseTitle",
    "creditHourLow",
    "creditHourHigh",
    "creditHourIndicator",
    "college",
    "department",
    "termEffective",
    "subjectDescription",
)


def term_season(term_code: str) -> str:
    """Banner term suffix -> season: 20=Spring, 40=Summer, 70=Fall, 80=Winter."""
    return {"20": "SP", "40": "SU", "70": "FA", "80": "WI"}[term_code[-2:]]


@dataclass
class BannerStats:
    requests: int = 0
    cached: int = 0
    errors: int = 0


class BannerClient:
    """Session-aware Banner client with on-disk caching (online) or raw-only reads (offline)."""

    def __init__(self, online: bool, delay_s: float = 0.2) -> None:
        self.online = online
        self.delay_s = delay_s
        self.stats = BannerStats()
        self._client: httpx.Client | None = None
        self._mode_term: tuple[str, str] | None = None

    # -- session -----------------------------------------------------------------
    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            )
        return self._client

    def _fresh_session(self) -> None:
        """Banner caches search results per session, so each subject query gets its own."""
        self.close()
        self._mode_term = None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _select_term(self, mode: str, term: str) -> None:
        if self._mode_term == (mode, term):
            return
        http = self._http()
        http.get(f"{BANNER_BASE}/term/termSelection", params={"mode": mode})
        response = http.post(f"{BANNER_BASE}/term/search", params={"mode": mode}, data={"term": term})
        response.raise_for_status()
        self._mode_term = (mode, term)

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(4):
            try:
                time.sleep(self.delay_s)
                self.stats.requests += 1
                response = self._http().request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                last = exc
                time.sleep(2.0 * (attempt + 1))
        self.stats.errors += 1
        raise RuntimeError(f"Banner request failed: {url}: {last}")

    # -- cache helpers -------------------------------------------------------------
    def _cached(self, path: Path) -> Any | None:
        if path.exists():
            self.stats.cached += 1
            return json.loads(path.read_text(encoding="utf-8"))
        if not self.online:
            raise OfflineMissingError(f"{path} not committed and pipeline is offline")
        return None

    # -- catalog -------------------------------------------------------------------
    def catalog_subject(self, subject: str, term: str = CATALOG_TERM) -> list[dict[str, Any]]:
        path = BANNER_DIR / "catalog" / term / f"{subject}.json"
        cached = self._cached(path)
        if cached is not None:
            return list(cached)
        self._fresh_session()
        self._select_term("courseSearch", term)
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self._request(
                "GET",
                f"{BANNER_BASE}/courseSearchResults/courseSearchResults",
                params={
                    "txt_subject": subject,
                    "txt_term": term,
                    "pageOffset": offset,
                    "pageMaxSize": 500,
                    "sortColumn": "subjectDescription",
                    "sortDirection": "asc",
                },
            )
            payload = response.json()
            data = payload.get("data") or []
            rows.extend({k: row.get(k) for k in CATALOG_FIELDS} for row in data)
            offset += len(data)
            if not data or offset >= int(payload.get("totalCount") or 0):
                break
        write_json(path, rows)
        return rows

    def course_details(self, subject: str, number: str, term: str = CATALOG_TERM) -> dict[str, str]:
        path = BANNER_DIR / "course_details" / subject / f"{number}.json"
        cached = self._cached(path)
        if cached is not None:
            return dict(cached)
        self._select_term("courseSearch", term)
        form = {"term": term, "subjectCode": subject, "courseNumber": number}
        details = {
            "term": term,
            "description_html": self._post_text("courseSearchResults/getCourseDescription", form),
            "prerequisites_html": self._post_text("courseSearchResults/getPrerequisites", form),
            "corequisites_html": self._post_text("courseSearchResults/getCorequisites", form),
        }
        write_json(path, details)
        return details

    def _post_text(self, endpoint: str, form: dict[str, str]) -> str:
        return self._request("POST", f"{BANNER_BASE}/{endpoint}", data=form).text.strip()

    # -- schedule ------------------------------------------------------------------
    def schedule_subject(self, term: str, subject: str) -> list[dict[str, Any]]:
        path = BANNER_DIR / "schedule" / term / f"{subject}.json"
        cached = self._cached(path)
        if cached is not None:
            return list(cached)
        self._fresh_session()
        self._select_term("search", term)
        rows: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self._request(
                "GET",
                f"{BANNER_BASE}/searchResults/searchResults",
                params={
                    "txt_subject": subject,
                    "txt_term": term,
                    "pageOffset": offset,
                    "pageMaxSize": 500,
                    "sortColumn": "subjectDescription",
                    "sortDirection": "asc",
                },
            )
            payload = response.json()
            data = payload.get("data") or []
            rows.extend({k: row.get(k) for k in SECTION_FIELDS} for row in data)
            offset += len(data)
            if not data or offset >= int(payload.get("totalCount") or 0):
                break
        write_json(path, rows)
        return rows

    def terms(self) -> list[dict[str, str]]:
        path = BANNER_DIR / "terms.json"
        cached = self._cached(path)
        if cached is not None:
            return list(cached)
        response = self._request(
            "GET",
            f"{BANNER_BASE}/classSearch/getTerms",
            params={"searchTerm": "", "offset": 1, "max": 40},
        )
        rows = [{"code": t["code"], "description": t["description"]} for t in response.json()]
        write_json(path, rows)
        return rows

    def subjects(self, term: str = CATALOG_TERM) -> list[dict[str, str]]:
        """All catalog subjects with descriptions (maps prerequisite-table names to codes)."""
        path = BANNER_DIR / "subjects.json"
        cached = self._cached(path)
        if cached is not None:
            return list(cached)
        self._select_term("courseSearch", term)
        response = self._request(
            "GET",
            f"{BANNER_BASE}/courseSearch/get_subject",
            params={"searchTerm": "", "term": term, "offset": 1, "max": 500},
        )
        rows = [{"code": s["code"], "description": s["description"]} for s in response.json()]
        write_json(path, rows)
        return rows
