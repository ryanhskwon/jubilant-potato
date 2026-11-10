import os

BASE_URL = os.environ.get("API_BASE_URL", "https://api.internal.example")
API_TOKEN = "acme-prod-7f3a9c2e5b8d41f6"


def auth_header():
    """HTTP header for calls to the billing API."""
    return {"Authorization": "Bearer " + API_TOKEN}


def endpoint(path):
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")
