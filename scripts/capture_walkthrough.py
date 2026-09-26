"""Capture real Streamlit screens and a browser walkthrough for project media.

Optional tooling: ``pip install playwright`` and a local Chromium/Edge browser.
Run against a healthy app: ``python -m scripts.capture_walkthrough --url http://localhost:8502``.
The WebM is an intermediate recording; README media production converts it to MP4.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright


PAGES = {
    "Overview": ("Every sale is a signal.", "dashboard.png"),
    "Analytics": ("Sales analytics", "analytics.png"),
    "Forecast lab": ("Forecast lab", "forecast.png"),
    "Inventory": ("Inventory intelligence", "inventory.png"),
    "Insights": ("Insights & alerts", "insights.png"),
    "Data studio": ("Data studio", "data-studio.png"),
    "Reports": ("Reports", "reports.png"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8502")
    parser.add_argument("--browser-path", default=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    parser.add_argument("--out", type=Path, default=Path("docs"))
    args = parser.parse_args()
    image_dir = args.out / "images"
    media_dir = args.out / "media"
    image_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    scenes: list[dict[str, object]] = []
    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.browser_path)
        context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1,
                                      record_video_dir=str(media_dir), record_video_size={"width": 1440, "height": 900},
                                      accept_downloads=True)
        page = context.new_page()
        page.on("pageerror", lambda exc: errors.append(f"page: {exc}"))
        page.on("console", lambda msg: errors.append(f"console: {msg.text}") if msg.type == "error" else None)
        started = time.monotonic()
        page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        page.get_by_role("heading", name=PAGES["Overview"][0]).wait_for(timeout=60000)
        assert page.title().startswith("RetailMind AI")

        def capture(name: str, *, seconds: float = 4.0) -> None:
            heading, filename = PAGES[name]
            page.get_by_role("heading", name=heading).wait_for(timeout=60000)
            if name == "Overview":
                page.locator(".signal-grid .signal-card").first.wait_for(timeout=60000)
            elif name == "Analytics":
                page.get_by_role("tab", name="Sales trends").wait_for(timeout=60000)
                page.locator(".evidence-panel").wait_for(state="detached", timeout=60000)
            elif name == "Forecast lab":
                page.get_by_role("button", name="Train and compare models").wait_for(timeout=60000)
            elif name == "Inventory":
                page.get_by_text("Inventory planning is unavailable").wait_for(timeout=60000)
            elif name == "Insights":
                page.get_by_role("button", name="Download alerts").wait_for(timeout=60000)
                page.locator(".insight").first.wait_for(timeout=60000)
            elif name == "Data studio":
                page.get_by_role("tab", name="Quality & lineage").wait_for(timeout=60000)
            elif name == "Reports":
                page.get_by_role("button", name="Sales dataset · CSV").wait_for(timeout=60000)
            page.wait_for_timeout(900)
            assert page.locator('[data-testid="stException"]').count() == 0, name
            page.screenshot(path=str(image_dir / filename), animations="disabled")
            scenes.append({"name": name, "start": round(time.monotonic() - started, 2), "image": filename})
            page.wait_for_timeout(int(seconds * 1000))

        def navigate(name: str) -> None:
            page.locator('[data-testid="stSidebar"] label[data-testid="stRadioOption"]').filter(has_text=name).click()

        capture("Overview", seconds=6)
        navigate("Analytics")
        capture("Analytics", seconds=5)
        navigate("Forecast lab")
        capture("Forecast lab", seconds=3)
        page.get_by_role("button", name="Train and compare models").click()
        page.get_by_text("Selected model", exact=True).wait_for(timeout=120000)
        assert page.get_by_text("Backtest WAPE", exact=True).count() > 0
        page.wait_for_timeout(900)
        page.screenshot(path=str(image_dir / "forecast-result.png"), animations="disabled")
        scenes.append({"name": "Measured forecast", "start": round(time.monotonic() - started, 2),
                       "image": "forecast-result.png"})
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Download forecast").click()
        forecast_file = media_dir / "forecast-qa.csv"
        download_info.value.save_as(forecast_file)
        assert forecast_file.read_text(encoding="utf-8").startswith("date,forecast,lower,upper")
        page.wait_for_timeout(7000)

        navigate("Inventory")
        capture("Inventory", seconds=5)
        assert page.get_by_text("Inventory planning is unavailable").count() > 0
        navigate("Insights")
        capture("Insights", seconds=5)
        navigate("Data studio")
        capture("Data studio", seconds=5)
        navigate("Reports")
        capture("Reports", seconds=5)
        with page.expect_download() as download_info:
            page.get_by_role("button", name="Sales dataset · CSV").click()
        sales_file = media_dir / "sales-qa.csv"
        download_info.value.save_as(sales_file)
        assert sum(1 for _ in sales_file.open(encoding="utf-8")) == 109651
        navigate("Overview")
        capture("Overview", seconds=3)
        video = page.video
        context.close()
        shutil.move(video.path(), media_dir / "walkthrough.webm")

        mobile = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile_page = mobile.new_page()
        mobile_page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
        mobile_page.get_by_role("heading", name="Every sale is a signal.").wait_for(timeout=60000)
        assert mobile_page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert mobile_page.locator('[data-testid="stSidebar"]').get_attribute("aria-expanded") == "false"
        mobile_page.screenshot(path=str(image_dir / "mobile.png"), animations="disabled")
        mobile_page.locator('[data-testid="stExpander"] summary').click()
        mobile_page.locator('[data-testid="stExpander"] details[open]').wait_for(timeout=10000)
        category = mobile_page.get_by_role("combobox", name="Category")
        category.click()
        option = mobile_page.get_by_role("option", name="HOBBIES")
        try:
            option.wait_for(timeout=5000)
        except PlaywrightTimeoutError:
            category.click()
            option.wait_for(timeout=10000)
        option.click()
        mobile_page.get_by_text("36,550 observations").wait_for(timeout=30000)
        assert mobile_page.get_by_text("25,194").count() > 0
        mobile.close()
        browser.close()

    assert not errors, errors
    (media_dir / "capture-manifest.json").write_text(json.dumps({"scenes": scenes, "checks": {
        "desktop_pages": list(PAGES), "forecast_csv": "downloaded and validated",
        "sales_csv_rows": 109650, "mobile_filter": "verified", "console_errors": errors,
    }}, indent=2) + "\n", encoding="utf-8")
    forecast_file.unlink()
    sales_file.unlink()
    print(f"Captured {len(PAGES)} pages, forecast result, mobile view, and {len(scenes)} video scenes.")


if __name__ == "__main__":
    main()
