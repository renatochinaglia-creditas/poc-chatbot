import os
import requests

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://api")
FAST_API_PORT = os.getenv("FASTAPI_PORT", "8000")
CHAT_URL = f"{FASTAPI_BASE_URL}:{FAST_API_PORT}/ask"


def generate_response(prompt: str) -> str:
    """
    Send a prompt to the API and return the response.
    Returns a dictionary with success status and message/error.
    """
    try:
        response = requests.get(CHAT_URL, params={"prompt": prompt})
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"API Error (Status {response.status_code}): "
                "See Datadog trace for details",
            }

        return {"success": True, "message": response.text}
    except Exception as e:
        return {
            "success": False,
            "error": f"API Error {str(e)}: See Datadog trace for details",
        }

