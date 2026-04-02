import ollama

def analyze_with_llm(img1_path, img2_path):
    try:
        response = ollama.chat(
            model="llama3.2-vision",
            messages=[
                {
                    "role": "user",
                    "content": "Compare these two UI screenshots and describe visual differences in detail",
                    "images": [img1_path, img2_path]
                }
            ]
        )
        return response["message"]["content"]
    except Exception as exc:
        return f"[LLM unavailable] {type(exc).__name__}: {exc}"