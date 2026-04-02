import os

from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity as ssim

# Pixels with local (1 - SSIM) above this count as a “hotspot” for area %.
_HOTSPOT_THRESHOLD = 0.15

# Pad shorter screenshot to match full canvas (typical browser background).
_PAD_GRAY = 255
_PAD_RGB = (255, 255, 255)

# Diff overlay: max red tint (0–1) per pixel so page content stays visible.
_DIFF_OVERLAY_MAX_ALPHA = 0.72

# Gamma < 1 lifts low dissimilarity so small UI shifts show a visible tint.
_DIFF_OVERLAY_GAMMA = 0.5


def _pad_gray(pil_img: Image.Image, width: int, height: int) -> np.ndarray:
    """Top-left align image on a WxH canvas; padding fills the rest."""
    g = pil_img.convert("L")
    w, h = g.size
    out = np.full((height, width), _PAD_GRAY, dtype=np.uint8)
    out[0:h, 0:w] = np.asarray(g, dtype=np.uint8)
    return out


def _pad_rgb_float(pil_img: Image.Image, width: int, height: int) -> np.ndarray:
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    out = np.full((height, width, 3), _PAD_RGB, dtype=np.float32)
    out[0:h, 0:w] = np.asarray(rgb, dtype=np.float32)
    return out


def _save_diff_overlay(
    pil1: Image.Image,
    pil2: Image.Image,
    width: int,
    height: int,
    dissim: np.ndarray,
    diff_save_path: str,
) -> None:
    """Blend full-canvas baseline/test RGB with a red highlight where SSIM dissimilarity is high."""
    rgb1 = _pad_rgb_float(pil1, width, height)
    rgb2 = _pad_rgb_float(pil2, width, height)
    base = (rgb1 + rgb2) / 2.0

    strength = np.clip(dissim, 0.0, 1.0) ** _DIFF_OVERLAY_GAMMA
    alpha = (strength * _DIFF_OVERLAY_MAX_ALPHA)[..., np.newaxis]
    highlight = np.array([255.0, 72.0, 72.0], dtype=np.float32)
    blended = base * (1.0 - alpha) + highlight * alpha

    os.makedirs(os.path.dirname(diff_save_path) or ".", exist_ok=True)
    Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8), mode="RGB").save(
        diff_save_path
    )


def compare_images(img1_path, img2_path, diff_save_path=None):
    pil1 = Image.open(img1_path)
    pil2 = Image.open(img2_path)

    w1, h1 = pil1.size
    w2, h2 = pil2.size
    width = max(w1, w2)
    height = max(h1, h2)

    a1 = _pad_gray(pil1, width, height)
    a2 = _pad_gray(pil2, width, height)

    score, ssim_map = ssim(a1, a2, full=True)

    dissim = np.clip(1.0 - ssim_map, 0.0, 1.0)
    structural_diff_pct = round(float(np.mean(dissim) * 100), 2)
    hotspot_area_pct = round(float(np.mean(dissim > _HOTSPOT_THRESHOLD) * 100), 2)
    mean_pixel_diff = round(
        float(np.mean(np.abs(a1.astype(np.float32) - a2.astype(np.float32)))), 2
    )

    out = {
        "similarity": round(score * 100, 2),
        "status": "PASS" if score > 0.95 else "FAIL",
        "structural_diff_pct": structural_diff_pct,
        "hotspot_area_pct": hotspot_area_pct,
        "mean_pixel_diff": mean_pixel_diff,
        "compared_width_px": width,
        "compared_height_px": height,
    }

    if diff_save_path:
        _save_diff_overlay(pil1, pil2, width, height, dissim, diff_save_path)
        out["diff_heatmap_path"] = diff_save_path

    return out
