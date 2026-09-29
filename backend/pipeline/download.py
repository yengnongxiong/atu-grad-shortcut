"""Stage 2: download degree-map PDFs and supporting policy pages into data/raw."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.common import RAW_DIR, Fetcher, OfflineMissingError, sha256_bytes
from pipeline.discover import MapRef

PAGES_DIR = RAW_DIR / "pages"

# Public www.atu.edu pages used as policy and calendar sources (catalog.atu.edu is WAF-gated).
SUPPORTING_PAGES: dict[str, str] = {
    "admissions-credit.html": "https://www.atu.edu/admissions/credit.php",
    "registrar-registrationinfo.html": "https://www.atu.edu/registrar/registrationinfo.php",
    "registrar-calendar.html": "https://www.atu.edu/registrar/calendar.php",
    "registrar-transfer.html": "https://www.atu.edu/registrar/transfer.php",
    "cpl-students.html": "https://www.atu.edu/cpl/students.php",
    "academic-calendar-2026-27.pdf": "https://www.atu.edu/academicaffairs/docs/2026-27%20UpdateCalendar.pdf",
}

CATALOG_PROBE_URL = "https://catalog.atu.edu/undergraduate/institutional-credit/clep/"


@dataclass
class DownloadResult:
    ref: MapRef
    ok: bool
    sha256: str | None
    detail: str


def download_maps(fetcher: Fetcher, refs: list[MapRef]) -> list[DownloadResult]:
    results: list[DownloadResult] = []
    for ref in refs:
        try:
            body = fetcher.get(ref.url, ref.raw_path())
        except (OfflineMissingError, RuntimeError) as exc:
            results.append(DownloadResult(ref, False, None, str(exc)))
            continue
        if not body.startswith(b"%PDF"):
            results.append(DownloadResult(ref, False, None, "response is not a PDF"))
            continue
        results.append(DownloadResult(ref, True, sha256_bytes(body), ""))
    return results


def download_supporting_pages(fetcher: Fetcher) -> dict[str, str]:
    """Fetch policy/calendar pages. Returns filename -> status."""
    status: dict[str, str] = {}
    for filename, url in SUPPORTING_PAGES.items():
        try:
            fetcher.get(url, PAGES_DIR / filename)
            status[filename] = "ok"
        except (OfflineMissingError, RuntimeError) as exc:
            status[filename] = f"unavailable: {exc}"
    return status
