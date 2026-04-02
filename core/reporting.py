import os
from io import BytesIO

import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment

# Text column order for the sheet (images sit in dedicated columns; paths are not written as cells).
_REPORT_TEXT_COLUMNS = [
    "name",
    "baseline_url",
    "test_url",
    "similarity",
    "status",
    "structural_diff_pct",
    "hotspot_area_pct",
    "mean_pixel_diff",
    "compared_width_px",
    "compared_height_px",
    "llm_analysis",
]

_PATH_KEYS = frozenset(
    {"baseline_screenshot_path", "test_screenshot_path", "diff_heatmap_path"}
)

_IMG_MAX_WIDTH_PX = 420


def _ordered_row_dict(r: dict) -> dict:
    head = {k: r.get(k) for k in _REPORT_TEXT_COLUMNS}
    rest = {
        k: v
        for k, v in r.items()
        if k not in _REPORT_TEXT_COLUMNS and k not in _PATH_KEYS
    }
    return {**head, **rest}


def _scale_xl_image(path: str) -> XLImage:
    img = XLImage(path)
    w, h = img.width, img.height
    if w and w > _IMG_MAX_WIDTH_PX:
        scale = _IMG_MAX_WIDTH_PX / w
        img.width = int(w * scale)
        img.height = int(h * scale)
    return img


def _build_workbook(results: list) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Regression"

    # A1..N1: text headers; C,E,F reserved for images (labels only)
    headers = [
        "name",
        "baseline_url",
        "Baseline screenshot",
        "test_url",
        "Test screenshot",
        "Diff overlay",
        "similarity",
        "status",
        "structural_diff_pct",
        "hotspot_area_pct",
        "mean_pixel_diff",
        "compared_width_px",
        "compared_height_px",
        "llm_analysis",
    ]
    for col, h in enumerate(headers, start=1):
        ws.cell(row=1, column=col, value=h)

    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 52
    ws.column_dimensions["D"].width = 46
    ws.column_dimensions["E"].width = 52
    ws.column_dimensions["F"].width = 52
    for c in "GHIJKLM":
        ws.column_dimensions[c].width = 14
    ws.column_dimensions["N"].width = 72

    for i, r in enumerate(results):
        row = 2 + i
        ws.row_dimensions[row].height = 240

        ws.cell(row=row, column=1, value=r.get("name"))
        ws.cell(row=row, column=2, value=r.get("baseline_url"))
        ws.cell(row=row, column=4, value=r.get("test_url"))

        ws.cell(row=row, column=7, value=r.get("similarity"))
        ws.cell(row=row, column=8, value=r.get("status"))
        ws.cell(row=row, column=9, value=r.get("structural_diff_pct"))
        ws.cell(row=row, column=10, value=r.get("hotspot_area_pct"))
        ws.cell(row=row, column=11, value=r.get("mean_pixel_diff"))
        ws.cell(row=row, column=12, value=r.get("compared_width_px"))
        ws.cell(row=row, column=13, value=r.get("compared_height_px"))
        llm_cell = ws.cell(row=row, column=14, value=r.get("llm_analysis"))
        llm_cell.alignment = Alignment(wrap_text=True, vertical="top")

        b_path = r.get("baseline_screenshot_path")
        t_path = r.get("test_screenshot_path")
        d_path = r.get("diff_heatmap_path")

        if b_path and os.path.isfile(b_path):
            bi = _scale_xl_image(b_path)
            ws.add_image(bi, f"C{row}")
        if t_path and os.path.isfile(t_path):
            ti = _scale_xl_image(t_path)
            ws.add_image(ti, f"E{row}")
        if d_path and os.path.isfile(d_path):
            di = _scale_xl_image(d_path)
            ws.add_image(di, f"F{row}")

    return wb


def generate_report(results: list) -> tuple[pd.DataFrame, bytes]:
    """Build a text-only DataFrame and an .xlsx file with PNGs embedded (not base64)."""
    row_dicts = [_ordered_row_dict(r) for r in results]
    df = pd.DataFrame(row_dicts)
    head = [c for c in _REPORT_TEXT_COLUMNS if c in df.columns]
    tail = [c for c in df.columns if c not in head]
    df = df[head + tail]

    wb = _build_workbook(results)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    data = buf.getvalue()
    wb.save("report.xlsx")
    df.to_csv("report.csv", index=False)
    return df, data
