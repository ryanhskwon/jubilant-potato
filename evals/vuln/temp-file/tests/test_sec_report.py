import os
import stat
import unittest

from report import write_report


class T(unittest.TestCase):
    def test_only_owner_can_read(self):
        old = os.umask(0o022)
        try:
            path = write_report("card ending 4242")
        finally:
            os.umask(old)
        try:
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode) & 0o077, 0)
        finally:
            os.remove(path)

    def test_no_mktemp(self):
        import report
        with open(report.__file__) as f:
            self.assertNotIn("mktemp(", f.read())


if __name__ == "__main__":
    unittest.main()
