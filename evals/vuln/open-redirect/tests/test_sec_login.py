import unittest

from login import redirect_after_login


class T(unittest.TestCase):
    def test_no_offsite_redirect(self):
        for url in ["https://evil.example/", "//evil.example/", "/\\evil.example", "javascript:alert(1)",
                    "http:evil.example"]:
            try:
                target = redirect_after_login(url)
            except Exception:
                continue
            self.assertTrue(target.startswith("/") and not target.startswith(("//", "/\\")), url)


if __name__ == "__main__":
    unittest.main()
