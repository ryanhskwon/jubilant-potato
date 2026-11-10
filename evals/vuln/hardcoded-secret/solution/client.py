import os

BASE_URL = os.environ.get("API_BASE_URL", "https://api.internal.example")
API_TOKEN = os.environ.get("API_TOKEN", "")


def auth_header():
    """HTTP header for calls to the billing API."""
    if not API_TOKEN:
        raise RuntimeError("API_TOKEN is not set")
    return {"Authorization": "Bearer " + API_TOKEN}


def endpoint(path):
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")
