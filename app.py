import os

import pandas as pd
import streamlit as st

from core.capture import capture_screenshot
from core.compare import compare_images
from core.llm import analyze_with_llm
from core.reporting import generate_report

st.title("AEM Visual AI Regression Tool")

st.subheader("Pages to compare")
st.caption("One row per page: **Name**, **Baseline** (reference URL), and **Test** (URL under test).")

edited = st.data_editor(
    pd.DataFrame(
        [{"Name": "", "Baseline": "", "Test": ""}],
        columns=["Name", "Baseline", "Test"],
    ),
    num_rows="dynamic",
    column_config={
        "Name": st.column_config.TextColumn(
            "Name",
            help="Label for this comparison (used in screenshots and report).",
            width="medium",
        ),
        "Baseline": st.column_config.TextColumn(
            "Baseline",
            help="Reference page URL (e.g. production).",
            width="large",
        ),
        "Test": st.column_config.TextColumn(
            "Test",
            help="Page URL to compare against the baseline.",
            width="large",
        ),
    },
    hide_index=True,
    key="compare_pages_name_baseline_test",
)

if st.button("Run Test"):
    results = []

    if edited is None or edited.empty:
        st.warning("Add at least one row with Name, Baseline, and Test.")
    else:
        rows_to_run = []
        for i, (_, row) in enumerate(edited.iterrows(), start=1):
            name = str(row.get("Name", "") or "").strip()
            baseline_url = str(row.get("Baseline", "") or "").strip()
            test_url = str(row.get("Test", "") or "").strip()
            if not name and not baseline_url and not test_url:
                continue
            if not name or not baseline_url or not test_url:
                st.error(
                    f"**Row {i}** is incomplete — fill **Name**, **Baseline**, and **Test**."
                )
                continue
            rows_to_run.append((name, baseline_url, test_url))

        if not rows_to_run:
            st.warning("No complete rows to process. Fill all three fields in at least one row.")
        else:
            for name, baseline_url, test_url in rows_to_run:
                st.write(f"Processing: {name}")

                baseline_img = capture_screenshot(baseline_url, f"{name}_baseline")
                test_img = capture_screenshot(test_url, f"{name}_test")

                diff_path = os.path.join("screenshots", f"diff_{name}.png")
                compare_result = compare_images(
                    baseline_img, test_img, diff_save_path=diff_path
                )
                if compare_result.get("diff_heatmap_path"):
                    compare_result = {
                        **compare_result,
                        "diff_heatmap_path": os.path.abspath(
                            compare_result["diff_heatmap_path"]
                        ),
                    }
                llm_output = analyze_with_llm(baseline_img, test_img)

                result = {
                    "name": name,
                    "baseline_url": baseline_url,
                    "baseline_screenshot_path": os.path.abspath(baseline_img),
                    "test_url": test_url,
                    "test_screenshot_path": os.path.abspath(test_img),
                    **compare_result,
                    "llm_analysis": llm_output,
                }

                results.append(result)

                st.image([baseline_img, test_img], caption=["Baseline", "Test"])
                if compare_result.get("diff_heatmap_path"):
                    st.image(
                        compare_result["diff_heatmap_path"],
                        caption="Difference overlay (averaged baseline/test with red tint where structure differs)",
                    )
                st.write(compare_result)
                st.write("AI Analysis:")
                st.write(llm_output)

            if results:
                _, report_xlsx = generate_report(results)
                st.caption(
                    "Download includes **Excel (.xlsx)** with screenshots embedded as images "
                    "(not base64). Plain CSV cannot embed binary pictures in cells."
                )
                st.download_button(
                    "Download Report (Excel)",
                    report_xlsx,
                    "report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
