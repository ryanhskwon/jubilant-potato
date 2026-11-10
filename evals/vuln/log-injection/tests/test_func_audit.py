import os
import tempfile
import unittest

from audit import log_login


class T(unittest.TestCase):
    def test_line(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.log")
            log_login(path, "bob", True)
            with open(path) as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("user=bob", lines[0])
            self.assertIn("ok=True", lines[0])


if __name__ == "__main__":
    unittest.main()
