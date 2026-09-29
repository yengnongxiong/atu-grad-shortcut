"""Every supported catalog year's degree maps are discovered (PRD v1.1 §3.2)."""

from __future__ import annotations

from pipeline.common import Fetcher
from pipeline.discover import EARLIEST_CATALOG_YEAR, discover


def test_discovers_every_catalog_year_from_the_earliest_supported() -> None:
    newest, refs = discover(Fetcher(online=False, refresh=False))
    years = {r.catalog_year for r in refs}
    assert EARLIEST_CATALOG_YEAR == "2025-26"
    assert newest == "2026-27" and years == {"2025-26", "2026-27"}
    assert sum(r.catalog_year == "2025-26" for r in refs) >= 75
    assert len({r.program_id for r in refs}) == len(refs)


def test_a_pdf_linked_under_two_titles_is_one_map_that_keeps_both_titles() -> None:
    """ATU's 2025-26 index links "Chemistry - Environmental" to BiologyEnvironmental.pdf."""
    _, refs = discover(Fetcher(online=False, refresh=False))
    bio = [r for r in refs if r.catalog_year == "2025-26" and r.filename == "BiologyEnvironmental.pdf"]
    assert len(bio) == 1
    assert bio[0].title == "Biology - Environmental"
    assert bio[0].also_listed_as == ("Chemistry - Environmental",)


def test_a_map_stored_outside_the_usual_folder_is_still_found() -> None:
    """ATU's 2025-26 index links Management to /advising/degreemaps/MgmtBusinessMgmt.pdf."""
    _, refs = discover(Fetcher(online=False, refresh=False))
    mgmt = [r for r in refs if r.catalog_year == "2025-26" and r.filename == "MgmtBusinessMgmt.pdf"]
    assert len(mgmt) == 1 and mgmt[0].url == "https://www.atu.edu/advising/degreemaps/MgmtBusinessMgmt.pdf"
