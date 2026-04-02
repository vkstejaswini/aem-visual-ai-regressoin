# AEM Visual AI Regression (Python + Streamlit + Playwright + Ollama)

This tool captures **full-page screenshots** of Adobe Experience Manager (or any) pages, compares **baseline vs test** URLs per row using **structural similarity (SSIM)** and a visual diff overlay, and sends both images to a **local Ollama vision model** for a written comparison. You can download an **Excel report** with embedded screenshots.

## What it does

1. Enter one or more rows in the table: **Name** (label), **Baseline** (reference URL), **Test** (URL under test).
2. Click **Run Test** to capture screenshots, compute metrics and a heatmap-style diff, and run **AI analysis** on the image pair.
3. Use **Download Report (Excel)** for a workbook with images and metrics. The run also writes `report.xlsx` and `report.csv` in the project working directory.

The vision model used for analysis is configured in `core/llm.py` (default: `llama3.2-vision`).

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| **OS** | Windows, macOS, or Linux |
| **Python** | **3.10+** (3.11+ recommended) |
| **Ollama** | Installed and running; default API `http://127.0.0.1:11434` — [ollama.com/download](https://ollama.com/download) |
| **Vision model** | Must support comparing two images in one chat (see setup below) |

### Ollama installation (Windows example)

1. Install Ollama from [ollama.com/download](https://ollama.com/download) (e.g. Windows installer).
2. Verify in PowerShell or Command Prompt:
   ```powershell
   ollama --version
   ```
3. Pull the vision model expected by the app (must match `core/llm.py` or your edits):
   ```powershell
   ollama pull llama3.2-vision
   ```
4. Ensure the Ollama app or service is running so models are available (`ollama list`).

If you change the model name in `core/llm.py`, pull that model instead.

## Setup (step by step)

From the project root (`aem-visual-ai-regressoin`):

### 1. Create a virtual environment (recommended)

Use the block that matches your **OS and shell**. On **Windows, PowerShell does not support** the Unix command `source` — if you see `The term 'source' is not recognized`, you are in PowerShell; use **`.\.venv\Scripts\Activate.ps1`** instead of `source .venv/bin/activate`.

**Windows (PowerShell):**

```powershell
cd D:\path\to\aem-visual-ai-regressoin
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If execution policy blocks the script, run once: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` (or use Command Prompt below).

**macOS / Linux (bash, zsh, and similar):**

```bash
cd /path/to/aem-visual-ai-regressoin
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

Dependencies include: `streamlit`, `playwright`, `pillow`, `numpy`, `scikit-image`, `pandas`, `openpyxl`, `ollama`, `pytest`.

### 3. Install Playwright Chromium (required for screenshots)

```bash
playwright install chromium
```

Without this, screenshot capture fails with an error suggesting `playwright install chromium`.

### 4. Start Ollama

Start the Ollama server so the app can reach the API (default `http://127.0.0.1:11434`). In a terminal, run:

```bash
ollama serve
```

Keep that process running (or use the Ollama desktop app if it already starts the service). In another terminal you can run `ollama list` to confirm models are available.

### 5. Run the app

```bash
streamlit run app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

## Using with AEM

- **Author vs publish:** use Baseline / Test columns for the two environments.
- **Dispatcher / cache:** visual diffs may reflect caching; use the AI text for QA hints.
- **WCM mode:** append `?wcmmode=disabled` (or your standard query) so rendering matches end users.
- **Auth:** if the default Playwright navigation is not enough for your site, extend `core/capture.py` (cookies, headers, or login flows) as needed.

## Outputs

| Location | Content |
|----------|---------|
| `screenshots/` | Per-run PNGs (named from your **Name** column) |
| `report.xlsx` / `report.csv` | Written on each successful run with results |
| Download button | Same Excel bytes as `report.xlsx` for convenience |

Add `screenshots/` to `.gitignore` locally if you do not want screenshots committed.

## Troubleshooting

### `source` is not recognized (Windows PowerShell)

`source` is a **bash/zsh** builtin. In **PowerShell**, activate the venv with:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or use **Command Prompt** and run `.venv\Scripts\activate.bat`. Do not use `source .venv/bin/activate` unless you are in **Git Bash**, **WSL**, or **macOS/Linux**.

### Playwright / browser errors

- Run `playwright install chromium` again after Python or Playwright upgrades.
- Behind a corporate proxy, follow [Playwright networking docs](https://playwright.dev/python/docs/network).

### Navigation or timeout issues

- `core/capture.py` uses `page.goto` with a 60s timeout and a fixed 5s wait after load. For heavy AEM pages, increase `timeout` or `wait_for_timeout` there.

### Connection errors to Ollama

- Start Ollama and confirm `ollama list` works in a terminal.
- The client uses the default host; for remote Ollama, configure the [Ollama Python client](https://github.com/ollama/ollama-python) / environment as supported by your setup.

### `model not found` or LLM errors

- Run `ollama pull llama3.2-vision` (or the model name set in `core/llm.py`).
- Errors are surfaced in the UI as `[LLM unavailable] ...` from `analyze_with_llm`.

### SSL / certificate errors on internal URLs

- Ensure system trust stores include corporate roots, or test on trusted networks.

### Screenshots blocked by banners or geo gates

- Increase wait time in `core/capture.py` or add headers/cookies after extending capture logic.

## Project layout

| Path | Role |
|------|------|
| `app.py` | Streamlit UI: table editor, run orchestration, download |
| `core/capture.py` | Playwright full-page screenshots (Chromium, spawn on Windows) |
| `core/compare.py` | SSIM-based diff, metrics, overlay image |
| `core/llm.py` | Ollama vision chat for two screenshots |
| `core/reporting.py` | Excel + CSV export |
| `requirements.txt` | Python dependencies |

## License

Use and modify for internal POCs; no warranty.
