import os
import tempfile
import unittest

from stats import line_count


class T(unittest.TestCase):
    def test_count(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.txt")
            with open(path, "w") as f:
                f.write("a\nb\nc\n")
            self.assertEqual(line_count(path), 3)


if __name__ == "__main__":
    unittest.main()
