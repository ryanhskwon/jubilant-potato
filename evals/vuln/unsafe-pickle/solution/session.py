import base64
import json


def dump_session(data):
    """Encode a session dict for the browser cookie."""
    return base64.b64encode(json.dumps(data).encode()).decode()


def load_session(cookie):
    """Decode the session cookie sent back by the browser."""
    return json.loads(base64.b64decode(cookie))
