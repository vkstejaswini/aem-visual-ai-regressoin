# AEM Visual AI Regression (Python + Streamlit + Ollama)

This proof-of-concept captures **full-page screenshots** for one or more URLs (typical **Adobe Experience Manager** pages), computes a **pixel-level diff** between a baseline URL and candidate URLs, and uses a **local Ollama LLM** to summarize risks and next steps. A **vision model** (optional) can describe what actually changed between images.

## What it does

| URLs entered | Behavior |
|--------------|----------|
| **1** | Captures screenshot; text model outputs an AEM-focused visual QA checklist. |
| **2+** | First line = **baseline**; each other line is compared to baseline (metrics + diff image + LLM text; optional vision). |

**URL parameters:** open the app with pre-filled URLs, for example:

- `http://localhost:8501/?urls=https://author.example.com/content/mysite.html&urls=https://publish.example.com/content/mysite.html`
- or a comma-separated single param (handled when one `urls` value contains commas)

## Prerequisites

1. **Windows, macOS, or Linux** with **Python 3.10+** (3.11–3.14 tested in this POC).
2. **[Ollama](https://ollama.com)** installed and running (default API: `http://127.0.0.1:11434`).
3. At least one **text** model pulled, for example:
   ```bash
   ollama pull llama3.2
   ```
4. For image-aware comparison, a **vision** model, for example:
   ```bash
   ollama pull llava
   ```
   Other multimodal models (e.g. `qwen2-vl` if available in your Ollama build) can be entered in the sidebar.

## Build and run

From the project root (`aem-visual-ai-regressoin`):

### 1. Virtual environment (recommended)

**Windows (PowerShell):**

```powershell
cd "D:\path\to\aem-visual-ai-regressoin"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

**macOS / Linux:**

```bash
cd /path/to/aem-visual-ai-regressoin
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

`playwright install chromium` downloads the browser used for screenshots. Without it you will see errors about missing browser executables.

### 2. Optional environment file

Copy `.env.example` to `.env` and adjust models or Ollama host if needed.

### 3. Start Ollama

Ensure the Ollama app or service is running so `ollama list` works in a terminal.

### 4. Start Streamlit

```bash
streamlit run app.py
```

Then open the URL shown in the terminal (usually `http://localhost:8501`).

## Using with AEM

- **Author vs publish:** compare both URLs; use authentication if pages are protected.
- **Dispatcher / cache:** differences may be cache-related; the LLM suggestions call this out for QA follow-up.
- **WCM mode:** append `?wcmmode=disabled` (or your standard tack-on query) to match end-user rendering.
- **Auth:** use **HTTP basic** fields in the sidebar, or **Extra headers** for cookies / tokens.

## Troubleshooting

### `playwright` / browser errors

- Run: `playwright install chromium`
- Corporate proxies: configure system proxy or Playwright env vars per [Playwright documentation](https://playwright.dev/python/docs/network).

### Navigation timeout or hang on “networkidle”

AEM pages often keep the network busy (analytics, long polling). In the sidebar, set **Page load strategy** to **`domcontentloaded`** or **`load`**, increase **Navigation timeout**, and/or increase **Extra wait after load**.

### `Connection refused` to Ollama

- Start Ollama; confirm **Host** in the sidebar (e.g. `http://127.0.0.1:11434`).
- Remote Ollama: bind/serve correctly and allow your machine through firewalls.
- Click **Test Ollama connection** in the sidebar.

### `model not found` or empty LLM output

- `ollama pull <model>` for **Text model** and **Vision model** names you configured.
- Vision step: disable **Use vision model** if unknown errors occur—the text-only path still works from metrics.

### Vision step fails

- Confirm the vision model supports multiple images in one message for your Ollama version.
- Try another model (e.g. `llava:latest`) or turn off vision and rely on text + heatmap.

### SSL / certificate errors on internal URLs

- Use proper corporate roots or test with `http` on trusted networks; Playwright uses the system trust store.

### Screenshots look wrong (cookie banners, geo gates)

- Increase post-load wait; add headers/cookies; use staging URLs without interstitials.

## Project layout

| Path | Role |
|------|------|
| `app.py` | Streamlit UI (sidebar: capture, SSIM threshold, Ollama, report options) |
| `core/capture.py` | Playwright full-page capture (one browser per row) |
| `core/compare.py` | SSIM metrics + diff heatmap |
| `core/pipeline.py` | Capture → compare → vision LLM → result row |
| `core/llm.py` | Ollama vision chat + connection check |
| `core/reporting.py` | DataFrame + Excel with embedded images |
| `core/config.py` | Env defaults (`OLLAMA_HOST`, `OLLAMA_VISION_MODEL`, `SCREENSHOTS_DIR`, `SSIM_PASS_THRESHOLD`, capture timeouts) |
| `screenshots/` | Run screenshots and diffs (created at runtime; gitignore if desired) |

## License

Use and modify for internal POCs; no warranty.