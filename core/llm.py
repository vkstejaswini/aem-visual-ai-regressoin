from __future__ import annotations

from ollama import Client

from .config import ollama_host, ollama_vision_model


def describe_ollama_connection(host: str | None = None) -> str:
    """Short status string for UI diagnostics (lists model names when reachable)."""
    base = host if host is not None else ollama_host()
    try:
        client = Client(host=base)
        names = [m.model for m in client.list().models if m.model]
        if not names:
            return "Connected; no models reported."
        return "Connected: " + ", ".join(names[:12]) + (
            "…" if len(names) > 12 else ""
        )
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def analyze_with_llm(
    img1_path: str,
    img2_path: str,
    *,
    host: str | None = None,
    model: str | None = None,
) -> str:
    base = host if host is not None else ollama_host()
    mdl = model if model is not None else ollama_vision_model()
    try:
        client = Client(host=base)
        response = client.chat(
            model=mdl,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Compare these two UI screenshots and describe "
                        "visual differences in detail. Focus on layout, "
                        "content, and regressions relevant to web/CMS QA."
                    ),
                    "images": [img1_path, img2_path],
                }
            ],
        )
        return response["message"]["content"]
    except Exception as exc:
        return f"[LLM unavailable] {type(exc).__name__}: {exc}"
