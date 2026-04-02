"""End-to-end comparison: capture pair → SSIM metrics → optional LLM summary."""

from __future__ import annotations

import os
from typing import Any

from .capture import capture_comparison_pair
from .compare import compare_images
from .config import CaptureOptions, default_screenshots_dir
from .llm import analyze_with_llm


def run_regression_row(
    name: str,
    baseline_url: str,
    test_url: str,
    *,
    screenshots_dir: str | None = None,
    capture_options: CaptureOptions | None = None,
    ollama_host: str | None = None,
    vision_model: str | None = None,
    use_vision_llm: bool = True,
    ssim_pass_threshold: float | None = None,
) -> dict[str, Any]:
    root = screenshots_dir or default_screenshots_dir()
    capture_options = capture_options or CaptureOptions()

    baseline_img, test_img = capture_comparison_pair(
        baseline_url,
        test_url,
        name,
        screenshots_dir=root,
        options=capture_options,
    )

    diff_path = os.path.join(os.path.abspath(root), f"diff_{name}.png")
    compare_result = compare_images(
        baseline_img,
        test_img,
        diff_save_path=diff_path,
        pass_threshold=ssim_pass_threshold,
    )
    if compare_result.get("diff_heatmap_path"):
        compare_result = {
            **compare_result,
            "diff_heatmap_path": os.path.abspath(
                compare_result["diff_heatmap_path"]
            ),
        }

    if use_vision_llm:
        llm_output = analyze_with_llm(
            baseline_img,
            test_img,
            host=ollama_host,
            model=vision_model,
        )
    else:
        llm_output = "[Vision LLM skipped] Enable “Use vision model” in the sidebar for AI analysis."

    return {
        "name": name,
        "baseline_url": baseline_url,
        "baseline_screenshot_path": os.path.abspath(baseline_img),
        "test_url": test_url,
        "test_screenshot_path": os.path.abspath(test_img),
        **compare_result,
        "llm_analysis": llm_output,
    }
