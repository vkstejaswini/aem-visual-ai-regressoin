"""Defaults and environment overrides for capture, comparison, and Ollama."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v.strip() if v and v.strip() else default


@dataclass(frozen=True)
class CaptureOptions:
    """Playwright navigation settings (passed into the capture subprocess).

    ``wait_until`` is forwarded to Playwright ``page.goto`` (e.g. load, domcontentloaded).
    """

    nav_timeout_ms: int = 60_000
    post_load_wait_ms: int = 5_000
    wait_until: str = "load"
    process_join_timeout_s: float = 300.0

    @staticmethod
    def from_env() -> CaptureOptions:
        return CaptureOptions(
            nav_timeout_ms=_env_int("CAPTURE_NAV_TIMEOUT_MS", 60_000),
            post_load_wait_ms=_env_int("CAPTURE_POST_LOAD_WAIT_MS", 5_000),
            wait_until=_env_str("CAPTURE_WAIT_UNTIL", "load"),
            process_join_timeout_s=float(
                _env_int("CAPTURE_PROCESS_JOIN_TIMEOUT_S", 300) or 300
            ),
        )


def default_screenshots_dir() -> str:
    return _env_str("SCREENSHOTS_DIR", "screenshots")


def ollama_host() -> str:
    return _env_str("OLLAMA_HOST", "http://127.0.0.1:11434")


def ollama_vision_model() -> str:
    return _env_str("OLLAMA_VISION_MODEL", "llama3.2-vision")


def ssim_pass_threshold() -> float:
    """Raw SSIM above this value marks status PASS (default 0.95 → 95% on UI)."""
    raw = os.environ.get("SSIM_PASS_THRESHOLD")
    if raw is None or not str(raw).strip():
        return 0.95
    try:
        return float(raw)
    except ValueError:
        return 0.95
