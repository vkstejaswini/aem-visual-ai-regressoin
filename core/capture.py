import multiprocessing
import os
import sys


def _playwright_capture_worker(url: str, path: str) -> None:
    """Run in a child process so Playwright's asyncio subprocess transport works on Windows."""
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            page.screenshot(path=path, full_page=True)
        finally:
            browser.close()


def capture_screenshot(url: str, name: str) -> str:
    base = os.path.abspath("screenshots")
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, f"{name}.png")

    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_playwright_capture_worker, args=(url, path))
    proc.start()
    proc.join()

    if proc.exitcode != 0:
        raise RuntimeError(
            f"Screenshot capture failed (exit {proc.exitcode}). "
            "Ensure Playwright browsers are installed: playwright install chromium"
        )
    return path
