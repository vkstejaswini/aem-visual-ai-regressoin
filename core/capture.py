"""Full-page screenshots via Playwright (subprocess on Windows for asyncio compatibility)."""

from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
from typing import TYPE_CHECKING

from .config import CaptureOptions, default_screenshots_dir

if TYPE_CHECKING:
    pass


def _playwright_capture_worker(payload: tuple) -> None:
    """Run sequential navigations in one browser session."""
    jobs, nav_timeout_ms, post_load_wait_ms, wait_until = payload

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        print(f"[capture] Playwright import failed: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                for url, path in jobs:
                    parent = os.path.dirname(path) or "."
                    os.makedirs(parent, exist_ok=True)
                    page.goto(
                        url, timeout=nav_timeout_ms, wait_until=wait_until
                    )
                    page.wait_for_timeout(post_load_wait_ms)
                    page.screenshot(path=path, full_page=True)
            finally:
                browser.close()
    except Exception:
        traceback.print_exc()
        sys.exit(1)


def _run_capture_jobs(
    jobs: list[tuple[str, str]],
    options: CaptureOptions,
) -> None:
    if not jobs:
        raise ValueError("No capture jobs")
    payload = (
        jobs,
        options.nav_timeout_ms,
        options.post_load_wait_ms,
        options.wait_until,
    )
    ctx = multiprocessing.get_context("spawn")
    proc = ctx.Process(target=_playwright_capture_worker, args=(payload,))
    proc.start()
    proc.join(timeout=options.process_join_timeout_s)
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=15)
        raise TimeoutError(
            f"Screenshot capture exceeded {options.process_join_timeout_s}s "
            "(see sidebar / CaptureOptions.process_join_timeout_s)."
        )
    if proc.exitcode != 0:
        raise RuntimeError(
            f"Screenshot capture failed (exit {proc.exitcode}). "
            "Ensure Playwright browsers are installed: playwright install chromium"
        )


def capture_comparison_pair(
    baseline_url: str,
    test_url: str,
    name: str,
    *,
    screenshots_dir: str | None = None,
    options: CaptureOptions | None = None,
) -> tuple[str, str]:
    """Capture baseline and test URLs in one browser session. Returns absolute PNG paths."""
    options = options or CaptureOptions()
    base_root = os.path.abspath(screenshots_dir or default_screenshots_dir())
    os.makedirs(base_root, exist_ok=True)
    baseline_path = os.path.join(base_root, f"{name}_baseline.png")
    test_path = os.path.join(base_root, f"{name}_test.png")
    _run_capture_jobs(
        [(baseline_url, baseline_path), (test_url, test_path)],
        options,
    )
    return baseline_path, test_path


def capture_screenshot(
    url: str,
    name: str,
    *,
    screenshots_dir: str | None = None,
    options: CaptureOptions | None = None,
) -> str:
    """Capture a single URL (one subprocess, one browser session)."""
    options = options or CaptureOptions()
    base_root = os.path.abspath(screenshots_dir or default_screenshots_dir())
    os.makedirs(base_root, exist_ok=True)
    path = os.path.join(base_root, f"{name}.png")
    _run_capture_jobs([(url, path)], options)
    return path
