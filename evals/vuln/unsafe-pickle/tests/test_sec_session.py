import base64
import os
import pickle
import tempfile
import unittest

from session import load_session


class Evil:
    def __init__(self, path):
        self.path = path

    def __reduce__(self):
        return (os.mkdir, (self.path,))


class T(unittest.TestCase):
    def test_cookie_cannot_run_code(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "pwned")
            cookie = base64.b64encode(pickle.dumps(Evil(marker))).decode()
            try:
                load_session(cookie)
            except Exception:
                pass
            self.assertFalse(os.path.exists(marker))


if __name__ == "__main__":
    unittest.main()
