"""Drive the running app with Playwright: set up the slide design, record the demo video and take screenshots.

Usage: python capture.py <work_dir> <app_url>   (called by make.sh)

Expects bg.jpg and logo.png in work_dir. Writes there:
  video/*.webm      demo flow (Termin-Folien)
  demo.pdf          the PDF exported at the end of the flow
  agenda.png        Agenda page, first event expanded
  dienstplan.png    Dienstplan page
"""

import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

WORK = Path(sys.argv[1])
BASE = sys.argv[2].rstrip("/")
# The sample data in fake_churchtools.py lies in the week after this date ("Diese Woche" = 15.-22.11.2026)
NOW = datetime(2026, 11, 13, 10, 0)
DEMO_SIZE = {"width": 580, "height": 820}  # below the 600px breakpoint: one column, large slide preview
CUSTOM_TEXT = "Taufe von Emma und Paul. Anschließend Kirchenkaffee."


def new_page(browser, **options) -> Page:
    page = browser.new_context(locale="de-DE", timezone_id="Europe/Berlin", **options).new_page()
    page.clock.set_system_time(NOW)
    return page


def login(page: Page) -> None:
    page.goto(BASE + "/")
    page.fill("#username", "maria")
    page.fill("#password", "demo")
    page.click("#login_submit")
    page.wait_for_load_state("networkidle")


def smooth_scroll(page: Page, y: float, ms: int = 900) -> None:
    page.evaluate(
        """([y, ms]) => new Promise(done => {
            const y0 = window.scrollY, t0 = performance.now();
            const step = t => {
                const k = Math.min(1, (t - t0) / ms), e = k < .5 ? 2*k*k : 1 - Math.pow(-2*k + 2, 2) / 2;
                window.scrollTo(0, y0 + (y - y0) * e);
                k < 1 ? requestAnimationFrame(step) : done();
            };
            requestAnimationFrame(step);
        })""",
        [y, ms],
    )


def scroll_to(page: Page, selector: str, offset: int = 90, ms: int = 900) -> None:
    y = page.locator(selector).first.evaluate(f"e => e.getBoundingClientRect().top + window.scrollY - {offset}")
    smooth_scroll(page, y, ms)


def set_alpha(page: Page, value: int) -> None:
    page.fill("#alpha", str(value))
    page.dispatch_event("#alpha", "input")


def set_up_design(browser) -> dict:
    """Upload background and logo, set the colors, return the logged-in storage state."""
    page = new_page(browser, viewport={"width": 1280, "height": 860})
    login(page)
    page.click("#this-week")
    page.wait_for_timeout(1200)
    page.set_input_files("#bg_upload", WORK / "bg.jpg")
    page.wait_for_timeout(800)
    page.set_input_files("#logo_upload", WORK / "logo.png")
    page.wait_for_timeout(800)
    # Light box: slide titles are always black, so a dark box would make them unreadable
    for field, color in (
        ("#background_color", "#ffffff"),
        ("#date_color", "#a8441b"),
        ("#description_color", "#3a3a3a"),
    ):
        page.fill(field, color)
        page.dispatch_event(field, "input")
    set_alpha(page, 225)
    # Colors are saved with an export
    with page.expect_download():
        page.click("#generate_pdf_btn")
    state = page.context.storage_state()
    page.context.close()
    return state


def record_demo(browser, state: dict) -> None:
    page = new_page(
        browser,
        viewport=DEMO_SIZE,
        storage_state=state,
        record_video_dir=WORK / "video",
        record_video_size=DEMO_SIZE,
    )
    page.goto(BASE + "/appointments")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    page.click("#this-week")
    page.wait_for_timeout(1800)

    # Custom text for the first appointment
    scroll_to(page, ".appointment-item", offset=140)
    page.wait_for_timeout(400)
    page.locator(".appointment-item").first.locator('button[data-action="edit-custom-text"]').click()
    page.wait_for_timeout(400)
    page.keyboard.type(CUSTOM_TEXT, delay=45)
    page.wait_for_timeout(700)
    page.locator("textarea:visible").blur()
    page.wait_for_timeout(700)

    # Leave out the choir rehearsal
    choir = page.locator(".appointment-item", has_text="Probe Gospelchor")
    smooth_scroll(page, choir.evaluate("e => e.getBoundingClientRect().top + window.scrollY - 260"), 800)
    page.wait_for_timeout(300)
    choir.locator('input[type="checkbox"]').click()
    page.wait_for_timeout(1200)

    # Design: the preview shows the first appointment with the custom text
    scroll_to(page, "#design_card", offset=20)
    page.click("#design_card summary")
    page.wait_for_timeout(500)
    scroll_to(page, "#design_card", offset=20, ms=600)
    page.wait_for_timeout(1000)
    for color in ("#2f6b4f", "#1f4e79", "#a8441b"):
        page.fill("#date_color", color)
        page.dispatch_event("#date_color", "input")
        page.wait_for_timeout(900)
    for alpha in [*range(225, 150, -15), *range(150, 226, 15)]:
        set_alpha(page, alpha)
        page.wait_for_timeout(120)
    page.wait_for_timeout(800)

    page.hover("#generate_pdf_btn")
    page.wait_for_timeout(400)
    with page.expect_download() as download:
        page.click("#generate_pdf_btn")
    download.value.save_as(WORK / "demo.pdf")
    page.wait_for_timeout(1200)
    page.context.close()


def take_screenshots(browser, state: dict) -> None:
    page = new_page(browser, viewport={"width": 430, "height": 900}, device_scale_factor=2, storage_state=state)
    for path, image, card in (("agenda", "agenda", ".event-card"), ("services", "dienstplan", ".service-card")):
        page.goto(f"{BASE}/{path}")
        page.wait_for_load_state("networkidle")
        page.click("#this-week")
        page.wait_for_timeout(1200)
        if path == "agenda":
            page.locator(".event-card-header").first.click()
        page.wait_for_timeout(1500)
        page.evaluate(f"scrollTo(0, document.querySelector('{card}').getBoundingClientRect().top + scrollY - 90)")
        page.wait_for_timeout(500)
        page.screenshot(path=WORK / f"{image}.png")
    page.context.close()


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        state = set_up_design(browser)
        record_demo(browser, state)
        take_screenshots(browser, state)
        browser.close()


if __name__ == "__main__":
    main()
