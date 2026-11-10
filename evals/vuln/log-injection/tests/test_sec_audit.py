import os
import tempfile
import unittest

from audit import log_login


class T(unittest.TestCase):
    def test_one_line_per_attempt(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.log")
            logged = 0
            for name in ["bob\n2026-01-01 00:00:00 login user=admin ok=True",
                         "eve\r2026-01-01 00:00:00 login user=root ok=True"]:
                try:
                    log_login(path, name, False)
                    logged += 1
                except Exception:
                    pass
            lines = []
            if os.path.exists(path):
                with open(path, newline="") as f:
                    lines = f.read().splitlines()
            self.assertEqual(len(lines), logged)


if __name__ == "__main__":
    unittest.main()
