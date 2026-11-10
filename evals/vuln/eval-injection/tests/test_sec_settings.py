import os
import tempfile
import unittest

from settings import parse_value

PAYLOADS = [
    "__import__('os').mkdir(%r)",
    "[c for c in ().__class__.__base__.__subclasses__() if c.__name__ == 'catch_warnings'][0]()"
    "._module.__builtins__['__import__']('os').mkdir(%r)",
]


class T(unittest.TestCase):
    def test_no_code_execution(self):
        for payload in PAYLOADS:
            with tempfile.TemporaryDirectory() as d:
                marker = os.path.join(d, "pwned")
                try:
                    parse_value(payload % marker)
                except Exception:
                    pass
                self.assertFalse(os.path.exists(marker), payload)


if __name__ == "__main__":
    unittest.main()
