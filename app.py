import json
import os
import time
from urllib.parse import unquote

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from core.config import (
    CaptureOptions,
    default_screenshots_dir,
    ollama_host,
    ollama_vision_model,
)
from core.llm import describe_ollama_connection
from core.pipeline import run_regression_row
from core.reporting import generate_report

_COMPARE_COLS = ["Name", "Base Link", "Test Link"]


def _urls_from_query_params() -> list[str]:
    qp = st.query_params
    if "urls" not in qp:
        return []
    getter = getattr(qp, "get_all", None)
    parts = qp.get_all("urls") if callable(getter) else [qp["urls"]]
    out: list[str] = []
    for raw in parts:
        out.extend(
            unquote(p.strip())
            for p in str(raw).split(",")
            if p.strip()
        )
    return out


def _one_empty_compare_row() -> pd.DataFrame:
    return pd.DataFrame([{c: "" for c in _COMPARE_COLS}], columns=_COMPARE_COLS)


def _migrate_legacy_compare_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename old column names once; avoid reindex/copy on every run (prevents editor glitches)."""
    rename_map = {}
    if "Baseline" in df.columns:
        rename_map["Baseline"] = "Base Link"
    if "Test" in df.columns and "Test Link" not in df.columns:
        rename_map["Test"] = "Test Link"
    if rename_map:
        df = df.rename(columns=rename_map)
    if list(df.columns) != _COMPARE_COLS:
        df = df.reindex(columns=_COMPARE_COLS, fill_value="")
    return df


def _coerce_compare_df_for_editor(df: pd.DataFrame) -> pd.DataFrame:
    """RangeIndex + plain strings for every cell (Glide loses edits on blur if dtype/index drift)."""
    if df is None or len(df) == 0:
        return _one_empty_compare_row()
    work = df.reindex(columns=_COMPARE_COLS, fill_value="")
    work = work.reset_index(drop=True)
    work = work.fillna("")
    for c in _COMPARE_COLS:
        work[c] = work[c].map(lambda v: "" if v is None else str(v))
    return work


def _finalize_compare_edits(df: pd.DataFrame | None) -> pd.DataFrame:
    """After data_editor: enforce min one row only (editor already uses correct columns)."""
    if df is None or not isinstance(df, pd.DataFrame) or len(df) == 0:
        return _one_empty_compare_row()
    return df


def _maybe_migrate_compare_session() -> None:
    """Only touch session_state.compare_df when legacy/wrong columns are detected."""
    df = st.session_state.compare_df
    wrong = (
        "Baseline" in df.columns
        or ("Test" in df.columns and "Test Link" not in df.columns)
        or list(df.columns) != _COMPARE_COLS
    )
    if wrong:
        st.session_state.compare_df = _migrate_legacy_compare_columns(df)


def _initial_compare_dataframe() -> pd.DataFrame:
    urls = _urls_from_query_params()
    if len(urls) >= 2:
        return pd.DataFrame(
            [
                {
                    "Name": "from-url",
                    "Base Link": urls[0],
                    "Test Link": urls[1],
                }
            ],
            columns=_COMPARE_COLS,
        )
    return _one_empty_compare_row()


def _iter_complete_rows(df: pd.DataFrame):
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        name = str(row.get("Name", "") or "").strip()
        baseline_url = str(row.get("Base Link", "") or "").strip()
        test_url = str(row.get("Test Link", "") or "").strip()
        if not name and not baseline_url and not test_url:
            continue
        if not name or not baseline_url or not test_url:
            yield i, None, (
                f"**Row {i}** is incomplete — fill **Name**, **Base Link**, and **Test Link**."
            )
            continue
        yield i, (name, baseline_url, test_url), None


def _format_elapsed(seconds: float) -> str:
    """Human-readable elapsed time for progress text."""
    if seconds < 0:
        return "0.0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds + 0.5), 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


# Client-side timer: white on dark; stops when `_broadcast_stop_live_timer` runs.
_LIVE_ELAPSED_TIMER_HTML = """
<div id="avr-live-wrap" style="font-family:system-ui,sans-serif;font-size:1.05rem;background:#1a1c24;border:1px solid #3d4050;border-radius:8px;padding:10px 16px;display:inline-block;color:#ffffff;">
  <span id="avr-live-label" style="opacity:0.9;color:#ffffff;">Live elapsed</span>
  <strong id="avr-live-elapsed" style="margin-left:0.5rem;color:#ffffff;">0.0s</strong>
