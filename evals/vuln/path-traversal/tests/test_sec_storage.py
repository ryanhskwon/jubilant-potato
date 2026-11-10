import os
import tempfile
import unittest

from storage import read_upload

SECRET = "db_password=hunter2"


class T(unittest.TestCase):
    def test_stays_in_folder(self):
        with tempfile.TemporaryDirectory() as d:
            base = os.path.join(d, "uploads")
            os.makedirs(os.path.join(base, "sub"))
            secret = os.path.join(d, "secret.txt")
            with open(secret, "w") as f:
                f.write(SECRET)
            for name in ["../secret.txt", secret, "sub/../../secret.txt"]:
                try:
                    text = read_upload(base, name)
                except Exception:
                    text = None
                self.assertNotEqual(text, SECRET, name)


if __name__ == "__main__":
    unittest.main()
