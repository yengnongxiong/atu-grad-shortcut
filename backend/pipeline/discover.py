"""Stage 1: discover degree-map PDFs from ATU's advising pages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from pipeline.common import RAW_DIR, Fetcher

ADVISING_INDEX_URL = "https://www.atu.edu/advising/degreemaps.php"
PAGES_DIR = RAW_DIR / "pages"

# 2025-26 Computer Science is the owner's catalog year and PRD Appendix A's ground truth.
GROUND_TRUTH_YEAR = "2025-26"
GROUND_TRUTH_FILE = "ComputerScience.pdf"
# Students follow the map for the year they entered (catalog of entry), so every listed year
# from this one on is ingested (PRD v1.1 §3.2). Older years are a documented non-goal.
EARLIEST_CATALOG_YEAR = "2025-26"

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
    # Other titles the index links to this same PDF (an ATU index error, kept visible)
    also_listed_as: tuple[str, ...] = ()

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
    by_file: dict[str, int] = {}
    for a in soup.find_all("a", href=True):
        href = str(a["href"])
        # Maps live under /advising/degreemaps_docs/<year>/, but ATU's index occasionally links
        # one from /advising/degreemaps/ (2025-26 Management); both are degree maps.
        if not re.search(r"/advising/degreemaps(_docs)?/", href) or not href.lower().endswith(".pdf"):
            continue
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        url = urljoin(page_url, href)
        filename = unquote(url.rsplit("/", 1)[-1]).replace(" ", "")
        if filename in by_file:  # the same PDF listed again: one map, remember the other title
            first = refs[by_file[filename]]
            if title != first.title and title not in first.also_listed_as:
                refs[by_file[filename]] = replace(first, also_listed_as=(*first.also_listed_as, title))
            continue
        by_file[filename] = len(refs)
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
    """Return (newest catalog year, map refs for every year from EARLIEST_CATALOG_YEAR on)."""
    index_html = fetcher.get(ADVISING_INDEX_URL, PAGES_DIR / "advising-degreemaps.html").decode(
        "utf-8", errors="replace"
    )
    pages = year_pages(index_html)
    if not pages:
        raise RuntimeError("no degree-map year pages found on the advising index")
    newest = full_year(max(pages))
    refs: list[MapRef] = []
    for short in sorted(pages, reverse=True):
        year = full_year(short)
        if year < EARLIEST_CATALOG_YEAR:
            continue
        raw = fetcher.get(pages[short], PAGES_DIR / f"degreemaps-{short}.html")
        html = raw.decode("utf-8", errors="replace")
        refs.extend(parse_year_page(html, pages[short], year))
    return newest, refs
