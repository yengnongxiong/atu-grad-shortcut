"""Regenerate the README screenshots in docs/screenshots from demo data.

Run `make build`, then `make screenshots`. The script starts the built app on a spare port, opens
it in Chromium (Playwright) at 1440x900 and 2x scale, and saves each view. It uses the demo
profiles and the synthetic Degree Works audit in frontend/src/degreeworks/fixtures/sample-audit.ts,
never a personal record. Each shot first checks the text its README caption states (dates, the
critical chain), so a changed plan fails here instead of producing a caption that's wrong.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from html import escape
from pathlib import Path

from playwright.sync_api import Browser, FloatRect, Locator, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
OUT = ROOT / "docs" / "screenshots"
SAMPLE_AUDIT = ROOT / "frontend" / "src" / "degreeworks" / "fixtures" / "sample-audit.ts"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
LEVERS = ("Heavier regular terms", "Summer terms", "Winter intersession")


@contextmanager
def app_server() -> Iterator[None]:
    """Serve the built app and API from one process, as `make serve` does."""
    if not (BACKEND / "shortcut" / "static" / "index.html").exists():
        sys.exit("The frontend isn't built. Run `make build` first.")
    command = [sys.executable, "-m", "uvicorn", "shortcut.api.app:app", "--port", str(PORT)]
    process = subprocess.Popen(command, cwd=BACKEND, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(f"{BASE}/api/health", timeout=1)
                break
            except OSError:
                if time.monotonic() > deadline:
                    sys.exit(f"The app didn't start on port {PORT}.")
                time.sleep(0.3)
        yield
    finally:
        process.terminate()
        process.wait(timeout=10)


def new_page(browser: Browser) -> Page:
    """A fresh context per flow, so localStorage and sessionStorage start empty."""
    context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    page = context.new_page()
    page.set_default_timeout(30_000)
    return page


def settle(page: Page) -> None:
    """Wait until no re-solve is in flight."""
    expect(page.get_by_text("Re-solving")).to_have_count(0)
    page.wait_for_load_state("networkidle")


def headline(page: Page) -> Locator:
    return page.locator("section[aria-labelledby='plan-title']")


def open_persona(page: Page, name: str) -> None:
    page.goto(BASE)
    page.get_by_role("button", name=re.compile(name)).click()
    expect(headline(page)).to_contain_text("Your Shortcut")
    settle(page)


def save(target: Page | Locator, name: str) -> None:
    target.screenshot(path=OUT / name)
    print(f"saved docs/screenshots/{name}")


def save_region(page: Page, name: str, first: Locator, last: Locator) -> None:
    """Save the page from the top of `first` to the bottom of `last`, at `first`'s width."""
    top, end = first.bounding_box(), last.bounding_box()
    assert top is not None and end is not None
    height = end["y"] + end["height"] - top["y"]
    clip: FloatRect = {"x": top["x"], "y": top["y"], "width": top["width"], "height": height}
    page.screenshot(path=OUT / name, full_page=True, clip=clip)
    print(f"saved docs/screenshots/{name}")


def landing(browser: Browser) -> None:
    page = new_page(browser)
    page.goto(BASE)
    demos = page.locator("section").filter(has_text="One-click demos")
    expect(demos.get_by_role("button")).to_have_count(4)
    save_region(page, "landing.png", page.locator("#root"), demos)
    page.context.close()


