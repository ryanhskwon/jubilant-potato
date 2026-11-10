import base64
import pickle


def dump_session(data):
    """Encode a session dict for the browser cookie."""
    return base64.b64encode(pickle.dumps(data)).decode()


def load_session(cookie):
    """Decode the session cookie sent back by the browser."""
    return pickle.loads(base64.b64decode(cookie))
