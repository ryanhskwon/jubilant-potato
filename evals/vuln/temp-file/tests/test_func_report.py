import os
import unittest

from report import write_report


class T(unittest.TestCase):
    def test_write(self):
        path = write_report("total: 42")
        try:
            with open(path) as f:
                self.assertEqual(f.read(), "total: 42")
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