def p1_accelerated(browser: Browser) -> None:
    """P1 with summer, winter, and heavier terms on: the hero, levers, bottlenecks, and what-if."""
    page = new_page(browser)
    open_persona(page, "Starting from scratch")
    for lever in LEVERS:
        page.get_by_role("switch", name=re.compile(f"^{lever}")).click()
        settle(page)
    expect(headline(page)).to_contain_text(re.compile(r"Degree map\s*May 2030"))
    expect(headline(page)).to_contain_text(re.compile(r"Standard pace\s*May 2030"))
    expect(headline(page)).to_contain_text(re.compile(r"Your Shortcut\s*May 2029"))
    page.mouse.move(0, 0)
    save(page, "plan-overview.png")

    levers = page.locator("section[aria-labelledby='levers-title']")
    items = levers.locator("li")
    expect(items.nth(0)).to_contain_text("Saves 2 terms")
    expect(items.nth(1)).to_contain_text("Saves 2 terms")
    expect(items.nth(2)).to_contain_text("No time saved alone")
    save_region(page, "lever-panel.png", levers, items.nth(3))

    page.get_by_role("tab", name="Bottlenecks").click()
    panel = page.locator("#panel-bottlenecks")
    expect(panel).to_contain_text(
        "Critical chain: COMS 2203 (Fall 2027, F/S) → COMS 2213 (Spring 2028, S) → "
        "COMS 3213 (Fall 2028, F) → COMS 3313 (Spring 2029, S)"
    )
    panel.locator("aside select").select_option(label="COMS 3213 (Fall 2028) · critical")
    expect(panel.locator("aside")).to_contain_text("What if I delay this one term?")
    page.wait_for_timeout(500)  # let the graph finish its layout
    save(panel, "bottlenecks.png")

    page.get_by_role("tab", name="What-if").click()
    panel = page.locator("#panel-whatif")
    panel.get_by_text("I fail a course").click()
    course = panel.locator("label", has_text=re.compile(r"^Course")).locator("select")
    option = course.locator("option", has_text="COMS 2203").first.text_content()
    assert option is not None
    course.select_option(label=option)
    panel.get_by_role("button", name="Run what-if").click()
    expect(panel).to_contain_text("May 2029 → May 2030")
    expect(panel).to_contain_text("You retake COMS 2203 in Spring 2028")
    page.mouse.move(0, 0)
    save(panel, "whatif-fail-course.png")
    page.context.close()


def p4_no_shortcut(browser: Browser) -> None:
    page = new_page(browser)
    open_persona(page, "No shortcut")
    expect(headline(page)).to_contain_text(re.compile(r"Your Shortcut\s*May 2029"))
    expect(headline(page)).to_contain_text(
        "NUR 2023 (Spring 2027, offered F/S) → NUR 3404 (Fall 2027, offered F/S) → NUR 3606 (Spring 2028, "
        "offered F/S) → NUR 4206 (Fall 2028, offered F/S) → NUR 4606 (Spring 2029, offered F/S)"
    )
    save(headline(page), "no-shortcut.png")
    page.context.close()


def sample_audit_pdf(browser: Browser, folder: Path) -> Path:
    """Print the synthetic audit's lines to a PDF, one visual line per fixture line."""
    source = SAMPLE_AUDIT.read_text()
    lines = source[source.index("`") + 1 : source.rindex("`")].split("\n")
    body = "".join(f"<div>{escape(line)}</div>" for line in lines)
    page = new_page(browser)
    page.set_content(f"<body style='font: 8px monospace; white-space: pre'>{body}</body>")
    path = folder / "sample-audit.pdf"
    page.pdf(path=str(path), format="Letter", landscape=True)
    page.context.close()
    return path


def degree_works_import(browser: Browser) -> None:
    with tempfile.TemporaryDirectory() as folder:
        pdf = sample_audit_pdf(browser, Path(folder))
        page = new_page(browser)
        page.goto(f"{BASE}/import")
        page.locator("input[type=file]").set_input_files(pdf)
        review = page.locator("section[aria-label='What Shortcut read from your audit']")
        expect(review).to_contain_text("Computer Science")
        card = page.locator("div.card").filter(has=review).first
        save(card, "degree-works-import.png")
        page.context.close()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with app_server(), sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            landing(browser)
            p1_accelerated(browser)
            p4_no_shortcut(browser)
            degree_works_import(browser)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
