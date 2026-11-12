"""Start the Streamlit app, take one fixed-viewport screenshot per page with headless Playwright, stop the app.

Usage: python -m scripts.screenshots [--fixture]
"""

import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

from campuspulse import config as C

PAGES = [("", "01-overview"), ("price", "02-price-vs-earnings"), ("florida", "03-florida"), ("model", "04-model")]
PORT, VIEWPORT = 8599, {"width": 1440, "height": 1800}


def main(fixture: bool) -> None:
    out = C.ROOT / "docs" / ("screenshots_fixture" if fixture else "")
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "CAMPUSPULSE_FIXTURE": "1" if fixture else "0"}
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(C.ROOT / "app/streamlit_app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(PORT),
            "--browser.gatherUsageStats",
            "false",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                if urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2).status == 200:
                    break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("Streamlit did not start")
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception:  # bundled browser missing: fall back to the installed Chrome
                browser = p.chromium.launch(channel="chrome")
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            for path, name in PAGES:
                page.goto(f"http://localhost:{PORT}/{path}", wait_until="networkidle")
                page.wait_for_selector("h1")
                page.wait_for_timeout(3000)  # let Plotly finish drawing
                if page.query_selector('[data-testid="stException"]'):
                    raise RuntimeError(f"Streamlit raised an exception on page {path}")
                page.screenshot(path=str(out / f"{name}.png"), full_page=True)
                print("wrote", (out / f"{name}.png").relative_to(C.ROOT))
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=15)


if __name__ == "__main__":
    main("--fixture" in sys.argv)
