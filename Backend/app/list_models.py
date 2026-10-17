"""Run: python -m app.list_models  -- shows Gemma models your key can access."""
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
found = False
for m in client.models.list():
    if "gemma" in m.name.lower():
        found = True
        print(m.name, "| actions:", getattr(m, "supported_actions", None), "| inputs:", getattr(m, "input_token_limit", None))
if not found:
    print("No Gemma models visible to this key.")
