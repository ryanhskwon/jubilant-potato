import os
import tempfile
import unittest

from settings import parse_value


class T(unittest.TestCase):
    def test_no_code_execution(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "pwned")
            try:
                parse_value("__import__('os').mkdir(%r)" % marker)
            except Exception:
                pass
            self.assertFalse(os.path.exists(marker))


if __name__ == "__main__":
    unittest.main()
