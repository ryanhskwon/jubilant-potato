import os

BASE_URL = os.environ.get("API_BASE_URL", "https://api.internal.example")
API_TOKEN = os.environ["API_TOKEN"]


def auth_header():
    return {"Authorization": "Bearer " + API_TOKEN}


def endpoint(path):
    return BASE_URL.rstrip("/") + "/" + path.lstrip("/")
