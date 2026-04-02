import os
import tempfile

import numpy as np
from PIL import Image

from core.compare import compare_images


def test_compare_images_metrics_sum_to_100():
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "a.png")
    p2 = os.path.join(d, "b.png")
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(p1)
    Image.fromarray(np.ones((32, 32), dtype=np.uint8) * 40).save(p2)
    out = compare_images(p1, p2)
    assert "similarity" in out and "structural_diff_pct" in out
    assert abs(out["similarity"] + out["structural_diff_pct"] - 100.0) < 0.2


def test_pass_threshold_respected():
    d = tempfile.mkdtemp()
    p1 = os.path.join(d, "a.png")
    p2 = os.path.join(d, "b.png")
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(p1)
    Image.fromarray(np.zeros((32, 32), dtype=np.uint8)).save(p2)
    out = compare_images(p1, p2, pass_threshold=0.99)
    assert out["status"] == "PASS"
