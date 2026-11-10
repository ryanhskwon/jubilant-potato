import os
import tempfile
import unittest

from audit import log_login


class T(unittest.TestCase):
    def test_one_line_per_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.log")
            log_login(path, "bob\n2026-01-01 00:00:00 login user=admin ok=True", False)
            log_login(path, "eve\r2026-01-01 00:00:00 login user=root ok=True", False)
            with open(path, newline="") as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