</div>
<script>
(function () {
  var el = document.getElementById("avr-live-elapsed");
  var label = document.getElementById("avr-live-label");
  if (!el) return;
  var t0 = performance.now();
  var iv = null;
  function fmt(sec) {
    if (sec < 60) return (Math.round(sec * 10) / 10).toFixed(1) + "s";
    var m = Math.floor(sec / 60);
    var s = Math.round(sec - m * 60);
    if (m < 60) return m + "m " + String(s).padStart(2, "0") + "s";
    var h = Math.floor(m / 60);
    var mm = m % 60;
    return h + "h " + String(mm).padStart(2, "0") + "m " + String(s).padStart(2, "0") + "s";
  }
  function tick() {
    el.textContent = fmt((performance.now() - t0) / 1000);
  }
  iv = setInterval(tick, 100);
  tick();
  window.addEventListener("message", function (ev) {
    if (!ev.data || ev.data.type !== "avr-stop") return;
    if (iv !== null) {
      clearInterval(iv);
      iv = null;
    }
    el.textContent = ev.data.final;
    if (label) label.textContent = "Total time";
  });
})();
</script>
"""


def _broadcast_stop_live_timer(final_display: str) -> str:
    """Notify all Streamlit component frames to stop the live timer and show final time."""
    final_js = json.dumps(final_display)
    return f"""
