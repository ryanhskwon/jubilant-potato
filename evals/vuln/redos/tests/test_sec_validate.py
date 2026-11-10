import os
import subprocess
import sys
import unittest


class T(unittest.TestCase):
    def test_long_input_is_fast(self):
        code = "import validate; validate.is_valid_email('a' * 40 + '!')"
        try:
            r = subprocess.run([sys.executable, "-c", code], cwd=os.path.dirname(os.path.abspath(__file__)),
                               timeout=3, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            self.fail("email check took more than 3 seconds on a 41-character input")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
