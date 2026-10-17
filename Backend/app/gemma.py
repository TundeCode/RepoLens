"""All Gemma 4 interactions live here."""
import json
import os
import re

DEFAULT_MODEL = "gemma-4-26b-a4b-it"  # documented Gemma 4 ids: gemma-4-26b-a4b-it, gemma-4-31b-it


class GemmaError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def model_name() -> str:
    name = os.getenv("GEMMA_MODEL") or DEFAULT_MODEL
    if not name.startswith("gemma-4"):
        raise GemmaError(f"GEMMA_MODEL must be a Gemma 4 model, got '{name}'", 500)
    return name


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in response")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object")
    return data


def generate_text(prompt: str, image: tuple[bytes, str] | None = None) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise GemmaError("GEMINI_API_KEY is not set on the server", 503)
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=key)
        contents = [types.Part.from_bytes(data=image[0], mime_type=image[1]), prompt] if image else prompt
        resp = client.models.generate_content(model=model_name(), contents=contents)
        return resp.text or ""
    except GemmaError:
        raise
    except Exception as e:  # SDK errors carry an HTTP-like .code
        code = getattr(e, "code", None)
        if code == 429:
            raise GemmaError("Gemma rate limit reached, try again shortly", 429)
        raise GemmaError(f"Model request failed: {e}", 502)


def generate_json(prompt: str, image: tuple[bytes, str] | None = None) -> dict:
    """Prompt-level JSON (not API JSON mode, which Gemma may not support); one retry on bad output."""
    for attempt in range(2):
        text = generate_text(prompt if attempt == 0 else prompt + "\n\nReturn ONLY valid JSON.", image)
        try:
            return parse_json(text)
        except ValueError:
            continue
    raise GemmaError("Model returned invalid JSON twice", 502)