<script>
(function () {{
  var msg = {{ type: "avr-stop", final: {final_js} }};
  function postAll(root) {{
    try {{
      if (!root || !root.frames) return;
      for (var i = 0; i < root.frames.length; i++) {{
        try {{ root.frames[i].postMessage(msg, "*"); }} catch (e) {{}}
      }}
    }} catch (e) {{}}
  }}
  postAll(window.top);
  postAll(window.parent);
}})();
</script>
"""


st.title("AEM Visual AI Regression Tool")

st.subheader("Pages to compare")
st.caption(
    "One row per page: **Name**, **Base Link** (reference URL), and **Test Link** (URL under test). "
    "Optional: open with `?urls=<base>&urls=<test>` or comma-separated values. "
    "The table **starts with one row**. Use the editor **toolbar** for add/delete rows. "
    "If **paste** does not stay in the grid, use **Paste links into table** below."
)

with st.sidebar:
    st.header("Capture")
    nav_timeout_s = st.number_input("Navigation timeout (s)", 5, 600, 60)
    post_load_s = st.number_input("Extra wait after load (s)", 0, 120, 5)
    wait_until = st.selectbox(
        "Page load strategy",
        ("load", "domcontentloaded", "networkidle", "commit"),
        index=0,
        help="AEM sites often need `domcontentloaded` or `load` instead of `networkidle`.",
    )
    capture_deadline_s = st.number_input(
        "Max capture time per row (s)",
        60,
        3600,
        300,
        help="Subprocess join timeout; increase for very long pages.",
    )

    st.header("Comparison")
    pass_ssim = st.slider(
        "PASS if SSIM ≥",
        min_value=0.85,
        max_value=0.99,
        value=0.95,
        step=0.01,
        help="Structural similarity threshold (scalar from scikit-image).",
    )

    st.header("Ollama")
    host_in = st.text_input("Host", value=ollama_host())
    vision_model_in = st.text_input("Vision model", value=ollama_vision_model())
    use_vision = st.checkbox("Use vision model", value=True)
    if st.button("Test Ollama connection"):
        st.info(describe_ollama_connection(host_in))

    st.header("Report")
    save_to_disk = st.checkbox(
        "Also save report.xlsx / report.csv next to the app",
        value=False,
    )

if "compare_df" not in st.session_state:
    st.session_state.compare_df = _initial_compare_dataframe()

_maybe_migrate_compare_session()

with st.expander("Paste links into table (fixes grid paste / long URLs)", expanded=False):
    st.markdown(
        "The spreadsheet grid sometimes **drops pastes** until the cell fully commits. "
        "Paste here, pick the row number, then **Apply** — values are written straight into the table data."
    )

    _nrows_now = max(1, len(st.session_state.compare_df))
    _paste_target = st.number_input(
        "Table row #",
        min_value=1,
        max_value=max(50, _nrows_now),
        value=1,
        step=1,
        key="paste_target_row_1based",
        help="1 = first row. **Apply** can extend the table if you pick a higher number.",
    )
    st.text_input(
        "Name (paste field)",
        key="clipboard_name",
        placeholder="e.g. homepage",
    )
    st.text_area(
        "Base Link — paste here",
        key="clipboard_base",
        height=90,
        placeholder="https://…",
    )
    st.text_area(
        "Test Link — paste here",
        key="clipboard_test",
        height=90,
        placeholder="https://…",
    )
    if st.button("Apply → table", type="primary", key="clipboard_apply"):
        ix = int(_paste_target) - 1
        name_v = str(st.session_state.get("clipboard_name", "") or "").strip()
        base_v = str(st.session_state.get("clipboard_base", "") or "").strip()
        test_v = str(st.session_state.get("clipboard_test", "") or "").strip()
        df_w = _coerce_compare_df_for_editor(st.session_state.compare_df).copy()
        while len(df_w) <= ix:
            df_w = pd.concat([df_w, _one_empty_compare_row()], ignore_index=True)
        df_w.at[ix, "Name"] = name_v
        df_w.at[ix, "Base Link"] = base_v
        df_w.at[ix, "Test Link"] = test_v
        st.session_state.compare_df = _coerce_compare_df_for_editor(df_w)
        st.toast(f"Updated row {ix + 1} in the table.")
        st.rerun()

# Pass a fresh coerced copy into the widget; do not assign this back to session before the
# editor (avoids clearing cells when focusing another field — see streamlit/issues re: Glide).
_compare_display_df = _coerce_compare_df_for_editor(st.session_state.compare_df).copy()
_row_ct = max(1, len(_compare_display_df))
# Toolbar (search, CSV, columns, fullscreen) includes add/delete row when num_rows="dynamic".
_editor_height = min(480, max(140, 92 + _row_ct * 40))

edited = st.data_editor(
    _compare_display_df,
    num_rows="dynamic",
    height=_editor_height,
    row_height=36,
    use_container_width=True,
    column_config={
        "Name": st.column_config.TextColumn(
            "Name",
            help="Label for this comparison (used in screenshots and report).",
            width="small",
            max_chars=80,
        ),
        "Base Link": st.column_config.TextColumn(
            "Base Link",
            help="Reference page URL (e.g. production).",
            width="large",
            max_chars=2048,
        ),
        "Test Link": st.column_config.TextColumn(
            "Test Link",
            help="Page URL to compare against the base link.",
            width="large",
            max_chars=2048,
        ),
    },
    hide_index=True,
    key="compare_pages_name_baseline_test",
)
st.session_state.compare_df = _coerce_compare_df_for_editor(
    _finalize_compare_edits(
        edited if edited is not None else st.session_state.compare_df
    )
)

st.caption(
    "Grid tip: **double-click** a cell to edit, paste, then press **Enter** or **Tab** "
    "so the value commits before you leave the cell."
)

capture_options = CaptureOptions(
    nav_timeout_ms=int(nav_timeout_s * 1000),
    post_load_wait_ms=int(post_load_s * 1000),
    wait_until=wait_until,
    process_join_timeout_s=float(capture_deadline_s),
)

if st.button("Run Test"):
    results: list = []

    if edited is None or edited.empty:
        st.warning("Add at least one row with Name, Base Link, and Test Link.")
    else:
        rows_to_run: list[tuple[str, str, str]] = []
        errors: list[str] = []
        for i, payload, err in _iter_complete_rows(edited):
            if err:
                errors.append(err)
            elif payload:
                rows_to_run.append(payload)
        for e in errors:
            st.error(e)

        if not rows_to_run:
            st.warning(
                "No complete rows to process. Fill all three fields in at least one row."
            )
        else:
            run_started = time.perf_counter()
            st.markdown(
                "**Overall run timer** (below, real time). Each row also has its own status "
                "and timing in the **result** block."
            )
            components.html(_LIVE_ELAPSED_TIMER_HTML, height=64)
            progress = st.progress(
                0,
                text=f"Starting… (elapsed {_format_elapsed(0)})",
            )
            shot_dir = default_screenshots_dir()
            nrows = len(rows_to_run)

            for idx, (name, baseline_url, test_url) in enumerate(rows_to_run):
                step = idx + 1
                elapsed = time.perf_counter() - run_started
                progress.progress(
                    (idx) / nrows,
                    text=(
                        f"Starting row {step}/{nrows}: {name} — "
                        f"total {_format_elapsed(elapsed)}"
                    ),
                )
                st.divider()
                st.markdown(f"#### Row {step} of {nrows}: **{name}**")

                result = None
                row_elapsed = 0.0
                row_t0 = time.perf_counter()

                with st.status(
                    f"Row {step}/{nrows} — **{name}** (capture · compare · LLM)…",
                    expanded=True,
                    state="running",
                ) as row_status:
                    st.caption(
                        "Timer here is for **this row only**. "
                        "The white panel above tracks the **whole run**."
                    )
                    try:
                        result = run_regression_row(
                            name,
                            baseline_url,
                            test_url,
                            screenshots_dir=shot_dir,
                            capture_options=capture_options,
                            ollama_host=host_in,
                            vision_model=vision_model_in,
                            use_vision_llm=use_vision,
                            ssim_pass_threshold=pass_ssim,
                        )
                        row_elapsed = time.perf_counter() - row_t0
                        row_status.update(
                            label=(
                                f"Row {step} completed in "
                                f"{_format_elapsed(row_elapsed)}"
                            ),
                            state="complete",
                            expanded=False,
                        )
                    except (TimeoutError, RuntimeError) as exc:
                        row_elapsed = time.perf_counter() - row_t0
                        row_status.update(
                            label=(
                                f"Row {step} stopped after "
                                f"{_format_elapsed(row_elapsed)}"
                            ),
                            state="error",
                            expanded=True,
                        )
                        st.error(f"{name}: {exc}")

                done_elapsed = time.perf_counter() - run_started
                progress.progress(
                    step / nrows,
                    text=(
                        f"Row {step}/{nrows} finished — "
                        f"total {_format_elapsed(done_elapsed)}"
                    ),
                )

                if result is not None:
                    result["row_duration_sec"] = round(row_elapsed, 2)
                    results.append(result)

                    total_s = time.perf_counter() - run_started
                    avg_s = total_s / step
                    _banner = st.success if step % 2 == 1 else st.info
                    _banner(
                        f"**Row {step} duration:** {_format_elapsed(row_elapsed)} · "
                        f"**Run total:** {_format_elapsed(total_s)} · "
                        f"**Average per row:** {_format_elapsed(avg_s)}"
                    )
                    t_a, t_b, t_c = st.columns(3)
                    with t_a:
                        st.metric(
                            f"This row ({step})",
                            _format_elapsed(row_elapsed),
                            help="Screenshots + SSIM + vision LLM for this row.",
                        )
                    with t_b:
                        st.metric(
                            "Cumulative run",
                            _format_elapsed(total_s),
                            help="Wall time since Run Test.",
                        )
                    with t_c:
                        st.metric(
                            "Avg / row (so far)",
                            _format_elapsed(avg_s),
                            help="Total elapsed ÷ completed rows.",
                        )

                    metric_keys = (
                        "similarity",
                        "status",
                        "structural_diff_pct",
                        "hotspot_area_pct",
                        "mean_pixel_diff",
                        "compared_width_px",
                        "compared_height_px",
                        "row_duration_sec",
                        "diff_heatmap_path",
                    )
                    compare_metrics = {
                        k: result[k] for k in metric_keys if k in result
                    }

                    st.image(
                        [
                            result["baseline_screenshot_path"],
                            result["test_screenshot_path"],
                        ],
                        caption=["Base Link", "Test Link"],
                        use_container_width=True,
                    )
                    if result.get("diff_heatmap_path"):
                        st.image(
                            result["diff_heatmap_path"],
                            caption=(
                                "Difference overlay (averaged baseline/test "
                                "with red tint where structure differs)"
                            ),
                            use_container_width=True,
                        )
                    st.json(compare_metrics)
                    st.write("AI Analysis:")
                    st.write(result["llm_analysis"])

            total_elapsed = time.perf_counter() - run_started
            progress.progress(
                1.0,
                text=(
                    f"Done — {_format_elapsed(total_elapsed)} total "
                    f"({len(results)}/{nrows} row(s) completed)"
                ),
            )
            components.html(
                _broadcast_stop_live_timer(_format_elapsed(total_elapsed)),
                height=1,
            )

            if results:
                persist_xlsx = (
                    os.path.abspath("report.xlsx") if save_to_disk else None
                )
                persist_csv = (
                    os.path.abspath("report.csv") if save_to_disk else None
                )
                _, report_xlsx = generate_report(
                    results,
                    persist_xlsx_path=persist_xlsx,
                    persist_csv_path=persist_csv,
                )
                st.caption(
                    "Download includes **Excel (.xlsx)** with screenshots embedded as images "
                    "(not base64). Plain CSV cannot embed binary pictures in cells."
                )
                if save_to_disk:
                    st.caption(
                        f"Also wrote **{persist_xlsx}** and **{persist_csv}**."
                    )
                st.download_button(
                    "Download Report (Excel)",
                    report_xlsx,
                    "report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
