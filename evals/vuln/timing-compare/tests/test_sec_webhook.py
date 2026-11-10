import unittest

import webhook


class T(unittest.TestCase):
    def test_constant_time_compare(self):
        with open(webhook.__file__) as f:
            self.assertIn("compare_digest", f.read())


if __name__ == "__main__":
    unittest.main()
