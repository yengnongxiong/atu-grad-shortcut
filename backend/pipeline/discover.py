"""Stage 1: discover degree-map PDFs from ATU's advising pages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from pipeline.common import RAW_DIR, Fetcher

ADVISING_INDEX_URL = "https://www.atu.edu/advising/degreemaps.php"
PAGES_DIR = RAW_DIR / "pages"

# 2025-26 Computer Science is the owner's catalog year and PRD Appendix A's ground truth.
GROUND_TRUTH_YEAR = "2025-26"
GROUND_TRUTH_FILE = "ComputerScience.pdf"

ASSOCIATE_MARKERS = ("(AS)", "(AAS)", "(AA)", "(ASNT)")


@dataclass(frozen=True)
class MapRef:
    """One degree-map PDF as listed on an advising index page."""

    program_id: str
    title: str
    url: str
    catalog_year: str
    filename: str
    listed_as_associate: bool

    def raw_path(self) -> Path:
        return RAW_DIR / "degree_maps" / self.catalog_year / self.filename

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def year_pages(index_html: str) -> dict[str, str]:
    """Map short catalog year ('26-27') to its index page URL."""
    soup = BeautifulSoup(index_html, "html.parser")
    pages: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        m = re.search(r"degreemaps-(\d{2})-(\d{2})\.php$", href)
        if m:
            pages[f"{m.group(1)}-{m.group(2)}"] = urljoin(ADVISING_INDEX_URL, href)
    return pages


def full_year(short: str) -> str:
    """'26-27' -> '2026-27'."""
    first, second = short.split("-")
    return f"20{first}-{second}"


def parse_year_page(html: str, page_url: str, catalog_year: str) -> list[MapRef]:
    """Extract every degree-map PDF link (in page order, duplicates kept once per title)."""
    soup = BeautifulSoup(html, "html.parser")
    refs: list[MapRef] = []
    seen: set[tuple[str, str]] = set()
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        if "/degreemaps_docs/" not in href or not href.lower().endswith(".pdf"):
            continue
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        url = urljoin(page_url, href)
        filename = unquote(url.rsplit("/", 1)[-1]).replace(" ", "")
        key = (title, filename)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            MapRef(
                program_id=program_id_for(filename, catalog_year),
                title=title,
                url=url,
                catalog_year=catalog_year,
                filename=filename,
                listed_as_associate=any(mark in title for mark in ASSOCIATE_MARKERS),
            )
        )
    return refs


def program_id_for(filename: str, catalog_year: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    slug = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", stem)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return f"{slug}-{catalog_year}"


def discover(fetcher: Fetcher) -> tuple[str, list[MapRef]]:
    """Return (newest catalog year, map refs for newest year + 2025-26 CS ground truth)."""
    index_html = fetcher.get(ADVISING_INDEX_URL, PAGES_DIR / "advising-degreemaps.html").decode(
        "utf-8", errors="replace"
    )
    pages = year_pages(index_html)
    if not pages:
        raise RuntimeError("no degree-map year pages found on the advising index")
    newest_short = max(pages)
    newest = full_year(newest_short)
    refs: list[MapRef] = []

    newest_html = fetcher.get(pages[newest_short], PAGES_DIR / f"degreemaps-{newest_short}.html").decode(
        "utf-8", errors="replace"
    )
    refs.extend(parse_year_page(newest_html, pages[newest_short], newest))

    gt_short = GROUND_TRUTH_YEAR[2:]
    if newest != GROUND_TRUTH_YEAR and gt_short in pages:
        gt_html = fetcher.get(pages[gt_short], PAGES_DIR / f"degreemaps-{gt_short}.html").decode(
            "utf-8", errors="replace"
        )
        refs.extend(
            ref
            for ref in parse_year_page(gt_html, pages[gt_short], GROUND_TRUTH_YEAR)
            if ref.filename == GROUND_TRUTH_FILE
        )
    return newest, refs
