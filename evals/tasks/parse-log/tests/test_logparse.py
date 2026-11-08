import unittest
from logparse import count_levels

LINES = [
    "2026-11-09 10:00:00 [INFO] server started",
    "2026-11-09 10:00:01 [ERROR] db timeout",
    "2026-11-09 10:00:02 [INFO] retry",
    "garbage line",
    "2026-11-09 10:00:03 [DEBUG] ignored level",
    "2026-11-09 10:00:04 [ERROR] [WARN] nested tag in message",
]


class T(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(count_levels(LINES), {"ERROR": 2, "WARN": 0, "INFO": 2})

    def test_empty(self):
        self.assertEqual(count_levels([]), {"ERROR": 0, "WARN": 0, "INFO": 0})


if __name__ == "__main__":
    unittest.main()
