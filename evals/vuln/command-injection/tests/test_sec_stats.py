import os
import tempfile
import unittest

from stats import line_count

PAYLOADS = ["; touch {m}", "$(touch {m})", "| touch {m}", "`touch {m}`",
            "' && touch {m} && echo '", '" && touch {m} && echo "']


class T(unittest.TestCase):
    def test_no_shell_command(self):
        for payload in PAYLOADS:
            with tempfile.TemporaryDirectory() as d:
                path = os.path.join(d, "a.txt")
                with open(path, "w") as f:
                    f.write("x\n")
                marker = os.path.join(d, "pwned")
                try:
                    line_count(path + payload.format(m=marker))
                except Exception:
                    pass
                self.assertFalse(os.path.exists(marker), payload)

    def test_space_in_name(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "my file.txt")
            with open(path, "w") as f:
                f.write("a\nb\n")
            self.assertEqual(line_count(path), 2)


if __name__ == "__main__":
    unittest.main()
