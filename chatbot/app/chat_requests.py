import os

import requests

API_URL = f"{os.getenv('FASTAPI_BASE_URL', 'http://api')}:{os.getenv('FASTAPI_PORT', '8000')}"


def generate_response(prompt: str) -> dict:
    """Send the prompt to the backend API, which calls the LLM."""
    try:
        r = requests.post(f"{API_URL}/chat", json={"prompt": prompt}, timeout=130)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"success": False, "error": f"Backend error: {e}"}
